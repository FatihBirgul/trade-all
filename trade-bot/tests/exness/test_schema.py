import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tradebot.exness import schema

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def ts(*args):
    return datetime(*args, tzinfo=timezone.utc).timestamp()


def test_parse_account_combines_details_and_state():
    account = schema.parse_account(load("account"), load("snapshot")["account_state"])
    assert account.currency == "USC"
    assert (account.balance, account.equity, account.margin) == (3000.0, 3012.5, 100.0)
    assert account.margin_free == pytest.approx(2912.5)
    assert account.leverage == 2000.0
    assert account.can_open is True


def test_cent_account_currency_usc():
    assert schema.parse_account(load("account"), {"balance": "1", "equity": "1", "used_margin": "0"}).currency == "USC"


def test_account_close_only_cannot_open():
    raw = load("account")
    raw["settings"]["account_status"] = "close_only"
    assert schema.parse_account(raw, load("snapshot")["account_state"]).can_open is False
    raw["settings"]["account_status"] = "active"
    raw["settings"]["trade_mode"] = "trading_disabled"
    assert schema.parse_account(raw, load("snapshot")["account_state"]).can_open is False


def test_parse_instrument_forex():
    inst = schema.parse_instrument(load("instrument_eurusd"))
    assert (inst.symbol, inst.broker_symbol, inst.kind) == ("EURUSD", "EURUSD", "forex")
    assert inst.tick_size == pytest.approx(0.00001) and inst.digits == 5
    assert (inst.contract_size, inst.volume_min, inst.volume_max, inst.volume_step) == (100000.0, 0.01, 200.0, 0.01)
    assert (inst.currency_base, inst.currency_profit) == ("EUR", "USD")
    assert inst.tradable is True and inst.stops_level == 0
    assert inst.exec_mode == "market" and inst.calc_mode == "forex"
    assert inst.trading_hours["timezone"] == "UTC"
    assert inst.trading_hours["weekly"]["0"] == [["00:00", "24:00"]]
    assert inst.trading_hours["weekly"]["4"] == [["00:00", "24:00"]]
    assert "5" not in inst.trading_hours["weekly"] and "6" not in inst.trading_hours["weekly"]


def test_cent_suffix_maps_to_canonical_symbol():
    inst = schema.parse_instrument(load("instrument_cent_eurusd"))
    assert (inst.symbol, inst.broker_symbol, inst.kind) == ("EURUSD", "EURUSDc", "forex")
    weekly = inst.trading_hours["weekly"]
    assert weekly["6"] == [["21:05", "24:00"]]
    assert weekly["0"] == [["00:00", "24:00"]]
    assert weekly["4"] == [["00:00", "20:59"]]
    assert "5" not in weekly


def test_metal_sessions_keep_daily_break():
    inst = schema.parse_instrument(load("instrument_xauusd"))
    assert inst.kind == "metal" and inst.tick_size == pytest.approx(0.001)
    weekly = inst.trading_hours["weekly"]
    assert weekly["0"] == [["00:00", "20:58"], ["22:01", "24:00"]]
    assert weekly["6"] == [["22:05", "24:00"]]
    assert weekly["4"] == [["00:00", "20:58"]]


def test_crypto_hours_cover_whole_week():
    inst = schema.parse_instrument(load("instrument_btcusd"))
    assert inst.kind == "crypto"
    assert inst.trading_hours["weekly"] == {str(day): [["00:00", "24:00"]] for day in range(7)}


def test_stocks_and_indices_marked_other():
    assert schema.parse_instrument(load("instrument_stock")).kind == "other"
    assert schema.parse_instrument(load("instrument_index")).kind == "other"


