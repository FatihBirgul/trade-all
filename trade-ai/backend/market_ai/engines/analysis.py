"""Analysis aggregation engine.

Combines deterministic outputs from technical indicators, market structure,
candlestick patterns, chart patterns, volume, volatility, news sentiment,
optional Order Flow / Delta, optional Liquidity / Order Book evidence,
optional Futures Positioning, optional Liquidation evidence, and optional MTF
evidence into a single structured analysis.

The final score is an analytical heuristic, NOT a statistically proven
probability. Calibration can be added later from backtesting.

Current architecture:
- Weighted composite is built only from core current-timeframe pillars.
- Candlestick and chart-pattern evidence enter through Confluence directly.
- Order Flow / Delta enters through Confluence directly.
- Liquidity / Order Book enters through Confluence directly.
- Futures Positioning enters through Confluence directly.
- Liquidation enters through Confluence directly.
- MTF enters through Confluence directly.
- Evidence/Confluence is the single source for agreement/conflict gating.
- Trend/structure correlation is de-duplicated.
- Volume direction is independent from trend direction.
- Volatility is quality/risk context, not directional evidence.
- Pattern information is not counted in both composite and Confluence.
- Order Flow is not counted in both composite and Confluence.
- Liquidity is not counted in both composite and Confluence.
- Futures Positioning is not counted in both composite and Confluence.
- Liquidation is not counted in both composite and Confluence.
- Confidence has no artificial +20 floor.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .confluence import confluence_from_scores


def _clip(
    v,
    lo=-100,
    hi=100,
):
    return max(
        lo,
        min(
            hi,
            v,
        ),
    )


def _trend_score(
    ind: Dict,
) -> float:
    price = ind.get(
        "price"
    )

    score = 0.0

    for ema_key, w in [
        ("ema20", 12),
        ("ema50", 12),
        ("ema100", 10),
        ("ema200", 16),
    ]:
        e = ind.get(
            ema_key
        )

        if (
            e is not None
            and price is not None
        ):
            score += (
                w
                if price > e
                else -w
            )

    e20 = ind.get(
        "ema20"
    )

    e50 = ind.get(
        "ema50"
    )

    e200 = ind.get(
        "ema200"
    )

    if (
        e20 is not None
        and e50 is not None
        and e200 is not None
    ):
        if e20 > e50 > e200:
            score += 20

        elif e20 < e50 < e200:
            score -= 20

    return _clip(
        score
    )


def _momentum_score(
    ind: Dict,
) -> float:
    score = 0.0

    rsi = ind.get(
        "rsi14"
    )

    # A partial momentum snapshot must not turn a contrary RSI into a
    # stronger confirmation merely because the RSI value is missing.
    if rsi is None:
        return 0.0

    if rsi > 70:
        score -= 10

    elif rsi > 55:
        score += 22

    elif rsi < 30:
        score += 8

    elif rsi < 45:
        score -= 22

    hist = ind.get(
        "macd_hist"
    )

    if hist is not None:
        if hist > 0:
            score += 25
        elif hist < 0:
            score -= 25

    k = ind.get(
        "stoch_rsi_k"
    )

    d = ind.get(
        "stoch_rsi_d"
    )

    if (
        k is not None
        and d is not None
    ):
        if (
            k > d
            and k < 80
        ):
            score += 15

        elif (
            k < d
            and k > 20
        ):
            score -= 15

    return _clip(
        score
    )


def _volume_score(
    ind: Dict,
) -> float:
    ratio = (
        ind.get(
            "volume_ratio"
        )
        or 1.0
    )

    direction = ind.get(
        "volume_direction",
        0,
    )

    if direction not in (
        -1,
        0,
        1,
    ):
        direction = 0

    if direction == 0:
        return 0.0

    if ratio > 1.3:
        magnitude = 30.0

    elif ratio > 1.0:
        magnitude = 12.0

    elif ratio < 0.7:
        magnitude = 5.0

    else:
        magnitude = 8.0

    return _clip(
        magnitude * direction
    )


def _volatility_score(
    ind: Dict,
) -> float:
    """Return volatility magnitude for compatibility.

    This is context only. It is NOT included in directional weighting.
    """
    atrp = ind.get(
        "atr_pct"
    )

    if atrp is None:
        return 0

    if atrp > 6:
        return 80

    if atrp > 3:
        return 55

    if atrp > 1.5:
        return 35

    return 20


def _volatility_regime(
    ind: Dict,
) -> str:
    """Classify current ATR% into a simple volatility regime."""
    atrp = ind.get(
        "atr_pct"
    )

    if atrp is None:
        return "unknown"

    if atrp > 6:
        return "extreme"

    if atrp > 3:
        return "high"

    if atrp > 1.5:
        return "normal"

    return "low"


def _volatility_rr_floor(
    regime: str,
) -> float:
    """Return minimum acceptable RR for the current volatility regime."""
    if regime == "extreme":
        return 1.5

    if regime == "high":
        return 1.2

    return 1.0


def _volatility_confidence_multiplier(
    regime: str,
) -> float:
    """Return a bounded confidence modifier for volatility regime."""
    if regime == "extreme":
        return 0.85

    if regime == "high":
        return 0.95

    return 1.0


def _pattern_score(
    candles: List[Dict],
    charts: List[Dict],
) -> float:
    """Legacy aggregate pattern score.

    Kept for API/backward compatibility and display only.

    IMPORTANT:
    This score is NOT part of the weighted directional composite anymore.
    Actual candlestick/chart pattern objects are passed directly to
    Confluence, where age/confirmation/recency are handled.
    """
    score = 0.0

    for p in candles:
        strength = p.get(
            "strength",
            0,
        )

        w = (
            strength
            / 100
            * 22
        )

        if p.get(
            "classification"
        ) == "bullish":
            score += w

        elif p.get(
            "classification"
        ) == "bearish":
            score -= w

    for p in charts:
        confidence = p.get(
            "confidence",
            0,
        )

        w = (
            confidence
            / 100
            * 30
        )

        if p.get(
            "classification"
        ) == "bullish":
            score += w

        elif p.get(
            "classification"
        ) == "bearish":
            score -= w

    return _clip(
        score
    )


def _structure_score(
    structure: Dict,
) -> float:
    if structure.get(
        "label"
    ) == "uptrend":
        return 60

    if structure.get(
        "label"
    ) == "downtrend":
        return -60

    return 0


def _confidence_from_confluence(
    final_score: float,
    confluence: Dict,
    volatility_multiplier: float,
) -> float:
    """Calculate confidence from the single Confluence source."""
    magnitude = abs(
        final_score
    )

    active_count = int(
        confluence.get(
            "deduplicated_evidence_count",
            0,
        )
    )

    supporting_count = int(
        confluence.get(
            "supporting_count",
            0,
        )
    )

    opposing_count = int(
        confluence.get(
            "opposing_count",
            0,
        )
    )

    agreement_ratio = float(
        confluence.get(
            "agreement_ratio",
            0.0,
        )
    )

    if active_count <= 0:
        agreement_multiplier = 0.5

    else:
        agreement_multiplier = (
            0.55
            + 0.45 * agreement_ratio
        )

    conflict_multiplier = max(
        0.55,
        1.0
        - 0.12 * opposing_count,
    )

    support_bonus = min(
        1.10,
        1.0
        + max(
            0,
            supporting_count - 1,
        )
        * 0.03,
    )

    confidence = (
        magnitude
        * agreement_multiplier
        * conflict_multiplier
        * support_bonus
        * volatility_multiplier
    )

    return round(
        _clip(
            confidence,
            lo=0,
            hi=100,
        ),
        1,
    )


def _empty_zones() -> Dict:
    return {
        "entry_low": None,
        "entry_high": None,
        "target_1": None,
        "target_2": None,
        "invalidation": None,
        "risk_reward": None,
    }


def build_zones(
    direction: str,
    price: float,
    support,
    resistance,
    atr: float,
) -> Dict:
    """Build executable trade zones with balanced ATR/level geometry.

    Bullish:
        entry_low <= entry_high < target_1 < target_2
        invalidation < entry_low

    Bearish:
        target_2 < target_1 < entry_low <= entry_high < invalidation

    Design goals:
    - Do not let a distant support create disproportionate risk.
    - Do not let a very close resistance create an unusably small TP1.
    - Use nearby market levels when useful.
    - Fall back to ATR-based distances when levels are absent or unsuitable.
    """
    price = float(price)

    atr = float(
        atr
        or price * 0.01
    )

    if atr <= 0:
        atr = price * 0.01

    sup = sorted(
        [
            float(
                s["level"]
            )
            for s in (
                support or []
            )
            if s.get(
                "level"
            ) is not None
        ],
        reverse=True,
    )

    res = sorted(
        [
            float(
                r["level"]
            )
            for r in (
                resistance or []
            )
            if r.get(
                "level"
            ) is not None
        ]
    )

    def r(v):
        return (
            round(
                float(v),
                4,
            )
            if v is not None
            else None
        )

    empty = _empty_zones()

    if direction == "neutral":
        return empty

    if direction == "bullish":
        entry_high = price

        nearby_supports = [
            level
            for level in sup
            if level < price
            and (
                price - level
                <= atr * 2.0
            )
        ]

        if nearby_supports:
            entry_low = max(
                nearby_supports
            )
        else:
            entry_low = (
                price
                - atr * 0.50
            )

        entry_low = max(
            entry_low,
            price - atr * 0.75,
        )

        invalidation = (
            entry_low
            - atr * 0.75
        )

        invalidation = min(
            invalidation,
            price - atr * 0.50,
        )

        nearby_resistances = [
            level
            for level in res
            if level > price
        ]

        min_tp1_distance = max(
            atr * 1.0,
            price * 0.001,
        )

        target_1 = None

        for level in nearby_resistances:
            if (
                level - price
                >= min_tp1_distance
            ):
                target_1 = level
                break

        if target_1 is None:
            target_1 = (
                price
                + atr * 2.0
            )

        if (
            target_1 - price
            < atr * 1.0
        ):
            target_1 = (
                price
                + atr * 2.0
            )

        target_2 = None

        for level in nearby_resistances:
            if (
                level > target_1
                and level - target_1 >= atr * 0.50
            ):
                target_2 = level
                break

        if target_2 is None:
            target_2 = max(
                target_1 + atr * 1.5,
                price + atr * 4.0,
            )

        target_1 = max(
            target_1,
            price + atr * 1.0,
        )

        target_2 = max(
            target_2,
            target_1 + atr * 0.50,
        )

        risk = (
            price
            - invalidation
        )

        reward = (
            target_1
            - price
        )

    elif direction == "bearish":
        entry_low = price

        nearby_resistances = [
            level
            for level in res
            if level > price
            and (
                level - price
                <= atr * 2.0
            )
        ]

        if nearby_resistances:
            entry_high = min(
                nearby_resistances
            )
        else:
            entry_high = (
                price
                + atr * 0.50
            )

        entry_high = min(
            entry_high,
            price + atr * 0.75,
        )

        invalidation = (
            entry_high
            + atr * 0.75
        )

        invalidation = max(
            invalidation,
            price + atr * 0.50,
        )

        nearby_supports = [
            level
            for level in sup
            if level < price
        ]

        min_tp1_distance = max(
            atr * 1.0,
            price * 0.001,
        )

        target_1 = None

        for level in nearby_supports:
            if (
                price - level
                >= min_tp1_distance
            ):
                target_1 = level
                break

        if target_1 is None:
            target_1 = (
                price
                - atr * 2.0
            )

        if (
            price - target_1
            < atr * 1.0
        ):
            target_1 = (
                price
                - atr * 2.0
            )

        target_2 = None

        for level in nearby_supports:
            if (
                level < target_1
                and target_1 - level >= atr * 0.50
            ):
                target_2 = level
                break

        if target_2 is None:
            target_2 = min(
                target_1 - atr * 1.5,
                price - atr * 4.0,
            )

        target_1 = min(
            target_1,
            price - atr * 1.0,
        )

        target_2 = min(
            target_2,
            target_1 - atr * 0.50,
        )

        risk = (
            invalidation
            - price
        )

        reward = (
            price
            - target_1
        )

    else:
        return empty

    rr = (
        round(
            reward / risk,
            2,
        )
        if risk > 0
        and reward > 0
        else None
    )

    return {
        "entry_low": r(
            min(
                entry_low,
                entry_high,
            )
        ),
        "entry_high": r(
            max(
                entry_low,
                entry_high,
            )
        ),
        "target_1": r(
            target_1
        ),
        "target_2": r(
            target_2
        ),
        "invalidation": r(
            invalidation
        ),
        "risk_reward": rr,
    }


def aggregate(
    technical: Dict,
    candle_patterns: List[Dict],
    chart_patterns: List[Dict],
    news: Dict,
    mtf: Optional[Dict] = None,
    order_flow: Optional[Dict] = None,
    liquidity: Optional[Dict] = None,
    futures_positioning: Optional[Dict] = None,
    liquidation: Optional[Dict] = None,
) -> Dict:
    """Aggregate current-timeframe analysis.

    MTF, Order Flow, Liquidity, Futures Positioning and Liquidation are
    evidence-layer inputs.

    None of them are added to the weighted directional composite.
    """
    ind = technical[
        "indicators"
    ]

    structure = technical[
        "structure"
    ]

    levels = technical[
        "levels"
    ]

    price = technical[
        "price"
    ]

    timeframe = technical.get(
        "timeframe",
        ind.get(
            "timeframe"
        ),
    )

    trend = _trend_score(
        ind
    )

    momentum = _momentum_score(
        ind
    )

    volume = _volume_score(
        ind
    )

    volatility = _volatility_score(
        ind
    )

    volatility_regime = _volatility_regime(
        ind
    )

    volatility_rr_floor = _volatility_rr_floor(
        volatility_regime
    )

    volatility_confidence_multiplier = (
        _volatility_confidence_multiplier(
            volatility_regime
        )
    )

    pattern = _pattern_score(
        candle_patterns,
        chart_patterns,
    )

    struct = _structure_score(
        structure
    )

    news_score = (
        float(
            news
            .get(
                "sentiment",
                {},
            )
            .get(
                "score",
                0.0,
            )
        )
        if news
        else 0.0
    )

    scores = {
        "trend": round(
            trend,
            1,
        ),
        "momentum": round(
            momentum,
            1,
        ),
        "volume": round(
            volume,
            1,
        ),
        "volatility": round(
            volatility,
            1,
        ),
        "pattern": round(
            pattern,
            1,
        ),
        "structure": round(
            struct,
            1,
        ),
        "news": round(
            news_score,
            1,
        ),
    }

    # -----------------------------------------------------------------------
    # Directional composite.
    #
    # Pattern, Order Flow, Liquidity, Futures Positioning, Liquidation and MTF
    # are deliberately excluded.
    # -----------------------------------------------------------------------
    weights = {
        "trend": 0.35,
        "momentum": 0.275,
        "volume": 0.15,
        "structure": 0.175,
        "news": 0.05,
    }

    final = sum(
        scores[k] * w
        for k, w in weights.items()
    )

    final = _clip(
        final
    )

    if final > 15:
        composite_direction = "bullish"

    elif final < -15:
        composite_direction = "bearish"

    else:
        composite_direction = "neutral"

    # -----------------------------------------------------------------------
    # Confluence evidence inputs.
    # -----------------------------------------------------------------------
    mtf_evidence = []

    if mtf:
        mtf_evidence = mtf.get(
            "evidence",
            []
        )

    confluence = confluence_from_scores(
        scores,
        timeframe=timeframe,
        threshold=8.0,
        candle_patterns=candle_patterns,
        chart_patterns=chart_patterns,
        mtf_evidence=mtf_evidence,
        order_flow=order_flow,
        liquidity=liquidity,
        futures_positioning=futures_positioning,
        liquidation=liquidation,
    )

    confluence_direction = confluence.get(
        "direction",
        "neutral",
    )

    original_evidence_count = int(
        confluence.get(
            "original_evidence_count",
            0,
        )
    )

    deduplicated_evidence_count = int(
        confluence.get(
            "deduplicated_evidence_count",
            0,
        )
    )

    supporting_count = int(
        confluence.get(
            "supporting_count",
            0,
        )
    )

    opposing_count = int(
        confluence.get(
            "opposing_count",
            0,
        )
    )

    # -----------------------------------------------------------------------
    # Single decision gate.
    # -----------------------------------------------------------------------
    min_supporting_evidence = 2

    same_direction = (
        composite_direction
        in (
            "bullish",
            "bearish",
        )
        and composite_direction
        == confluence_direction
    )

    gate_passed = (
        same_direction
        and ind.get("rsi14") is not None
        and supporting_count
        >= min_supporting_evidence
        and supporting_count
        > opposing_count
    )

    if gate_passed:
        direction = composite_direction

    else:
        direction = "neutral"

    confidence = _confidence_from_confluence(
        final,
        confluence,
        volatility_confidence_multiplier,
    )

    if not gate_passed:
        confidence = round(
            confidence * 0.50,
            1,
        )

    atr = (
        ind.get(
            "atr14"
        )
        or price * 0.01
    )

    zones = build_zones(
        direction,
        price,
        levels.get(
            "support"
        ),
        levels.get(
            "resistance"
        ),
        atr,
    )

    rr = zones.get(
        "risk_reward"
    )

    # -----------------------------------------------------------------------
    # Volatility-aware RR gate.
    # -----------------------------------------------------------------------
    rr_gate_passed = True

    if direction in (
        "bullish",
        "bearish",
    ):
        if (
            rr is None
            or rr < volatility_rr_floor
        ):
            rr_gate_passed = False

            direction = "neutral"

            neutral_zones = _empty_zones()

            neutral_zones[
                "risk_reward"
            ] = rr

            zones = neutral_zones

    # -----------------------------------------------------------------------
    # Order Flow summary for API/UI.
    # -----------------------------------------------------------------------
    order_flow_summary = {
        "available": bool(
            order_flow
        ),
        "trade_count": (
            int(
                order_flow.get(
                    "trade_count",
                    0,
                )
                or 0
            )
            if order_flow
            else 0
        ),
        "delta": (
            float(
                order_flow.get(
                    "delta",
                    0.0,
                )
                or 0.0
            )
            if order_flow
            else 0.0
        ),
        "delta_ratio": (
            float(
                order_flow.get(
                    "delta_ratio",
                    0.0,
                )
                or 0.0
            )
            if order_flow
            else 0.0
        ),
        "buy_pressure": (
            float(
                order_flow.get(
                    "buy_pressure",
                    0.0,
                )
                or 0.0
            )
            if order_flow
            else 0.0
        ),
        "sell_pressure": (
            float(
                order_flow.get(
                    "sell_pressure",
                    0.0,
                )
                or 0.0
            )
            if order_flow
            else 0.0
        ),
        "dominant_side": (
            order_flow.get(
                "dominant_side",
                "neutral",
            )
            if order_flow
            else "neutral"
        ),
    }

    # -----------------------------------------------------------------------
    # Liquidity summary for API/UI.
    # -----------------------------------------------------------------------
    liquidity_summary = {
        "available": bool(
            liquidity
        ),
        "level_count": (
            int(
                liquidity.get(
                    "level_count",
                    0,
                )
                or 0
            )
            if liquidity
            else 0
        ),
        "bid_volume": (
            float(
                liquidity.get(
                    "bid_volume",
                    0.0,
                )
                or 0.0
            )
            if liquidity
            else 0.0
        ),
        "ask_volume": (
            float(
                liquidity.get(
                    "ask_volume",
                    0.0,
                )
                or 0.0
            )
            if liquidity
            else 0.0
        ),
        "imbalance": (
            float(
                liquidity.get(
                    "imbalance",
                    0.0,
                )
                or 0.0
            )
            if liquidity
            else 0.0
        ),
        "imbalance_ratio": (
            float(
                liquidity.get(
                    "imbalance_ratio",
                    0.0,
                )
                or 0.0
            )
            if liquidity
            else 0.0
        ),
        "bid_pressure": (
            float(
                liquidity.get(
                    "bid_pressure",
                    0.0,
                )
                or 0.0
            )
            if liquidity
            else 0.0
        ),
        "ask_pressure": (
            float(
                liquidity.get(
                    "ask_pressure",
                    0.0,
                )
                or 0.0
            )
            if liquidity
            else 0.0
        ),
        "spread": (
            liquidity.get(
                "spread"
            )
            if liquidity
            else None
        ),
        "spread_pct": (
            liquidity.get(
                "spread_pct"
            )
            if liquidity
            else None
        ),
        "best_bid": (
            liquidity.get(
                "best_bid"
            )
            if liquidity
            else None
        ),
        "best_ask": (
            liquidity.get(
                "best_ask"
            )
            if liquidity
            else None
        ),
        "mid_price": (
            liquidity.get(
                "mid_price"
            )
            if liquidity
            else None
        ),
        "dominant_side": (
            liquidity.get(
                "dominant_side",
                "neutral",
            )
            if liquidity
            else "neutral"
        ),
    }

    # -----------------------------------------------------------------------
    # Futures Positioning summary for API/UI.
    # -----------------------------------------------------------------------
    futures_positioning_summary = {
        "available": bool(
            futures_positioning
        ),
        "current_open_interest": (
            float(
                futures_positioning.get(
                    "current_open_interest",
                    0.0,
                )
                or 0.0
            )
            if futures_positioning
            else 0.0
        ),
        "previous_open_interest": (
            (
                float(
                    futures_positioning.get(
                        "previous_open_interest"
                    )
                )
                if futures_positioning.get(
                    "previous_open_interest"
                )
                is not None
                else None
            )
            if futures_positioning
            else None
        ),
        "open_interest_change": (
            (
                float(
                    futures_positioning.get(
                        "open_interest_change"
                    )
                )
                if futures_positioning.get(
                    "open_interest_change"
                )
                is not None
                else None
            )
            if futures_positioning
            else None
        ),
        "open_interest_change_pct": (
            (
                float(
                    futures_positioning.get(
                        "open_interest_change_pct"
                    )
                )
                if futures_positioning.get(
                    "open_interest_change_pct"
                )
                is not None
                else None
            )
            if futures_positioning
            else None
        ),
        "latest_funding_rate": (
            (
                float(
                    futures_positioning.get(
                        "latest_funding_rate"
                    )
                )
                if futures_positioning.get(
                    "latest_funding_rate"
                )
                is not None
                else None
            )
            if futures_positioning
            else None
        ),
        "open_interest_score": (
            float(
                futures_positioning.get(
                    "open_interest_score",
                    0.0,
                )
                or 0.0
            )
            if futures_positioning
            else 0.0
        ),
        "funding_score": (
            float(
                futures_positioning.get(
                    "funding_score",
                    0.0,
                )
                or 0.0
            )
            if futures_positioning
            else 0.0
        ),
        "positioning_score": (
            float(
                futures_positioning.get(
                    "positioning_score",
                    0.0,
                )
                or 0.0
            )
            if futures_positioning
            else 0.0
        ),
        "dominant_side": (
            futures_positioning.get(
                "dominant_side",
                "neutral",
            )
            if futures_positioning
            else "neutral"
        ),
        "positioning_quality": (
            futures_positioning.get(
                "positioning_quality",
                "unavailable",
            )
            if futures_positioning
            else "unavailable"
        ),
        "funding_sample_count": (
            int(
                futures_positioning.get(
                    "funding_sample_count",
                    0,
                )
                or 0
            )
            if futures_positioning
            else 0
        ),
        "price_change_pct": (
            (
                float(
                    futures_positioning.get(
                        "price_change_pct"
                    )
                )
                if futures_positioning.get(
                    "price_change_pct"
                )
                is not None
                else None
            )
            if futures_positioning
            else None
        ),
    }

    # -----------------------------------------------------------------------
    # Liquidation summary for API/UI.
    # -----------------------------------------------------------------------
    liquidation_summary = {
        "available": bool(
            liquidation
        ),
        "event_count": (
            int(
                liquidation.get(
                    "event_count",
                    0,
                )
                or 0
            )
            if liquidation
            else 0
        ),
        "buy_liquidation_count": (
            int(
                liquidation.get(
                    "buy_liquidation_count",
                    0,
                )
                or 0
            )
            if liquidation
            else 0
        ),
        "sell_liquidation_count": (
            int(
                liquidation.get(
                    "sell_liquidation_count",
                    0,
                )
                or 0
            )
            if liquidation
            else 0
        ),
        "short_liquidation_count": (
            int(
                liquidation.get(
                    "short_liquidation_count",
                    0,
                )
                or 0
            )
            if liquidation
            else 0
        ),
        "long_liquidation_count": (
            int(
                liquidation.get(
                    "long_liquidation_count",
                    0,
                )
                or 0
            )
            if liquidation
            else 0
        ),
        "short_liquidation_notional": (
            float(
                liquidation.get(
                    "short_liquidation_notional",
                    0.0,
                )
                or 0.0
            )
            if liquidation
            else 0.0
        ),
        "long_liquidation_notional": (
            float(
                liquidation.get(
                    "long_liquidation_notional",
                    0.0,
                )
                or 0.0
            )
            if liquidation
            else 0.0
        ),
        "total_liquidation_notional": (
            float(
                liquidation.get(
                    "total_liquidation_notional",
                    0.0,
                )
                or 0.0
            )
            if liquidation
            else 0.0
        ),
        "liquidation_imbalance": (
            float(
                liquidation.get(
                    "liquidation_imbalance",
                    0.0,
                )
                or 0.0
            )
            if liquidation
            else 0.0
        ),
        "liquidation_imbalance_ratio": (
            float(
                liquidation.get(
                    "liquidation_imbalance_ratio",
                    0.0,
                )
                or 0.0
            )
            if liquidation
            else 0.0
        ),
        "short_liquidation_pressure": (
            float(
                liquidation.get(
                    "short_liquidation_pressure",
                    0.0,
                )
                or 0.0
            )
            if liquidation
            else 0.0
        ),
        "long_liquidation_pressure": (
            float(
                liquidation.get(
                    "long_liquidation_pressure",
                    0.0,
                )
                or 0.0
            )
            if liquidation
            else 0.0
        ),
        "dominant_side": (
            liquidation.get(
                "dominant_side",
                "neutral",
            )
            if liquidation
            else "neutral"
        ),
        "largest_liquidation": (
            liquidation.get(
                "largest_liquidation"
            )
            if liquidation
            else None
        ),
        "first_timestamp": (
            liquidation.get(
                "first_timestamp"
            )
            if liquidation
            else None
        ),
        "last_timestamp": (
            liquidation.get(
                "last_timestamp"
            )
            if liquidation
            else None
        ),
    }

    # -----------------------------------------------------------------------
    # MTF summary for API/UI.
    # -----------------------------------------------------------------------
    mtf_summary = (
        mtf
        if mtf
        else {
            "direction": "neutral",
            "current_timeframe": timeframe,
            "alignment_ratio": 0.0,
            "conflict_ratio": 0.0,
            "supporting_count": 0,
            "opposing_count": 0,
            "higher_timeframe_bias": {},
            "higher_timeframe_alignment": {},
            "lower_timeframe_confirmation": {},
            "evidence": [],
        }
    )

    return {
        "direction": direction,

        "confidence": confidence,

        "final_score": round(
            final,
            1,
        ),

        "scores": scores,

        "zones": zones,

        "quality": {
            "volatility_regime": (
                volatility_regime
            ),

            "atr_pct": ind.get(
                "atr_pct"
            ),

            "min_risk_reward": (
                volatility_rr_floor
            ),

            "volatility_confidence_multiplier": (
                volatility_confidence_multiplier
            ),

            "minimum_supporting_evidence": (
                min_supporting_evidence
            ),

            "gate_passed": gate_passed,

            "rr_gate_passed": (
                rr_gate_passed
            ),

            "composite_direction": (
                composite_direction
            ),

            "confluence_direction": (
                confluence_direction
            ),

            "original_evidence_count": (
                original_evidence_count
            ),

            "deduplicated_evidence_count": (
                deduplicated_evidence_count
            ),

            "supporting_count": (
                supporting_count
            ),

            "opposing_count": (
                opposing_count
            ),

            "agreement_ratio": float(
                confluence.get(
                    "agreement_ratio",
                    0.0,
                )
            ),

            "conflict_ratio": float(
                confluence.get(
                    "conflict_ratio",
                    0.0,
                )
            ),

            "order_flow": (
                order_flow_summary
            ),

            "liquidity": (
                liquidity_summary
            ),

            "futures_positioning": (
                futures_positioning_summary
            ),

            "liquidation": (
                liquidation_summary
            ),

            "mtf": mtf_summary,

            "confluence": {
                "direction": confluence.get(
                    "direction",
                    "neutral",
                ),

                "original_evidence_count": (
                    original_evidence_count
                ),

                "deduplicated_evidence_count": (
                    deduplicated_evidence_count
                ),

                "bullish_strength": float(
                    confluence.get(
                        "bullish_strength",
                        0.0,
                    )
                ),

                "bearish_strength": float(
                    confluence.get(
                        "bearish_strength",
                        0.0,
                    )
                ),

                "supporting_count": (
                    supporting_count
                ),

                "opposing_count": (
                    opposing_count
                ),

                "agreement_ratio": float(
                    confluence.get(
                        "agreement_ratio",
                        0.0,
                    )
                ),

                "conflict_ratio": float(
                    confluence.get(
                        "conflict_ratio",
                        0.0,
                    )
                ),

                "recency_half_life_bars": int(
                    confluence.get(
                        "recency_half_life_bars",
                        8,
                    )
                ),

                "evidence": confluence.get(
                    "evidence",
                    [],
                ),
            },
        },

        "calibration": {
            "method": "heuristic_v1_6",

            "note": (
                "Analytical confidence derived from weighted technical "
                "components with structure de-duplication, independent "
                "volume direction, volatility-quality gating, a single "
                "Evidence/Confluence source for agreement and conflict, "
                "candlestick/chart-pattern recency and confirmation, "
                "multi-timeframe evidence, Order Flow/Delta evidence, "
                "Liquidity/Order Book evidence, Futures Positioning evidence "
                "based on Open Interest and Funding, and Liquidation evidence "
                "from Binance Futures force-order events. Pattern, Order Flow, "
                "Liquidity, Futures Positioning and Liquidation information "
                "are excluded from the weighted composite to prevent double "
                "counting. The confidence value is NOT a statistically "
                "proven probability. Thresholds remain pending backtest "
                "calibration."
            ),

            "sample_size": 0,
        },
    }
