"""V2 market data contract: explicit instrument, source and candle semantics.

A candle is not an exchange-independent price without its instrument/venue,
price type, volume type, timestamps and finality. No network calls here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .data_quality import QualityIssue, QualityReport, validate_closed_candles


@dataclass(frozen=True)
class Instrument:
    symbol: str
    market: str
    venue: str
    price_kind: str  # last / bid / ask / mid
    contract_type: str  # spot / perpetual / future
    quote_currency: str

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (
                self.symbol, self.market, self.venue, self.quote_currency, self.price_kind, self.contract_type)):
            raise ValueError("Instrument identity fields must be nonempty strings")
        if self.price_kind not in {"last", "bid", "ask", "mid"}:
            raise ValueError("Unsupported price kind")
        if self.contract_type not in {"spot", "perpetual", "future"}:
            raise ValueError("Unsupported contract type")


@dataclass(frozen=True)
class Candle:
    instrument: Instrument
    open_time_ms: int
    close_time_ms: int  # EXCLUSIVE UTC epoch ms
    is_final: bool
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    volume_kind: str  # real / tick / unavailable
    source: str

    def quality_input(self) -> dict:
        return {
            "open_time_ms": self.open_time_ms,
            "close_time_ms": self.close_time_ms,
            "is_final": self.is_final,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "volume_kind": self.volume_kind,
        }


def validate_series(
    candles: Iterable[Candle],
    *,
    timeframe_ms: int,
    as_of_ms: int,
    max_age_ms: int,
    min_bars: int = 1,
) -> QualityReport:
    series = tuple(candles)
    issues: list[QualityIssue] = []
    identity = None
    source = None
    quality_inputs = []
    for i, candle in enumerate(series):
        if not isinstance(candle, Candle):
            quality_inputs.append(None)  # QC emits invalid_candle; no attribute access.
            continue
        quality_inputs.append(candle.quality_input())
        if not isinstance(candle.instrument, Instrument):
            issues.append(QualityIssue("invalid_instrument", i))
        elif identity is None:
            identity = candle.instrument
        elif candle.instrument != identity:
            issues.append(QualityIssue("mixed_instrument", i))
        if not isinstance(candle.source, str) or not candle.source.strip():
            issues.append(QualityIssue("mixed_or_missing_source", i))
        elif source is None:
            source = candle.source
        elif candle.source != source:
            issues.append(QualityIssue("mixed_or_missing_source", i))
    report = validate_closed_candles(
        quality_inputs,
        timeframe_ms=timeframe_ms,
        as_of_ms=as_of_ms,
        max_age_ms=max_age_ms,
        min_bars=min_bars,
    )
    return QualityReport(
        ok=report.ok and not issues,
        issues=tuple(issues) + report.issues,
        last_close_ms=report.last_close_ms,
    )


def from_binance_spot_kline(raw: list, *, symbol: str, quote_currency: str, as_of_ms: int) -> Candle:
    """Convert one Binance spot kline; source close time is INCLUSIVE.

    Only spot klines are supported here. Futures/FX must use their own
    adapters; do not silently reuse spot contract semantics.
    """
    if len(raw) < 7:
        raise ValueError("Incomplete Binance kline")
    instrument = Instrument(
        symbol=symbol,
        market="crypto_spot",
        venue="binance",
        price_kind="last",
        contract_type="spot",
        quote_currency=quote_currency,
    )
    close_exclusive = int(raw[6]) + 1
    return Candle(
        instrument=instrument,
        open_time_ms=int(raw[0]),
        close_time_ms=close_exclusive,
        is_final=close_exclusive <= as_of_ms,
        open=float(raw[1]),
        high=float(raw[2]),
        low=float(raw[3]),
        close=float(raw[4]),
        volume=float(raw[5]),
        volume_kind="real",
        source="binance_spot",
    )
