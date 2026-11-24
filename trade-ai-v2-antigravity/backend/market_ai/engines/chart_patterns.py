"""Chart pattern detection engine.

Uses swing pivots + trendline geometry to detect classic chart patterns.

All detections are heuristic signals, not guarantees.

V2 evidence metadata:
- `location`: candle index where the pattern is considered formed.
- `age_bars`: number of closed candles since that location.
- `confirmed`: whether the pattern is considered structurally confirmed.
- `base_confidence`: original detector confidence.
- `recency_multiplier`: time-decay multiplier.
- `confidence`: recency-adjusted confidence used by downstream scoring.

Defensive by design: any unexpected failure returns an empty list.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Pivot helpers
# ---------------------------------------------------------------------------
def _pivots(
    highs,
    lows,
    left=3,
    right=3,
):
    hi = []
    lo = []

    n = len(highs)

    for i in range(
        left,
        n - right,
    ):
        wh = highs[
            i - left : i + right + 1
        ]

        wl = lows[
            i - left : i + right + 1
        ]

        if (
            highs[i] == max(wh)
            and wh.count(highs[i]) == 1
        ):
            hi.append(
                (i, highs[i])
            )

        if (
            lows[i] == min(wl)
            and wl.count(lows[i]) == 1
        ):
            lo.append(
                (i, lows[i])
            )

    return hi, lo


def _slope(points):
    if len(points) < 2:
        return 0.0

    xs = np.array(
        [
            p[0]
            for p in points
        ],
        dtype=float,
    )

    ys = np.array(
        [
            p[1]
            for p in points
        ],
        dtype=float,
    )

    if xs.max() == xs.min():
        return 0.0

    return float(
        np.polyfit(
            xs,
            ys,
            1,
        )[0]
    )


# ---------------------------------------------------------------------------
# Recency
# ---------------------------------------------------------------------------
def _recency_multiplier(
    age_bars: int,
) -> float:
    """Decay chart-pattern confidence as it becomes older.

    0 bars old -> 1.00
    1 bar old  -> 0.55
    2 bars     -> 0.35
    3 bars     -> 0.20
    4 bars     -> 0.10
    5+ bars    -> 0.05
    """
    age = max(
        0,
        int(age_bars),
    )

    if age == 0:
        return 1.00

    if age == 1:
        return 0.55

    if age == 2:
        return 0.35

    if age == 3:
        return 0.20

    if age == 4:
        return 0.10

    return 0.05


def _pattern_age(
    location: int,
    last_location: int,
) -> int:
    return max(
        0,
        int(last_location) - int(location),
    )


# ---------------------------------------------------------------------------
# Pattern metadata
# ---------------------------------------------------------------------------
def _mk(
    name: str,
    cls: str,
    confidence: int,
    explanation: str,
    target=None,
    location: Optional[int] = None,
    confirmed: bool = True,
) -> Dict:
    base = int(
        max(
            1,
            min(
                100,
                confidence,
            ),
        )
    )

    return {
        "name": name,
        "classification": cls,
        "confidence": base,
        "base_confidence": base,
        "explanation": explanation,
        "implied_target": target,
        "location": (
            int(location)
            if location is not None
            else 0
        ),
        "confirmed": bool(
            confirmed
        ),
    }


def _apply_recency(
    patterns: List[Dict],
    last_location: int,
) -> List[Dict]:
    """Apply pattern-age metadata and confidence decay."""
    result: List[Dict] = []

    for pattern in patterns:
        location = int(
            pattern.get(
                "location",
                last_location,
            )
        )

        age_bars = _pattern_age(
            location,
            last_location,
        )

        multiplier = _recency_multiplier(
            age_bars
        )

        adjusted = round(
            pattern[
                "base_confidence"
            ]
            * multiplier
        )

        item = dict(
            pattern
        )

        item["age_bars"] = int(
            age_bars
        )

        item["recency_multiplier"] = (
            multiplier
        )

        item["confidence"] = int(
            max(
                1,
                min(
                    100,
                    adjusted,
                ),
            )
        )

        result.append(
            item
        )

    return result


# ---------------------------------------------------------------------------
# Confirmation helpers
# ---------------------------------------------------------------------------
def _pivot_pattern_location(
    pivot_indices: List[int],
) -> int:
    """Use the latest structural pivot as pattern location."""
    if not pivot_indices:
        return 0

    return max(
        pivot_indices
    )


def _is_pivot_confirmed(
    location: int,
    last_location: int,
) -> bool:
    """Pivot-based patterns are confirmed because pivots require right bars.

    The detector uses right=3, so a pivot could not have been returned unless
    those confirmation bars already existed.
    """
    return (
        location
        <= last_location - 3
    )


def _breakout_confirmed(
    direction: str,
    closes: List[float],
    range_high: float,
    range_low: float,
) -> bool:
    """Check whether the current range break survived another closed candle.

    The last candle creates the breakout itself; without a subsequent closed
    candle, the breakout remains unconfirmed.

    This helper is kept explicit so later retest logic can replace it without
    changing the pattern schema.
    """
    if len(closes) < 2:
        return False

    current = closes[-1]
    previous = closes[-2]

    if direction == "bullish":
        return (
            current >= range_high
            and previous < range_high
        )

    if direction == "bearish":
        return (
            current <= range_low
            and previous > range_low
        )

    return False


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------
def detect(
    candles: List[dict],
) -> List[Dict]:
    try:
        return _detect(
            candles
        )

    except Exception:
        return []


def _detect(
    candles: List[dict],
) -> List[Dict]:
    if len(candles) < 40:
        return []

    highs = [
        c["high"]
        for c in candles
    ]

    lows = [
        c["low"]
        for c in candles
    ]

    closes = [
        c["close"]
        for c in candles
    ]

    price = closes[-1]

    last_location = (
        len(candles) - 1
    )

    hi_piv, lo_piv = _pivots(
        highs,
        lows,
    )

    out: List[Dict] = []

    recent_hi = hi_piv[-5:]
    recent_lo = lo_piv[-5:]

    # -----------------------------------------------------------------------
    # Double Top
    # -----------------------------------------------------------------------
    if len(recent_hi) >= 2:
        a, b = recent_hi[-2:]

        if (
            abs(a[1] - b[1])
            / b[1]
            < 0.02
            and price
            < min(
                a[1],
                b[1],
            )
        ):
            location = _pivot_pattern_location(
                [
                    a[0],
                    b[0],
                ]
            )

            out.append(
                _mk(
                    "Double Top",
                    "bearish",
                    62,
                    "Two swing highs at a similar level with price rolling over — bearish reversal signal.",
                    target=round(
                        price
                        - (
                            max(
                                a[1],
                                b[1],
                            )
                            - price
                        ),
                        4,
                    ),
                    location=location,
                    confirmed=_is_pivot_confirmed(
                        location,
                        last_location,
                    ),
                )
            )

    # -----------------------------------------------------------------------
    # Double Bottom
    # -----------------------------------------------------------------------
    if len(recent_lo) >= 2:
        a, b = recent_lo[-2:]

        if (
            abs(a[1] - b[1])
            / b[1]
            < 0.02
            and price
            > max(
                a[1],
                b[1],
            )
        ):
            location = _pivot_pattern_location(
                [
                    a[0],
                    b[0],
                ]
            )

            out.append(
                _mk(
                    "Double Bottom",
                    "bullish",
                    62,
                    "Two swing lows at a similar level with price recovering — bullish reversal signal.",
                    target=round(
                        price
                        + (
                            price
                            - min(
                                a[1],
                                b[1],
                            )
                        ),
                        4,
                    ),
                    location=location,
                    confirmed=_is_pivot_confirmed(
                        location,
                        last_location,
                    ),
                )
            )

    # -----------------------------------------------------------------------
    # Head and Shoulders
    # -----------------------------------------------------------------------
    if len(recent_hi) >= 3:
        left, head, right = (
            recent_hi[-3],
            recent_hi[-2],
            recent_hi[-1],
        )

        l = left[1]
        h = head[1]
        r = right[1]

        if (
            h > l
            and h > r
            and abs(
                l - r
            )
            / h
            < 0.03
        ):
            location = _pivot_pattern_location(
                [
                    left[0],
                    head[0],
                    right[0],
                ]
            )

            out.append(
                _mk(
                    "Head and Shoulders",
                    "bearish",
                    58,
                    "Central peak (head) higher than two similar peaks (shoulders) — classic bearish reversal.",
                    location=location,
                    confirmed=_is_pivot_confirmed(
                        location,
                        last_location,
                    ),
                )
            )

    # -----------------------------------------------------------------------
    # Inverse Head and Shoulders
    # -----------------------------------------------------------------------
    if len(recent_lo) >= 3:
        left, head, right = (
            recent_lo[-3],
            recent_lo[-2],
            recent_lo[-1],
        )

        l = left[1]
        h = head[1]
        r = right[1]

        if (
            h < l
            and h < r
            and abs(
                l - r
            )
            / (
                h or 1
            )
            < 0.03
        ):
            location = _pivot_pattern_location(
                [
                    left[0],
                    head[0],
                    right[0],
                ]
            )

            out.append(
                _mk(
                    "Inverse Head and Shoulders",
                    "bullish",
                    58,
                    "Central trough (head) lower than two similar troughs — classic bullish reversal.",
                    location=location,
                    confirmed=_is_pivot_confirmed(
                        location,
                        last_location,
                    ),
                )
            )

    # -----------------------------------------------------------------------
    # Trendline-based patterns
    # -----------------------------------------------------------------------
    if (
        len(recent_hi) >= 3
        and len(recent_lo) >= 3
    ):
        hs = _slope(
            recent_hi
        )

        ls = _slope(
            recent_lo
        )

        hs_n = (
            hs / price
            if price
            else 0.0
        )

        ls_n = (
            ls / price
            if price
            else 0.0
        )

        flat = 0.0008

        location = _pivot_pattern_location(
            [
                p[0]
                for p in (
                    recent_hi[-3:]
                    + recent_lo[-3:]
                )
            ]
        )

        confirmed = _is_pivot_confirmed(
            location,
            last_location,
        )

        if (
            abs(hs_n) < flat
            and ls_n > flat
        ):
            out.append(
                _mk(
                    "Ascending Triangle",
                    "bullish",
                    55,
                    "Flat resistance with rising support — buyers stepping up, bullish bias.",
                    location=location,
                    confirmed=confirmed,
                )
            )

        elif (
            hs_n < -flat
            and abs(ls_n) < flat
        ):
            out.append(
                _mk(
                    "Descending Triangle",
                    "bearish",
                    55,
                    "Falling resistance with flat support — sellers pressing, bearish bias.",
                    location=location,
                    confirmed=confirmed,
                )
            )

        elif (
            hs_n < -flat
            and ls_n > flat
        ):
            out.append(
                _mk(
                    "Symmetrical Triangle",
                    "neutral",
                    45,
                    "Converging trendlines — a breakout is pending; direction unconfirmed.",
                    location=location,
                    confirmed=confirmed,
                )
            )

        elif (
            hs_n > flat
            and ls_n > flat
            and ls_n > hs_n
        ):
            out.append(
                _mk(
                    "Rising Wedge",
                    "bearish",
                    50,
                    "Both trendlines rising but converging — often resolves bearish.",
                    location=location,
                    confirmed=confirmed,
                )
            )

        elif (
            hs_n < -flat
            and ls_n < -flat
            and hs_n > ls_n
        ):
            out.append(
                _mk(
                    "Falling Wedge",
                    "bullish",
                    50,
                    "Both trendlines falling but converging — often resolves bullish.",
                    location=location,
                    confirmed=confirmed,
                )
            )

        elif (
            abs(
                hs_n - ls_n
            ) < flat
            and abs(hs_n) > flat
        ):
            direction = (
                "bullish"
                if hs_n > 0
                else "bearish"
            )

            out.append(
                _mk(
                    "Channel",
                    direction,
                    45,
                    "Parallel trendlines — price trending inside a channel.",
                    location=location,
                    confirmed=confirmed,
                )
            )

        elif (
            abs(hs_n) < flat
            and abs(ls_n) < flat
        ):
            out.append(
                _mk(
                    "Rectangle",
                    "neutral",
                    40,
                    "Horizontal support and resistance — ranging / accumulation.",
                    location=location,
                    confirmed=confirmed,
                )
            )

    # -----------------------------------------------------------------------
    # Breakout / Breakdown / Retest vs recent range
    # -----------------------------------------------------------------------
    window = closes[-30:]

    hi_range = max(
        highs[-30:]
    )

    lo_range = min(
        lows[-30:]
    )

    rng = (
        hi_range
        - lo_range
    )

    if rng > 0:
        bullish_breakout = (
            price
            >= hi_range - rng * 0.02
            and closes[-2]
            < hi_range - rng * 0.05
        )

        if bullish_breakout:
            confirmed = _breakout_confirmed(
                "bullish",
                closes,
                hi_range,
                lo_range,
            )

            out.append(
                _mk(
                    "Breakout",
                    "bullish",
                    55,
                    "Price pushing above the recent range high — bullish breakout, watch for a retest.",
                    location=last_location,
                    confirmed=confirmed,
                )
            )

        bearish_breakdown = (
            price
            <= lo_range + rng * 0.02
            and closes[-2]
            > lo_range + rng * 0.05
        )

        if bearish_breakdown:
            confirmed = _breakout_confirmed(
                "bearish",
                closes,
                hi_range,
                lo_range,
            )

            out.append(
                _mk(
                    "Breakdown",
                    "bearish",
                    55,
                    "Price slipping below the recent range low — bearish breakdown, watch for a retest.",
                    location=last_location,
                    confirmed=confirmed,
                )
            )

    # -----------------------------------------------------------------------
    # Dedupe by pattern name.
    # Keep highest base confidence, then most recent location.
    # -----------------------------------------------------------------------
    seen: Dict[
        str,
        Dict,
    ] = {}

    for pattern in out:
        name = pattern["name"]

        current = seen.get(
            name
        )

        if current is None:
            seen[name] = pattern
            continue

        if (
            pattern["base_confidence"]
            > current["base_confidence"]
        ):
            seen[name] = pattern
            continue

        if (
            pattern["base_confidence"]
            == current["base_confidence"]
            and pattern["location"]
            > current["location"]
        ):
            seen[name] = pattern

    deduped = list(
        seen.values()
    )

    # Apply recency after deduplication.
    adjusted = _apply_recency(
        deduped,
        last_location=last_location,
    )

    # Most recent first, then adjusted confidence.
    return sorted(
        adjusted,
        key=lambda pattern: (
            -pattern["location"],
            -pattern["confidence"],
        ),
    )[:6]