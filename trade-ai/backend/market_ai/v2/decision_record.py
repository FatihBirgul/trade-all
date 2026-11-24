"""Immutable offline analysis/risk records with complete snapshot provenance.

Content hashes identify decisions and detect accidental corruption; they are
NOT digital signatures or a trust boundary for hostile input. No persistence
or migration is performed by this module. Consumers receive fresh JSON copies.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from decimal import Decimal
from hashlib import sha256
import json
from math import isfinite
from typing import Iterable

from market_ai.engines import technical
from .market_data_contract import Candle, Instrument
from .paper_risk import (PaperSetup, PaperPortfolioSnapshot, PaperRiskPolicy,
                         PaperRiskDecision, evaluate_paper_risk, RISK_VERSION)
from .pipeline import evaluate_strategies, PIPELINE_VERSION
from .price_action import VERSION as PRICE_ACTION_VERSION
from .strategies import VERSION as SETUPS_VERSION
from .regime import REGIME_VERSION, DEFAULT_MIN_EFFICIENCY, DEFAULT_BREAKOUT_ATR_MULTIPLE
from .strategy_router import StrategySpec, RouteDecision, ROUTER_VERSION
from .technical_adapter import compute_technical, ADAPTER_VERSION, TIMEFRAME_MS


RECORD_SCHEMA = "v2-decision-record-1"


def _safe(value):
    if is_dataclass(value):
        return {field.name: _safe(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_safe(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, Decimal):
        return str(value) if value.is_finite() else {"invalid": "nonfinite_decimal"}
    if isinstance(value, float) and not isfinite(value):
        return {"invalid": "nonfinite_number"}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError("Unsupported record value type")


def _canonical(body):
    return json.dumps(_safe(body), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


@dataclass(frozen=True)
class ImmutableDecisionRecord:
    record_id: str
    body_json: str

    def payload(self) -> dict:
        return json.loads(self.body_json)

    def verify(self) -> bool:
        try:
            payload = self.payload()
            return (isinstance(payload, dict) and payload.get("schema") == RECORD_SCHEMA
                    and _canonical(payload) == self.body_json
                    and sha256(self.body_json.encode("utf-8")).hexdigest() == self.record_id)
        except (ValueError, TypeError):
            return False


def _record(body):
    text = _canonical({"schema": RECORD_SCHEMA, **body})
    return ImmutableDecisionRecord(sha256(text.encode("utf-8")).hexdigest(), text)


@dataclass(frozen=True)
class AnalysisConfig:
    data_version: str
    configuration_version: str
    timeframe: str
    as_of_ms: int
    max_age_ms: int
    session: str
    risk_gate_ok: bool
    lookback: int = 20

    def __post_init__(self):
        if (not isinstance(self.data_version, str) or not self.data_version.strip()
                or not isinstance(self.configuration_version, str) or not self.configuration_version.strip()
                or self.timeframe not in TIMEFRAME_MS
                or not isinstance(self.risk_gate_ok, bool)):
            raise ValueError("Explicit data/configuration versions and supported timeframe are required")


def record_analysis(
    candles: Iterable[Candle], strategies: Iterable[StrategySpec], *, config: AnalysisConfig,
) -> ImmutableDecisionRecord:
    """Record candles, parameters, all strategy versions and deterministic gates.

    Only a selected route triggers technical computation. Insufficient technical
    warm-up remains WAIT, even when the shorter regime lookback passed QC.
    Invalid bars are recorded as diagnostics; their nonfinite values are tagged,
    never serialized as nonstandard JSON NaN/Infinity.
    """
    series = tuple(candles)
    specs = tuple(sorted(strategies, key=lambda s: s.strategy_id))
    decision = evaluate_strategies(
        series, specs, timeframe_ms=TIMEFRAME_MS[config.timeframe], as_of_ms=config.as_of_ms,
        max_age_ms=config.max_age_ms, session=config.session,
        risk_gate_ok=config.risk_gate_ok, lookback=config.lookback,
    )
    snapshot = None
    status, reason = "wait", decision.route.reason
    if decision.route.status == "selected":
        snapshot = compute_technical(series, timeframe=config.timeframe,
                                     as_of_ms=config.as_of_ms, max_age_ms=config.max_age_ms)
        if snapshot.status == "available":
            status, reason = "analysis_ready", "validated_analysis"
        else:
            reason = "technical_" + snapshot.reason
    return _record({
        "kind": "analysis", "status": status, "reason": reason,
        "config": config, "candles": series, "strategies": specs, "routing": decision,
        "technical": snapshot,
        "engine_versions": {"routing": PIPELINE_VERSION, "regime": REGIME_VERSION,
                            "strategy_router": ROUTER_VERSION,
                            "technical": ADAPTER_VERSION, "price_action": PRICE_ACTION_VERSION, "setups": SETUPS_VERSION},
        "parameters": {"regime": {"lookback": config.lookback,
                                  "min_efficiency": DEFAULT_MIN_EFFICIENCY,
                                  "breakout_atr_multiple": DEFAULT_BREAKOUT_ATR_MULTIPLE},
                       "technical": technical.TIMEFRAME_PARAMS[config.timeframe]},
    })


def record_paper_risk(
    analysis: ImmutableDecisionRecord, setup: PaperSetup, portfolio: PaperPortfolioSnapshot,
    policy: PaperRiskPolicy, *, as_of_ms: int, session_allowed: bool,
    news_clear: bool, emergency_paused: bool,
) -> ImmutableDecisionRecord:
    """Bind risk inputs to the exact analysis snapshot, instrument and timestamp."""
    def blocked(reason):
        return PaperRiskDecision("wait", reason, RISK_VERSION, policy.version)

    if not analysis.verify():
        decision = blocked("invalid_analysis_record")
    else:
        body = analysis.payload()
        if (body.get("kind") != "analysis" or body.get("status") != "analysis_ready"
                or not isinstance(body.get("engine_versions"), dict)
                or body["engine_versions"].get("routing") != PIPELINE_VERSION):
            decision = blocked("analysis_not_ready")
        else:
            try:
                matches = (setup.analysis_record_id == analysis.record_id
                           and setup.created_at_ms == body["config"]["as_of_ms"]
                           and asdict(setup.instrument) == body["candles"][0]["instrument"])
                route_fields = body["routing"]["route"]
                route = RouteDecision(**{**route_fields,
                                         "eligible_strategy_ids": tuple(route_fields["eligible_strategy_ids"])})
            except (KeyError, TypeError, ValueError, IndexError):
                decision = blocked("invalid_analysis_record")
            else:
                decision = (evaluate_paper_risk(setup, portfolio, policy, route=route,
                                               as_of_ms=as_of_ms, session_allowed=session_allowed,
                                               news_clear=news_clear, emergency_paused=emergency_paused)
                            if matches else blocked("analysis_setup_mismatch"))
    return _record({"kind": "paper_risk", "analysis_record_id": analysis.record_id,
                    "setup": setup, "portfolio": portfolio, "policy": policy,
                    "as_of_ms": as_of_ms, "session_allowed": session_allowed,
                    "news_clear": news_clear, "emergency_paused": emergency_paused,
                    "decision": decision})


@dataclass(frozen=True)
class ReplayResult:
    status: str  # matched / mismatch / unavailable; no execution side effects
    reason: str
    original_record_id: str
    replayed_record_id: str = ""


def replay_analysis(record: ImmutableDecisionRecord) -> ReplayResult:
    """Recompute the recorded snapshot at its original as-of time, offline.

    Future engine versions need explicit adapters; never silently replay an old
    record under different semantics and label it verified. Invalid-number tags
    are diagnostic-only and cannot be reconstructed as real market observations.
    """
    def unavailable(reason):
        return ReplayResult("unavailable", reason, record.record_id)

    if not record.verify():
        return unavailable("invalid_record")
    body = record.payload()
    expected_versions = {"routing": PIPELINE_VERSION, "regime": REGIME_VERSION,
                         "strategy_router": ROUTER_VERSION, "technical": ADAPTER_VERSION, "price_action": PRICE_ACTION_VERSION, "setups": SETUPS_VERSION}
    if body.get("kind") != "analysis" or body.get("engine_versions") != expected_versions:
        return unavailable("unsupported_kind_or_engine_version")
    try:
        bars = []
        for raw in body["candles"]:
            if any(isinstance(raw[key], dict) for key in ("open", "high", "low", "close", "volume")):
                return unavailable("invalid_number_diagnostics_not_replayable")
            bars.append(Candle(**{**raw, "instrument": Instrument(**raw["instrument"])}))
        strategies = [StrategySpec(**{**raw,
            **{key: frozenset(raw[key]) for key in ("regimes", "markets", "sessions", "required_capabilities")},
        }) for raw in body["strategies"]]
        config = AnalysisConfig(**body["config"])
        replayed = record_analysis(bars, strategies, config=config)
    except (KeyError, TypeError, ValueError, IndexError):
        return unavailable("invalid_replay_inputs")
    matched = replayed.record_id == record.record_id
    return ReplayResult("matched" if matched else "mismatch",
                        "identical_decision" if matched else "decision_or_parameters_changed",
                        record.record_id, replayed.record_id)
