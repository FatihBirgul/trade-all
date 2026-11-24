"""V2 handoff risks checked against the existing manual V3 Forex pipeline."""
import unittest
from unittest.mock import patch

from forex.contracts import capture
from forex.core import DataError, analyze, indicators
from forex.strategies import candidates
from forex.unified import unified_analyze
from test_forex import NOW, fixture


class V2HandoffRegression(unittest.TestCase):
    def test_missing_rsi_cannot_confirm_a_direction(self):
        provider = fixture()
        with patch('forex.core.scanner.rsi', return_value=None):
            legacy = analyze(provider, 'XAUUSD', now=NOW)
            report = unified_analyze(provider, 'XAUUSD', now=NOW)
        self.assertEqual(legacy['signal'], 'WAIT')
        self.assertIsNone(legacy['plan'])
        self.assertEqual(legacy['data_status'], 'DATA_UNAVAILABLE')
        self.assertEqual(report.final_decision, 'INSUFFICIENT_DATA')
        self.assertIsNone(report.entry_zone)
        self.assertIsNone(report.lot_size)

    def test_zero_macd_histogram_does_not_confirm_momentum(self):
        provider = fixture()
        bars = provider.candles('XAUUSD', 'M15', 220)
        metrics = indicators(bars)
        metrics['macd'] = metrics['macd_signal']
        self.assertEqual(metrics['macd'] - metrics['macd_signal'], 0)
        self.assertFalse(any(v['strategy'] in ('trend_following', 'pullback')
                             for v in candidates(bars, metrics)))

    def test_future_higher_candle_does_not_change_decision_snapshot(self):
        provider = fixture()
        original = capture(provider, 'XAUUSD', 'M15', NOW)
        future = dict(provider.data['XAUUSD']['candles']['H4'][-1])
        future.update(time=NOW, open=5000, high=5001, low=4999, close=5000)
        provider.data['XAUUSD']['candles']['H4'].append(future)
        after = capture(provider, 'XAUUSD', 'M15', NOW)
        self.assertEqual(after.snapshot_id, original.snapshot_id)
        self.assertTrue(all(bar['close_time_utc'] <= after.payload()['decision_close_utc']
                            for bar in after.payload()['frames']['H4']))

    def test_stale_higher_and_unfinished_primary_fail_closed(self):
        provider = fixture()
        for bar in provider.data['XAUUSD']['candles']['H4']:
            bar['time'] -= 3 * 14400
        self.assertEqual(unified_analyze(provider, 'XAUUSD', now=NOW).final_decision,
                         'STALE_DATA')
        provider = fixture()
        provider.data['XAUUSD']['candles']['M15'][-1]['is_final'] = False
        self.assertEqual(unified_analyze(provider, 'XAUUSD', now=NOW).final_decision,
                         'INSUFFICIENT_DATA')

    def test_quote_provider_market_identity_and_volume_capability(self):
        provider = fixture()
        provider.data['XAUUSD']['quote']['provider'] = 'foreign-source'
        with self.assertRaisesRegex(DataError, 'quote provider identity mismatch'):
            capture(provider, 'XAUUSD', 'M15', NOW)
        provider = fixture()
        provider.data['XAUUSD']['metadata']['market_type'] = 'crypto_spot'
        with self.assertRaisesRegex(DataError, 'unsupported market identity'):
            capture(provider, 'XAUUSD', 'M15', NOW)
        provider = fixture()
        provider.data['XAUUSD']['candles']['M15'][-1].update(volume_kind='tick', tick_volume=100)
        self.assertEqual(capture(provider, 'XAUUSD', 'M15', NOW).payload()['frames']['M15'][-1]['volume_kind'], 'tick')
        provider.data['XAUUSD']['candles']['M15'][-1].update(volume_kind='real', volume=100)
        with self.assertRaisesRegex(DataError, 'real volume unavailable'):
            capture(provider, 'XAUUSD', 'M15', NOW)


if __name__ == '__main__':
    unittest.main()
