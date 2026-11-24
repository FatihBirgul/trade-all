"""Outcome tracking engine.

Evaluates a completed analysis against REAL price action that occurred *after*
it was created. It answers a single honest question: did Target 1 get hit before
the Invalidation level? This is the foundation for measuring the app's own
historical hit-rate instead of claiming an arbitrary accuracy number.

Neutral analyses (no directional call) are not scored. Everything is derived
from real Binance candles — nothing is fabricated.
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


def evaluate(analysis: Dict, candles: List[dict]) -> Dict:
    """Return an outcome dict. `candles` are real candles AFTER the analysis time."""
    direction = analysis.get("direction")
    zones = analysis.get("zones") or {}
    target = zones.get("target_1")
    invalid = zones.get("invalidation")
    checked_at = datetime.now(timezone.utc).isoformat()

    if direction not in ("bullish", "bearish"):
        return {"status": "neutral", "note": "No directional call — not scored.", "checked_at": checked_at}

    if target is None or invalid is None:
        return {"status": "unresolvable", "note": "Missing target/invalidation.", "checked_at": checked_at}

    if not candles:
        return {"status": "pending", "note": "No price action yet since analysis.", "checked_at": checked_at}

    for i, c in enumerate(candles):
        hi, lo = c["high"], c["low"]
        if direction == "bullish":
            hit_target = hi >= target
            hit_invalid = lo <= invalid
        else:  # bearish
            hit_target = lo <= target
            hit_invalid = hi >= invalid

        if hit_target and hit_invalid:
            # Both in the same candle — be conservative and count as a loss.
            return {
                "status": "loss",
                "resolved_at": datetime.fromtimestamp(c["time"] / 1000, tz=timezone.utc).isoformat(),
                "resolved_price": invalid,
                "bars_to_resolve": i + 1,
                "note": "Target and invalidation both touched in one candle — counted conservatively as a loss.",
                "checked_at": checked_at,
            }
        if hit_target:
            return {
                "status": "win",
                "resolved_at": datetime.fromtimestamp(c["time"] / 1000, tz=timezone.utc).isoformat(),
                "resolved_price": target,
                "bars_to_resolve": i + 1,
                "note": "Target 1 reached before invalidation.",
                "checked_at": checked_at,
            }
        if hit_invalid:
            return {
                "status": "loss",
                "resolved_at": datetime.fromtimestamp(c["time"] / 1000, tz=timezone.utc).isoformat(),
                "resolved_price": invalid,
                "bars_to_resolve": i + 1,
                "note": "Invalidation reached before Target 1.",
                "checked_at": checked_at,
            }

    return {"status": "pending", "note": "Neither target nor invalidation reached yet.", "checked_at": checked_at}


def summarize(outcomes: List[Dict]) -> Dict:
    """Aggregate a list of outcome dicts into a performance summary."""
    wins = sum(1 for o in outcomes if o.get("status") == "win")
    losses = sum(1 for o in outcomes if o.get("status") == "loss")
    pending = sum(1 for o in outcomes if o.get("status") == "pending")
    neutral = sum(1 for o in outcomes if o.get("status") in ("neutral", "unresolvable"))
    resolved = wins + losses
    hit_rate = round((wins / resolved) * 100, 1) if resolved else None
    return {
        "total": len(outcomes),
        "wins": wins,
        "losses": losses,
        "pending": pending,
        "neutral": neutral,
        "resolved": resolved,
        "hit_rate": hit_rate,
        "note": (
            "Hit-rate = Target 1 reached before invalidation, measured on real price action. "
            "Small samples are not statistically meaningful and this is not a guarantee of future results."
        ),
    }
