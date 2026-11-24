"""Isolated V2 QC -> regime -> strategy eligibility orchestration.

No API, storage, provider, AI, network or order execution dependencies. A
selected route authorizes analytical work only, never a trade. Session labels
and the external risk veto are explicit caller inputs. FX/gold need a verified
calendar adapter before this continuous-market pipeline can evaluate them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .capabilities import candle_capabilities
from .market_data_contract import Candle, validate_series
from .data_quality import QualityReport
from .regime import RegimeResult, classify_regime
from .strategy_router import RouteDecision, StrategySpec, route_strategy


PIPELINE_VERSION = "v2-routing-3"


@dataclass(frozen=True)
class PipelineResult:
    version: str
    as_of_ms: int
    quality: QualityReport
    regime: RegimeResult
    capabilities: frozenset[str]
    route: RouteDecision
    strategy_analysis: dict | None = None


def evaluate_strategies(
    candles: Iterable[Candle],
    strategies: Iterable[StrategySpec],
    *,
    timeframe_ms: int,
    as_of_ms: int,
    max_age_ms: int,
    session: str,
    risk_gate_ok: bool,
    lookback: int = 20,
) -> PipelineResult:
    """Evaluate one immutable snapshot with explicit replay time and veto.

    Reject the whole batch on quality failure, including invalid older bars;
    never filter out future/unfinished bars to make a route appear eligible.
    Configuration errors raise rather than masquerading as market outcomes.
    """
    if isinstance(lookback, bool) or not isinstance(lookback, int) or lookback < 5:
        raise ValueError("lookback must be an integer >= 5")
    series = tuple(candles)
    quality = validate_series(
        series, timeframe_ms=timeframe_ms, as_of_ms=as_of_ms,
        max_age_ms=max_age_ms, min_bars=lookback,
    )
    def wait(reason: str) -> PipelineResult:
        return PipelineResult(
            PIPELINE_VERSION, as_of_ms, quality,
            RegimeResult("unknown", "neutral", reason, len(series)), frozenset(),
            RouteDecision("wait", None, reason, ()),
        )

    if not quality.ok:
        return wait("data_quality_gate")
    capabilities = candle_capabilities(series)
    if not capabilities:
        return wait("unsupported_instrument_or_volume")
    if series[0].instrument.market in {"forex_spot", "gold_spot"}:
        return wait("session_calendar_unavailable")

    regime = classify_regime(
        [float(c.close) for c in series], [float(c.high) for c in series],
        [float(c.low) for c in series], lookback=lookback,
    )
    from .strategies import BUILTIN_IDS, assess_setups, resolve_setups
    specs = tuple(strategies)
    setup = (assess_setups(series, timeframe_ms=timeframe_ms, as_of_ms=as_of_ms,
                         max_age_ms=max_age_ms, regime=regime.regime, regime_direction=regime.direction)
             if any(s.strategy_id in BUILTIN_IDS for s in specs) else None)
    router = (lambda specs, **kwargs: resolve_setups(specs, setup, **kwargs)) if setup else route_strategy
    route = router(
        specs, regime=regime.regime, market=series[0].instrument.market,
        session=session, capabilities=capabilities,
        data_quality_ok=quality.ok, risk_gate_ok=risk_gate_ok,
    )
    return PipelineResult(PIPELINE_VERSION, as_of_ms, quality, regime, capabilities, route, setup)
