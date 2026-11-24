"""Mathematical reference and regression tests for Breakout / Breakdown detection.

Validates:
1. Bullish Breakout with upper wick (verifies fix for self-referential range bug).
2. Bearish Breakdown with lower wick (verifies fix for self-referential range bug).
3. Marubozu (flat extreme) Breakout and Breakdown.
4. Rejection of false-positive wick spikes (closing back inside the range).
5. Unconfirmed breakout detection when closing near range boundary (<2% distance).
6. Prior-candle qualification (closes[-2] must be sufficiently inside the range).
7. Boundary conditions (<40 candles, exactly 40 candles, zero-width range).
8. Schema integrity (name, classification, confidence, location, confirmed, age_bars).
"""
import unittest

from market_ai.engines import chart_patterns


def _create_base_candles(count: int = 39, low: float = 90.0, high: float = 100.0) -> list[dict]:
    """Generate deterministic range-bound candles between low and high.

    Indices 0 to count-1.
    Sets explicit extreme high at index 15 and extreme low at index 16.
    Ensures candle count-1 (closes[-2] relative to breakout) is safely inside range.
    """
    candles = []
    mid = (low + high) / 2.0
    for i in range(count):
        # Default candles stay within [low + 1.0, high - 1.0]
        h = high - 2.0 if i % 2 == 0 else high - 1.0
        l = low + 1.0 if i % 2 == 0 else low + 2.0
        o = mid
        c = mid + 1.0 if i % 2 == 0 else mid - 1.0
        candles.append({"open": o, "high": h, "low": l, "close": c, "volume": 100.0})

    # Anchor exact 30-bar reference extremes
    if count >= 30:
        candles[count - 20]["high"] = high
        candles[count - 19]["low"] = low

    # Set candle count-1 close (the bar preceding breakout) well below high - 5% rng
    # rng = 10.0 -> high - 0.5 = 99.5; low + 0.5 = 90.5
    candles[-1]["close"] = mid
    candles[-1]["high"] = high - 1.5
    candles[-1]["low"] = low + 1.5
    return candles


