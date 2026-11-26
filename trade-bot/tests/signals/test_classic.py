"""Bilinen uc golge strateji: ICT Silver Bullet, Asya araligi / Londra kirilimi, Kaplumbaga 55/20."""
from datetime import datetime, timezone

import pytest

from tests.signals.market_gen import DURATIONS, T0, closed, market
from tradebot.signals import outcome
from tradebot.signals.modules import modules
from tradebot.signals.modules.base import Context
from tradebot.signals.modules.strategies import classic, v13
from tradebot.signals.modules.strategies.v13 import Frame

IDS = ("tb_silver_bullet_v1", "tb_asia_london_v1", "tb_turtle55_v1")


def signals(frames, start_day, end_day):
    chosen = [m for m in modules("strategy") if m.id in IDS]
    out = []
    for m15 in frames["M15"]:
        now = m15["time"] + 900
        if now < T0 + start_day * 86400 or now >= T0 + end_day * 86400:
            continue
        bars = {"M15": closed(frames, "M15", now, 256), "H1": closed(frames, "H1", now, 256),
                "H4": closed(frames, "H4", now, 120), "D1": closed(frames, "D1", now, 120)}
        context = Context(symbol="X", now=now + 5, bars=bars)
        for module in chosen:
            signal = module.evaluate(context)
            if signal is not None:
                out.append((module.id, now, signal, context))
    return out


@pytest.fixture(scope="module")
def run():
    frames = market(3, 300)
    return frames, signals(frames, 150, 300)


def test_registered_as_shadow_only_strategies():
    from tradebot.config import BotSettings, strategy_mode
    assert set(IDS) <= {m.id for m in modules("strategy")}
    assert all(strategy_mode(BotSettings(), name) == "shadow" for name in IDS)


