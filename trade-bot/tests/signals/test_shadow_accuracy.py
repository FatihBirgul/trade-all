"""Golge izleyicinin DOGRULUK kaniti.

Karne ve canliya gecis kararlari golge sonuclarina dayanir. Bu dosya izleyiciyi uc yoldan sinar:
1. Rastgele senaryolarda, testin icindeki en duz "kitabi" hesapla ve `outcome.simulate_fixed` ile (ikisi de
   izleyiciden bagimsiz yazildi) ayni sonucu vermeli.
2. Yonsuz (egilimsiz) rastgele yuruyuste, maliyetsiz bir oyunun beklenen sonucu 0R'dir: AL ve SAT ayri ayri
   sifira yakin olmali (yon ya da stop tarafi hatasi buyuk eksi verirdi).
3. Spread stop mesafesinin %20'si ise beklenen sonuc yaklasik -0,2R'dir (spread BIR kez odenir; iki kez dusulseydi
   -0,4R olurdu).
"""
import random

import pytest

from tradebot.signals import outcome
from tradebot.signals.adapter import Candidate
from tradebot.signals.shadow import MAX_BARS, ShadowBook
from tradebot.store.repo import Repo

M15 = 900
START = 1_800_000_000 // M15 * M15


def walk(rnd: random.Random, bars: int, start: float = 100.0, step: float = 0.02) -> list[dict]:
    """Egilimsiz bid mumlari: her mum 15 kucuk adimdan olusur (tepe/dip adimlarin gercek uclaridir)."""
    out, price = [], start
    for index in range(bars):
        opened = high = low = price
        for _ in range(15):
            price += rnd.gauss(0.0, step)
            high, low = max(high, price), min(low, price)
        out.append({"time": START + index * M15, "open": opened, "high": high, "low": low, "close": price})
    return out


def textbook(side, entry, stop, target, spread, bars):
    """Kitabi hesap: her mumda pozisyonun KAPANACAGI fiyat araligi; once stop, sonra hedef; 96 mumda sure."""
    risk = abs(entry - stop)
    for count, bar in enumerate(bars[:MAX_BARS], start=1):
        if side == "BUY":  # bid'den satilarak kapanir
            if bar["low"] <= stop:
                return -1.0
            if bar["high"] >= target:
                return (target - entry) / risk
            last = (bar["close"] - entry) / risk
        else:  # ask'tan (bid + spread) geri alinarak kapanir
            if bar["high"] + spread >= stop:
                return -1.0
            if bar["low"] + spread <= target:
                return (entry - target) / risk
            last = (entry - (bar["close"] + spread)) / risk
        if count == MAX_BARS:
            return last
    return None


def trade(rnd: random.Random, index: int, spread_share: float, tmp_book: ShadowBook, side: str | None = None):
    """Rastgele bir islem acar -> (golge sonucu, kitabi sonuc, bagimsiz hesap sonucu)."""
    bars = walk(rnd, 140)
    side = side or rnd.choice(["BUY", "SELL"])
    sign = 1.0 if side == "BUY" else -1.0
    distance = rnd.uniform(0.12, 0.6)  # stop mesafesi (bir M15 mumunun ~1,5-8 kati)
    spread = spread_share * distance
    opened_at = bars[20]["time"] + rnd.uniform(1.0, 40.0)  # 20. mum olusurken, kapanistan birkac saniye sonra
    bid = bars[19]["close"]
    entry = bid + spread if side == "BUY" else bid  # AL ask'tan, SAT bid'den acilir
    stop, target = entry - sign * distance, entry + sign * 2.0 * distance
    symbol = f"S{index}"
    candidate = Candidate(symbol=symbol, side=side, entry=entry, stop_loss=stop, take_profit_1=target,
                          take_profit_2=target, lots=0.01, strategy_id="tb_ema_pullback_v1", setup_id=f"k{index}",
                          net_rr=2.0, analysis_id="a" * 64, risk_amount=1.0)
    assert tmp_book.open(candidate, "shadow", 60.0, opened_at, spread)
    closed = tmp_book.resolve(symbol, bars, bars[-1]["time"] + M15)
    got = closed[0]["result_r"] if closed else None
    after = [b for b in bars if b["time"] + M15 > opened_at]
    independent = outcome.simulate_fixed(side, entry, stop, target, opened_at, bars, spread_at=lambda moment: spread)
    return got, textbook(side, entry, stop, target, spread, after), independent["r"]


def test_shadow_result_equals_two_independent_calculations(tmp_path):
    book, rnd = ShadowBook(Repo(tmp_path / "bot.db")), random.Random(7)
    seen = {"stop": 0, "target": 0, "time": 0}
    for index in range(400):
        got, expected, independent = trade(rnd, index, rnd.choice([0.0, 0.1, 0.25]), book)
        assert got is not None and got == pytest.approx(expected, abs=1e-9), index
        assert independent == pytest.approx(expected, abs=1e-3), index
        seen["stop" if got == -1.0 else "target" if got == pytest.approx(2.0) else "time"] += 1
    assert min(seen.values()) >= 20  # uc sonuc turu de yeterince goruldu


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_a_driftless_market_gives_zero_expectancy_and_the_spread_is_paid_exactly_once(tmp_path, side):
    book, rnd = ShadowBook(Repo(tmp_path / "bot.db")), random.Random(11 if side == "BUY" else 12)
    free = [trade(rnd, i, 0.0, book, side)[0] for i in range(1200)]
    costly = [trade(rnd, 5000 + i, 0.2, book, side)[0] for i in range(1200)]
    mean = lambda values: sum(values) / len(values)  # noqa: E731
    wins = sum(1 for r in free if r > 1.9) / len(free)
    # Maliyetsiz, egilimsiz: beklenen 0R (olcum hatasi ~0,04R). Ayni mumda stop onceligi cok kucuk bir eksi verir.
    assert -0.12 < mean(free) < 0.08, mean(free)
    assert 0.24 < wins < 0.40, wins  # 2R hedefte kazanma ~1/3; %3 gibi bir oran bu izleyiciden CIKMAZ
    # Spread = 0,2R: beklenen ~-0,2R. Iki kez dusulseydi ~-0,4R olurdu.
    assert -0.31 < mean(costly) < -0.10, mean(costly)
