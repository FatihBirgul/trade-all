"""Read-only observations for the additional broker symbols."""
import unittest

from forex.core import DATA_SYMBOLS, SYMBOLS, DataError
from forex.technical_preview import build_technical_preview
from test_forex import NOW, bars


class PreviewFeed:
    name = "fixture"

    def __init__(self):
        self.timestamp = NOW

    def metadata(self, symbol):
        return {"symbol": symbol, "broker_symbol": symbol + "c",
                "broker_server": "Exness-MT5Real50", "account_currency": "USC"}

    def quote(self, symbol):
        return {"symbol": symbol, "bid": 1900, "ask": 1900.1, "time": self.timestamp}

    def candles(self, symbol, timeframe, count):
        return bars(timeframe)[-count:]


class TechnicalPreviewTests(unittest.TestCase):
    def test_additional_symbol_is_observation_only(self):
        self.assertEqual(len(set(DATA_SYMBOLS)), 19)
        self.assertNotIn("AUDJPY", SYMBOLS)
        result = build_technical_preview(PreviewFeed(), "AUDJPY", now=NOW)
        self.assertEqual(result["final_decision"], "NO_TRADE")
        self.assertFalse(result["execution_permission"])
        self.assertIsNone(result["lot_size"])
        self.assertGreaterEqual(result["closed_candle_count"], 200)

    def test_stale_quotes_are_rejected(self):
        feed = PreviewFeed()
        feed.timestamp -= 121
        with self.assertRaisesRegex(DataError, "stale preview quote"):
            build_technical_preview(feed, "AUDJPY", now=NOW)
