import pytest

from tests.app_helpers import NOW, SATURDAY, build, feed_ticks, load_market, restart, started
from tradebot.exness.errors import ExnessAuthError
from tradebot.store.repo import Trade


def posts(app):
    return app.fake.calls("POST", "/positions")


async def open_one(app):
    summary = await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    return summary, trade


async def test_full_cycle_candidate_to_close(tmp_path):
    app = await started(tmp_path)
    summary, trade = await open_one(app)
    assert (summary.candidates, summary.opened) == (1, 1) and len(posts(app)) == 1
    assert trade.symbol == "XAUUSD" and trade.side == "BUY" and trade.sl < trade.entry
    risk = trade.initial_risk_r_price
    volume = trade.volume
    assert risk > 0 and volume >= 0.02
    # V9'un lot hesabi: zarar en fazla equity'nin %0.5'i
    assert risk * volume * 100 <= 10_000 * 0.005 + 1e-6

    # +1R: SL girise (+ maliyet) cekilir
    await app.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await app.bot.manage_tick()
    await app.fake.flush()
    moved = app.repo.get_trade(trade.position_id)
    assert moved.sl == pytest.approx(trade.entry + 0.01) and moved.be_done is True
    assert "sl_breakeven" in app.kinds() and "sl_breakeven" in app.notifier.kinds()

    # +2R: yarisi kapatilir, sonra SL fiyati izler
    await app.fake.set_price("XAUUSD", round(trade.entry + 2 * risk, 2), round(trade.entry + 2 * risk + 0.2, 2))
    await app.bot.manage_tick()
    await app.fake.flush()
    half = app.repo.get_trade(trade.position_id)
    assert half.volume == pytest.approx(volume - int(volume * 50 + 1e-9) / 100) and half.pnl > 0
    await app.bot.manage_tick()
    await app.fake.flush()
    trailed = app.repo.get_trade(trade.position_id)
    assert trailed.partial_done is True and trailed.sl > moved.sl

    # TP2 (3R): broker tarafindaki TP calisir
    await app.fake.set_price("XAUUSD", trade.tp2, trade.tp2 + 0.2)
    closed = app.repo.get_trade(trade.position_id)
    assert not closed.is_open and closed.close_price == trade.tp2
    assert app.repo.bot_realized_pnl() == pytest.approx(app.fake.balance - 10_000.0, abs=0.01)
    assert app.repo.bot_realized_pnl() > 0 and app.repo.open_trades() == []
    assert app.kinds().count("trade_opened") == 1 and app.kinds().count("trade_closed") == 1
    assert len(posts(app)) == 1


async def test_same_bar_scanned_twice_opens_once(tmp_path):
    app = await started(tmp_path)
    await open_one(app)
    await app.bot.on_bar_close()
    await app.fake.flush()
    assert len(posts(app)) == 1 and len(app.repo.open_trades()) == 1


async def test_restart_with_open_position_resumes_management(tmp_path):
    app = await started(tmp_path)
    _, trade = await open_one(app)

    again = restart(app)
    await again.bot.start()
    assert len(posts(again)) == 1  # yeniden baslatma emir gondermedi
    resumed = again.repo.open_trades("bot")
    assert [t.position_id for t in resumed] == [trade.position_id] and resumed[0].setup_id == trade.setup_id
    assert again.kinds().count("trade_opened") == 1  # mutabakat yeni islem uydurmadi

    risk = trade.initial_risk_r_price
    await again.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await again.bot.manage_tick()
    await again.fake.flush()
    assert again.repo.get_trade(trade.position_id).sl == pytest.approx(trade.entry + 0.01)
    await again.bot.on_bar_close()
    assert len(posts(again)) == 1  # ayni setup ikinci kez acilmadi


