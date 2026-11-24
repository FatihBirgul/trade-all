import unittest

from market_ai.v2.regime import classify_regime


def bars(closes, width=0.3):
    return closes, [v + width for v in closes], [v - width for v in closes]


class RegimeTests(unittest.TestCase):
    def test_missing_data_returns_unknown(self):
        self.assertEqual(classify_regime(*bars([100] * 4), lookback=5).regime, "unknown")

    def test_uptrend_without_breakout(self):
        c = [100 + i * 0.1 for i in range(20)]
        result = classify_regime(*bars(c, width=5), lookback=20)
        self.assertEqual((result.regime, result.direction), ("trend", "bullish"))

    def test_downtrend_without_breakout(self):
        c = [100 - i * 0.1 for i in range(20)]
        result = classify_regime(*bars(c, width=5), lookback=20)
        self.assertEqual((result.regime, result.direction), ("trend", "bearish"))

    def test_range(self):
        c = [100 + (1 if i % 2 else -1) for i in range(20)]
        result = classify_regime(*bars(c), lookback=20)
        self.assertEqual((result.regime, result.direction), ("range", "neutral"))

    def test_upside_breakout(self):
        c = [100] * 19 + [106]
        result = classify_regime(*bars(c), lookback=20)
        self.assertEqual((result.regime, result.direction), ("breakout", "bullish"))

    def test_downside_breakout(self):
        c = [100] * 19 + [94]
        result = classify_regime(*bars(c), lookback=20)
        self.assertEqual((result.regime, result.direction), ("breakout", "bearish"))

    def test_nan_and_invalid_ohlc_return_unknown(self):
        c, h, l = bars([100] * 20)
        c[-1] = float("nan")
        self.assertEqual(classify_regime(c, h, l).regime, "unknown")
        c[-1] = 100
        h[-1] = 90
        self.assertEqual(classify_regime(c, h, l).regime, "unknown")

    def test_no_price_movement_not_a_signal(self):
        self.assertEqual(classify_regime(*bars([100] * 20, width=0)).regime, "unknown")

    def test_configuration_validation(self):
        with self.assertRaises(ValueError):
            classify_regime(*bars([100] * 20), lookback=0)


if __name__ == "__main__":
    unittest.main()
