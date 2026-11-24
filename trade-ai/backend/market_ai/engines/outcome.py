"""Outcome tracking engine.

Evaluates a completed analysis against REAL price action that occurred after
it was created.

The engine answers:
Did Target 1 get hit before the Invalidation level?

If both Target 1 and Invalidation are touched inside the same evaluation
candle, the result is marked as `ambiguous` because OHLC data alone cannot
reliably establish which level was touched first.

Neutral analyses are not scored.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional


def created_at_ms(created_at: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(created_at)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return int(dt.timestamp() * 1000)

    except Exception:
        return None


def evaluate(
    analysis: Dict,
    candles: List[dict],
) -> Dict:
    """Evaluate an analysis against real candles after its creation."""
    direction = analysis.get("direction")
    zones = analysis.get("zones") or {}

    target = zones.get("target_1")
    invalid = zones.get("invalidation")

    checked_at = datetime.now(
        timezone.utc
    ).isoformat()

    if direction not in ("bullish", "bearish"):
        return {
            "status": "neutral",
            "note": "No directional call — not scored.",
            "checked_at": checked_at,
        }

    if target is None or invalid is None:
        return {
            "status": "unresolvable",
            "note": "Missing target/invalidation.",
            "checked_at": checked_at,
        }

    if not candles:
        return {
            "status": "pending",
            "note": "No price action yet since analysis.",
            "checked_at": checked_at,
        }

    for i, candle in enumerate(candles):
        hi = float(candle["high"])
        lo = float(candle["low"])

        if direction == "bullish":
            hit_target = hi >= target
            hit_invalid = lo <= invalid
        else:
            hit_target = lo <= target
            hit_invalid = hi >= invalid

        resolved_at = datetime.fromtimestamp(
            candle["time"] / 1000,
            tz=timezone.utc,
        ).isoformat()

        if hit_target and hit_invalid:
            return {
                "status": "ambiguous",
                "resolved_at": resolved_at,
                "bars_to_resolve": i + 1,
                "note": (
                    "Target and invalidation were both touched in the same "
                    "evaluation candle. OHLC data cannot determine which "
                    "level was reached first."
                ),
                "checked_at": checked_at,
            }

        if hit_target:
            return {
                "status": "win",
                "resolved_at": resolved_at,
                "resolved_price": target,
                "bars_to_resolve": i + 1,
                "note": "Target 1 reached before invalidation.",
                "checked_at": checked_at,
            }

        if hit_invalid:
            return {
                "status": "loss",
                "resolved_at": resolved_at,
                "resolved_price": invalid,
                "bars_to_resolve": i + 1,
                "note": "Invalidation reached before Target 1.",
                "checked_at": checked_at,
            }

    return {
        "status": "pending",
        "note": "Neither target nor invalidation reached yet.",
        "checked_at": checked_at,
    }


def summarize(outcomes: List[Dict]) -> Dict:
    """Aggregate outcomes into a performance summary."""
    wins = sum(
        1
        for o in outcomes
        if o.get("status") == "win"
    )

    losses = sum(
        1
        for o in outcomes
        if o.get("status") == "loss"
    )

    pending = sum(
        1
        for o in outcomes
        if o.get("status") == "pending"
    )

    ambiguous = sum(
        1
        for o in outcomes
        if o.get("status") == "ambiguous"
    )

    neutral = sum(
        1
        for o in outcomes
        if o.get("status")
        in ("neutral", "unresolvable")
    )

    resolved = wins + losses

    hit_rate = (
        round((wins / resolved) * 100, 1)
        if resolved
        else None
    )

    return {
        "total": len(outcomes),
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "ambiguous": ambiguous,
        "neutral": neutral,
        "resolved": resolved,
        "hit_rate": hit_rate,
        "note": (
            "Hit-rate = Target 1 reached before invalidation, measured on "
            "real price action. Ambiguous outcomes are excluded from the "
            "win/loss denominator because candle OHLC does not reveal "
            "intrabar ordering. Small samples are not statistically "
            "meaningful and this is not a guarantee of future results."
        ),
    }