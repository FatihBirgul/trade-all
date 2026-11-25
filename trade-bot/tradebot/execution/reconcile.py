"""Broker durumu ile SQLite'in esitlenmesi.

Akislar kalici olmadigi icin (kopukluk, yeniden baslatma) dogru kaynak her zaman broker'dir:
anlik goruntu acik pozisyonlari, deal gecmisi kapanislari verir. Bu fonksiyon emir gondermez.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from ..exness import schema
from ..exness.errors import ExnessError
from ..exness.schema import AccountState, Deal, Position, Snapshot
from ..store.repo import Repo, Trade

OPEN_STATES = ("PENDING", "ACKED", "UNKNOWN")
HISTORY_DAYS = 30
FRESH_SECONDS = 120.0  # bu kadar yeni bir islem, tek bir anlik goruntuye dayanarak kapatilmaz
SNAPSHOT_RETRIES = 3
_EPS = 1e-9


@dataclass
class ReconcileReport:
    imported: list[str] = field(default_factory=list)  # botun bilmedigi pozisyonlar -> manual
    adopted: list[str] = field(default_factory=list)  # sonucu bilinmeyen bot emrine eslesen pozisyonlar
    closed: list[str] = field(default_factory=list)  # bot bakmazken kapanmis islemler
    updated: list[str] = field(default_factory=list)  # hacim / SL / TP esitlendi
    unexplained: list[str] = field(default_factory=list)  # kapanmis ama deal bulunamadi
    reopened: list[str] = field(default_factory=list)  # DB'de kapali, broker'da acik bulunup geri acilanlar
    deferred: list[str] = field(default_factory=list)  # goruntude yok ama kapatmak icin kanit yetersiz
    errors: list[str] = field(default_factory=list)
    account: AccountState | None = None


def deal_pnl(deal: Deal) -> float:
    """Kapanis deal'inin hesaba etkisi: kar/zarar eksi komisyon."""
    return (deal.profit or 0.0) - abs(deal.commission or 0.0)


def canonical(catalog, broker_symbol: str) -> str:
    instrument = catalog.by_broker(broker_symbol)
    return instrument.symbol if instrument else broker_symbol


def risk_distance(side: str, entry: float | None, stop: float | None) -> float | None:
    """1R = giris ile ZARAR tarafindaki stop arasi. Stop kar tarafindaysa R tanimsizdir (None).

    Kar tarafina cekilmis bir stoptan R turetilirse fiyat sahte bicimde "+10R" gorunur ve yonetici
    pozisyonu hemen kismen kapatir; bu yuzden boyle islemler yonetilmez.
    """
    if entry is None or stop is None or entry <= 0:
        return None
    distance = (entry - stop) if side == "BUY" else (stop - entry)
    return distance if distance > 0 else None


def _differs(a: float | None, b: float | None, tolerance: float = 1e-9) -> bool:
    if a is None or b is None:
        return a is not b
    return abs(a - b) > tolerance


def trade_from_order(order: dict, position: Position, symbol: str, fallback_time: float) -> Trade:
    """Bot/elle acma emrinin kaydindan ve dolan pozisyondan islem satiri."""
    meta = order["payload"]
    entry = position.open_price if position.open_price is not None else meta.get("entry")
    requested = meta.get("sl")
    # `sl` yalnizca broker'in onayladigi degerdir (bagli SL/TP emri gorulduyse). Istenen SL, R'yi ve
    # eksik stopu yeniden kurmayi belirler; broker'da SL oldugu varsayilmaz.
    return Trade(
        position_id=position.id, origin=order["origin"], symbol=symbol, side=position.side,
        volume=position.volume, initial_volume=position.initial_volume or position.volume, entry=entry,
        sl=position.sl, tp1=meta.get("tp1"), tp2=position.tp if position.tp is not None else meta.get("tp2"),
        initial_risk_r_price=risk_distance(position.side, entry, requested if requested is not None else position.sl),
        risk_amount=meta.get("risk_amount"), strategy_id=meta.get("strategy_id"), setup_id=order.get("setup_id"),
        opened_at=position.opened_at or fallback_time, sltp_order_id=position.sltp_order_id,
        manage=bool(meta.get("manage", True)))


def manual_trade(position: Position, symbol: str, fallback_time: float) -> Trade:
    """Botun disindan (MT5/web) acilmis pozisyon. Izlenir ve raporlanir ama kullanici acmadikca
    yonetilmez (`manage=False`): bot, kendisinin acmadigi bir pozisyona kendiliginden emir gondermez."""
    entry = position.open_price or 0.0
    return Trade(
        position_id=position.id, origin="manual", symbol=symbol, side=position.side, volume=position.volume,
        initial_volume=position.initial_volume or position.volume, entry=entry, sl=position.sl, tp2=position.tp,
        initial_risk_r_price=risk_distance(position.side, entry, position.sl), manage=False,
        opened_at=position.opened_at or fallback_time, sltp_order_id=position.sltp_order_id)


def _matching_order(repo: Repo, position: Position, taken: set[str]) -> dict | None:
    """Sonucu bilinmeyen acma emirlerinden bu pozisyona uyan en eskisi."""
    for order in repo.orders_in(OPEN_STATES):
        if order["kind"] != "open" or order["idempotency_key"] in taken:
            continue
        body = order["payload"].get("body", {})
        try:
            volume = float(body.get("volume"))
        except (TypeError, ValueError):
            continue
        reference = position.initial_volume or position.volume
        if (body.get("instrument") == position.symbol and body.get("side") == position.side.lower()
                and abs(volume - reference) < 1e-6
                and (position.opened_at is None or position.opened_at >= order["created_at"] - 5)):
            return order
    return None


