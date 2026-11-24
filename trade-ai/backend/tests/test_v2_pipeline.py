"""Offline contract integration: normalized candles through QC/regime/router."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from market_ai.v2.capabilities import candle_capabilities
from market_ai.v2.market_data_contract import Candle, Instrument, from_binance_spot_kline
from market_ai.v2.pipeline import evaluate_strategies
from market_ai.v2.strategy_router import StrategySpec


TF = 60_000
SPOT = Instrument("BTCUSDT", "crypto_spot", "binance", "last", "spot", "USDT")


def candles(closes=None, **overrides):
    closes = closes if closes is not None else [100 + i * 0.1 for i in range(20)]
    return [replace(Candle(
        SPOT, i * TF, (i + 1) * TF, True, c, c + 5, c - 5, c,
        10.0, "real", "fixture",
    ), **overrides) for i, c in enumerate(closes)]


def strategy(name="trend", regimes=("trend",), required=(), priority=0):
    return StrategySpec(name, frozenset(regimes), frozenset({"crypto_spot"}),
                        frozenset(required), priority=priority)


def evaluate(series, strategies=None, **overrides):
    args = dict(timeframe_ms=TF, as_of_ms=20 * TF, max_age_ms=TF,
                session="london", risk_gate_ok=True)
    args.update(overrides)
    return evaluate_strategies(series, strategies if strategies is not None else [strategy()], **args)


class PipelineTests(TestCase):
    def test_trend_is_repeatable_and_inputs_unchanged(self):
        series = candles()
        original = tuple(series)
        first = evaluate(series)
        self.assertEqual(first, evaluate(iter(series)))
        self.assertEqual(tuple(series), original)
        self.assertTrue(first.quality.ok)
        self.assertEqual((first.regime.regime, first.regime.direction), ("trend", "bullish"))
        self.assertEqual(first.route.strategy_id, "trend")
        self.assertEqual(first.capabilities, frozenset({"ohlc", "real_volume"}))

    def test_range_breakout_and_flat_route_end_to_end(self):
        strategies = [strategy("range", ("range",)), strategy("breakout", ("breakout",))]
        for values, selected in [([99, 101] * 10, "range"), ([100] * 19 + [120], "breakout")]:
            with self.subTest(selected=selected):
                self.assertEqual(evaluate(candles(values), strategies).route.strategy_id, selected)
        flat = evaluate(candles([100] * 20, high=100, low=100))
        self.assertEqual(flat.route.reason, "unknown_regime")

    def test_invalid_batches_never_reach_classifier(self):
        base = candles()
        invalid = {
            "empty": [], "short": base[:4], "gap": base[:8] + base[9:],
            "duplicate": base[:8] + [base[7]] + base[8:],
            "reversed": list(reversed(base)),
            "unfinished": base[:-1] + [replace(base[-1], is_final=False)],
            "nan": [replace(base[0], close=float("nan"))] + base[1:],
            "mixed_source": base[:-1] + [replace(base[-1], source="other")],
            "mixed_contract": base[:-1] + [replace(base[-1], instrument=replace(
                SPOT, market="crypto_perpetual", contract_type="perpetual"))],
        }
        with patch("market_ai.v2.pipeline.classify_regime", side_effect=AssertionError("QC bypass")):
            for label, series in invalid.items():
                with self.subTest(label=label):
                    result = evaluate(series)
                    self.assertFalse(result.quality.ok)
                    self.assertEqual(result.route.reason, "data_quality_gate")
                    self.assertFalse(result.capabilities)

    def test_as_of_rejects_future_and_stale_snapshots(self):
        for as_of in (19 * TF, 22 * TF):
            with self.subTest(as_of=as_of):
                self.assertEqual(evaluate(candles(), as_of_ms=as_of).route.reason, "data_quality_gate")

    def test_risk_veto_and_conflict_cannot_be_overridden(self):
        self.assertEqual(evaluate(candles(), risk_gate_ok=False).route.reason, "risk_gate")
        self.assertEqual(evaluate(candles(), risk_gate_ok="yes").route.reason, "risk_gate")
        result = evaluate(candles(), [strategy("a"), strategy("b")])
        self.assertEqual(result.route.reason, "equal_priority_conflict")

    def test_no_candle_metadata_can_grant_flow_or_futures_feeds(self):
        for capability in ("order_book", "aggregate_trades", "open_interest", "funding", "liquidation"):
            with self.subTest(capability=capability):
                result = evaluate(candles(), [strategy(required=(capability,))])
                self.assertEqual(result.route.reason, "no_eligible_strategy")

    def test_volume_unavailable_or_mixed_does_not_grant_real_volume(self):
        series = candles(volume=None, volume_kind="unavailable")
        self.assertEqual(evaluate(series).capabilities, frozenset({"ohlc"}))
        series[-1] = replace(series[-1], volume=5, volume_kind="tick")
        self.assertEqual(evaluate(series).capabilities, frozenset({"ohlc"}))
        self.assertEqual(evaluate(series, [strategy(required=("real_volume",))]).route.status, "wait")

    def test_fx_and_gold_require_calendar_and_reject_exchange_volume(self):
        for market in ("forex_spot", "gold_spot"):
            identity = Instrument("TESTUSD", market, "fixture", "mid", "spot", "USD")
            series = candles(instrument=identity, volume_kind="tick")
            self.assertEqual(candle_capabilities(series), frozenset({"ohlc", "tick_volume"}))
            self.assertEqual(evaluate(series).route.reason, "session_calendar_unavailable")
            series[-1] = replace(series[-1], volume_kind="real")
            self.assertFalse(candle_capabilities(series))
            self.assertEqual(evaluate(series).route.reason, "unsupported_instrument_or_volume")

    def test_invalid_market_contract_cannot_route(self):
        series = candles(instrument=replace(SPOT, contract_type="perpetual"))
        self.assertEqual(evaluate(series).route.reason, "unsupported_instrument_or_volume")

    def test_binance_adapter_to_route_smoke(self):
        series = [from_binance_spot_kline(
            [i * TF, str(c), str(c + 5), str(c - 5), str(c), "10", (i + 1) * TF - 1],
            symbol="BTCUSDT", quote_currency="USDT", as_of_ms=20 * TF,
        ) for i, c in enumerate(100 + n * 0.1 for n in range(20))]
        self.assertEqual(evaluate(series).route.status, "selected")

    def test_numeric_strings_accepted_by_qc_are_normalized_for_regime(self):
        series = [replace(c, close=str(c.close), high=str(c.high), low=str(c.low)) for c in candles()]
        self.assertEqual(evaluate(series).regime.regime, "trend")

    def test_bad_lookback_is_configuration_error(self):
        for value in (True, 0, 4, 20.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate(candles(), lookback=value)
