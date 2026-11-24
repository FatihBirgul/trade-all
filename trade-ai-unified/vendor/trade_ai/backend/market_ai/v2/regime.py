"""Trade AI 2.0 market regime classifier — deterministic and conservative.

The output describes observed *historical* market behavior; it is not a
trade signal or probability. Uses only already closed candles, with no
future pivot confirmation and no dependencies on the V1 API or database.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Sequence


REGIME_VERSION = "v2-regime-1"
DEFAULT_MIN_EFFICIENCY = 0.45
DEFAULT_BREAKOUT_ATR_MULTIPLE = 0.25


@dataclass(frozen=True)
class RegimeResult:
    regime: str  # trend / range / breakout / unknown
    direction: str  # bullish / bearish / neutral
    reason: str
    observations: int


def classify_regime(
    closes: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    lookback: int = 20,
    min_efficiency: float = DEFAULT_MIN_EFFICIENCY,
    breakout_atr_multiple: float = DEFAULT_BREAKOUT_ATR_MULTIPLE,
) -> RegimeResult:
    """Classify using path efficiency and previous-window breakout.

    A breakout requires the last close to exceed the previous N-1 highs/lows
    by a fraction of mean true range; a trend requires net movement relative
    to total movement. Inconclusive observations return unknown/range, not a
    fabricated directional signal.

    Callers MUST first pass a quality gate and supply only final bars.
    """
    unknown = RegimeResult("unknown", "neutral", "insufficient_or_invalid_data", len(closes))
    if (
        isinstance(lookback, bool) or not isinstance(lookback, int)
        or lookback < 5 or not 0 <= min_efficiency <= 1
        or not isfinite(min_efficiency) or not isfinite(breakout_atr_multiple)
        or breakout_atr_multiple < 0
    ):
        raise ValueError("Invalid regime configuration")
    if len(closes) != len(highs) or len(closes) != len(lows) or len(closes) < lookback:
        return unknown
    c = closes[-lookback:]
    h = highs[-lookback:]
    l = lows[-lookback:]
    if any(
        isinstance(x, bool) or not isinstance(x, (int, float)) or not isfinite(x) or x <= 0
        for series in (c, h, l) for x in series
    ):
        return unknown
    if any(low > min(close, high) or high < close for close, high, low in zip(c, h, l)):
        return unknown

    true_ranges = [
        max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        for i in range(1, len(c))
    ]
    typical_range = mean(true_ranges)
    if typical_range <= 0:
        return RegimeResult("unknown", "neutral", "flat_or_zero_range", len(c))

    threshold = typical_range * breakout_atr_multiple
    if c[-1] > max(h[:-1]) + threshold:
        return RegimeResult("breakout", "bullish", "closed_above_previous_range", len(c))
    if c[-1] < min(l[:-1]) - threshold:
        return RegimeResult("breakout", "bearish", "closed_below_previous_range", len(c))

    traveled = sum(abs(c[i] - c[i - 1]) for i in range(1, len(c)))
    if traveled <= 0:
        return RegimeResult("range", "neutral", "no_directional_progress", len(c))
    efficiency = abs(c[-1] - c[0]) / traveled
    if efficiency >= min_efficiency:
        if c[-1] > c[0]:
            return RegimeResult("trend", "bullish", "efficient_upward_path", len(c))
        if c[-1] < c[0]:
            return RegimeResult("trend", "bearish", "efficient_downward_path", len(c))
    return RegimeResult("range", "neutral", "low_path_efficiency", len(c))
