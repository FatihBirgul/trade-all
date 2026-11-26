"""Faz 5 stratejilerinin kural testleri: elle kurulmus, sonucu bilinen fiyat serileri."""
import numpy as np
import pytest

from tradebot.research import engine as E
from tradebot.research import indicators as ind
from tradebot.research import strategies as S

T0 = 1_704_067_200  # 2024-01-01


def daily(closes, spread=0.5):
    c = np.array(closes, float)
    return E.Series("X", "D1", T0 + np.arange(len(c)) * 86400, c.copy(), c + spread, c - spread, c)


def v_shape(n_down=150, n_up=150):
    return np.concatenate([np.linspace(200, 100, n_down), np.linspace(100, 220, n_up)])


def test_turtle_enters_on_a_close_beyond_the_prior_channel_and_exits_on_the_short_channel():
    closes = [100.0] * 30 + [106.0, 107.0, 108.0] + [100.0] * 3
    s = daily(closes)
    spec = S.turtle(20, 10)(s, {})
    assert np.flatnonzero(spec.long).tolist()[0] == 30 and not spec.long[:30].any()
    assert spec.stop[30] == pytest.approx(2 * ind.atr(s.high, s.low, s.close, 20)[30])
    assert not spec.exit_long[33]  # 100 >= onceki 10 gunun dibi (99.5): cikis yok
    or_not = S.turtle(20, 10)(daily([100.0] * 30 + [106.0] + [90.0]), {})
    assert or_not.exit_long[31]


def test_ma_cross_signals_once_at_the_crossing_bar():
    s = daily(v_shape(250, 250))
    spec = S.ma_cross(s, {})
    fast, slow = ind.sma(s.close, 50), ind.sma(s.close, 200)
    ups = np.flatnonzero(spec.long)
    assert len(ups) == 1 and fast[ups[0]] > slow[ups[0]] and fast[ups[0] - 1] <= slow[ups[0] - 1]
    assert not spec.short.any() or np.flatnonzero(spec.short)[0] < ups[0]


def test_faber_is_long_above_and_short_below_the_200_day_average():
    s = daily(v_shape(250, 250))
    spec = S.faber(s, {})
    m = ind.sma(s.close, 200)
    i = 480
    assert s.close[i] > m[i] and spec.long[i] and spec.exit_short[i] and not spec.short[i]


def test_tsmom_rebalances_on_the_first_daily_bar_of_a_month_by_the_252_day_sign():
    s = daily(np.linspace(100, 200, 400))
    spec = S.tsmom(s, {})
    hits = np.flatnonzero(spec.long)
    assert len(hits) > 0 and all(i >= 252 for i in hits)
    for i in hits:
        day = np.datetime64(int(s.time[i]), "s").astype(object)
        assert day.day == 1  # 2024: her ayin 1'i bir D1 mumu
    assert not spec.short.any()


def test_clenow_needs_the_ema_filter_and_a_new_50_day_closing_high():
    s = daily(v_shape(200, 200))
    spec = S.clenow(s, {})
    first = np.flatnonzero(spec.long)[0]
    assert first > 200 and s.close[first] > s.close[first - 50:first].max()
    assert spec.trail is not None and spec.trail[first] == pytest.approx(spec.stop[first])


@pytest.mark.parametrize("build", [S.supertrend, S.adx_dmi, S.parabolic, S.ichimoku, S.macd_zero])
def test_trend_rules_go_long_in_the_rise_and_not_in_the_fall(build):
    rng = np.random.default_rng(1)
    closes = v_shape(200, 200) + rng.normal(0, 0.3, 400)
    s = daily(closes, spread=1.0)
    spec = build(s, {})
    longs = np.flatnonzero(spec.long)
    assert len(longs) > 0 and longs.min() >= 150  # dususun ortasinda (ilk 150 mum) alis yok
    assert np.all(spec.stop[longs] > 0)


def test_supertrend_and_psar_flip_signals_are_events_with_exit_on_the_opposite_flip():
    s = daily(v_shape(200, 200), spread=1.0)
    for build in (S.supertrend, S.parabolic):
        spec = build(s, {})
        assert not (spec.long & spec.short).any()
        ups = np.flatnonzero(spec.long)
        assert len(ups) <= 3 and np.array_equal(spec.exit_short, spec.long)