def test_every_signal_follows_its_published_rule(run):
    frames, found = run
    assert {name for name, *_ in found} == set(IDS)
    for name, now, signal, context in found:
        sign = 1.0 if signal.side == "BUY" else -1.0
        risk = (signal.entry - signal.stop) * sign
        assert risk > 0 and signal.bar_time == now - 900 and signal.entry == context.bars["M15"][-1]["close"]
        plan = signal.plan
        if name == "tb_silver_bullet_v1":
            local = datetime.fromtimestamp(now - 1, timezone.utc).astimezone(classic.NEW_YORK)
            assert any(0 <= (local.hour - hour) * 60 + local.minute < 120 for hour in classic.SILVER_HOURS)
            assert plan["type"] == "FIXED" and (plan["target"] - signal.entry) * sign >= risk - 1e-9  # hedef >= 1R
        if name == "tb_asia_london_v1":
            local = datetime.fromtimestamp(now - 1, timezone.utc).astimezone(classic.LONDON)
            assert classic.ASIA_END <= local.hour < classic.LONDON_END
            day = [b for b in context.bars["M15"]
                   if datetime.fromtimestamp(b["time"], timezone.utc).astimezone(classic.LONDON).date() == local.date()]
            asia = [b for b in day if datetime.fromtimestamp(b["time"], timezone.utc).astimezone(classic.LONDON).hour < 8]
            top, bottom = max(b["high"] for b in asia), min(b["low"] for b in asia)
            assert signal.stop == (bottom if signal.side == "BUY" else top)  # stop araligin karsi ucu
            assert plan["target"] == pytest.approx(top + (top - bottom) if signal.side == "BUY" else bottom - (top - bottom))
            assert (signal.entry > top) if signal.side == "BUY" else (signal.entry < bottom)
            daily = Frame(context.bars["D1"]).atr[-1]
            assert classic.RANGE_MIN_ATR * daily <= top - bottom <= classic.RANGE_MAX_ATR * daily
            assert 1 <= plan["max_bars"] <= 13 * 4  # gun sonuna (21:00 Londra) kadar
        if name == "tb_turtle55_v1":
            d1 = context.bars["D1"]
            assert now % 86400 == 0 and d1[-1]["time"] + 86400 == now  # yalnizca gunluk kapanista
            prior = d1[-56:-1]
            if signal.side == "BUY":
                assert d1[-1]["close"] > max(b["high"] for b in prior)
            else:
                assert d1[-1]["close"] < min(b["low"] for b in prior)
            assert risk == pytest.approx(2.0 * v13.rma_series(Frame(d1).tr, 20)[-1])
            assert plan == {"type": "CHANNEL", "model": "turtle 55/20", "score": None, "exit_days": 20, "volume_ratio": None}
    # Asya/Londra: gunde en cok bir kirilim (ilk kapanis).
    days = [int(now // 86400) for name, now, *_ in found if name == "tb_asia_london_v1"]
    assert len(days) == len(set(days))


def test_signals_do_not_change_when_the_future_is_cut_off(run):
    frames, found = run
    cut = T0 + 230 * 86400 + 9 * 3600
    past = {tf: [b for b in bars if b["time"] + DURATIONS[tf] <= cut] for tf, bars in frames.items()}
    again = signals(past, 150, 300)
    key = lambda item: (item[0], item[1], item[2].side, item[2].stop, item[2].target)  # noqa: E731
    assert [key(i) for i in again] == [key(i) for i in found if i[1] <= cut] and len(again) > 30


def test_channel_exit_uses_only_earlier_days_and_the_stop_comes_first():
    day = 86400
    at = 100 * day
    flat = lambda start, price: [{"time": start + i * 900, "open": price, "high": price + 0.1, "low": price - 0.1,  # noqa: E731
                                 "close": price} for i in range(96)]
    bars = flat(at, 102.0) + flat(at + day, 104.0) + flat(at + 2 * day, 100.5)
    levels = {at + day: 95.0, at + 2 * day: 96.0, at + 3 * day: 101.0}  # ucuncu gun kapanisi kanalin altinda
    result = outcome.simulate_channel("BUY", 100.0, 98.0, at + 5, bars, lambda moment: levels.get(moment))
    assert result["first"] == "CHANNEL" and result["closed_at"] == at + 3 * day and result["r"] == pytest.approx(0.25)
    stopped = flat(at, 102.0) + [{"time": at + day, "open": 102, "high": 102, "low": 97.5, "close": 99}]
    assert outcome.simulate_channel("BUY", 100.0, 98.0, at + 5, stopped, lambda moment: None)["r"] == -1.0
    still = outcome.simulate_channel("SELL", 100.0, 102.0, at + 5, flat(at, 99.0), lambda moment: None)
    assert still["r"] is None and still["open_r"] == pytest.approx(0.5)
    short = outcome.simulate_channel("SELL", 100.0, 102.0, at + 5, flat(at, 99.0), lambda moment: 98.5)
    assert short["first"] == "CHANNEL" and short["r"] == pytest.approx(0.5)  # kapanis kanalin ustunde: cikis


def test_forward_replay_runs_the_three_strategies_with_their_own_exits():
    from tradebot import backtest, forward
    history = backtest.History()
    for tf, bars in market(3, 300).items():
        history.add("X", tf, bars)
    spreads = forward.Spreads({"X": {"hours": {}, "all": 0.004}})
    trades = [t for t in forward.swing_trades("X", "forex", history, spreads, T0 + 200 * 86400, T0 + 300 * 86400, 0.15)
              if t["strategy_id"] in IDS]
    exits = {name: {t["exit"] for t in trades if t["strategy_id"] == name} for name in IDS}
    assert exits["tb_silver_bullet_v1"] <= {"SL", "TP", "TIME", None} and "TP" in exits["tb_silver_bullet_v1"]
    assert "TIME" in exits["tb_asia_london_v1"]  # gun sonunda cikis
    assert exits["tb_turtle55_v1"] <= {"SL", "CHANNEL", None} and exits["tb_turtle55_v1"]
    level = forward.d1_channel(history, "X")
    d1 = history.all("X", "D1")
    moment = d1[100]["time"] + 86400  # 100. gunluk mumun kapanisi
    assert level(moment, "BUY", 20) == min(b["low"] for b in d1[80:100])  # kapanan gunun kendisi dahil degil
    assert level(d1[5]["time"] + 86400, "BUY", 20) is None
