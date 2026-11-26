"""Yeniden baslatmadan sonra 30 dk yeni giris yok (kullanici karari, 2026-11-26): analiz ve yonetim surer."""
import inspect

from tests.app_helpers import feed_ticks, load_market, restart, started
from tests.test_scan_summary import public_get
from tradebot import runtime
from tradebot.app import RESTART_ENTRY_PAUSE, RESTART_PAUSE_REASON, Bot

M15 = 900


def posts(app):
    return app.fake.calls("POST", "/positions")


async def restarted(app, pause=RESTART_ENTRY_PAUSE):
    again = restart(app, restart_pause=pause)
    await again.bot.start()
    return again


async def next_bar(app):
    app.advance(M15)
    bid, ask = load_market(app.fake, "XAUUSD", app.clock["now"])
    await feed_ticks(app, "XAUUSD", bid, ask, app.clock["now"])
    return await app.bot.on_bar_close()


def test_production_default_is_thirty_minutes():
    assert RESTART_ENTRY_PAUSE == 1800.0
    assert inspect.signature(Bot.__init__).parameters["restart_pause"].default == RESTART_ENTRY_PAUSE
    assert "restart_pause" not in inspect.getsource(runtime.build_runtime)


async def test_no_order_for_thirty_minutes_after_a_restart_then_entries_resume(tmp_path):
    app = await started(tmp_path)  # piyasa aday uretiyor; henuz tarama yapilmadi
    again = await restarted(app)
    assert again.bot.entry_paused()
    first = await next_bar(again)  # +15 dk
    assert (first.candidates, first.opened, first.blocked) == (1, 0, 1)
    assert first.blocked_reasons == {RESTART_PAUSE_REASON: 1} and posts(again) == []
    again.advance(M15 - 1)  # 30 dakikanin dolmasina 1 sn kala hala kapali
    assert again.bot.entry_paused()
    again.advance(1 - M15)
    second = await next_bar(again)  # +30 dk: sure doldu
    await again.fake.flush()
    assert not again.bot.entry_paused()
    assert second.opened == 1 and len(posts(again)) == 1


async def test_open_trade_is_managed_and_manual_orders_work_during_the_pause(tmp_path):
    app = await started(tmp_path)
    await app.bot.on_bar_close()
    await app.fake.flush()
    trade = app.repo.open_trades("bot")[0]
    again = await restarted(app)
    risk = trade.initial_risk_r_price
    await again.fake.set_price("XAUUSD", round(trade.entry + risk, 2), round(trade.entry + risk + 0.2, 2))
    await again.bot.manage_tick()
    await again.fake.flush()
    assert again.bot.entry_paused()
    assert again.repo.get_trade(trade.position_id).sl >= trade.entry  # stop basa basa cekildi
    await again.bot.executor.open_manual("XAUUSD", "BUY", 0.01, sl=round(trade.entry - risk, 2), tp=None)
    assert len(posts(again)) == 2  # elle islem bekleme suresine takilmaz


async def test_dry_run_counts_the_pause_like_live_and_health_shows_it(tmp_path):
    app = await started(tmp_path, dry_run=True)
    again = await restarted(app)
    summary = await next_bar(again)
    assert (summary.would_open, summary.blocked) == (0, 1)  # deneme modu canlidaki davranisi gosterir
    assert (await public_get(again, "/health")).json()["entries_paused"] is True
    body = (await public_get(again, "/health/summary")).json()
    assert body["portfolio_reasons"] == {RESTART_PAUSE_REASON: 1} and body["would_open"] == 0
    started_event = [e for e in again.repo.events(newest=True, limit=50) if e["kind"] == "bot_started"][0]
    assert "İlk 30 dakika yeni işlem açılmaz" in started_event["message"]
    assert (await next_bar(again)).would_open == 1
    assert (await public_get(again, "/health")).json()["entries_paused"] is False
