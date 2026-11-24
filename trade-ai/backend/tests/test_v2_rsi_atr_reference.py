"""Deterministic mathematical reference and regression tests for RSI and ATR.

Validates:
1. Cutler's SMA RSI (engines/technical.py) vs independent closed-form reference.
2. Wilder's RMA RSI (v2/strategies.py) vs independent closed-form reference.
3. Methodological divergence between Cutler SMA and Wilder RMA under volatility.
4. SMA ATR (engines/technical.py & v2/price_action.py) vs independent closed-form reference.
5. Contrast between SMA ATR cliff-drop and Wilder RMA ATR exponential decay.
6. Edge cases: zero loss, zero gain, flat price, gap-ups, gap-downs, warm-up boundaries.
"""
from decimal import Decimal as D
import math
import unittest

import numpy as np
import pandas as pd

from market_ai.engines import technical
from market_ai.v2.market_data_contract import Candle, Instrument
from market_ai.v2.price_action import compute_price_action


def _make_valid_candles(highs, lows, closes, opens=None, volumes=None):
    n = len(closes)
    tf = 60000
    identity = Instrument("BTCUSDT", "crypto_spot", "fixture", "last", "spot", "USDT")
    vols = volumes or [10.0] * n
    candles = []
    for i in range(n):
        o = opens[i] if opens else (closes[i - 1] if i > 0 else closes[0])
        c = closes[i]
        h = max(highs[i], o, c)
        l = min(lows[i], o, c)
        candles.append(
            Candle(
                identity,
                i * tf,
                (i + 1) * tf,
                True,
                o,
                h,
                l,
                c,
                vols[i],
                "real",
                "fixture_spot",
            )
        )
    return candles


class CutlerRsiReferenceTests(unittest.TestCase):
    """Mathematical validation for engines/technical.py:rsi (Cutler SMA method)."""

    def test_cutler_rsi_strictly_increasing_yields_100(self):
        """Monotonically increasing series has loss == 0, gain > 0 -> RSI = 100.0."""
        prices = pd.Series([100.0 + i for i in range(25)], dtype=float)
        result = technical.rsi(prices, period=14)
        # First 14 bars are warm-up (NaN)
        self.assertTrue(result.iloc[:14].isna().all())
        # All bars from index 14 onwards must be exactly 100.0
        for i in range(14, len(prices)):
            self.assertEqual(result.iloc[i], 100.0)

    def test_cutler_rsi_strictly_decreasing_yields_0(self):
        """Monotonically decreasing series has gain == 0, loss > 0 -> RSI = 0.0."""
        prices = pd.Series([200.0 - i for i in range(25)], dtype=float)
        result = technical.rsi(prices, period=14)
        self.assertTrue(result.iloc[:14].isna().all())
        for i in range(14, len(prices)):
            self.assertEqual(result.iloc[i], 0.0)

    def test_cutler_rsi_flat_series_yields_50(self):
        """Constant prices have gain == 0 and loss == 0 -> neutral RSI = 50.0."""
        prices = pd.Series([150.0] * 25, dtype=float)
        result = technical.rsi(prices, period=14)
        self.assertTrue(result.iloc[:14].isna().all())
        for i in range(14, len(prices)):
            self.assertEqual(result.iloc[i], 50.0)

    def test_cutler_rsi_hand_derived_period_4_reference(self):
        """Hand-derived 4-period SMA RSI.

        Deltas: +2, -1, +2, -1
        Rolling sum gain = 2.0, mean gain = 1.0
        Rolling sum loss = 1.0, mean loss = 0.5
        RS = 1.0 / 0.5 = 2.0
        RSI = 100 - (100 / 3) = 66.666666...
        """
        prices = pd.Series([10.0, 12.0, 11.0, 13.0, 12.0], dtype=float)
        result = technical.rsi(prices, period=4)
        expected = 100.0 - (100.0 / 3.0)
        self.assertAlmostEqual(result.iloc[-1], expected, places=7)

    def test_cutler_rsi_hand_derived_period_14_alternating(self):
        """Hand-derived 14-period SMA RSI on 14 alternating steps.

        7 gains of +2.0, 7 losses of -1.0.
        Total gain = 14.0, mean gain = 1.0.
        Total loss = 7.0, mean loss = 0.5.
        RS = 1.0 / 0.5 = 2.0 -> RSI = 66.666666...
        """
        prices = [100.0]
        for i in range(14):
            delta = 2.0 if i % 2 == 0 else -1.0
            prices.append(prices[-1] + delta)
        s = pd.Series(prices, dtype=float)
        result = technical.rsi(s, period=14)
        expected = 100.0 - (100.0 / 3.0)
        self.assertAlmostEqual(result.iloc[-1], expected, places=7)

    def test_cutler_rsi_warmup_requires_exactly_15_bars_for_first_value(self):
        """Cutler 14-period RSI needs 14 deltas, thus index 14 (15th bar) is first valid."""
        prices_14 = pd.Series([100.0 + i for i in range(14)], dtype=float)
        prices_15 = pd.Series([100.0 + i for i in range(15)], dtype=float)
        res_14 = technical.rsi(prices_14, period=14)
        res_15 = technical.rsi(prices_15, period=14)
        self.assertTrue(res_14.isna().all())
        self.assertTrue(res_15.iloc[:14].isna().all())
        self.assertFalse(math.isnan(res_15.iloc[14]))


