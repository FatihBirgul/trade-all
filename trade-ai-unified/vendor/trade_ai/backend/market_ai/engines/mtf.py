"""Multi-timeframe analysis engine.

This module provides a deterministic MTF confluence layer.

It does not fetch market data and does not call external services.
It receives already-computed timeframe snapshots and converts them into
higher-timeframe bias, current-timeframe bias, lower-timeframe confirmation,
alignment/conflict metrics, and explicit MTF evidence.

Important architecture rule:
- Directional bias and tradeability are separate concepts.
- A timeframe can have a bullish/bearish composite bias while its final
  executable direction is neutral because of a later RR/trade-quality gate.
- MTF uses the validated directional composite as bias when the single-TF
  evidence gate passed.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional
from math import isfinite


# ---------------------------------------------------------------------------
# Timeframe ordering
# ---------------------------------------------------------------------------
TIMEFRAME_RANK = {
    "1m": 0,
    "5m": 1,
    "15m": 2,
    "30m": 2.5,
    "1H": 3,
    "4H": 4,
    "1D": 5,
}


DEFAULT_TIMEFRAMES = (
    "1m",
    "5m",
    "15m",
    "1H",
    "4H",
    "1D",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def timeframe_rank(timeframe: str) -> float:
    """Return the ordering rank of a supported timeframe."""
    if timeframe not in TIMEFRAME_RANK:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    return TIMEFRAME_RANK[timeframe]


def normalize_direction(
    direction: Optional[str],
) -> str:
    """Normalize a direction into bullish/bearish/neutral."""
    if direction in (
        "bullish",
        "bearish",
        "neutral",
    ):
        return direction

    return "neutral"


def _snapshot_quality(
    snapshot: Dict,
) -> Dict:
    """Return the snapshot quality dictionary safely."""
    quality = snapshot.get(
        "quality"
    )

    if isinstance(
        quality,
        dict,
    ):
        return quality

    return {}


def _snapshot_direction(
    snapshot: Dict,
) -> str:
    """Extract the directional bias from a timeframe snapshot.

    Priority:
    1. Explicit non-neutral executable direction.
    2. Validated composite_direction when the single-TF evidence gate passed.
    3. neutral.

    This intentionally separates directional bias from later tradeability
    filters such as RR. A timeframe can therefore remain bullish/bearish as
    an MTF bias even when its executable single-TF direction is neutral.
    """
    direction = normalize_direction(
        snapshot.get(
            "direction"
        )
    )

    if direction in (
        "bullish",
        "bearish",
    ):
        return direction

    quality = _snapshot_quality(
        snapshot
    )

    composite = normalize_direction(
        quality.get(
            "composite_direction"
        )
    )

    gate_passed = _snapshot_gate_passed(snapshot)

    if (
        gate_passed
        and composite in (
            "bullish",
            "bearish",
        )
    ):
        return composite

    return "neutral"


def _snapshot_executable_direction(
    snapshot: Dict,
) -> str:
    """Return the final single-TF executable direction."""
    return normalize_direction(
        snapshot.get(
            "direction"
        )
    )


def _snapshot_confidence(
    snapshot: Dict,
) -> float:
    """Extract analytical confidence from a snapshot."""
    value = snapshot.get(
        "confidence",
        0.0,
    )

    try:
        if isinstance(value, bool):
            return 0.0
        numeric = float(value)
        if not isfinite(numeric):
            return 0.0
        return max(
            0.0,
            min(
                100.0,
                numeric,
            ),
        )
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0.0


def _snapshot_gate_passed(
    snapshot: Dict,
) -> bool:
    """Extract whether the single-timeframe evidence gate passed."""
    quality = _snapshot_quality(
        snapshot
    )

    return quality.get("gate_passed") is True


def _snapshot_tradeable(
    snapshot: Dict,
) -> bool:
    """Determine whether the final single-TF direction is executable."""
    return (
        _snapshot_executable_direction(
            snapshot
        )
        in (
            "bullish",
            "bearish",
        )
    )


def _snapshot_final_score(
    snapshot: Dict,
) -> float:
    """Extract the deterministic composite score."""
    value = snapshot.get(
        "final_score",
        0.0,
    )

    if value is None:
        quality = _snapshot_quality(
            snapshot
        )

        value = quality.get(
            "final_score",
            0.0,
        )

    try:
        if isinstance(value, bool):
            return 0.0
        numeric = float(value)
        return max(-100.0, min(100.0, numeric)) if isfinite(numeric) else 0.0
    except (
        TypeError,
        ValueError,
        OverflowError,
    ):
        return 0.0


# ---------------------------------------------------------------------------
# Timeframe buckets
# ---------------------------------------------------------------------------
def higher_timeframes(
    timeframe: str,
    available: Iterable[str] = DEFAULT_TIMEFRAMES,
) -> List[str]:
    """Return supported timeframes strictly above the requested timeframe."""
    rank = timeframe_rank(
        timeframe
    )

    return [
        tf
        for tf in available
        if tf in TIMEFRAME_RANK
        and timeframe_rank(tf) > rank
    ]


def lower_timeframes(
    timeframe: str,
    available: Iterable[str] = DEFAULT_TIMEFRAMES,
) -> List[str]:
    """Return supported timeframes strictly below the requested timeframe."""
    rank = timeframe_rank(
        timeframe
    )

    return [
        tf
        for tf in available
        if tf in TIMEFRAME_RANK
        and timeframe_rank(tf) < rank
    ]


# ---------------------------------------------------------------------------
# Higher-timeframe bias
# ---------------------------------------------------------------------------
def _select_highest_bias(
    snapshots: Dict[str, Dict],
) -> Dict:
    """Select the highest available non-neutral timeframe as HTF bias."""
    candidates = []

    for timeframe, snapshot in snapshots.items():
        if timeframe not in TIMEFRAME_RANK:
            continue

        direction = _snapshot_direction(
            snapshot
        )

        if direction == "neutral":
            continue

        candidates.append(
            (
                timeframe_rank(
                    timeframe
                ),
                timeframe,
                direction,
                _snapshot_confidence(
                    snapshot
                ),
                _snapshot_gate_passed(
                    snapshot
                ),
                _snapshot_tradeable(
                    snapshot
                ),
                _snapshot_final_score(
                    snapshot
                ),
            )
        )

    if not candidates:
        return {
            "timeframe": None,
            "direction": "neutral",
            "confidence": 0.0,
            "gate_passed": False,
            "tradeable": False,
            "final_score": 0.0,
        }

    (
        _rank,
        timeframe,
        direction,
        confidence,
        gate_passed,
        tradeable,
        final_score,
    ) = max(
        candidates,
        key=lambda item: (
            item[0],
            item[4],
            item[3],
        ),
    )

    return {
        "timeframe": timeframe,
        "direction": direction,
        "confidence": round(
            confidence,
            1,
        ),
        "gate_passed": bool(
            gate_passed
        ),
        "tradeable": bool(
            tradeable
        ),
        "final_score": round(
            final_score,
            1,
        ),
    }


# ---------------------------------------------------------------------------
# Current timeframe
# ---------------------------------------------------------------------------
def _current_bias(
    timeframe: str,
    snapshots: Dict[str, Dict],
) -> Dict:
    """Return the selected/current timeframe bias."""
    snapshot = snapshots.get(
        timeframe
    )

    if not snapshot:
        return {
            "timeframe": timeframe,
            "direction": "neutral",
            "confidence": 0.0,
            "gate_passed": False,
            "tradeable": False,
            "final_score": 0.0,
            "available": False,
        }

    return {
        "timeframe": timeframe,
        "direction": _snapshot_direction(
            snapshot
        ),
        "executable_direction": (
            _snapshot_executable_direction(
                snapshot
            )
        ),
        "confidence": round(
            _snapshot_confidence(
                snapshot
            ),
            1,
        ),
        "gate_passed": _snapshot_gate_passed(
            snapshot
        ),
        "tradeable": _snapshot_tradeable(
            snapshot
        ),
        "final_score": round(
            _snapshot_final_score(
                snapshot
            ),
            1,
        ),
        "available": True,
    }


# ---------------------------------------------------------------------------
# Lower-timeframe confirmation
# ---------------------------------------------------------------------------
def _lower_confirmation(
    timeframe: str,
    snapshots: Dict[str, Dict],
    reference_direction: str,
) -> Dict:
    """Measure lower-timeframe confirmation against a reference direction."""
    lowers = [
        tf
        for tf in lower_timeframes(
            timeframe,
            snapshots.keys(),
        )
    ]

    available = []

    for tf in sorted(
        lowers,
        key=timeframe_rank,
        reverse=True,
    ):
        snapshot = snapshots.get(
            tf
        )

        if not snapshot:
            continue

        available.append(
            {
                "timeframe": tf,
                "direction": _snapshot_direction(
                    snapshot
                ),
                "executable_direction": (
                    _snapshot_executable_direction(
                        snapshot
                    )
                ),
                "confidence": round(
                    _snapshot_confidence(
                        snapshot
                    ),
                    1,
                ),
                "gate_passed": _snapshot_gate_passed(
                    snapshot
                ),
                "tradeable": _snapshot_tradeable(
                    snapshot
                ),
            }
        )

    if not available:
        return {
            "direction": "neutral",
            "agreement_ratio": 0.0,
            "conflict_ratio": 0.0,
            "supporting_count": 0,
            "opposing_count": 0,
            "available_count": 0,
            "evidence": [],
        }

    if reference_direction not in (
        "bullish",
        "bearish",
    ):
        return {
            "direction": "neutral",
            "agreement_ratio": 0.0,
            "conflict_ratio": 0.0,
            "supporting_count": 0,
            "opposing_count": 0,
            "available_count": len(
                available
            ),
            "evidence": available,
        }

    supporting = [
        item
        for item in available
        if item["direction"]
        == reference_direction
    ]

    opposing = [
        item
        for item in available
        if (
            item["direction"]
            in (
                "bullish",
                "bearish",
            )
            and item["direction"]
            != reference_direction
        )
    ]

    directional_count = (
        len(supporting)
        + len(opposing)
    )

    agreement_ratio = (
        len(supporting)
        / directional_count
        if directional_count
        else 0.0
    )

    conflict_ratio = (
        len(opposing)
        / directional_count
        if directional_count
        else 0.0
    )

    if len(supporting) > len(opposing):
        direction = reference_direction

    elif len(opposing) > len(supporting):
        direction = (
            "bearish"
            if reference_direction
            == "bullish"
            else "bullish"
        )

    else:
        direction = "neutral"

    return {
        "direction": direction,
        "agreement_ratio": round(
            agreement_ratio,
            3,
        ),
        "conflict_ratio": round(
            conflict_ratio,
            3,
        ),
        "supporting_count": len(
            supporting
        ),
        "opposing_count": len(
            opposing
        ),
        "available_count": len(
            available
        ),
        "evidence": available,
    }


# ---------------------------------------------------------------------------
# Higher-timeframe alignment
# ---------------------------------------------------------------------------
def _higher_alignment(
    timeframe: str,
    snapshots: Dict[str, Dict],
    reference_direction: str,
) -> Dict:
    """Measure higher-timeframe alignment against current direction."""
    highs = [
        tf
        for tf in higher_timeframes(
            timeframe,
            snapshots.keys(),
        )
    ]

    available = []

    for tf in sorted(
        highs,
        key=timeframe_rank,
        reverse=True,
    ):
        snapshot = snapshots.get(
            tf
        )

        if not snapshot:
            continue

        available.append(
            {
                "timeframe": tf,
                "direction": _snapshot_direction(
                    snapshot
                ),
                "executable_direction": (
                    _snapshot_executable_direction(
                        snapshot
                    )
                ),
                "confidence": round(
                    _snapshot_confidence(
                        snapshot
                    ),
                    1,
                ),
                "gate_passed": _snapshot_gate_passed(
                    snapshot
                ),
                "tradeable": _snapshot_tradeable(
                    snapshot
                ),
            }
        )

    if not available:
        return {
            "direction": "neutral",
            "agreement_ratio": 0.0,
            "conflict_ratio": 0.0,
            "supporting_count": 0,
            "opposing_count": 0,
            "available_count": 0,
            "evidence": [],
        }

    if reference_direction not in (
        "bullish",
        "bearish",
    ):
        return {
            "direction": "neutral",
            "agreement_ratio": 0.0,
            "conflict_ratio": 0.0,
            "supporting_count": 0,
            "opposing_count": 0,
            "available_count": len(
                available
            ),
            "evidence": available,
        }

    supporting = [
        item
        for item in available
        if item["direction"]
        == reference_direction
    ]

    opposing = [
        item
        for item in available
        if (
            item["direction"]
            in (
                "bullish",
                "bearish",
            )
            and item["direction"]
            != reference_direction
        )
    ]

    directional_count = (
        len(supporting)
        + len(opposing)
    )

    agreement_ratio = (
        len(supporting)
        / directional_count
        if directional_count
        else 0.0
    )

    conflict_ratio = (
        len(opposing)
        / directional_count
        if directional_count
        else 0.0
    )

    if len(supporting) > len(opposing):
        direction = reference_direction

    elif len(opposing) > len(supporting):
        direction = (
            "bearish"
            if reference_direction
            == "bullish"
            else "bullish"
        )

    else:
        direction = "neutral"

    return {
        "direction": direction,
        "agreement_ratio": round(
            agreement_ratio,
            3,
        ),
        "conflict_ratio": round(
            conflict_ratio,
            3,
        ),
        "supporting_count": len(
            supporting
        ),
        "opposing_count": len(
            opposing
        ),
        "available_count": len(
            available
        ),
        "evidence": available,
    }


# ---------------------------------------------------------------------------
# MTF evidence
# ---------------------------------------------------------------------------
def _build_mtf_evidence(
    higher: Dict,
    current: Dict,
    lower: Dict,
) -> List[Dict]:
    """Convert MTF states into explicit evidence objects."""
    evidence = []

    if higher["timeframe"] is not None:
        if higher["direction"] in (
            "bullish",
            "bearish",
        ):
            evidence.append(
                {
                    "source": "mtf_htf_bias",
                    "direction": higher[
                        "direction"
                    ],
                    "strength": higher[
                        "confidence"
                    ],
                    "timeframe": higher[
                        "timeframe"
                    ],
                    "age_bars": 0,
                    "confirmed": higher[
                        "gate_passed"
                    ],
                    "bucket": "mtf_htf",
                }
            )

    if current["direction"] in (
        "bullish",
        "bearish",
    ):
        evidence.append(
            {
                "source": "mtf_current",
                "direction": current[
                    "direction"
                ],
                "strength": current[
                    "confidence"
                ],
                "timeframe": current[
                    "timeframe"
                ],
                "age_bars": 0,
                "confirmed": current[
                    "gate_passed"
                ],
                "bucket": "mtf_current",
            }
        )

    if lower["direction"] in (
        "bullish",
        "bearish",
    ):
        strength = round(
            lower[
                "agreement_ratio"
            ]
            * 100,
            2,
        )

        evidence.append(
            {
                "source": "mtf_ltf_confirmation",
                "direction": lower[
                    "direction"
                ],
                "strength": strength,
                "timeframe": (
                    lower[
                        "evidence"
                    ][0]["timeframe"]
                    if lower[
                        "evidence"
                    ]
                    else None
                ),
                "age_bars": 0,
                "confirmed": (
                    lower[
                        "supporting_count"
                    ]
                    > lower[
                        "opposing_count"
                    ]
                ),
                "bucket": "mtf_ltf",
            }
        )

    return evidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def analyze(
    current_timeframe: str,
    snapshots: Dict[str, Dict],
) -> Dict:
    """Build a deterministic multi-timeframe confluence summary."""
    if current_timeframe not in TIMEFRAME_RANK:
        raise ValueError(
            f"Unsupported timeframe: {current_timeframe}"
        )

    normalized = {
        tf: snapshot
        for tf, snapshot in snapshots.items()
        if tf in TIMEFRAME_RANK
        and isinstance(
            snapshot,
            dict,
        )
    }

    current = _current_bias(
        current_timeframe,
        normalized,
    )

    higher = _select_highest_bias(
        {
            tf: snapshot
            for tf, snapshot in normalized.items()
            if timeframe_rank(tf)
            > timeframe_rank(
                current_timeframe
            )
        }
    )

    reference_direction = current[
        "direction"
    ]

    if reference_direction == "neutral":
        reference_direction = higher[
            "direction"
        ]

    higher_alignment = _higher_alignment(
        current_timeframe,
        normalized,
        reference_direction,
    )

    lower_confirmation = _lower_confirmation(
        current_timeframe,
        normalized,
        reference_direction,
    )

    evidence = _build_mtf_evidence(
        higher,
        current,
        lower_confirmation,
    )

    # -----------------------------------------------------------------------
    # Final MTF direction
    #
    # MTF reports directional bias. It does not independently declare an
    # executable trade when the current timeframe itself is not directionally
    # validated.
    # -----------------------------------------------------------------------
    if current["direction"] in (
        "bullish",
        "bearish",
    ):
        base_direction = current[
            "direction"
        ]

    else:
        base_direction = higher[
            "direction"
        ]

    htf_conflict = (
        higher_alignment[
            "opposing_count"
        ]
        > higher_alignment[
            "supporting_count"
        ]
        and higher_alignment[
            "available_count"
        ]
        > 0
    )

    ltf_conflict = (
        lower_confirmation[
            "opposing_count"
        ]
        > lower_confirmation[
            "supporting_count"
        ]
        and lower_confirmation[
            "available_count"
        ]
        > 0
    )

    if (
        base_direction in (
            "bullish",
            "bearish",
        )
        and htf_conflict
        and ltf_conflict
    ):
        final_direction = "neutral"

    else:
        final_direction = (
            base_direction
        )

    # -----------------------------------------------------------------------
    # Alignment metrics
    # -----------------------------------------------------------------------
    alignment_components = []

    if higher_alignment[
        "available_count"
    ] > 0:
        alignment_components.append(
            higher_alignment[
                "agreement_ratio"
            ]
        )

    if lower_confirmation[
        "available_count"
    ] > 0:
        alignment_components.append(
            lower_confirmation[
                "agreement_ratio"
            ]
        )

    if (
        current["direction"]
        in (
            "bullish",
            "bearish",
        )
    ):
        alignment_components.append(
            1.0
        )

    alignment_ratio = (
        sum(
            alignment_components
        )
        / len(
            alignment_components
        )
        if alignment_components
        else 0.0
    )

    conflict_components = []

    if higher_alignment[
        "available_count"
    ] > 0:
        conflict_components.append(
            higher_alignment[
                "conflict_ratio"
            ]
        )

    if lower_confirmation[
        "available_count"
    ] > 0:
        conflict_components.append(
            lower_confirmation[
                "conflict_ratio"
            ]
        )

    conflict_ratio = (
        sum(
            conflict_components
        )
        / len(
            conflict_components
        )
        if conflict_components
        else 0.0
    )

    supporting_count = (
        sum(
            1
            for item in evidence
            if (
                item["direction"]
                == final_direction
            )
        )
        if final_direction != "neutral"
        else 0
    )

    opposing_count = (
        sum(
            1
            for item in evidence
            if (
                final_direction != "neutral"
                and item["direction"]
                != final_direction
            )
        )
        if final_direction != "neutral"
        else 0
    )

    return {
        "direction": final_direction,

        "current_timeframe": current_timeframe,

        "current": current,

        "higher_timeframe_bias": higher,

        "higher_timeframe_alignment": (
            higher_alignment
        ),

        "lower_timeframe_confirmation": (
            lower_confirmation
        ),

        "alignment_ratio": round(
            alignment_ratio,
            3,
        ),

        "conflict_ratio": round(
            conflict_ratio,
            3,
        ),

        "supporting_count": (
            supporting_count
        ),

        "opposing_count": (
            opposing_count
        ),

        "evidence": evidence,
    }