class ChartBreakoutReferenceTests(unittest.TestCase):
    """Deterministic reference tests for chart_patterns breakout detection."""

    def test_bullish_breakout_with_upper_wick_detected_and_confirmed(self):
        """A candle closing above prior 30-bar high with an upper wick must be confirmed.

        Prior 30-bar range: [90.0, 100.0].
        Current candle: high = 105.0, close = 102.0.
        Must detect Breakout with confirmed=True.
        """
        candles = _create_base_candles(39, low=90.0, high=100.0)
        # 40th candle (index 39)
        candles.append({"open": 97.0, "high": 105.0, "low": 96.5, "close": 102.0, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakouts = [p for p in results if p["name"] == "Breakout"]

        self.assertEqual(len(breakouts), 1)
        b = breakouts[0]
        self.assertEqual(b["classification"], "bullish")
        self.assertEqual(b["confidence"], 55)
        self.assertEqual(b["location"], 39)
        self.assertTrue(b["confirmed"])
        self.assertEqual(b["age_bars"], 0)

    def test_bearish_breakdown_with_lower_wick_detected_and_confirmed(self):
        """A candle closing below prior 30-bar low with a lower wick must be confirmed.

        Prior 30-bar range: [90.0, 100.0].
        Current candle: low = 85.0, close = 88.0.
        Must detect Breakdown with confirmed=True.
        """
        candles = _create_base_candles(39, low=90.0, high=100.0)
        # 40th candle (index 39)
        candles.append({"open": 93.0, "high": 93.5, "low": 85.0, "close": 88.0, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakdowns = [p for p in results if p["name"] == "Breakdown"]

        self.assertEqual(len(breakdowns), 1)
        bd = breakdowns[0]
        self.assertEqual(bd["classification"], "bearish")
        self.assertEqual(bd["confidence"], 55)
        self.assertEqual(bd["location"], 39)
        self.assertTrue(bd["confirmed"])
        self.assertEqual(bd["age_bars"], 0)

    def test_bullish_breakout_marubozu_detected_and_confirmed(self):
        """A candle closing at the exact high above prior range is confirmed."""
        candles = _create_base_candles(39, low=90.0, high=100.0)
        candles.append({"open": 97.0, "high": 102.0, "low": 96.5, "close": 102.0, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakouts = [p for p in results if p["name"] == "Breakout"]

        self.assertEqual(len(breakouts), 1)
        self.assertTrue(breakouts[0]["confirmed"])

    def test_bearish_breakdown_marubozu_detected_and_confirmed(self):
        """A candle closing at the exact low below prior range is confirmed."""
        candles = _create_base_candles(39, low=90.0, high=100.0)
        candles.append({"open": 93.0, "high": 93.5, "low": 88.0, "close": 88.0, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakdowns = [p for p in results if p["name"] == "Breakdown"]

        self.assertEqual(len(breakdowns), 1)
        self.assertTrue(breakdowns[0]["confirmed"])

    def test_false_bullish_breakout_wick_only_rejected(self):
        """Wick breaches 100.0 to 105.0 but close is 98.0 (inside range) -> no Breakout."""
        candles = _create_base_candles(39, low=90.0, high=100.0)
        candles.append({"open": 97.0, "high": 105.0, "low": 96.5, "close": 98.0, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakouts = [p for p in results if p["name"] == "Breakout"]
        self.assertEqual(len(breakouts), 0)

    def test_false_bearish_breakdown_wick_only_rejected(self):
        """Wick drops below 90.0 to 85.0 but close is 92.0 (inside range) -> no Breakdown."""
        candles = _create_base_candles(39, low=90.0, high=100.0)
        candles.append({"open": 93.0, "high": 93.5, "low": 85.0, "close": 92.0, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakdowns = [p for p in results if p["name"] == "Breakdown"]
        self.assertEqual(len(breakdowns), 0)

    def test_unconfirmed_breakout_near_range_high(self):
        """Close is within 2% of range high (99.9 vs 100.0, rng=10) -> confirmed=False.

        Formula: price >= hi_range - 0.02 * rng = 100.0 - 0.2 = 99.8.
        Since 99.9 >= 99.8, breakout is detected.
        Since 99.9 < 100.0, confirmed must be False.
        """
        candles = _create_base_candles(39, low=90.0, high=100.0)
        candles.append({"open": 97.0, "high": 99.9, "low": 96.5, "close": 99.9, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakouts = [p for p in results if p["name"] == "Breakout"]

        self.assertEqual(len(breakouts), 1)
        self.assertFalse(breakouts[0]["confirmed"])

    def test_unconfirmed_breakdown_near_range_low(self):
        """Close is within 2% of range low (90.1 vs 90.0, rng=10) -> confirmed=False.

        Formula: price <= lo_range + 0.02 * rng = 90.0 + 0.2 = 90.2.
        Since 90.1 <= 90.2, breakdown is detected.
        Since 90.1 > 90.0, confirmed must be False.
        """
        candles = _create_base_candles(39, low=90.0, high=100.0)
        candles.append({"open": 93.0, "high": 93.5, "low": 90.1, "close": 90.1, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakdowns = [p for p in results if p["name"] == "Breakdown"]

        self.assertEqual(len(breakdowns), 1)
        self.assertFalse(breakdowns[0]["confirmed"])

    def test_prior_candle_too_close_to_high_rejects_breakout(self):
        """If candle -2 was already near high (closes[-2] >= hi_range - 0.05 * rng), reject."""
        candles = _create_base_candles(39, low=90.0, high=100.0)
        # hi_range = 100.0, rng = 10.0 -> threshold = 100 - 0.5 = 99.5
        # Set candle -2 close to 99.8 (violates closes[-2] < hi_range - rng * 0.05)
        candles[-1]["close"] = 99.8
        candles.append({"open": 99.8, "high": 105.0, "low": 99.5, "close": 102.0, "volume": 250.0})

        results = chart_patterns.detect(candles)
        breakouts = [p for p in results if p["name"] == "Breakout"]
        self.assertEqual(len(breakouts), 0)

    def test_boundary_insufficient_bars_returns_empty(self):
        """Fewer than 40 candles must immediately return empty list."""
        candles = _create_base_candles(38, low=90.0, high=100.0)
        candles.append({"open": 97.0, "high": 105.0, "low": 96.5, "close": 102.0, "volume": 250.0})
        self.assertEqual(len(candles), 39)
        self.assertEqual(chart_patterns.detect(candles), [])

    def test_boundary_zero_width_range_returns_empty(self):
        """If range high equals range low (rng == 0), no breakout/breakdown is detected."""
        candles = [{"open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 100.0} for _ in range(40)]
        results = chart_patterns.detect(candles)
        breakouts = [p for p in results if p["name"] in ("Breakout", "Breakdown")]
        self.assertEqual(len(breakouts), 0)


if __name__ == "__main__":
    unittest.main()
