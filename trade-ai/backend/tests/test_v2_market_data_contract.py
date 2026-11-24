import unittest

from market_ai.v2.market_data_contract import (
    Candle, Instrument, from_binance_spot_kline, validate_series,
)


def instrument(symbol="BTCUSDT", market="crypto_spot"):
    return Instrument(symbol, market, "binance", "last", "spot", "USDT")


def candle(index=0, inst=None, source="binance_spot"):
    return Candle(
        instrument=inst or instrument(),
        open_time_ms=index * 60_000,
        close_time_ms=(index + 1) * 60_000,
        is_final=True,
        open=100, high=103, low=99, close=101,
        volume=12, volume_kind="real", source=source,
    )


def codes(report):
    return {issue.code for issue in report.issues}


class MarketDataContractTests(unittest.TestCase):
    def test_blank_or_nonstring_instrument_identity_is_rejected(self):
        from dataclasses import replace
        instrument = Instrument("BTCUSDT", "crypto_spot", "binance", "last", "spot", "USDT")
        for field in ("symbol", "market", "venue", "quote_currency"):
            for value in (" ", 123, None):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    replace(instrument, **{field: value})

    def test_malformed_objects_and_missing_source_fail_closed(self):
        from dataclasses import replace
        instrument = Instrument("BTCUSDT", "crypto_spot", "binance", "last", "spot", "USDT")
        candle = Candle(instrument, 0, 60000, True, 100, 101, 99, 100, 10, "real", "source")
        for bad, expected in ((None, "invalid_candle"), ({}, "invalid_candle"),
                              (replace(candle, instrument="invalid"), "invalid_instrument"),
                              (replace(candle, source=" "), "mixed_or_missing_source"),
                              (replace(candle, source=123), "mixed_or_missing_source")):
            with self.subTest(bad=bad):
                report = validate_series([bad], timeframe_ms=60000, as_of_ms=120000, max_age_ms=120000)
                self.assertFalse(report.ok)
                self.assertIn(expected, {issue.code for issue in report.issues})

    def test_same_instrument_valid(self):
        report = validate_series(
            [candle(0), candle(1)],
            timeframe_ms=60_000, as_of_ms=120_000, max_age_ms=60_000,
        )
        self.assertTrue(report.ok)

    def test_mixed_instruments_rejected(self):
        report = validate_series(
            [candle(0), candle(1, inst=instrument("ETHUSDT"))],
            timeframe_ms=60_000, as_of_ms=120_000, max_age_ms=60_000,
        )
        self.assertIn("mixed_instrument", codes(report))

    def test_mixed_sources_rejected(self):
        report = validate_series(
            [candle(0), candle(1, source="different_provider")],
            timeframe_ms=60_000, as_of_ms=120_000, max_age_ms=60_000,
        )
        self.assertIn("mixed_or_missing_source", codes(report))

    def test_binance_inclusive_close_time_is_normalized(self):
        raw = [0, "100", "103", "99", "101", "12", 59_999]
        result = from_binance_spot_kline(
            raw, symbol="BTCUSDT", quote_currency="USDT", as_of_ms=60_000,
        )
        self.assertEqual(result.close_time_ms, 60_000)
        self.assertTrue(result.is_final)
        self.assertEqual(result.instrument.contract_type, "spot")

    def test_unclosed_binance_bar_rejected_by_quality_gate(self):
        raw = [0, "100", "103", "99", "101", "12", 59_999]
        result = from_binance_spot_kline(
            raw, symbol="BTCUSDT", quote_currency="USDT", as_of_ms=59_000,
        )
        report = validate_series(
            [result], timeframe_ms=60_000, as_of_ms=59_000, max_age_ms=60_000,
        )
        self.assertFalse(report.ok)
        self.assertIn("unfinished_candle", codes(report))

    def test_missing_binance_fields_raise(self):
        with self.assertRaises(ValueError):
            from_binance_spot_kline(
                [1, 2], symbol="BTCUSDT", quote_currency="USDT", as_of_ms=60_000,
            )


if __name__ == "__main__":
    unittest.main()
