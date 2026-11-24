"""Paper-only risk reference cases; policies are fixtures, not advice."""
from dataclasses import asdict, replace
from decimal import Decimal as D, localcontext, ROUND_UP
import json
from unittest import TestCase

from market_ai.v2.market_data_contract import Instrument
from market_ai.v2.paper_risk import (PaperRiskPolicy, PaperPortfolioSnapshot, PaperSetup,
                                     OpenPaperExposure, evaluate_paper_risk, DAY_MS)
from market_ai.v2.strategy_router import RouteDecision


NOW = DAY_MS + 60_000
INSTRUMENT = Instrument("BTCUSDT", "crypto_spot", "fixture", "last", "spot", "USDT")
POLICY = PaperRiskPolicy("fixture-v1", D(".01"), D(".04"), D(".02"), D(".05"),
                         D("1"), D("1.5"), 5, 1000)
ROUTE = RouteDecision("selected", "trend", "fixture", ("trend",))


def setup(**changes):
    return replace(PaperSetup("demo-a", "trend", INSTRUMENT, "crypto", "bullish",
                             D("99"), D("100"), D("95"), D("110"), D("120"),
                             NOW - 1000, NOW + 60_000, D(".1"), D(".1"), D("1"),
                             D("1"), D("0"), "linear", "USDT"), **changes)


def portfolio(**changes):
    return replace(PaperPortfolioSnapshot("demo-a", "USDT", NOW, DAY_MS,
                                          D("10000"), D("10000"), D("10000"), D("0")), **changes)


def check(s=None, p=None, policy=POLICY, **overrides):
    args = dict(route=ROUTE, as_of_ms=NOW, session_allowed=True, news_clear=True, emergency_paused=False)
    args.update(overrides)
    return evaluate_paper_risk(s or setup(), p or portfolio(), policy, **args)


def exposure(risk="100", notional="1000", group="crypto", account="demo-a"):
    return OpenPaperExposure(account, group, D(risk), D(notional))


