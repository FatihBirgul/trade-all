"""Eski masanin kodundan tasinan stratejiler (v13 SMC / EMA geri cekilme, WEEK TRADE) ve cikis planlari."""
import json
import math
from pathlib import Path

import pytest

from tests.signals.market_gen import DURATIONS, T0, closed, context_bars, market
from tradebot.signals import outcome
from tradebot.signals.modules import modules
from tradebot.signals.modules.base import Context
from tradebot.signals.modules.strategies import v13, week_trade
from tradebot.signals.modules.strategies.v13 import V13, Frame

GOLDEN = json.loads((Path(__file__).parent / "v13_golden.json").read_text())
NEW_IDS = ("tb_smc_day_v13", "tb_emapb_day_v13", "tb_smc_week_v13", "tb_emapb_week_v13", "tb_week_trade_v1")


def bar(time, o, h, low, c, volume=100):
    return {"time": time, "open": o, "high": h, "low": low, "close": c, "tick_volume": volume}


def test_port_gives_exactly_the_candidates_of_the_original_code():
    """Referans dosyasi, kullanicinin ozgun `smc.py`si (pandas) ayni sentetik veriyle calistirilarak uretildi:
    her karar aninda GECEN adaylar (yon, model, puan, stop, hedefler). Tasinan kod hepsinde ayni sonucu vermeli;
    referansta aday olmayan anlarda da aday uretmemeli."""
    expected = {(row["seed"], row["tf"], row["end"], row["family"]): row["candidates"] for row in GOLDEN["rows"]}
    checked, seen = 0, set()
    for seed in range(GOLDEN["seeds"]):
        frames = market(seed, GOLDEN["days"])
        for tf in ("H1", "H4"):
            bars_all = frames[tf]
            for end in range(len(bars_all) - GOLDEN["count"][tf], len(bars_all) + 1):
                bars = bars_all[max(0, end - (256 if tf == "H1" else 120)):end]
                now = bars[-1]["time"] + DURATIONS[tf]
                h4, d1 = closed(frames, "H4", now, 120), closed(frames, "D1", now, 120)
                frame = Frame(bars)
                upper = frame if tf == "H4" else Frame(h4)
                checked += 1
                for family in ("smc", "ema"):
                    got = sorted(([c["side"], c["model"][0], c["score"], round(c["plan"]["sl"], 6),
                                   None if c["plan"]["tp1"] is None else round(c["plan"]["tp1"], 6),
                                   None if c["plan"]["tp2"] is None else round(c["plan"]["tp2"], 6)]
                                  for c in v13.candidates(frame, Frame(d1), upper, d1, tf, family)), key=str)
                    want = expected.get((seed, tf, end, family), [])
                    assert len(got) == len(want), (seed, tf, end, family)
                    for mine, theirs in zip(got, want):
                        assert mine[:3] == theirs[:3], (seed, tf, end, family)
                        assert all((a is None and b is None) or a == pytest.approx(b, abs=2e-6)
                                   for a, b in zip(mine[3:], theirs[3:])), (seed, tf, end, family)
                    if want:
                        seen.add((seed, tf, end, family))
    assert checked == GOLDEN["checked"] and len(seen) == len(expected) >= 40
    assert {key[3] for key in seen} == {"smc", "ema"} and {key[1] for key in seen} == {"H1", "H4"}


def test_indicator_columns_follow_the_source_definitions():
    bars = [bar(i * 3600, 10 + i, 11 + i, 9 + i, 10.5 + i) for i in range(30)]
    frame = Frame(bars)
    assert frame.e20[0] == 10.5 and frame.e20[1] == pytest.approx(10.5 + 2 / 21)  # ewm(adjust=False): ilk deger tohum
    assert frame.tr[0] == 2.0 and frame.atr[0] == 2.0 and frame.atr[1] == pytest.approx(2.0)
    assert math.isnan(frame.ab[18]) and frame.ab[19] == pytest.approx(0.5)  # 20 mum dolmadan ortalama yok
    assert math.isnan(frame.rsi[0]) and frame.rsi[-1] == 100.0  # hep yukselen seri
    flat = Frame([bar(i * 3600, 10, 10, 10, 10) for i in range(30)])
    assert math.isnan(flat.rsi[-1])
    highs, lows = v13.swings(Frame([bar(i, 1, h, 0, 1) for i, h in enumerate([1, 2, 3, 5, 3, 2, 1, 1, 5, 1, 1, 1])]))
    assert highs == [3, 8] and lows  # esit degerler de donus noktasi sayilir (kaynaktaki gibi); son 3 mum sayilmaz


