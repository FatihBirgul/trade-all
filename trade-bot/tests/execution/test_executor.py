import pytest

from tests.execution.helpers import candidate, make_world
from tradebot.execution.reconcile import reconcile
from tradebot.exness.errors import ExnessRateLimited, ExnessUnavailable


def opens(world):
    return world.fake.calls("POST", "/positions")


async def test_open_fills_and_records_bot_trade(tmp_path):
    w = await make_world(tmp_path)
    key = await w.executor.open(candidate(), "bot")
    assert key == "bot-setup000000000000000001"
    await w.fake.flush()
    trade = w.repo.open_trades("bot")[0]
    assert (trade.symbol, trade.side, trade.volume, trade.entry) == ("EURUSD", "BUY", 0.10, 1.1002)
    assert (trade.sl, trade.tp1, trade.tp2) == (1.0972, 1.1062, 1.1092)
    assert trade.initial_risk_r_price == pytest.approx(0.0030)
    assert trade.setup_id == "setup000000000000000001" and trade.strategy_id == "fx_trend_momentum_v6"
    assert trade.sltp_order_id is not None and trade.initial_volume == 0.10 and trade.manage is True
    order = w.repo.get_order(key)
    assert order["state"] == "FILLED" and order["position_id"] == trade.position_id
    assert "trade_opened" in w.notifier.kinds()
    assert [e["kind"] for e in w.repo.events()] == ["trade_opened"]


