"""Causal, descriptive-only checks against the immutable V2 chart Git blob."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from forex.api import app
from forex.contracts import Snapshot, canonical, capture
from forex.core import DataError
from forex.unified import unified_analyze
from forex.v2_bridge import configured_v2_extension
from forex.v2_chart_bridge import (SOURCE_COMMIT, SOURCE_SHA256,
                                   V2ChartPatternBridge, _load_source)
from test_forex import NOW, fixture


SOURCE_ROOT = Path(__file__).resolve().parents[2] / 'trade-ai-v2-antigravity'
DECISION_FIELDS = ('final_decision', 'legacy_signal', 'trading_eligibility',
                   'market_status', 'data_status', 'decision_reasons',
                   'entry_zone', 'stop_loss', 'take_profit_1', 'take_profit_2',
                   'spread', 'lot_size', 'risk_amount', 'risk_reward',
                   'account_currency', 'execution_permission', 'risk_policy')


def double_top(at=(200, 212), *, late_break=False):
    provider = fixture()
    for index in at:
        provider.data['XAUUSD']['candles']['M15'][index]['high'] = 1940
    if late_break:
        last = provider.data['XAUUSD']['candles']['M15'][-1]
        last.update(high=1945, close=1944)
    return provider


def double_bottom():
    provider = fixture()
    for index in (200, 212):
        provider.data['XAUUSD']['candles']['M15'][index]['low'] = 1870
    return provider


def prefix(snapshot, length):
    payload = snapshot.payload()
    payload['frames']['M15'] = payload['frames']['M15'][:length]
    payload['decision_close_utc'] = payload['frames']['M15'][-1]['close_time_utc']
    serialized = canonical(payload)
    return Snapshot(hashlib.sha256(serialized.encode()).hexdigest(), serialized)


class V2ChartBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = V2ChartPatternBridge(SOURCE_ROOT)

    def items(self, provider):
        snapshot = capture(provider, 'XAUUSD', 'M15', NOW)
        output = self.bridge.evaluate(snapshot, context_json='{}')
        self.assertEqual(output.snapshot_id, snapshot.snapshot_id)
        self.assertEqual(output.status, 'PARTIAL')
        return json.loads(output.data_json)['chart_patterns']['items'], snapshot

    def test_exact_commit_hash_and_dirty_checkout_is_not_read(self):
        self.assertEqual(self.bridge.source_sha256, SOURCE_SHA256)
        self.assertEqual(SOURCE_COMMIT[:7], 'c80c97f')
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('working tree read')):
            items, _ = self.items(double_top())
        self.assertIn('Double Top', {item['name'] for item in items})
        with TemporaryDirectory() as other:
            with self.assertRaisesRegex(DataError, 'untrusted V2 chart root'):
                _load_source(other)
        with patch('forex.v2_chart_bridge.SOURCE_SHA256', '0' * 64):
            with self.assertRaisesRegex(DataError, 'hash mismatch'):
                _load_source(SOURCE_ROOT)
        with patch('forex.v2_chart_bridge.NUMPY_VERSION', '0.0.0'):
            with self.assertRaisesRegex(DataError, 'NumPy version mismatch'):
                _load_source(SOURCE_ROOT)

    def test_pinned_source_has_no_order_network_or_dynamic_import_calls(self):
        content, _ = _load_source(SOURCE_ROOT)
        tree = ast.parse(content)
        calls = [node.func for node in ast.walk(tree) if isinstance(node, ast.Call)]
        forbidden = {'order_send', 'order_check', 'login', 'initialize', 'shutdown',
                     '__import__', 'eval', 'exec', 'open', 'connect', 'request'}
        called = {fn.id for fn in calls if isinstance(fn, ast.Name)}
        called |= {fn.attr for fn in calls if isinstance(fn, ast.Attribute)}
        self.assertFalse(called & forbidden)

    def test_confirmed_pivot_first_known_and_prefix_replay(self):
        items, snapshot = self.items(double_top())
        top, = [item for item in items if item['name'] == 'Double Top']
        frame = snapshot.payload()['frames']['M15']
        self.assertEqual(top['formed_at_utc'], frame[212]['close_time_utc'])
        self.assertEqual(top['first_known_utc'], frame[215]['close_time_utc'])
        self.assertEqual(top['confirmation_utc'], frame[215]['close_time_utc'])
        self.assertEqual(top['knowledge_scope'], 'PREFIX_REPLAY_IN_CAPTURE_WINDOW')
        self.assertEqual(top['confirmation_state'], 'STRUCTURAL_CONFIRMED')
        before = json.loads(self.bridge.evaluate(prefix(snapshot, 215), context_json='{}').data_json)
        after = json.loads(self.bridge.evaluate(prefix(snapshot, 216), context_json='{}').data_json)
        self.assertNotIn(top['pattern_id'], {p['pattern_id'] for p in before['chart_patterns']['items']})
        self.assertIn(top['pattern_id'], {p['pattern_id'] for p in after['chart_patterns']['items']})
        self.assertEqual(top['pattern_id'], self.items(double_top())[0][0]['pattern_id'])

    def test_double_bottom_has_the_same_causal_right_window(self):
        items, snapshot = self.items(double_bottom())
        bottom, = [item for item in items if item['name'] == 'Double Bottom']
        frame = snapshot.payload()['frames']['M15']
        self.assertEqual(bottom['formed_at_utc'], frame[212]['close_time_utc'])
        self.assertEqual(bottom['first_known_utc'], frame[215]['close_time_utc'])
        self.assertEqual(bottom['confirmation_utc'], frame[215]['close_time_utc'])
        self.assertEqual(bottom['direction'], 'BULLISH')
        before = json.loads(self.bridge.evaluate(prefix(snapshot, 215), context_json='{}').data_json)
        self.assertNotIn(bottom['pattern_id'],
                         {p['pattern_id'] for p in before['chart_patterns']['items']})

    def test_m15_h1_h4_use_their_own_closed_candle_clock(self):
        for timeframe, seconds in (('M15', 900), ('H1', 3600), ('H4', 14400)):
            with self.subTest(timeframe=timeframe):
                provider = double_top()
                if timeframe == 'H1':
                    rows = provider.data['XAUUSD']['candles']['M15']
                    for index, bar in enumerate(rows):
                        bar['time'] = NOW - (221 - index) * seconds
                    provider.data['XAUUSD']['candles']['H1'] = rows
                elif timeframe == 'H4':
                    for index in (200, 212):
                        provider.data['XAUUSD']['candles']['H4'][index]['high'] = 1940
                snapshot = capture(provider, 'XAUUSD', timeframe, NOW,
                                   confirmations=(timeframe,))
                items = json.loads(self.bridge.evaluate(snapshot, context_json='{}').data_json)
                top, = [item for item in items['chart_patterns']['items']
                        if item['name'] == 'Double Top']
                self.assertEqual(top['timeframe'], timeframe)
                self.assertEqual(top['first_known_utc'],
                                 snapshot.payload()['frames'][timeframe][215]['close_time_utc'])

    def test_expiry_invalidation_and_unsupported_breakout(self):
        expired, _ = self.items(double_top((170, 182)))
        top, = [item for item in expired if item['name'] == 'Double Top']
        self.assertEqual(top['age_bars'], 37)
        self.assertEqual(top['confirmation_state'], 'EXPIRED')
        broken, _ = self.items(double_top(late_break=True))
        self.assertFalse(any(item['name'] == 'Double Top' for item in broken))
        self.assertTrue(all(item['name'] not in ('Breakout', 'Breakdown') for item in expired + broken))
        self.assertTrue(all(item['invalidation_state'] == 'NOT_MODELED' for item in expired + broken))

    def test_unfinished_future_and_identity_are_rejected_before_bridge(self):
        for defect in ('unfinished', 'future', 'wrong_source', 'wrong_market',
                       'missing', 'unknown_session', 'future_h4', 'stale_h4'):
            provider = double_top()
            bars = provider.data['XAUUSD']['candles']['M15']
            if defect == 'unfinished':
                bars[-1]['is_final'] = False
            elif defect == 'future':
                bars[-1]['time'] = NOW + 900
            elif defect == 'wrong_source':
                bars[-1]['source'] = 'different-provider'
            elif defect == 'wrong_market':
                provider.data['XAUUSD']['metadata']['market_type'] = 'crypto_spot'
            elif defect == 'missing':
                bars.pop(-3)
            elif defect == 'unknown_session':
                bars.pop(-3)
                provider.data['XAUUSD']['metadata']['broker_hours'] = None
            elif defect == 'future_h4':
                provider.data['XAUUSD']['candles']['H4'][-1]['time'] = NOW
            else:
                for bar in provider.data['XAUUSD']['candles']['H4']:
                    bar['time'] -= 3 * 14400
            report = unified_analyze(provider, 'XAUUSD', now=NOW, extension=self.bridge)
            if defect == 'future_h4':
                # A future higher candle is discarded by the shared cutoff.
                self.assertEqual(report.final_decision, 'BUY_CANDIDATE')
                self.assertIsNotNone(report.chart_patterns)
            else:
                self.assertIn(report.final_decision, ('INSUFFICIENT_DATA', 'STALE_DATA'))
                self.assertIsNone(report.entry_zone)
                self.assertIsNone(report.chart_patterns)

    def test_buy_sell_wait_risk_and_session_are_unchanged(self):
        providers = [('BUY', double_top()), ('SELL', fixture()), ('WAIT', fixture())]
        sell = providers[1][1]
        for timeframe in ('M15', 'H4'):
            for index, bar in enumerate(sell.data['XAUUSD']['candles'][timeframe]):
                close = 2100 - index * .1 - (5 if index == 219 else 0)
                bar.update(open=close + .05, high=close + .2, low=close - .1, close=close)
        sell.data['XAUUSD']['quote'].update(bid=2073, ask=2073.2)
        wait = providers[2][1]
        wait.data['XAUUSD']['metadata']['trade_allowed'] = False
        for expected, provider in providers:
            with self.subTest(expected=expected):
                base = unified_analyze(provider, 'XAUUSD', now=NOW, balance=10000)
                extended = unified_analyze(provider, 'XAUUSD', now=NOW, balance=10000,
                                           extension=self.bridge)
                self.assertEqual({key: getattr(base, key) for key in DECISION_FIELDS},
                                 {key: getattr(extended, key) for key in DECISION_FIELDS})
                self.assertFalse(extended.execution_permission)
                if expected == 'BUY':
                    self.assertEqual(base.final_decision, 'BUY_CANDIDATE')
                    self.assertEqual(extended.chart_patterns['role'], 'DESCRIPTIVE_ONLY')
                    self.assertGreater(extended.lot_size, 0)
                elif expected == 'SELL':
                    self.assertEqual(base.final_decision, 'SELL_CANDIDATE')
                else:
                    self.assertEqual(base.final_decision, 'MARKET_CLOSED')

    def test_session_risk_veto_and_tick_volume_remain_enforced(self):
        provider = double_top()
        provider.data['XAUUSD']['metadata']['broker_hours'] = None
        base = unified_analyze(provider, 'XAUUSD', now=NOW)
        extended = unified_analyze(provider, 'XAUUSD', now=NOW, extension=self.bridge)
        self.assertEqual(base.final_decision, extended.final_decision)
        self.assertEqual(base.final_decision, 'NO_TRADE')
        provider = double_top()
        for bars in provider.data['XAUUSD']['candles'].values():
            for bar in bars:
                bar['tick_volume'] = 50
        extended = unified_analyze(provider, 'XAUUSD', now=NOW, extension=self.bridge)
        self.assertIn('real_volume', extended.missing_capabilities)
        self.assertIn('real_volume_methods', extended.missing_capabilities)
        self.assertEqual(extended.chart_patterns['role'], 'DESCRIPTIVE_ONLY')
        cent = double_top()
        cent.data['XAUUSD']['metadata'].update(account_currency='USC',
                                               tick_value_currency='USC',
                                               broker_symbol='XAUUSDc')
        base = unified_analyze(cent, 'XAUUSD', now=NOW, balance=10000)
        extended = unified_analyze(cent, 'XAUUSD', now=NOW, balance=10000,
                                   extension=self.bridge)
        self.assertEqual({key: getattr(base, key) for key in DECISION_FIELDS},
                         {key: getattr(extended, key) for key in DECISION_FIELDS})
        self.assertEqual(extended.account_currency, 'USC')
        self.assertEqual(extended.broker_symbol, 'XAUUSDc')

    def test_manual_api_and_configuration_fail_closed(self):
        provider = double_top()
        app.state.provider = provider
        app.state.analytical_extension = None
        try:
            with patch.dict(os.environ, {'V2_CHART_GIT_ROOT': str(SOURCE_ROOT)}, clear=False):
                with patch('forex.unified.datetime') as clock:
                    clock.now.return_value = datetime.fromtimestamp(NOW, timezone.utc)
                    clock.fromtimestamp.side_effect = datetime.fromtimestamp
                    response = TestClient(app).post('/api/v5/analysis',
                                                    json={'symbol': 'XAUUSD', 'balance': 10000})
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body['final_decision'], 'BUY_CANDIDATE')
            self.assertEqual(body['legacy_signal'], 'BUY')
            self.assertEqual(body['chart_patterns']['items'][0]['name'], 'Double Top')
            self.assertFalse(body['execution_permission'])
            with patch.dict(os.environ, {'V2_CHART_GIT_ROOT': 'C:/invalid'}, clear=False):
                failed = TestClient(app).post('/api/v5/analysis', json={'symbol': 'XAUUSD'})
                self.assertEqual(failed.status_code, 503)
                self.assertEqual(failed.json()['detail']['status'], 'DATA_UNAVAILABLE')
        finally:
            app.state.provider = None
            app.state.analytical_extension = None

    def test_candlestick_and_chart_bridges_compose_without_decision_votes(self):
        candle_source = (b'def detect(candles):\n'
                         b'    return [{"name":"fixture", "classification":"bullish", '
                         b'"location":len(candles)-2, "confirmed":True, "age_bars":1}]\n')
        with TemporaryDirectory() as root:
            engines = Path(root) / 'engines'
            engines.mkdir()
            file = engines / 'candlestick.py'
            file.write_bytes(candle_source)
            with patch.dict(os.environ, {'V2_CANDLESTICK_FILE': str(file),
                                          'V2_CANDLESTICK_SHA256': hashlib.sha256(candle_source).hexdigest(),
                                          'V2_CHART_GIT_ROOT': str(SOURCE_ROOT)}):
                extension = configured_v2_extension()
                provider = double_top()
                base = unified_analyze(provider, 'XAUUSD', now=NOW, balance=10000)
                report = unified_analyze(provider, 'XAUUSD', now=NOW, balance=10000,
                                         extension=extension)
        self.assertEqual({key: getattr(base, key) for key in DECISION_FIELDS},
                         {key: getattr(report, key) for key in DECISION_FIELDS})
        self.assertEqual(report.candlestick_patterns['items'][0]['name'], 'fixture')
        self.assertEqual(report.chart_patterns['items'][0]['name'], 'Double Top')
        self.assertEqual(report.confluence['independent_price_groups'],
                         base.confluence['independent_price_groups'])

    def test_bounded_runtime_and_output(self):
        snapshot = capture(double_top(), 'XAUUSD', 'M15', NOW)
        started = time.monotonic()
        output = self.bridge.evaluate(snapshot, context_json='{}')
        self.assertLess(time.monotonic() - started, 2.0)
        self.assertLess(len(output.data_json), 15_000)
        self.assertLessEqual(len(json.loads(output.data_json)['chart_patterns']['items']), 6)


if __name__ == '__main__':
    unittest.main()
