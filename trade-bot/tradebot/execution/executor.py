"""Emir durum makinesi.

Kurallar:
- Her emir once SQLite'a yazilir, sonra gonderilir. Ayni idempotency anahtari ikinci kez gonderilmez.
- ACK dolum degildir. Sonuc `transaction_event` ile gelir; gelmezse operasyon durumu sorgulanir.
- Sonucu bilinmeyen bir ACMA emri asla yeniden gonderilmez (bayat sinyalle islem acmamak icin);
  broker'daki pozisyonlara bakilarak cozulur.
- Bu sinif hicbir istegi dongude tekrar denemez; reddedilen degisiklikler icin bekleme suresi vardir.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable

from ..exness import schema
from ..exness.errors import (ExnessAuthError, ExnessError, ExnessRateLimited, ExnessRejected,
                             ExnessUnavailable)
from ..exness.schema import TxEvent
from ..signals.adapter import Candidate
from ..store.repo import Repo
from .reconcile import (OPEN_STATES, ReconcileReport, _matching_order, canonical, deal_pnl, manual_trade,
                        reconcile, trade_from_order)

log = logging.getLogger(__name__)

ACK_TIMEOUT = 10.0  # ACK'ten sonra olay bu kadar surede gelmezse operasyon durumu sorgulanir
UNKNOWN_TIMEOUT = 60.0  # operasyon kimligi olmayan emir bu kadar surede eslesmezse iptal sayilir
COOLDOWN = 60.0  # reddedilen degisiklik/kapama sonrasi ayni pozisyon icin bekleme


class Executor:
    def __init__(self, client, repo: Repo, notifier, catalog, *, clock: Callable[[], float] = time.time):
        self.client = client
        self.repo = repo
        self.notifier = notifier
        self.catalog = catalog
        self._clock = clock
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

    def _busy(self, position_id: str) -> bool:
        return any(o["position_id"] == position_id and o["kind"] in ("modify", "close")
                   for o in self.repo.orders_in(OPEN_STATES))

    def _cooling(self, position_id: str) -> bool:
        return self._cooldown.get(position_id, 0.0) > self._clock()

    # ------------------------------------------------------------------ gonderim
    async def open(self, candidate: Candidate, origin: str = "bot") -> str:
        """Aday icin piyasa emri. Ayni setup icin ikinci kez cagrilirsa hicbir sey gondermez."""
        key = f"bot-{candidate.setup_id}"
        instrument = self.catalog.get(candidate.symbol)
        path, body = schema.open_position_request(
            self.client.account_id, instrument, candidate.side, candidate.lots,
            sl=candidate.stop_loss, tp=candidate.take_profit_2, price=candidate.entry)
        if self.repo.get_order(key) is not None or self.repo.trade_by_setup(candidate.setup_id) is not None:
            return key
        payload = {"path": path, "body": body, "symbol": candidate.symbol, "side": candidate.side,
                   "entry": candidate.entry, "sl": candidate.stop_loss, "tp1": candidate.take_profit_1,
                   "tp2": candidate.take_profit_2, "strategy_id": candidate.strategy_id,
                   "risk_amount": candidate.risk_amount, "analysis_id": candidate.analysis_id}
        if not self.repo.insert_order(key, kind="open", payload=payload, setup_id=candidate.setup_id, origin=origin):
            return key
        await self._send(key, "post", path, body)
        return key

    async def open_manual(self, symbol: str, side: str, lots: float, *, sl: float | None, tp: float | None,
                          price: float | None = None) -> str:
        """Kullanicinin uygulamadan actigi islem (`origin='manual'`). SL zorunludur."""
        instrument = self.catalog.get(symbol)
        path, body = schema.open_position_request(self.client.account_id, instrument, side, lots,
                                                  sl=sl, tp=tp, price=price)
        key = f"man-{uuid.uuid4().hex}"
        payload = {"path": path, "body": body, "symbol": symbol, "side": side, "entry": price, "sl": sl,
                   "tp1": None, "tp2": tp, "strategy_id": None, "risk_amount": None}
        self.repo.insert_order(key, kind="open", payload=payload, origin="manual")
        await self._send(key, "post", path, body)
        return key

    async def modify(self, position_id: str, sl: float | None = None, tp: float | None = None, *,
                     user: bool = False) -> str | None:
        """SL/TP degisikligi. Bekleyen bir degisiklik varsa ya da bekleme suresindeyse None doner."""
        trade = self.repo.get_trade(position_id)
        if trade is None or not trade.is_open or (sl is None and tp is None):
            return None
        if self._busy(position_id) or (self._cooling(position_id) and not user):
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
        payload = {"path": path, "body": body, "symbol": trade.symbol, "sl": sl, "tp": tp, "user": user}
        self.repo.insert_order(key, kind="modify", payload=payload, origin=trade.origin, position_id=position_id)
        await self._send(key, method, path, body)
        return key

    async def close(self, position_id: str, volume: float | None = None, *, user: bool = False) -> str | None:
        """Tam ya da kismi kapama."""
        trade = self.repo.get_trade(position_id)
        if trade is None or not trade.is_open:
            return None
        if self._busy(position_id) or (self._cooling(position_id) and not user):
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
        except (ExnessRejected, ExnessAuthError, ExnessRateLimited) as exc:
            # ACK'ten once reddedildi: islenmedi.
            await self._order_failed(self.repo.get_order(key), exc.code, exc.message)
            return
        ack = schema.parse_ack(raw)
        current = self.repo.get_order(key)
        # Olay ACK'ten once gelmis olabilir; FILLED/REJECTED durumunu geri alma.
        state = "ACKED" if current and current["state"] in ("PENDING", "UNKNOWN") else current["state"]
        self.repo.update_order_state(key, state, operation_id=ack.operation_id)

    async def _order_failed(self, order: dict | None, code: int | None, message: str | None) -> None:
        if order is None:
            return
        text = f"{message or 'bilinmeyen hata'}" + (f" ({code})" if code is not None else "")
        self.repo.update_order_state(order["idempotency_key"], "REJECTED", error=text)
        if order["kind"] in ("modify", "close") and order["position_id"]:
            self._cooldown[order["position_id"]] = self._clock() + COOLDOWN
        symbol = order["payload"].get("symbol")
        await self._record("error", "order_rejected", f"{symbol} {_KINDS[order['kind']]} reddedildi: {text}",
                           {"code": code, "symbol": symbol, "kind": order["kind"],
                            "position_id": order["position_id"], "origin": order["origin"]})

    # ------------------------------------------------------------------ olaylar
    def _find_order(self, event: TxEvent) -> dict | None:
        if event.client_request_id:
            order = self.repo.get_order(event.client_request_id)
            if order is not None:
                return order
        return self.repo.order_by_operation(event.operation_id) if event.operation_id else None

    async def on_transaction(self, event: TxEvent) -> None:
        order = self._find_order(event)
        if event.status != "success":
            if order is not None and order["state"] in OPEN_STATES:
                await self._order_failed(order, event.error_code, event.reason)
            return
        now = self._clock()
        if order is not None and order["state"] in OPEN_STATES:
            key = order["idempotency_key"]
            if order["kind"] == "open":
                position = next((p for p in event.positions if not p.closed), None)
                if position is not None and self.repo.get_trade(position.id) is None:
                    symbol = canonical(self.catalog, position.symbol)
                    trade = self.repo.upsert_trade(trade_from_order(order, position, symbol, event.time or now))
                    await self._record(
                        "info", "trade_opened",
                        f"{trade.symbol} {trade.side} {trade.volume:g} lot @ {trade.entry:g} (SL {trade.sl:g})",
                        {"position_id": trade.position_id, "symbol": trade.symbol, "side": trade.side,
                         "origin": trade.origin, "strategy_id": trade.strategy_id})
                self.repo.update_order_state(key, "FILLED", operation_id=event.operation_id,
                                             position_id=position.id if position else None)
            else:
                self.repo.update_order_state(key, "FILLED", operation_id=event.operation_id)
        await self._apply(event, order, now)

    async def _apply(self, event: TxEvent, order: dict | None, now: float) -> None:
        """Olaydaki degisen varliklari (deal, pozisyon, SL/TP emri) yerel duruma isler."""
        moment = event.time or now
        for deal in event.deals:
            if deal.type == "close" and deal.position_id:
                self.repo.add_realized(deal.position_id, deal.id, deal.time or moment, deal_pnl(deal))
        seen: set[str] = set()
        for position in event.positions:
            seen.add(position.id)
            trade = self.repo.get_trade(position.id)
            if trade is None:
                if not position.closed and position.volume > 0:
                    symbol = canonical(self.catalog, position.symbol)
                    pending = _matching_order(self.repo, position, set()) if order is None else None
                    if pending is not None:
                        # Olay istek kimligi tasimiyor ama sonucu beklenen bir acma emrine birebir uyuyor.
                        trade = self.repo.upsert_trade(trade_from_order(pending, position, symbol, moment))
                        self.repo.update_order_state(pending["idempotency_key"], "FILLED", position_id=position.id)
                        await self._record(
                            "info", "trade_opened", f"{trade.symbol} {trade.side} {trade.volume:g} lot",
                            {"position_id": trade.position_id, "symbol": trade.symbol, "side": trade.side,
                             "origin": trade.origin, "strategy_id": trade.strategy_id})
                        continue
                    # Botun gondermedigi bir pozisyon: MT5/web'den acilmis, elle islem olarak izlenir.
                    trade = self.repo.upsert_trade(manual_trade(position, symbol, moment))
                    await self._record(
                        "info", "trade_opened", f"{trade.symbol} {trade.side} {trade.volume:g} lot (elle)",
                        {"position_id": trade.position_id, "symbol": trade.symbol, "side": trade.side,
                         "origin": "manual", "strategy_id": None})
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
                    f"{closed.symbol} {closed.side} kapandi: {closed.pnl:+.2f} ({_REASONS.get(reason, reason)})",
                    {"position_id": position.id, "symbol": closed.symbol, "side": closed.side, "pnl": closed.pnl,
                     "reason": reason, "origin": closed.origin})
                continue
            trade.volume = position.volume
            if position.sltp_order_id is not None:
                self._levels(trade, position.sl, position.tp, position.sltp_order_id, order)
            self.repo.upsert_trade(trade)
        for item in event.orders:
            if item.type != "sltp" or not item.position_id or item.position_id in seen:
                continue
            trade = self.repo.get_trade(item.position_id)
            if trade is None or not trade.is_open:
                continue
            if item.state in ("placed", "pending_new"):
                self._levels(trade, item.sl, item.tp, item.id, order)
            elif item.state == "cancelled":
                trade.sl, trade.tp2, trade.sltp_order_id = None, None, None
            self.repo.upsert_trade(trade)

    @staticmethod
    def _levels(trade, sl: float | None, tp: float | None, order_id: str, order: dict | None) -> None:
        own = order is not None
        by_user = (not own) or bool(order["payload"].get("user"))
        if sl is not None and (trade.sl is None or abs(sl - trade.sl) > 1e-9):
            if by_user and (not own or order["payload"].get("sl") is not None):
                trade.user_sl_override = True
            if trade.initial_risk_r_price is None:
                trade.initial_risk_r_price = abs(trade.entry - sl)
        trade.sl, trade.tp2, trade.sltp_order_id = sl, tp, order_id

    # ------------------------------------------------------------------ toparlama
    async def publish(self, report: ReconcileReport) -> None:
        """Mutabakatin buldugu degisiklikleri olay olarak kaydeder ve bildirir."""
        for position_id in report.adopted + report.imported:
            trade = self.repo.get_trade(position_id)
            if trade is not None:
                await self._record(
                    "info", "trade_opened",
                    f"{trade.symbol} {trade.side} {trade.volume:g} lot" + (" (elle)" if trade.origin == "manual" else ""),
                    {"position_id": position_id, "symbol": trade.symbol, "side": trade.side,
                     "origin": trade.origin, "strategy_id": trade.strategy_id})
        for position_id in report.closed:
            trade = self.repo.get_trade(position_id)
            if trade is not None:
                await self._record(
                    "info", "trade_closed", f"{trade.symbol} {trade.side} kapandi: {trade.pnl:+.2f}",
                    {"position_id": position_id, "symbol": trade.symbol, "side": trade.side, "pnl": trade.pnl,
                     "reason": "unknown" if position_id in report.unexplained else "offline",
                     "origin": trade.origin})
        for message in report.errors:
            await self._record("warning", "reconcile_error", message, notify=False)

    async def resolve_unknown(self) -> ReconcileReport | None:
        """Sonucu gorulmemis emirleri cozer: operasyon durumu + broker ile mutabakat. Yeniden gondermez."""
        pending = self.repo.orders_in(OPEN_STATES)
        if not pending:
            return None
        now = self._clock()
        confirmed: set[str] = set()
        need_reconcile = False
        for order in pending:
            key = order["idempotency_key"]
            if not order["operation_id"]:
                need_reconcile = True
                continue
            if order["state"] == "ACKED" and now - order["updated_at"] < ACK_TIMEOUT:
                continue  # olay hala yolda olabilir
            try:
                status = schema.parse_operation(
                    await self.client.get(schema.operation_path(self.client.account_id, order["operation_id"])))
            except ExnessRejected:
                # Operasyon kaydi artik yok (24 saat saklanir): broker durumuna bak.
                self.repo.update_order_state(key, "UNKNOWN")
                confirmed.add(key)
                need_reconcile = True
                continue
            except (ExnessError, ValueError) as exc:
                log.warning("operasyon durumu okunamadi %s: %s", key, exc)
                continue
            if status.status == "pending":
                continue
            if status.status in ("rejected", "failed"):
                await self._order_failed(order, status.error_code, status.reason)
                continue
            confirmed.add(key)
            need_reconcile = True
        if not need_reconcile:
            return None
        try:
            report = await reconcile(self.client, self.repo, self.catalog, clock=self._clock)
        except (ExnessError, ValueError) as exc:
            log.warning("mutabakat yapilamadi: %s", exc)
            return None
        await self.publish(report)
        if report.errors:
            return report  # eksik bilgiyle emir kapatma; sonraki turda yeniden dene
        for order in pending:
            key = order["idempotency_key"]
            current = self.repo.get_order(key)
            if current is None or current["state"] not in OPEN_STATES:
                continue
            if key in confirmed:
                self.repo.update_order_state(key, "FILLED")
            elif not current["operation_id"] and now - current["created_at"] >= UNKNOWN_TIMEOUT:
                self.repo.update_order_state(key, "CANCELLED", error="sonuc bilinmiyor; pozisyon bulunamadi")
                symbol = current["payload"].get("symbol")
                await self._record(
                    "warning", "order_unknown",
                    f"{symbol} {_KINDS[current['kind']]} emrinin sonucu alinamadi; broker'da karsiligi yok",
                    {"symbol": symbol, "kind": current["kind"], "position_id": current["position_id"]})
        return report


_KINDS = {"open": "acma", "modify": "SL/TP degisikligi", "close": "kapama"}
_REASONS = {"sl": "stop", "tp": "kar al", "so": "stop out", "close": "kapatildi", "external": "disaridan kapatildi"}
_TITLES = {"trade_opened": "Islem acildi", "trade_closed": "Islem kapandi", "order_rejected": "Emir reddedildi",
           "order_unknown": "Emir sonucu bilinmiyor"}
