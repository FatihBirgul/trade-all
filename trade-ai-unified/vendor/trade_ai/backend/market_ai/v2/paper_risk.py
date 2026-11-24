"""Pure paper-only setup sizing and portfolio veto; never submits orders.

Policies are explicit, versioned test/application inputs, not calibrated risk
recommendations. Supports linear crypto contracts in account quote currency.
No FX conversion, inverse contracts, borrowing, leverage or persistent balance
mutation. Fees/spread/slippage are caller-supplied conservative per-unit costs.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, localcontext, ROUND_FLOOR, ROUND_HALF_EVEN

from .market_data_contract import Instrument
from .strategy_router import RouteDecision


ZERO = Decimal("0")
DAY_MS = 86_400_000
RISK_VERSION = "v2-paper-risk-1"


def _amount(value: object, *, positive=False) -> bool:
    return (isinstance(value, Decimal) and value.is_finite()
            and (value > 0 if positive else value >= 0)
            and value <= Decimal("1e24")
            and len(value.as_tuple().digits) <= 28
            and -18 <= value.as_tuple().exponent <= 18)


def _time(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


@dataclass(frozen=True)
class PaperRiskPolicy:
    version: str
    trade_risk_fraction: Decimal
    total_risk_fraction: Decimal
    group_risk_fraction: Decimal
    daily_loss_fraction: Decimal
    notional_fraction: Decimal
    min_reward_risk: Decimal
    max_open_positions: int
    max_snapshot_age_ms: int

    def __post_init__(self):
        fractions = (self.trade_risk_fraction, self.total_risk_fraction,
                     self.group_risk_fraction, self.daily_loss_fraction, self.notional_fraction)
        if (not isinstance(self.version, str) or not self.version.strip()
                or any(not _amount(v, positive=True) or v > 1 for v in fractions)
                or not _amount(self.min_reward_risk, positive=True)
                or isinstance(self.max_open_positions, bool)
                or not isinstance(self.max_open_positions, int) or self.max_open_positions < 1
                or not _time(self.max_snapshot_age_ms)):
            raise ValueError("Invalid paper risk policy")


@dataclass(frozen=True)
class OpenPaperExposure:
    portfolio_id: str
    correlation_group: str
    reserved_risk_quote: Decimal
    reserved_notional_quote: Decimal


@dataclass(frozen=True)
class PaperPortfolioSnapshot:
    portfolio_id: str
    quote_currency: str
    as_of_ms: int
    day_start_ms: int  # UTC midnight; loss-to-date never nets profitable trades
    equity_quote: Decimal
    day_start_equity_quote: Decimal
    available_cash_quote: Decimal
    realized_loss_today_quote: Decimal
    exposures: tuple[OpenPaperExposure, ...] = ()


@dataclass(frozen=True)
class PaperSetup:
    portfolio_id: str
    strategy_id: str
    instrument: Instrument
    correlation_group: str
    direction: str
    entry_low: Decimal
    entry_high: Decimal
    invalidation: Decimal
    target_1: Decimal
    target_2: Decimal
    created_at_ms: int
    expires_at_ms: int
    quantity_step: Decimal
    minimum_quantity: Decimal
    minimum_notional_quote: Decimal
    contract_multiplier: Decimal
    round_trip_cost_per_unit_quote: Decimal
    payoff_type: str  # only explicit "linear" is supported
    settlement_currency: str
    analysis_record_id: str = ""  # required by the recorded-analysis integration


@dataclass(frozen=True)
class PaperRiskDecision:
    status: str  # eligible_for_paper / wait; neither is an execution
    reason: str
    version: str
    policy_version: str
    quantity: str = "0"
    reserved_risk_quote: str = "0"
    reserved_notional_quote: str = "0"
    reward_risk: str = "0"


def evaluate_paper_risk(
    setup: PaperSetup, portfolio: PaperPortfolioSnapshot, policy: PaperRiskPolicy,
    *, route: RouteDecision, as_of_ms: int, session_allowed: bool,
    news_clear: bool, emergency_paused: bool,
) -> PaperRiskDecision:
    """Size at the worst entry edge; all vetoes are evaluated without writes.

    Total/group/daily risk and cash/notional budgets include existing reserved
    exposure. Daily loss capacity reserves BOTH open and proposed stop risk.
    Invalid market/snapshot data returns WAIT; invalid policy raises at creation.
    """
    def wait(reason):
        return PaperRiskDecision("wait", reason, RISK_VERSION, policy.version)

    if not _time(as_of_ms):
        raise ValueError("as_of_ms must be a nonnegative UTC epoch integer")
    if emergency_paused is not False:
        return wait("emergency_pause")
    if session_allowed is not True or news_clear is not True:
        return wait("session_or_news_gate")
    if route.status != "selected" or route.strategy_id != setup.strategy_id:
        return wait("strategy_route_gate")
    if not setup.portfolio_id or setup.portfolio_id != portfolio.portfolio_id:
        return wait("portfolio_mismatch")
    if portfolio.quote_currency != setup.instrument.quote_currency:
        return wait("quote_currency_mismatch")
    instrument = setup.instrument
    if ((instrument.market, instrument.contract_type) not in {
            ("crypto_spot", "spot"), ("crypto_perpetual", "perpetual")}
            or instrument.price_kind != "last"
            or setup.payoff_type != "linear"
            or setup.settlement_currency != portfolio.quote_currency
            or (instrument.market == "crypto_spot" and setup.direction == "bearish")):
        return wait("unsupported_paper_contract")
    if (not _time(setup.created_at_ms) or not _time(setup.expires_at_ms)
            or not setup.created_at_ms <= as_of_ms < setup.expires_at_ms):
        return wait("setup_expired_or_future")
    if (not _time(portfolio.as_of_ms)
            or not 0 <= as_of_ms - portfolio.as_of_ms <= policy.max_snapshot_age_ms
            or not _time(portfolio.day_start_ms)
            or portfolio.day_start_ms != as_of_ms // DAY_MS * DAY_MS
            or portfolio.day_start_ms != portfolio.as_of_ms // DAY_MS * DAY_MS):
        return wait("stale_or_invalid_portfolio_time")
    levels = (setup.entry_low, setup.entry_high, setup.invalidation, setup.target_1, setup.target_2)
    if any(not _amount(v, positive=True) for v in levels):
        return wait("invalid_zone_geometry")
    if setup.direction == "bullish":
        geometry_ok = setup.invalidation < setup.entry_low <= setup.entry_high < setup.target_1 < setup.target_2
        entry = setup.entry_high
    elif setup.direction == "bearish":
        geometry_ok = setup.target_2 < setup.target_1 < setup.entry_low <= setup.entry_high < setup.invalidation
        entry = setup.entry_low
    else:
        geometry_ok = False
        entry = ZERO
    if not geometry_ok:
        return wait("invalid_zone_geometry")
    if (any(not _amount(v, positive=True) for v in (
            setup.quantity_step, setup.minimum_quantity, setup.contract_multiplier))
            or any(not _amount(v) for v in (setup.minimum_notional_quote, setup.round_trip_cost_per_unit_quote))
            or not isinstance(setup.correlation_group, str) or not setup.correlation_group.strip()):
        return wait("invalid_sizing_contract")
    if (any(not _amount(v, positive=True) for v in (portfolio.equity_quote, portfolio.day_start_equity_quote))
            or any(not _amount(v) for v in (portfolio.available_cash_quote, portfolio.realized_loss_today_quote))
            or not isinstance(portfolio.exposures, tuple)):
        return wait("invalid_portfolio_snapshot")
    for exposure in portfolio.exposures:
        if (not isinstance(exposure, OpenPaperExposure) or exposure.portfolio_id != portfolio.portfolio_id
                or not isinstance(exposure.correlation_group, str) or not exposure.correlation_group.strip()
                or not _amount(exposure.reserved_risk_quote, positive=True)
                or not _amount(exposure.reserved_notional_quote, positive=True)):
            return wait("invalid_or_mixed_portfolio_exposure")
    if len(portfolio.exposures) >= policy.max_open_positions:
        return wait("position_count_limit")

    # Stable decimal context: caller precision must not change a saved decision.
    with localcontext(Context(prec=80, rounding=ROUND_HALF_EVEN)):
        cost = setup.round_trip_cost_per_unit_quote
        risk_per_unit = abs(entry - setup.invalidation) * setup.contract_multiplier + cost
        reward_per_unit = abs(setup.target_1 - entry) * setup.contract_multiplier - cost
        rr = reward_per_unit / risk_per_unit
        if reward_per_unit <= 0 or rr < policy.min_reward_risk:
            return wait("reward_risk_gate")
        total = sum((e.reserved_risk_quote for e in portfolio.exposures), ZERO)
        group = sum((e.reserved_risk_quote for e in portfolio.exposures
                     if e.correlation_group == setup.correlation_group), ZERO)
        notional = sum((e.reserved_notional_quote for e in portfolio.exposures), ZERO)
        risk_budget = min(
            portfolio.equity_quote * policy.trade_risk_fraction,
            portfolio.equity_quote * policy.total_risk_fraction - total,
            portfolio.equity_quote * policy.group_risk_fraction - group,
            portfolio.day_start_equity_quote * policy.daily_loss_fraction
            - portfolio.realized_loss_today_quote - total,
        )
        notional_budget = min(portfolio.available_cash_quote,
                              portfolio.equity_quote * policy.notional_fraction - notional)
        if risk_budget <= 0:
            return wait("portfolio_risk_limit")
        if notional_budget <= 0:
            return wait("cash_or_notional_limit")
        unit_notional = entry * setup.contract_multiplier + cost
        raw_quantity = min(risk_budget / risk_per_unit, notional_budget / unit_notional)
        quantity = (raw_quantity / setup.quantity_step).to_integral_value(rounding=ROUND_FLOOR) * setup.quantity_step
        # A repeating decimal quotient must never round through a budget edge.
        if quantity * risk_per_unit > risk_budget or quantity * unit_notional > notional_budget:
            quantity -= setup.quantity_step
        if quantity <= 0 or quantity < setup.minimum_quantity or quantity * unit_notional < setup.minimum_notional_quote:
            return wait("below_minimum_size")
        return PaperRiskDecision("eligible_for_paper", "within_explicit_limits", RISK_VERSION,
                                 policy.version, str(quantity), str(quantity * risk_per_unit),
                                 str(quantity * unit_notional), str(rr))