async def test_restart_after_stop_hit_while_down_closes_trade(tmp_path):
    app = await started(tmp_path)
    _, trade = await open_one(app)
    app.fake.event_listeners.clear()  # servis kapali: olaylar kimseye ulasmaz
    await app.fake.set_price("XAUUSD", trade.sl - 0.5, trade.sl - 0.3)
    again = restart(app)
    await again.bot.start()
    closed = again.repo.get_trade(trade.position_id)
    assert not closed.is_open and closed.close_price == trade.sl and closed.pnl < 0
    assert "trade_closed" in again.notifier.kinds()


async def test_weekend_scans_only_crypto(tmp_path):
    app = build(tmp_path, now=SATURDAY, dry_run=True)
    bid, ask = load_market(app.fake, "BTCUSD", SATURDAY)
    for symbol in ("EURUSD", "GBPUSD", "XAUUSD"):
        load_market(app.fake, symbol, SATURDAY)
    await app.bot.start()
    await feed_ticks(app, "BTCUSD", bid, ask, SATURDAY)
    summary = await app.bot.on_bar_close()
    assert summary.scanned == 1 and summary.closed == 3
    candle_symbols = {r[1].split("instrument=")[1].split("&")[0] for r in app.fake.calls("GET", "/candles")}
    assert candle_symbols == {"BTCUSD"}
    assert summary.candidates == 1  # kripto hafta sonu da degerlendirilir
    assert app.notifier.sent == []  # kapali semboller icin bildirim yok
    assert all(e["level"] == "info" for e in app.repo.events())
    assert posts(app) == []  # dry-run


async def test_no_entries_while_stream_down(tmp_path):
    app = await started(tmp_path)
    app.streams[0].go_down()
    summary = await app.bot.on_bar_close()
    assert summary.skipped == "stream_down" and posts(app) == []
    assert app.fake.calls("GET", "/candles") == []
    await app.bot.on_bar_close()
    assert app.kinds().count("scan_skipped") == 2 and app.notifier.sent == []

    app.streams[0].go_down(61)  # 60 sn'den uzun kopukluk: tek bildirim
    await app.bot.heartbeat()
    await app.bot.heartbeat()
    assert app.notifier.kinds() == ["connection_lost"]
    app.streams[0].come_up()
    await app.bot.heartbeat()
    assert "connection_restored" in app.kinds()
    summary = await app.bot.on_bar_close()
    assert summary.skipped is None and summary.opened == 1


async def test_halt_at_total_loss_blocks_entries_but_manages_open(tmp_path):
    app = await started(tmp_path)
    _, trade = await open_one(app)
    assert app.repo.bot_state().start_capital == 10_000.0
    # Botun baska bir isleminde baslangic sermayesinin %25'inden fazla kayip
    app.advance(60)  # kayip, bot basladiktan sonra gerceklesir
    app.repo.upsert_trade(Trade(position_id="9", origin="bot", symbol="EURUSD", side="BUY", volume=0.0,
                                entry=1.1, opened_at=NOW + 10, closed_at=NOW + 60))
    app.repo.add_realized("9", "deal-loss", NOW + 60, -2600.0)

    summary = await app.bot.on_bar_close()
    state = app.repo.bot_state()
    assert state.halted is True and "toplam" in state.halt_reason
    assert summary.skipped == "halted" and len(posts(app)) == 1
    assert app.notifier.kinds().count("bot_halted") == 1
    await app.bot.on_bar_close()
    await app.bot.heartbeat()
    assert app.notifier.kinds().count("bot_halted") == 1  # tekrar tekrar bildirilmez

    risk = trade.initial_risk_r_price
    await app.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await app.bot.manage_tick()
    await app.fake.flush()
    assert app.repo.get_trade(trade.position_id).sl == pytest.approx(trade.entry + 0.01)  # acik islem yonetiliyor


async def test_manual_loss_does_not_halt_bot(tmp_path):
    app = await started(tmp_path)
    app.repo.upsert_trade(Trade(position_id="9", origin="manual", symbol="EURUSD", side="BUY", volume=0.0,
                                entry=1.1, opened_at=NOW - 50, closed_at=NOW - 10))
    app.repo.add_realized("9", "deal-loss", NOW - 10, -5000.0)
    summary = await app.bot.on_bar_close()
    assert app.repo.bot_state().halted is False and summary.opened == 1


