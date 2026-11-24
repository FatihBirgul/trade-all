"""Candlestick pattern detection engine.

Detects common candlestick structures from recent closed OHLCV candles.

The detector keeps the original pattern set and applies three safeguards:

1. Older patterns receive progressively smaller effective strength.
2. Multiple directional patterns detected on the same candle are reduced to
   the strongest one.
3. Patterns are annotated with `age_bars` and `confirmed` so the V2
   Evidence/Confluence layer can distinguish fresh confirmed evidence from
   stale or unconfirmed evidence.

The returned `strength` is the time-adjusted strength used by the aggregation
engine. `base_strength` preserves the original pattern strength.
"""
from __future__ import annotations

from typing import Dict, List


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(h - l, 1e-9)


def _trend_at(
    closes: List[float],
    idx: int,
    look: int = 10,
) -> str:
    start = max(0, idx - look)
    seg = closes[start : idx + 1]

    if len(seg) < 3:
        return "flat"

    if seg[-1] > seg[0] * 1.01:
        return "up"

    if seg[-1] < seg[0] * 0.99:
        return "down"

    return "flat"


def _mk(
    name: str,
    cls: str,
    idx: int,
    strength: int,
    context: str,
    explanation: str,
) -> Dict:
    return {
        "name": name,
        "classification": cls,
        "location": int(idx),
        "strength": int(
            max(
                1,
                min(100, strength),
            )
        ),
        "base_strength": int(
            max(
                1,
                min(100, strength),
            )
        ),
        "context": context,
        "explanation": explanation,
    }