def _set_by_bot(repo: Repo, position_id: str, sl: float) -> bool:
    """Broker'daki SL, botun bu pozisyon icin gonderdigi son degisikliklerden biri mi?"""
    for order in repo.orders_for_position(position_id, "modify"):
        sent = order["payload"].get("sl")
        if order["state"] not in ("REJECTED", "CANCELLED") and not order["payload"].get("user") \
                and sent is not None and abs(sent - sl) < 1e-9:
            return True
    return False


async def fetch_deals(client, since: float) -> list[Deal]:
    """`since` anindan bugune pozisyona bagli tum deal'lar (eskiden yeniye)."""
    deals: list[Deal] = []
    cursor = None
    for _ in range(50):
        if cursor is None:
            path = schema.deals_path(client.account_id, start=since, limit=200)
        else:
            path = schema.deals_path(client.account_id, cursor=cursor, limit=200)
        page, cursor = schema.parse_deals(await client.get(path))
        deals += [d for d in page if d.position_id]
        if not cursor:
            break
    return sorted(deals, key=lambda d: d.time or 0.0)


async def _close_deals(client, since: float) -> list[Deal]:
    return [d for d in await fetch_deals(client, since) if d.type == "close"]


async def reconcile(client, repo: Repo, catalog, *, clock: Callable[[], float] = time.time,
                    snapshot: Snapshot | None = None) -> ReconcileReport:
    report = ReconcileReport()
    if snapshot is None:
        # REST goruntusu yoldayken WS olaylari islenebilir; o zaman goruntu bayattir. Veritabani bu
        # arada degistiyse goruntuyu at ve yeniden al (son denemede asagidaki korumalar devrededir).
        for _ in range(SNAPSHOT_RETRIES):
            before = repo.conn.total_changes
            snapshot = schema.parse_snapshot(await client.get(schema.snapshot_path(client.account_id)))
            if repo.conn.total_changes == before:
                break
    now = clock()
    report.account = snapshot.account
    broker = {p.id: p for p in snapshot.positions}
    known = {t.position_id: t for t in repo.open_trades()}

    taken: set[str] = set()
    for position in snapshot.positions:
        if position.id in known:
            continue
        existing = repo.get_trade(position.id)
        if existing is not None:
            # DB'de kapali ama broker'da acik: sahipsiz kalmasin, geri ac.
            repo.reopen_trade(position.id, position.volume)
            known[position.id] = repo.get_trade(position.id)
            report.reopened.append(position.id)
            continue
        symbol = canonical(catalog, position.symbol)
        order = _matching_order(repo, position, taken)
        if order is not None:
            taken.add(order["idempotency_key"])
            repo.upsert_trade(trade_from_order(order, position, symbol, now))
            repo.update_order_state(order["idempotency_key"], "FILLED", position_id=position.id)
            report.adopted.append(position.id)
        else:
            repo.upsert_trade(manual_trade(position, symbol, now))
            report.imported.append(position.id)

    missing: list[Trade] = []
    reduced: list[Trade] = []
    for trade in known.values():
        position = broker.get(trade.position_id)
        if position is None:
            missing.append(trade)
            continue
        changed = False
        if abs(position.volume - trade.volume) > _EPS:
            if position.volume < trade.volume:
                reduced.append(trade)
            trade.volume, changed = position.volume, True
        if _differs(position.sl, trade.sl):
            if position.sl is not None and not _set_by_bot(repo, trade.position_id, position.sl):
                trade.user_sl_override = True  # kullanici botun disindan degistirmis
            if trade.initial_risk_r_price is None:
                trade.initial_risk_r_price = risk_distance(trade.side, trade.entry, position.sl)
            trade.sl, changed = position.sl, True
        if _differs(position.tp, trade.tp2):
            trade.tp2, changed = position.tp, True
        if position.sltp_order_id != trade.sltp_order_id:
            trade.sltp_order_id, changed = position.sltp_order_id, True
        if changed:
            repo.upsert_trade(trade)
            report.updated.append(trade.position_id)

    affected = missing + reduced
    if affected:
        since = max(min(t.opened_at for t in affected) - 60, now - HISTORY_DAYS * 86400)
        try:
            deals = await _close_deals(client, since)
        except ExnessError as exc:
            # Gecmis okunamadi: islemleri acik birak, bir sonraki mutabakatta yeniden denenir.
            report.errors.append(f"deal gecmisi okunamadi: {exc}")
            return report
        ids = {t.position_id for t in affected}
        last: dict[str, Deal] = {}
        for deal in sorted(deals, key=lambda d: d.time or 0.0):
            if deal.position_id in ids:
                repo.add_realized(deal.position_id, deal.id, deal.time or now, deal_pnl(deal))
                last[deal.position_id] = deal
        for trade in missing:
            deal = last.get(trade.position_id)
            if deal is None and now - trade.opened_at < FRESH_SECONDS:
                # Kapanis deal'i yok ve islem cok yeni: goruntu buyuk olasilikla bayat. Kapatma;
                # bir sonraki mutabakat karar verir.
                report.deferred.append(trade.position_id)
                continue
            repo.close_trade(trade.position_id, close_price=deal.price if deal else None,
                             closed_at=(deal.time if deal and deal.time else now))
            report.closed.append(trade.position_id)
            if deal is None:
                report.unexplained.append(trade.position_id)
    return report
