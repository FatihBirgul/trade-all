"""Trade AI 2.0 — fail-closed closed-candle quality gate.

Independent of network, DB, pandas, and AI. It is intentionally NOT wired into
V1 endpoints until provider adapters implement the V2 candle contract.

Contract: open_time_ms inclusive; close_time_ms exclusive (UTC epoch ms).
A Binance kline close_time is inclusive: convert by adding 1 millisecond.
Only final bars are accepted. Historical replay passes its own as_of_ms.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Sequence


@dataclass(frozen=True)
class QualityIssue:
    code: str
    candle_index: int | None = None


@dataclass(frozen=True)
class QualityReport:
    ok: bool
    issues: tuple[QualityIssue, ...]
    last_close_ms: int | None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if isfinite(result) else None


def _timestamp(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if value >= 0 else None


def validate_closed_candles(
    candles: Sequence[Mapping[str, object]],
    *,
    timeframe_ms: int,
    as_of_ms: int,
    max_age_ms: int,
    min_bars: int = 1,
) -> QualityReport:
    """Reject missing, future, unfinished, malformed, stale, or gapped bars.

    This strict validator assumes a continuously traded series. A separate
    session-aware calendar adapter must handle FX/weekend/holiday gaps; callers
    must not simply disable gap checks for those markets.
    """
    if (
        isinstance(timeframe_ms, bool)
        or isinstance(as_of_ms, bool)
        or isinstance(max_age_ms, bool)
        or isinstance(min_bars, bool)
        or not all(isinstance(v, int) for v in (timeframe_ms, as_of_ms, max_age_ms, min_bars))
        or timeframe_ms <= 0
        or as_of_ms < 0
        or max_age_ms < 0
        or min_bars < 1
    ):
        raise ValueError("Invalid quality gate configuration")

    issues: list[QualityIssue] = []
    if len(candles) < min_bars:
        issues.append(QualityIssue("insufficient_bars"))

    previous_open: int | None = None
    previous_close: int | None = None
    last_close: int | None = None

    for i, candle in enumerate(candles):
        if not isinstance(candle, Mapping):
            issues.append(QualityIssue("invalid_candle", i))
            continue

        opened = _timestamp(candle.get("open_time_ms"))
        closed = _timestamp(candle.get("close_time_ms"))
        if opened is None or closed is None or closed - opened != timeframe_ms:
            issues.append(QualityIssue("invalid_interval", i))
        if closed is not None:
            if closed > as_of_ms:
                issues.append(QualityIssue("future_candle", i))
            last_close = closed

        if candle.get("is_final") is not True:
            issues.append(QualityIssue("unfinished_candle", i))

        prices = {k: _number(candle.get(k)) for k in ("open", "high", "low", "close")}
        if any(v is None or v <= 0 for v in prices.values()):
            issues.append(QualityIssue("invalid_price", i))
        else:
            o, h, l, c = (prices[k] for k in ("open", "high", "low", "close"))
            if h < max(o, c) or l > min(o, c) or l > h:
                issues.append(QualityIssue("invalid_ohlc", i))

        volume = _number(candle.get("volume"))
        if volume is not None and volume < 0:
            issues.append(QualityIssue("invalid_volume", i))
        if candle.get("volume_kind") not in ("real", "tick", "unavailable"):
            issues.append(QualityIssue("invalid_volume_kind", i))
        if candle.get("volume_kind") == "unavailable":
            if candle.get("volume") is not None:
                issues.append(QualityIssue("unavailable_volume_has_value", i))
        elif volume is None:
            issues.append(QualityIssue("missing_volume", i))

        if opened is not None and previous_open is not None:
            if opened <= previous_open:
                issues.append(QualityIssue("duplicate_or_out_of_order", i))
            if previous_close is not None and opened != previous_close:
                issues.append(QualityIssue("gap_or_overlap", i))
        if opened is not None:
            previous_open = opened
        if closed is not None:
            previous_close = closed

    if last_close is None:
        issues.append(QualityIssue("missing_last_close"))
    elif as_of_ms - last_close > max_age_ms:
        issues.append(QualityIssue("stale_data"))

    return QualityReport(ok=not issues, issues=tuple(issues), last_close_ms=last_close)
