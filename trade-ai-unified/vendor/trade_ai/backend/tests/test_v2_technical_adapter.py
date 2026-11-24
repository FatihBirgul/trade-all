"""Normalized candle -> legacy engine contract smoke; no live services."""
from dataclasses import replace
import json
import math
from unittest import TestCase
from unittest.mock import patch

from market_ai.v2.market_data_contract import Candle, Instrument
from market_ai.v2.technical_adapter import compute_technical


TF = 60_000
IDENTITY = Instrument("BTCUSDT", "crypto_spot", "fixture", "last", "spot", "USDT")


def candles(n=300):
    values = [100 + i * .1 + math.sin(i) for i in range(n)]
    return [Candle(IDENTITY, i * TF, (i + 1) * TF, True, c - .2, c + 2, c - 2,
                   c, 10 + i % 5, "real", "fixture") for i, c in enumerate(values)]


def compute(series, **overrides):
    args = dict(timeframe="1m", as_of_ms=len(series) * TF, max_age_ms=TF)
    args.update(overrides)
    return compute_technical(series, **args)


class TechnicalAdapterTests(TestCase):
    def test_full_snapshot_has_reference_ema_and_valid_numeric_json(self):
        series = candles()
        snapshot = compute(series)
        self.assertEqual(snapshot.status, "available")
        ind = snapshot.payload()["indicators"]
        expected = series[0].close
        alpha = 2 / 21
        for candle in series[1:]:
            expected = alpha * candle.close + (1 - alpha) * expected
        self.assertAlmostEqual(ind["ema20"], expected, places=4)
        self.assertTrue(0 <= ind["rsi14"] <= 100)
        self.assertGreater(ind["atr14"], 0)
        json.dumps(snapshot.payload(), allow_nan=False)
        self.assertNotIn("ema200", snapshot.unavailable_indicators)

    def test_warmup_is_explicit(self):
        result = compute(candles(30))
        self.assertEqual(result.status, "available")
        self.assertNotIn("ema20", result.unavailable_indicators)
        self.assertIn("ema200", result.unavailable_indicators)
        self.assertEqual(compute(candles(29)).status, "unavailable")

    def test_invalid_batches_never_reach_legacy_engine(self):
        base = candles(30)
        invalid = [[], base[:-1], [replace(base[0], high=1)] + base[1:],
                   base[:-1] + [replace(base[-1], is_final=False)],
                   base[:-1] + [replace(base[-1], instrument=replace(IDENTITY, symbol="ETHUSDT"))]]
        with patch("market_ai.v2.technical_adapter.technical.compute", side_effect=AssertionError("QC bypass")):
            for series in invalid:
                with self.subTest(count=len(series)):
                    self.assertEqual(compute(series).reason, "data_quality_gate")

    def test_missing_or_tick_volume_not_replaced_with_zero(self):
        for kind, value in (("unavailable", None), ("tick", 20)):
            series = [replace(c, volume_kind=kind, volume=value) for c in candles(30)]
            self.assertEqual(compute(series).reason, "real_volume_required")

    def test_unsupported_timeframe_not_silently_changed(self):
        self.assertEqual(compute(candles(30), timeframe="bad").reason, "unsupported_timeframe")

    def test_future_data_and_stale_snapshots_rejected(self):
        for as_of in (29 * TF, 32 * TF):
            self.assertEqual(compute(candles(30), as_of_ms=as_of).reason, "data_quality_gate")

    def test_result_is_deterministic_and_payload_copy_is_independent(self):
        series = candles(30)
        original = tuple(series)
        result = compute(series)
        result.payload()["indicators"]["price"] = -100
        self.assertEqual(result, compute(series))
        self.assertEqual(tuple(series), original)
        self.assertGreater(result.payload()["indicators"]["price"], 0)

    def test_engine_failure_is_observable_and_unavailable(self):
        with patch("market_ai.v2.technical_adapter.technical.compute", side_effect=RuntimeError("fixture")):
            with self.assertLogs("market_ai.v2.technical_adapter", level="ERROR"):
                result = compute(candles(30))
        self.assertEqual(result.reason, "engine_error")
        self.assertEqual(result.payload(), {})
