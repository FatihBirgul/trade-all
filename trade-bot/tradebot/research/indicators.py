"""Gostergeler (numpy). Hepsi yalnizca o mumun ve oncesinin verisini kullanir; ilk degerler NaN."""

from __future__ import annotations

import numpy as np

NAN = np.nan


def sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), NAN)
    if len(x) >= n:
        c = np.cumsum(np.insert(x.astype(float), 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def ema(x: np.ndarray, n: int) -> np.ndarray:
    """Ustel ortalama; ilk deger ilk n degerin basit ortalamasi."""
    out = np.full(len(x), NAN)
    if len(x) < n:
        return out
    alpha = 2.0 / (n + 1.0)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = out[i - 1] + alpha * (x[i] - out[i - 1])
    return out


def rma(x: np.ndarray, n: int) -> np.ndarray:
    """Wilder ortalamasi (ATR, RSI, ADX)."""
    out = np.full(len(x), NAN)
    valid = np.flatnonzero(~np.isnan(x))
    if len(valid) < n:
        return out
    first = valid[0]
    if first + n > len(x):
        return out
    out[first + n - 1] = np.nanmean(x[first:first + n])
    for i in range(first + n, len(x)):
        out[i] = out[i - 1] + (x[i] - out[i - 1]) / n
    return out


def true_range(h, low, c) -> np.ndarray:
    prev = np.concatenate([[NAN], c[:-1]])
    tr = np.fmax(h - low, np.fmax(np.abs(h - prev), np.abs(low - prev)))
    tr[0] = h[0] - low[0]
    return tr


def atr(h, low, c, n: int = 14) -> np.ndarray:
    return rma(true_range(h, low, c), n)


def rolling_max(x: np.ndarray, n: int, *, prior: bool = True) -> np.ndarray:
    """Son n degerin en buyugu. `prior`: mevcut mum HARIC (kirilim icin onceki n mum)."""
    out = np.full(len(x), NAN)
    for i in range(n if prior else n - 1, len(x)):
        lo = i - n if prior else i - n + 1
        out[i] = x[lo:i if prior else i + 1].max()
    return out


def rolling_min(x: np.ndarray, n: int, *, prior: bool = True) -> np.ndarray:
    return -rolling_max(-x, n, prior=prior)


def rsi(c: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(c, prepend=NAN)
    up, down = rma(np.where(np.isnan(d), NAN, np.maximum(d, 0.0)), n), rma(np.where(np.isnan(d), NAN, np.maximum(-d, 0.0)), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100.0 - 100.0 / (1.0 + up / down)
    out[(down == 0) & (up > 0)] = 100.0
    out[(down == 0) & (up == 0)] = 50.0
    return out


def dmi(h, low, c, n: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(+DI, -DI, ADX), Wilder."""
    up = np.diff(h, prepend=NAN)
    down = -np.diff(low, prepend=NAN)
    plus = np.where((up > down) & (up > 0), up, 0.0)
    minus = np.where((down > up) & (down > 0), down, 0.0)
    plus[0] = minus[0] = NAN
    tr = true_range(h, low, c)
    tr[0] = NAN
    atr_ = rma(tr, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100.0 * rma(plus, n) / atr_
        mdi = 100.0 * rma(minus, n) / atr_
        dx = 100.0 * np.abs(pdi - mdi) / (pdi + mdi)
    return pdi, mdi, rma(dx, n)


def supertrend(h, low, c, n: int = 10, mult: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """(cizgi, yon: +1 / -1). Klasik bant tasima kurali."""
    a = atr(h, low, c, n)
    mid = (h + low) / 2.0
    upper, lower = mid + mult * a, mid - mult * a
    line, direction = np.full(len(c), NAN), np.zeros(len(c))
    fu, fl = upper.copy(), lower.copy()
    for i in range(len(c)):
        if np.isnan(a[i]):
            continue
        if i > 0 and not np.isnan(fu[i - 1]):
            fu[i] = upper[i] if (upper[i] < fu[i - 1] or c[i - 1] > fu[i - 1]) else fu[i - 1]
            fl[i] = lower[i] if (lower[i] > fl[i - 1] or c[i - 1] < fl[i - 1]) else fl[i - 1]
            prev = direction[i - 1] or 1.0
            if prev > 0:
                direction[i] = -1.0 if c[i] < fl[i] else 1.0
            else:
                direction[i] = 1.0 if c[i] > fu[i] else -1.0
        else:
            direction[i] = 1.0
        line[i] = fl[i] if direction[i] > 0 else fu[i]
    return line, direction


def psar(h, low, step: float = 0.02, maximum: float = 0.2) -> tuple[np.ndarray, np.ndarray]:
    """(SAR, yon). Wilder."""
    n = len(h)
    sar, direction = np.full(n, NAN), np.zeros(n)
    if n < 2:
        return sar, direction
    up, af = True, step
    ep, s = h[0], low[0]
    for i in range(1, n):
        s = s + af * (ep - s)
        if up:
            s = min(s, low[i - 1], low[i - 2] if i > 1 else low[i - 1])
            if low[i] < s:
                up, s, ep, af = False, ep, low[i], step
            elif h[i] > ep:
                ep, af = h[i], min(af + step, maximum)
        else:
            s = max(s, h[i - 1], h[i - 2] if i > 1 else h[i - 1])
            if h[i] > s:
                up, s, ep, af = True, ep, h[i], step
            elif low[i] < ep:
                ep, af = low[i], min(af + step, maximum)
        sar[i], direction[i] = s, 1.0 if up else -1.0
    return sar, direction


def macd(c, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray]:
    line = ema(c, fast) - ema(c, slow)
    sig = np.full(len(c), NAN)
    valid = np.flatnonzero(~np.isnan(line))
    if len(valid):
        sig[valid[0]:] = ema(line[valid[0]:], signal)
    return line, sig


def ichimoku(h, low, tenkan: int = 9, kijun: int = 26, span_b: int = 52):
    """(tenkan, kijun, bulut ust, bulut alt) — bulut `kijun` mum ileri kaydirilmis: i'deki bulut i-26'da hesaplanir."""
    def mid(n):
        return (rolling_max(h, n, prior=False) + rolling_min(low, n, prior=False)) / 2.0
    t, k = mid(tenkan), mid(kijun)
    a, b = (t + k) / 2.0, mid(span_b)
    shift = lambda x: np.concatenate([np.full(kijun, NAN), x[:-kijun]])  # noqa: E731
    sa, sb = shift(a), shift(b)
    return t, k, np.fmax(sa, sb), np.fmin(sa, sb)


def bollinger(c, n: int = 20, k: float = 2.0):
    mid = sma(c, n)
    sd = np.full(len(c), NAN)
    for i in range(n - 1, len(c)):
        sd[i] = c[i - n + 1:i + 1].std()
    return mid, mid + k * sd, mid - k * sd


def cross_up(a, b) -> np.ndarray:
    prev_a, prev_b = np.concatenate([[NAN], a[:-1]]), np.concatenate([[NAN], b[:-1]])
    return (a > b) & (prev_a <= prev_b)


def cross_down(a, b) -> np.ndarray:
    return cross_up(-np.asarray(a), -np.asarray(b))