def test_rejection_candles():
    def frame(previous, last):
        return Frame([bar(0, *previous), bar(3600, *last)])
    assert v13.rejection(frame((10, 10.2, 9.4, 9.5), (9.5, 10.3, 9.4, 10.2)), "L") == "boga engulfing"
    assert v13.rejection(frame((10, 10.1, 9.9, 10.05), (10.0, 10.1, 9.0, 10.05)), "L") == "pinbar (alt fitil)"
    assert v13.rejection(frame((10, 10.1, 9.9, 10.05), (9.8, 10.3, 9.4, 10.25)), "L") == "boga ret mumu"
    assert v13.rejection(frame((10, 10.1, 9.9, 10.05), (10.0, 10.3, 9.9, 10.1)), "L") is None
    assert v13.rejection(frame((10, 10.6, 9.8, 10.5), (10.5, 10.6, 9.7, 9.8)), "S") == "ayi engulfing"
    assert v13.rejection(frame((10, 10.1, 9.9, 9.95), (10.0, 11.0, 9.9, 9.95)), "S") == "pinbar (ust fitil)"


def test_session_levels_use_istanbul_hours_and_only_closed_days():
    # 30 saatlik H1: UTC gun basindan baslar. Asya 03-11 TSI = 00-08 UTC, Londra 10-19 TSI = 07-16 UTC.
    bars = [bar(T0 + i * 3600, 100, 100.5, 99.5, 100) for i in range(30)]
    bars[2] = bar(bars[2]["time"], 100, 103.0, 99.5, 100)  # Asya tepesi (02 UTC)
    bars[9] = bar(bars[9]["time"], 100, 100.5, 96.0, 100)  # Londra dibi (09 UTC)
    frame = Frame(bars)
    daily = [bar(T0 - 86400, 100, 110, 90, 100), bar(T0, 100, 120, 80, 100)]  # ikincisi karar aninda KAPANMAMIS
    ph, pl = v13.levels(frame, daily, [], [], 12)  # 12 UTC = 15 TSI
    assert (103.0, "Asya H") in ph and (110.0, "PDH") in ph and (90.0, "PDL") in pl
    assert not any(name.startswith("Londra") for _, name in ph + pl)  # Londra seviyesi ancak 19 TSI'den sonra
    assert (120.0, "PDH") not in ph  # olusmakta olan gunun tepesi kullanilmaz
    ph, pl = v13.levels(frame, daily, [], [], 17)  # 17 UTC = 20 TSI
    assert (96.0, "Londra L") in pl
    ph, pl = v13.levels(frame, daily, [], [], 26)  # ertesi gun 02 UTC: onceki gun artik kapandi
    assert (120.0, "PDH") in ph and (96.0, "Londra L") not in pl


def signals(frames, start_day, end_day, ids=NEW_IDS):
    chosen = [m for m in modules("strategy") if m.id in ids]
    out = []
    for index, m15 in enumerate(frames["M15"]):
        now = m15["time"] + 900
        if now < T0 + start_day * 86400 or now >= T0 + end_day * 86400 or now % 3600:
            continue
        context = Context(symbol="X", now=now + 5, bars=context_bars(frames, now))
        for module in chosen:
            signal = module.evaluate(context)
            if signal is not None:
                out.append((module.id, now, signal, context))
    return out


@pytest.fixture(scope="module")
def run():
    frames = market(1, 240)
    return frames, signals(frames, 200, 240)


def test_every_signal_keeps_the_source_rules(run):
    frames, found = run
    assert {name for name, *_ in found} == set(NEW_IDS)  # bes strateji de sinyal uretiyor
    for name, now, signal, context in found:
        sign = 1.0 if signal.side == "BUY" else -1.0
        risk = (signal.entry - signal.stop) * sign
        assert risk > 0 and signal.bar_time == now - 900 and signal.entry == context.bars["M15"][-1]["close"]
        plan = signal.plan
        if name.endswith("day_v13"):
            assert now % 3600 == 0 and plan["type"] == "DAY"
            assert (plan["tp1"] - signal.entry) * sign / risk >= 1.5 - 1e-9  # R/R < 1,5 ise islem yok
            assert (plan["tp2"] - signal.entry) * sign / risk >= 2.5 - 1e-9
            assert (plan["tp2"] - plan["tp1"]) * sign >= 0.5 * risk - 1e-9
        else:
            assert now % 14400 == 0 and plan["tp1"] is None  # WEEK: yalnizca 4H kapanisinda, hedef yok
        if name.endswith("_v13"):
            assert plan["score"] >= (65 if plan["model"].startswith("1") else 60)
            frame = Frame(context.bars["H1" if "day" in name else "H4"])
            assert v13.rejection(frame, "L" if signal.side == "BUY" else "S")  # son kapanmis mumda ret mumu sart
        if name == "tb_week_trade_v1":
            upper = Frame(context.bars["H4"])
            # Gunluk veri "bir onceki takvim gunu"dur: yon sinyal mumunun, stop giris mumunun gunune gore.
            before_signal = week_trade.daily_state(week_trade.days_before(context.bars["D1"], now - 14400))
            before_entry = week_trade.daily_state(week_trade.days_before(context.bars["D1"], now))
            assert risk == pytest.approx(2.0 * before_entry["atr"])  # stop 2 x gunluk ATR (basit ortalama)
            assert before_signal["bias"] == (1 if signal.side == "BUY" else -1)
            assert (upper.C[-1] > upper.e20[-1] > upper.e50[-1]) == (signal.side == "BUY")
            body, span = abs(upper.C[-1] - upper.O[-1]), upper.H[-1] - upper.L[-1]
            assert body > 0.5 * span and span <= 2.0 * week_trade.simple_atr(upper)[-1]
            assert (upper.rsi[-1] > 50) == (signal.side == "BUY") and plan["atr4"] == week_trade.simple_atr(upper)[-1]


