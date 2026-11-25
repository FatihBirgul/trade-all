"""Faz 1 bagimsiz incelemesinde bulunan hatalarin gerileme testleri (C = kritik, I = onemli)."""
import copy
import dataclasses

import httpx
import pytest

from tests.app_helpers import NOW, build, feed_ticks, load_market, restart, started
from tests.execution.helpers import candidate, make_world
from tests.fakes.exness import DEFAULT_INSTRUMENTS, conditions
from tradebot.api.auth import issue_token
from tradebot.api.server import create_app
from tradebot.config import BotSettings, RiskSettings
from tradebot.execution.reconcile import reconcile, risk_distance
from tradebot.exness import schema
from tradebot.exness.errors import ExnessAuthError, ExnessRateLimited, ExnessUnavailable
from tradebot.exness.limits import RateLimiter
from tradebot.market.catalog import InstrumentCatalog

METALS = {**DEFAULT_INSTRUMENTS,
          "XAGUSD": conditions("XAGUSD", category="Metals", digits=2, contract="100", sessions="weekdays"),
          "XPTUSD": conditions("XPTUSD", category="Metals", digits=2, contract="100", sessions="weekdays")}


def posts(app):
    return app.fake.calls("POST", "/positions")


async def multi(tmp_path, symbols, **kwargs):
    app = build(tmp_path, instruments=METALS, **kwargs)
    quotes = {s: load_market(app.fake, s, NOW) for s in symbols}
    await app.bot.start()
    for symbol, (bid, ask) in quotes.items():
        await feed_ticks(app, symbol, bid, ask, NOW)
    return app


async def open_one(app):
    await app.bot.on_bar_close()
    await app.fake.flush()
    return app.repo.open_trades("bot")[0]


# ---------------------------------------------------------------- C1
async def test_c1_dry_run_sends_no_management_orders(tmp_path):
    app = await started(tmp_path, dry_run=True)
    bid, ask = app.fake.prices["XAUUSD"]
    position_id = await app.fake.external_open("XAUUSD", "BUY", 0.10, sl=round(ask - 5.0, 2))
    assert app.repo.update_trade(position_id, manage=True)  # yonetim acik olsa bile
    for multiple in (1, 2, 3):
        await app.fake.set_price("XAUUSD", round(ask + 5.0 * multiple, 2), round(ask + 5.0 * multiple + 0.2, 2))
        await app.bot.manage_tick()
        await app.fake.flush()
    assert app.fake.calls("PATCH") == [] and app.fake.calls("DELETE") == [] and posts(app) == []
    assert app.repo.get_trade(position_id).volume == 0.10


async def test_c1_external_positions_are_not_managed_by_default(tmp_path):
    app = await started(tmp_path)
    _, ask = app.fake.prices["XAUUSD"]
    by_event = await app.fake.external_open("XAUUSD", "BUY", 0.10, sl=round(ask - 5.0, 2))
    assert app.repo.get_trade(by_event).manage is False
    await app.fake.set_price("XAUUSD", round(ask + 20.0, 2), round(ask + 20.2, 2))
    await app.bot.manage_tick()
    assert app.fake.calls("PATCH") == [] and app.fake.calls("DELETE") == []

    app.fake.drop_events = True
    by_reconcile = await app.fake.external_open("XAUUSD", "SELL", 0.05, sl=round(ask + 40.0, 2))
    await app.bot.reconcile_now()
    assert app.repo.get_trade(by_reconcile).manage is False


