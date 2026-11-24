"""QC boundary for reusing the legacy technical engine in V2.

No network/DB imports. Only crypto candles with real volume are supported by
this first adapter: the bundled legacy snapshot includes directional volume
calculations, so missing/tick volume must not be substituted with fake zeros.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Iterable

from market_ai.engines import technical
from .capabilities import candle_capabilities
from .data_quality import QualityReport
from .market_data_contract import Candle, validate_series


TIMEFRAME_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000,
                "1H": 3_600_000, "4H": 14_400_000, "1D": 86_400_000}
ADAPTER_VERSION = "v2-technical-1"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TechnicalSnapshot:
    status: str
    reason: str
    version: str
    as_of_ms: int
    quality: QualityReport | None
    unavailable_indicators: tuple[str, ...] = ()
    payload_json: str = "{}"

    def payload(self) -> dict:
        """Return a fresh copy so consumers cannot mutate the saved result."""
        return json.loads(self.payload_json)


def compute_technical(
    candles: Iterable[Candle], *, timeframe: str, as_of_ms: int, max_age_ms: int,
) -> TechnicalSnapshot:
    """Validate the complete batch before converting to legacy OHLCV inputs.

    Thirty bars warm EMA20 only; longer EMAs retain explicit unavailable values
    until their documented warm-up. Availability never authorizes a trade.
    """
    def unavailable(reason, quality=None):
        return TechnicalSnapshot("unavailable", reason, ADAPTER_VERSION, as_of_ms, quality)

    if timeframe not in TIMEFRAME_MS:
        return unavailable("unsupported_timeframe")
    series = tuple(candles)
    quality = validate_series(series, timeframe_ms=TIMEFRAME_MS[timeframe],
                              as_of_ms=as_of_ms, max_age_ms=max_age_ms, min_bars=30)
    if not quality.ok:
        return unavailable("data_quality_gate", quality)
    if "real_volume" not in candle_capabilities(series):
        return unavailable("real_volume_required", quality)
    # Candle quality accepts numeric strings; normalize at the engine boundary.
    legacy = [{key: float(getattr(c, key)) for key in ("open", "high", "low", "close", "volume")}
              for c in series]
    try:
        result = technical.compute(legacy, timeframe=timeframe)
        payload_json = json.dumps(result, sort_keys=True, allow_nan=False, separators=(",", ":"))
    except Exception:
        logger.exception("V2 technical engine unavailable")
        return unavailable("engine_error", quality)
    missing = tuple(sorted(key for key, value in result["indicators"].items() if value is None))
    return TechnicalSnapshot("available", "validated_snapshot", ADAPTER_VERSION,
                             as_of_ms, quality, missing, payload_json)
