"""Pure unit tests: no network, DB, production state, or external packages."""
import unittest

from market_ai.v2.data_quality import validate_closed_candles


TF = 60_000


def bar(n=0, **overrides):
    value = {
        "open_time_ms": n * TF,
        "close_time_ms": (n + 1) * TF,
        "is_final": True,
        "open": 100.0,
        "high": 103.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 12.0,
        "volume_kind": "real",
    }
    value.update(overrides)
    return value


def check(candles, **overrides):
    config = dict(timeframe_ms=TF, as_of_ms=3 * TF, max_age_ms=2 * TF)
    config.update(overrides)
    return validate_closed_candles(candles, **config)


def codes(report):
    return {issue.code for issue in report.issues}


class ClosedCandleQualityTests(unittest.TestCase):
    def test_two_valid_closed_bars(self):
        result = check([bar(0), bar(1)])
        self.assertTrue(result.ok)
        self.assertEqual(result.last_close_ms, 2 * TF)

    def test_empty_and_insufficient_history(self):
        self.assertIn("insufficient_bars", codes(check([])))
        self.assertIn("insufficient_bars", codes(check([bar()], min_bars=2)))

    def test_unfinished_or_future_candle_fails_closed(self):
        self.assertIn("unfinished_candle", codes(check([bar(is_final=False)])))
        self.assertIn("future_candle", codes(check([bar(3)])))

    def test_gap_and_duplicate_fail(self):
        self.assertIn("gap_or_overlap", codes(check([bar(0), bar(2)])))
        self.assertIn("duplicate_or_out_of_order", codes(check([bar(0), bar(0)])))

    def test_ohlc_and_nonfinite_fail(self):
        self.assertIn("invalid_ohlc", codes(check([bar(high=99.0)])))
        self.assertIn("invalid_price", codes(check([bar(close=float("nan"))])))
        self.assertIn("invalid_price", codes(check([bar(close=float("inf"))])))

    def test_missing_and_wrong_volume_fail(self):
        self.assertIn("missing_volume", codes(check([bar(volume=None)])))
        self.assertIn("invalid_volume", codes(check([bar(volume=-1)])))
        self.assertIn("invalid_volume_kind", codes(check([bar(volume_kind="exchange")])))
        self.assertIn("unavailable_volume_has_value", codes(check([bar(volume_kind="unavailable")])))

    def test_explicitly_unavailable_volume_is_acceptable(self):
        self.assertTrue(check([bar(volume=None, volume_kind="unavailable")]).ok)

    def test_unavailable_volume_requires_explicit_none(self):
        for value in (float("nan"), float("inf"), "invalid", "", False):
            with self.subTest(value=value):
                self.assertIn("unavailable_volume_has_value", codes(check([
                    bar(volume=value, volume_kind="unavailable"),
                ])))

    def test_stale_data_and_bad_interval(self):
        self.assertIn("stale_data", codes(check([bar()], as_of_ms=4 * TF)))
        self.assertIn("invalid_interval", codes(check([bar(close_time_ms=TF - 1)])))

    def test_invalid_config_rejected(self):
        with self.assertRaises(ValueError):
            check([bar()], timeframe_ms=0)
        with self.assertRaises(ValueError):
            check([bar()], max_age_ms=-1)

    def test_does_not_mutate_input(self):
        candle = bar()
        original = candle.copy()
        check([candle])
        self.assertEqual(candle, original)


if __name__ == "__main__":
    unittest.main()