def test_kind_falls_back_to_currency_structure_without_category():
    raw = load("instrument_eurusd")
    del raw["category"]
    assert schema.parse_instrument(raw).kind == "forex"
    raw = load("instrument_xauusd")
    raw["category"] = "Forex"  # bazi brokerlar altini forex grubunda listeler
    assert schema.parse_instrument(raw).kind == "metal"
    raw = load("instrument_btcusd")
    del raw["category"]
    assert schema.parse_instrument(raw).kind == "crypto"
    raw = load("instrument_stock")
    del raw["category"]
    assert schema.parse_instrument(raw).kind == "other"


def test_instrument_without_sessions_has_no_hours():
    raw = load("instrument_eurusd")
    del raw["trade_sessions"]
    assert schema.parse_instrument(raw).trading_hours is None


def test_instrument_disabled_or_incomplete_is_not_tradable():
    raw = load("instrument_eurusd")
    raw["trade_mode"] = "trading_disabled"
    assert schema.parse_instrument(raw).tradable is False
    raw = load("instrument_eurusd")
    raw["volume_step"] = None
    assert schema.parse_instrument(raw).tradable is False


def test_parse_candles_bid():
    rows = schema.parse_candles(load("candles_bid"))
    assert rows[0] == {"time": int(ts(2026, 3, 16, 12, 30)), "open": 1.08321, "high": 1.0835, "low": 1.0831,
                       "close": 1.0834, "tick_volume": 124.0}
    assert rows[1]["time"] == int(ts(2026, 3, 16, 12, 45))
    assert all(type(row["time"]) is int for row in rows)


def test_parse_candle_rejects_bid_ask_shape():
    with pytest.raises(ValueError):
        schema.parse_candle({"time": "2026-03-16T12:30:00+00:00", "bid": {"open": 1}, "ask": {"open": 1}})


def test_parse_tick():
    tick = schema.parse_tick(load("tick"))
    assert (tick.symbol, tick.bid, tick.ask) == ("XAUUSD", 2650.12, 2650.32)
    assert tick.time == pytest.approx(ts(2026, 3, 16, 12, 54, 30) + 0.25)
    assert schema.parse_tick({"id": "x", "code": 3000, "error_message": "REQUEST_INVALID"}) is None


def test_parse_snapshot_joins_sltp_orders_to_positions():
    snap = schema.parse_snapshot(load("snapshot"))
    first, second = snap.positions
    assert (first.id, first.symbol, first.side, first.volume, first.initial_volume) == ("2001", "EURUSD", "BUY", 0.5, 1.0)
    assert (first.open_price, first.sl, first.tp, first.sltp_order_id) == (1.08, 1.075, 1.095, "1002")
    assert first.opened_at == ts(2026, 12, 14, 11, 46, 30)
    assert (second.side, second.sl, second.tp, second.sltp_order_id) == ("SELL", None, None, None)
    assert snap.account.equity == 3012.5
    assert [o.id for o in snap.orders] == ["1001", "1002"]


def test_parse_transaction_event_open():
    kind, event = schema.parse_ws_event(load("event_open"))
    assert kind == "transaction"
    assert (event.operation_id, event.client_request_id, event.status) == ("789", "bot-abc123def456", "success")
    assert (event.position_id, event.price, event.volume) == ("2001", 1.0834, 1.0)
    assert event.reason is None and event.error_code is None
    assert event.positions[0].sl == 1.08 and event.positions[0].tp == 1.0936
    assert event.account.balance == 10000.0


def test_parse_transaction_event_close_carries_profit_and_reason():
    kind, event = schema.parse_ws_event(load("event_close"))
    assert kind == "transaction" and event.operation_id is None
    deal = event.deals[0]
    assert (deal.type, deal.position_id, deal.price, deal.profit, deal.commission) == ("close", "2001", 1.08, -340.0, -0.2)
    assert event.positions[0].closed is True
    assert event.orders[0].reason == "sl"


def test_parse_transaction_event_rejected():
    kind, event = schema.parse_ws_event(load("event_rejected"))
    assert kind == "transaction"
    assert (event.status, event.error_code, event.reason) == ("rejected", 5006, "TRADING_RULE_INSUFFICIENT_MARGIN")
    assert event.positions == () and event.position_id is None


