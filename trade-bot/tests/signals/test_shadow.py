from types import SimpleNamespace

import pytest

from tests.app_helpers import NOW, started
from tests.execution.helpers import candidate
from tradebot.config import BotSettings, strategy_mode
from tradebot.signals.adapter import evaluate_all
from tradebot.signals.shadow import MAX_BARS, ShadowBook
from tradebot.store.repo import Repo

M15 = 900


def book(tmp_path):
    return ShadowBook(Repo(tmp_path / "bot.db"))


def bar(n, low, high, close=None, start=NOW):
    return {"time": start + n * M15, "open": low, "high": high, "low": low, "close": close if close is not None else high}


def test_modes_default_live_and_off_excluded():
    assert strategy_mode(BotSettings(), "fx_trend_momentum_v6") == "live"
    listed = BotSettings(enabled_strategies={"fx_trend_momentum_v6"})
    assert strategy_mode(listed, "fx_trend_momentum_v6") == "live"
    assert strategy_mode(listed, "fx_range_reversion_v6") == "off"  # eski alan: listede olmayan kapali
    modes = BotSettings(strategy_modes={"fx_range_reversion_v6": "shadow", "fx_failed_breakout_v6": "off"})
    assert strategy_mode(modes, "fx_range_reversion_v6") == "shadow"
    assert strategy_mode(modes, "fx_failed_breakout_v6") == "off"
    assert strategy_mode(modes, "fx_confirmed_breakout_v6") == "live"
    with pytest.raises(Exception):
        BotSettings(strategy_modes={"fx_trend_momentum_v6": "turbo"})


def fake_report(decision, routed, confirmed, *, side="BUY"):
    candidate_fields = dict(entry_zone={"low": 2000.2}, stop_loss=1999.0, take_profit_1=2002.6, take_profit_2=2003.8,
                            lot_size=0.1, net_risk_reward=2.0, risk_amount=12.0, analysis_id="a" * 64)
    empty = dict(entry_zone=None, stop_loss=None, take_profit_1=None, take_profit_2=None, lot_size=None,
                 net_risk_reward=None, risk_amount=None, analysis_id="b" * 64)
    ok = decision.endswith("_CANDIDATE")
    return SimpleNamespace(
        final_decision=decision, trading_eligibility="ELIGIBLE" if ok else "BLOCKED",
        decision_reasons=["ok" if ok else "cost-adjusted reward/risk below minimum"],
        routing={"status": "selected", "strategy_id": routed},
        strategies=[{"strategy_id": s, "status": "CONFIRMED", "direction": side, "setup_id": "setup-" + s[:12]}
                    for s in confirmed],
        **(candidate_fields if ok else empty))


class Engine:
    """Ilk yonlendirilen strateji kapidan gecemiyor; ikincisi tek basina degerlendirilince geciyor."""

    def __init__(self):
        self.calls = []

    def analyze(self, provider, symbol, timeframe, **kwargs):
        enabled = kwargs["enabled_strategies"]
        self.calls.append(list(enabled))
        both = ["fx_trend_momentum_v6", "fx_confirmed_breakout_v6"]
        if "fx_trend_momentum_v6" in enabled:
            return fake_report("NO_TRADE", "fx_trend_momentum_v6", both)
        if enabled == ["fx_confirmed_breakout_v6"]:
            return fake_report("BUY_CANDIDATE", "fx_confirmed_breakout_v6", ["fx_confirmed_breakout_v6"])
        return fake_report("WAIT", None, [])


def run_all(engine, modes=None):
    return evaluate_all(None, "XAUUSD", equity=10_000.0, risk_pct=0.5, commission_per_lot=0.0,
                        modes=modes or {}, now=NOW, engine=engine)


def test_second_confirmed_strategy_tried_when_first_fails_gate():
    engine = Engine()
    results = run_all(engine)
    assert [r.candidate.strategy_id for r in results if r.candidate] == ["fx_confirmed_breakout_v6"]
    assert results[0].mode == "live"
    assert len(engine.calls) == 2 and engine.calls[1] == ["fx_confirmed_breakout_v6"]


def test_off_strategy_is_never_evaluated_and_shadow_mode_is_carried():
    engine = Engine()
    assert [r.candidate for r in run_all(engine, {"fx_confirmed_breakout_v6": "off"}) if r.candidate] == []
    assert all("fx_confirmed_breakout_v6" not in call for call in engine.calls)
    shadowed = run_all(Engine(), {"fx_confirmed_breakout_v6": "shadow"})
    assert [r.mode for r in shadowed if r.candidate] == ["shadow"]
    everything_off = run_all(Engine(), {s: "off" for s in ("fx_trend_momentum_v6", "fx_range_reversion_v6",
                                                           "fx_confirmed_breakout_v6", "fx_failed_breakout_v6")})
    assert everything_off[0].candidate is None and everything_off[0].reasons == ("etkin strateji yok",)


def test_shadow_setup_recorded_once(tmp_path):
    shadow = book(tmp_path)
    cand = candidate()
    assert shadow.open(cand, "shadow", 72.0, NOW) is True
    assert shadow.open(cand, "shadow", 72.0, NOW) is False
    assert shadow.open_symbols() == {"EURUSD"}


