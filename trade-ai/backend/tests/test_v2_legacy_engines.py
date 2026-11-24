"""Offline reference fixtures for V1 algorithms reused by V2.

No server/providers/DB imports. Reference values are hand-derived, rather
than snapshots copied from the implementation under test.
"""
import itertools
import math
import unittest

import pandas as pd

from market_ai.engines import technical, confluence, mtf


class IndicatorReferenceTests(unittest.TestCase):
    def test_sma_and_ema_reference_values(self):
        series = pd.Series([1., 2., 3., 4.])
        self.assertTrue(math.isnan(technical.sma(series, 3).iloc[1]))
        self.assertEqual(technical.sma(series, 3).iloc[-1], 3.)
        # alpha = 2/(3+1): 1, 1.5, 2.25, 3.125
        self.assertEqual(technical.ema(series, 3).tolist(), [1., 1.5, 2.25, 3.125])

    def test_rsi_zero_loss_and_flat_reference(self):
        for values, expected in ((list(range(20)), 100.), (list(range(20, 0, -1)), 0.), ([100.] * 20, 50.)):
            with self.subTest(expected=expected):
                result = technical.rsi(pd.Series(values, dtype=float))
                self.assertTrue(result.iloc[:14].isna().all())
                self.assertEqual(result.iloc[-1], expected)

    def test_rsi_simple_average_reference(self):
        # Last four deltas: +2, -1, +2, -1 -> gain/loss = 2 -> RSI=66.666...
        result = technical.rsi(pd.Series([10., 12., 11., 13., 12.]), period=4)
        self.assertAlmostEqual(result.iloc[-1], 100 - 100 / 3)

    def test_atr_includes_previous_close_gap(self):
        frame = pd.DataFrame({"high": [11., 15., 14.], "low": [9., 13., 10.], "close": [10., 14., 12.]})
        # true ranges = 2, 5, 4; 2-bar simple ATR = 4.5
        self.assertEqual(technical.atr(frame, 2).iloc[-1], 4.5)

    def test_bollinger_sample_standard_deviation(self):
        upper, middle, lower = technical.bollinger(pd.Series([1., 2., 3.]), 3)
        self.assertEqual((upper.iloc[-1], middle.iloc[-1], lower.iloc[-1]), (4., 2., 0.))


class ConfluenceReferenceTests(unittest.TestCase):
    def test_recency_and_confirmation(self):
        item = confluence.Evidence("test", "bullish", 80, age_bars=8, confirmed=False)
        self.assertEqual(confluence.effective_strength(item), 24.)

    def test_correlated_trend_structure_count_once(self):
        result = confluence.confluence_from_scores({"trend": 60, "structure": 40, "momentum": 30})
        self.assertEqual(result["original_evidence_count"], 3)
        self.assertEqual(result["deduplicated_evidence_count"], 2)
        self.assertEqual(result["bullish_strength"], 90)

    def test_volatility_and_direct_feeds_not_generic_evidence(self):
        result = confluence.confluence_from_scores({
            "volatility": 100, "pattern": 100, "order_flow": 100,
            "liquidity": 100, "futures_positioning": 100, "liquidation": 100,
            "mtf": 100, "unknown_indicator": 100,
        })
        self.assertEqual(result["deduplicated_evidence_count"], 0)
        self.assertEqual(result["direction"], "neutral")

    def test_invalid_core_scores_never_become_clamped_maximum_evidence(self):
        for value in (float("nan"), float("inf"), -float("inf"), True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                confluence.confluence_from_scores({"trend": value})

    def test_equal_opposing_bucket_abstains_regardless_of_order(self):
        evidence = [confluence.Evidence("a", "bullish", 60, bucket="same"),
                    confluence.Evidence("b", "bearish", 60, bucket="same")]
        outputs = [confluence.build_confluence(items) for items in itertools.permutations(evidence)]
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[0]["direction"], "neutral")
        self.assertEqual(outputs[0]["supporting_count"], 0)

    def test_nonfinite_evidence_is_rejected(self):
        for value in (float("nan"), float("inf"), -1, True, 101, 10 ** 1000):
            with self.subTest(value=value), self.assertRaises(ValueError):
                confluence.Evidence("test", "bullish", value)

    def test_confirmation_precedence_and_full_permutation_invariance(self):
        items = [confluence.Evidence("a", "bullish", 40, bucket="same"),
                 confluence.Evidence("b", "bearish", 100, confirmed=False, bucket="same"),
                 confluence.Evidence("c", "bearish", 20, bucket="other")]
        results = [confluence.build_confluence(p) for p in itertools.permutations(items)]
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(results[0]["bullish_strength"], 40)
        self.assertEqual(results[0]["bearish_strength"], 20)

    def test_invalid_age_and_confirmation_rejected(self):
        for values in ({"age_bars": -1}, {"age_bars": .5}, {"age_bars": True}, {"confirmed": "yes"}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                confluence.Evidence("test", "bullish", 20, **values)


class MTFReferenceTests(unittest.TestCase):
    def test_nonfinite_snapshot_metrics_do_not_manufacture_confidence(self):
        for value in (float("nan"), float("inf"), -float("inf"), True):
            with self.subTest(value=value):
                result = mtf.analyze("1H", {"1H": {
                    "direction": "neutral", "confidence": value, "final_score": value,
                    "quality": {"gate_passed": False},
                }})
                self.assertEqual(result["current"]["confidence"], 0)
                self.assertEqual(result["current"]["final_score"], 0)

    def test_truthy_string_is_not_a_validated_gate(self):
        result = mtf.analyze("1H", {"1H": {
            "direction": "neutral", "confidence": 30, "final_score": 40,
            "quality": {"gate_passed": "false", "composite_direction": "bullish"},
        }})
        self.assertEqual(result["current"]["direction"], "neutral")
        self.assertFalse(result["current"]["gate_passed"])

    def test_timeframe_hierarchy(self):
        self.assertEqual(mtf.higher_timeframes("1H"), ["4H", "1D"])
        self.assertEqual(mtf.lower_timeframes("1H"), ["1m", "5m", "15m"])

    def test_missing_current_does_not_manufacture_executable_direction(self):
        result = mtf.analyze("1H", {})
        self.assertEqual(result["direction"], "neutral")
        self.assertFalse(result["current"]["available"])

    def test_rr_veto_preserves_validated_bias_not_tradeability(self):
        result = mtf.analyze("1H", {"1H": {
            "direction": "neutral", "confidence": 45, "final_score": 40,
            "quality": {"gate_passed": True, "tradeable": False, "composite_direction": "bullish"},
        }})
        self.assertEqual(result["current"]["direction"], "bullish")
        self.assertEqual(result["current"]["executable_direction"], "neutral")
        self.assertFalse(result["current"]["tradeable"])