def test_parse_other_ws_events():
    kind, state = schema.parse_ws_event(load("event_account_state"))
    assert kind == "account" and state.equity == 10018.0
    kind, snap = schema.parse_ws_event({"event_type": "trading_state_snapshot", "payload": load("snapshot")})
    assert kind == "snapshot" and len(snap.positions) == 2
    assert schema.parse_ws_event({"event_type": "hmr_snapshot", "periods": []})[0] == "other"
    assert schema.parse_ws_event({"id": "s1", "code": 3000, "error_message": "REQUEST_INVALID"})[0] == "error"


def test_parse_ack_and_operation_status():
    ack = schema.parse_ack(load("ack"))
    assert (ack.operation_id, ack.client_request_id) == ("789", "bot-abc123def456")
    op = schema.parse_operation(load("operation_rejected"))
    assert (op.operation_id, op.status, op.error_code, op.reason) == ("791", "rejected", 5005, "TRADING_RULE_INVALID_PRICE_LEVELS")
    assert op.final is True
    assert schema.parse_operation({"operation_id": "1", "status": "pending"}).final is False


def test_parse_limits():
    limits = schema.parse_limits(load("limits"))
    assert limits.global_rate == (600, 60.0)
    assert ("GET", "/v1/market-data/accounts/{account_id}/candles", 120, 60.0) in limits.methods
    assert limits.max_candles == 1000
    assert (limits.history_range_days, limits.history_age_days) == (31, 365)
    assert limits.tick_subscription_rate == (100, 1.0, 100)
    assert schema.parse_limits({}).max_candles is None and schema.parse_limits({}).tick_subscription_rate is None


def test_parse_deals():
    deals, cursor = schema.parse_deals(load("deals"))
    assert cursor == "abc"
    assert [d.type for d in deals] == ["open", "close", "balance"]
    assert deals[1].profit == -340.0 and deals[1].time == ts(2026, 12, 14, 13)
    assert deals[2].position_id is None
    assert schema.parse_deals({"items": []}) == ([], None)


def test_open_position_request_always_has_stop_loss():
    inst = schema.parse_instrument(load("instrument_eurusd"))
    path, body = schema.open_position_request("123", inst, "BUY", 0.03, sl=1.07501, tp=1.095)
    assert path == "/v1/trading/accounts/123/positions"
    assert body == {"instrument": "EURUSD", "side": "buy", "volume": "0.03",
                    "stop_loss_price": "1.07501", "take_profit_price": "1.09500"}
    for bad in (None, 0, -1.0, float("nan")):
        with pytest.raises(ValueError):
            schema.open_position_request("123", inst, "BUY", 0.03, sl=bad, tp=1.095)


def test_open_position_request_uses_broker_symbol_and_volume_grid():
    inst = schema.parse_instrument(load("instrument_cent_eurusd"))
    _, body = schema.open_position_request("123", inst, "SELL", 0.1 + 0.2, sl=1.1, tp=None)
    assert body["instrument"] == "EURUSDc" and body["side"] == "sell" and body["volume"] == "0.30"
    assert "take_profit_price" not in body
    with pytest.raises(ValueError):
        schema.open_position_request("123", inst, "SELL", 0.001, sl=1.1, tp=None)
    with pytest.raises(ValueError):
        schema.open_position_request("123", inst, "HOLD", 0.01, sl=1.1, tp=None)


def test_open_position_request_instant_execution_needs_price():
    raw = load("instrument_eurusd")
    raw["exec_mode"] = "instant"
    inst = schema.parse_instrument(raw)
    with pytest.raises(ValueError):
        schema.open_position_request("123", inst, "BUY", 0.01, sl=1.07, tp=None)
    _, body = schema.open_position_request("123", inst, "BUY", 0.01, sl=1.07, tp=None, price=1.08, deviation_points=20)
    assert body["price"] == "1.08000" and body["deviation"] == "20"


