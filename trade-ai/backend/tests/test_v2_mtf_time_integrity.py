"""Common decision time and closed-candle gates across timeframe snapshots."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from fastapi.testclient import TestClient

from market_ai.v2.api import create_app
from market_ai.v2.spot_provider import FixtureSpotProvider
from market_ai.v2.technical_adapter import TIMEFRAME_MS


NOW = 1_800_000_000_000
TOKEN = "mtf-time-fixture-token-not-a-secret"


class TimeShiftProvider(FixtureSpotProvider):
    def __init__(self, fault=None):
        super().__init__()
        self.fault = fault
        self.request_times = []

    def candles(self, symbol, timeframe, as_of_ms):
        self.request_times.append((timeframe, as_of_ms))
        bars = super().candles(symbol, timeframe, as_of_ms)
        if timeframe == "4H" and self.fault == "future":
            bars[-1] = replace(bars[-1], open_time_ms=as_of_ms,
                               close_time_ms=as_of_ms + TIMEFRAME_MS[timeframe])
        if timeframe == "4H" and self.fault == "stale":
            shift = 2 * TIMEFRAME_MS[timeframe]
            bars = [replace(b, open_time_ms=b.open_time_ms - shift,
                            close_time_ms=b.close_time_ms - shift) for b in bars]
        return bars


class MultiTimeframeIntegrityTests(TestCase):
    def analyze(self, fault):
        provider = TimeShiftProvider(fault)
        with TemporaryDirectory(prefix="v2-mtf-integrity-") as root:
            app = create_app(Path(root) / "isolated.sqlite", mode="fixture",
                             token=TOKEN, provider=provider, clock=lambda: NOW)
            with TestClient(app, headers={"Authorization": "Bearer " + TOKEN}) as client:
                response = client.post("/api/v2/analyze", json={
                    "data_mode": "fixture", "timeframe": "1H", "timeframes": ["4H"],
                    "idempotency_key": "mtf-" + str(fault),
                })
                self.assertEqual(response.status_code, 200, response.text)
                return response.json(), provider.request_times

    def test_each_frame_uses_same_decision_time_with_last_closed_candle(self):
        result, times = self.analyze(None)
        self.assertEqual(times, [("1H", NOW), ("4H", NOW)])
        self.assertTrue(result["quality"]["ok"], result["quality"])
        self.assertLessEqual(result["price_time_ms"], NOW)
        self.assertLessEqual(NOW - result["price_time_ms"], TIMEFRAME_MS["1H"])

    def test_future_or_stale_higher_frame_blocks_decision(self):
        for fault, issue in (("future", "future_candle"), ("stale", "stale_data")):
            with self.subTest(fault=fault):
                result, times = self.analyze(fault)
                self.assertEqual(times, [("1H", NOW), ("4H", NOW)])
                self.assertFalse(result["quality"]["ok"])
                self.assertTrue(any(issue in value for value in result["quality"]["issues"]))
                self.assertEqual(result["direction"], "WAIT")
                self.assertIsNone(result["levels"])
