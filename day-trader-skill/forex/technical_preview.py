"""Read-only technical observations; never an executable trade plan."""

import json
import time
from datetime import datetime, timezone

from .core import (
    DATA_SYMBOLS, TIMEFRAMES, DataError,
    finite, indicators
)


def build_technical_preview(provider, symbol, timeframe="M15", *, now=None):
    if symbol not in DATA_SYMBOLS or timeframe not in TIMEFRAMES:
        raise DataError("unsupported preview symbol or timeframe")

    now = finite(time.time() if now is None else now, "as of")

    meta = provider.metadata(symbol)
    quote = provider.quote(symbol)

    if not isinstance(meta, dict) or not isinstance(quote, dict):
        raise DataError("metadata or quote unavailable")

    if (
        meta.get("symbol") != symbol
        or meta.get("broker_symbol") != symbol + "c"
        or meta.get("broker_server") != "Exness-MT5Real50"
        or meta.get("account_currency") != "USC"
    ):
        raise DataError("preview broker identity unverified")

    if quote.get("symbol") != symbol:
        raise DataError("quote symbol mismatch")

    bid = finite(quote.get("bid"), "bid")
    ask = finite(quote.get("ask"), "ask")
    tick_time = finite(quote.get("time"), "tick time")

    if bid <= 0 or ask <= bid:
        raise DataError("invalid bid ask")

    if now - tick_time > 120 or tick_time > now + 5:
        raise DataError("stale preview quote")

    interval = TIMEFRAMES[timeframe]
    raw = provider.candles(symbol, timeframe, 220)

    if not isinstance(raw, (list, tuple)) or len(raw) > 220:
        raise DataError("invalid candle batch")

    closed = []
    previous_time = None
    gaps = 0

    for candle in raw:
        if not isinstance(candle, dict):
            raise DataError("invalid candle")

        timestamp = candle.get("time")

        if type(timestamp) is not int or timestamp <= 0:
            raise DataError("invalid candle timestamp")

        if previous_time is not None:
            delta = timestamp - previous_time

            if delta <= 0 or delta % interval != 0:
                raise DataError("unordered or misaligned candles")

            if delta > interval:
                gaps += 1

        previous_time = timestamp

        prices = [
            finite(candle.get(key), key)
            for key in ("open", "high", "low", "close")
        ]

        opening, high, low, closing = prices

        if (
            min(prices) <= 0
            or low > min(opening, closing)
            or high < max(opening, closing)
            or high < low
            or timestamp % interval != 0
        ):
            raise DataError("invalid candle prices")

        if timestamp + interval <= now:
            closed.append({
                "time": timestamp,
                "open": opening,
                "high": high,
                "low": low,
                "close": closing,
                "tick_volume": candle.get("tick_volume", 0),
            })

    if len(closed) < 200:
        raise DataError("insufficient closed candles for preview")

    last_close = closed[-1]["time"] + interval

    if now - last_close > interval * 2:
        raise DataError("stale preview candles")

    result = indicators(closed)

    if not isinstance(result, dict):
        raise DataError("technical indicators unavailable")

    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError):
        raise DataError("invalid technical indicator output")

    return {
        "schema_version": "forex-technical-preview-1",
        "symbol": symbol,
        "broker_symbol": symbol + "c",
        "timeframe": timeframe,
        "provider": provider.name,
        "account_currency": "USC",
        "as_of_utc": datetime.fromtimestamp(
            now, timezone.utc
        ).isoformat(),
        "analysis_mode": "READ_ONLY_TECHNICAL_PREVIEW",
        "technical_status": "PROVISIONAL_UNVERIFIED_SESSION",
        "data_status": "PREVIEW_ONLY",
        "indicators": result,
        "closed_candle_count": len(closed),
        "observed_gap_count": gaps,
        "final_decision": "NO_TRADE",
        "trading_eligibility": "BLOCKED",
        "execution_permission": False,
        "entry_zone": None,
        "stop_loss": None,
        "take_profit_1": None,
        "take_profit_2": None,
        "lot_size": None,
        "risk_amount": None,
        "warnings": [
            "Technical observation is not an approved V5 trade signal.",
            "Historical quote sessions are not independently verified.",
            "Spread policy and cross-currency USC risk approval are unavailable."
        ]
    }