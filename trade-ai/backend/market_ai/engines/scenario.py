"""Deterministic, display-safe trade scenario construction.

Scenario text is explanatory only. It never creates a trading setup: a
trigger, invalidation and targets are described only when the supplied zones
are finite and obey the executable geometry contract.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Dict, Optional


SCENARIO_DIRECTIONS = (
    "bullish",
    "bearish",
    "neutral",
)

_UNSAFE_TEXT = re.compile(
    r"\b(?:none|undefined|nan|infinity)\b",
    re.IGNORECASE,
)


def _finite_number(
    value,
) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return None

    return number if math.isfinite(number) and number > 0 else None


def _validated_levels(
    direction: str,
    zones: Optional[Dict],
) -> Optional[Dict[str, float]]:
    raw_zones = (
        zones
        if isinstance(
            zones,
            Mapping,
        )
        else {}
    )

    levels = {
        key: _finite_number(
            raw_zones.get(key)
        )
        for key in (
            "entry_low",
            "entry_high",
            "target_1",
            "target_2",
            "invalidation",
        )
    }

    if any(
        value is None
        for value in levels.values()
    ):
        return None

    entry_low = levels["entry_low"]
    entry_high = levels["entry_high"]
    target_1 = levels["target_1"]
    target_2 = levels["target_2"]
    invalidation = levels["invalidation"]

    bullish_valid = (
        invalidation
        < entry_low
        <= entry_high
        < target_1
        < target_2
    )

    bearish_valid = (
        target_2
        < target_1
        < entry_low
        <= entry_high
        < invalidation
    )

    if (
        direction == "bullish"
        and bullish_valid
    ):
        return levels

    if (
        direction == "bearish"
        and bearish_valid
    ):
        return levels

    return None


def _format_level(
    value: float,
) -> str:
    return format(
        value,
        ".8g",
    )


def _generic_scenarios() -> Dict[str, str]:
    return {
        "bullish": (
            "No validated bullish setup is available. Wait for a confirmed "
            "trigger, invalidation and target."
        ),
        "bearish": (
            "No validated bearish setup is available. Wait for a confirmed "
            "trigger, invalidation and target."
        ),
        "neutral": (
            "No executable setup is confirmed. Wait for price to break a "
            "validated level with volume."
        ),
    }


def build(
    direction: str,
    zones: Optional[Dict],
) -> Dict[str, str]:
    """Return complete scenario copy without unsafe numeric placeholders."""
    scenarios = _generic_scenarios()
    levels = _validated_levels(
        direction,
        zones,
    )

    if levels is None:
        return scenarios

    entry_low = _format_level(
        levels["entry_low"]
    )
    entry_high = _format_level(
        levels["entry_high"]
    )
    target_1 = _format_level(
        levels["target_1"]
    )
    target_2 = _format_level(
        levels["target_2"]
    )
    invalidation = _format_level(
        levels["invalidation"]
    )

    if direction == "bullish":
        scenarios["bullish"] = (
            f"Bullish trigger: hold within or reclaim the {entry_low}–"
            f"{entry_high} entry zone. Invalidation: below "
            f"{invalidation}. Targets: {target_1}, then {target_2}."
        )
        scenarios["bearish"] = (
            f"Bearish alternative: a confirmed break below {invalidation} "
            "invalidates the bullish setup. No validated short target is "
            "available yet."
        )
    else:
        scenarios["bearish"] = (
            f"Bearish trigger: reject from or trade below the {entry_low}–"
            f"{entry_high} entry zone. Invalidation: above "
            f"{invalidation}. Targets: {target_1}, then {target_2}."
        )
        scenarios["bullish"] = (
            f"Bullish alternative: a confirmed break above {invalidation} "
            "invalidates the bearish setup. No validated long target is "
            "available yet."
        )

    return scenarios


def _safe_text(
    value,
) -> Optional[str]:
    if not isinstance(
        value,
        str,
    ):
        return None

    text = value.strip()

    if (
        not text
        or _UNSAFE_TEXT.search(text)
    ):
        return None

    return text


def sanitize(
    scenarios,
    fallback: Dict[str, str],
) -> Dict[str, str]:
    """Preserve usable AI copy and replace unsafe/missing fields safely."""
    raw_scenarios = (
        scenarios
        if isinstance(
            scenarios,
            Mapping,
        )
        else {}
    )

    return {
        direction: (
            _safe_text(
                raw_scenarios.get(
                    direction
                )
            )
            or fallback[direction]
        )
        for direction in SCENARIO_DIRECTIONS
    }
