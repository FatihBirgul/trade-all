"""Deterministic liquidation analysis engine.

Consumes normalized Binance Futures liquidation / force-order events and
converts them into directional liquidation pressure.

This module:
- does not fetch market data,
- does not maintain a WebSocket connection,
- does not make trade decisions,
- produces deterministic analysis and Evidence-compatible output.

Interpretation:
- A BUY liquidation means a short position was forcibly closed.
- A SELL liquidation means a long position was forcibly closed.

The engine distinguishes:
- long liquidation pressure,
- short liquidation pressure,
- total liquidation notional,
- directional imbalance,
- event count,
- largest liquidation.

Liquidation direction is treated as market pressure/context rather than a
guaranteed future price direction.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional


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


def _normalize_side(
    side: Optional[str],
) -> str:
    value = str(
        side or ""
    ).upper()

    if value in (
        "BUY",
        "SELL",
    ):
        return value

    return ""


# ---------------------------------------------------------------------------
# Event normalization
# ---------------------------------------------------------------------------
def normalize_event(
    event: Dict,
) -> Optional[Dict]:
    """Normalize one liquidation event.

    Supported normalized input fields:

        symbol
        price
        average_price
        original_quantity
        executed_quantity
        side
        trade_time
        update_time

    The Binance force-order stream may provide:
        s, S, p, ap, q, z, T, E, ps

    Long liquidation:
        SELL order

    Short liquidation:
        BUY order
    """
    if not event:
        return None

    # Already-normalized provider event.
    symbol = event.get(
        "symbol"
    )

    side = _normalize_side(
        event.get(
            "side"
        )
    )

    price = _safe_float(
        event.get(
            "price"
        )
    )

    average_price = _safe_float(
        event.get(
            "average_price",
            price,
        )
    )

    original_quantity = _safe_float(
        event.get(
            "original_quantity"
        )
    )

    executed_quantity = _safe_float(
        event.get(
            "executed_quantity",
            original_quantity,
        )
    )

    trade_time = _safe_int(
        event.get(
            "trade_time",
            event.get(
                "timestamp",
                0,
            ),
        )
    )

    update_time = _safe_int(
        event.get(
            "update_time",
            event.get(
                "timestamp",
                trade_time,
            ),
        )
    )

    # Binance raw stream compatibility.
    if not symbol:
        symbol = event.get(
            "s"
        )

    if not side:
        side = _normalize_side(
            event.get(
                "S"
            )
        )

    if price <= 0:
        price = _safe_float(
            event.get(
                "p"
            )
        )

    if average_price <= 0:
        average_price = _safe_float(
            event.get(
                "ap",
                price,
            )
        )

    if original_quantity <= 0:
        original_quantity = _safe_float(
            event.get(
                "q"
            )
        )

    if executed_quantity <= 0:
        executed_quantity = _safe_float(
            event.get(
                "z",
                original_quantity,
            )
        )

    if trade_time <= 0:
        trade_time = _safe_int(
            event.get(
                "T",
                0,
            )
        )

    if update_time <= 0:
        update_time = _safe_int(
            event.get(
                "E",
                trade_time,
            )
        )

    if (
        not symbol
        or side not in (
            "BUY",
            "SELL",
        )
        or price <= 0
        or executed_quantity <= 0
    ):
        return None

    notional = (
        average_price
        if average_price > 0
        else price
    ) * executed_quantity

    return {
        "symbol": symbol,
        "price": price,
        "average_price": (
            average_price
            if average_price > 0
            else price
        ),
        "original_quantity": (
            original_quantity
        ),
        "executed_quantity": (
            executed_quantity
        ),
        "side": side,
        "trade_time": trade_time,
        "update_time": update_time,
        "notional": notional,
    }


# ---------------------------------------------------------------------------
# Batch analysis
# ---------------------------------------------------------------------------
def analyze(
    events: Optional[Iterable[Dict]],
) -> Dict:
    """Analyze a batch of liquidation events.

    Direction convention:

        BUY liquidation  -> short positions liquidated -> bullish pressure

        SELL liquidation -> long positions liquidated  -> bearish pressure

    `event_count` represents valid liquidation events.
    """
    normalized: List[Dict] = []

    for event in (
        events or []
    ):
        item = normalize_event(
            event
        )

        if item:
            normalized.append(
                item
            )

    if not normalized:
        return {
            "event_count": 0,
            "buy_liquidation_count": 0,
            "sell_liquidation_count": 0,
            "short_liquidation_count": 0,
            "long_liquidation_count": 0,
            "buy_liquidation_notional": 0.0,
            "sell_liquidation_notional": 0.0,
            "short_liquidation_notional": 0.0,
            "long_liquidation_notional": 0.0,
            "total_liquidation_notional": 0.0,
            "liquidation_imbalance": 0.0,
            "liquidation_imbalance_ratio": 0.0,
            "short_liquidation_pressure": 0.0,
            "long_liquidation_pressure": 0.0,
            "dominant_side": "neutral",
            "largest_liquidation": None,
            "first_timestamp": None,
            "last_timestamp": None,
        }

    buy_events = [
        event
        for event in normalized
        if event["side"] == "BUY"
    ]

    sell_events = [
        event
        for event in normalized
        if event["side"] == "SELL"
    ]

    buy_notional = sum(
        event["notional"]
        for event in buy_events
    )

    sell_notional = sum(
        event["notional"]
        for event in sell_events
    )

    total_notional = (
        buy_notional
        + sell_notional
    )

    # BUY liquidation = shorts liquidated.
    short_liquidation_notional = (
        buy_notional
    )

    # SELL liquidation = longs liquidated.
    long_liquidation_notional = (
        sell_notional
    )

    liquidation_imbalance = (
        short_liquidation_notional
        - long_liquidation_notional
    )

    liquidation_imbalance_ratio = (
        liquidation_imbalance
        / total_notional
        if total_notional > 0
        else 0.0
    )

    short_pressure = (
        short_liquidation_notional
        / total_notional
        if total_notional > 0
        else 0.0
    )

    long_pressure = (
        long_liquidation_notional
        / total_notional
        if total_notional > 0
        else 0.0
    )

    if liquidation_imbalance > 0:
        dominant_side = "bullish"

    elif liquidation_imbalance < 0:
        dominant_side = "bearish"

    else:
        dominant_side = "neutral"

    largest_liquidation = max(
        normalized,
        key=lambda item: item[
            "notional"
        ],
    )

    timestamps = [
        event["trade_time"]
        for event in normalized
        if event["trade_time"] > 0
    ]

    return {
        "event_count": len(
            normalized
        ),

        "buy_liquidation_count": len(
            buy_events
        ),

        "sell_liquidation_count": len(
            sell_events
        ),

        "short_liquidation_count": len(
            buy_events
        ),

        "long_liquidation_count": len(
            sell_events
        ),

        "buy_liquidation_notional": round(
            buy_notional,
            8,
        ),

        "sell_liquidation_notional": round(
            sell_notional,
            8,
        ),

        "short_liquidation_notional": round(
            short_liquidation_notional,
            8,
        ),

        "long_liquidation_notional": round(
            long_liquidation_notional,
            8,
        ),

        "total_liquidation_notional": round(
            total_notional,
            8,
        ),

        "liquidation_imbalance": round(
            liquidation_imbalance,
            8,
        ),

        "liquidation_imbalance_ratio": round(
            _clip(
                liquidation_imbalance_ratio,
                -1.0,
                1.0,
            ),
            6,
        ),

        "short_liquidation_pressure": round(
            _clip(
                short_pressure,
                0.0,
                1.0,
            ),
            6,
        ),

        "long_liquidation_pressure": round(
            _clip(
                long_pressure,
                0.0,
                1.0,
            ),
            6,
        ),

        "dominant_side": (
            dominant_side
        ),

        "largest_liquidation": {
            "symbol": largest_liquidation[
                "symbol"
            ],
            "side": largest_liquidation[
                "side"
            ],
            "price": round(
                largest_liquidation[
                    "price"
                ],
                8,
            ),
            "executed_quantity": round(
                largest_liquidation[
                    "executed_quantity"
                ],
                8,
            ),
            "notional": round(
                largest_liquidation[
                    "notional"
                ],
                8,
            ),
            "trade_time": largest_liquidation[
                "trade_time"
            ],
        },

        "first_timestamp": (
            min(
                timestamps
            )
            if timestamps
            else None
        ),

        "last_timestamp": (
            max(
                timestamps
            )
            if timestamps
            else None
        ),
    }


# ---------------------------------------------------------------------------
# Score
# ---------------------------------------------------------------------------
def score(
    analysis: Dict,
    minimum_notional: float = 0.0,
    minimum_events: int = 1,
) -> float:
    """Convert liquidation imbalance into a bounded directional score.

    The score is based on the relative notional imbalance, not raw event
    count. This prevents many tiny liquidations from automatically outweighing
    a smaller number of large liquidations.

    `minimum_notional` can be used later as a market-specific calibration
    filter.
    """
    event_count = _safe_int(
        analysis.get(
            "event_count",
            0,
        )
    )

    total_notional = _safe_float(
        analysis.get(
            "total_liquidation_notional",
            0.0,
        )
    )

    if event_count < minimum_events:
        return 0.0

    if total_notional < minimum_notional:
        return 0.0

    ratio = _safe_float(
        analysis.get(
            "liquidation_imbalance_ratio",
            0.0,
        )
    )

    return round(
        _clip(
            ratio * 100.0,
            -100.0,
            100.0,
        ),
        1,
    )


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
def evidence(
    analysis: Dict,
    timeframe: Optional[str] = None,
    minimum_notional: float = 0.0,
    minimum_events: int = 1,
    minimum_abs_score: float = 8.0,
) -> Optional[Dict]:
    """Return an Evidence-compatible liquidation object."""
    liquidation_score = score(
        analysis,
        minimum_notional=minimum_notional,
        minimum_events=minimum_events,
    )

    if abs(
        liquidation_score
    ) < minimum_abs_score:
        return None

    direction = (
        "bullish"
        if liquidation_score > 0
        else "bearish"
    )

    return {
        "source": "liquidation",
        "direction": direction,
        "strength": abs(
            float(
                liquidation_score
            )
        ),
        "timeframe": timeframe,
        "age_bars": 0,
        "confirmed": True,
        "bucket": "liquidation",
        "event_count": _safe_int(
            analysis.get(
                "event_count",
                0,
            )
        ),
        "total_liquidation_notional": (
            _safe_float(
                analysis.get(
                    "total_liquidation_notional",
                    0.0,
                )
            )
        ),
        "short_liquidation_notional": (
            _safe_float(
                analysis.get(
                    "short_liquidation_notional",
                    0.0,
                )
            )
        ),
        "long_liquidation_notional": (
            _safe_float(
                analysis.get(
                    "long_liquidation_notional",
                    0.0,
                )
            )
        ),
        "liquidation_imbalance_ratio": (
            _safe_float(
                analysis.get(
                    "liquidation_imbalance_ratio",
                    0.0,
                )
            )
        ),
    }