def test_buy_and_sell_are_exact_mirror_images(run):
    frames, found = run
    mirrored = signals(market(1, 240, flip=True), 200, 240)
    normal = sorted((name, now, s.side, round(s.stop, 6)) for name, now, s, _ in found)
    flipped = sorted((name, now, {"BUY": "SELL", "SELL": "BUY"}[s.side], round(200 - s.stop, 6))
                     for name, now, s, _ in mirrored)
    assert normal == flipped and {side for _, _, side, _ in normal} == {"BUY", "SELL"}


def test_signals_do_not_change_when_the_future_is_cut_off(run):
    frames, found = run
    cut = T0 + 222 * 86400 + 5 * 3600
    past = {tf: [b for b in bars if b["time"] + DURATIONS[tf] <= cut] for tf, bars in frames.items()}
    again = signals(past, 200, 240)
    key = lambda item: (item[0], item[1], item[2].side, item[2].stop, item[2].plan["model"])  # noqa: E731
    assert [key(i) for i in again] == [key(i) for i in found if i[1] <= cut] and len(again) > 20


def test_modules_wait_for_their_own_candle_and_fresh_data(run):
    frames, found = run
    name, now, signal, context = next(item for item in found if item[0] == "tb_emapb_day_v13")
    module = V13("ema", "H1")
    assert module.evaluate(context) is not None
    early = dict(context.bars, M15=closed(frames, "M15", now - 900, 4))  # saat basindan onceki M15 mumu
    assert module.evaluate(Context(symbol="X", now=now - 895, bars=early)) is None
    stale = dict(context.bars, H1=context.bars["H1"][:-1])  # son H1 mumu onbellekte yok: veri guncel degil
    assert module.evaluate(Context(symbol="X", now=now + 5, bars=stale)) is None
    assert module.evaluate(Context(symbol="X", now=now + 5, bars=dict(context.bars, D1=[]))) is None
    with pytest.raises(ValueError):
        V13("ema", "M15")


# ---------------------------------------------------------------- cikis planlari
def flat(start, count, price=100.0):
    return [bar(start + i * 900, price, price + 0.05, price - 0.05, price) for i in range(count)]


def test_day_plan_takes_half_at_target_one_then_breakeven_and_target_two():
    at = 1000 * 900
    rise = [bar(at + 900, 100, 101.6, 99.9, 101.5), bar(at + 1800, 101.5, 101.6, 99.9, 100.0)]
    result = outcome.simulate_plan("BUY", 100.0, 99.0, 101.5, 102.5, at + 5, rise)
    assert result["first"] == "TP1" and result["r"] == pytest.approx(0.5 * 1.5 + 0.5 * 0.625, abs=1e-3)  # %60 ilerleme kilidi
    two = [bar(at + 900, 100, 102.6, 99.9, 102.5)]
    assert outcome.simulate_plan("BUY", 100.0, 99.0, 101.5, 102.5, at + 5, two)["r"] == pytest.approx(0.75 + 1.25)
    stopped = [bar(at + 900, 100, 100.2, 98.9, 99.0)]
    assert outcome.simulate_plan("BUY", 100.0, 99.0, 101.5, 102.5, at + 5, stopped)["r"] == -1.0
    # %40 ilerleme (1R) goruldu, Hedef 1 gorulmedi: stop girise cekilir.
    back = [bar(at + 900, 100, 101.05, 99.9, 101.0), bar(at + 1800, 101.0, 101.0, 99.5, 99.6)]
    assert outcome.simulate_plan("BUY", 100.0, 99.0, 101.5, 102.5, at + 5, back)["r"] == 0.0
    # 5 gun (480 mum) dolunca kapanis fiyatindan cikilir.
    slow = flat(at + 900, 600, 100.3)
    timed = outcome.simulate_plan("BUY", 100.0, 99.0, 101.5, 102.5, at + 5, slow)
    assert timed["first"] == "TIME" and timed["r"] == pytest.approx(0.3) and timed["bars"] == 480
    assert outcome.simulate_plan("BUY", 100.0, 99.0, 99.5, 102.5, at + 5, slow) is None  # hedef girisin gerisinde


