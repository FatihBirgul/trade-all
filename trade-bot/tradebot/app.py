"""Servis dongusu: tara -> sinyal -> risk kapisi -> emir -> pozisyon yonetimi.

Zamanlayicilar `run()` icindedir; `on_bar_close`, `manage_tick` ve `heartbeat` tek tek cagrilabilir
oldugu icin testler gercek saat ve ag olmadan tum akisi calistirir.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from .config import BotSettings, Settings
from .execution.executor import Executor
from .execution.reconcile import reconcile
from .store.repo import Trade
from .exness import schema
from .exness.errors import ExnessAuthError, ExnessError, ExnessRateLimited, ExnessUnavailable
from .exness.schema import Account, AccountState, Instrument
from .exness.stream import Stream
from .manager.manage import MoveSL, NoOp, PartialClose, decide
from .market.candles import CandleStore
from .market.catalog import InstrumentCatalog
from .market.quotes import QuoteBook
from .risk.portfolio import check_entry
from .signals import v9
from .signals.adapter import Candidate, evaluate
from .signals.provider import ExnessV9Provider
from .store.repo import BotState, Repo

log = logging.getLogger(__name__)

FRAMES = ("M15", "H1", "H4")
BAR_SECONDS = 900
BAR_DELAY = 5.0  # mumun broker tarafinda kesinlesmesi icin kapanistan sonra bekleme
MANAGE_INTERVAL = 2.0
HEARTBEAT_INTERVAL = 30.0
RESOLVE_INTERVAL = 10.0
STREAM_ALERT_AFTER = 60.0
QUOTE_MAX_AGE = 60.0
EQUITY_SAMPLE_INTERVAL = 300.0
RECONCILE_INTERVAL = 300.0  # olay kacirilmis olabilir: broker durumu duzenli olarak yeniden okunur
AUTH_BACKOFF = 300.0  # kimlik reddinden sonra yonetim istekleri bu kadar sure durur
STOP_GRACE = 5.0  # dolumdan sonra SL/TP emrinin gorulmesi icin taninan sure
STOP_RECHECK = 30.0
TICK_CHUNK = 20


@dataclass
class ScanSummary:
    at: float
    scanned: int = 0
    closed: int = 0  # piyasasi kapali oldugu icin sessizce atlanan semboller
    candidates: int = 0
    opened: int = 0
    blocked: int = 0
    errors: int = 0
    skipped: str | None = None
    reasons: dict[str, int] = field(default_factory=dict)
    blocked_reasons: dict[str, int] = field(default_factory=dict)


def _default_stream_factory(client, path, on_message, name):
    return Stream(client, path, on_message, name=name)


class Bot:
    def __init__(self, settings: Settings, client, repo: Repo, notifier, clock: Callable[[], float] = time.time,
                 *, stream_factory=None, sleep=asyncio.sleep):
        self.settings = settings
        self.client = client
        self.repo = repo
        self.notifier = notifier
        self._clock = clock
        self._sleep = sleep
        self._stream_factory = stream_factory or _default_stream_factory
        self.catalog = InstrumentCatalog(client)
        self.quotes = QuoteBook(clock=clock)
        self.candles = CandleStore(repo.conn, client, self.catalog, clock=clock)
        self.account: Account | None = None
        self.provider = ExnessV9Provider(self.catalog, self.candles, self.quotes, lambda: self.account)
        self.executor = Executor(client, repo, notifier, self.catalog, clock=clock,
                                 on_auth_error=self._auth_error)
        self.streams: list = []
        self.started = False
        self._details: dict | None = None
        self._tick_stream = None
        self._subscribed: set[str] = set()
        self._connection_alerted = False
        self._daily_blocked = False
        self._last_equity_sample = 0.0
        self._limits = schema.Limits()
        self._events_stream = None
        self._event_connections = 0
        self._auth_alerted = False
        self._auth_blocked_until = 0.0
        self._stop_checked: dict[str, float] = {}
        self._dry_logged: dict[str, str] = {}

    # ------------------------------------------------------------------ kayit ve bildirim
    async def _record(self, level: str, kind: str, message: str, data: dict | None = None, *,
                      notify: bool = False, title: str | None = None) -> None:
        self.repo.add_event(level, kind, message, data)
        log.log({"error": logging.ERROR, "warning": logging.WARNING}.get(level, logging.INFO), "%s: %s", kind, message)
        if notify and self.notifier is not None:
            try:
                await self.notifier.send(kind, title or kind, message, data)
            except Exception:
                log.exception("bildirim gonderilemedi: %s", kind)

    # ------------------------------------------------------------------ acilis
    async def start(self) -> None:
        """limitler -> katalog -> hesap -> mutabakat -> akislar."""
        v9.load_v9(self.settings.v9_root)
        account_id = self.client.account_id
        await self.client.resolve_host()
        self._limits = schema.parse_limits(await self.client.get(schema.limits_path(account_id)))
        if self._limits.global_rate or self._limits.methods:
            self.client.limiter.configure(global_rate=self._limits.global_rate, methods=self._limits.methods)
        if self._limits.max_candles:
            self.candles.max_candles = self._limits.max_candles
        catalog_errors = await self.catalog.refresh()
        self._details = await self.client.get(schema.account_path(account_id))
        snapshot = schema.parse_snapshot(await self.client.get(schema.snapshot_path(account_id)))
        self._set_account(snapshot.account)
        now = self._clock()
        state = self.repo.bot_state()
        if state.start_capital is None and self.account is not None:
            # Toplam kayip siniri botun ilk calistigi andaki sermayeye gore olculur (spec §6.3).
            self.repo.set_bot_state(start_capital=self.account.equity, start_at=now)
        report = await reconcile(self.client, self.repo, self.catalog, clock=self._clock, snapshot=snapshot)
        await self.executor.publish(report)
        self._open_streams()
        self.started = True
        universe = self.catalog.universe(self.repo.get_bot_settings().enabled_symbols)
        await self._record("info", "bot_started", f"Bot başladı: {len(universe)} sembol izleniyor",
                           {"universe": len(universe), "catalog_errors": len(catalog_errors),
                            "dry_run": self.repo.get_bot_settings().dry_run})

    def _set_account(self, state: AccountState | None) -> None:
        if state is None or self._details is None:
            return
        try:
            self.account = schema.parse_account(self._details, state)
        except ValueError as exc:
            log.warning("hesap durumu okunamadi: %s", exc)

    def _tick_symbols(self) -> list[str]:
        """Evren + acik islemlerin sembolleri (broker adlariyla). Donusum pariteleri evrenin icindedir."""
        names = {i.broker_symbol for i in self.catalog.universe()}
        for trade in self.repo.open_trades():
            try:
                names.add(self.catalog.get(trade.symbol).broker_symbol)
            except KeyError:
                continue
        return sorted(names)

    def _open_streams(self) -> None:
        account_id = self.client.account_id
        ticks = self._stream_factory(self.client, schema.ticks_ws_path(account_id), self.on_tick_message, "ticks")
        symbols = self._tick_symbols()
        rate = self._limits.tick_subscription_rate
        chunk = max(1, min(TICK_CHUNK, rate[2])) if rate else 10
        ticks.subscription_delay = (rate[1] * chunk / rate[0] * 1.1) if rate else 1.0
        ticks.set_subscriptions([schema.subscribe_ticks(f"ticks-{i // chunk}", symbols[i:i + chunk])
                                 for i in range(0, len(symbols), chunk)])
        self._subscribed = set(symbols)
        events = self._stream_factory(self.client, schema.events_ws_path(account_id), self.on_event_message, "events")
        events.subscription_delay = 0.5
        events.set_subscriptions([schema.subscribe_events("events-tx", "transactions"),
                                  schema.subscribe_events("events-account", "account_state"),
                                  schema.subscribe_events("events-instruments", "instruments", ["all"])])
        self._tick_stream = ticks
        self._events_stream = events
        self._event_connections = getattr(events, "connections", 0)
        self.streams = [ticks, events]

    def streams_up(self) -> bool:
        return bool(self.streams) and all(s.connected for s in self.streams)

    # ------------------------------------------------------------------ akis mesajlari
    async def on_tick_message(self, raw: dict) -> None:
        tick = schema.parse_tick(raw)
        if tick is None:
            return
        instrument = self.catalog.by_broker(tick.symbol)
        self.quotes.on_tick(dataclasses.replace(tick, symbol=instrument.symbol) if instrument else tick)

    async def on_event_message(self, raw: dict) -> None:
        kind, data = schema.parse_ws_event(raw)
        if kind == "transaction":
            self._set_account(data.account)
            await self.executor.on_transaction(data)
        elif kind == "snapshot":
            # Her (yeniden) baglanmada gelir: kacirilan olaylar icin durum buradan toparlanir.
            self._set_account(data.account)
            await self.executor.reconcile(snapshot=data)
        elif kind == "account":
            self._set_account(data)
        elif kind == "instrument":
            self.catalog.update(data)
        elif kind == "error":
            log.warning("olay akisi hata dondurdu: %s", data)

    # ------------------------------------------------------------------ kar/zarar ve limitler
    def _unrealized(self, origin: str) -> float:
        total = 0.0
        for trade in self.repo.open_trades(origin):
            quote = self.quotes.quote(trade.symbol)
            if quote is None:
                continue
            price = quote["bid"] if trade.side == "BUY" else quote["ask"]
            total += self.provider.pnl(trade.symbol, trade.side, trade.volume, trade.entry, price) or 0.0
        return total

    def _day_start(self) -> float:
        return float(int(self._clock() // 86400) * 86400)  # gun siniri UTC 00:00

    def bot_pnl(self, state: BotState | None = None) -> tuple[float, float]:
        """(bugun, toplam): botun gerceklesen + acik kar/zarari."""
        state = state or self.repo.bot_state()
        floating = self._unrealized("bot")
        return (self.repo.bot_realized_pnl(since=self._day_start()) + floating,
                self.repo.realized_pnl("bot", after=state.start_at) + floating)  # taban anindan sonrasi

    async def _halt(self, reason: str) -> None:
        if self.repo.bot_state().halted:
            return
        self.repo.set_bot_state(halted=True, halt_reason=reason)
        await self._record("error", "bot_halted", f"Bot durdu: {reason}. Devam için uygulamadan onay gerekli.",
                           {"reason": reason}, notify=True, title="Bot durdu")

    async def _check_limits(self, settings: BotSettings) -> None:
        state = self.repo.bot_state()
        if state.start_capital is None and self.account is not None:
            # Acilista hesap okunamadiysa taban ilk firsatta kurulur; yoksa bot hic islem acamaz.
            self.repo.set_bot_state(start_capital=self.account.equity, start_at=self._clock())
            state = self.repo.bot_state()
        capital = state.start_capital
        if not capital or capital <= 0:
            return
        today, total = self.bot_pnl(state)
        if not state.halted and total <= -settings.risk.total_loss_pct / 100.0 * capital:
            await self._halt(f"toplam kayıp sınırı (%{settings.risk.total_loss_pct:g}) aşıldı")
        self._daily_blocked = today <= -settings.risk.daily_loss_pct / 100.0 * capital
        if self._daily_blocked:
            day = datetime.fromtimestamp(self._day_start(), timezone.utc).strftime("%Y-%m-%d")
            if self.repo.get_setting("daily_limit_day") != day:
                self.repo.set_setting("daily_limit_day", day)
                await self._record("warning", "daily_limit",
                                   f"Günlük kayıp sınırı (%{settings.risk.daily_loss_pct:g}) doldu; "
                                   "bugün yeni bot işlemi açılmayacak.",
                                   {"pnl_today": today}, notify=True, title="Günlük limit doldu")

    # ------------------------------------------------------------------ tarama
    def _is_open(self, instrument: Instrument, now: float) -> bool:
        from forex.sessions import broker_status

        if not instrument.trading_hours:
            return False
        status = broker_status(datetime.fromtimestamp(now, timezone.utc), instrument.symbol, True,
                               instrument.trading_hours)
        return status["status"] in ("OPEN", "CLOSING_SOON")

    def _commission(self, instrument: Instrument, settings: BotSettings) -> float:
        """Lot basina gidis-donus komisyon (hesap para birimi): ayar ile enstrumanin bildirdiginden buyuk olan."""
        derived = 0.0
        if instrument.commission_value and instrument.commission_type in ("per_lot_per_side", "per_lot_per_trade"):
            currency = instrument.commission_currency or "USD"
            bounds = self.provider.rates.bounds(currency, self.account.currency) if self.account else None
            if bounds:
                derived = abs(instrument.commission_value) * 2 * bounds[1]
        return max(settings.commission_per_lot, derived)

    async def _refresh_open_candles(self, already: set[str]) -> None:
        """Iz suren stop icin acik islemlerin M15 mumlari, tarama yapilmasa da guncel kalmali."""
        for trade in self.repo.open_trades():
            if trade.symbol in already:
                continue
            already.add(trade.symbol)
            try:
                self.catalog.get(trade.symbol)
                await self.candles.get(trade.symbol, "M15", 64)
            except (ExnessError, ValueError, KeyError):
                continue

    async def _skip(self, summary: ScanSummary, reason: str) -> ScanSummary:
        summary.skipped = reason
        if reason != "stream_down":
            await self._refresh_open_candles(set())
        await self._record("info", "scan_skipped", f"Tarama yapılmadı: {_SKIP.get(reason, reason)}", {"reason": reason})
        return summary

    async def _auth_error(self, exc: ExnessError) -> None:
        """Kimlik reddi: tek olay + tek bildirim; duzelene kadar yonetim istekleri de durur (dongu yok)."""
        self._auth_blocked_until = self._clock() + AUTH_BACKOFF
        if self._auth_alerted:
            log.error("kimlik dogrulamasi hala reddediliyor: %s", exc)
            return
        self._auth_alerted = True
        await self._record(
            "error", "auth_error",
            f"Exness kimlik doğrulaması reddedildi: {exc}. Sunucu saatini (NTP) ve API anahtarını kontrol edin.",
            {"code": exc.code}, notify=True, title="API erişimi reddedildi")

    async def _auth_ok(self) -> None:
        if self._auth_alerted:
            self._auth_alerted = False
            self._auth_blocked_until = 0.0
            await self._record("info", "auth_restored", "Exness kimlik doğrulaması yeniden çalışıyor.")

    async def on_bar_close(self, tf: str = "M15") -> ScanSummary:
        now = self._clock()
        summary = ScanSummary(at=now)
        self.repo.set_bot_state(last_scan_at=now)
        settings = self.repo.get_bot_settings()
        await self._check_limits(settings)
        state = self.repo.bot_state()
        if state.halted:
            return await self._skip(summary, "halted")
        if state.stopped:
            return await self._skip(summary, "stopped")
        if not self.streams_up():
            return await self._skip(summary, "stream_down")  # baglanti yokken yeni islem yok (spec §7)
        if self.account is None or not self.account.can_open:
            return await self._skip(summary, "account_blocked")
        if self._daily_blocked:
            return await self._skip(summary, "daily_limit")

        scanned: set[str] = set()
        for instrument in self.catalog.universe(settings.enabled_symbols):
            symbol = instrument.symbol
            if not self._is_open(instrument, now):
                summary.closed += 1  # hafta sonu forex gibi: sessizce atla
                continue
            try:
                for frame in FRAMES:
                    await self.candles.get(symbol, frame, 256)
            except ExnessAuthError as exc:
                await self._auth_error(exc)
                summary.skipped = "auth_error"
                return summary
            except ExnessRateLimited as exc:
                # Limit asildi: bu turu birak, dongude tekrar deneme.
                summary.errors += 1
                summary.skipped = "rate_limited"
                await self._record("warning", "rate_limited", f"İstek limiti doldu; tarama yarıda kesildi ({exc})")
                return summary
            except (ExnessError, ValueError) as exc:
                summary.errors += 1
                log.warning("mumlar alinamadi %s: %s", symbol, exc)
                continue
            scanned.add(symbol)
            await self._auth_ok()
            result = evaluate(self.provider, symbol, equity=self.account.equity, risk_pct=settings.risk.risk_pct,
                              commission_per_lot=self._commission(instrument, settings),
                              enabled_strategies=settings.enabled_strategies, now=now)
            summary.scanned += 1
            await asyncio.sleep(0)  # analiz islemciyi tutar; pozisyon yonetimine sira ver
            if result.candidate is None:
                summary.reasons[result.decision] = summary.reasons.get(result.decision, 0) + 1
                log.info("aday yok %s: %s (%s)", symbol, result.decision, "; ".join(result.reasons))
                continue
            summary.candidates += 1
            await self._consider(result.candidate, instrument, settings, summary)

        await self._refresh_open_candles(scanned)
        await self._record(
            "info", "scan",
            f"Tarama: {summary.scanned} sembol, {summary.candidates} aday, {summary.opened} emir"
            + (f", {summary.closed} kapalı" if summary.closed else ""), dataclasses.asdict(summary))
        return summary

    def _with_tp2(self, candidate: Candidate, instrument: Instrument, settings: BotSettings) -> Candidate:
        multiple = settings.manage.tp2_r
        if abs(multiple - 3.0) < 1e-9:
            return candidate  # V9 plani zaten 3R
        sign = 1.0 if candidate.side == "BUY" else -1.0
        raw = candidate.entry + sign * multiple * abs(candidate.entry - candidate.stop_loss)
        quantum = Decimal(str(instrument.tick_size))
        units = (Decimal(str(raw)) / quantum).to_integral_value(rounding=ROUND_CEILING if sign > 0 else ROUND_FLOOR)
        return dataclasses.replace(candidate, take_profit_2=float(units * quantum))

    async def _consider(self, candidate: Candidate, instrument: Instrument, settings: BotSettings,
                        summary: ScanSummary) -> None:
        if self.executor.already_submitted(candidate):
            return  # ayni mum ikinci kez tarandi
        state = self.repo.bot_state()
        today, total = self.bot_pnl(state)
        # Islem satiri ancak dolum olayiyla olusur. Ayni taramada gonderilmis ama henuz dolmamis
        # emirler de acik sayilir; yoksa tek mumda birden cok aday limitleri asar.
        in_flight = [Trade(position_id="pending:" + o["idempotency_key"], origin="bot",
                           symbol=o["payload"].get("symbol") or "", side=o["payload"].get("side") or "BUY",
                           volume=0.0, entry=o["payload"].get("entry") or 0.0)
                     for o in self.executor.pending_opens("bot")]
        verdict = check_entry(candidate, open_bot=self.repo.open_trades("bot") + in_flight, bot_pnl_today=today,
                              bot_pnl_total=total, start_capital=state.start_capital,
                              halted=state.halted or state.stopped, settings=settings.risk,
                              instruments=self.catalog.as_mapping())
        if verdict.should_halt:
            await self._halt(verdict.reason)
        if not verdict.allowed:
            summary.blocked += 1
            summary.blocked_reasons[verdict.reason] = summary.blocked_reasons.get(verdict.reason, 0) + 1
            log.info("aday engellendi %s %s: %s", candidate.symbol, candidate.side, verdict.reason)
            return
        candidate = self._with_tp2(candidate, instrument, settings)
        data = {**dataclasses.asdict(candidate), "dry_run": settings.dry_run}
        text = (f"{candidate.symbol} {candidate.side} {candidate.lots:g} lot @ {candidate.entry:g}, "
                f"SL {candidate.stop_loss:g}, TP {candidate.take_profit_2:g} ({candidate.strategy_id})")
        if settings.dry_run:
            await self._record("info", "signal", "[dry-run] " + text, data)  # kaydet, emir gonderme
            return
        await self._record("info", "signal", text, data)
        try:
            key = await self.executor.open(candidate, "bot")
        except ValueError as exc:  # istek kurulamadi (or. hacim sinir disi): bu adayi birak, taramaya devam
            await self._record("warning", "signal_invalid", f"{candidate.symbol} emri kurulamadı: {exc}",
                               {"symbol": candidate.symbol})
            return
        order = self.repo.get_order(key)
        if order is not None and order["state"] != "REJECTED":
            summary.opened += 1

    # ------------------------------------------------------------------ pozisyon yonetimi
    def _atr(self, symbol: str) -> float | None:
        from forex.core import atr

        bars = self.candles.cached(symbol, "M15", 64)
        return atr(bars) if len(bars) >= 15 else None

    def _cost_per_unit(self, instrument: Instrument, settings: BotSettings) -> float:
        """Basa bas seviyesine eklenecek fiyat mesafesi: komisyonun fiyat karsiligi + 1 tick."""
        cost = instrument.tick_size
        commission = self._commission(instrument, settings)
        if commission > 0 and self.account is not None and instrument.contract_size > 0:
            bounds = self.provider.rates.bounds(instrument.currency_profit, self.account.currency)
            if bounds:
                cost += commission / (instrument.contract_size * bounds[0])
        return cost

    async def _guard_stop(self, trade: Trade, quote: dict, now: float) -> bool:
        """Broker'da onaylanmis SL'i olmayan pozisyonu yakalar. True: bu turda baska islem yapma.

        Her bot pozisyonunun broker tarafinda SL'i olmalidir. Dolum olayi SL/TP emrini tasimadiysa ya
        da emir sonradan iptal edildiyse once broker'dan dogrulanir; gercekten yoksa stop yeniden
        kurulur, fiyat stop seviyesini coktan gectiyse pozisyon kapatilir.
        """
        if trade.sl is not None and trade.sltp_order_id:
            return False
        if now - trade.opened_at < STOP_GRACE or now - self._stop_checked.get(trade.position_id, 0.0) < STOP_RECHECK:
            return True
        self._stop_checked[trade.position_id] = now
        await self.executor.reconcile()  # goruntu SL/TP emirlerini de getirir
        fresh = self.repo.get_trade(trade.position_id)
        if fresh is None or not fresh.is_open or (fresh.sl is not None and fresh.sltp_order_id):
            return True
        data = {"position_id": fresh.position_id, "symbol": fresh.symbol}
        risk = fresh.initial_risk_r_price
        if not risk:
            await self._record("error", "sl_missing",
                               f"{fresh.symbol} {fresh.side}: broker'da stop yok ve seviye bilinmiyor. "
                               "Uygulamadan SL koyun ya da pozisyonu kapatın.", data, notify=True, title="Stop eksik")
            return True
        buy = fresh.side == "BUY"
        level = fresh.entry - risk if buy else fresh.entry + risk
        price = quote["bid"] if buy else quote["ask"]
        if (price <= level) if buy else (price >= level):
            await self.executor.close(fresh.position_id, user=True)
            await self._record("error", "sl_missing",
                               f"{fresh.symbol} {fresh.side}: broker'da stop yoktu ve fiyat stop seviyesini geçti; "
                               "pozisyon kapatılıyor.", data, notify=True, title="Stop eksik")
        else:
            await self.executor.modify(fresh.position_id, sl=level, tp=fresh.tp2)
            await self._record("error", "sl_missing",
                               f"{fresh.symbol} {fresh.side}: broker'da stop bulunamadı; {level:g} seviyesine "
                               "yeniden kuruluyor.", {**data, "sl": level}, notify=True, title="Stop eksik")
        return True

    async def manage_tick(self) -> None:
        settings = self.repo.get_bot_settings()
        now = self._clock()
        if now < self._auth_blocked_until:
            return  # kimlik reddi suruyor: reddedilecek istekleri gonderme
        for listed in self.repo.open_trades():
            # Onceki pozisyonun istegi beklenirken bu islem bir olayla degismis ya da kapanmis olabilir.
            trade = self.repo.get_trade(listed.position_id)
            if trade is None or not trade.is_open:
                continue
            try:
                instrument = self.catalog.get(trade.symbol)
            except KeyError:
                continue
            quote = self.quotes.quote(trade.symbol)
            if quote is None or now - quote["time"] > QUOTE_MAX_AGE:
                continue  # bayat fiyatla stop tasima
            if (trade.origin == "bot" or trade.manage) and await self._guard_stop(trade, quote, now):
                continue
            if not trade.manage:
                continue
            if not trade.partial_done and trade.initial_volume and trade.volume < trade.initial_volume - 1e-9:
                trade.partial_done = True  # kismi kapama gerceklesmis (olay ya da mutabakat hacmi guncelledi)
                self.repo.update_trade(trade.position_id, partial_done=True)
            actions = decide(trade, bid=quote["bid"], ask=quote["ask"], atr_m15=self._atr(trade.symbol),
                             cost_per_unit=self._cost_per_unit(instrument, settings), instrument=instrument,
                             settings=settings.manage)
            if settings.dry_run:
                # Dry-run: bot hicbir emir gondermez; ne yapacagi yalnizca loglanir.
                described = repr(actions)
                if actions and self._dry_logged.get(trade.position_id) != described:
                    self._dry_logged[trade.position_id] = described
                    log.info("[dry-run] %s %s icin gonderilmeyen yonetim adimi: %s", trade.symbol, trade.side, described)
                continue
            for action in actions:
                if isinstance(action, NoOp):
                    if action.reason == "partial_skipped":
                        self.repo.update_trade(trade.position_id, partial_done=True)
                    continue
                if isinstance(action, MoveSL):
                    # Basa bas isareti ve bildirimi, broker degisikligi onaylayinca yurutucu tarafindan yapilir.
                    await self.executor.modify(trade.position_id, sl=action.price, stage=action.stage)
                elif isinstance(action, PartialClose):
                    await self.executor.close(trade.position_id, volume=action.volume)
                break  # pozisyon basina bir seferde tek istek; sonucu gelince devam edilir

    async def reconcile_now(self) -> None:
        """Broker durumunu REST ile yeniden okur (kacirilan olaylar icin)."""
        report = await self.executor.reconcile()
        if report is not None:
            self._set_account(report.account)

    # ------------------------------------------------------------------ kalp atisi
    async def heartbeat(self) -> None:
        now = self._clock()
        self.repo.set_bot_state(heartbeat_at=now)
        if self.account is not None and now - self._last_equity_sample >= EQUITY_SAMPLE_INTERVAL:
            self._last_equity_sample = now
            self.repo.add_equity(now, self.account.balance, self.account.equity)
        down = max((s.disconnected_for() for s in self.streams), default=0.0)
        if down > STREAM_ALERT_AFTER and not self._connection_alerted:
            self._connection_alerted = True
            await self._record("error", "connection_lost",
                               f"Exness bağlantısı {int(down)} saniyedir yok; yeni işlem açılmıyor.",
                               {"seconds": down}, notify=True, title="Bağlantı koptu")
        elif self._connection_alerted and self.streams_up():
            self._connection_alerted = False
            await self._record("info", "connection_restored", "Exness bağlantısı geri geldi.")
        await self._check_limits(self.repo.get_bot_settings())
        connections = getattr(self._events_stream, "connections", 0)
        if connections != self._event_connections:
            # Olay akisi yeniden baglandi: arada kacirilan olaylar icin durumu broker'dan toparla.
            self._event_connections = connections
            await self.reconcile_now()
        if self._tick_stream is not None:
            missing = [s for s in self._tick_symbols() if s not in self._subscribed]
            if missing:
                self._subscribed.update(missing)
                await self._tick_stream.subscribe(schema.subscribe_ticks(f"ticks-extra-{int(now)}", missing))

    def status(self) -> dict:
        state = self.repo.bot_state()
        settings = self.repo.get_bot_settings()
        day = self._day_start()
        bot_today = self.repo.realized_pnl("bot", since=day) + self._unrealized("bot")
        manual_today = self.repo.realized_pnl("manual", since=day) + self._unrealized("manual")
        account = self.account
        return {
            "currency": account.currency if account else None,
            "balance": account.balance if account else None,
            "equity": account.equity if account else None,
            "margin_free": account.margin_free if account else None,
            "pnl_today": {"bot": bot_today, "manual": manual_today, "total": bot_today + manual_today},
            "open_bot": len(self.repo.open_trades("bot")), "open_manual": len(self.repo.open_trades("manual")),
            "halted": state.halted, "halt_reason": state.halt_reason, "stopped": state.stopped,
            "dry_run": settings.dry_run, "start_capital": state.start_capital,
            "last_scan_at": state.last_scan_at, "heartbeat_at": state.heartbeat_at,
            "stream_connected": self.streams_up(), "started": self.started,
        }

    # ------------------------------------------------------------------ zamanlayicilar
    async def _start_with_backoff(self) -> None:
        """Acilis basarisiz olursa surec cokup yeniden baslamaz (istek dongusu olmasin); bekleyip dener."""
        delay = 10.0
        alerted = False
        while True:
            try:
                await self.start()
                return
            except ExnessAuthError as exc:
                if not alerted:
                    alerted = True
                    await self._auth_error(exc)
                delay = 300.0
            except (ExnessError, ValueError) as exc:
                log.error("acilis basarisiz: %s", exc)
                if not alerted:
                    alerted = True
                    await self._record("error", "startup_failed", f"Bot başlatılamadı: {exc}",
                                       notify=True, title="Bot başlatılamadı")
            await self._sleep(delay)
            delay = min(delay * 2, 300.0)

    async def _every(self, interval: float, action, name: str) -> None:
        while True:
            await self._sleep(interval)
            try:
                await action()
            except asyncio.CancelledError:
                raise
            except Exception:  # tek bir turun hatasi donguyu durdurmamali
                log.exception("%s dongusunde hata", name)

    async def _bar_loop(self) -> None:
        while True:
            now = self._clock()
            boundary = (int(now // BAR_SECONDS) + 1) * BAR_SECONDS + BAR_DELAY
            await self._sleep(max(0.5, boundary - now))
            try:
                await self.on_bar_close()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("tarama dongusunde hata")

    async def run(self) -> None:
        await self._start_with_backoff()
        await asyncio.gather(
            *(stream.run() for stream in self.streams),
            self._bar_loop(),
            self._every(MANAGE_INTERVAL, self.manage_tick, "yonetim"),
            self._every(HEARTBEAT_INTERVAL, self.heartbeat, "kalp atisi"),
            self._every(RESOLVE_INTERVAL, self.executor.resolve_unknown, "emir cozumleme"),
            self._every(RECONCILE_INTERVAL, self.reconcile_now, "mutabakat"),
        )


_SKIP = {"halted": "bot durduruldu (toplam kayıp sınırı)", "stopped": "kullanıcı durdurdu",
         "stream_down": "Exness bağlantısı yok", "account_blocked": "hesap yeni işleme kapalı",
         "daily_limit": "günlük kayıp sınırı doldu"}