async def test_open_always_includes_sl(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    body = opens(w)[0][2]
    assert body["stop_loss_price"] == "1.09720" and body["take_profit_price"] == "1.10920"  # broker TP = TP2 (3R)
    assert body["instrument"] == "EURUSD" and body["volume"] == "0.10" and body["side"] == "buy"
    import dataclasses
    broken = dataclasses.replace(candidate(setup="setup000000000000000002"), stop_loss=None)
    with pytest.raises(ValueError):
        await w.executor.open(broken, "bot")
    assert len(opens(w)) == 1
    with pytest.raises(ValueError):
        await w.executor.open_manual("EURUSD", "BUY", 0.1, sl=None, tp=None)
    assert len(opens(w)) == 1


async def test_same_setup_never_submitted_twice(tmp_path):
    w = await make_world(tmp_path)
    for _ in range(3):
        await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    await w.executor.open(candidate(), "bot")  # doldu; yine gonderilmez
    assert len(opens(w)) == 1 and len(w.repo.open_trades()) == 1

    # Servis yeniden baslamis gibi: yeni Executor ayni depoyla
    from tradebot.execution.executor import Executor
    again = Executor(w.fake, w.repo, w.notifier, w.catalog, clock=lambda: w.clock["now"])
    await again.open(candidate(), "bot")
    assert len(opens(w)) == 1


async def test_ack_then_disconnect_resolves_without_resubmit(tmp_path):
    w = await make_world(tmp_path)
    w.fake.drop_events = True  # ACK gelir, WS kopuktur: dolum olayi kaybolur
    key = await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    assert w.repo.get_order(key)["state"] == "ACKED" and w.repo.open_trades() == []

    w.advance(30)
    await w.executor.resolve_unknown()
    trade = w.repo.open_trades("bot")[0]
    assert trade.setup_id == "setup000000000000000001" and trade.sl == 1.0972
    assert w.repo.get_order(key)["state"] == "FILLED"
    assert len(opens(w)) == 1  # yeniden gonderilmedi
    assert len(w.fake.calls("GET", "/operations/")) == 1
    await w.executor.resolve_unknown()
    assert len(w.fake.calls("GET", "/operations/")) == 1 and len(w.repo.open_trades()) == 1


async def test_lost_ack_is_matched_by_client_request_id(tmp_path):
    w = await make_world(tmp_path)
    w.fake.lose_next_ack = True  # istek islendi ama yanit kayboldu
    key = await w.executor.open(candidate(), "bot")
    assert w.repo.get_order(key)["state"] == "UNKNOWN"
    await w.fake.flush()  # olay client_request_id ile gelir
    assert w.repo.get_order(key)["state"] == "FILLED"
    assert w.repo.open_trades("bot")[0].setup_id == "setup000000000000000001"
    assert len(opens(w)) == 1


async def test_lost_ack_and_lost_event_adopts_position_on_resolve(tmp_path):
    w = await make_world(tmp_path)
    w.fake.lose_next_ack = True
    w.fake.drop_events = True
    key = await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    w.advance(30)
    await w.executor.resolve_unknown()
    trade = w.repo.open_trades()[0]
    assert trade.origin == "bot" and trade.setup_id == "setup000000000000000001"
    assert w.repo.get_order(key)["state"] == "FILLED" and len(opens(w)) == 1


async def test_network_failure_before_send_is_never_resent(tmp_path):
    w = await make_world(tmp_path)
    w.fake.fail_next = ExnessUnavailable("ag hatasi: ConnectError")
    key = await w.executor.open(candidate(), "bot")
    assert w.repo.get_order(key)["state"] == "UNKNOWN"
    await w.executor.resolve_unknown()  # hemen: henuz karar verme
    assert w.repo.get_order(key)["state"] == "UNKNOWN"
    w.advance(120)
    await w.executor.resolve_unknown()
    assert w.repo.get_order(key)["state"] == "CANCELLED"
    await w.executor.open(candidate(), "bot")
    assert len(opens(w)) == 1 and w.repo.open_trades() == [] and w.fake.positions == {}
    assert "order_unknown" in [e["kind"] for e in w.repo.events()]


async def test_rejection_records_event_and_notifies(tmp_path):
    w = await make_world(tmp_path)
    w.fake.reject_next = (5006, "TRADING_RULE_INSUFFICIENT_MARGIN")
    key = await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    order = w.repo.get_order(key)
    assert order["state"] == "REJECTED" and "INSUFFICIENT_MARGIN" in order["error"]
    event = w.repo.events()[-1]
    assert event["kind"] == "order_rejected" and event["level"] == "error"
    assert event["data"]["code"] == 5006 and event["data"]["symbol"] == "EURUSD"
    assert event["data"]["order_kind"] == "open" and "kind" not in event["data"]
    assert w.notifier.kinds() == ["order_rejected"]
    assert w.repo.open_trades() == []
    await w.executor.open(candidate(), "bot")
    assert len(opens(w)) == 1


async def test_sync_rate_limit_is_recorded_once_without_retry(tmp_path):
    w = await make_world(tmp_path)
    w.fake.fail_next = ExnessRateLimited("REQUEST_RATE_LIMIT", retry_after=5, code=3015)
    key = await w.executor.open(candidate(), "bot")
    assert w.repo.get_order(key)["state"] == "REJECTED"
    assert len(opens(w)) == 1 and w.notifier.kinds() == ["order_rejected"]


async def test_modify_patches_existing_sltp_and_updates_trade(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    await w.fake.set_price("EURUSD", 1.1040, 1.1042)  # fiyat lehte: SL girisin ustune cekilebilir
    key = await w.executor.modify(trade.position_id, sl=1.1003)
    assert key is not None
    assert await w.executor.modify(trade.position_id, sl=1.1004) is None  # onceki sonuclanmadan ikincisi yok
    await w.fake.flush()
    patches = w.fake.calls("PATCH")
    assert len(patches) == 1 and patches[0][1].endswith("/orders/" + trade.sltp_order_id)
    assert patches[0][2] == {"stop_loss_price": "1.10030"}
    updated = w.repo.get_trade(trade.position_id)
    assert updated.sl == 1.1003 and updated.tp2 == 1.1092 and updated.user_sl_override is False
    assert w.repo.get_order(key)["state"] == "FILLED"
    assert await w.executor.modify(trade.position_id, sl=1.1004) is not None  # artik serbest


async def test_modify_creates_sltp_when_position_has_none(tmp_path):
    w = await make_world(tmp_path)
    position_id = await w.fake.external_open("EURUSD", "BUY", 0.10)
    trade = w.repo.get_trade(position_id)
    assert trade.origin == "manual" and trade.sl is None and trade.sltp_order_id is None
    await w.executor.modify(position_id, sl=1.0950, tp=1.1100)
    await w.fake.flush()
    created = [r for r in w.fake.calls("POST", "/orders")]
    assert created[0][2] == {"position_id": position_id, "type": "sltp", "stop_loss_price": "1.09500",
                             "take_profit_price": "1.11000"}
    trade = w.repo.get_trade(position_id)
    assert (trade.sl, trade.tp2, trade.initial_risk_r_price) == (1.095, 1.11, pytest.approx(0.0052))
    assert trade.sltp_order_id is not None


async def test_modify_rejection_sets_cooldown(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    w.fake.reject_next = (5005, "TRADING_RULE_INVALID_PRICE_LEVELS")
    await w.executor.modify(trade.position_id, sl=1.1001)
    await w.fake.flush()
    assert w.repo.get_trade(trade.position_id).sl == 1.0972
    assert await w.executor.modify(trade.position_id, sl=1.0990) is None  # bekleme suresi
    w.advance(61)
    assert await w.executor.modify(trade.position_id, sl=1.0990) is not None


async def test_partial_then_full_close_records_realized_pnl(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    await w.fake.set_price("EURUSD", 1.1062, 1.1064)
    await w.executor.close(trade.position_id, volume=0.05)
    await w.fake.flush()
    partial = w.repo.get_trade(trade.position_id)
    assert partial.is_open and partial.volume == pytest.approx(0.05)
    assert partial.pnl == pytest.approx((1.1062 - 1.1002) * 0.05 * 100000, abs=0.01)
    assert w.fake.calls("DELETE")[0][1].endswith(f"/positions/{trade.position_id}?volume=0.05")

    await w.executor.close(trade.position_id)
    await w.fake.flush()
    closed = w.repo.get_trade(trade.position_id)
    assert not closed.is_open and closed.close_price == 1.1062
    assert closed.pnl == pytest.approx((1.1062 - 1.1002) * 0.10 * 100000, abs=0.01)
    assert w.repo.bot_realized_pnl() == pytest.approx(closed.pnl)
    assert w.notifier.kinds().count("trade_closed") == 1


async def test_broker_side_stop_closes_trade(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    await w.fake.set_price("EURUSD", 1.0970, 1.0972)  # SL 1.0972
    trade = w.repo.closed_trades()[0]
    assert trade.close_price == 1.0972 and trade.pnl == pytest.approx(-30.0, abs=0.01)
    event = w.repo.events()[-1]
    assert event["kind"] == "trade_closed" and event["data"]["reason"] == "sl"
    assert w.repo.open_trades() == []


async def test_external_position_and_external_sl_change(tmp_path):
    w = await make_world(tmp_path)
    position_id = await w.fake.external_open("XAUUSD", "SELL", 0.02, sl=2010.0, tp=1980.0)
    trade = w.repo.get_trade(position_id)
    assert (trade.origin, trade.symbol, trade.side, trade.sl, trade.tp2) == ("manual", "XAUUSD", "SELL", 2010.0, 1980.0)
    assert trade.setup_id is None and trade.manage is False and trade.user_sl_override is False  # disaridan acildi
    assert trade.initial_risk_r_price == pytest.approx(10.0)

    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    bot_trade = w.repo.open_trades("bot")[0]
    await w.fake.external_set_sl(bot_trade.position_id, 1.0950)  # kullanici MT5'ten SL'i degistirdi
    changed = w.repo.get_trade(bot_trade.position_id)
    assert changed.sl == 1.095 and changed.user_sl_override is True


async def test_reconcile_imports_unknown_position_as_manual(tmp_path):
    w = await make_world(tmp_path)
    w.fake.drop_events = True
    position_id = await w.fake.external_open("XAUUSD", "BUY", 0.03, sl=1990.0)
    assert w.repo.open_trades() == []
    report = await reconcile(w.fake, w.repo, w.catalog, clock=lambda: w.clock["now"])
    assert report.imported == [position_id]
    trade = w.repo.get_trade(position_id)
    assert (trade.origin, trade.symbol, trade.volume, trade.sl) == ("manual", "XAUUSD", 0.03, 1990.0)
    assert trade.entry == 2000.20
    again = await reconcile(w.fake, w.repo, w.catalog, clock=lambda: w.clock["now"])
    assert again.imported == [] and len(w.repo.open_trades()) == 1


async def test_reconcile_closes_missing_with_deal_pnl(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    w.fake.drop_events = True  # bot kapaliyken stop calisti
    w.advance(600)
    await w.fake.set_price("EURUSD", 1.0970, 1.0972)
    assert w.repo.get_trade(trade.position_id).is_open

    report = await reconcile(w.fake, w.repo, w.catalog, clock=lambda: w.clock["now"])
    assert report.closed == [trade.position_id]
    closed = w.repo.get_trade(trade.position_id)
    assert not closed.is_open and closed.close_price == 1.0972
    assert closed.pnl == pytest.approx(-30.0, abs=0.01)
    assert closed.closed_at == w.clock["now"]
    assert w.repo.bot_realized_pnl() == pytest.approx(-30.0, abs=0.01)
    # Olay sonradan gelse bile ayni deal ikinci kez sayilmaz
    w.fake.drop_events = False
    again = await reconcile(w.fake, w.repo, w.catalog, clock=lambda: w.clock["now"])
    assert again.closed == [] and w.repo.bot_realized_pnl() == pytest.approx(-30.0, abs=0.01)


async def test_reconcile_syncs_volume_and_levels_and_flags_user_stop(tmp_path):
    w = await make_world(tmp_path)
    await w.executor.open(candidate(), "bot")
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    w.fake.drop_events = True
    await w.fake.external_set_sl(trade.position_id, 1.0960)
    await w.fake.set_price("EURUSD", 1.1030, 1.1032)
    await w.fake.delete(f"/v1/trading/accounts/123456/positions/{trade.position_id}?volume=0.04", "ext-close-1")
    await w.fake.flush()
    report = await reconcile(w.fake, w.repo, w.catalog, clock=lambda: w.clock["now"])
    synced = w.repo.get_trade(trade.position_id)
    assert report.updated == [trade.position_id]
    assert synced.volume == pytest.approx(0.06) and synced.sl == 1.096 and synced.user_sl_override is True
    assert synced.pnl == pytest.approx((1.1030 - 1.1002) * 0.04 * 100000, abs=0.01)


async def test_manual_open_uses_manual_origin_and_unique_keys(tmp_path):
    w = await make_world(tmp_path)
    first = await w.executor.open_manual("EURUSD", "SELL", 0.02, sl=1.1050, tp=1.0900)
    second = await w.executor.open_manual("EURUSD", "SELL", 0.02, sl=1.1050, tp=1.0900)
    await w.fake.flush()
    assert first != second and first.startswith("man-")
    trades = w.repo.open_trades("manual")
    assert len(trades) == 2 and trades[0].side == "SELL" and trades[0].tp2 == 1.09
    assert trades[0].setup_id is None and trades[0].initial_risk_r_price == pytest.approx(0.0050)
    assert w.repo.open_trades("bot") == []


async def test_event_without_request_id_is_matched_to_pending_open(tmp_path):
    w = await make_world(tmp_path)
    w.fake.auto_process = False
    key = await w.executor.open(candidate(), "bot")
    operation = w.fake._queue[0]
    operation["client_request_id"] = None  # olay istek kimligi olmadan gelsin
    w.repo.update_order_state(key, "UNKNOWN")
    w.repo.conn.execute("UPDATE orders SET operation_id = NULL WHERE idempotency_key = ?", (key,))
    await w.fake.flush()
    trade = w.repo.open_trades()[0]
    assert trade.origin == "bot" and trade.setup_id == "setup000000000000000001"
    assert w.repo.get_order(key)["state"] == "FILLED"
