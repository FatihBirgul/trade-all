"""Swing ailesi (SMC, H1 EMA geri cekilme): kurallar yalnizca kapanmis mumlarla ve onceden sabit esiklerle calisir."""
import pytest

from tradebot.signals.modules.base import Context
from tradebot.signals.modules.indicators import atr, pivots, rsi
from tradebot.signals.modules.strategies import swing_rules
from tradebot.signals.modules.strategies.ema_pullback_h1 import EmaPullbackH1
from tradebot.signals.modules.strategies.smc_sweep import SmcSweep, find_setup, trigger

M15, H1, H4, D1 = 900, 3600, 14400, 86400
END = 2_000 * H1  # son H1 mumunun kapandigi an (saat basi)


def bar(time, opened, high, low, close):
    return {"time": time, "open": opened, "high": high, "low": low, "close": close}


def rising(count, step, last_close, seconds, end, spread=0.5):
    """`end` aninda kapanan, duzenli yukselen `count` mum; her mumun araligi `spread`."""
    out = []
    for i in range(count):
        close = last_close - (count - 1 - i) * step
        out.append(bar(end - (count - i) * seconds, close - step, close + spread / 2, close - step - spread / 2, close))
    return out


def falling(count, step, last_close, seconds, end, spread=0.5):
    return [bar(b["time"], -b["open"] + 2 * last_close, -b["low"] + 2 * last_close, -b["high"] + 2 * last_close,
                -b["close"] + 2 * last_close) for b in rising(count, step, last_close, seconds, end, spread)]


def test_rsi_and_pivots():
    assert rsi([1.0] * 20) == 50.0 and rsi(list(range(1, 30))) == 100.0 and rsi([1, 2]) is None
    assert rsi([float(v) for v in range(30, 1, -1)]) == pytest.approx(0.0)
    bars = [bar(i, 0, h, low, 0) for i, (h, low) in enumerate([(1, 0), (2, 1), (5, 2), (2, 1), (1, -3), (2, 0), (3, 1)])]
    assert pivots(bars) == ([2], [4])
    assert pivots(bars[:6]) == ([2], [])  # son iki mum donus noktasi sayilmaz: sagi henuz kapanmadi


def test_daily_bias_needs_d1_and_h4_to_agree():
    up_d1, up_h4 = rising(80, 0.26, 100.5, D1, END), rising(80, 0.05, 100.5, H4, END)
    assert swing_rules.daily_bias(up_d1, up_h4) == "bullish"
    assert swing_rules.daily_bias(falling(80, 0.26, 100.5, D1, END), falling(80, 0.05, 100.5, H4, END)) == "bearish"
    assert swing_rules.daily_bias(up_d1, falling(80, 0.05, 100.5, H4, END)) is None  # H4 ters
    assert swing_rules.daily_bias(up_d1[:40], up_h4) is None  # yeterli gunluk mum yok


def test_stop_is_structure_or_one_and_a_half_daily_atr_whichever_is_further():
    d1 = rising(80, 0.26, 100.5, D1, END, spread=1.0)
    daily = atr(d1)
    assert swing_rules.stop_price("BUY", 100.0, 99.9, d1) == pytest.approx(100.0 - 1.5 * daily)  # yapi cok yakin
    assert swing_rules.stop_price("BUY", 100.0, 90.0, d1) == 90.0  # yapi daha uzak
    assert swing_rules.stop_price("SELL", 100.0, 100.1, d1) == pytest.approx(100.0 + 1.5 * daily)
    assert swing_rules.stop_price("BUY", 100.0, 99.0, d1[:5]) is None  # gunluk ATR yok: islem yok


def test_room_to_the_nearest_opposing_daily_swing_must_be_at_least_one_r():
    d1 = rising(80, 0.26, 100.5, D1, END)
    assert swing_rules.room_ok("BUY", 100.5, 99.0, d1)  # karsi donus noktasi yok
    capped = [dict(b) for b in d1]
    capped[-10]["high"] = 101.5  # yakin bir gunluk tepe (1 birim yukarida)
    assert not swing_rules.room_ok("BUY", 100.5, 99.0, capped)  # risk 1.5 > yer 1.0
    assert swing_rules.room_ok("BUY", 100.5, 99.8, capped)  # risk 0.7 < yer 1.0


