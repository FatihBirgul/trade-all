import unittest
from unittest.mock import patch
from types import SimpleNamespace
from fastapi.testclient import TestClient

from forex.core import DataError
from forex.providers import MT5Provider
from forex.api import app
from forex.unified import unified_analyze
from test_forex import fixture, NOW


class AccountTerminal:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2
    mode = 0
    connected = True
    def __init__(self): self.symbol_reads = 0
    def initialize(self): return True
    def terminal_info(self): return SimpleNamespace(connected=self.connected)
    def account_info(self):
        return SimpleNamespace(trade_mode=self.mode, server='Demo-Server',
                               currency='USC', balance=12345.67, login=123456)
    def symbol_info(self, symbol):
        self.symbol_reads += 1
        raise AssertionError('preflight must precede symbol access')


class DemoPreflight(unittest.TestCase):
    def test_demo_pass_is_read_only(self):
        terminal = AccountTerminal()
        result = MT5Provider(terminal, {}).demo_preflight('Demo-Server', 'USC')
        self.assertEqual(result, {'status':'PASS', 'currency':'USC', 'balance':12345.67})
        self.assertEqual(terminal.symbol_reads, 0)

    def test_real_contest_unknown_disconnected_and_mismatch_block(self):
        for mode in (1, 2, 99, None):
            terminal = AccountTerminal(); terminal.mode = mode
            with self.subTest(mode=mode), self.assertRaisesRegex(DataError, 'demo preflight blocked'):
                MT5Provider(terminal, {}).demo_preflight('Demo-Server', 'USC')
            self.assertEqual(terminal.symbol_reads, 0)
        terminal = AccountTerminal(); terminal.connected = False
        with self.assertRaisesRegex(DataError, 'demo preflight blocked'):
            MT5Provider(terminal, {}).demo_preflight('Demo-Server', 'USC')
        terminal = AccountTerminal()
        for server, currency in (('Wrong-Server','USC'), ('Demo-Server','USD')):
            with self.subTest(server=server,currency=currency), self.assertRaisesRegex(DataError,'demo preflight blocked'):
                MT5Provider(terminal, {}).demo_preflight(server,currency)
        self.assertEqual(terminal.symbol_reads, 0)

    def test_sdk_enum_constants_are_required(self):
        terminal = AccountTerminal(); terminal.ACCOUNT_TRADE_MODE_DEMO = None
        with self.assertRaisesRegex(DataError, 'demo preflight blocked'):
            MT5Provider(terminal, {}).demo_preflight('Demo-Server', 'USC')

    def test_account_switch_is_detected_before_symbol_read(self):
        terminal = AccountTerminal()
        provider = MT5Provider(terminal, {'XAUUSD':'XAUUSDc'})
        provider.demo_preflight('Demo-Server', 'USC')
        terminal.mode = terminal.ACCOUNT_TRADE_MODE_REAL
        with self.assertRaisesRegex(DataError, 'account changed'):
            provider.metadata('XAUUSD')
        self.assertEqual(terminal.symbol_reads, 0)

    def test_v5_api_blocks_real_before_symbol_reads(self):
        terminal = AccountTerminal(); terminal.mode = terminal.ACCOUNT_TRADE_MODE_REAL
        app.state.provider = MT5Provider(terminal, {})
        try:
            with patch.dict('os.environ', {'MT5_EXPECTED_DEMO_SERVER':'Demo-Server',
                                            'MT5_EXPECTED_DEMO_CURRENCY':'USC'}):
                response = TestClient(app).post('/api/v5/analysis', json={'symbol':'XAUUSD'})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()['detail']['status'], 'DEMO_PREFLIGHT_BLOCKED')
            self.assertNotIn('123456', response.text)
            self.assertEqual(terminal.symbol_reads, 0)
        finally:
            app.state.provider = None

    def test_v5_api_blocks_missing_demo_configuration(self):
        terminal = AccountTerminal()
        app.state.provider = MT5Provider(terminal, {})
        try:
            with patch.dict('os.environ', {}, clear=True):
                response = TestClient(app).post('/api/v5/analysis', json={'symbol':'XAUUSD'})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()['detail']['status'], 'DEMO_PREFLIGHT_BLOCKED')
            self.assertEqual(terminal.symbol_reads, 0)
        finally:
            app.state.provider = None

    def test_v5_api_uses_broker_balance_not_caller_10000(self):
        terminal = AccountTerminal()
        app.state.provider = MT5Provider(terminal, {})
        try:
            def evaluate(*args, **kwargs):
                provider = fixture()
                provider.data['XAUUSD']['metadata'].update(account_currency='USC', tick_value_currency='USC')
                return unified_analyze(provider, 'XAUUSD', now=NOW,
                                       balance=kwargs['balance'],
                                       balance_source=kwargs['balance_source'])
            with patch.dict('os.environ', {'MT5_EXPECTED_DEMO_SERVER':'Demo-Server',
                                            'MT5_EXPECTED_DEMO_CURRENCY':'USC'}), \
                 patch('forex.api.unified_analyze', side_effect=evaluate):
                response = TestClient(app).post('/api/v5/analysis',
                                                json={'symbol':'XAUUSD', 'balance':10000})
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body['risk_balance_source'], 'BROKER_VERIFIED_DEMO')
            self.assertAlmostEqual(body['risk_policy']['sizing']['risk_cap'], 123.46)
            self.assertEqual(terminal.symbol_reads, 0)
        finally:
            app.state.provider = None

    def test_direct_caller_balance_is_only_hypothetical(self):
        report = unified_analyze(fixture(), 'XAUUSD', now=NOW, balance=10000)
        self.assertEqual(report.risk_balance_source, 'CALLER_SUPPLIED_HYPOTHETICAL')


if __name__ == '__main__': unittest.main()
