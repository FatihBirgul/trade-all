"""Deterministic order-flow / delta analysis engine.

Consumes normalized aggregate trades from the market-data provider and
converts them into directional order-flow statistics.

Interpretation:
- buyer_maker=False -> buyer was the aggressor -> positive delta
- buyer_maker=True  -> seller was the aggressor -> negative delta

This module does not fetch market data and does not make trading decisions.
It produces a deterministic analytical snapshot that can later be converted
into Evidence by the confluence layer.
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


def _trade_side(
    trade: Dict,
) -> str:
    """Return aggressor side from normalized Binance trade data."""
    return (
        "sell"
        if bool(
            trade.get(
                "buyer_maker",
                False,
            )
        )
        else "buy"
    )


def _trade_notional(
    trade: Dict,
) -> float:
    """Return price * quantity notional for one trade."""
    price = _safe_float(
        trade.get(
            "price"
        )
    )

    quantity = _safe_float(
        trade.get(
            "quantity"
        )
    )

    if price <= 0 or quantity <= 0:
        return 0.0

    return price * quantity


def _trade_quantity(
    trade: Dict,
) -> float:
    return max(
        0.0,
        _safe_float(
            trade.get(
                "quantity"
            )
        ),
    )


def _trade_timestamp(
    trade: Dict,
) -> int:
    return _safe_int(
        trade.get(
            "timestamp",
            0,
        )
    )


def analyze(
    trades: Optional[List[Dict]],
) -> Dict:
    """Build deterministic order-flow statistics from aggregate trades.

    Returns:
        trade_count
        buy_volume
        sell_volume
        total_volume
        delta
        delta_ratio
        buy_pressure
        sell_pressure
        dominant_side
        imbalance
        vwap
        first_timestamp
        last_timestamp
    """
    items = list(
        trades or []
    )

    if not items:
        return {
            "trade_count": 0,
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "total_volume": 0.0,
            "delta": 0.0,
            "delta_ratio": 0.0,
            "buy_pressure": 0.0,
            "sell_pressure": 0.0,
            "dominant_side": "neutral",
            "imbalance": 0.0,
            "vwap": None,
            "first_timestamp": None,
            "last_timestamp": None,
        }

    buy_volume = 0.0
    sell_volume = 0.0

    buy_notional = 0.0
    sell_notional = 0.0

    total_notional = 0.0
    total_volume = 0.0

    timestamps = []

    valid_trade_count = 0

    for trade in items:
        quantity = _trade_quantity(
            trade
        )

        if quantity <= 0:
            continue

        notional = _trade_notional(
            trade
        )

        side = _trade_side(
            trade
        )

        timestamp = _trade_timestamp(
            trade
        )

        if timestamp > 0:
            timestamps.append(
                timestamp
            )

        total_volume += quantity
        total_notional += notional

        if side == "buy":
            buy_volume += quantity
            buy_notional += notional

        else:
            sell_volume += quantity
            sell_notional += notional

        valid_trade_count += 1

    delta = (
        buy_volume
        - sell_volume
    )

    delta_ratio = (
        delta / total_volume
        if total_volume > 0
        else 0.0
    )

    buy_pressure = (
        buy_volume
        / total_volume
        if total_volume > 0
        else 0.0
    )

    sell_pressure = (
        sell_volume
        / total_volume
        if total_volume > 0
        else 0.0
    )

    if delta > 0:
        dominant_side = "bullish"

    elif delta < 0:
        dominant_side = "bearish"

    else:
        dominant_side = "neutral"

    imbalance = abs(
        delta_ratio
    )

    vwap = (
        total_notional
        / total_volume
        if total_volume > 0
        else None
    )

    return {
        "trade_count": valid_trade_count,

        "buy_volume": round(
            buy_volume,
            8,
        ),

        "sell_volume": round(
            sell_volume,
            8,
        ),

        "total_volume": round(
            total_volume,
            8,
        ),

        "delta": round(
            delta,
            8,
        ),

        "delta_ratio": round(
            _clip(
                delta_ratio,
                -1.0,
                1.0,
            ),
            6,
        ),

        "buy_pressure": round(
            _clip(
                buy_pressure,
                0.0,
                1.0,
            ),
            6,
        ),

        "sell_pressure": round(
            _clip(
                sell_pressure,
                0.0,
                1.0,
            ),
            6,
        ),

        "dominant_side": dominant_side,

        "imbalance": round(
            _clip(
                imbalance,
                0.0,
                1.0,
            ),
            6,
        ),

        "vwap": (
            round(
                vwap,
                4,
            )
            if vwap is not None
            else None
        ),

        "first_timestamp": (
            min(timestamps)
            if timestamps
            else None
        ),

        "last_timestamp": (
            max(timestamps)
            if timestamps
            else None
        ),
    }


def score(
    analysis: Dict,
    minimum_trade_count: int = 1,
) -> float:
    """Convert delta pressure into a bounded directional score.

    The score is intentionally simple in this first version:
        +100 = fully buy-dominant
        -100 = fully sell-dominant
         0   = balanced

    A minimum trade-count guard prevents empty/tiny samples from being
    interpreted as meaningful order-flow evidence.
    """
    trade_count = _safe_int(
        analysis.get(
            "trade_count",
            0,
        )
    )

    if trade_count < minimum_trade_count:
        return 0.0

    delta_ratio = _safe_float(
        analysis.get(
            "delta_ratio",
            0.0,
        )
    )

    return round(
        _clip(
            delta_ratio * 100.0,
            -100.0,
            100.0,
        ),
        1,
    )


def evidence(
    analysis: Dict,
    timeframe: Optional[str] = None,
    minimum_trade_count: int = 1,
    minimum_abs_score: float = 8.0,
) -> Optional[Dict]:
    """Return an Evidence-compatible order-flow object.

    Weak/neutral flow returns None instead of manufacturing directional
    evidence.
    """
    flow_score = score(
        analysis,
        minimum_trade_count=minimum_trade_count,
    )

    if abs(flow_score) < minimum_abs_score:
        return None

    direction = (
        "bullish"
        if flow_score > 0
        else "bearish"
    )

    return {
        "source": "order_flow",
        "direction": direction,
        "strength": abs(
            float(
                flow_score
            )
        ),
        "timeframe": timeframe,
        "age_bars": 0,
        "confirmed": (
            _safe_int(
                analysis.get(
                    "trade_count",
                    0,
                )
            )
            >= minimum_trade_count
        ),
        "bucket": "order_flow",
        "trade_count": _safe_int(
            analysis.get(
                "trade_count",
                0,
            )
        ),
        "delta": _safe_float(
            analysis.get(
                "delta",
                0.0,
            )
        ),
        "delta_ratio": _safe_float(
            analysis.get(
                "delta_ratio",
                0.0,
            )
        ),
    }