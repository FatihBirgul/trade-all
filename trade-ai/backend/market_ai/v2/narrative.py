"""Safe scenario prose for V2 and V1 fallback compatibility.

Never interpolate missing/invalid trade levels as 'None', 'nan', or 'inf'.
Directional scenario text requires fully valid stop/entry/target geometry.
"""
from __future__ import annotations

from math import isfinite
from typing import Mapping


def _price(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if isfinite(number) and number > 0 else None


def build_safe_scenarios(direction: str, zones: Mapping[str, object] | None) -> dict[str, str]:
    zones = zones or {}
    levels = {
        name: _price(zones.get(name))
        for name in ("invalidation", "entry_low", "entry_high", "target_1", "target_2")
    }
    invalid, low, high, t1, t2 = (
        levels[key] for key in ("invalidation", "entry_low", "entry_high", "target_1", "target_2")
    )

    scenarios = {
        "bullish": "No validated bullish setup is available; wait for confirmed levels.",
        "bearish": "No validated bearish setup is available; wait for confirmed levels.",
        "neutral": "Wait for a confirmed break or a better-defined setup; no executable trade is implied.",
    }
    if any(value is None for value in levels.values()):
        return scenarios

    if direction == "bullish" and invalid < low <= high < t1 < t2:
        scenarios["bullish"] = (
            f"If price holds above {low:g} and clears {t1:g}, "
            f"upside may extend toward {t2:g}. A move below {invalid:g} "
            "would invalidate this bullish setup."
        )
    elif direction == "bearish" and t2 < t1 < low <= high < invalid:
        scenarios["bearish"] = (
            f"If price breaks below {low:g}, downside may extend toward "
            f"{t1:g} then {t2:g}. A move above {invalid:g} "
            "would invalidate this bearish setup."
        )
    return scenarios