class PaperRiskTests(TestCase):
    def test_worst_entry_long_reference_and_no_mutation(self):
        s, p = setup(), portfolio()
        before = (asdict(s), asdict(p))
        result = check(s, p)
        # 10,000 * 1% / (100 - 95) = 20 units; TP1 reward/risk = 10/5 = 2.
        self.assertEqual(result.status, "eligible_for_paper")
        self.assertEqual(D(result.quantity), D("20"))
        self.assertEqual(D(result.reserved_risk_quote), D("100"))
        self.assertEqual(D(result.reserved_notional_quote), D("2000"))
        self.assertEqual(D(result.reward_risk), D("2"))
        self.assertEqual(before, (asdict(s), asdict(p)))
        json.dumps(asdict(result), allow_nan=False)

    def test_perpetual_short_uses_lower_entry_edge(self):
        s = setup(instrument=replace(INSTRUMENT, market="crypto_perpetual", contract_type="perpetual"),
                  direction="bearish", entry_low=D("100"), entry_high=D("101"),
                  invalidation=D("105"), target_1=D("90"), target_2=D("80"))
        self.assertEqual(D(check(s).quantity), D("20"))

    def test_spot_short_and_fx_or_inverse_semantics_are_not_assumed(self):
        self.assertEqual(check(setup(direction="bearish")).reason, "unsupported_paper_contract")
        self.assertEqual(check(setup(instrument=replace(INSTRUMENT, market="forex_spot"))).reason,
                         "unsupported_paper_contract")
        self.assertEqual(check(setup(payoff_type="inverse")).reason, "unsupported_paper_contract")
        self.assertEqual(check(setup(settlement_currency="BTC")).reason, "unsupported_paper_contract")

    def test_geometry_and_nonfinite_values_fail_closed(self):
        for changes in ({"invalidation": D("100")}, {"target_1": D("98")},
                        {"entry_low": D("101")}, {"target_2": D("109")},
                        {"entry_high": D("NaN")}, {"target_1": D("Infinity")},
                        {"invalidation": D("0")}, {"direction": "neutral"}):
            with self.subTest(changes=changes):
                self.assertEqual(check(setup(**changes)).reason, "invalid_zone_geometry")

    def test_costs_reduce_size_and_rr_and_can_veto(self):
        result = check(setup(round_trip_cost_per_unit_quote=D(".5")))
        self.assertEqual(D(result.quantity), D("18.1"))
        self.assertLess(D(result.reward_risk), D("2"))
        self.assertEqual(check(setup(round_trip_cost_per_unit_quote=D("3"))).reason, "reward_risk_gate")

    def test_total_and_group_capacity_include_open_reserved_risk(self):
        # Group cap=200; existing=180 -> 20 risk -> 4 units.
        self.assertEqual(D(check(p=portfolio(exposures=(exposure("180"),))).quantity), D("4"))
        # Total cap=400 exhausted across another group as well.
        self.assertEqual(check(p=portfolio(exposures=(exposure("400", group="other"),))).reason,
                         "portfolio_risk_limit")
        self.assertEqual(check(p=portfolio(exposures=(exposure("200"),))).reason, "portfolio_risk_limit")

    def test_daily_loss_cap_does_not_net_gains_or_ignore_open_risk(self):
        self.assertEqual(check(p=portfolio(realized_loss_today_quote=D("500"))).reason, "portfolio_risk_limit")
        p = portfolio(realized_loss_today_quote=D("450"), exposures=(exposure("40"),))
        self.assertEqual(D(check(p=p).quantity), D("2"))

    def test_cash_and_notional_cap_quantity(self):
        self.assertEqual(D(check(p=portfolio(available_cash_quote=D("150"))).quantity), D("1.5"))
        self.assertEqual(check(p=portfolio(exposures=(exposure("10", "10000"),))).reason,
                         "cash_or_notional_limit")

    def test_step_minimums_and_multiplier_are_explicit(self):
        self.assertEqual(check(setup(minimum_quantity=D("21"))).reason, "below_minimum_size")
        self.assertEqual(check(setup(minimum_notional_quote=D("3000"))).reason, "below_minimum_size")
        self.assertEqual(D(check(setup(contract_multiplier=D("10"))).quantity), D("2"))
        for changes in ({"quantity_step": D("0")}, {"contract_multiplier": D("-1")},
                        {"round_trip_cost_per_unit_quote": D("-1")}, {"correlation_group": ""}):
            self.assertEqual(check(setup(**changes)).reason, "invalid_sizing_contract")

    def test_accounts_and_quote_currencies_never_mix(self):
        self.assertEqual(check(p=portfolio(portfolio_id="demo-b")).reason, "portfolio_mismatch")
        self.assertEqual(check(p=portfolio(quote_currency="USD")).reason, "quote_currency_mismatch")
        self.assertEqual(check(p=portfolio(exposures=(exposure(account="demo-b"),))).reason,
                         "invalid_or_mixed_portfolio_exposure")
        # Independent second demo account, with independent balances.
        result = check(setup(portfolio_id="demo-b"), portfolio(portfolio_id="demo-b", equity_quote=D("1000")))
        self.assertEqual(D(result.reserved_risk_quote), D("10"))

    def test_expiry_future_stale_and_utc_day_rollover(self):
        for changes in ({"expires_at_ms": NOW}, {"created_at_ms": NOW + 1}):
            self.assertEqual(check(setup(**changes)).reason, "setup_expired_or_future")
        for changes in ({"as_of_ms": NOW - 1001}, {"as_of_ms": NOW + 1}, {"day_start_ms": 0}):
            self.assertEqual(check(p=portfolio(**changes)).reason, "stale_or_invalid_portfolio_time")

    def test_flags_and_route_cannot_override_veto(self):
        for args in ({"news_clear": False}, {"session_allowed": False}, {"news_clear": "yes"}):
            self.assertEqual(check(**args).reason, "session_or_news_gate")
        self.assertEqual(check(emergency_paused=True).reason, "emergency_pause")
        self.assertEqual(check(emergency_paused=None).reason, "emergency_pause")
        self.assertEqual(check(route=replace(ROUTE, status="wait")).reason, "strategy_route_gate")
        self.assertEqual(check(setup(strategy_id="other")).reason, "strategy_route_gate")

    def test_position_count_and_invalid_snapshot(self):
        self.assertEqual(check(p=portfolio(exposures=(exposure(),) * 5)).reason, "position_count_limit")
        for changes in ({"equity_quote": D("NaN")}, {"available_cash_quote": D("-1")}, {"exposures": []}):
            self.assertEqual(check(p=portfolio(**changes)).reason, "invalid_portfolio_snapshot")

    def test_policy_config_is_explicit_and_validated(self):
        for changes in ({"trade_risk_fraction": D("0")}, {"trade_risk_fraction": D("1.1")},
                        {"min_reward_risk": D("NaN")}, {"max_open_positions": True}, {"version": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(POLICY, **changes)

    def test_decimal_context_cannot_change_decision(self):
        s = setup(round_trip_cost_per_unit_quote=D(".1"))
        normal = check(s)
        with localcontext() as context:
            context.prec = 4
            context.rounding = ROUND_UP
            self.assertEqual(check(s), normal)

    def test_many_fractional_steps_stay_inside_every_budget(self):
        for step in (".000001", ".03", ".1", ".7", "3"):
            for cost in ("0", ".01", ".5"):
                result = check(setup(quantity_step=D(step), round_trip_cost_per_unit_quote=D(cost)))
                self.assertLessEqual(D(result.reserved_risk_quote), D("100"))
                self.assertLessEqual(D(result.reserved_notional_quote), D("10000"))
                self.assertEqual(D(result.quantity) % D(step), D("0"))
