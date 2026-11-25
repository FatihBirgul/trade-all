"""API uc noktalari. `/health` ve `/pair` disinda hepsi Bearer token ister."""

from __future__ import annotations

import asyncio
import math
from decimal import ROUND_FLOOR, Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect

from ..app import QUOTE_MAX_AGE, Bot
from ..config import BotSettings, strategy_mode
from ..signals import custom, scorecard, v9
from ..signals.shadow import ShadowBook
from . import auth
from .models import (CloseAllRequest, CloseRequest, DeviceRequest, ManualTrade, PairRequest, PositionPatch,
                     ResumeRequest, StrategyModeRequest)

MAX_LEVEL_DISTANCE = 0.5  # kullanici SL/TP seviyesi fiyattan en cok bu oranda uzak olabilir
CLOSE_ALL_PHRASE = "CLOSE-ALL"
HEARTBEAT_STALE = 120.0


def build_router(bot: Bot, clock, stream_interval: float) -> APIRouter:
    repo = bot.repo
    public = APIRouter()

    def require_token(authorization: str | None = Header(default=None)) -> None:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not auth.verify_token(repo, token.strip()):
            raise HTTPException(status_code=401, detail="geçersiz ya da eksik token")

    private = APIRouter(dependencies=[Depends(require_token)])

    # ------------------------------------------------------------------ acik uc noktalar
    @public.get("/health")
    async def health():
        state = repo.bot_state()
        fresh = state.heartbeat_at is not None and clock() - state.heartbeat_at <= HEARTBEAT_STALE
        scan = getattr(bot, "last_scan", None)
        # Herkese acik: yalnizca calisma durumu ve sayilar. Bakiye, pozisyon ya da sinyal icermez.
        last_scan = None if scan is None else {
            "at": scan.at, "scanned": scan.scanned, "closed": scan.closed, "errors": scan.errors,
            "skipped": scan.skipped,
            # quoted: taranan sembollerden taze fiyati olanlar. 0 ise akis "bagli" gorunse de fiyat gelmiyor.
            "quoted": scan.quoted, "candle_retries": scan.candle_retries}
        return {"status": "ok" if fresh else "stale", "last_scan_at": state.last_scan_at,
                "heartbeat_at": state.heartbeat_at, "stream_connected": bot.streams_up(), "halted": state.halted,
                "last_scan": last_scan, "tick_errors": getattr(bot, "tick_errors", 0),
                "tick_error": getattr(bot, "tick_error", None), "tick_acks": getattr(bot, "tick_acks", 0),
                # Su an taze fiyati olan evren sembolu sayisi: tarama beklemeden fiyat akisinin calistigini gosterir.
                "quoted_now": bot.quoted_now() if hasattr(bot, "quoted_now") else None}

    @public.get("/health/summary")
    async def health_summary(hours: float = Query(default=24.0, ge=0.25, le=168.0)):
        """Son taramalarin ozeti (canliya gecis karari icin). Herkese acik: yalnizca sayilar, nedenler ve
        ornek adaylarin lot / risk yuzdesi. Hesap numarasi, bakiye ya da para tutari icermez."""
        return bot.scan_summary(hours)

    @public.post("/pair")
    async def pair(body: PairRequest):
        token = auth.redeem_pair_code(repo, body.code, now=clock())
        if token is None:
            raise HTTPException(status_code=401, detail="kod geçersiz ya da süresi dolmuş")
        repo.add_event("info", "device_paired", "Yeni cihaz eşleştirildi")
        return {"token": token}

    # ------------------------------------------------------------------ durum ve pozisyonlar
    @private.get("/status")
    async def status():
        return bot.status()

    def _position(trade) -> dict:
        quote = bot.quotes.quote(trade.symbol)
        price = pnl = multiple = None
        if quote is not None:
            price = quote["bid"] if trade.side == "BUY" else quote["ask"]
            pnl = bot.provider.pnl(trade.symbol, trade.side, trade.volume, trade.entry, price)
            if trade.initial_risk_r_price:
                sign = 1.0 if trade.side == "BUY" else -1.0
                multiple = (price - trade.entry) * sign / trade.initial_risk_r_price
        return {"position_id": trade.position_id, "origin": trade.origin, "symbol": trade.symbol,
                "side": trade.side, "volume": trade.volume, "initial_volume": trade.initial_volume,
                "entry": trade.entry, "sl": trade.sl, "tp1": trade.tp1, "tp2": trade.tp2,
                "strategy_id": trade.strategy_id, "opened_at": trade.opened_at, "manage": trade.manage,
                "user_sl_override": trade.user_sl_override, "be_done": trade.be_done,
                "partial_done": trade.partial_done, "realized_pnl": trade.pnl, "price": price,
                "unrealized_pnl": pnl, "r_multiple": multiple}

    @private.get("/positions")
    async def positions():
        return {"positions": [_position(t) for t in repo.open_trades()]}

    def _open_trade(position_id: str):
        trade = repo.get_trade(position_id)
        if trade is None or not trade.is_open:
            raise HTTPException(status_code=404, detail="açık pozisyon bulunamadı")
        return trade

    def _check_levels(trade, sl: float | None, tp: float | None) -> None:
        """Kullanicinin verdigi SL/TP: yon ve akla yatkinlik. Yazim hatasi (binlik ayrac, eksik hane)
        korumayi fiilen kaldirabilir; broker boyle bir seviyeyi kabul eder ve bot geri almaz."""
        quote = bot.quotes.quote(trade.symbol)
        reference = (quote["bid"] if trade.side == "BUY" else quote["ask"]) if quote else trade.entry
        buy = trade.side == "BUY"
        for name, value, below in (("SL", sl, buy), ("TP", tp, not buy)):
            if value is None:
                continue
            if abs(value - reference) / reference > MAX_LEVEL_DISTANCE:
                raise HTTPException(status_code=422,
                                    detail=f"{name} {value:g} anlık fiyattan ({reference:g}) çok uzak; yazım hatası olabilir")
            if (value >= reference) if below else (value <= reference):
                side = "altında" if below else "üstünde"
                raise HTTPException(status_code=422, detail=f"{name} anlık fiyatın ({reference:g}) {side} olmalı")

    @private.patch("/positions/{position_id}")
    async def patch_position(position_id: str, body: PositionPatch):
        trade = _open_trade(position_id)
        key = None
        if body.sl is not None or body.tp is not None:
            _check_levels(trade, body.sl, body.tp)
            # Kullanicinin koydugu SL: bot bunu zarar yonune geri almaz (user_sl_override).
            key = await bot.executor.modify(position_id, sl=body.sl, tp=body.tp, user=True)
            if key is None:
                raise HTTPException(status_code=409, detail="pozisyonda sonucu beklenen başka bir istek var")
        if body.manage is not None:
            repo.update_trade(position_id, manage=body.manage)  # hedefli guncelleme: baska alanlara dokunmaz
        return {"order": key, "manage": _open_trade(position_id).manage}

    @private.post("/positions/{position_id}/close")
    async def close_position(position_id: str, body: CloseRequest):
        trade = _open_trade(position_id)
        if body.volume is not None and body.volume > trade.volume + 1e-9:
            raise HTTPException(status_code=422, detail="hacim açık pozisyondan büyük")
        key = await bot.executor.close(position_id, volume=body.volume, user=True)
        if key is None:
            raise HTTPException(status_code=409, detail="bu pozisyon için sonucu beklenen bir kapama isteği var")
        return {"order": key}

    # ------------------------------------------------------------------ elle islem
    @private.post("/trades")
    async def manual_trade(body: ManualTrade):
        try:
            instrument = bot.catalog.get(body.symbol)
        except KeyError:
            raise HTTPException(status_code=404, detail="sembol bulunamadı") from None
        if not instrument.tradable:
            raise HTTPException(status_code=409, detail="sembol işleme kapalı")
        if body.client_id is not None:
            previous = repo.get_order(f"man-{body.client_id}")
            if previous is not None:
                # Ayni istek yeniden geldi (uygulama zaman asimi): yeni emir yok, ilk emrin bilgisi doner.
                sent = previous["payload"]
                if sent.get("symbol") != body.symbol or sent.get("side") != body.side:
                    raise HTTPException(status_code=409, detail="bu client_id başka bir emir için kullanıldı")
                return {"order": previous["idempotency_key"], "state": previous["state"], "duplicate": True,
                        "lots": float(sent["body"]["volume"]), "sl": sent.get("sl"), "tp": sent.get("tp2")}
        quote = bot.quotes.quote(body.symbol)
        if quote is None or clock() - quote["time"] > QUOTE_MAX_AGE:
            raise HTTPException(status_code=409, detail="güncel fiyat yok")
        sign = 1.0 if body.side == "BUY" else -1.0
        entry = quote["ask"] if body.side == "BUY" else quote["bid"]
        sl = entry - sign * body.sl_distance
        tp = entry + sign * body.tp_distance if body.tp_distance is not None else None
        if sl <= 0:
            raise HTTPException(status_code=422, detail="SL mesafesi fiyattan büyük")
        lots = body.lots
        if lots is None:
            # Sermaye ve marjin ortak oldugu icin gercek hesap equity'si kullanilir (spec §6.4).
            if bot.account is None:
                raise HTTPException(status_code=409, detail="hesap durumu bilinmiyor")
            try:
                per_lot = abs(bot.provider.loss_for(body.symbol, body.side, 1.0, entry, sl))
            except LookupError:
                raise HTTPException(status_code=409, detail="hesap para birimine dönüşüm kuru yok") from None
            budget = bot.account.equity * repo.get_bot_settings().risk.risk_pct / 100.0
            if per_lot <= 0 or not math.isfinite(per_lot):
                raise HTTPException(status_code=409, detail="lot hesaplanamadı")
            step = Decimal(str(instrument.volume_step))
            units = (Decimal(str(budget / per_lot + 1e-9)) / step).to_integral_value(rounding=ROUND_FLOOR)
            lots = float(min(units * step, Decimal(str(instrument.volume_max))))
        if lots < instrument.volume_min - 1e-12:
            raise HTTPException(status_code=422, detail="en küçük lot risk sınırını aşıyor")
        try:
            key = await bot.executor.open_manual(body.symbol, body.side, lots, sl=sl, tp=tp, price=entry,
                                                 client_id=body.client_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        order = repo.get_order(key)
        return {"order": key, "state": order["state"] if order else None, "lots": lots, "sl": sl, "tp": tp}

    # ------------------------------------------------------------------ durdur / devam
    @private.post("/bot/stop")
    async def stop():
        repo.set_bot_state(stopped=True)
        repo.add_event("warning", "bot_stopped", "Bot durduruldu: yeni işlem açılmayacak, açık işlemler yönetilecek")
        return bot.status()

    @private.post("/bot/resume")
    async def resume(body: ResumeRequest | None = None):
        state = repo.bot_state()
        if state.halted:
            if body is None or not body.confirm_halt:
                raise HTTPException(status_code=409,
                                    detail="toplam kayıp sınırı nedeniyle durdu; devam için confirm_halt=true gerekli")
            # Bilincli devam: olcum tabani sifirlanir, yoksa bot ayni kayip yuzunden hemen yeniden dururdu.
            capital = bot.account.equity if bot.account is not None else state.start_capital
            repo.set_bot_state(halted=False, halt_reason=None, start_capital=capital, start_at=clock())
        repo.set_bot_state(stopped=False)
        repo.add_event("info", "bot_resumed", "Bot devam ediyor" + (" (durma onaylandı)" if state.halted else ""))
        return bot.status()

    @private.post("/bot/close-all")
    async def close_all(body: CloseAllRequest):
        if body.confirm != CLOSE_ALL_PHRASE:
            raise HTTPException(status_code=409, detail=f'onay için confirm="{CLOSE_ALL_PHRASE}" gönderilmeli')
        repo.set_bot_state(stopped=True)  # kapatirken yeni islem acilmasin
        requested, skipped = 0, []
        for trade in repo.open_trades():
            if await bot.executor.close(trade.position_id, user=True) is not None:
                requested += 1
            else:
                skipped.append(trade.position_id)  # zaten bekleyen bir kapama istegi var
        repo.add_event("warning", "close_all", f"Tüm pozisyonlar için kapama istendi ({requested})",
                       {"requested": requested, "skipped": skipped})
        return {"requested": requested, "skipped": skipped, "stopped": True}

    # ------------------------------------------------------------------ ayarlar
    @private.get("/settings")
    async def get_settings():
        return repo.get_bot_settings().model_dump(mode="json")

    @private.put("/settings")
    async def put_settings(body: BotSettings, confirm_live: bool = Query(default=False)):
        previous = repo.get_bot_settings()
        if previous.dry_run and not body.dry_run and not confirm_live:
            # Canli mod gercek para ile emir gonderir. Bu gecis, ayar govdesinden ayri ve acik bir onay
            # ister: eski bir ayar kopyasini geri gonderen ya da baska bir alani degistiren istek botu
            # farkinda olmadan canliya alamaz.
            raise HTTPException(
                status_code=409,
                detail="canlı moda geçiş gerçek emir gönderir; onay için confirm_live=true ile gönderin")
        # Bir stratejiyi canliya almak gercek islem acar ve bilincli onay ister; bu yalnizca
        # POST /strategies/{id}/mode (confirm=true) ile yapilir. Aksi halde eski bir ayar kopyasini
        # geri gonderen istemci, botun duraklattigi stratejiyi farkinda olmadan yeniden acardi.
        revived = sorted(s for s in _strategy_ids()
                         if strategy_mode(body, s) == "live" and strategy_mode(previous, s) != "live")
        if revived:
            raise HTTPException(
                status_code=409,
                detail="strateji bu yoldan canlıya alınamaz (" + ", ".join(revived) + "); güncel ayarları "
                       "yeniden okuyun ya da strateji kipini onaylayarak değiştirin")
        unknown = sorted(set(body.strategy_modes) - _strategy_ids())
        if unknown:
            raise HTTPException(status_code=422, detail="bilinmeyen strateji: " + ", ".join(unknown))
        repo.set_bot_settings(body)
        if previous.dry_run != body.dry_run:
            repo.add_event("warning", "mode_changed",
                           "Canlı moda geçildi: bot gerçek emir gönderecek" if not body.dry_run
                           else "Deneme moduna geçildi: bot emir göndermeyecek", {"dry_run": body.dry_run})
        repo.add_event("info", "settings_changed", "Ayarlar güncellendi", body.model_dump(mode="json"))
        await bot.settings_changed()  # canli moda ilk geciste kayip siniri tabani o andaki varliktan alinir
        return body.model_dump(mode="json")

    # ------------------------------------------------------------------ raporlar ve olaylar
    def _totals(trades) -> dict:
        wins = sum(1 for t in trades if t.pnl > 0)
        return {"pnl": round(sum(t.pnl for t in trades), 10), "trades": len(trades), "wins": wins,
                "win_rate": wins / len(trades) if trades else None}

    def _drawdown(rows) -> float:
        peak = running = worst = 0.0
        for _, pnl in rows:
            running += pnl
            peak = max(peak, running)
            worst = max(worst, peak - running)
        return round(worst, 10)

    def _breakdown(trades, key) -> dict:
        groups: dict[str, dict] = {}
        for trade in trades:
            name = key(trade)
            if name is None:
                continue
            row = groups.setdefault(name, {"pnl": 0.0, "trades": 0, "wins": 0})
            row["pnl"] = round(row["pnl"] + trade.pnl, 10)
            row["trades"] += 1
            row["wins"] += 1 if trade.pnl > 0 else 0
        return groups

    @private.get("/reports")
    async def reports(period: str = Query(default="day", pattern="^(day|week|month)$")):
        closed = repo.closed_trades(limit=5000)
        by_origin = {"bot": [t for t in closed if t.origin == "bot"],
                     "manual": [t for t in closed if t.origin == "manual"], "all": closed}
        return {
            "period": period,
            "totals": {name: _totals(trades) for name, trades in by_origin.items()},
            "periods": {name: repo.pnl_by_period(period, name) for name in ("bot", "manual", "all")},
            "max_drawdown": {"bot": _drawdown(repo.realized_rows("bot")),
                             "manual": _drawdown(repo.realized_rows("manual")),
                             "all": _drawdown(repo.realized_rows())},
            "by_strategy": _breakdown(by_origin["bot"], lambda t: t.strategy_id),
            "by_symbol": _breakdown(closed, lambda t: t.symbol),
            "history": [{"position_id": t.position_id, "origin": t.origin, "symbol": t.symbol, "side": t.side,
                         "entry": t.entry, "close_price": t.close_price, "opened_at": t.opened_at,
                         "closed_at": t.closed_at, "pnl": t.pnl, "strategy_id": t.strategy_id}
                        for t in closed[:200]],
        }

    @private.get("/scorecard")
    async def get_scorecard():
        return scorecard.scorecard(repo, repo.get_bot_settings())

    def _strategy_ids() -> frozenset[str]:
        return v9.builtin_strategy_ids() | custom.strategy_ids()

    def _live_blocker(strategy_id: str, settings: BotSettings) -> str | None:
        """Yeni (V9 disi) strateji ancak golge karnesi olumluysa canliya alinabilir (spec §6.2)."""
        if strategy_id not in custom.strategy_ids():
            return None
        stats = ShadowBook(repo).stats(strategy_id, "shadow")
        need = settings.fusion.pause_min_trades
        if stats["trades"] < need:
            return (f"yeni strateji canlıya alınamaz: en az {need} sonuçlanmış gölge işlem gerekli "
                    f"(şu an {stats['trades']})")
        if not stats["avg_r"] or stats["avg_r"] <= 0:
            return f"yeni strateji canlıya alınamaz: gölge karnesi olumlu değil (ortalama R {stats['avg_r']:.2f})"
        return None

    @private.get("/strategies")
    async def strategies():
        """Tum stratejiler: kaynak, kip, golge karnesi ve canliya alinabilirlik."""
        settings = repo.get_bot_settings()
        book, held = ShadowBook(repo), scorecard.paused(repo)
        rows = []
        for strategy_id in sorted(_strategy_ids()):
            mode = strategy_mode(settings, strategy_id)
            blocker = _live_blocker(strategy_id, settings)
            rows.append({"strategy_id": strategy_id,
                         "source": "custom" if strategy_id in custom.strategy_ids() else "v9", "mode": mode,
                         "paused": strategy_id in held, "shadow": book.stats(strategy_id, "shadow"),
                         "can_go_live": mode != "live" and blocker is None, "live_blocker": blocker})
        return {"strategies": rows}

    @private.post("/strategies/{strategy_id}/mode")
    async def set_strategy_mode(strategy_id: str, body: StrategyModeRequest):
        if strategy_id not in _strategy_ids():
            raise HTTPException(status_code=404, detail="strateji bulunamadı")
        settings = repo.get_bot_settings()
        current = strategy_mode(settings, strategy_id)
        if body.mode == "live" and current != "live":
            if not body.confirm:
                raise HTTPException(status_code=409,
                                    detail="stratejiyi canlıya almak gerçek işlem açar; onay için confirm=true gönderin")
            blocker = _live_blocker(strategy_id, settings)
            if blocker:
                raise HTTPException(status_code=409, detail=blocker)
            if strategy_id in scorecard.paused(repo):
                # Yalnizca botun duraklattigi strateji icin karne denetimi bu andan yeniden baslar.
                # Hic duraklatilmamis stratejiyi kapatip acmak sayaci sifirlamaz.
                scorecard.mark_resumed(repo, strategy_id, clock())
        settings.strategy_modes[strategy_id] = body.mode
        if settings.enabled_strategies is not None and body.mode != "off":
            settings.enabled_strategies.add(strategy_id)
        repo.set_bot_settings(settings)
        repo.add_event("info", "strategy_mode", f"{strategy_id} kipi: {body.mode}",
                       {"strategy_id": strategy_id, "mode": body.mode})
        return {"strategy_id": strategy_id, "mode": body.mode}

    @private.get("/news")
    async def news(hours: int = Query(default=48, ge=1, le=168)):
        """Onumuzdeki yuksek etkili haberler ve takvimin guncelligi."""
        calendar = bot.news
        settings = repo.get_bot_settings().news
        now = clock()
        events = [] if calendar is None else [
            {"currency": e.currency, "title": e.title, "at": e.at, "impact": e.impact}
            for e in calendar.events() if e.impact == "high" and now - settings.window_minutes * 60 <= e.at <= now + hours * 3600]
        return {"enabled": settings.enabled, "window_minutes": settings.window_minutes,
                "fetched_at": calendar.fetched_at() if calendar is not None else None,
                "stale": calendar.stale() if calendar is not None else True, "events": events}

    @private.get("/events")
    async def events(after: int = Query(default=0, ge=0), limit: int = Query(default=200, ge=1, le=500),
                     newest: bool = False):
        # newest=true: en yeni olaylar, yeniden eskiye (uygulamanin ilk acilisi icin).
        return {"events": repo.events(after=after, limit=limit, newest=newest)}

    @private.post("/devices")
    async def register_device(body: DeviceRequest):
        repo.add_device(body.expo_token)
        return {"registered": True}

    # ------------------------------------------------------------------ canli akis
    @public.websocket("/stream")
    async def stream(socket: WebSocket, token: str | None = None):
        header = socket.headers.get("authorization", "")
        supplied = token or (header.partition(" ")[2].strip() if header.lower().startswith("bearer ") else None)
        if not auth.verify_token(repo, supplied):
            await socket.close(code=1008)
            return
        await socket.accept()
        newest = repo.events(limit=1, newest=True)
        last = newest[0]["id"] if newest else 0
        try:
            while True:
                await socket.send_json({"type": "status", "status": bot.status()})
                await asyncio.sleep(stream_interval)
                for event in repo.events(after=last, limit=100):
                    last = event["id"]
                    await socket.send_json({"type": "event", "event": event})
        except (WebSocketDisconnect, RuntimeError):
            return

    public.include_router(private)
    return public