def test_sltp_requests():
    path, body = schema.sltp_create_request("123", "2001", sl=1.0751, tp=None, digits=5)
    assert path == "/v1/trading/accounts/123/orders"
    assert body == {"position_id": "2001", "type": "sltp", "stop_loss_price": "1.07510"}
    path, body = schema.sltp_modify_request("123", "1002", sl=1.08, tp=1.1, digits=5)
    assert path == "/v1/trading/accounts/123/orders/1002"
    assert body == {"stop_loss_price": "1.08000", "take_profit_price": "1.10000"}
    with pytest.raises(ValueError):
        schema.sltp_modify_request("123", "1002", sl=None, tp=None, digits=5)
    with pytest.raises(ValueError):
        schema.sltp_create_request("123", "2001", sl=None, tp=None, digits=5)


def test_close_position_path():
    assert schema.close_position_path("123", "2001") == "/v1/trading/accounts/123/positions/2001"
    assert schema.close_position_path("123", "2001", volume=0.5, volume_step=0.01) == \
        "/v1/trading/accounts/123/positions/2001?volume=0.50"
    with pytest.raises(ValueError):
        schema.close_position_path("123", "2001", volume=0, volume_step=0.01)


def test_candles_path_needs_no_url_escaping():
    path = schema.candles_path("123", "EURUSDc", "M15", ts(2026, 3, 16, 12), ts(2026, 3, 16, 13))
    assert path == ("/v1/market-data/accounts/123/candles?instrument=EURUSDc&timeframe=M15"
                    "&from=2026-03-16T12:00:00Z&to=2026-03-16T13:00:00Z")
    assert schema.candles_path("123", "EURUSD", "H4", ts(2026, 3, 16, 12), count=-256).endswith("&count=-256")
    with pytest.raises(ValueError):
        schema.candles_path("123", "EURUSD", "M7", ts(2026, 3, 16, 12), count=5)
    with pytest.raises(ValueError):
        schema.candles_path("123", "EUR/USD", "M15", ts(2026, 3, 16, 12), count=5)


def test_other_paths_and_subscriptions():
    assert schema.account_path("1") == "/v1/configuration/accounts/1/account"
    assert schema.limits_path("1") == "/v1/configuration/accounts/1/limits"
    assert schema.instruments_path("1") == "/v1/configuration/accounts/1/instruments"
    assert schema.instrument_path("1", "EURUSDc") == "/v1/configuration/accounts/1/instruments/EURUSDc/conditions"
    assert schema.snapshot_path("1") == "/v1/trading/accounts/1/snapshot"
    assert schema.operation_path("1", "789") == "/v1/trading/accounts/1/operations/789"
    assert schema.ticks_ws_path("1") == "/v1/server-events/accounts/1/ws/ticks"
    assert schema.events_ws_path("1") == "/v1/server-events/accounts/1/ws/events"
    assert schema.deals_path("1", start=ts(2026, 12, 14), end=ts(2026, 12, 15), limit=200) == \
        "/v1/history/accounts/1/deals?from=2026-12-14T00:00:00Z&to=2026-12-15T00:00:00Z&limit=200"
    assert schema.deals_path("1", cursor="abc", limit=200) == "/v1/history/accounts/1/deals?cursor=abc&limit=200"
    assert schema.subscribe_ticks("t1", ["EURUSD", "XAUUSD"]) == \
        {"id": "t1", "subscribe": {"event": "ticks", "instruments": ["EURUSD", "XAUUSD"]}}
    assert schema.subscribe_events("e1", "transactions") == {"id": "e1", "subscribe": {"event": "transactions"}}
    assert schema.parse_instrument_names({"instruments": ["EURUSD", "XAUUSD"]}) == ["EURUSD", "XAUUSD"]
