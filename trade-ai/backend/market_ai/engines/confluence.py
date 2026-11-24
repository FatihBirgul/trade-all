"""Evidence and confluence engine.

Converts deterministic analysis outputs into explicit Evidence objects,
applies confirmation/recency adjustments, removes correlated duplicates,
and produces a single confluence summary used by the decision gate.

This module does not fetch market data.
All calculations are deterministic and calibration-free.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from math import isfinite
from typing import Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Evidence:
    """A single directional evidence item."""

    source: str
    direction: str
    strength: float

    timeframe: Optional[str] = None
    age_bars: int = 0
    confirmed: bool = True
    bucket: str = "general"

    def __post_init__(self):
        if self.direction not in (
            "bullish",
            "bearish",
            "neutral",
        ):
            raise ValueError(
                f"Invalid evidence direction: {self.direction}"
            )

        if (
            isinstance(self.strength, bool)
            or not isinstance(self.strength, (int, float))
            or not 0 <= self.strength <= 100
            or not isfinite(self.strength)
        ):
            raise ValueError(
                "Evidence strength must be finite and between 0 and 100."
            )

        if isinstance(self.age_bars, bool) or not isinstance(self.age_bars, int) or self.age_bars < 0:
            raise ValueError(
                "Evidence age must be a nonnegative integer."
            )
        if not isinstance(self.confirmed, bool):
            raise ValueError("Evidence confirmation must be boolean.")
        if not isinstance(self.source, str) or not self.source.strip() or not isinstance(self.bucket, str):
            raise ValueError("Evidence source and bucket must be valid strings.")


# ---------------------------------------------------------------------------
# Correlation buckets
# ---------------------------------------------------------------------------
CORRELATION_BUCKETS = {
    "trend": "trend_structure",
    "structure": "trend_structure",
    "momentum": "momentum",
    "volume": "volume",
    "news": "news",

    "candlestick": "candlestick",
    "chart_pattern": "chart_pattern",

    "pattern": "pattern",

    "order_flow": "order_flow",
    "liquidity": "liquidity",
    "futures_positioning": "futures_positioning",
    "liquidation": "liquidation",

    "mtf_htf_bias": "mtf_htf",
    "mtf_current": "mtf_current",
    "mtf_ltf_confirmation": "mtf_ltf",
}


# ---------------------------------------------------------------------------
# Recency / confirmation
# ---------------------------------------------------------------------------
RECENCY_HALF_LIFE_BARS = 8

CONFIRMATION_MULTIPLIERS = {
    True: 1.0,
    False: 0.60,
}


def recency_multiplier(
    age_bars: int,
    half_life_bars: int = RECENCY_HALF_LIFE_BARS,
) -> float:
    """Return exponential evidence decay."""
    if age_bars < 0:
        raise ValueError(
            "Evidence age cannot be negative."
        )

    if half_life_bars <= 0:
        raise ValueError(
            "half_life_bars must be positive."
        )

    return max(
        0.0,
        0.5 ** (
            float(age_bars)
            / float(half_life_bars)
        ),
    )


def confirmation_multiplier(
    confirmed: bool,
) -> float:
    return CONFIRMATION_MULTIPLIERS[
        bool(confirmed)
    ]


def effective_strength(
    evidence: Evidence,
) -> float:
    """Calculate effective strength after confirmation/recency adjustment."""
    value = (
        float(evidence.strength)
        * confirmation_multiplier(
            evidence.confirmed
        )
        * recency_multiplier(
            evidence.age_bars
        )
    )

    return round(
        max(
            0.0,
            min(
                100.0,
                value,
            ),
        ),
        4,
    )


def with_effective_strength(
    evidence: Evidence,
) -> Evidence:
    """Return an immutable copy carrying effective strength."""
    return replace(
        evidence,
        strength=effective_strength(
            evidence
        ),
    )


# ---------------------------------------------------------------------------
# Score-based Evidence
# ---------------------------------------------------------------------------
def _direction_from_score(
    score: float,
    threshold: float = 8.0,
) -> str:
    if score >= threshold:
        return "bullish"

    if score <= -threshold:
        return "bearish"

    return "neutral"


def _strength_from_score(
    score: float,
) -> float:
    return min(
        100.0,
        abs(
            float(score)
        ),
    )


def evidence_from_scores(
    scores: Dict[str, float],
    timeframe: Optional[str] = None,
    threshold: float = 8.0,
) -> List[Evidence]:
    """Convert non-direct evidence pillars into Evidence.

    Pattern, Order Flow, Liquidity, Futures Positioning and Liquidation are
    supplied explicitly and therefore excluded from generic score conversion.
    """
    evidence: List[Evidence] = []

    if isinstance(threshold, bool):
        raise ValueError("Evidence threshold must be positive and finite")
    try:
        threshold = float(threshold)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid evidence threshold") from exc
    if not isfinite(threshold) or threshold <= 0:
        raise ValueError("Evidence threshold must be positive and finite")

    for source, score in scores.items():
        if source not in {"trend", "momentum", "volume", "structure", "news"}:
            continue

        if isinstance(score, bool):
            raise ValueError("Core evidence scores must be finite numbers")
        try:
            value = float(score if score is not None else 0.0)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Invalid core evidence score") from exc
        if not isfinite(value):
            raise ValueError("Core evidence scores must be finite numbers")

        direction = _direction_from_score(
            value,
            threshold=threshold,
        )

        if direction == "neutral":
            continue

        evidence.append(
            Evidence(
                source=source,
                direction=direction,
                strength=_strength_from_score(
                    value
                ),
                timeframe=timeframe,
                age_bars=0,
                confirmed=True,
                bucket=CORRELATION_BUCKETS.get(
                    source,
                    "general",
                ),
            )
        )

    return evidence


# ---------------------------------------------------------------------------
# Pattern -> Evidence
# ---------------------------------------------------------------------------
def evidence_from_patterns(
    candle_patterns: Optional[List[Dict]] = None,
    chart_patterns: Optional[List[Dict]] = None,
    timeframe: Optional[str] = None,
) -> List[Evidence]:
    """Convert candlestick/chart patterns into explicit Evidence."""
    evidence: List[Evidence] = []

    for pattern in (
        candle_patterns or []
    ):
        direction = pattern.get(
            "classification",
            "neutral",
        )

        if direction not in (
            "bullish",
            "bearish",
        ):
            continue

        strength = float(
            pattern.get(
                "strength",
                pattern.get(
                    "base_strength",
                    0,
                ),
            )
            or 0
        )

        if strength <= 0:
            continue

        evidence.append(
            Evidence(
                source="candlestick",
                direction=direction,
                strength=min(
                    100.0,
                    strength,
                ),
                timeframe=timeframe,
                age_bars=int(
                    pattern.get(
                        "age_bars",
                        0,
                    )
                    or 0
                ),
                confirmed=bool(
                    pattern.get(
                        "confirmed",
                        True,
                    )
                ),
                bucket=CORRELATION_BUCKETS[
                    "candlestick"
                ],
            )
        )

    for pattern in (
        chart_patterns or []
    ):
        direction = pattern.get(
            "classification",
            "neutral",
        )

        if direction not in (
            "bullish",
            "bearish",
        ):
            continue

        strength = float(
            pattern.get(
                "confidence",
                pattern.get(
                    "base_confidence",
                    0,
                ),
            )
            or 0
        )

        if strength <= 0:
            continue

        evidence.append(
            Evidence(
                source="chart_pattern",
                direction=direction,
                strength=min(
                    100.0,
                    strength,
                ),
                timeframe=timeframe,
                age_bars=int(
                    pattern.get(
                        "age_bars",
                        0,
                    )
                    or 0
                ),
                confirmed=bool(
                    pattern.get(
                        "confirmed",
                        True,
                    )
                ),
                bucket=CORRELATION_BUCKETS[
                    "chart_pattern"
                ],
            )
        )

    return evidence


# ---------------------------------------------------------------------------
# Order Flow -> Evidence
# ---------------------------------------------------------------------------
def evidence_from_order_flow(
    order_flow: Optional[Dict] = None,
    timeframe: Optional[str] = None,
    minimum_trade_count: int = 20,
    minimum_abs_score: float = 8.0,
) -> List[Evidence]:
    """Convert Order Flow / Delta analysis into explicit Evidence."""
    evidence: List[Evidence] = []

    if not order_flow:
        return evidence

    trade_count = int(
        order_flow.get(
            "trade_count",
            0,
        )
        or 0
    )

    if trade_count < minimum_trade_count:
        return evidence

    raw_ratio = float(
        order_flow.get(
            "delta_ratio",
            0.0,
        )
        or 0.0
    )

    delta_score = (
        raw_ratio
        * 100.0
    )

    if abs(
        delta_score
    ) < minimum_abs_score:
        return evidence

    delta_score = max(
        -100.0,
        min(
            100.0,
            delta_score,
        ),
    )

    direction = (
        "bullish"
        if delta_score > 0
        else "bearish"
    )

    evidence.append(
        Evidence(
            source="order_flow",
            direction=direction,
            strength=abs(
                delta_score
            ),
            timeframe=timeframe,
            age_bars=0,
            confirmed=True,
            bucket=CORRELATION_BUCKETS[
                "order_flow"
            ],
        )
    )

    return evidence


# ---------------------------------------------------------------------------
# Liquidity -> Evidence
# ---------------------------------------------------------------------------
def evidence_from_liquidity(
    liquidity: Optional[Dict] = None,
    timeframe: Optional[str] = None,
    minimum_levels: int = 2,
    minimum_abs_score: float = 8.0,
) -> List[Evidence]:
    """Convert order-book liquidity imbalance into explicit Evidence."""
    evidence: List[Evidence] = []

    if not liquidity:
        return evidence

    level_count = int(
        liquidity.get(
            "level_count",
            0,
        )
        or 0
    )

    if level_count < minimum_levels:
        return evidence

    raw_ratio = float(
        liquidity.get(
            "imbalance_ratio",
            0.0,
        )
        or 0.0
    )

    liquidity_score = (
        raw_ratio
        * 100.0
    )

    if abs(
        liquidity_score
    ) < minimum_abs_score:
        return evidence

    liquidity_score = max(
        -100.0,
        min(
            100.0,
            liquidity_score,
        ),
    )

    direction = (
        "bullish"
        if liquidity_score > 0
        else "bearish"
    )

    evidence.append(
        Evidence(
            source="liquidity",
            direction=direction,
            strength=abs(
                liquidity_score
            ),
            timeframe=timeframe,
            age_bars=0,
            confirmed=True,
            bucket=CORRELATION_BUCKETS[
                "liquidity"
            ],
        )
    )

    return evidence


# ---------------------------------------------------------------------------
# Futures Positioning -> Evidence
# ---------------------------------------------------------------------------
def evidence_from_futures_positioning(
    futures_positioning: Optional[Dict] = None,
    timeframe: Optional[str] = None,
    minimum_abs_score: float = 8.0,
) -> List[Evidence]:
    """Convert OI + Funding positioning analysis into Evidence."""
    evidence: List[Evidence] = []

    if not futures_positioning:
        return evidence

    raw_score = float(
        futures_positioning.get(
            "positioning_score",
            0.0,
        )
        or 0.0
    )

    if abs(
        raw_score
    ) < minimum_abs_score:
        return evidence

    positioning_score = max(
        -100.0,
        min(
            100.0,
            raw_score,
        ),
    )

    direction = (
        "bullish"
        if positioning_score > 0
        else "bearish"
    )

    confirmed = (
        futures_positioning.get(
            "current_open_interest"
        )
        is not None
        and (
            futures_positioning.get(
                "previous_open_interest"
            )
            is not None
            or futures_positioning.get(
                "latest_funding_rate"
            )
            is not None
        )
    )

    evidence.append(
        Evidence(
            source="futures_positioning",
            direction=direction,
            strength=abs(
                positioning_score
            ),
            timeframe=timeframe,
            age_bars=0,
            confirmed=bool(
                confirmed
            ),
            bucket=CORRELATION_BUCKETS[
                "futures_positioning"
            ],
        )
    )

    return evidence


# ---------------------------------------------------------------------------
# Liquidation -> Evidence
# ---------------------------------------------------------------------------
def evidence_from_liquidation(
    liquidation: Optional[Dict] = None,
    timeframe: Optional[str] = None,
    minimum_events: int = 1,
    minimum_abs_score: float = 8.0,
) -> List[Evidence]:
    """Convert liquidation analysis into explicit Evidence.

    BUY liquidation:
        short positions liquidated -> bullish pressure

    SELL liquidation:
        long positions liquidated -> bearish pressure

    The liquidation engine already performs the directional interpretation,
    so Confluence consumes only its bounded `liquidation_imbalance_ratio`
    through the normalized `liquidation_score` convention.
    """
    evidence: List[Evidence] = []

    if not liquidation:
        return evidence

    event_count = int(
        liquidation.get(
            "event_count",
            0,
        )
        or 0
    )

    if event_count < minimum_events:
        return evidence

    raw_ratio = float(
        liquidation.get(
            "liquidation_imbalance_ratio",
            0.0,
        )
        or 0.0
    )

    liquidation_score = (
        raw_ratio
        * 100.0
    )

    if abs(
        liquidation_score
    ) < minimum_abs_score:
        return evidence

    liquidation_score = max(
        -100.0,
        min(
            100.0,
            liquidation_score,
        ),
    )

    direction = (
        "bullish"
        if liquidation_score > 0
        else "bearish"
    )

    evidence.append(
        Evidence(
            source="liquidation",
            direction=direction,
            strength=abs(
                liquidation_score
            ),
            timeframe=timeframe,
            age_bars=0,
            confirmed=True,
            bucket=CORRELATION_BUCKETS[
                "liquidation"
            ],
        )
    )

    return evidence


# ---------------------------------------------------------------------------
# MTF -> Evidence
# ---------------------------------------------------------------------------
def evidence_from_mtf(
    mtf_evidence: Optional[List[Dict]] = None,
    timeframe: Optional[str] = None,
) -> List[Evidence]:
    """Convert MTF evidence dictionaries into Evidence objects."""
    evidence: List[Evidence] = []

    for item in (
        mtf_evidence or []
    ):
        direction = item.get(
            "direction",
            "neutral",
        )

        if direction not in (
            "bullish",
            "bearish",
        ):
            continue

        strength = float(
            item.get(
                "strength",
                0,
            )
            or 0
        )

        if strength <= 0:
            continue

        source = str(
            item.get(
                "source",
                "mtf",
            )
        )

        bucket = item.get(
            "bucket",
            CORRELATION_BUCKETS.get(
                source,
                "mtf",
            ),
        )

        evidence.append(
            Evidence(
                source=source,
                direction=direction,
                strength=min(
                    100.0,
                    strength,
                ),
                timeframe=item.get(
                    "timeframe",
                    timeframe,
                ),
                age_bars=int(
                    item.get(
                        "age_bars",
                        0,
                    )
                    or 0
                ),
                confirmed=bool(
                    item.get(
                        "confirmed",
                        True,
                    )
                ),
                bucket=bucket,
            )
        )

    return evidence


# ---------------------------------------------------------------------------
# Preparation
# ---------------------------------------------------------------------------
def _prepare_evidence(
    evidence: Iterable[Evidence],
) -> List[Evidence]:
    return [
        with_effective_strength(
            item
        )
        for item in evidence
    ]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
def _best_in_bucket(
    evidence: Iterable[Evidence],
) -> List[Evidence]:
    """Keep one representative per bucket, independent of iterable order.

    Confirmed evidence takes precedence, then effective strength and recency.
    Equal-rank opposing directions abstain within that bucket; a neutral zero
    strength marker records the conflict without inventing directional support.
    """
    grouped: Dict[str, List[Evidence]] = {}
    for item in evidence:
        grouped.setdefault(item.bucket or item.source, []).append(item)
    selected = []
    for bucket, items in sorted(grouped.items()):
        rank = lambda item: (item.confirmed, item.strength, -item.age_bars)
        highest = max(map(rank, items))
        tied = sorted((item for item in items if rank(item) == highest),
                      key=lambda item: (item.source, item.timeframe or "", item.direction))
        winner = tied[0]
        directions = {item.direction for item in tied} - {"neutral"}
        if len(directions) > 1:
            winner = replace(winner, source="bucket_conflict:" + bucket,
                             direction="neutral", strength=0.0)
        selected.append(winner)
    return selected


def deduplicate_evidence(
    evidence: Iterable[Evidence],
) -> List[Evidence]:
    return _best_in_bucket(
        _prepare_evidence(
            evidence
        )
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def _direction_counts(
    evidence: Iterable[Evidence],
) -> Dict[str, float]:
    bullish = 0.0
    bearish = 0.0

    for item in evidence:
        if item.direction == "bullish":
            bullish += item.strength

        elif item.direction == "bearish":
            bearish += item.strength

    return {
        "bullish": round(
            bullish,
            2,
        ),
        "bearish": round(
            bearish,
            2,
        ),
    }


def build_confluence(
    evidence: Iterable[Evidence],
) -> Dict:
    original = list(
        evidence
    )

    deduplicated = (
        deduplicate_evidence(
            original
        )
    )

    totals = _direction_counts(
        deduplicated
    )

    bullish = totals[
        "bullish"
    ]

    bearish = totals[
        "bearish"
    ]

    if bullish > bearish:
        direction = "bullish"

    elif bearish > bullish:
        direction = "bearish"

    else:
        direction = "neutral"

    supporting = [
        item
        for item in deduplicated
        if direction != "neutral" and item.direction == direction
    ]

    opposing = [
        item
        for item in deduplicated
        if (
            direction
            != "neutral"
            and item.direction != "neutral"
            and item.direction
            != direction
        )
    ]

    total_strength = (
        bullish
        + bearish
    )

    agreement_ratio = (
        bullish
        / total_strength
        if (
            direction == "bullish"
            and total_strength > 0
        )
        else (
            bearish
            / total_strength
            if (
                direction == "bearish"
                and total_strength > 0
            )
            else 0.0
        )
    )

    conflict_ratio = (
        len(opposing)
        / len(deduplicated)
        if deduplicated
        else 0.0
    )

    return {
        "direction": direction,

        "original_evidence_count": len(
            original
        ),

        "deduplicated_evidence_count": len(
            deduplicated
        ),

        "bullish_strength": bullish,

        "bearish_strength": bearish,

        "supporting_count": len(
            supporting
        ),

        "opposing_count": len(
            opposing
        ),

        "agreement_ratio": round(
            agreement_ratio,
            3,
        ),

        "conflict_ratio": round(
            conflict_ratio,
            3,
        ),

        "recency_half_life_bars": (
            RECENCY_HALF_LIFE_BARS
        ),

        "evidence": [
            asdict(item)
            for item in deduplicated
        ],
    }


# ---------------------------------------------------------------------------
# Public convenience API
# ---------------------------------------------------------------------------
def confluence_from_scores(
    scores: Dict[str, float],
    timeframe: Optional[str] = None,
    threshold: float = 8.0,
    candle_patterns: Optional[List[Dict]] = None,
    chart_patterns: Optional[List[Dict]] = None,
    mtf_evidence: Optional[List[Dict]] = None,
    order_flow: Optional[Dict] = None,
    liquidity: Optional[Dict] = None,
    futures_positioning: Optional[Dict] = None,
    liquidation: Optional[Dict] = None,
) -> Dict:
    """Build confluence from scores plus direct evidence sources.

    Pattern, Order Flow, Liquidity, Futures Positioning and Liquidation are
    not taken from generic scores. They enter as dedicated evidence buckets.
    """
    evidence = evidence_from_scores(
        scores,
        timeframe=timeframe,
        threshold=threshold,
    )

    evidence.extend(
        evidence_from_patterns(
            candle_patterns=candle_patterns,
            chart_patterns=chart_patterns,
            timeframe=timeframe,
        )
    )

    evidence.extend(
        evidence_from_order_flow(
            order_flow=order_flow,
            timeframe=timeframe,
        )
    )

    evidence.extend(
        evidence_from_liquidity(
            liquidity=liquidity,
            timeframe=timeframe,
        )
    )

    evidence.extend(
        evidence_from_futures_positioning(
            futures_positioning=futures_positioning,
            timeframe=timeframe,
        )
    )

    evidence.extend(
        evidence_from_liquidation(
            liquidation=liquidation,
            timeframe=timeframe,
        )
    )

    evidence.extend(
        evidence_from_mtf(
            mtf_evidence=mtf_evidence,
            timeframe=timeframe,
        )
    )

    return build_confluence(
        evidence
    )