async def test_c1_manual_trade_from_app_is_managed(tmp_path):
    app = await started(tmp_path)
    token = issue_token(app.repo, now=NOW)
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot",
                                 headers={"Authorization": f"Bearer {token}"}) as http:
        await http.post("/trades", json={"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0, "lots": 0.10})
    await app.fake.flush()
    assert app.repo.open_trades("manual")[0].manage is True  # spec §6.4: varsayilan acik


def test_c1_risk_is_never_derived_from_a_profit_side_stop():
    assert risk_distance("BUY", 1.1002, 1.0972) == pytest.approx(0.0030)
    assert risk_distance("SELL", 1.1002, 1.1032) == pytest.approx(0.0030)
    assert risk_distance("BUY", 1.1002, 1.1007) is None
    assert risk_distance("SELL", 1.1002, 1.0990) is None
    assert risk_distance("BUY", 1.1002, None) is None and risk_distance("BUY", None, 1.0) is None


async def test_c1_imported_position_with_locked_in_stop_is_left_alone(tmp_path):
    w = await make_world(tmp_path)
    position_id = await w.fake.external_open("EURUSD", "BUY", 0.10)
    await w.fake.set_price("EURUSD", 1.1050, 1.1052)
    await w.fake.external_set_sl(position_id, 1.1007)  # stop zaten kar tarafinda
    trade = w.repo.get_trade(position_id)
    assert trade.sl == 1.1007 and trade.initial_risk_r_price is None


# ---------------------------------------------------------------- C2
async def test_c2_orders_in_flight_count_against_max_open(tmp_path):
    app = await multi(tmp_path, ["XAUUSD", "XAGUSD"])
    app.repo.set_bot_settings(BotSettings(dry_run=False, risk=RiskSettings(max_open_bot=1)))
    summary = await app.bot.on_bar_close()
    assert summary.candidates == 2 and summary.opened == 1 and summary.blocked == 1
    assert len(posts(app)) == 1
    await app.fake.flush()
    assert len(app.repo.open_trades("bot")) == 1


async def test_c2_orders_in_flight_count_against_currency_exposure(tmp_path):
    app = await multi(tmp_path, ["XAUUSD", "XAGUSD", "XPTUSD"])  # ucu de USD satar
    summary = await app.bot.on_bar_close()
    assert summary.candidates == 3 and len(posts(app)) == 2
    assert any("USD" in reason for reason in summary.blocked_reasons)


# ---------------------------------------------------------------- C3
async def test_c3_stale_snapshot_does_not_close_a_fresh_trade(tmp_path):
    w = await make_world(tmp_path)
    w.fake.auto_process = False  # emir kuyrukta: pozisyon henuz yok
    w.fake.lose_next_ack = True
    key = await w.executor.open(candidate(), "bot")
    assert w.repo.get_order(key)["state"] == "UNKNOWN"

    async def fill_arrives_while_snapshot_is_in_flight():
        await w.fake.flush()
    w.fake.mid_request = fill_arrives_while_snapshot_is_in_flight
    await w.executor.resolve_unknown()

    trade = w.repo.open_trades("bot")[0]
    assert trade.is_open and trade.setup_id == "setup000000000000000001"
    assert len(w.fake.positions) == 1 and w.repo.closed_trades() == []


async def test_c3_guard_holds_even_when_snapshot_cannot_be_refreshed(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    stale = schema.Snapshot(positions=(), orders=(), account=None)  # pozisyonu icermeyen bayat goruntu
    report = await reconcile(w.fake, w.repo, w.catalog, clock=lambda: w.clock["now"], snapshot=stale)
    assert report.closed == [] and report.deferred == [trade.position_id]
    assert w.repo.get_trade(trade.position_id).is_open


async def test_c3_trade_closed_in_db_but_open_at_broker_is_reopened(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    w.repo.close_trade(trade.position_id, close_price=None)  # hatali kapatilmis kayit
    report = await w.executor.reconcile()
    assert report.reopened == [trade.position_id]
    reopened = w.repo.get_trade(trade.position_id)
    assert reopened.is_open and reopened.volume == 0.10 and reopened.setup_id == trade.setup_id
    assert "trade_reopened" in [e["kind"] for e in w.repo.events()]


# ---------------------------------------------------------------- I1
async def test_i1_position_opened_and_stopped_while_blind_is_recorded(tmp_path):
    w = await make_world(tmp_path)
    w.fake.drop_events = True
    key = await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    await w.fake.set_price("EURUSD", 1.0970, 1.0972)  # stop calisti; hicbir olay gelmedi
    w.advance(30)
    await w.executor.resolve_unknown()
    assert w.repo.get_order(key)["state"] == "FILLED"
    trade = w.repo.closed_trades()[0]
    assert (trade.origin, trade.setup_id, trade.close_price) == ("bot", "setup000000000000000001", 1.0972)
    assert w.repo.bot_realized_pnl() == pytest.approx(w.fake.balance - 10_000.0, abs=0.01)
    assert w.repo.bot_realized_pnl() < 0 and len(w.fake.calls("POST", "/positions")) == 1


# ---------------------------------------------------------------- I2
class FakeTime:
    def __init__(self):
        self.now, self.sleeps = 0.0, []

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


async def test_i2_trading_request_is_not_stuck_behind_a_candle_wait():
    import asyncio
    release = asyncio.Event()
    waits = []

    async def blocking_sleep(seconds):
        waits.append(seconds)
        await release.wait()

    limiter = RateLimiter(clock=lambda: 0.0, sleep=blocking_sleep)
    limiter.configure(global_rate=(1000, 60.0), methods=[
        ("GET", "/v1/market-data/accounts/{account_id}/candles", 1, 60.0),
        ("DELETE", "/v1/trading/accounts/{account_id}/positions/{position_id}", 10, 60.0)])
    await limiter.acquire("GET", "/v1/market-data/accounts/1/candles?x=1")
    waiting = asyncio.create_task(limiter.acquire("GET", "/v1/market-data/accounts/1/candles?x=2"))
    await asyncio.sleep(0)
    assert waits == [60.0] and not waiting.done()
    await asyncio.wait_for(limiter.acquire("DELETE", "/v1/trading/accounts/1/positions/7"), timeout=1)
    waiting.cancel()


async def test_i2_reads_leave_room_for_orders_in_the_global_budget():
    fake = FakeTime()
    limiter = RateLimiter(clock=fake.clock, sleep=fake.sleep)
    limiter.configure(global_rate=(10, 60.0), methods=[])
    for _ in range(9):
        await limiter.acquire("GET", "/v1/x")
    assert fake.sleeps == []
    await limiter.acquire("POST", "/v1/trading/accounts/1/positions")  # ayrilan pay
    assert fake.sleeps == []
    await limiter.acquire("GET", "/v1/x")
    assert sum(fake.sleeps) >= 60.0


# ---------------------------------------------------------------- I3
async def test_i3_event_during_another_positions_request_is_not_overwritten(tmp_path):
    app = await multi(tmp_path, ["XAUUSD", "XAGUSD"])
    await app.bot.on_bar_close()
    await app.fake.flush()
    first, second = app.repo.open_trades("bot")
    risk = first.initial_risk_r_price
    await app.fake.set_price(first.symbol, round(first.entry + risk, 2), round(first.entry + risk + 0.2, 2))

    async def second_is_stopped_out():
        await app.fake.set_price(second.symbol, second.sl - 0.5, second.sl - 0.3)
    app.fake.mid_request = second_is_stopped_out
    await app.bot.manage_tick()  # ilk pozisyonun PATCH'i beklenirken ikincisi kapanir
    await app.fake.flush()

    closed = app.repo.get_trade(second.position_id)
    assert not closed.is_open and closed.volume == 0.0 and closed.pnl < 0
    assert [t.position_id for t in app.repo.open_trades("bot")] == [first.position_id]


# ---------------------------------------------------------------- I4 / I5
async def test_i4_unreadable_operation_status_does_not_lock_the_position_forever(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    await w.fake.set_price("EURUSD", 1.1040, 1.1042)
    w.fake.drop_events = True
    key = await w.executor.modify(trade.position_id, sl=1.1003)
    await w.fake.flush()
    w.repo.update_order_state(key, "ACKED", operation_id="op-not-numeric")  # durum sorgulanamaz
    w.advance(30)
    await w.executor.resolve_unknown()
    assert w.repo.get_order(key)["state"] == "ACKED"  # henuz erken
    w.advance(120)
    await w.executor.resolve_unknown()
    assert w.repo.get_order(key)["state"] not in ("PENDING", "ACKED", "UNKNOWN")
    assert w.repo.get_trade(trade.position_id).sl == 1.1003  # gercek durum mutabakatla esitlendi
    assert await w.executor.modify(trade.position_id, sl=1.1005) is not None


async def test_i5_user_close_is_not_blocked_by_a_pending_bot_modify(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    await w.fake.set_price("EURUSD", 1.1040, 1.1042)
    w.fake.drop_events = True
    assert await w.executor.modify(trade.position_id, sl=1.1003) is not None  # sonucu gelmedi
    assert await w.executor.close(trade.position_id, volume=0.05) is None  # botun kendi kapamasi bekler
    key = await w.executor.close(trade.position_id, user=True)
    assert key is not None and len(w.fake.calls("DELETE")) == 1
    assert await w.executor.close(trade.position_id, user=True) is None  # ikinci kapama: zaten bekliyor


async def test_i5_close_all_reports_skipped_positions(tmp_path):
    app = await started(tmp_path)
    trade = await open_one(app)
    token = issue_token(app.repo, now=NOW)
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot",
                                 headers={"Authorization": f"Bearer {token}"}) as http:
        first = (await http.post("/bot/close-all", json={"confirm": "CLOSE-ALL"})).json()
        second = (await http.post("/bot/close-all", json={"confirm": "CLOSE-ALL"})).json()
    assert first == {"requested": 1, "skipped": [], "stopped": True}
    assert second == {"requested": 0, "skipped": [trade.position_id], "stopped": True}


# ---------------------------------------------------------------- I6
async def test_i6_missing_broker_stop_is_detected_and_rearmed(tmp_path):
    app = await started(tmp_path)
    app.fake.drop_sltp_on_open = True  # broker SL/TP emrini olusturmadi
    trade = await open_one(app)
    assert trade.sl is None and trade.sltp_order_id is None and trade.initial_risk_r_price > 0
    expected = round(trade.entry - trade.initial_risk_r_price, 2)

    await app.bot.manage_tick()  # dolumdan hemen sonra: olay gecikmis olabilir, bekle
    assert app.fake.calls("POST", "/orders") == []
    app.advance(10)
    await feed_ticks(app, "XAUUSD", *app.fake.prices["XAUUSD"], app.clock["now"], count=2)
    await app.bot.manage_tick()
    await app.fake.flush()
    created = app.fake.calls("POST", "/orders")
    assert len(created) == 1 and float(created[0][2]["stop_loss_price"]) == pytest.approx(expected)
    armed = app.repo.get_trade(trade.position_id)
    assert armed.sl == pytest.approx(expected) and armed.sltp_order_id is not None
    assert armed.user_sl_override is False
    assert "sl_missing" in app.kinds() and "sl_missing" in app.notifier.kinds()
    await app.bot.manage_tick()
    assert len(app.fake.calls("POST", "/orders")) == 1  # tekrar tekrar kurulmaz


async def test_i6_stop_present_at_broker_but_absent_from_event_is_confirmed_not_duplicated(tmp_path):
    app = await started(tmp_path)
    app.fake.omit_sltp_in_event = True  # broker'da SL var, yalnizca dolum olayinda gelmedi
    trade = await open_one(app)
    assert trade.sl is None
    app.advance(10)
    await feed_ticks(app, "XAUUSD", *app.fake.prices["XAUUSD"], app.clock["now"], count=2)
    await app.bot.manage_tick()
    confirmed = app.repo.get_trade(trade.position_id)
    assert confirmed.sl is not None and confirmed.sltp_order_id is not None
    assert app.fake.calls("POST", "/orders") == [] and "sl_missing" not in app.kinds()


async def test_i6_price_already_through_missing_stop_closes_position(tmp_path):
    app = await started(tmp_path)
    app.fake.drop_sltp_on_open = True
    trade = await open_one(app)
    level = trade.entry - trade.initial_risk_r_price
    app.advance(10)
    await app.fake.set_price("XAUUSD", round(level - 1.0, 2), round(level - 0.8, 2))
    await app.bot.manage_tick()
    await app.fake.flush()
    assert not app.repo.get_trade(trade.position_id).is_open and len(app.fake.calls("DELETE")) == 1


# ---------------------------------------------------------------- I8
async def test_i8_replaced_sltp_order_keeps_the_stop(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    event = {"event_type": "transaction_event", "status": "success", "event_time": "2027-01-15T08:00:00+00:00",
             "payload": {"orders": [
                 {"order_id": "9001", "position_id": trade.position_id, "order_type": "sltp", "state": "placed",
                  "stop_loss_price": "1.10300", "take_profit_price": "1.10920",
                  "create_time": "2027-01-15T08:00:00+00:00"},
                 {"order_id": trade.sltp_order_id, "position_id": trade.position_id, "order_type": "sltp",
                  "state": "cancelled", "create_time": "2027-01-15T07:00:00+00:00"}]}}
    for raw in (event, {**event, "payload": {"orders": list(reversed(event["payload"]["orders"]))}}):
        await w.executor.on_transaction(schema.parse_ws_event(copy.deepcopy(raw))[1])
        current = w.repo.get_trade(trade.position_id)
        assert current.sl == 1.103 and current.sltp_order_id == "9001"
    stale_cancel = {**event, "payload": {"orders": [
        {"order_id": "1", "position_id": trade.position_id, "order_type": "sltp", "state": "cancelled",
         "create_time": "2027-01-15T07:00:00+00:00"}]}}
    await w.executor.on_transaction(schema.parse_ws_event(stale_cancel)[1])
    assert w.repo.get_trade(trade.position_id).sl == 1.103  # baska bir emrin iptali stopu silmez


# ---------------------------------------------------------------- I9
async def test_i9_catalog_refresh_stops_on_rate_limit_and_auth_errors():
    class Client:
        account_id = "1"

        def __init__(self, error):
            self.error, self.calls = error, 0

        async def get(self, path):
            if path.endswith("/instruments"):
                return {"instruments": ["EURUSD", "GBPUSD", "XAUUSD", "BTCUSD"]}
            self.calls += 1
            raise self.error

    for error in (ExnessRateLimited("REQUEST_RATE_LIMIT", code=3015), ExnessAuthError("AUTH_INVALID_SIGNATURE", code=1001)):
        client = Client(error)
        with pytest.raises(type(error)):
            await InstrumentCatalog(client).refresh()
        assert client.calls == 1  # kalan enstrumanlar icin istek gonderilmedi


def test_catalog_ignores_incomplete_update_but_disables_trading():
    catalog = InstrumentCatalog(client=None)
    full = schema.parse_instrument(conditions("EURUSD"))
    catalog.update(full)
    catalog.update(schema.parse_instrument({"instrument": "EURUSD", "category": "Forex", "base_currency": "EUR",
                                            "quote_currency": "USD"}))
    kept = catalog.get("EURUSD")
    assert kept.contract_size == 100000.0 and kept.tick_size == full.tick_size and kept.tradable is False


# ---------------------------------------------------------------- I10
async def test_i10_events_stream_reconnect_triggers_reconcile(tmp_path):
    app = await started(tmp_path)
    trade = await open_one(app)
    events = app.streams[1]
    events.go_down()
    await app.fake.set_price("XAUUSD", trade.sl - 0.5, trade.sl - 0.3)  # kopukken stop calisti
    assert app.repo.get_trade(trade.position_id).is_open
    events.come_up()  # yeniden baglandi ama sunucu goruntu gondermedi
    await app.bot.heartbeat()
    closed = app.repo.get_trade(trade.position_id)
    assert not closed.is_open and closed.pnl < 0


# ---------------------------------------------------------------- I12
async def test_i12_breakeven_is_announced_only_after_broker_confirms(tmp_path):
    app = await started(tmp_path)
    trade = await open_one(app)
    risk = trade.initial_risk_r_price
    await app.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    app.fake.reject_next = (5005, "TRADING_RULE_INVALID_PRICE_LEVELS")
    await app.bot.manage_tick()
    assert "sl_breakeven" not in app.kinds()  # istek gonderildi, onay yok
    await app.fake.flush()
    rejected = app.repo.get_trade(trade.position_id)
    assert rejected.be_done is False and rejected.sl == trade.sl
    assert "sl_breakeven" not in app.notifier.kinds() and "order_rejected" in app.notifier.kinds()

    app.advance(61)  # bekleme suresi doldu
    await feed_ticks(app, "XAUUSD", *app.fake.prices["XAUUSD"], app.clock["now"], count=2)
    await app.bot.manage_tick()
    await app.fake.flush()
    assert app.repo.get_trade(trade.position_id).be_done is True
    assert app.notifier.kinds().count("sl_breakeven") == 1


# ---------------------------------------------------------------- I13
async def test_i13_late_fill_after_order_was_given_up_is_still_the_bots_trade(tmp_path):
    w = await make_world(tmp_path)
    w.fake.auto_process = False
    w.fake.lose_next_ack = True
    key = await w.executor.open(candidate(), "bot")
    w.advance(130)
    await w.executor.resolve_unknown()
    assert w.repo.get_order(key)["state"] == "CANCELLED"
    await w.fake.flush()  # dolum cok gec geldi
    trade = w.repo.open_trades()[0]
    assert (trade.origin, trade.setup_id) == ("bot", "setup000000000000000001")
    assert w.repo.get_order(key)["state"] == "FILLED"


# ---------------------------------------------------------------- kucukler
async def test_persistent_auth_failure_is_reported_once_and_stops_management_requests(tmp_path):
    app = await started(tmp_path)
    trade = await open_one(app)
    risk = trade.initial_risk_r_price
    await app.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    before = len(app.fake.requests)
    for _ in range(4):  # bir saat: dort tarama
        app.fake.fail_next = ExnessAuthError("AUTH_INVALID_SIGNATURE", code=1001, status=401)
        await app.bot.on_bar_close()
        for _ in range(20):
            await app.bot.manage_tick()
        app.advance(900)
    assert app.notifier.kinds().count("auth_error") == 1
    assert len(app.fake.requests) - before == 4  # tarama basina tek deneme; yonetim istegi yok
    assert app.fake.calls("PATCH") == []


async def test_manual_trade_with_client_id_is_not_duplicated_on_retry(tmp_path):
    app = await started(tmp_path)
    token = issue_token(app.repo, now=NOW)
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    body = {"symbol": "XAUUSD", "side": "BUY", "sl_distance": 5.0, "lots": 0.05, "client_id": "app-7f3a9c21"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot",
                                 headers={"Authorization": f"Bearer {token}"}) as http:
        first = await http.post("/trades", json=body)
        second = await http.post("/trades", json=body)
        assert first.status_code == second.status_code == 200
        assert first.json()["order"] == second.json()["order"] == "man-app-7f3a9c21"
        assert (await http.post("/trades", json={**body, "client_id": "x"})).status_code == 422
    await app.fake.flush()
    assert len(posts(app)) == 1 and len(app.repo.open_trades("manual")) == 1


async def test_push_data_keeps_event_kind(tmp_path):
    w = await make_world(tmp_path)
    w.fake.reject_next = (5006, "TRADING_RULE_INSUFFICIENT_MARGIN")
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    kind, _, _, data = w.notifier.sent[0]
    assert kind == "order_rejected" and "kind" not in data and data["order_kind"] == "open"
    from tradebot.notify.expo import _safe_data
    assert _safe_data("order_rejected", {"kind": "modify", "symbol": "EURUSD"}) == \
        {"kind": "order_rejected", "symbol": "EURUSD"}


async def test_open_atr_candles_refresh_even_when_scan_is_skipped(tmp_path):
    app = await started(tmp_path)
    await open_one(app)
    app.repo.set_bot_state(stopped=True)
    before = len(app.fake.calls("GET", "/candles"))
    app.advance(1800)
    summary = await app.bot.on_bar_close()
    assert summary.skipped == "stopped" and len(app.fake.calls("GET", "/candles")) == before + 1


async def test_start_capital_is_set_later_if_account_was_unreadable_at_start(tmp_path):
    app = await started(tmp_path)
    app.repo.conn.execute("UPDATE bot_state SET start_capital = NULL, start_at = NULL")
    await app.bot.heartbeat()
    assert app.repo.bot_state().start_capital == 10_000.0


def test_revoke_removes_all_tokens(tmp_path):
    from tests.exness.test_client import settings
    from tradebot.api.auth import verify_token
    from tradebot.runtime import revoke_tokens
    from tradebot.store.repo import Repo
    config = settings(TRADEBOT_DB_PATH=str(tmp_path / "bot.db"))
    repo = Repo(config.db_path)
    token = issue_token(repo, now=1.0)
    assert verify_token(repo, token)
    assert revoke_tokens(config) == 1
    assert not verify_token(repo, token)
