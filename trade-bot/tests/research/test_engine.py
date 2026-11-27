"""Faz 5 motoru: benzetim kurallari, pencereler, gecme karari ve monkey test (ag yok)."""
import numpy as np
import pytest

from tradebot.research import engine as E

T0 = E.add_months(1_700_000_000, 0)


def series(closes, *, tf="H1", spread_hi=0.0, highs=None, lows=None, opens=None):
    c = np.array(closes, float)
    n = len(c)
    return E.Series("X", tf, T0 + np.arange(n) * E.TF_SECONDS[tf], np.array(opens if opens is not None else c, float),
                    np.array(highs if highs is not None else c + spread_hi, float),
                    np.array(lows if lows is not None else c - spread_hi, float), c)


def spec(n, long_at=(), short_at=(), stop=1.0, **kw):
    lg, sh = np.zeros(n, bool), np.zeros(n, bool)
    lg[list(long_at)] = True
    sh[list(short_at)] = True
    return E.Spec(long=lg, short=sh, stop=np.full(n, stop), **kw)


def test_long_entry_pays_the_spread_and_stop_is_taken_before_target_in_the_same_bar():
    s = series([10, 10, 10, 10], highs=[10, 10, 13, 10], lows=[10, 10, 8.5, 10])
    trades, _ = E.simulate(s, spec(4, long_at=[1], target=np.full(4, 2.0)), E.Costs({}, 0.1))
    t = trades[0]
    assert t.reason == "stop" and t.r == pytest.approx((9.1 - 10.1) / 1.0)  # giris ask 10.1, stop 9.1
    assert t.entry_time == T0 + 2 * 3600 and t.exit_time == T0 + 3 * 3600


def test_gap_through_the_stop_exits_at_the_open_and_short_closes_at_the_ask():
    s = series([10, 10, 13.5, 13], opens=[10, 10, 13.5, 13], highs=[10, 10, 14, 13], lows=[10, 10, 13, 13])
    trades, _ = E.simulate(s, spec(4, short_at=[1], stop=3.0), E.Costs({}, 0.2))
    t = trades[0]
    assert t.reason == "stop" and t.r == pytest.approx(-(13.7 - 10.0) / 3.0)  # acilis 13.5 + spread 0.2 > stop 13


def test_cost_gate_signal_exit_trailing_and_time_exit():
    s = series([10, 10, 11, 12, 11.5, 11, 10])
    blocked, stats = E.simulate(s, spec(7, long_at=[1], stop=0.5), E.Costs({}, 0.1))
    assert blocked == [] and stats["cost_blocked"] == 1  # 0.1 / 0.5 = %20 > %15
    ex = np.zeros(7, bool)
    ex[4] = True
    t = E.simulate(s, spec(7, long_at=[1], stop=5.0, exit_long=ex), E.Costs({}, 0.0))[0][0]
    assert t.reason == "signal" and t.r == pytest.approx(1.5 / 5.0)
    t = E.simulate(s, spec(7, long_at=[1], stop=5.0, trail=np.full(7, 0.6)), E.Costs({}, 0.0))[0][0]
    # iz suren stop 12 - 0.6 = 11.4; sonraki mum 11'den ACILIR (stopun altinda): cikis acilistan
    assert t.reason == "stop" and t.r == pytest.approx((11 - 10) / 5.0)
    t = E.simulate(s, spec(7, long_at=[1], stop=5.0, max_bars=2), E.Costs({}, 0.0))[0][0]
    assert t.reason == "time" and t.exit_time == T0 + 4 * 3600


def test_one_position_at_a_time_and_open_trade_at_the_end_is_not_counted():
    s = series([10, 10, 10, 10, 10, 10])
    trades, stats = E.simulate(s, spec(6, long_at=[1, 2, 3], stop=5.0), E.Costs({}, 0.0))
    assert len(trades) == 1 and trades[0].r is None and stats["open_at_end"] == 1
    assert E.metrics(trades)["trades"] == 0


def test_metrics_compound_the_balance_and_measure_drawdown():
    trades = [E.Trade(i, i + 1, 1, r) for i, r in enumerate([2.0, -1.0, -1.0, 3.0])]
    m = E.metrics(trades)
    assert m["trades"] == 4 and m["net_r"] == 3.0 and m["pf"] == 2.5
    assert m["max_dd_pct"] == pytest.approx((1 - 0.995 ** 2) * 100, abs=0.01)
    assert E.metrics([E.Trade(0, 1, 1, 1.0, weight=0.5)])["net_r"] == 0.5


