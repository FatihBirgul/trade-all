"""Offline regression for missing momentum inputs at the decision gate."""
from unittest import TestCase

from market_ai.engines.analysis import aggregate, _momentum_score


def analysis_with_rsi(rsi, *, macd_hist=0.5, volume_direction=0):
    indicators = {
        "price": 100.0,
        "ema20": 98.0,
        "ema50": 96.0,
        "ema100": 94.0,
        "ema200": 92.0,
        "rsi14": rsi,
        "macd_hist": macd_hist,
        "volume_ratio": 1.5,
        "volume_direction": volume_direction,
        "atr14": 1.0,
        "atr_pct": 1.0,
    }
    technical = {
        "price": 100.0,
        "timeframe": "1H",
        "indicators": indicators,
        "structure": {"label": "sideways"},
        "levels": {"support": [], "resistance": []},
    }
    return aggregate(technical, [], [], {})


class MissingMomentumTests(TestCase):
    def test_missing_rsi_cannot_improve_bullish_decision(self):
        observed = {value: analysis_with_rsi(value) for value in (None, 40)}
        missing, contrary = observed[None], observed[40]
        self.assertEqual(contrary["scores"]["momentum"], 3)
        self.assertFalse(contrary["quality"]["gate_passed"])
        self.assertEqual(missing["scores"]["momentum"], 0)
        self.assertLessEqual(missing["scores"]["momentum"], contrary["scores"]["momentum"])
        self.assertLessEqual(missing["final_score"], contrary["final_score"])
        self.assertLessEqual(missing["confidence"], contrary["confidence"])
        self.assertFalse(missing["quality"]["gate_passed"] and not contrary["quality"]["gate_passed"])
        self.assertEqual(missing["direction"], "neutral")

    def test_zero_macd_is_neutral(self):
        self.assertEqual(_momentum_score({"rsi14": 50, "macd_hist": 0.0}), 0)
        self.assertEqual(_momentum_score({"rsi14": 50, "macd_hist": 1e-12}), 25)
        self.assertEqual(_momentum_score({"rsi14": 50, "macd_hist": -1e-12}), -25)

    def test_other_evidence_cannot_open_gate_with_missing_rsi(self):
        missing = analysis_with_rsi(None, macd_hist=-0.5, volume_direction=1)
        self.assertGreaterEqual(missing["quality"]["supporting_count"], 2)
        self.assertFalse(missing["quality"]["gate_passed"])
        self.assertEqual(missing["direction"], "neutral")