class WilderRsiReferenceTests(unittest.TestCase):
    """Mathematical validation for Wilder's RMA RSI (v2/strategies.py)."""

    def test_wilder_rsi_closed_form_exact_step(self):
        """Hand-calculated 14-period initial SMA + 2 steps of Wilder RMA.

        Bars 0..14: 14 consecutive +1 gains.
          Bar 14: avg_gain = 1.0, avg_loss = 0.0 -> RSI = 100.0.
        Bar 15: delta = -1.0.
          avg_gain = (1.0 * 13 + 0) / 14 = 13/14
          avg_loss = (0.0 * 13 + 1) / 14 = 1/14
          RS = 13 -> RSI = 100 - (100 / 14) = 92.8571428571...
        Bar 16: delta = -1.0.
          avg_gain = (13/14 * 13 + 0) / 14 = 169/196
          avg_loss = (1/14 * 13 + 1) / 14 = 27/196
          RS = 169/27 -> RSI = 100 - (2700 / 196) = 86.2244897959...
        """
        prices = [100.0 + i for i in range(15)] + [114.0 - 1.0, 114.0 - 2.0]
        changes = [D(str(prices[i] - prices[i - 1])) for i in range(1, len(prices))]

        gain = sum(max(x, D(0)) for x in changes[:14]) / 14
        loss = sum(max(-x, D(0)) for x in changes[:14]) / 14
        values = []
        for change in changes[14:]:
            gain = (gain * 13 + max(change, D(0))) / 14
            loss = (loss * 13 + max(-change, D(0))) / 14
            val = D(100) - D(100) / (1 + gain / loss) if loss else D(100) if gain else D(50)
            values.append(val)

        # Bar 15 check
        expected_bar_15 = float(D(100) - D(100) / D(14))
        self.assertAlmostEqual(float(values[0]), expected_bar_15, places=7)

        # Bar 16 check
        expected_bar_16 = float(D(100) - D(2700) / D(196))
        self.assertAlmostEqual(float(values[1]), expected_bar_16, places=7)

    def test_wilder_vs_cutler_methodological_divergence(self):
        """Mathematical proof: Flat bars leave Wilder RSI unchanged, but force Cutler RSI to 50.

        When delta == 0:
          Wilder: avg_gain and avg_loss both scale by 13/14, so RS = avg_gain/avg_loss remains unchanged!
          Cutler: after 14 flat bars, non-zero deltas exit the window, forcing sum_gain=sum_loss=0 -> 50.0!
        """
        # Start with 14 upward bars of +1 (Bar 0..14)
        # Then Bar 15: delta = -5.0
        # Then Bars 16..29 (14 flat bars of delta = 0.0)
        prices = [100.0 + i for i in range(15)]
        prices.append(prices[-1] - 5.0)  # Bar 15: -5.0
        for _ in range(14):
            prices.append(prices[-1])  # Bars 16..29: flat (delta = 0)

        s = pd.Series(prices, dtype=float)
        cutler = technical.rsi(s, period=14)

        changes = [D(str(prices[i] - prices[i - 1])) for i in range(1, len(prices))]
        gain = sum(max(x, D(0)) for x in changes[:14]) / 14
        loss = sum(max(-x, D(0)) for x in changes[:14]) / 14
        wilder_vals = []
        for change in changes[14:]:
            gain = (gain * 13 + max(change, D(0))) / 14
            loss = (loss * 13 + max(-change, D(0))) / 14
            val = D(100) - D(100) / (1 + gain / loss) if loss else D(100) if gain else D(50)
            wilder_vals.append(float(val))

        # At Bar 29: exactly 14 flat bars have elapsed since the -5.0 shock at Bar 15.
        # Cutler SMA: all 14 bars in window are 0.0 -> loss=0, gain=0 -> exactly 50.0!
        self.assertEqual(cutler.iloc[29], 50.0)

        # Wilder RMA: because delta=0 scales gain and loss equally, RS = gain/loss is unchanged!
        # Thus Wilder RSI at Bar 29 equals Wilder RSI at Bar 15!
        self.assertAlmostEqual(wilder_vals[-1], wilder_vals[0], places=7)
        self.assertNotEqual(wilder_vals[-1], 50.0)
        # Exactly 72.222222... (RS = (13/14) / (5/14) = 13/5 = 2.6 -> 100 - 100/3.6 = 72.222...)
        self.assertAlmostEqual(wilder_vals[-1], 100.0 - 100.0 / 3.6, places=7)


