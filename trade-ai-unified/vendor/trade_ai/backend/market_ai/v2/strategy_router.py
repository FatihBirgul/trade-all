"""Trade AI 2.0 deterministic strategy eligibility and conflict resolver.

This module chooses *which analytical strategy may run*, not whether to trade.
A route is never an order or a profitable-signal prediction. All inputs must
already pass the closed-candle/data-quality and portfolio-risk gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


REGIMES = frozenset({"trend", "range", "breakout", "reversal", "unknown"})
ROUTER_VERSION = "v2-strategy-router-2"
MARKETS = frozenset({"crypto_spot", "crypto_perpetual", "forex_spot", "gold_spot", "cfd"})
SESSIONS = frozenset({"asia", "london", "new_york", "overlap", "off_hours"})


@dataclass(frozen=True)
class StrategySpec:
    strategy_id: str
    regimes: frozenset[str]
    markets: frozenset[str]
    required_capabilities: frozenset[str] = frozenset()
    sessions: frozenset[str] = frozenset()
    priority: int = 0
    enabled: bool = True
    version: str = "1"

    def __post_init__(self):
        if (not isinstance(self.strategy_id, str) or not self.strategy_id.strip()
                or not isinstance(self.version, str) or not self.version.strip()
                or not isinstance(self.enabled, bool)
                or isinstance(self.priority, bool) or not isinstance(self.priority, int)):
            raise ValueError("Invalid strategy identity, version or priority")
        for values, supported in ((self.regimes, REGIMES - {"unknown"}),
                                  (self.markets, MARKETS), (self.sessions, SESSIONS)):
            if not isinstance(values, frozenset) or not values.issubset(supported):
                raise ValueError("Strategy constraints must be supported immutable sets")
        if not self.regimes or not self.markets:
            raise ValueError("A strategy needs at least one regime and market")
        if (not isinstance(self.required_capabilities, frozenset)
                or any(not isinstance(v, str) or not v.strip() for v in self.required_capabilities)):
            raise ValueError("Capabilities must be an immutable set of nonempty names")


@dataclass(frozen=True)
class RouteDecision:
    status: str  # "selected" or "wait"
    strategy_id: str | None
    reason: str
    eligible_strategy_ids: tuple[str, ...]


def route_strategy(
    strategies: Iterable[StrategySpec],
    *,
    regime: str,
    market: str,
    session: str,
    capabilities: frozenset[str],
    data_quality_ok: bool,
    risk_gate_ok: bool,
) -> RouteDecision:
    """Select exactly one eligible strategy, or WAIT on unsafe/ambiguous input.

    Priority is a documented operational precedence, NOT a success score.
    Equal-priority candidates are ambiguous and deliberately produce WAIT.
    """
    if data_quality_ok is not True:
        return RouteDecision("wait", None, "data_quality_gate", ())
    if risk_gate_ok is not True:
        return RouteDecision("wait", None, "risk_gate", ())
    if regime not in REGIMES or regime == "unknown":
        return RouteDecision("wait", None, "unknown_regime", ())
    if market not in MARKETS or session not in SESSIONS:
        return RouteDecision("wait", None, "unsupported_market_or_session", ())

    specs = tuple(strategies)
    if any(not isinstance(spec, StrategySpec) for spec in specs):
        raise TypeError("Every strategy must be a StrategySpec")
    identifiers = [spec.strategy_id for spec in specs]
    if any(not identifier for identifier in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("Strategy identifiers must be nonempty and unique")

    eligible = sorted(
        (
            spec for spec in specs
            if spec.enabled
            and regime in spec.regimes
            and market in spec.markets
            and (not spec.sessions or session in spec.sessions)
            and spec.required_capabilities.issubset(capabilities)
        ),
        key=lambda spec: (-spec.priority, spec.strategy_id),
    )
    names = tuple(spec.strategy_id for spec in eligible)
    if not eligible:
        return RouteDecision("wait", None, "no_eligible_strategy", names)
    if len(eligible) > 1 and eligible[0].priority == eligible[1].priority:
        return RouteDecision("wait", None, "equal_priority_conflict", names)
    return RouteDecision("selected", eligible[0].strategy_id, "eligible_priority", names)
