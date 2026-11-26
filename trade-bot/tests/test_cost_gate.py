"""Maliyet kapisi (kullanici karari 2026-11-26): giristeki spread stop mesafesinin %15'inden buyukse islem yok.

Ortak sahte piyasada spread stop mesafesinin ~%17'sidir: varsayilan ayarla (%15) aday elenir, %25 ile gecer."""
import httpx
import pytest

from tests.api.test_manual_preview import client
from tests.app_helpers import feed_ticks, started
from tradebot import forward
from tradebot.config import BotSettings, RiskSettings


def with_limit(app, percent, **extra):
    app.repo.set_bot_settings(BotSettings(risk=RiskSettings(max_spread_stop_pct=percent), **extra))


async def test_default_is_fifteen_percent_and_the_range_is_five_to_twenty_five():
    assert RiskSettings().max_spread_stop_pct == 15
    for bad in (4.9, 25.1):
        with pytest.raises(ValueError):
            RiskSettings(max_spread_stop_pct=bad)
    assert RiskSettings(max_spread_stop_pct=5).max_spread_stop_pct == 5


async def test_live_candidate_above_the_limit_is_not_sent_and_is_counted_per_strategy(tmp_path):
    app = await started(tmp_path)
    with_limit(app, 15, dry_run=False)
    before = len(app.fake.requests)
    summary = await app.bot.on_bar_close()
    assert summary.candidates >= 1 and summary.opened == 0 and summary.cost_blocked >= 1
    assert summary.cost_reasons.get("fx_trend_momentum_v6") == 1
    assert not [r for r in app.fake.requests[before:] if r[0] == "POST"]  # hicbir emir gitmedi
    assert app.repo.orders_in(("PENDING", "ACKED", "UNKNOWN", "FILLED")) == []
    public = app.bot.scan_summary()
    assert public["cost_blocked"] == summary.cost_blocked and public["max_spread_stop_pct"] == 15
    assert public["cost_by_strategy"]["fx_trend_momentum_v6"] == 1


async def test_same_candidate_passes_when_the_limit_is_wider_and_fails_again_when_the_spread_widens(tmp_path):
    app = await started(tmp_path)  # ortak kurulum: sinir %25
    summary = await app.bot.on_bar_close()
    assert summary.opened == 1 and summary.cost_blocked == 0
    other = await started(tmp_path / "genis")
    quote = other.bot.quotes.quote("XAUUSD")
    await feed_ticks(other, "XAUUSD", quote["bid"], quote["bid"] + 3 * quote["spread"], other.clock["now"], count=5)
    wide = await other.bot.on_bar_close()
    assert wide.opened == 0  # spread uc katina cikti: %25 siniri da asildi (ya da V9 kendi spread kapisinda eledi)


async def test_shadow_records_follow_the_same_gate(tmp_path):
    """Golge karnesi de ayni kuralla olusur: kapiya takilan aday sanal isleme donusmez."""
    app = await started(tmp_path)
    with_limit(app, 15, dry_run=False, strategy_modes={"fx_trend_momentum_v6": "shadow"})
    summary = await app.bot.on_bar_close()
    assert summary.shadowed == 0 and summary.cost_blocked >= 1
    assert app.repo.conn.execute("SELECT COUNT(*) FROM shadow_trades").fetchone()[0] == 0
    with_limit(app, 25, dry_run=False, strategy_modes={"fx_trend_momentum_v6": "shadow"})
    app.clock["now"] += 900
    again = await started(tmp_path / "ikinci")
    with_limit(again, 25, dry_run=False, strategy_modes={"fx_trend_momentum_v6": "shadow"})
    assert (await again.bot.on_bar_close()).shadowed >= 1


