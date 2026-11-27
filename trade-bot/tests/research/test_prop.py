"""Prop sinavi benzetimi: kurallar elle kurulmus islemlerle."""
import numpy as np

from tradebot.research import prop as P

T0 = 1_704_196_800  # 2024-01-02 12:00 UTC (Sali)


def tr(entry_h, hours, r, worst=None, symbol="X", comm=0.0, w=1.0, path=None):
    close = np.array(path if path is not None else np.linspace(r / hours, r, hours))
    worst = np.array(worst if worst is not None else np.minimum(close, 0))
    return P.PTrade(symbol, T0 + entry_h * 3600, T0 + (entry_h + hours) * 3600, r, comm, w, worst, close)


def run(trades, risk=0.01, stop=None):
    trades = sorted(trades, key=lambda t: t.entry)
    return P.exam(trades, [t.entry for t in trades], T0, P.risk_fixed(risk), stop, T0 + 400 * 86400)


def test_phase_targets_pass_with_eight_then_five_percent():
    trades = [tr(i * 30, 5, 2.0, symbol=f"S{i % 3}") for i in range(12)]  # her biri +%2 (risk %1)
    out = run(trades)
    assert out["result"] == "pass" and out["phase"] == 3 and 0 < out["days1"] < out["days"]


def test_total_loss_is_static_ten_percent_and_daily_loss_uses_the_higher_of_balance_and_equity():
    losers = [tr(i * 30, 3, -1.0, symbol=f"S{i % 3}") for i in range(11)]
    assert run(losers)["result"] == "total"
    deep = [tr(1, 4, -0.5, worst=[-1.0, -2.0, -3.0, -4.0], path=[-0.5, -0.5, -0.5, -0.5], symbol=s) for s in ("A",)]
    assert run(deep, risk=0.01)["result"] == "daily"  # gun ici equity -%4'e degdi
    assert run(deep, risk=0.0075)["result"] != "daily"


def test_bot_stop_at_three_percent_avoids_the_daily_breach():
    deep = [tr(1, 4, -0.5, worst=[-1.0, -2.0, -3.0, -4.0], path=[-0.5] * 4)]
    out = run(deep, risk=0.01, stop=0.03)
    assert out["result"] != "daily"


def test_thirty_days_without_a_trade_is_a_violation_and_trading_day_rolls_at_17_ny():
    out = run([tr(0, 2, 1.0), tr(40 * 24, 2, 1.0)])
    assert out["result"] == "inactive"
    assert P.trading_day(T0 + 4 * 3600) == P.trading_day(T0)  # 16:00 UTC = 11:00 NY
    assert P.trading_day(T0 + 10 * 3600) == P.trading_day(T0) + 1  # 22:00 UTC = 17:00 NY


def test_funded_floating_limit_closes_all_and_lowers_the_share():
    trades = [tr(1, 6, -0.5, worst=[-1, -2, -3.4, -3.4, -2, -0.5], path=[-1, -2, -3, -3, -2, -0.5], symbol="A")]
    out = P.funded(trades, [t.entry for t in trades], T0, T0 + 40 * 86400, risk_pct=0.003)
    assert out["floating_breaches"] == 1 and out["final_share"] == 0.5
    good = [tr(i * 30, 5, 2.0, symbol=f"S{i % 3}") for i in range(30)]
    paid = P.funded(good, [t.entry for t in good], T0, T0 + 60 * 86400, risk_pct=0.003)
    assert paid["payout_per_year_pct"] > 0 and paid["floating_breaches"] == 0


def test_summary_counts_phases_and_reasons():
    res = [{"result": "pass", "phase": 3, "days": 10.0}, {"result": "daily", "phase": 1}, {"result": "total", "phase": 2}]
    s = P.summarize(res)
    assert s["phase1_pct"] == 66.7 and s["pass_pct"] == 33.3 and s["fail_reasons_pct"] == {"daily": 33.3, "total": 33.3}
