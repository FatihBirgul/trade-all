"""REAL mode reads metadata but never treats REAL balance as simulation capital."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from forex.api import app
from forex.core import DataError
from forex.providers import MT5Provider
from forex.unified import unified_analyze
from test_exness_cent import ALIASES, CentTerminal
from test_forex import fixture, NOW


class RealTerminal(CentTerminal):
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2
    mode = 2
    def __init__(self): self.mutations = []
    def terminal_info(self): return SimpleNamespace(connected=True)
    def account_info(self):
        class Account:
            login=54321
            server='Real-Server'
            currency='USC'
            trade_mode=2
            trade_allowed=True
            @property
            def balance(self): raise AssertionError('REAL balance must not be read')
        account=Account(); account.trade_mode=self.mode
        return account
    def symbol_info(self, symbol):
        info=super().symbol_info(symbol)
        if info: info.visible=True
        return info
    def symbol_select(self, symbol, enabled):
        self.mutations.append('symbol_select')
        raise AssertionError('REAL read-only mode must not select symbol')


class RealReadOnly(unittest.TestCase):
    def test_real_policy_reads_four_exact_aliases_without_mutation(self):
        terminal=RealTerminal(); provider=MT5Provider(terminal, ALIASES)
        result=provider.account_preflight('REAL_READONLY_DATA','Real-Server','USC')
        self.assertEqual(result, {'status':'PASS','currency':'USC','balance':None})
        for symbol,alias in ALIASES.items():
            self.assertEqual(provider.metadata(symbol)['broker_symbol'],alias)
        self.assertEqual(terminal.mutations,[])

    def test_policy_mode_server_currency_and_account_change(self):
        terminal=RealTerminal(); provider=MT5Provider(terminal, ALIASES)
        for mode in ('DEMO_ONLY','UNKNOWN'):
            with self.subTest(mode=mode), self.assertRaises(DataError):
                provider.account_preflight(mode,'Real-Server','USC')
        for server,currency in (('Other','USC'),('Real-Server','USD'),('Real-Server','USDC')):
            with self.subTest(server=server,currency=currency), self.assertRaises(DataError):
                provider.account_preflight('REAL_READONLY_DATA',server,currency)
        provider.account_preflight('REAL_READONLY_DATA','Real-Server','USC')
        terminal.mode=0
        with self.assertRaisesRegex(DataError,'account changed'):
            provider.metadata('XAUUSD')
        self.assertEqual(terminal.mutations,[])

    def test_account_switch_during_symbol_read_is_rejected(self):
        class SwitchingTerminal(RealTerminal):
            def symbol_info(self,symbol):
                info=super().symbol_info(symbol)
                self.mode=self.ACCOUNT_TRADE_MODE_DEMO
                return info
        terminal=SwitchingTerminal(); provider=MT5Provider(terminal,ALIASES)
        provider.account_preflight('REAL_READONLY_DATA','Real-Server','USC')
        with self.assertRaisesRegex(DataError,'account changed'):
            provider.metadata('XAUUSD')
        self.assertEqual(terminal.mutations,[])

    def test_api_ignores_legacy_balance_and_labels_hypothetical_capital(self):
        terminal=RealTerminal(); app.state.provider=MT5Provider(terminal,ALIASES)
        def evaluate(*args,**kwargs):
            p=fixture()
            p.data['XAUUSD']['metadata'].update(account_currency='USC',tick_value_currency='USC',
                                                  broker_symbol='XAUUSDc')
            return unified_analyze(p,'XAUUSD',now=NOW,balance=kwargs['balance'],
                                   balance_source=kwargs['balance_source'],
                                   account_mode=kwargs['account_mode'])
        try:
            env={'MT5_ANALYSIS_POLICY':'REAL_READONLY_DATA','MT5_EXPECTED_REAL_SERVER':'Real-Server',
                 'MT5_EXPECTED_REAL_CURRENCY':'USC'}
            with patch.dict('os.environ',env), patch('forex.api.unified_analyze',side_effect=evaluate):
                client=TestClient(app)
                base=client.post('/api/v5/analysis',json={'symbol':'XAUUSD','balance':10000})
                self.assertEqual(base.status_code,200,base.text)
                body=base.json()
                self.assertEqual(body['market_data_account_mode'],'REAL')
                self.assertEqual(body['risk_balance_source'],'NOT_PROVIDED')
                self.assertIsNone(body['lot_size'])
                self.assertEqual(body['trading_eligibility'],'NOT_EVALUATED')
                self.assertFalse(body['execution_permission'])
                sim=client.post('/api/v5/analysis',json={'symbol':'XAUUSD','balance':10000,
                    'hypothetical_capital':2500,'hypothetical_currency':'USC'})
                self.assertEqual(sim.status_code,200,sim.text)
                self.assertEqual(sim.json()['risk_balance_source'],'HYPOTHETICAL_CAPITAL')
                self.assertEqual(sim.json()['trading_eligibility'],'NOT_EVALUATED')
                self.assertGreater(sim.json()['lot_size'],0)
                wrong=client.post('/api/v5/analysis',json={'symbol':'XAUUSD',
                    'hypothetical_capital':2500,'hypothetical_currency':'USDC'})
                self.assertEqual(wrong.status_code,503)
            self.assertEqual(terminal.mutations,[])
        finally:
            app.state.provider=None

    def test_verified_currency_remains_visible_on_safe_data_refusal(self):
        p=fixture()
        del p.data['XAUUSD']['candles']['M15'][10]
        result=unified_analyze(p,'XAUUSD',now=NOW,account_mode='REAL',
                               account_currency_context='USC',balance_source='NOT_PROVIDED')
        self.assertEqual(result.final_decision,'INSUFFICIENT_DATA')
        self.assertEqual(result.account_currency,'USC')
        self.assertIsNone(result.lot_size)


if __name__=='__main__': unittest.main()
