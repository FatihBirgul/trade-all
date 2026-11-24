"""Deterministic technical-analysis engine.

All indicator values are computed here from real OHLCV data using pandas/numpy.
The AI layer is NEVER asked to invent indicator numbers — it only receives the
structured output of this module.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def _round(v, n=2):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), n)


def _to_df(candles: List[dict]) -> pd.DataFrame:
    df = pd.DataFrame(candles)
    return df


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(series: pd.Series):
    ema12 = ema(series, 12)
    ema26 = ema(series, 26)
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return macd_line, signal, hist


def stoch_rsi(series: pd.Series, period: int = 14):
    r = rsi(series, period)
    min_r = r.rolling(period).min()
    max_r = r.rolling(period).max()
    k = (r - min_r) / (max_r - min_r).replace(0, np.nan) * 100
    d = k.rolling(3).mean()
    return k, d


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.rolling(period).mean()


def bollinger(series: pd.Series, period: int = 20, mult: float = 2.0):
    mid = sma(series, period)
    std = series.rolling(period).std()
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower


def _swings(df: pd.DataFrame, left: int = 3, right: int = 3):
    """Return indices of swing highs and swing lows (fractal pivots)."""
    highs, lows = [], []
    h = df["high"].values
    l = df["low"].values
    n = len(df)
    for i in range(left, n - right):
        window_h = h[i - left : i + right + 1]
        window_l = l[i - left : i + right + 1]
        if h[i] == window_h.max() and (window_h == h[i]).sum() == 1:
            highs.append(i)
        if l[i] == window_l.min() and (window_l == l[i]).sum() == 1:
            lows.append(i)
    return highs, lows


def support_resistance(df: pd.DataFrame, swing_highs, swing_lows, price: float):
    """Cluster recent swing points into support (below price) / resistance (above)."""
    tol = price * 0.006  # 0.6% clustering tolerance

    def cluster(vals):
        vals = sorted(vals)
        clusters = []
        for v in vals:
            placed = False
            for c in clusters:
                if abs(c["level"] - v) <= tol:
                    c["points"].append(v)
                    c["level"] = float(np.mean(c["points"]))
                    placed = True
                    break
            if not placed:
                clusters.append({"level": v, "points": [v]})
        # strength = number of touches
        return [
            {"level": _round(c["level"], 4), "touches": len(c["points"])}
            for c in clusters
        ]

    high_vals = [df["high"].values[i] for i in swing_highs][-12:]
    low_vals = [df["low"].values[i] for i in swing_lows][-12:]

    resistance = [c for c in cluster(high_vals + low_vals) if c["level"] and c["level"] > price]
    support = [c for c in cluster(high_vals + low_vals) if c["level"] and c["level"] < price]

    resistance = sorted(resistance, key=lambda x: x["level"])[:4]
    support = sorted(support, key=lambda x: x["level"], reverse=True)[:4]
    return support, resistance


def market_structure(df: pd.DataFrame, swing_highs, swing_lows) -> Dict:
    """Classify structure from the last swing highs/lows."""
    h = [df["high"].values[i] for i in swing_highs][-3:]
    l = [df["low"].values[i] for i in swing_lows][-3:]

    hh = len(h) >= 2 and h[-1] > h[-2]
    hl = len(l) >= 2 and l[-1] > l[-2]
    lh = len(h) >= 2 and h[-1] < h[-2]
    ll = len(l) >= 2 and l[-1] < l[-2]

    if hh and hl:
        label = "uptrend"
        desc = "Higher highs and higher lows"
    elif lh and ll:
        label = "downtrend"
        desc = "Lower highs and lower lows"
    else:
        label = "ranging"
        desc = "No clear sequence of higher highs/lows"

    return {
        "label": label,
        "description": desc,
        "higher_high": bool(hh),
        "higher_low": bool(hl),
        "lower_high": bool(lh),
        "lower_low": bool(ll),
    }


def compute(candles: List[dict]) -> Dict:
    """Compute the full structured technical snapshot."""
    df = _to_df(candles)
    close = df["close"]
    price = float(close.iloc[-1])

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    ema100 = ema(close, 100)
    ema200 = ema(close, 200)
    sma20 = sma(close, 20)

    rsi14 = rsi(close, 14)
    macd_line, macd_signal, macd_hist = macd(close)
    srsi_k, srsi_d = stoch_rsi(close)
    atr14 = atr(df, 14)
    bb_u, bb_m, bb_l = bollinger(close, 20)

    vol = df["volume"]
    vol_ma = sma(vol, 20)
    last_vol = float(vol.iloc[-1])
    last_vol_ma = float(vol_ma.iloc[-1]) if not np.isnan(vol_ma.iloc[-1]) else last_vol
    vol_ratio = last_vol / last_vol_ma if last_vol_ma else 1.0

    swing_highs, swing_lows = _swings(df)
    support, resistance = support_resistance(df, swing_highs, swing_lows, price)
    structure = market_structure(df, swing_highs, swing_lows)

    def last(s):
        v = s.iloc[-1]
        return _round(v, 4) if not np.isnan(v) else None

    indicators = {
        "price": _round(price, 4),
        "ema20": last(ema20),
        "ema50": last(ema50),
        "ema100": last(ema100),
        "ema200": last(ema200),
        "sma20": last(sma20),
        "rsi14": last(rsi14),
        "macd": last(macd_line),
        "macd_signal": last(macd_signal),
        "macd_hist": last(macd_hist),
        "stoch_rsi_k": last(srsi_k),
        "stoch_rsi_d": last(srsi_d),
        "atr14": last(atr14),
        "atr_pct": _round((atr14.iloc[-1] / price) * 100, 2) if not np.isnan(atr14.iloc[-1]) else None,
        "bb_upper": last(bb_u),
        "bb_middle": last(bb_m),
        "bb_lower": last(bb_l),
        "volume": _round(last_vol, 2),
        "volume_ma20": _round(last_vol_ma, 2),
        "volume_ratio": _round(vol_ratio, 2),
    }

    return {
        "price": _round(price, 4),
        "indicators": indicators,
        "structure": structure,
        "levels": {"support": support, "resistance": resistance},
        "closes": [ _round(c, 4) for c in close.tail(60).tolist() ],
    }
