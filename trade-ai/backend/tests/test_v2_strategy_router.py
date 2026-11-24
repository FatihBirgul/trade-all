"""No live data, DB, or external service is used by these tests."""
import unittest

from market_ai.v2.strategy_router import StrategySpec, route_strategy


def spec(name, *, regimes=("trend",), markets=("crypto_spot",),
         capabilities=(), sessions=(), priority=0, enabled=True):
    return StrategySpec(
        strategy_id=name,
        regimes=frozenset(regimes),
        markets=frozenset(markets),
        required_capabilities=frozenset(capabilities),
        sessions=frozenset(sessions),
        priority=priority,
        enabled=enabled,
    )


def route(strategies, **kwargs):
    args = dict(
        regime="trend",
        market="crypto_spot",
        session="london",
        capabilities=frozenset({"ohlc", "real_volume"}),
        data_quality_ok=True,
        risk_gate_ok=True,
    )
    args.update(kwargs)
    return route_strategy(strategies, **args)


class StrategyRouterTests(unittest.TestCase):
    def test_selects_eligible_strategy(self):
        d = route([spec("trend_follow")])
        self.assertEqual(d.status, "selected")
        self.assertEqual(d.strategy_id, "trend_follow")

    def test_unknown_regime_fails_closed(self):
        d = route([spec("trend_follow")], regime="unknown")
        self.assertEqual(d.status, "wait")
        self.assertEqual(d.reason, "unknown_regime")

    def test_data_quality_and_risk_veto(self):
        strategies = [spec("trend_follow")]
        self.assertEqual(route(strategies, data_quality_ok=False).reason, "data_quality_gate")
        self.assertEqual(route(strategies, risk_gate_ok=False).reason, "risk_gate")

    def test_missing_order_flow_capability_rejects(self):
        strategies = [spec("flow", capabilities=("aggregate_trades",))]
        d = route(strategies)
        self.assertEqual(d.status, "wait")
        self.assertEqual(d.reason, "no_eligible_strategy")

    def test_forex_does_not_inherit_crypto_capabilities(self):
        strategies = [spec("flow", markets=("forex_spot",), capabilities=("order_book",))]
        d = route(strategies, market="forex_spot", capabilities=frozenset({"ohlc"}))
        self.assertEqual(d.status, "wait")

    def test_market_and_session_constraints(self):
        strategies = [spec("orb", regimes=("breakout",), sessions=("new_york",))]
        self.assertEqual(route(strategies, regime="breakout").status, "wait")
        self.assertEqual(route(strategies, regime="breakout", session="new_york").status, "selected")

    def test_priority_breaks_conflict_deterministically(self):
        strategies = [spec("low", priority=2), spec("high", priority=10)]
        d = route(strategies)
        self.assertEqual(d.strategy_id, "high")
        self.assertEqual(d.eligible_strategy_ids, ("high", "low"))

    def test_equal_priority_conflict_abstains(self):
        d = route([spec("alpha", priority=5), spec("beta", priority=5)])
        self.assertEqual(d.status, "wait")
        self.assertEqual(d.reason, "equal_priority_conflict")
        self.assertIsNone(d.strategy_id)

    def test_disabled_strategy_not_selected(self):
        self.assertEqual(route([spec("disabled", enabled=False)]).status, "wait")

    def test_duplicate_strategy_identifiers_rejected(self):
        with self.assertRaises(ValueError):
            route([spec("dup"), spec("dup")])

    def test_unsupported_market_fails_closed(self):
        self.assertEqual(route([spec("any")], market="unknown").status, "wait")


if __name__ == "__main__":
    unittest.main()
