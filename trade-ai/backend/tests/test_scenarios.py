"""The V1 server uses validated fallback levels and repairs incomplete AI copy."""
import unittest

from market_ai.engines.scenario import build, sanitize


class ScenarioDisplayTests(unittest.TestCase):
    def test_invalid_prices_cannot_create_a_setup(self):
        zones = dict(invalidation=90, entry_low=95, entry_high=96, target_1=100, target_2=110)
        self.assertIn("Bullish trigger", build("bullish", zones)["bullish"])
        for invalid in (None, False, -1, float("nan"), float("inf"), 10**400):
            with self.subTest(invalid=invalid):
                result = build("bullish", {**zones, "invalidation": invalid})
                self.assertIn("No validated bullish setup", result["bullish"])

    def test_missing_and_unsafe_fields_use_their_own_fallback(self):
        fallback = build("neutral", {})
        result = sanitize({"bullish": "Wait for confirmation.", "bearish": "Target None"}, fallback)
        self.assertEqual(result, {**fallback, "bullish": "Wait for confirmation."})