def swing_context(m15, h1, d1=None, h4=None):
    bars = {"M15": m15, "H1": h1, "H4": h4 or rising(80, 0.05, 100.5, H4, END),
            "D1": d1 or rising(80, 0.26, 100.5, D1, END, spread=1.0)}
    return Context(symbol="EURUSD", now=END + 5, bars=bars)


def pullback_h1():
    """Zikzakla yukselen H1 serisi (RSI ~60); son mum EMA20/21'e inip ustunde, yukselen mum olarak kapaniyor."""
    h1, close = [], 96.4
    for i in range(80):
        opened = close
        close += 0.25 if i % 2 == 0 else -0.15
        h1.append(bar(END - (80 - i) * H1, opened, max(opened, close) + 0.05, min(opened, close) - 0.05, close))
    top = h1[-3]["close"]
    h1[-2] = bar(h1[-2]["time"], top, top + 0.05, top - 0.45, top - 0.4)  # geri cekilme
    h1[-1] = bar(h1[-1]["time"], top - 0.4, top + 0.02, top - 0.9, top)  # EMA'ya igne, guclu kapanis
    return h1


def last_quarter(close=None):
    close = pullback_h1()[-1]["close"] if close is None else close
    return [bar(END - 2 * M15, close, close, close, close), bar(END - M15, close, close, close, close)]


def test_ema_pullback_h1_buys_the_rejection_with_a_daily_atr_stop():
    h1, d1 = pullback_h1(), rising(80, 0.26, 100.5, D1, END, spread=1.0)
    signal = EmaPullbackH1("20_21").evaluate(swing_context(last_quarter(), h1, d1))
    assert signal is not None and signal.side == "BUY" and signal.entry == h1[-1]["close"]
    assert signal.bar_time == END - M15
    # Ayni mum genis bant surumunde de gecerli (dip EMA21'in altina indi, bant kirilmadi).
    assert EmaPullbackH1("21_50").evaluate(swing_context(last_quarter(), h1, d1)) is not None
    # Bandin ICINDE kapanan ret mumu: dar bant surumu saymaz (kapanis EMA'larin ustunde degil), genis bant sayar.
    inside = [dict(b) for b in h1]
    inside[-1] = bar(h1[-1]["time"], 99.5, 99.8, 99.4, 99.75)
    assert EmaPullbackH1("20_21").evaluate(swing_context(last_quarter(99.75), inside, d1)) is None
    wide = EmaPullbackH1("21_50").evaluate(swing_context(last_quarter(99.75), inside, d1))
    assert wide is not None and wide.side == "BUY"
    # Bant asagi kirildiysa (dip EMA50'nin cok altinda) genis bant surumu de saymaz.
    broken = [dict(b) for b in h1]
    broken[-1] = bar(h1[-1]["time"], 99.5, 99.8, 98.5, 99.75)
    assert EmaPullbackH1("21_50").evaluate(swing_context(last_quarter(99.75), broken, d1)) is None
    assert signal.entry - signal.stop >= 1.5 * atr(d1) - 1e-9  # stop en az 1,5 x gunluk ATR uzakta
    assert signal.target == pytest.approx(signal.entry + 2 * (signal.entry - signal.stop))


def test_ema_pullback_h1_skips_without_h1_close_bias_or_rejection():
    h1 = pullback_h1()
    strategy = EmaPullbackH1("20_21")
    assert strategy.evaluate(swing_context(last_quarter(), h1)) is not None
    early = [bar(END - 3 * M15, 100.4, 100.4, 100.4, 100.4), bar(END - 2 * M15, 100.4, 100.4, 100.4, 100.4)]
    assert strategy.evaluate(swing_context(early, h1)) is None  # H1 mumu henuz kapanmadi
    down = falling(80, 0.26, 100.5, D1, END, spread=1.0)
    assert strategy.evaluate(swing_context(last_quarter(), h1, d1=down, h4=falling(80, 0.05, 100.5, H4, END))) is None
    weak = [dict(b) for b in h1]
    weak[-1] = bar(h1[-1]["time"], h1[-1]["close"], h1[-1]["high"], h1[-1]["low"], h1[-1]["open"])  # dusen mum: ret yok
    assert strategy.evaluate(swing_context(last_quarter(), weak)) is None
    with pytest.raises(ValueError):
        EmaPullbackH1("9_13")


