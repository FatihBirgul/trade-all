import unittest

from market_ai.v2.narrative import build_safe_scenarios


class SafeNarrativeTests(unittest.TestCase):
    def test_neutral_without_levels_has_no_none_leak(self):
        scenarios = build_safe_scenarios("neutral", {})
        self.assertEqual(set(scenarios), {"bullish", "bearish", "neutral"})
        self.assertTrue(all("None" not in s for s in scenarios.values()))

    def test_partial_levels_do_not_produce_executable_scenario(self):
        scenarios = build_safe_scenarios("bullish", {"entry_low": 100, "target_1": None})
        self.assertIn("No validated bullish setup", scenarios["bullish"])
        self.assertTrue(all("None" not in s for s in scenarios.values()))

    def test_valid_bullish_geometry(self):
        z = dict(invalidation=95, entry_low=100, entry_high=102, target_1=110, target_2=120)
        scenarios = build_safe_scenarios("bullish", z)
        self.assertIn("110", scenarios["bullish"])
        self.assertIn("95", scenarios["bullish"])
        self.assertIn("No validated bearish", scenarios["bearish"])

    def test_valid_bearish_geometry(self):
        z = dict(invalidation=110, entry_low=100, entry_high=102, target_1=90, target_2=80)
        scenarios = build_safe_scenarios("bearish", z)
        self.assertIn("90", scenarios["bearish"])
        self.assertIn("above 110", scenarios["bearish"])

    def test_invalid_geometry_or_nonfinite_levels(self):
        z = dict(invalidation=95, entry_low=100, entry_high=102, target_1=99, target_2=120)
        self.assertIn("No validated", build_safe_scenarios("bullish", z)["bullish"])
        z["target_1"] = float("nan")
        self.assertIn("No validated", build_safe_scenarios("bullish", z)["bullish"])


if __name__ == "__main__":
    unittest.main()