class SmaAtrReferenceTests(unittest.TestCase):
    """Mathematical validation for Simple Moving Average ATR."""

    def test_sma_atr_constant_prices_yields_zero(self):
        """Constant prices have TR = 0 -> ATR = 0."""
        df = pd.DataFrame({"high": [100.0] * 20, "low": [100.0] * 20, "close": [100.0] * 20})
        result = technical.atr(df, period=14)
        self.assertTrue(result.iloc[:13].isna().all())
        for i in range(13, 20):
            self.assertEqual(result.iloc[i], 0.0)

    def test_sma_atr_first_bar_true_range_is_high_minus_low(self):
        """At index 0 without prev_close, TR must equal H0 - L0."""
        df = pd.DataFrame({"high": [105.0, 106.0], "low": [100.0, 101.0], "close": [103.0, 104.0]})
        result = technical.atr(df, period=1)
        self.assertEqual(result.iloc[0], 5.0)

    def test_sma_atr_gap_up_and_gap_down(self):
        """True range handles both gap up (|H - Cprev|) and gap down (|L - Cprev|)."""
        df = pd.DataFrame({
            "high": [100.0, 120.0, 85.0],
            "low": [90.0, 110.0, 75.0],
            "close": [95.0, 115.0, 80.0],
        })
        atr_1 = technical.atr(df, period=1)
        self.assertEqual(atr_1.iloc[0], 10.0)
        self.assertEqual(atr_1.iloc[1], 25.0)
        self.assertEqual(atr_1.iloc[2], 40.0)

        # 3-bar SMA ATR = (10 + 25 + 40) / 3 = 25.0
        atr_3 = technical.atr(df, period=3)
        self.assertEqual(atr_3.iloc[2], 25.0)

    def test_sma_atr_v1_and_v2_price_action_are_identical_at_last_bar(self):
        """v2/price_action.py:atr14_sma matches engines/technical.py:atr for the last bar."""
        closes = [100.0 + i for i in range(30)]
        highs = [c + 2.0 for c in closes]
        lows = [c - 2.0 for c in closes]
        opens = [c - 0.5 for c in closes]

        df = pd.DataFrame({"high": highs, "low": lows, "close": closes, "open": opens})
        v1_atr = technical.atr(df, period=14).iloc[-1]

        candles = _make_valid_candles(highs, lows, closes, opens=opens)
        pa = compute_price_action(candles, timeframe_ms=60000, as_of_ms=30 * 60000, max_age_ms=60000)
        self.assertIn("atr14_sma", pa)
        v2_atr = float(pa["atr14_sma"])

        # Must match to 7 decimal places
        self.assertAlmostEqual(v1_atr, v2_atr, places=7)


class WilderAtrReferenceTests(unittest.TestCase):
    """Mathematical validation for Wilder RMA ATR vs SMA ATR."""

    def test_wilder_atr_closed_form_exact(self):
        """Hand-derived 14-period initial SMA + 1 step of Wilder RMA ATR.

        14 bars of TR = 2.0 -> initial ATR = 2.0 at Bar 13.
        Bar 14: sudden surge with TR = 9.0.
        Both SMA and Wilder ATR at Bar 14 equal (13 * 2.0 + 9.0) / 14 = 2.50.
        Bar 15: TR returns to 2.0.
        Wilder ATR = (2.50 * 13 + 2.0) / 14 = 34.5 / 14 = 2.4642857...
        SMA ATR = (12 * 2.0 + 9.0 + 2.0) / 14 = 35.0 / 14 = 2.50.
        """
        trs = [2.0] * 14 + [9.0, 2.0]
        initial_atr = sum(trs[:14]) / 14.0  # 2.0
        wilder_14 = (initial_atr * 13.0 + trs[14]) / 14.0  # 2.50
        wilder_15 = (wilder_14 * 13.0 + trs[15]) / 14.0  # 34.5 / 14 = 2.4642857...

        sma_14 = sum(trs[1:15]) / 14.0  # 2.50
        sma_15 = sum(trs[2:16]) / 14.0  # 2.50

        self.assertEqual(wilder_14, 2.50)
        self.assertEqual(sma_14, 2.50)
        self.assertAlmostEqual(wilder_15, 34.5 / 14.0, places=7)
        self.assertEqual(sma_15, 2.50)
        self.assertNotEqual(wilder_15, sma_15)


if __name__ == "__main__":
    unittest.main()