def test_timeline_holdout_is_the_last_twelve_months_and_windows_slide_six_months():
    end = E.add_months(T0, 72)
    plan = E.timeline(end + 5 * 86400)
    assert plan["holdout"] == (E.add_months(end, -12), end) and plan["region"] == (E.add_months(end, -60), E.add_months(end, -12))
    w = plan["windows"]
    assert len(w) == 4 and w[0]["select"][0] == plan["region"][0] and w[3]["test"][1] == plan["holdout"][0]
    assert w[1]["select"][0] == E.add_months(plan["region"][0], 6) and w[0]["test"][0] == w[0]["select"][1]


def _trades_in(span, rs, side=1):
    step = (span[1] - span[0]) // (len(rs) + 1)
    return [E.Trade(span[0] + (i + 1) * step, span[0] + (i + 1) * step + 10, side, r) for i, r in enumerate(rs)]


def test_walk_forward_counts_a_test_window_only_after_selection_and_applies_the_pass_rule():
    plan = E.timeline(E.add_months(T0, 72))
    region = plan["region"]
    months = [(E.add_months(region[0], m), E.add_months(region[0], m + 1)) for m in range(48)]
    # Ilk 20 ay kaybettiren, sonrasi kazandiran bir eslesme: pencere 0 secilmez, sonrakiler secilir.
    trades = []
    for m, span in enumerate(months):
        trades += _trades_in(span, [-1.0, -1.0, 0.5] if m < 20 else [2.0, -1.0, 1.0])
    wf = E.walk_forward(trades, plan, region[0])
    rows = wf["windows"]
    assert [r["selected"] for r in rows] == [E.selected(r["select"]) for r in rows]
    assert rows[0]["selected"] is False and rows[3]["selected"] is True
    counted = [r for r in rows if r["selected"]]
    assert wf["counted"] == len(counted) and wf["oos"]["trades"] == sum(r["test"]["trades"] for r in counted)
    assert wf["passed"] is (len(counted) >= 2 and wf["oos"]["trades"] >= 40 and wf["oos"]["pf"] >= 1.15)
    late = E.walk_forward(trades, plan, plan["windows"][3]["select"][0])
    assert [r["usable"] for r in late["windows"]] == [False, False, False, True] and late["passed"] is False


def test_session_filter_and_daily_trend_filter_use_only_closed_daily_bars():
    assert E.in_session(int(T0 + 9 * 3600), "crypto")
    winter = 1_704_189_600  # 2024-01-02 10:00 UTC (Sali)
    assert E.in_session(winter, "forex") and not E.in_session(winter - 9 * 3600, "forex")
    assert E.in_session(winter + 5 * 3600, "index") and not E.in_session(winter, "index")
    n = 260
    d = E.Series("X", "D1", T0 + np.arange(n) * 86400, *(np.linspace(1, 2, n),) * 4)
    h = E.Series("X", "H1", np.array([T0 + 259 * 86400 + 3600]), *(np.array([2.0]),) * 4)
    assert E.daily_index(h, d)[0] == 258  # gun 259 henuz kapanmadi
    f = E.filters(h, d, "forex", None)
    assert f["F1"][0][0] and not f["F1"][1][0] and f["F3"] is not None and f["F4"][0][0]


def test_monkey_keeps_count_and_side_mix_and_reports_a_pass_rate():
    rng = np.random.default_rng(3)
    n = 24 * 30 * 66
    closes = 100 + np.cumsum(rng.normal(0, 0.1, n))
    s = series(closes, spread_hi=0.05)
    plan = E.timeline(int(s.time[-1]))
    entries = [(int(i), 1 if k % 3 else -1) for k, i in enumerate(range(1000, n - 10, 300))]
    sp = spec(n, stop=0.5, max_bars=24)
    out = E.monkey(s, sp, E.Costs({}, 0.01), entries, plan, int(s.time[0]), reps=20, seed=5)
    assert out["reps"] == 20 and 0.0 <= out["pass_rate"] <= 1.0 and 0.5 < out["pf_median"] < 2.0


def test_a_window_touching_a_missing_month_is_not_used():
    plan = E.timeline(E.add_months(T0, 72))
    gap = E.add_months(plan["windows"][3]["test"][0], 1)
    wf = E.walk_forward([], plan, plan["region"][0], gaps=[gap])
    assert [r["usable"] for r in wf["windows"]] == [True, True, True, False]
