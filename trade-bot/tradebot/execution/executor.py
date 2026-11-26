"""Emir durum makinesi.

Kurallar:
- Her emir once SQLite'a yazilir, sonra gonderilir. Ayni idempotency anahtari ikinci kez gonderilmez.
- ACK dolum degildir. Sonuc `transaction_event` ile gelir; gelmezse operasyon durumu sorgulanir.
- Sonucu bilinmeyen bir ACMA emri asla yeniden gonderilmez (bayat sinyalle islem acmamak icin);
  broker'daki pozisyonlara ve deal gecmisine bakilarak cozulur.
- Hicbir emir sonsuza dek "bekliyor" kalmaz: sonucu ogrenilemeyen emir bir sure sonra birakilir ve
  gercek durum broker'dan okunur.
- Bu sinif hicbir istegi dongude tekrar denemez; reddedilen degisiklikler icin bekleme suresi vardir.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from ..exness import schema
from ..exness.errors import (ExnessAuthError, ExnessError, ExnessRateLimited, ExnessRejected,
                             ExnessUnavailable)
from ..exness.schema import TxEvent
from ..signals.adapter import Candidate
from ..store.repo import Repo, Trade
from .reconcile import (OPEN_STATES, ReconcileReport, _matching_order, canonical, deal_pnl, fetch_deals,
                        manual_trade, reconcile, risk_distance, trade_from_order)

log = logging.getLogger(__name__)

ACK_TIMEOUT = 10.0  # ACK'ten sonra olay bu kadar surede gelmezse operasyon durumu sorgulanir
UNKNOWN_TIMEOUT = 60.0  # operasyon kimligi olmayan emir bu kadar surede eslesmezse iptal sayilir
ORDER_DEADLINE = 120.0  # sonucu hicbir yoldan ogrenilemeyen emir bu sureden sonra birakilir
CONFIRMED_GIVE_UP = 900.0  # onaylanmis ama pozisyonu hic gorulmeyen emir bu sureden sonra kapatilir
RECOVER_WINDOW_CONFIRMED = 300.0  # onaylanmis emir icin acilis deal'inin aranacagi pencere
RECOVER_WINDOW_UNCONFIRMED = 30.0  # onay yoksa yalnizca emirden hemen sonra acilmis pozisyon eslesir
COOLDOWN = 60.0  # reddedilen degisiklik/kapama sonrasi ayni pozisyon icin bekleme


class Executor:
    def __init__(self, client, repo: Repo, notifier, catalog, *, clock: Callable[[], float] = time.time,
                 on_auth_error: Callable[[ExnessError], Awaitable[None]] | None = None,
                 lot_guard: Callable[[str, str, float, float | None, float | None], None] | None = None):
        self.client = client
        self.repo = repo
        self.notifier = notifier
        self.catalog = catalog
        self._clock = clock
        self._on_auth_error = on_auth_error
        # Mutlak lot tavani (bkz. Bot.lot_guard): asilirsa ValueError verir ve emir KURULMAZ. Bot ve elle acilan
        # butun emirler bu iki yoldan gecer; tavani atlayan baska bir acma yolu yoktur.
        self._lot_guard = lot_guard
        self._cooldown: dict[str, float] = {}

    # ------------------------------------------------------------------ yardimcilar
    async def _notify(self, kind: str, title: str, body: str, data: dict | None = None) -> None:
        if self.notifier is None:
            return
        try:
            await self.notifier.send(kind, title, body, data)
        except Exception:  # bildirim hatasi emir akisini bozmamali
            log.exception("bildirim gonderilemedi: %s", kind)

    async def _record(self, level: str, kind: str, message: str, data: dict | None = None, *,
                      notify: bool = True) -> None:
        self.repo.add_event(level, kind, message, data)
        log.log(logging.ERROR if level == "error" else logging.INFO, "%s: %s", kind, message)
        if notify:
            await self._notify(kind, _TITLES.get(kind, kind), message, data)

    def _pending(self, position_id: str, kinds: tuple[str, ...]) -> bool:
        return any(o["position_id"] == position_id and o["kind"] in kinds for o in self.repo.orders_in(OPEN_STATES))

    def _cooling(self, position_id: str) -> bool:
        return self._cooldown.get(position_id, 0.0) > self._clock()

    def already_submitted(self, candidate: Candidate) -> bool:
        return (self.repo.get_order(f"bot-{candidate.setup_id}") is not None
                or self.repo.trade_by_setup(candidate.setup_id) is not None)

    def pending_opens(self, origin: str | None = "bot") -> list[dict]:
        """Gonderilmis ama sonucu henuz gorulmemis acma emirleri (risk kapisi bunlari da sayar)."""
        return [o for o in self.repo.orders_in(OPEN_STATES)
                if o["kind"] == "open" and (origin is None or o["origin"] == origin)]

    # ------------------------------------------------------------------ gonderim
    async def open(self, candidate: Candidate, origin: str = "bot", *, score: float | None = None,
                   votes: dict[str, int] | None = None) -> str:
        """Aday icin piyasa emri. Ayni setup icin ikinci kez cagrilirsa hicbir sey gondermez.

        `score` ve `votes` (guven puani ve modul oylari) emir kaydiyla saklanir; dolunca isleme yazilir.
        """
        key = f"bot-{candidate.setup_id}"
        instrument = self.catalog.get(candidate.symbol)
        path, body = schema.open_position_request(
            self.client.account_id, instrument, candidate.side, candidate.lots,
            sl=candidate.stop_loss, tp=candidate.take_profit_2, price=candidate.entry)
        if self.already_submitted(candidate):
            return key
        if self._lot_guard is not None:  # kayit ve gonderimden ONCE: tavani asan emir hic kaydedilmez
            self._lot_guard(candidate.symbol, candidate.side, candidate.lots, candidate.entry, candidate.stop_loss)
        payload = {"path": path, "body": body, "symbol": candidate.symbol, "side": candidate.side,
                   "entry": candidate.entry, "sl": candidate.stop_loss, "tp1": candidate.take_profit_1,
                   "tp2": candidate.take_profit_2, "strategy_id": candidate.strategy_id,
                   "risk_amount": candidate.risk_amount, "analysis_id": candidate.analysis_id,
                   "score": score, "votes": votes}
        if not self.repo.insert_order(key, kind="open", payload=payload, setup_id=candidate.setup_id, origin=origin):
            return key
        await self._send(key, "post", path, body)
        return key

    async def open_manual(self, symbol: str, side: str, lots: float, *, sl: float | None, tp: float | None,
                          price: float | None = None, client_id: str | None = None) -> str:
        """Kullanicinin uygulamadan actigi islem (`origin='manual'`). SL zorunludur.

        `client_id` verilirse ayni istek tekrarlandiginda (uygulama zaman asimi sonrasi yeniden
        denerse) ikinci bir emir gonderilmez.
        """
        instrument = self.catalog.get(symbol)
        if self._lot_guard is not None:
            self._lot_guard(symbol, side, lots, price, sl)
        path, body = schema.open_position_request(self.client.account_id, instrument, side, lots,
                                                  sl=sl, tp=tp, price=price)
        key = f"man-{client_id}" if client_id else f"man-{uuid.uuid4().hex}"
        payload = {"path": path, "body": body, "symbol": symbol, "side": side, "entry": price, "sl": sl,
                   "tp1": None, "tp2": tp, "strategy_id": None, "risk_amount": None, "manage": True}
        if not self.repo.insert_order(key, kind="open", payload=payload, origin="manual"):
            return key
        await self._send(key, "post", path, body)
        return key

    async def modify(self, position_id: str, sl: float | None = None, tp: float | None = None, *,
                     user: bool = False, stage: str | None = None) -> str | None:
        """SL/TP degisikligi. Bekleyen bir istek varsa ya da bekleme suresindeyse None doner.

        Yalnizca degisen alan gonderilir: API'de verilmeyen alan degismez. Boylece bayat bir yerel
        deger broker'daki (belki kullanicinin elle koydugu) seviyenin ustune yazilmaz.
        """
        trade = self.repo.get_trade(position_id)
        if trade is None or not trade.is_open or (sl is None and tp is None):
            return None
        if self._pending(position_id, ("modify", "close")) or (self._cooling(position_id) and not user):
            return None
        instrument = self.catalog.get(trade.symbol)
        if trade.sltp_order_id:
            method = "patch"
            path, body = schema.sltp_modify_request(self.client.account_id, trade.sltp_order_id, sl=sl, tp=tp,
                                                    digits=instrument.digits)
        else:
            method = "post"
            path, body = schema.sltp_create_request(self.client.account_id, position_id, sl=sl, tp=tp,
                                                    digits=instrument.digits)
        key = f"mod-{position_id}-{uuid.uuid4().hex[:12]}"
        payload = {"path": path, "body": body, "symbol": trade.symbol, "sl": sl, "tp": tp, "user": user,
                   "stage": stage, "tp_before": trade.tp2}
        self.repo.insert_order(key, kind="modify", payload=payload, origin=trade.origin, position_id=position_id)
        await self._send(key, method, path, body)
        return key

    async def close(self, position_id: str, volume: float | None = None, *, user: bool = False) -> str | None:
        """Tam ya da kismi kapama.

        Kullanicinin kapama istegi, botun sonucu beklenen bir SL degisikligi yuzunden engellenmez;
        yalnizca ayni pozisyon icin bekleyen baska bir kapama varsa None doner.
        """
        trade = self.repo.get_trade(position_id)
        if trade is None or not trade.is_open:
            return None
        blockers = ("close",) if user else ("modify", "close")
        if self._pending(position_id, blockers) or (self._cooling(position_id) and not user):
            return None
        instrument = self.catalog.get(trade.symbol)
        path = schema.close_position_path(self.client.account_id, position_id, volume=volume,
                                          volume_step=instrument.volume_step)
        key = f"cls-{position_id}-{uuid.uuid4().hex[:12]}"
        payload = {"path": path, "symbol": trade.symbol, "volume": volume, "user": user}
        self.repo.insert_order(key, kind="close", payload=payload, origin=trade.origin, position_id=position_id)
        await self._send(key, "delete", path, None)
        return key

    async def _send(self, key: str, method: str, path: str, body: dict | None) -> None:
        try:
            if method == "delete":
                raw = await self.client.delete(path, key)
            else:
                raw = await getattr(self.client, method)(path, body, key)
        except ExnessUnavailable as exc:
            # Istek ulasmis da olabilir, ulasmamis da: sonuc bilinmiyor. Yeniden gonderme.
            self.repo.update_order_state(key, "UNKNOWN", error=str(exc))
            log.warning("emir sonucu bilinmiyor %s: %s", key, exc)
            return
        except ExnessAuthError as exc:
            # ACK'ten once reddedildi: islenmedi. Kimlik sorunu tek yerden (servis dongusu) bildirilir.
            exc.source = "emir"  # tanilama: ret bir emir isteginde geldi (okuma isteginde degil)
            await self._order_failed(self.repo.get_order(key), exc.code, exc.message, notify=self._on_auth_error is None)
            if self._on_auth_error is not None:
                await self._on_auth_error(exc)
            return
        except (ExnessRejected, ExnessRateLimited) as exc:
            await self._order_failed(self.repo.get_order(key), exc.code, exc.message)  # ACK'ten once: islenmedi
            return
        ack = schema.parse_ack(raw)
        current = self.repo.get_order(key)
        # Olay ACK'ten once gelmis olabilir; FILLED/REJECTED durumunu geri alma.
        state = "ACKED" if current and current["state"] in ("PENDING", "UNKNOWN") else current["state"]
        self.repo.update_order_state(key, state, operation_id=ack.operation_id)

    async def _order_failed(self, order: dict | None, code: int | None, message: str | None, *,
                            notify: bool = True) -> None:
        if order is None:
            return
        text = f"{message or 'bilinmeyen hata'}" + (f" ({code})" if code is not None else "")
        self.repo.update_order_state(order["idempotency_key"], "REJECTED", error=text)
        if order["kind"] in ("modify", "close") and order["position_id"]:
            self._cooldown[order["position_id"]] = self._clock() + COOLDOWN
        symbol = order["payload"].get("symbol")
        await self._record("error", "order_rejected", f"{symbol} {_KINDS[order['kind']]} reddedildi: {text}",
                           {"code": code, "symbol": symbol, "order_kind": order["kind"],
                            "position_id": order["position_id"], "origin": order["origin"]}, notify=notify)

    # ------------------------------------------------------------------ olaylar
    def _find_order(self, event: TxEvent) -> dict | None:
        if event.client_request_id:
            order = self.repo.get_order(event.client_request_id)
            if order is not None:
                return order
        return self.repo.order_by_operation(event.operation_id) if event.operation_id else None

    async def _announce_open(self, trade: Trade) -> None:
        stop = f"SL {trade.sl:g}" if trade.sl is not None else "SL bekleniyor"
        await self._record(
            "info", "trade_opened",
            f"{trade.symbol} {trade.side} {trade.volume:g} lot @ {trade.entry:g} ({stop})"
            + (" (elle)" if trade.origin == "manual" else ""),
            {"position_id": trade.position_id, "symbol": trade.symbol, "side": trade.side,
             "origin": trade.origin, "strategy_id": trade.strategy_id})

    def _adopt(self, order: dict, position, when: float) -> Trade:
        """Dolan pozisyonu, onu acan emrin kaydiyla islem satirina cevirir."""
        symbol = canonical(self.catalog, position.symbol)
        trade = trade_from_order(order, position, symbol, when)
        return self.repo.upsert_trade(trade)

    async def _modify_confirmed(self, order: dict) -> None:
        """Onaylanan SL/TP degisikliginin sonuclari: basa bas isareti/bildirimi ve TP kaybi denetimi.

        Yalnizca broker'in onayladigi seviye istenenle ayniysa "uygulandi" sayilir; boylece durumu
        ogrenilememis bir istek yuzunden yanlis "SL girise cekildi" bildirimi gitmez.
        """
        payload = order["payload"]
        trade = self.repo.get_trade(order["position_id"]) if order["position_id"] else None
        if trade is None or not trade.is_open:
            return
        level = payload.get("sl")
        applied = level is not None and trade.sl is not None and abs(trade.sl - level) < 1e-9
        if payload.get("stage") == "breakeven" and applied and not trade.be_done:
            self.repo.update_trade(trade.position_id, be_done=True)
            await self._record("info", "sl_breakeven", f"{trade.symbol} {trade.side}: SL girişe çekildi ({level:g})",
                               {"position_id": trade.position_id, "symbol": trade.symbol, "sl": level})
        if (not payload.get("user") and payload.get("tp") is None and payload.get("tp_before") is not None
                and trade.tp2 is None and trade.planned_tp is not None):
            # Yalnizca SL gonderildi ama broker TP'yi de sildi: API verilmeyen alani korumuyor demektir.
            await self._record(
                "error", "tp_lost",
                f"{trade.symbol} {trade.side}: SL değişikliği TP'yi sildi; TP {trade.planned_tp:g} yeniden kuruluyor.",
                {"position_id": trade.position_id, "symbol": trade.symbol, "tp": trade.planned_tp})
            # SL de birlikte gonderilir: verilmeyen alan siliniyorsa yalnizca TP gondermek stopu silerdi.
            await self.modify(trade.position_id, sl=trade.sl, tp=trade.planned_tp)

    def _claim(self, order: dict, trade: Trade) -> None:
        """Mutabakatin `manual` diye ice aldigi pozisyon aslinda bu emrin: bot islemine cevir."""
        meta = order["payload"]
        requested = meta.get("sl")
        self.repo.update_trade(
            trade.position_id, origin=order["origin"], setup_id=order.get("setup_id"),
            strategy_id=meta.get("strategy_id"), tp1=meta.get("tp1"), risk_amount=meta.get("risk_amount"),
            score=meta.get("score"), votes_json=json.dumps(meta["votes"]) if meta.get("votes") else None,
            manage=bool(meta.get("manage", True)),
            planned_tp=meta.get("tp2") if meta.get("tp2") is not None else trade.planned_tp,
            initial_risk_r_price=risk_distance(trade.side, trade.entry, requested if requested is not None else trade.sl))

    async def on_transaction(self, event: TxEvent) -> None:
        order = self._find_order(event)
        if event.status != "success":
            if order is not None and order["state"] in OPEN_STATES:
                await self._order_failed(order, event.error_code, event.reason)
            return
        now = self._clock()
        confirmed_modify = None
        if order is not None:
            key = order["idempotency_key"]
            if order["kind"] == "open":
                # Emrin kayitli durumu ne olursa olsun (gec gelen dolum, iptal sayilmis emir dahil)
                # bu pozisyon o emrindir: `manual` diye ice alinmamali.
                position = next((p for p in event.positions if not p.closed), None)
                existing = self.repo.get_trade(position.id) if position is not None else None
                if position is not None and existing is None:
                    await self._announce_open(self._adopt(order, position, event.time or now))
                elif existing is not None and existing.setup_id is None and not order["position_id"] \
                        and (existing.origin != order["origin"] or order.get("setup_id")):
                    self._claim(order, existing)  # mutabakat olaydan once gorup `manual` yazmisti
                if position is not None:
                    self.repo.update_order_state(key, "FILLED", operation_id=event.operation_id,
                                                 position_id=position.id)
                elif event.operation_id and not order["operation_id"]:
                    # Olay pozisyonu tasimiyor: emri acik birak; hangi pozisyonun acildigi broker'dan
                    # (mutabakat) ogrenilir. Pozisyonsuz FILLED, o pozisyonu sahipsiz birakirdi.
                    self.repo.update_order_state(key, order["state"], operation_id=event.operation_id)
            elif order["state"] in OPEN_STATES:
                self.repo.update_order_state(key, "FILLED", operation_id=event.operation_id)
                if order["kind"] == "modify":
                    confirmed_modify = order
        await self._apply(event, order, now)
        if confirmed_modify is not None:
            await self._modify_confirmed(confirmed_modify)

    async def _apply(self, event: TxEvent, order: dict | None, now: float) -> None:
        """Olaydaki degisen varliklari (deal, pozisyon, SL/TP emri) yerel duruma isler."""
        moment = event.time or now
        for deal in event.deals:
            if deal.position_id and deal.type in ("open", "close"):
                amount = deal_pnl(deal)
                if deal.type == "close" or amount:  # acilis deal'i yalnizca komisyon tasiyorsa
                    self.repo.add_realized(deal.position_id, deal.id, deal.time or moment, amount)
        seen: set[str] = set()
        for position in event.positions:
            seen.add(position.id)
            trade = self.repo.get_trade(position.id)
            if trade is None:
                if not position.closed and position.volume > 0:
                    pending = _matching_order(self.repo, position, set()) if order is None else None
                    if pending is not None:
                        # Olay istek kimligi tasimiyor ama sonucu beklenen bir acma emrine birebir uyuyor.
                        trade = self._adopt(pending, position, moment)
                        self.repo.update_order_state(pending["idempotency_key"], "FILLED", position_id=position.id)
                    else:
                        # Botun gondermedigi bir pozisyon: MT5/web'den acilmis, elle islem olarak izlenir.
                        trade = self.repo.upsert_trade(manual_trade(position, canonical(self.catalog, position.symbol),
                                                                    moment))
                    await self._announce_open(trade)
                    for deal in event.deals:  # islem satiri yeni olustu: acilis komisyonunu simdi yaz
                        if deal.position_id == position.id and deal.type == "open" and deal_pnl(deal):
                            self.repo.add_realized(position.id, deal.id, deal.time or moment, deal_pnl(deal))
                continue
            if not trade.is_open:
                continue
            if position.closed or position.volume <= 0:
                closing = next((d for d in reversed(event.deals)
                                if d.type == "close" and d.position_id == position.id), None)
                reason = next((o.reason for o in event.orders if o.position_id == position.id and o.reason), None)
                reason = reason or ("close" if order is not None else "external")
                self.repo.close_trade(position.id, close_price=closing.price if closing else None, closed_at=moment)
                closed = self.repo.get_trade(position.id)
                await self._record(
                    "info", "trade_closed",
                    f"{closed.symbol} {closed.side} kapandı: {closed.pnl:+.2f} ({_REASONS.get(reason, reason)})",
                    {"position_id": position.id, "symbol": closed.symbol, "side": closed.side, "pnl": closed.pnl,
                     "reason": reason, "origin": closed.origin})
                continue
            trade.volume = position.volume
            if position.sltp_order_id is not None:
                self._levels(trade, position.sl, position.tp, position.sltp_order_id, order)
            self.repo.upsert_trade(trade)
        # Once iptaller, sonra yeni/guncel emirler: ayni olayda eski SL/TP emri iptal edilip yenisi
        # konmussa sonuc "SL var" olmalidir.
        linked = [o for o in event.orders if o.type == "sltp" and o.position_id and o.position_id not in seen]
        for item in sorted(linked, key=lambda o: o.state in ("placed", "pending_new")):
            trade = self.repo.get_trade(item.position_id)
            if trade is None or not trade.is_open:
                continue
            if item.state in ("placed", "pending_new"):
                self._levels(trade, item.sl, item.tp, item.id, order)
            elif item.state == "cancelled" and item.id == trade.sltp_order_id:
                trade.sl, trade.tp2, trade.sltp_order_id = None, None, None  # stop guard'i yeniden kurar
            else:
                continue
            self.repo.upsert_trade(trade)

    @staticmethod
    def _levels(trade: Trade, sl: float | None, tp: float | None, order_id: str, order: dict | None) -> None:
        own = order is not None
        by_user = (not own) or bool(order["payload"].get("user"))
        if sl is not None and (trade.sl is None or abs(sl - trade.sl) > 1e-9):
            if by_user and (not own or order["payload"].get("sl") is not None):
                trade.user_sl_override = True
            if trade.initial_risk_r_price is None:
                trade.initial_risk_r_price = risk_distance(trade.side, trade.entry, sl)
        if sl is not None:
            trade.last_sl = sl
        if tp is not None and (by_user or trade.planned_tp is None):
            trade.planned_tp = tp  # TP'yi yalnizca kullanici degistirir; bot planlanani korur
        trade.sl, trade.tp2, trade.sltp_order_id = sl, tp, order_id

    # ------------------------------------------------------------------ toparlama
    async def publish(self, report: ReconcileReport) -> None:
        """Mutabakatin buldugu degisiklikleri olay olarak kaydeder ve bildirir."""
        for position_id in report.adopted + report.imported:
            trade = self.repo.get_trade(position_id)
            if trade is not None:
                await self._announce_open(trade)
        for position_id in report.closed:
            trade = self.repo.get_trade(position_id)
            if trade is not None:
                await self._record(
                    "info", "trade_closed", f"{trade.symbol} {trade.side} kapandı: {trade.pnl:+.2f}",
                    {"position_id": position_id, "symbol": trade.symbol, "side": trade.side, "pnl": trade.pnl,
                     "reason": "unknown" if position_id in report.unexplained else "offline",
                     "origin": trade.origin})
        for position_id in report.reopened:
            trade = self.repo.get_trade(position_id)
            if trade is not None:
                await self._record(
                    "warning", "trade_reopened",
                    f"{trade.symbol} {trade.side}: kayıtta kapalı görünen pozisyon broker'da açık; yeniden izleniyor",
                    {"position_id": position_id, "symbol": trade.symbol})
        for message in report.errors:
            await self._record("warning", "reconcile_error", message, notify=False)

    async def reconcile(self, snapshot=None) -> ReconcileReport | None:
        """Broker ile mutabakat + bulunanlarin bildirimi. Hata olursa None (bir sonraki tur dener)."""
        try:
            report = await reconcile(self.client, self.repo, self.catalog, clock=self._clock, snapshot=snapshot)
        except ExnessAuthError as exc:
            if self._on_auth_error is not None:
                await self._on_auth_error(exc)
            return None
        except (ExnessError, ValueError) as exc:
            log.warning("mutabakat yapilamadi: %s", exc)
            return None
        await self.publish(report)
        return report

    async def _recover_closed(self, order: dict, *, confirmed: bool) -> bool:
        """Acik pozisyonu bulunamayan acma emri: pozisyon biz gormeden acilip kapanmis olabilir.

        Yalnizca kanit tamsa kapali bir bot islemi olarak kaydedilir: emre birebir uyan bir acilis
        deal'i VE hacmin tamamini kapatan kapanis deal'leri. Operasyon onaylanmadiysa (ACK kayip)
        yalnizca emirden hemen sonraki acilis eslesir; boylece kullanicinin ayni sembolde elle actigi
        bir islem bota yazilmaz.
        """
        body = order["payload"].get("body", {})
        try:
            deals = await fetch_deals(self.client, order["created_at"] - 5)
            volume = float(body.get("volume"))
        except ExnessAuthError as exc:
            if self._on_auth_error is not None:
                await self._on_auth_error(exc)
            return False
        except (ExnessError, TypeError, ValueError) as exc:
            log.warning("deal gecmisi okunamadi %s: %s", order["idempotency_key"], exc)
            return False
        window = RECOVER_WINDOW_CONFIRMED if confirmed else RECOVER_WINDOW_UNCONFIRMED
        opening = next((d for d in deals if d.type == "open" and d.symbol == body.get("instrument")
                        and d.side is not None and d.side.lower() == body.get("side")
                        and d.volume is not None and abs(d.volume - volume) < 1e-6
                        and d.time is not None and d.time <= order["created_at"] + window
                        and self.repo.get_trade(d.position_id) is None), None)
        if opening is not None:
            closed_volume = sum(d.volume or 0.0 for d in deals
                                if d.type == "close" and d.position_id == opening.position_id)
            if closed_volume < volume - 1e-6:
                return False  # pozisyon hala acik olabilir (goruntu gecikmis): kapali diye yazma
        if opening is None:
            return False
        meta = order["payload"]
        entry = opening.price if opening.price is not None else meta.get("entry")
        closes = [d for d in deals if d.type == "close" and d.position_id == opening.position_id]
        self.repo.upsert_trade(Trade(
            position_id=opening.position_id, origin=order["origin"], symbol=meta.get("symbol") or opening.symbol,
            side=opening.side, volume=volume, initial_volume=volume, entry=entry, tp1=meta.get("tp1"),
            tp2=meta.get("tp2"), initial_risk_r_price=risk_distance(opening.side, entry, meta.get("sl")),
            score=meta.get("score"), votes_json=json.dumps(meta["votes"]) if meta.get("votes") else None,
            risk_amount=meta.get("risk_amount"), strategy_id=meta.get("strategy_id"),
            setup_id=order.get("setup_id"), opened_at=opening.time or order["created_at"]))
        for deal in [opening, *closes]:
            if deal.type == "close" or deal_pnl(deal):
                self.repo.add_realized(opening.position_id, deal.id, deal.time or self._clock(), deal_pnl(deal))
        last = closes[-1] if closes else None
        self.repo.close_trade(opening.position_id, close_price=last.price if last else None,
                              closed_at=(last.time if last and last.time else self._clock()))
        self.repo.update_order_state(order["idempotency_key"], "FILLED", position_id=opening.position_id)
        trade = self.repo.get_trade(opening.position_id)
        await self._record(
            "info", "trade_closed", f"{trade.symbol} {trade.side} kapandı: {trade.pnl:+.2f} (bağlantı yokken)",
            {"position_id": trade.position_id, "symbol": trade.symbol, "side": trade.side, "pnl": trade.pnl,
             "reason": "offline", "origin": trade.origin})
        return True

    async def resolve_unknown(self) -> ReconcileReport | None:
        """Sonucu gorulmemis emirleri cozer: operasyon durumu + broker ile mutabakat. Yeniden gondermez."""
        pending = self.repo.orders_in(OPEN_STATES)
        if not pending:
            return None
        now = self._clock()
        confirmed: set[str] = set()
        gone: set[str] = set()
        need_reconcile = False
        for order in pending:
            key = order["idempotency_key"]
            age = now - order["updated_at"]
            if not order["operation_id"]:
                need_reconcile = True
                continue
            if order["state"] == "ACKED" and age < ACK_TIMEOUT:
                continue  # olay hala yolda olabilir
            try:
                status = schema.parse_operation(
                    await self.client.get(schema.operation_path(self.client.account_id, order["operation_id"])))
            except ExnessAuthError as exc:
                if self._on_auth_error is not None:
                    await self._on_auth_error(exc)
                return None  # kimlik sorunu surerken sorgulamaya devam etme
            except ExnessRejected as exc:
                if exc.status == 404 or exc.code == 3014:
                    # Operasyon kaydi artik yok (24 saat saklanir). Sonuc bilinmiyor: "onaylandi"
                    # sayma, broker durumuna bak.
                    gone.add(key)
                    need_reconcile = True
                else:
                    log.warning("operasyon durumu reddedildi %s: %s", key, exc)
                    need_reconcile = need_reconcile or age >= ORDER_DEADLINE
                continue
            except (ExnessError, ValueError) as exc:
                log.warning("operasyon durumu okunamadi %s: %s", key, exc)
                need_reconcile = need_reconcile or age >= ORDER_DEADLINE
                continue
            if status.status == "pending":
                need_reconcile = need_reconcile or age >= ORDER_DEADLINE
                continue
            if status.status in ("rejected", "failed"):
                await self._order_failed(order, status.error_code, status.reason)
                continue
            confirmed.add(key)
            need_reconcile = True
        if not need_reconcile:
            return None
        report = await self.reconcile()
        for order in pending:
            key = order["idempotency_key"]
            current = self.repo.get_order(key)
            if current is None or current["state"] not in OPEN_STATES:
                continue
            created_age = now - current["created_at"]
            if key in confirmed:
                # Broker islemi onayladi: bu emir asla "iptal" sayilmaz. Mutabakat yapilamadiysa bekle.
                if report is None:
                    continue
                if current["kind"] == "open":
                    if await self._recover_closed(current, confirmed=True):
                        continue  # acilip kapanmis pozisyon gecmisten kaydedildi
                    if created_age >= CONFIRMED_GIVE_UP:
                        # Onaylandi ama ne goruntude ne gecmiste izi var. Emri kapat (risk kapisinda
                        # sonsuza dek yer tutmasin) ve kullaniciya bildir; gec gelen bilgi yine baglanir.
                        self.repo.update_order_state(key, "FILLED")
                        symbol = current["payload"].get("symbol")
                        await self._record(
                            "warning", "order_unknown",
                            f"{symbol} açma emri onaylandı ama pozisyonu bulunamadı; hesabı kontrol edin",
                            {"symbol": symbol, "order_kind": "open", "position_id": None})
                    continue  # pozisyon henuz goruntude/gecmiste yok: acik birak, sonraki tur eslestirir
                self.repo.update_order_state(key, "FILLED")
                if current["kind"] == "modify":
                    await self._modify_confirmed(current)
                continue
            if current["kind"] == "open" and report is not None and created_age >= UNKNOWN_TIMEOUT \
                    and await self._recover_closed(current, confirmed=False):
                continue
            limit = UNKNOWN_TIMEOUT if not current["operation_id"] else ORDER_DEADLINE
            if created_age >= limit and (report is not None or created_age >= 2 * ORDER_DEADLINE):
                # Sonuc hicbir yoldan ogrenilemedi. Emri birak: pozisyonu kilitli tutma. Gercek durum
                # mutabakatla esitlenir; gec gelen bir dolum (olay ya da goruntu) yine bu emre baglanir.
                self.repo.update_order_state(key, "CANCELLED", error="sonuç bilinmiyor; pozisyon bulunamadı")
                symbol = current["payload"].get("symbol")
                await self._record(
                    "warning", "order_unknown",
                    f"{symbol} {_KINDS[current['kind']]} emrinin sonucu alınamadı; broker'da karşılığı yok",
                    {"symbol": symbol, "order_kind": current["kind"], "position_id": current["position_id"]})
        return report

_KINDS = {"open": "açma", "modify": "SL/TP değişikliği", "close": "kapama"}
_REASONS = {"sl": "stop", "tp": "kâr al", "so": "stop out", "close": "kapatıldı", "external": "dışarıdan kapatıldı"}
_TITLES = {"trade_opened": "İşlem açıldı", "trade_closed": "İşlem kapandı", "order_rejected": "Emir reddedildi",
           "order_unknown": "Emir sonucu bilinmiyor", "sl_breakeven": "SL girişe çekildi",
           "trade_reopened": "Pozisyon yeniden izleniyor", "tp_lost": "TP silindi"}
