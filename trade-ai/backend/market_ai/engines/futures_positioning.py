"""Deterministic Futures positioning analysis engine.

Combines:
- Open Interest change
- Funding Rate

into a bounded directional positioning signal.

Important:
- Absolute Open Interest is NOT treated as directional evidence.
- Open Interest direction requires a previous observation.
- Funding is treated as positioning pressure, not guaranteed price direction.
- This engine does not fetch market data.
- This engine does not make trade decisions.
"""
from __future__ import annotations

from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_float(
    value,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_int(
    value,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _clip(
    value: float,
    lo: float,
    hi: float,
) -> float:
    return max(
        lo,
        min(
            hi,
            value,
        ),
    )


# ---------------------------------------------------------------------------
# Funding interpretation
# ---------------------------------------------------------------------------
def funding_pressure(
    funding_rate: float,
    neutral_band: float = 0.00005,
    extreme_band: float = 0.00030,
) -> float:
    """Return a bounded directional funding score.

    Interpretation used by this first deterministic version:

    Positive funding:
        longs are paying shorts -> positioning is relatively long-heavy.

        Therefore:
            small positive -> mild bearish/crowded-long pressure
            large positive -> stronger bearish/crowded-long pressure

    Negative funding:
        shorts are paying longs -> positioning is relatively short-heavy.

        Therefore:
            small negative -> mild bullish/crowded-short pressure
            large negative -> stronger bullish/crowded-short pressure

    The signal is intentionally bounded because funding is positioning
    information, not a direct price forecast.
    """
    rate = _safe_float(
        funding_rate
    )

    magnitude = abs(
        rate
    )

    if magnitude <= neutral_band:
        return 0.0

    excess = (
        magnitude
        - neutral_band
    )

    denominator = (
        extreme_band
        - neutral_band
    )

    if denominator <= 0:
        denominator = 0.00025

    normalized = (
        excess / denominator
    )

    normalized = _clip(
        normalized,
        0.0,
        1.0,
    )

    score = (
        normalized
        * 40.0
    )

    if rate > 0:
        # Positive funding = crowded longs = contrarian bearish pressure.
        return round(
            -score,
            2,
        )

    # Negative funding = crowded shorts = contrarian bullish pressure.
    return round(
        score,
        2,
    )


# ---------------------------------------------------------------------------
# Open Interest interpretation
# ---------------------------------------------------------------------------
def open_interest_change_pct(
    current_open_interest: float,
    previous_open_interest: Optional[float],
) -> Optional[float]:
    """Return percentage change in Open Interest."""
    current = _safe_float(
        current_open_interest
    )

    if previous_open_interest is None:
        return None

    previous = _safe_float(
        previous_open_interest
    )

    if previous <= 0:
        return None

    return (
        (current - previous)
        / previous
        * 100.0
    )


def open_interest_score(
    current_open_interest: float,
    previous_open_interest: Optional[float],
    price_change_pct: Optional[float] = None,
    neutral_band_pct: float = 0.10,
    strong_change_pct: float = 1.00,
) -> float:
    """Convert OI change + optional price change into a directional score.

    Basic interpretation:

        Price up + OI up   -> long participation / bullish
        Price down + OI up -> short participation / bearish

    When price change is unavailable, OI change alone is intentionally weak
    and only reports participation expansion/contraction rather than a strong
    directional forecast.

    OI falling is treated as position closing and therefore carries less
    directional weight.
    """
    change = open_interest_change_pct(
        current_open_interest,
        previous_open_interest,
    )

    if change is None:
        return 0.0

    if abs(change) <= neutral_band_pct:
        return 0.0

    magnitude = _clip(
        (
            abs(change)
            - neutral_band_pct
        )
        / (
            strong_change_pct
            - neutral_band_pct
        ),
        0.0,
        1.0,
    )

    price_change = (
        _safe_float(
            price_change_pct
        )
        if price_change_pct is not None
        else None
    )

    # Without price direction, OI change expresses participation more than
    # direction. Keep it weak to avoid manufacturing a directional signal.
    if price_change is None:
        return round(
            (
                15.0
                * magnitude
                * (
                    1.0
                    if change > 0
                    else -1.0
                )
            ),
            2,
        )

    if change > 0:
        if price_change > 0:
            score = (
                60.0
                * magnitude
            )
        elif price_change < 0:
            score = (
                -60.0
                * magnitude
            )
        else:
            score = 0.0

    else:
        # Falling OI means positions are being closed. Keep this much weaker
        # than expanding OI.
        if price_change > 0:
            score = (
                20.0
                * magnitude
            )
        elif price_change < 0:
            score = (
                -20.0
                * magnitude
            )
        else:
            score = 0.0

    return round(
        _clip(
            score,
            -100.0,
            100.0,
        ),
        2,
    )


# ---------------------------------------------------------------------------
# Funding extraction
# ---------------------------------------------------------------------------
def latest_funding_rate(
    funding_history: Optional[List[Dict]],
) -> Optional[float]:
    """Return the latest funding rate from normalized funding history."""
    if not funding_history:
        return None

    latest = None
    latest_time = -1

    for item in funding_history:
        rate = item.get(
            "funding_rate"
        )

        timestamp = _safe_int(
            item.get(
                "funding_time",
                0,
            )
        )

        if rate is None:
            continue

        if (
            latest is None
            or timestamp > latest_time
        ):
            latest = _safe_float(
                rate
            )
            latest_time = timestamp

    return latest


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------
def analyze(
    current_open_interest: Optional[Dict] = None,
    previous_open_interest: Optional[Dict] = None,
    funding_history: Optional[List[Dict]] = None,
    price_change_pct: Optional[float] = None,
) -> Dict:
    """Build a deterministic Futures positioning snapshot."""
    current_oi = (
        _safe_float(
            current_open_interest.get(
                "open_interest",
                0.0,
            )
        )
        if current_open_interest
        else 0.0
    )

    previous_oi = (
        _safe_float(
            previous_open_interest.get(
                "open_interest",
                0.0,
            )
        )
        if previous_open_interest
        else None
    )

    current_oi_timestamp = (
        _safe_int(
            current_open_interest.get(
                "timestamp",
                0,
            )
        )
        if current_open_interest
        else None
    )

    previous_oi_timestamp = (
        _safe_int(
            previous_open_interest.get(
                "timestamp",
                0,
            )
        )
        if previous_open_interest
        else None
    )

    oi_change = open_interest_change_pct(
        current_oi,
        previous_oi,
    )

    latest_funding = latest_funding_rate(
        funding_history
    )

    oi_score = open_interest_score(
        current_oi,
        previous_oi,
        price_change_pct=price_change_pct,
    )

    funding_score = (
        funding_pressure(
            latest_funding
        )
        if latest_funding is not None
        else 0.0
    )

    # OI gets the larger weight because it measures actual position
    # participation. Funding is secondary positioning context.
    weighted_score = (
        oi_score * 0.70
        + funding_score * 0.30
    )

    weighted_score = round(
        _clip(
            weighted_score,
            -100.0,
            100.0,
        ),
        2,
    )

    if weighted_score > 0:
        dominant_side = "bullish"

    elif weighted_score < 0:
        dominant_side = "bearish"

    else:
        dominant_side = "neutral"

    if (
        oi_change is None
        and latest_funding is None
    ):
        positioning_quality = "unavailable"

    elif (
        abs(weighted_score) >= 40
    ):
        positioning_quality = "strong"

    elif (
        abs(weighted_score) >= 15
    ):
        positioning_quality = "moderate"

    else:
        positioning_quality = "weak"

    return {
        "current_open_interest": round(
            current_oi,
            8,
        ),

        "previous_open_interest": (
            round(
                previous_oi,
                8,
            )
            if previous_oi is not None
            else None
        ),

        "open_interest_change": (
            round(
                current_oi - previous_oi,
                8,
            )
            if previous_oi is not None
            else None
        ),

        "open_interest_change_pct": (
            round(
                oi_change,
                6,
            )
            if oi_change is not None
            else None
        ),

        "current_open_interest_timestamp": (
            current_oi_timestamp
        ),

        "previous_open_interest_timestamp": (
            previous_oi_timestamp
        ),

        "latest_funding_rate": (
            round(
                latest_funding,
                8,
            )
            if latest_funding is not None
            else None
        ),

        "open_interest_score": oi_score,

        "funding_score": funding_score,

        "positioning_score": weighted_score,

        "dominant_side": dominant_side,

        "positioning_quality": positioning_quality,

        "funding_sample_count": len(
            funding_history or []
        ),

        "price_change_pct": (
            round(
                _safe_float(
                    price_change_pct
                ),
                6,
            )
            if price_change_pct is not None
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Score / Evidence
# ---------------------------------------------------------------------------
def score(
    analysis: Dict,
    minimum_score: float = 8.0,
) -> float:
    """Return bounded positioning score."""
    value = _safe_float(
        analysis.get(
            "positioning_score",
            0.0,
        )
    )

    if abs(value) < minimum_score:
        return 0.0

    return round(
        _clip(
            value,
            -100.0,
            100.0,
        ),
        1,
    )


def evidence(
    analysis: Dict,
    timeframe: Optional[str] = None,
    minimum_score: float = 8.0,
) -> Optional[Dict]:
    """Return an Evidence-compatible Futures positioning object."""
    positioning_score = score(
        analysis,
        minimum_score=minimum_score,
    )

    if positioning_score == 0:
        return None

    direction = (
        "bullish"
        if positioning_score > 0
        else "bearish"
    )

    current_oi = analysis.get(
        "current_open_interest"
    )

    previous_oi = analysis.get(
        "previous_open_interest"
    )

    oi_change_pct = analysis.get(
        "open_interest_change_pct"
    )

    latest_funding = analysis.get(
        "latest_funding_rate"
    )

    # Confirmation requires at least one meaningful positioning input.
    confirmed = (
        current_oi is not None
        and (
            previous_oi is not None
            or latest_funding is not None
        )
    )

    return {
        "source": "futures_positioning",

        "direction": direction,

        "strength": abs(
            float(
                positioning_score
            )
        ),

        "timeframe": timeframe,

        "age_bars": 0,

        "confirmed": confirmed,

        "bucket": "futures_positioning",

        "positioning_score": positioning_score,

        "open_interest_change_pct": (
            oi_change_pct
        ),

        "funding_rate": (
            latest_funding
        ),
    }