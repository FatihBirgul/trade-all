"""Faz 5 strateji kutuphanesi: `strateji_listesi_v2.md`deki tanimlar, KAYNAKTAKI varsayilan parametrelerle.

Her strateji kendi zaman diliminde, mum KAPANISINDA sinyal uretir. Kaynak cikis vermiyorsa varsayilan: stop 2 x ATR(14)
ve karsi sinyalde cikis. Kaynaktan bilincli farklar her stratejinin `note` alaninda yazilidir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import indicators as ind
from .engine import Series, Spec

NAN = np.nan


@dataclass(frozen=True)
class Strategy:
    id: str
    family: str  # A trend, B kirilim, C ortalamaya donus, D takvim, E capraz, X mevcut
    tf: str
    source: str
    build: Callable  # (series, context) -> Spec
    note: str = ""
    kinds: tuple = ("forex", "metal", "crypto", "index")


def _rows(s: Series) -> list[dict]:
    return [{"time": int(s.time[i]), "open": float(s.open[i]), "high": float(s.high[i]), "low": float(s.low[i]),
             "close": float(s.close[i]), "tick_volume": 0} for i in range(len(s))]


def _false(n):
    return np.zeros(n, bool)


def _atr_stop(s: Series, k: float = 2.0, n: int = 14) -> np.ndarray:
    return k * ind.atr(s.high, s.low, s.close, n)


# ---------------------------------------------------------------- A. trend takibi
def turtle(entry_n: int, exit_n: int):
    def build(s: Series, ctx) -> Spec:
        hi, lo = ind.rolling_max(s.high, entry_n), ind.rolling_min(s.low, entry_n)
        xlo, xhi = ind.rolling_min(s.low, exit_n), ind.rolling_max(s.high, exit_n)
        n_ = ind.atr(s.high, s.low, s.close, 20)
        return Spec(long=s.close > hi, short=s.close < lo, stop=2.0 * n_,
                    exit_long=s.close < xlo, exit_short=s.close > xhi)
    return build


def ma_cross(s: Series, ctx) -> Spec:
    fast, slow = ind.sma(s.close, 50), ind.sma(s.close, 200)
    up, down = ind.cross_up(fast, slow), ind.cross_down(fast, slow)
    return Spec(long=up, short=down, stop=_atr_stop(s), exit_long=down, exit_short=up)


def faber(s: Series, ctx) -> Spec:
    m = ind.sma(s.close, 200)
    above, below = s.close > m, s.close < m
    return Spec(long=above, short=below, stop=_atr_stop(s), exit_long=below, exit_short=above)


def tsmom(s: Series, ctx) -> Spec:
    """Ayin ilk D1 kapanisinda son 252 islem gunu getirisinin isaretine gore yon; ayda bir yeniden dengeleme."""
    n = len(s)
    month = np.array([np.datetime64(int(x), "s").astype("datetime64[M]") for x in s.time])
    first = np.concatenate([[False], month[1:] != month[:-1]])  # ayin ilk mumu: bir onceki ayin son kapanisindan sonra
    past = np.concatenate([np.full(252, NAN), s.close[:-252]]) if n > 252 else np.full(n, NAN)
    with np.errstate(invalid="ignore"):
        up, down = first & (s.close > past), first & (s.close < past)
    return Spec(long=up, short=down, stop=_atr_stop(s), exit_long=down, exit_short=up)


def clenow(s: Series, ctx) -> Spec:
    e50, e100 = ind.ema(s.close, 50), ind.ema(s.close, 100)
    hi, lo = ind.rolling_max(s.close, 50), ind.rolling_min(s.close, 50)
    a100 = ind.atr(s.high, s.low, s.close, 100)
    return Spec(long=(e50 > e100) & (s.close > hi), short=(e50 < e100) & (s.close < lo), stop=3.0 * a100,
                trail=3.0 * a100)


def supertrend(s: Series, ctx) -> Spec:
    line, d = ind.supertrend(s.high, s.low, s.close, 10, 3.0)
    prev = np.concatenate([[0.0], d[:-1]])
    up, down = (d > 0) & (prev < 0), (d < 0) & (prev > 0)
    return Spec(long=up, short=down, stop=np.abs(s.close - line), exit_long=down, exit_short=up)


def adx_dmi(s: Series, ctx) -> Spec:
    pdi, mdi, adx = ind.dmi(s.high, s.low, s.close, 14)
    strong, weak = adx > 25, adx < 20
    return Spec(long=strong & (pdi > mdi), short=strong & (mdi > pdi), stop=_atr_stop(s), exit_long=weak,
                exit_short=weak)


def parabolic(s: Series, ctx) -> Spec:
    sar, d = ind.psar(s.high, s.low, 0.02, 0.2)
    prev = np.concatenate([[0.0], d[:-1]])
    up, down = (d > 0) & (prev < 0), (d < 0) & (prev > 0)
    return Spec(long=up, short=down, stop=np.abs(s.close - sar), exit_long=down, exit_short=up)


def ichimoku(s: Series, ctx) -> Spec:
    t, k, top, bottom = ind.ichimoku(s.high, s.low)
    return Spec(long=(s.close > top) & (t > k), short=(s.close < bottom) & (t < k), stop=_atr_stop(s),
                exit_long=s.close < k, exit_short=s.close > k)


def macd_zero(s: Series, ctx) -> Spec:
    line, sig = ind.macd(s.close)
    up, down = ind.cross_up(line, sig), ind.cross_down(line, sig)
    return Spec(long=up & (line > 0), short=down & (line < 0), stop=_atr_stop(s), exit_long=down, exit_short=up)


# ---------------------------------------------------------------- mevcut stratejiler (karsilastirma)
def week_trade(s: Series, ctx) -> Spec:
    """WEEK TRADE (`bt.py`): 4H kapanisinda sinyal; stop 2 x gunluk ATR; cikis: +1R'de stop girise, +2R'de +1R
    kilit, sonra en iyi fiyat - 2 x 4H ATR; 7 gunde +1R yoksa cikis. Golge stratejinin yumusak surumu."""
    from ..signals.modules.strategies import week_trade as wt
    from ..week_replica import H4 as H4S
    n = len(s)
    long, short, stop, atr4 = _false(n), _false(n), np.full(n, NAN), np.full(n, NAN)
    h4 = [{"time": int(s.time[i]), "open": s.open[i], "high": s.high[i], "low": s.low[i], "close": s.close[i]}
          for i in range(n)]
    d = ctx["D1"]
    d1 = [{"time": int(d.time[i]), "open": d.open[i], "high": d.high[i], "low": d.low[i], "close": d.close[i]}
          for i in range(len(d))]
    d1_times = [b["time"] for b in d1]
    import bisect
    for i in range(60, n):
        cut = bisect.bisect_right(d1_times, h4[i]["time"] + H4S)
        found = wt.signal(h4[max(0, i - 299):i + 1], d1[max(0, cut - 300):cut])
        if found is None:
            continue
        (long if found["side"] == "BUY" else short)[i] = True
        stop[i], atr4[i] = found["stop_distance"], found["atr4"]

    def exit_fn(series, i, sign, entry, stop_price, spread_at):
        risk = abs(entry - stop_price)
        best, locked, stop_level = 0.0, 0, stop_price
        for j in range(i + 1, len(series)):
            shift = 0.0 if sign > 0 else spread_at(series.time[j])
            op, hi, lo, cl = (series.open[j] + shift, series.high[j] + shift, series.low[j] + shift,
                              series.close[j] + shift)
            if (sign > 0 and lo <= stop_level) or (sign < 0 and hi >= stop_level):
                price = min(op, stop_level) if sign > 0 else max(op, stop_level)
                return j, price, "stop"
            fav = ((hi if sign > 0 else lo) - entry) * sign / risk
            best = max(best, fav)
            if best >= 1.0 and locked < 1:
                stop_level, locked = (max(stop_level, entry) if sign > 0 else min(stop_level, entry)), 1
            if best >= 2.0 and locked < 2:
                level = entry + sign * risk
                stop_level, locked = (max(stop_level, level) if sign > 0 else min(stop_level, level)), 2
            if best > 2.0:
                extreme = entry + sign * best * risk
                level = extreme - sign * 2.0 * atr4[i]
                stop_level = max(stop_level, level) if sign > 0 else min(stop_level, level)
            if locked == 0 and series.time[j] + series.seconds - (series.time[i] + series.seconds) >= 7 * 86400:
                return j, cl, "time"
        return None, None, "open"

    return Spec(long=long, short=short, stop=stop, exit_fn=exit_fn)


def ema_h1(fast: int, slow: int):
    """Eski masanin EMA pullback H1 stratejisi (golgedeki `tb_emapb_h1_*`): sinyal ve stop ayni modulden; cikis
    sabit stop + 2R hedef (golge izleyicinin kurali)."""
    def build(s: Series, ctx) -> Spec:
        from ..signals.modules.base import Context
        from ..signals.modules.strategies.ema_pullback_h1 import EmaPullbackH1
        strategy = EmaPullbackH1(f"{fast}_{slow}")
        n = len(s)
        long, short, stop = _false(n), _false(n), np.full(n, NAN)
        rows = [{"time": int(s.time[i]), "open": s.open[i], "high": s.high[i], "low": s.low[i], "close": s.close[i],
                 "tick_volume": 0} for i in range(n)]
        upper = {tf: _rows(ctx[tf]) for tf in ("H4", "D1")}
        closes = {tf: ctx[tf].time + ctx[tf].seconds for tf in ("H4", "D1")}
        for i in range(60, n):
            last = rows[i]
            now = last["time"] + 3600
            m15 = [{**last, "time": last["time"] + 2700}]  # zamanlama icin: H1'in son ceyregi (fiyat H1 kapanisi)
            bars = {"M15": m15, "H1": rows[max(0, i - 299):i + 1]}
            for tf in ("H4", "D1"):
                cut = int(np.searchsorted(closes[tf], now, side="right"))
                bars[tf] = upper[tf][max(0, cut - 300):cut]
            signal = strategy.evaluate(Context(symbol=s.symbol, now=now, bars=bars))
            if signal is None:
                continue
            (long if signal.side == "BUY" else short)[i] = True
            stop[i] = abs(signal.entry - signal.stop)
        return Spec(long=long, short=short, stop=stop, target=2.0 * stop, max_bars=None)
    return build


STRATEGIES: list[Strategy] = [
    Strategy("A01_turtle_s1", "A", "D1", "Curtis Faith, Way of the Turtle (Sistem 1: 20/10)", turtle(20, 10),
             "giris kapanisla (gun ici kirilim degil); 'onceki islem kazandiysa atla' kurali ve piramitleme yok"),
    Strategy("A02_turtle_s2", "A", "D1", "Curtis Faith, Way of the Turtle (Sistem 2: 55/20)", turtle(55, 20),
             "giris kapanisla; piramitleme yok"),
    Strategy("A03_ma_cross", "A", "D1", "Klasik 50/200 kesisimi; Clenow, Following the Trend", ma_cross,
             "stop 2 x ATR(14) (kaynakta stop yok: varsayilan)"),
    Strategy("A04_faber_sma200", "A", "D1", "Faber (2007), fiyat > SMA200", faber,
             "D1 kapanisinda; SMA200 altinda SAT (FX'te simetrik); stop 2 x ATR(14) varsayilan"),
    Strategy("A05_tsmom12", "A", "D1", "Moskowitz, Ooi, Pedersen (2012), 12 ay zaman serisi momentumu", tsmom,
             "ayin ilk D1 kapanisinda yeniden dengeleme; 252 islem gunu; stop 2 x ATR(14) varsayilan"),
    Strategy("A06_clenow", "A", "D1", "Clenow, Following the Trend", clenow,
             "50 gunluk KAPANIS tepesi/dibi; iz suren stop 3 x ATR(100)"),
    Strategy("A07_supertrend", "A", "H4", "Olivier Seban, Supertrend (10, 3)", supertrend,
             "yon degisiminde giris ve cikis; ilk stop giristeki Supertrend cizgisi"),
    Strategy("A08_adx_dmi", "A", "H4", "Wilder (1978), ADX(14) > 25 + DMI", adx_dmi,
             "ADX < 20'de cikis; stop 2 x ATR(14) varsayilan"),
    Strategy("A09_psar", "A", "D1", "Wilder (1978), Parabolic SAR 0.02 / 0.2", parabolic,
             "donuste giris ve cikis; ilk stop giristeki SAR"),
    Strategy("A10_ichimoku", "A", "D1", "Goichi Hosoda, Ichimoku 9/26/52", ichimoku,
             "bulut ustu + Tenkan > Kijun; Kijun alti kapanista cikis; stop 2 x ATR(14)"),
    Strategy("A11_macd_zero", "A", "D1", "Gerald Appel, MACD 12/26/9", macd_zero,
             "MACD > 0 iken sinyal kesisimi; ters kesisimde cikis; stop 2 x ATR(14)"),
    Strategy("X_week_trade", "X", "H4", "Eski masanin bt.py'si (WEEK TRADE, yumusak)", week_trade),
    Strategy("X_ema_h1_20_21", "X", "H1", "Eski masanin EMA pullback H1 (20/21)", ema_h1(20, 21)),
    Strategy("X_ema_h1_21_50", "X", "H1", "Eski masanin EMA pullback H1 (21/50)", ema_h1(21, 50)),
]
BY_ID = {s.id: s for s in STRATEGIES}