async def test_daily_loss_blocks_new_entries_for_the_day(tmp_path):
    app = await started(tmp_path)
    app.repo.upsert_trade(Trade(position_id="9", origin="bot", symbol="EURUSD", side="BUY", volume=0.0,
                                entry=1.1, opened_at=NOW - 50, closed_at=NOW - 10))
    app.repo.add_realized("9", "deal-loss", NOW - 10, -600.0)  # %6 > %5
    summary = await app.bot.on_bar_close()
    assert summary.opened == 0 and posts(app) == [] and app.repo.bot_state().halted is False
    assert app.notifier.kinds() == ["daily_limit"]
    await app.bot.on_bar_close()
    assert app.notifier.kinds() == ["daily_limit"]


async def test_dry_run_sends_no_orders(tmp_path):
    app = await started(tmp_path, dry_run=True)
    summary = await app.bot.on_bar_close()
    await app.fake.flush()
    assert summary.candidates == 1 and summary.opened == 0
    assert posts(app) == [] and app.repo.open_trades() == []
    signal = next(e for e in app.repo.events() if e["kind"] == "signal")
    assert signal["data"]["dry_run"] is True and signal["data"]["symbol"] == "XAUUSD"
    assert signal["data"]["side"] == "BUY" and signal["data"]["lots"] > 0
    assert app.notifier.sent == []


async def test_stopped_bot_scans_nothing_but_manages(tmp_path):
    app = await started(tmp_path)
    app.repo.set_bot_state(stopped=True)
    summary = await app.bot.on_bar_close()
    assert summary.skipped == "stopped" and posts(app) == []


async def test_non_candidates_do_not_notify(tmp_path):
    app = await started(tmp_path, balance=20.0)  # en kucuk lot risk sinirini asar
    for _ in range(3):
        summary = await app.bot.on_bar_close()
    assert summary.candidates == 0 and summary.reasons["NO_TRADE"] == 1  # diger sembollerde veri yok
    assert app.notifier.sent == [] and posts(app) == []
    assert set(app.kinds()) == {"bot_started", "scan"}


async def test_auth_error_stops_scan_with_single_notification(tmp_path):
    app = await started(tmp_path)
    app.fake.fail_next = ExnessAuthError("AUTH_INVALID_SIGNATURE", code=1001, status=401)
    summary = await app.bot.on_bar_close()
    assert summary.skipped == "auth_error" and posts(app) == []
    assert len(app.fake.calls("GET", "/candles")) == 1  # dongude tekrar denenmedi
    assert app.notifier.kinds() == ["auth_error"]
    event = app.repo.events()[-1]
    assert event["kind"] == "auth_error" and event["data"]["code"] == 1001


async def test_start_sets_capital_once_and_heartbeat_updates_state(tmp_path):
    app = await started(tmp_path)
    state = app.repo.bot_state()
    assert state.start_capital == 10_000.0 and state.start_at == NOW
    app.advance(30)
    await app.bot.heartbeat()
    assert app.repo.bot_state().heartbeat_at == NOW + 30
    assert app.repo.equity_series()[-1]["equity"] == 10_000.0
    again = restart(app)
    again.fake.balance = 12_345.0
    await again.bot.start()
    assert again.repo.bot_state().start_capital == 10_000.0  # yeniden baslatma sermayeyi sifirlamaz


async def test_status_snapshot(tmp_path):
    app = await started(tmp_path)
    _, trade = await open_one(app)
    await app.fake.set_price("XAUUSD", trade.entry + 1.0, trade.entry + 1.2)
    status = app.bot.status()
    assert status["balance"] == 10_000.0 and status["currency"] == "USD"
    assert status["open_bot"] == 1 and status["open_manual"] == 0
    assert status["pnl_today"]["bot"] == pytest.approx(1.0 * trade.volume * 100, abs=0.01)
    assert status["stream_connected"] is True and status["halted"] is False
