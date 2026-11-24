"""Deterministic order-book liquidity analysis engine.

Consumes normalized Futures order-book depth and calculates bid/ask
liquidity, imbalance, spread, and directional pressure.

This module does not fetch market data and does not make trading decisions.
It produces a deterministic snapshot that can later become Confluence
Evidence.
"""
from __future__ import annotations

from typing import Dict, List, Optional


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


def _normalize_levels(
    levels: Optional[List[Dict]],
) -> List[Dict]:
    result = []

    for level in (
        levels or []
    ):
        price = _safe_float(
            level.get("price")
        )

        quantity = _safe_float(
            level.get("quantity")
        )

        if price <= 0 or quantity <= 0:
            continue

        result.append(
            {
                "price": price,
                "quantity": quantity,
            }
        )

    return result


def _notional(
    level: Dict,
) -> float:
    return (
        level["price"]
        * level["quantity"]
    )


def analyze(
    order_book: Optional[Dict],
) -> Dict:
    """Analyze normalized order-book depth.

    Returns:
        bid_volume
        ask_volume
        bid_notional
        ask_notional
        total_volume
        total_notional
        imbalance
        imbalance_ratio
        bid_pressure
        ask_pressure
        spread
        spread_pct
        best_bid
        best_ask
        mid_price
        dominant_side
        level_count
        timestamp
    """
    if not order_book:
        return {
            "bid_volume": 0.0,
            "ask_volume": 0.0,
            "bid_notional": 0.0,
            "ask_notional": 0.0,
            "total_volume": 0.0,
            "total_notional": 0.0,
            "imbalance": 0.0,
            "imbalance_ratio": 0.0,
            "bid_pressure": 0.0,
            "ask_pressure": 0.0,
            "spread": None,
            "spread_pct": None,
            "best_bid": None,
            "best_ask": None,
            "mid_price": None,
            "dominant_side": "neutral",
            "level_count": 0,
            "timestamp": None,
        }

    bids = _normalize_levels(
        order_book.get(
            "bids",
            [],
        )
    )

    asks = _normalize_levels(
        order_book.get(
            "asks",
            [],
        )
    )

    bid_volume = sum(
        level["quantity"]
        for level in bids
    )

    ask_volume = sum(
        level["quantity"]
        for level in asks
    )

    bid_notional = sum(
        _notional(level)
        for level in bids
    )

    ask_notional = sum(
        _notional(level)
        for level in asks
    )

    total_volume = (
        bid_volume
        + ask_volume
    )

    total_notional = (
        bid_notional
        + ask_notional
    )

    imbalance = (
        bid_volume
        - ask_volume
    )

    imbalance_ratio = (
        imbalance
        / total_volume
        if total_volume > 0
        else 0.0
    )

    bid_pressure = (
        bid_volume
        / total_volume
        if total_volume > 0
        else 0.0
    )

    ask_pressure = (
        ask_volume
        / total_volume
        if total_volume > 0
        else 0.0
    )

    best_bid = (
        max(
            level["price"]
            for level in bids
        )
        if bids
        else None
    )

    best_ask = (
        min(
            level["price"]
            for level in asks
        )
        if asks
        else None
    )

    if (
        best_bid is not None
        and best_ask is not None
    ):
        spread = (
            best_ask
            - best_bid
        )

        mid_price = (
            best_bid
            + best_ask
        ) / 2

        spread_pct = (
            spread
            / mid_price
            * 100
            if mid_price > 0
            else None
        )
    else:
        spread = None
        mid_price = None
        spread_pct = None

    if imbalance > 0:
        dominant_side = "bullish"

    elif imbalance < 0:
        dominant_side = "bearish"

    else:
        dominant_side = "neutral"

    return {
        "bid_volume": round(
            bid_volume,
            8,
        ),
        "ask_volume": round(
            ask_volume,
            8,
        ),
        "bid_notional": round(
            bid_notional,
            4,
        ),
        "ask_notional": round(
            ask_notional,
            4,
        ),
        "total_volume": round(
            total_volume,
            8,
        ),
        "total_notional": round(
            total_notional,
            4,
        ),
        "imbalance": round(
            imbalance,
            8,
        ),
        "imbalance_ratio": round(
            _clip(
                imbalance_ratio,
                -1.0,
                1.0,
            ),
            6,
        ),
        "bid_pressure": round(
            _clip(
                bid_pressure,
                0.0,
                1.0,
            ),
            6,
        ),
        "ask_pressure": round(
            _clip(
                ask_pressure,
                0.0,
                1.0,
            ),
            6,
        ),
        "spread": (
            round(
                spread,
                8,
            )
            if spread is not None
            else None
        ),
        "spread_pct": (
            round(
                spread_pct,
                8,
            )
            if spread_pct is not None
            else None
        ),
        "best_bid": (
            round(
                best_bid,
                8,
            )
            if best_bid is not None
            else None
        ),
        "best_ask": (
            round(
                best_ask,
                8,
            )
            if best_ask is not None
            else None
        ),
        "mid_price": (
            round(
                mid_price,
                8,
            )
            if mid_price is not None
            else None
        ),
        "dominant_side": dominant_side,
        "level_count": len(
            bids
        ) + len(
            asks
        ),
        "timestamp": order_book.get(
            "timestamp"
        ),
    }


def score(
    analysis: Dict,
    minimum_levels: int = 2,
) -> float:
    """Convert order-book imbalance into a bounded directional score."""
    level_count = int(
        analysis.get(
            "level_count",
            0,
        )
        or 0
    )

    if level_count < minimum_levels:
        return 0.0

    imbalance_ratio = _safe_float(
        analysis.get(
            "imbalance_ratio",
            0.0,
        )
    )

    return round(
        _clip(
            imbalance_ratio * 100.0,
            -100.0,
            100.0,
        ),
        1,
    )


def evidence(
    analysis: Dict,
    timeframe: Optional[str] = None,
    minimum_levels: int = 2,
    minimum_abs_score: float = 8.0,
) -> Optional[Dict]:
    """Return an Evidence-compatible liquidity object.

    Weak or insufficient order-book samples return None.
    """
    liquidity_score = score(
        analysis,
        minimum_levels=minimum_levels,
    )

    if abs(
        liquidity_score
    ) < minimum_abs_score:
        return None

    direction = (
        "bullish"
        if liquidity_score > 0
        else "bearish"
    )

    return {
        "source": "liquidity",
        "direction": direction,
        "strength": abs(
            float(
                liquidity_score
            )
        ),
        "timeframe": timeframe,
        "age_bars": 0,
        "confirmed": (
            int(
                analysis.get(
                    "level_count",
                    0,
                )
                or 0
            )
            >= minimum_levels
        ),
        "bucket": "liquidity",
        "level_count": int(
            analysis.get(
                "level_count",
                0,
            )
            or 0
        ),
        "imbalance": _safe_float(
            analysis.get(
                "imbalance",
                0.0,
            )
        ),
        "imbalance_ratio": _safe_float(
            analysis.get(
                "imbalance_ratio",
                0.0,
            )
        ),
        "spread_pct": analysis.get(
            "spread_pct"
        ),
    }