import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from forex.api import app
from forex.core import DataError
from forex.v2_bridge import V2CandlestickBridge
from forex.unified import unified_analyze
from test_forex import NOW, fixture


SOURCE = b'''def detect(candles):
    return [{'name': 'test_pattern', 'classification': 'bullish',
             'location': len(candles)-2, 'confirmed': True, 'age_bars': 1}]
'''


class V2BridgeTests(unittest.TestCase):
    def bridge(self, root):
        engines = Path(root) / 'engines'
        engines.mkdir()
        source = engines / 'candlestick.py'
        source.write_bytes(SOURCE)
        return source, V2CandlestickBridge(source, hashlib.sha256(SOURCE).hexdigest())

    def test_real_abi_descriptive_pattern_and_existing_plan(self):
        with TemporaryDirectory() as root:
            _, bridge = self.bridge(root)
            report = unified_analyze(fixture(), 'XAUUSD', now=NOW, balance=10000,
                                     extension=bridge)
        self.assertEqual(report.integration_status, 'PRIVATE_PARTIAL')
        self.assertEqual(report.final_decision, 'BUY_CANDIDATE')
        self.assertGreater(report.lot_size, 0)
        self.assertEqual(report.candlestick_patterns['role'], 'DESCRIPTIVE_ONLY')
        item = report.candlestick_patterns['items'][0]
        self.assertEqual(item['direction'], 'BULLISH')
        self.assertLessEqual(item['known_at_utc'], NOW)
        self.assertIn('real_volume_methods', report.missing_capabilities)
        strict = unified_analyze(fixture(), 'XAUUSD', now=NOW, extension=bridge,
                                 require_private=True)
        self.assertEqual(strict.final_decision, 'NO_TRADE')

    def test_wrong_hash_and_invalid_pattern_fail_closed(self):
        with TemporaryDirectory() as root:
            source, bridge = self.bridge(root)
            with self.assertRaisesRegex(DataError, 'hash mismatch'):
                V2CandlestickBridge(source, '0' * 64)
            bridge._detect = lambda rows: [{'location': len(rows), 'classification': 'bullish',
                                             'confirmed': True, 'age_bars': 0}]
            report = unified_analyze(fixture(), 'XAUUSD', now=NOW, extension=bridge)
            self.assertEqual(report.private_extension['status'], 'UNAVAILABLE')
            self.assertEqual(report.integration_status, 'PUBLIC_CORE_ONLY')

    def test_manual_api_configuration(self):
        with TemporaryDirectory() as root:
            source, _ = self.bridge(root)
            app.state.provider = fixture()
            app.state.analytical_extension = None
            try:
                with patch.dict(os.environ, {'V2_CANDLESTICK_FILE': str(source),
                                              'V2_CANDLESTICK_SHA256': hashlib.sha256(SOURCE).hexdigest()}):
                    with patch('forex.unified.datetime') as clock:
                        from datetime import datetime, timezone
                        clock.now.return_value = datetime.fromtimestamp(NOW, timezone.utc)
                        clock.fromtimestamp.side_effect = datetime.fromtimestamp
                        response = TestClient(app).post('/api/v5/analysis', json={'symbol':'XAUUSD'})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['candlestick_patterns']['items'][0]['name'], 'test_pattern')
            finally:
                app.state.provider = None
                app.state.analytical_extension = None


if __name__ == '__main__':
    unittest.main()