def _recency_multiplier(
    location: int,
    last_location: int,
) -> float:
    """Give newer patterns more influence than older patterns.

    0 candles old  -> 1.00
    1 candle old   -> 0.55
    2 candles old  -> 0.35
    3 candles old  -> 0.20
    4 candles old  -> 0.10
    5+ candles old -> 0.05
    """
    age = max(
        0,
        last_location - location,
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
    """Return pattern age measured in closed signal candles."""
    return max(
        0,
        last_location - location,
    )


def _is_confirmed(
    pattern: Dict,
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> bool:
    """Determine whether the next closed candle confirms the pattern.

    Confirmation rules are intentionally conservative but generic:

    - Bullish pattern:
        next candle must close above the pattern candle close AND finish
        bullish.

    - Bearish pattern:
        next candle must close below the pattern candle close AND finish
        bearish.

    - Neutral pattern:
        confirmation is considered true once a subsequent closed candle
        exists because neutral patterns are context rather than directional
        trade evidence.

    - The latest candle cannot be confirmed yet because there is no later
      closed candle to validate it.
    """
    location = int(
        pattern["location"]
    )

    next_index = location + 1

    if next_index >= len(closes):
        return False

    classification = pattern.get(
        "classification"
    )

    pattern_close = float(
        closes[location]
    )

    next_open = float(
        opens[next_index]
    )

    next_close = float(
        closes[next_index]
    )

    if classification == "bullish":
        return (
            next_close > pattern_close
            and next_close > next_open
        )

    if classification == "bearish":
        return (
            next_close < pattern_close
            and next_close < next_open
        )

    return True


def _apply_recency_and_confirmation(
    patterns: List[Dict],
    last_location: int,
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
) -> List[Dict]:
    """Add age/confirmation metadata and recency-adjusted strength."""
    result: List[Dict] = []

    for pattern in patterns:
        location = int(
            pattern["location"]
        )

        age_bars = _pattern_age(
            location,
            last_location,
        )

        multiplier = _recency_multiplier(
            location,
            last_location,
        )

        confirmed = _is_confirmed(
            pattern,
            opens,
            highs,
            lows,
            closes,
        )

        adjusted = round(
            pattern["base_strength"]
            * multiplier
        )

        item = dict(
            pattern
        )

        item["age_bars"] = int(
            age_bars
        )

        item["confirmed"] = bool(
            confirmed
        )

        item["recency_multiplier"] = (
            multiplier
        )

        item["strength"] = int(
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


def _resolve_same_candle_conflicts(
    patterns: List[Dict],
) -> List[Dict]:
    """Keep at most one directional pattern per candle.

    Neutral patterns are retained only when there is no directional pattern on
    that candle. This prevents one candle from contributing multiple
    directional scores while preserving useful neutral context.
    """
    by_location: Dict[
        int,
        List[Dict],
    ] = {}

    for pattern in patterns:
        by_location.setdefault(
            pattern["location"],
            [],
        ).append(pattern)

    result: List[Dict] = []

    for location in sorted(
        by_location.keys(),
        reverse=True,
    ):
        group = by_location[
            location
        ]

        directional = [
            pattern
            for pattern in group
            if pattern["classification"]
            in (
                "bullish",
                "bearish",
            )
        ]

        if directional:
            # Prefer confirmed evidence first.
            strongest = max(
                directional,
                key=lambda pattern: (
                    int(
                        pattern.get(
                            "confirmed",
                            False,
                        )
                    ),
                    pattern["strength"],
                    pattern["base_strength"],
                ),
            )

            result.append(
                strongest
            )

        else:
            strongest_neutral = max(
                group,
                key=lambda pattern: (
                    int(
                        pattern.get(
                            "confirmed",
                            False,
                        )
                    ),
                    pattern["strength"],
                    pattern["base_strength"],
                ),
            )

            result.append(
                strongest_neutral
            )

    return result


def detect(
    candles: List[dict],
) -> List[Dict]:
    if len(candles) < 5:
        return []

    o = [
        c["open"]
        for c in candles
    ]

    h = [
        c["high"]
        for c in candles
    ]

    l = [
        c["low"]
        for c in candles
    ]

    c = [
        c["close"]
        for c in candles
    ]

    out: List[Dict] = []

    n = len(candles)

    # Analyze only the most recent six closed candles.
    scan_from = max(
        2,
        n - 6,
    )

    for i in range(
        scan_from,
        n,
    ):
        body = _body(
            o[i],
            c[i],
        )

        rng = _range(
            h[i],
            l[i],
        )

        upper = (
            h[i]
            - max(
                o[i],
                c[i],
            )
        )

        lower = (
            min(
                o[i],
                c[i],
            )
            - l[i]
        )

        bull = c[i] > o[i]

        trend = _trend_at(
            c,
            i,
        )

        body_ratio = (
            body / rng
        )

        # ---------------------------------------------------------------
        # Doji family
        # ---------------------------------------------------------------
        if body_ratio < 0.1:
            if (
                upper > rng * 0.4
                and lower > rng * 0.4
            ):
                out.append(
                    _mk(
                        "Long-legged Doji",
                        "neutral",
                        i,
                        40,
                        f"Trend: {trend}",
                        "Open and close nearly equal with long wicks both sides — strong indecision.",
                    )
                )

            elif (
                lower > rng * 0.6
                and upper < rng * 0.15
            ):
                out.append(
                    _mk(
                        "Dragonfly Doji",
                        (
                            "bullish"
                            if trend == "down"
                            else "neutral"
                        ),
                        i,
                        55,
                        f"Trend: {trend}",
                        "Long lower wick with open/close near the high — potential bullish reversal after a decline.",
                    )
                )

            elif (
                upper > rng * 0.6
                and lower < rng * 0.15
            ):
                out.append(
                    _mk(
                        "Gravestone Doji",
                        (
                            "bearish"
                            if trend == "up"
                            else "neutral"
                        ),
                        i,
                        55,
                        f"Trend: {trend}",
                        "Long upper wick with open/close near the low — potential bearish reversal after a rally.",
                    )
                )

            else:
                out.append(
                    _mk(
                        "Doji",
                        "neutral",
                        i,
                        35,
                        f"Trend: {trend}",
                        "Open equals close — market indecision.",
                    )
                )

            continue

        # ---------------------------------------------------------------
        # Marubozu
        # ---------------------------------------------------------------
        if body_ratio > 0.92:
            out.append(
                _mk(
                    "Marubozu",
                    (
                        "bullish"
                        if bull
                        else "bearish"
                    ),
                    i,
                    70,
                    f"Trend: {trend}",
                    "Full-bodied candle with negligible wicks — strong conviction in the direction of the close.",
                )
            )

            continue

        # ---------------------------------------------------------------
        # Spinning Top
        # ---------------------------------------------------------------
        if (
            body_ratio < 0.35
            and upper > rng * 0.25
            and lower > rng * 0.25
        ):
            out.append(
                _mk(
                    "Spinning Top",
                    "neutral",
                    i,
                    30,
                    f"Trend: {trend}",
                    "Small body between two wicks — indecision / possible pause.",
                )
            )

        # ---------------------------------------------------------------
        # Hammer / Hanging Man
        # ---------------------------------------------------------------
        if (
            lower > body * 2
            and upper < body
            and body_ratio < 0.4
        ):
            if trend == "down":
                out.append(
                    _mk(
                        "Hammer",
                        "bullish",
                        i,
                        65,
                        "After a decline",
                        "Long lower wick rejecting lower prices after a downtrend — bullish reversal signal.",
                    )
                )

            elif trend == "up":
                out.append(
                    _mk(
                        "Hanging Man",
                        "bearish",
                        i,
                        60,
                        "After a rally",
                        "Long lower wick after an uptrend — potential bearish reversal, needs confirmation.",
                    )
                )

        # ---------------------------------------------------------------
        # Inverted Hammer / Shooting Star
        # ---------------------------------------------------------------
        if (
            upper > body * 2
            and lower < body
            and body_ratio < 0.4
        ):
            if trend == "down":
                out.append(
                    _mk(
                        "Inverted Hammer",
                        "bullish",
                        i,
                        55,
                        "After a decline",
                        "Long upper wick after a downtrend — potential bullish reversal, needs confirmation.",
                    )
                )

            elif trend == "up":
                out.append(
                    _mk(
                        "Shooting Star",
                        "bearish",
                        i,
                        65,
                        "After a rally",
                        "Long upper wick rejecting higher prices after an uptrend — bearish reversal signal.",
                    )
                )

        # ---------------------------------------------------------------
        # Two-candle patterns
        # ---------------------------------------------------------------
        if i >= 1:
            po = o[i - 1]
            pc = c[i - 1]
            ph = h[i - 1]
            pl = l[i - 1]

            pbull = pc > po

            prev_body = _body(
                po,
                pc,
            )

            # Engulfing
            if (
                bull
                and not pbull
                and c[i] >= po
                and o[i] <= pc
                and body > prev_body
            ):
                out.append(
                    _mk(
                        "Bullish Engulfing",
                        "bullish",
                        i,
                        75,
                        f"Trend: {trend}",
                        "Current bullish body fully engulfs the previous bearish body — strong bullish reversal.",
                    )
                )

            if (
                not bull
                and pbull
                and o[i] >= pc
                and c[i] <= po
                and body > prev_body
            ):
                out.append(
                    _mk(
                        "Bearish Engulfing",
                        "bearish",
                        i,
                        75,
                        f"Trend: {trend}",
                        "Current bearish body fully engulfs the previous bullish body — strong bearish reversal.",
                    )
                )

            # Harami
            if (
                pbull
                and not bull
                and o[i] < pc
                and c[i] > po
                and body < prev_body
            ):
                out.append(
                    _mk(
                        "Bearish Harami",
                        "bearish",
                        i,
                        50,
                        f"Trend: {trend}",
                        "Small bearish candle inside prior bullish body — momentum stalling.",
                    )
                )

            if (
                not pbull
                and bull
                and o[i] > pc
                and c[i] < po
                and body < prev_body
            ):
                out.append(
                    _mk(
                        "Bullish Harami",
                        "bullish",
                        i,
                        50,
                        f"Trend: {trend}",
                        "Small bullish candle inside prior bearish body — momentum stalling.",
                    )
                )

            # Piercing / Dark Cloud
            mid_prev = (
                po + pc
            ) / 2

            if (
                not pbull
                and bull
                and o[i] < pl * 1.001
                and c[i] > mid_prev
                and c[i] < po
            ):
                out.append(
                    _mk(
                        "Piercing Line",
                        "bullish",
                        i,
                        60,
                        "After a decline",
                        "Opens near/below the prior low and closes above the midpoint of the prior bearish candle.",
                    )
                )

            if (
                pbull
                and not bull
                and o[i] > ph * 0.999
                and c[i] < mid_prev
                and c[i] > po
            ):
                out.append(
                    _mk(
                        "Dark Cloud Cover",
                        "bearish",
                        i,
                        60,
                        "After a rally",
                        "Opens near/above the prior high and closes below the midpoint of the prior bullish candle.",
                    )
                )

            # Tweezers
            current_range = _range(
                h[i],
                l[i],
            )

            if (
                abs(
                    h[i] - ph
                )
                / current_range
                < 0.001
                and trend == "up"
            ):
                out.append(
                    _mk(
                        "Tweezer Top",
                        "bearish",
                        i,
                        45,
                        "After a rally",
                        "Two candles with matching highs — resistance rejection.",
                    )
                )

            if (
                abs(
                    l[i] - pl
                )
                / current_range
                < 0.001
                and trend == "down"
            ):
                out.append(
                    _mk(
                        "Tweezer Bottom",
                        "bullish",
                        i,
                        45,
                        "After a decline",
                        "Two candles with matching lows — support hold.",
                    )
                )

            # Inside / Outside bar
            if (
                h[i] < ph
                and l[i] > pl
            ):
                out.append(
                    _mk(
                        "Inside Bar",
                        "neutral",
                        i,
                        30,
                        f"Trend: {trend}",
                        "Range contained within the prior candle — consolidation / breakout pending.",
                    )
                )

            if (
                h[i] > ph
                and l[i] < pl
            ):
                out.append(
                    _mk(
                        "Outside Bar",
                        (
                            "bullish"
                            if bull
                            else "bearish"
                        ),
                        i,
                        40,
                        f"Trend: {trend}",
                        "Range engulfs the prior candle — volatility expansion.",
                    )
                )

        # ---------------------------------------------------------------
        # Three-candle patterns
        # ---------------------------------------------------------------
        if i >= 2:
            o1 = o[i - 2]
            c1 = c[i - 2]

            o2 = o[i - 1]
            c2 = c[i - 1]

            b1 = c1 > o1
            b2 = c2 > o2

            small_mid = (
                _body(
                    o2,
                    c2,
                )
                < _body(
                    o1,
                    c1,
                )
                * 0.5
            )

            if (
                b1 is False
                and small_mid
                and bull
                and c[i]
                > (o1 + c1) / 2
            ):
                out.append(
                    _mk(
                        "Morning Star",
                        "bullish",
                        i,
                        80,
                        "After a decline",
                        "Bearish candle, small-bodied indecision, then a strong bullish candle — bullish reversal.",
                    )
                )

            if (
                b1 is True
                and small_mid
                and not bull
                and c[i]
                < (o1 + c1) / 2
            ):
                out.append(
                    _mk(
                        "Evening Star",
                        "bearish",
                        i,
                        80,
                        "After a rally",
                        "Bullish candle, small-bodied indecision, then a strong bearish candle — bearish reversal.",
                    )
                )

            if (
                b1
                and b2
                and bull
                and c[i] > c2 > c1
                and o2 > o1
                and o[i] > o2
            ):
                out.append(
                    _mk(
                        "Three White Soldiers",
                        "bullish",
                        i,
                        78,
                        f"Trend: {trend}",
                        "Three consecutive strong bullish candles — sustained buying pressure.",
                    )
                )

            if (
                not b1
                and not b2
                and not bull
                and c[i] < c2 < c1
                and o2 < o1
                and o[i] < o2
            ):
                out.append(
                    _mk(
                        "Three Black Crows",
                        "bearish",
                        i,
                        78,
                        f"Trend: {trend}",
                        "Three consecutive strong bearish candles — sustained selling pressure.",
                    )
                )

    # -----------------------------------------------------------------------
    # Remove duplicate pattern name + candle combinations.
    # -----------------------------------------------------------------------
    seen: Dict[
        tuple,
        Dict,
    ] = {}

    for pattern in out:
        key = (
            pattern["name"],
            pattern["location"],
        )

        if (
            key not in seen
            or pattern["base_strength"]
            > seen[key]["base_strength"]
        ):
            seen[key] = pattern

    deduped = list(
        seen.values()
    )

    # -----------------------------------------------------------------------
    # Add age + confirmation metadata and apply recency.
    #
    # These values are available to the future Evidence/Confluence layer.
    # -----------------------------------------------------------------------
    adjusted = _apply_recency_and_confirmation(
        deduped,
        last_location=n - 1,
        opens=o,
        highs=h,
        lows=l,
        closes=c,
    )

    # -----------------------------------------------------------------------
    # One directional winner per candle.
    # -----------------------------------------------------------------------
    resolved = _resolve_same_candle_conflicts(
        adjusted
    )

    # -----------------------------------------------------------------------
    # Most recent first, then strongest.
    # -----------------------------------------------------------------------
    result = sorted(
        resolved,
        key=lambda pattern: (
            -pattern["location"],
            -pattern["strength"],
        ),
    )

    return result[:8]