def smc_h1():
    """Duz bir bant, bir donus dibi (99.0) ve tepesi (101.0); sonra supurme, displacement, kirilim ve geri donus."""
    h1 = [bar(END - (70 - i) * H1, 100.0, 100.3, 99.7, 100.0) for i in range(60)]
    h1[40] = bar(h1[40]["time"], 100.0, 100.3, 99.0, 100.0)  # donus dibi
    h1[50] = bar(h1[50]["time"], 100.0, 101.0, 99.7, 100.0)  # donus tepesi
    tail = [
        (99.6, 99.7, 98.7, 99.4),     # 60: supurme (99.0'in altina igne, ustunde kapanis)
        (99.5, 99.6, 99.2, 99.3),     # 61: son dusen mum = Order Block
        (99.3, 101.5, 99.3, 101.4),   # 62: displacement + 101.0 ustunde kapanis (yapi kirilimi)
        (101.4, 101.8, 101.0, 101.6), # 63: FVG = [99.6, 101.0]
        (101.6, 101.7, 101.0, 101.1),
        (101.1, 101.2, 100.6, 100.7),
        (100.7, 100.8, 100.3, 100.4),
        (100.4, 100.6, 100.1, 100.3),
        (100.3, 100.5, 100.0, 100.4),
        (100.4, 100.6, 100.0, 100.5),
    ]
    for i, (o, h, low, c) in enumerate(tail):
        h1.append(bar(END - (10 - i) * H1, o, h, low, c))
    return h1


def smc_m15():
    return [bar(END - 3 * M15, 100.5, 100.5, 100.4, 100.4), bar(END - 2 * M15, 100.4, 100.45, 100.15, 100.2),
            bar(END - M15, 100.15, 100.55, 100.0, 100.5)]  # yutan mum, POI'ye degiyor


def test_smc_setup_is_found_and_bought_on_the_trigger_candle():
    h1 = smc_h1()
    setup = find_setup(h1)
    assert setup is not None and setup["sweep_low"] == 98.7
    assert setup["poi_low"] == 99.2 and setup["poi_high"] == pytest.approx(100.3)  # Order Block + FVG'nin alt yarisi
    d1 = rising(80, 0.26, 100.5, D1, END, spread=1.0)
    signal = SmcSweep().evaluate(swing_context(smc_m15(), h1, d1))
    assert signal is not None and signal.side == "BUY" and signal.entry == 100.5
    assert signal.stop <= 98.7 and signal.entry - signal.stop >= 1.5 * atr(d1) - 1e-9


def test_smc_needs_every_piece():
    h1, m15 = smc_h1(), smc_m15()
    no_sweep = [dict(b) for b in h1]
    no_sweep[60] = bar(h1[60]["time"], 99.6, 99.7, 99.1, 99.4)  # igne donus dibinin altina inmedi
    assert find_setup(no_sweep) is None
    no_gap = [dict(b) for b in h1]
    no_gap[63] = bar(h1[63]["time"], 101.4, 101.8, 99.5, 101.6)  # FVG kapandi
    assert find_setup(no_gap) is None
    broken = [dict(b) for b in h1]
    broken[-2] = bar(h1[-2]["time"], 100.3, 100.5, 98.0, 98.5)  # supurulen dibin altinda kapanis: kurulum bozuldu
    assert find_setup(broken) is None
    assert not trigger([m15[0], m15[1], bar(m15[2]["time"], 100.5, 100.55, 100.0, 100.15)], 99.2, 100.3)  # dusen mum
    assert not trigger([m15[0], m15[1], bar(m15[2]["time"], 100.6, 101.0, 100.5, 100.9)], 99.2, 100.3)  # POI'ye degmedi
    down_d1, down_h4 = falling(80, 0.26, 100.5, D1, END, spread=1.0), falling(80, 0.05, 100.5, H4, END)
    assert SmcSweep().evaluate(swing_context(m15, h1, down_d1, down_h4)) is None  # gunluk yon ters


def test_smc_sell_is_the_mirror_image():
    flip = lambda bars: [bar(b["time"], 200 - b["open"], 200 - b["low"], 200 - b["high"], 200 - b["close"]) for b in bars]  # noqa: E731
    down_d1, down_h4 = falling(80, 0.26, 99.5, D1, END, spread=1.0), falling(80, 0.05, 99.5, H4, END)
    signal = SmcSweep().evaluate(swing_context(flip(smc_m15()), flip(smc_h1()), down_d1, down_h4))
    assert signal is not None and signal.side == "SELL" and signal.entry == 99.5
    assert signal.stop >= 101.3 and signal.stop - signal.entry >= 1.5 * atr(down_d1) - 1e-9