def test_existing_strategy_adapters_run_and_give_positive_stops():
    rng = np.random.default_rng(7)
    n_h1 = 24 * 400
    closes = 1.1 + np.cumsum(rng.normal(0, 0.0008, n_h1))
    h1 = E.Series("EURUSD", "H1", T0 + np.arange(n_h1) * 3600, closes.copy(), closes + 0.0006, closes - 0.0006, closes)
    from tradebot.research.data import aggregate
    rows = [{"time": int(h1.time[i]), "open": h1.open[i], "high": h1.high[i], "low": h1.low[i], "close": h1.close[i]}
            for i in range(n_h1)]

    def to_series(tf, size):
        bars = aggregate(rows, size)
        return E.Series("EURUSD", tf, np.array([b["time"] for b in bars]), *(np.array([b[k] for b in bars])
                                                                              for k in ("open", "high", "low", "close")))
    ctx = {"H1": h1, "H4": to_series("H4", 14400), "D1": to_series("D1", 86400)}
    week = S.week_trade(ctx["H4"], ctx)
    marks = np.flatnonzero(week.long | week.short)
    assert np.all(week.stop[marks] > 0) and week.exit_fn is not None
    trades, _ = E.simulate(ctx["H4"], week, E.Costs({}, 0.00001))
    assert all(t.reason in ("stop", "time", "open") for t in trades)
    ema = S.ema_h1(21, 50)(ctx["H1"], ctx)
    marks = np.flatnonzero(ema.long | ema.short)
    assert np.all(ema.stop[marks] > 0) and np.allclose(ema.target[marks], 2 * ema.stop[marks])


def test_registry_ids_are_unique_and_every_strategy_states_a_source():
    ids = [s.id for s in S.STRATEGIES]
    assert len(ids) == len(set(ids)) and all(s.source and s.tf in E.TF_SECONDS for s in S.STRATEGIES)


def test_rsi2_buys_a_short_dip_above_the_200_day_average_and_exits_above_sma5():
    closes = list(np.linspace(100, 150, 230)) + [146.0, 141.0] + [150.0]
    s = daily(closes)
    spec = S.rsi2(s, {})
    assert spec.long[231] and not spec.long[:229].any() and spec.exit_long[232]


def test_double7_buys_the_seven_day_closing_low_in_an_uptrend():
    closes = list(np.linspace(100, 150, 230)) + [149.0, 148.0, 147.0]
    spec = S.double7(daily(closes), {})
    assert spec.long[232] and not spec.short.any()


def test_ibs_and_three_down_are_long_only_index_rules():
    s = E.Series("US500", "D1", T0 + np.arange(4) * 86400, np.array([10.0, 10, 10, 10]), np.array([11.0, 11, 11, 11]),
                 np.array([9.0, 9, 9, 9]), np.array([9.1, 10.9, 10, 10]))
    spec = S.ibs(s, {})
    assert spec.long[0] and not spec.long[1] and spec.exit_long[1] and spec.max_bars == 1
    closes = list(np.linspace(100, 150, 230)) + [149.0, 148.0, 147.0, 148.5]
    spec = S.three_down(daily(closes), {})
    assert spec.long[232] and not spec.long[231] and spec.exit_long[233]
    assert S.BY_ID["C21_ibs"].kinds == ("index",) and S.BY_ID["C23_three_down"].kinds == ("index",)


def test_turtle_soup_needs_an_old_low_a_break_and_a_close_back_above():
    lows = [100.0] * 5 + [95.0] + [100.0] * 15 + [94.0]
    closes = [101.0] * 21 + [96.0]
    s = E.Series("X", "D1", T0 + np.arange(22) * 86400, np.array(closes), np.array([102.0] * 22), np.array(lows),
                 np.array(closes))
    spec = S.turtle_soup(s, {})
    assert spec.long[21] and spec.stop[21] > 96.0 - 94.0
    fresh = lows[:]
    fresh[18] = 95.0  # dip yalnizca 3 gun once: kurulum yok
    fresh[5] = 100.0
    s2 = E.Series("X", "D1", s.time, s.open, s.high, np.array(fresh), s.close)
    assert not S.turtle_soup(s2, {}).long[21]


def test_holy_grail_and_bollinger_reversion_follow_the_trend_direction():
    rng = np.random.default_rng(4)
    up = np.linspace(100, 200, 300) + rng.normal(0, 0.8, 300)
    s = daily(up, spread=1.5)
    hg = S.holy_grail(s, {})
    assert not hg.short.any() and np.all(hg.stop[np.flatnonzero(hg.long)] > 0)
    br = S.bollinger_revert(s, {})
    assert not br.short[220:].any()
