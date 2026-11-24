"""A structural pivot is knowable three closed bars after its location."""
import unittest

from market_ai.engines.chart_patterns import detect


class PivotCausalityTests(unittest.TestCase):
    def assert_confirmation_window(self, name, highs=(), lows=()):
        pivot = max(index for index, price in (*highs, *lows))
        candles = [dict(open=100, close=100, high=101, low=99) for _ in range(pivot + 5)]
        for index, price in highs:
            candles[index]["high"] = price
        for index, price in lows:
            candles[index]["low"] = price

        def matches(last_index):
            return [item for item in detect(candles[:last_index + 1]) if item["name"] == name]

        self.assertEqual(matches(pivot + 2), [])
        for age, decay in ((3, 0.20), (4, 0.10)):
            with self.subTest(age=age):
                found = matches(pivot + age)
                self.assertEqual(len(found), 1)
                self.assertEqual(found[0]["location"], pivot)
                self.assertEqual(found[0]["age_bars"], age)
                self.assertEqual(found[0]["recency_multiplier"], decay)
                self.assertTrue(found[0]["confirmed"])

    def test_double_top_causality(self):
        self.assert_confirmation_window("Double Top", highs=[(42, 108), (50, 108)])

    def test_double_bottom_causality(self):
        self.assert_confirmation_window("Double Bottom", lows=[(42, 92), (50, 92)])

    def test_head_and_shoulders_causality(self):
        self.assert_confirmation_window("Head and Shoulders", highs=[(42, 108), (50, 116), (58, 108)])

    def test_inverse_head_and_shoulders_causality(self):
        self.assert_confirmation_window("Inverse Head and Shoulders", lows=[(42, 92), (50, 84), (58, 92)])

    def test_ascending_triangle_causality(self):
        self.assert_confirmation_window("Ascending Triangle",
                                        highs=[(36, 108), (44, 108), (52, 108)],
                                        lows=[(40, 91), (48, 93), (56, 95)])

    def test_descending_triangle_causality(self):
        self.assert_confirmation_window("Descending Triangle",
                                        highs=[(36, 109), (44, 107), (52, 105)],
                                        lows=[(40, 94), (48, 94), (56, 94)])