def test_shadow_tp_gives_positive_r(tmp_path):
    shadow = book(tmp_path)
    shadow.open(candidate(), "shadow", None, NOW)  # giris 1.1002, SL 1.0972, TP1 1.1062 (2R)
    assert shadow.resolve("EURUSD", [bar(-1, 1.0900, 1.1200)], NOW + M15) == []  # acilistan onceki mum sayilmaz
    closed = shadow.resolve("EURUSD", [bar(0, 1.0990, 1.1010), bar(1, 1.1000, 1.1070)], NOW + 2 * M15)
    assert len(closed) == 1 and closed[0]["result_r"] == pytest.approx(2.0)
    assert shadow.open_symbols() == set()


def test_shadow_stop_first_on_ambiguous_bar(tmp_path):
    shadow = book(tmp_path)
    shadow.open(candidate(), "shadow", None, NOW)
    closed = shadow.resolve("EURUSD", [bar(0, 1.0960, 1.1080)], NOW + M15)  # ayni mumda hem SL hem TP
    assert closed[0]["result_r"] == pytest.approx(-1.0)


def test_shadow_sell_side(tmp_path):
    shadow = book(tmp_path)
    sell = candidate(side="SELL", entry=1.1000, sl=1.1030, tp1=1.0940, tp2=1.0910)
    shadow.open(sell, "low_score", 35.0, NOW)
    assert shadow.resolve("EURUSD", [bar(0, 1.0950, 1.1010)], NOW + M15) == []
    assert shadow.resolve("EURUSD", [bar(0, 1.0950, 1.1010), bar(1, 1.0930, 1.0990)], NOW + 2 * M15)[0]["result_r"] == pytest.approx(2.0)


def test_shadow_expires_after_96_bars_at_market(tmp_path):
    shadow = book(tmp_path)
    shadow.open(candidate(), "shadow", None, NOW)
    quiet = [bar(n, 1.0990, 1.1020, close=1.1017) for n in range(MAX_BARS - 1)]
    assert shadow.resolve("EURUSD", quiet, NOW + (MAX_BARS - 1) * M15) == []
    quiet.append(bar(MAX_BARS - 1, 1.0990, 1.1020, close=1.1017))
    closed = shadow.resolve("EURUSD", quiet, NOW + MAX_BARS * M15)
    assert closed[0]["result_r"] == pytest.approx((1.1017 - 1.1002) / 0.0030)


def test_shadow_stats(tmp_path):
    shadow = book(tmp_path)
    for n, (low, high) in enumerate([(1.1000, 1.1070), (1.0960, 1.1010), (1.1000, 1.1070)]):
        shadow.open(candidate(setup=f"setup{n:021d}"), "shadow", None, NOW + n)
        shadow.resolve("EURUSD", [bar(1, low, high)], NOW + 2 * M15)
    stats = shadow.stats("fx_trend_momentum_v6")
    assert stats == {"trades": 3, "wins": 2, "win_rate": pytest.approx(2 / 3), "avg_r": pytest.approx(1.0)}
    assert shadow.stats("yok") == {"trades": 0, "wins": 0, "win_rate": None, "avg_r": None}
    assert shadow.stats("fx_trend_momentum_v6", reason="low_score")["trades"] == 0


async def test_shadow_strategy_never_sends_order(tmp_path):
    app = await started(tmp_path)
    app.repo.set_bot_settings(BotSettings(dry_run=False, strategy_modes={"fx_trend_momentum_v6": "shadow"}))
    summary = await app.bot.on_bar_close()
    assert summary.candidates == 1 and summary.shadowed == 1 and summary.opened == 0
    assert app.fake.calls("POST", "/positions") == [] and app.notifier.sent == []
    assert app.bot.shadow.open_symbols() == {"XAUUSD"}
    await app.bot.on_bar_close()  # ayni mum: ikinci kez kaydedilmez
    assert app.bot.shadow.stats("fx_trend_momentum_v6")["trades"] == 0  # henuz sonuclanmadi
    rows = app.repo.conn.execute("SELECT reason, strategy_id FROM shadow_trades").fetchall()
    assert [tuple(r) for r in rows] == [("shadow", "fx_trend_momentum_v6")]


async def test_low_score_candidate_is_tracked_as_shadow(tmp_path):
    from tradebot.config import FusionSettings
    app = await started(tmp_path)
    app.repo.set_bot_settings(BotSettings(dry_run=False, fusion=FusionSettings(min_score=100, mid_score=100, high_score=100)))
    await app.bot.on_bar_close()
    rows = app.repo.conn.execute("SELECT reason, score FROM shadow_trades").fetchall()
    assert len(rows) == 1 and rows[0][0] == "low_score" and rows[0][1] >= 80


async def test_off_strategy_produces_no_candidate(tmp_path):
    app = await started(tmp_path)
    app.repo.set_bot_settings(BotSettings(dry_run=False, strategy_modes={"fx_trend_momentum_v6": "off"}))
    summary = await app.bot.on_bar_close()
    assert summary.candidates == 0 and summary.opened == 0 and summary.shadowed == 0
