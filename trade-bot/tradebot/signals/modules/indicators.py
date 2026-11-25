"""Yeni stratejilerin kullandigi kucuk indikatorler. Girdi: kapanmis mumlar (eskiden yeniye)."""

from __future__ import annotations


def ema(values: list[float], period: int) -> list[float]:
    """Ustel hareketli ortalama; ilk deger ilk `period` degerin basit ortalamasidir. Cikti girdiyle ayni
    uzunluktadir, ilk `period - 1` deger icin ortalama henuz olusmadigindan `nan` doner."""
    if period <= 0 or len(values) < period:
        return [float("nan")] * len(values)
    out = [float("nan")] * (period - 1)
    current = sum(values[:period]) / period
    out.append(current)
    k = 2.0 / (period + 1)
    for value in values[period:]:
        current = value * k + current * (1 - k)
        out.append(current)
    return out


def atr(bars: list[dict], period: int = 14) -> float | None:
    """Son `period` mumun ortalama gercek araligi (basit ortalama)."""
    if len(bars) < period + 1:
        return None
    ranges = []
    for previous, bar in zip(bars[-period - 1:-1], bars[-period:]):
        ranges.append(max(bar["high"] - bar["low"], abs(bar["high"] - previous["close"]),
                          abs(bar["low"] - previous["close"])))
    return sum(ranges) / period


def trend(bars: list[dict], fast: int = 50, slow: int = 200) -> str | None:
    """EMA(fast) / EMA(slow) dizilimi ve son kapanisa gore yon: 'bullish' | 'bearish' | None."""
    if len(bars) < slow + 1:
        return None
    closes = [bar["close"] for bar in bars]
    fast_value, slow_value, close = ema(closes, fast)[-1], ema(closes, slow)[-1], closes[-1]
    if fast_value > slow_value and close > fast_value:
        return "bullish"
    if fast_value < slow_value and close < fast_value:
        return "bearish"
    return None