def state_of(atr=0.5, low=None, high=None):
    return lambda moment: {"atr": atr, "low": low, "high": high}


def test_week_trade_trail_breakeven_lock_then_two_atr_behind_the_best_price():
    at = 14400 * 100
    week = dict(lock=(2.0, 1.0), trail_atr=2.0, timeout=7 * 86400.0)
    up = [bar(at + 900, 100, 101.1, 99.9, 101.0), bar(at + 1800, 101.0, 101.0, 99.9, 100.0)]
    assert outcome.simulate_trail("BUY", 100.0, 99.0, at + 5, up, state_of(), **week)["r"] == 0.0  # +1R -> girise
    two = [bar(at + 900, 100, 102.1, 99.9, 102.0), bar(at + 1800, 102.0, 102.0, 100.5, 100.6)]
    assert outcome.simulate_trail("BUY", 100.0, 99.0, at + 5, two, state_of(), **week)["r"] == 1.0  # +2R -> +1R kilit
    # 4H kapanisinda iz: en iyi (5R) - 2 x 4H ATR (1,0) = 4R; bir sonraki mumda oradan cikilir.
    bars = [bar(at + i * 900, 104.9, 105.0, 104.8, 104.9) for i in range(1, 17)] + [bar(at + 17 * 900, 104.9, 104.9, 103.0, 103.5)]
    trailed = outcome.simulate_trail("BUY", 100.0, 99.0, at + 5, bars, state_of(), **week)
    assert trailed["first"] == "TRAIL" and trailed["r"] == pytest.approx(4.0)
    # 7 gunde +1R gorulmediyse mum kapanisinda cikilir.
    quiet = flat(at + 900, 800, 100.2)
    timed = outcome.simulate_trail("BUY", 100.0, 99.0, at + 5, quiet, state_of(), **week)
    assert timed["first"] == "TIME" and timed["r"] == pytest.approx(0.2) and timed["closed_at"] - at >= 7 * 86400
    # SAT ask'tan kapanir: spread stopu yaklastirir.
    sell = [bar(at + 900, 100, 100.95, 99.9, 100.0)]
    assert outcome.simulate_trail("SELL", 100.0, 101.0, at + 5, sell, state_of(), spread_at=lambda m: 0.1)["r"] == -1.0
    assert outcome.simulate_trail("SELL", 100.0, 101.0, at + 5, sell, state_of())["r"] is None


def test_structure_trail_follows_only_swings_confirmed_after_the_entry():
    at = 14400 * 100
    bars = [bar(at + i * 900, 103.0, 103.1, 102.9, 103.0) for i in range(1, 17)] + [bar(at + 17 * 900, 103.0, 103.0, 99.9, 100.2)]
    old = outcome.simulate_trail("BUY", 100.0, 99.0, at + 5, bars, state_of(low=(at - 14400, 102.5)), structure=True)
    assert old["r"] == 0.0  # giristen ONCEKI donus noktasi stopu tasimaz; yalnizca +1R -> girise
    new = outcome.simulate_trail("BUY", 100.0, 99.0, at + 5, bars, state_of(low=(at + 900, 102.5)), structure=True)
    assert new["first"] == "TRAIL" and new["r"] == pytest.approx(102.5 - 0.3 * 0.5 - 100.0)  # dip - 0,3 x 4H ATR
    above = outcome.simulate_trail("BUY", 100.0, 99.0, at + 5, bars, state_of(low=(at + 900, 103.5)), structure=True)
    assert above["r"] == 0.0  # fiyatin ustundeki seviyeye stop konmaz


def test_a_swing_becomes_a_sweepable_level_only_after_it_is_confirmed():
    """Donus noktasi, sagindaki 3 mum kapanmadan seviye sayilmaz (supurme mumu kendi olusturdugu tepeyi goremez)."""
    bars = [bar(i * 3600, 100, 100.5, 99.5, 100) for i in range(20)]
    bars[10] = bar(bars[10]["time"], 100, 104.0, 99.5, 100)
    frame = Frame(bars)
    highs, lows = v13.swings(frame)
    assert 10 in highs
    assert (104.0, "swing H") not in v13.levels(frame, [], highs, lows, 13)[0]
    assert (104.0, "swing H") in v13.levels(frame, [], highs, lows, 14)[0]