async def test_setting_can_be_changed_from_the_app_within_its_range(tmp_path):
    app = await started(tmp_path)
    async with client(app) as http:
        current = (await http.get("/settings")).json()
        assert current["risk"]["max_spread_stop_pct"] == 25  # ortak test kurulumu
        current["risk"]["max_spread_stop_pct"] = 10
        saved = await http.put("/settings", json=current)
        assert saved.status_code == 200 and app.repo.get_bot_settings().risk.max_spread_stop_pct == 10
        current["risk"]["max_spread_stop_pct"] = 40
        assert (await http.put("/settings", json=current)).status_code == 422
    assert isinstance(httpx.__version__, str)


def row(at, r, spread_r, strategy="tb_smc_day_v13", blocked=None):
    return {"strategy_id": strategy, "symbol": "X", "side": "BUY", "at": at, "spread_r": spread_r,
            "stop_daily_atr": 0.5, "cost_blocked": spread_r > 0.15 if blocked is None else blocked,
            "results": {forward.PLAN_KEY: [r, at + 3600.0, None]}, "kind": "forex", "model": "m", "score": 70,
            "volume_ratio": 1.0, "stretch": None, "weekend": False, "exit": "TP"}


def test_forward_test_totals_exclude_blocked_trades_and_report_what_the_gate_removed():
    split = 100 * 86400.0
    rows = [row(1 * 86400.0, 2.0, 0.05), row(2 * 86400.0, -1.0, 0.30), row(3 * 86400.0, -1.0, 0.20),
            row(4 * 86400.0, 1.0, 0.10)]
    summary = forward.summarize_swing(rows, split)["planned"]["tb_smc_day_v13"]
    assert summary["raw"]["all"]["trades"] == 2 and summary["raw"]["all"]["sum_r"] == 3.0  # yalnizca acilanlar
    gate = summary["cost_gate"]
    assert (gate["signals"], gate["blocked"], gate["blocked_pct"]) == (4, 2, 50.0)
    assert gate["would_have"]["sum_r"] == -2.0 and gate["would_have"]["trades"] == 2
    v9 = forward.summarize_v9([
        {"strategy_id": "fx_a", "symbol": "X", "side": "BUY", "at": 1.0, "r": 1.0, "closed_at": 2.0, "open_r": None,
         "wide_r": None, "wide_closed_at": None, "wide_open_r": None, "wide_open": False, "spread_r": 0.1,
         "cost_blocked": False},
        {"strategy_id": "fx_a", "symbol": "X", "side": "BUY", "at": 3.0, "r": -1.0, "closed_at": 4.0, "open_r": None,
         "wide_r": None, "wide_closed_at": None, "wide_open_r": None, "wide_open": False, "spread_r": 0.4,
         "cost_blocked": True}], 10.0)
    assert v9["fx_a"]["base"]["all"]["sum_r"] == 1.0 and v9["fx_a"]["cost_gate"]["blocked"] == 1
    assert v9["all"]["cost_gate"]["would_have"]["sum_r"] == -1.0


def test_blocked_signal_does_not_keep_the_strategy_busy():
    """Kapiya takilan islem acilmadigi icin ayni stratejinin sonraki sinyali alinabilir."""
    from tests.signals.market_gen import T0, market
    from tradebot import backtest
    history = backtest.History()
    for tf, bars in market(1, 230).items():
        history.add("X", tf, bars)
    start, end = T0 + 200 * 86400, T0 + 230 * 86400
    ids = ("tb_ema_pullback_v1",)
    tight = forward.Spreads({"X": {"hours": {}, "all": 0.05}})  # dar stoplu M15 stratejisinde spread/stop yuksek
    free = [t for t in forward.swing_trades("X", "forex", history, tight, start, end) if t["strategy_id"] in ids]
    gated = [t for t in forward.swing_trades("X", "forex", history, tight, start, end, 0.15) if t["strategy_id"] in ids]
    blocked = [t for t in gated if t["cost_blocked"]]
    assert blocked and all(t["spread_r"] > 0.15 for t in blocked)
    assert all(t["spread_r"] <= 0.15 for t in gated if not t["cost_blocked"])
    assert len(gated) > len(free)  # engellenen islemler stratejiyi mesgul etmedigi icin daha cok sinyal goruldu
    assert not any(t.get("cost_blocked") for t in free)
