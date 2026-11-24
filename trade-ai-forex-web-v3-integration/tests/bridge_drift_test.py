"""Old/new bridge differential fixtures; never loads the real MT5 extension."""
import ast
import importlib.util
import json
import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'release/bridge-drift-audit-9124'
sys.path.insert(0, str((Path(__file__).resolve().parents[2] / 'day-trader-skill')))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

audit = load('bridge_audit', ROOT/'tools/bridge-drift-audit.py')

class Account:
    currency = 'USC'
    server = 'Exness-MT5Real50'
    trade_mode = 2
    login = 123  # synthetic fixture, never a real account identifier
    @property
    def balance(self):
        raise AssertionError('REAL balance must never be read')

class FakeTerminal(types.ModuleType):
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_CONTEST = 1
    ACCOUNT_TRADE_MODE_REAL = 2
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    def __init__(self):
        super().__init__('MetaTrader5')
        for tf in ('M1','M5','M15','M30','H1','H4','D1'):
            setattr(self, 'TIMEFRAME_'+tf, tf)
        self.calls = []
        self.connected = True
        self.visible = True
        self.account = Account()
        self.info = NS(visible=True, digits=5, point=.00001, trade_tick_size=.00001,
                       trade_contract_size=1000, trade_tick_value=.01,
                       volume_min=.01, volume_max=10., volume_step=.01,
                       currency_profit='USD', currency_base='EUR', trade_stops_level=0)
        self.profit = -100.
        self.now = int(time.time())//300*300
    def terminal_info(self):
        self.calls.append(('terminal_info',))
        return NS(connected=self.connected)
    def account_info(self):
        self.calls.append(('account_info',))
        return self.account
    def symbol_info(self, symbol):
        self.calls.append(('symbol_info', symbol))
        self.info.visible = self.visible
        return self.info
    def symbol_info_tick(self, symbol):
        self.calls.append(('symbol_info_tick', symbol))
        return NS(bid=1.1, ask=1.1001, time=int(time.time()))
    def copy_rates_from_pos(self, symbol, tf, start, count):
        self.calls.append(('copy_rates_from_pos', symbol, tf, start, count))
        return [dict(time=self.now-i*300, open=1., high=1.2, low=.9,
                     close=1.1, tick_volume=10) for i in reversed(range(min(count,3)))]
    def order_calc_profit(self, action, symbol, lot, entry, stop):
        self.calls.append(('order_calc_profit', symbol))
        return None if self.profit is None else self.profit*lot
    def symbol_select(self, symbol, enabled):
        self.calls.append(('symbol_select', symbol, enabled))
        self.visible = True
        return True
    def shutdown(self): self.calls.append(('shutdown',))
    def initialize(self, **kwargs):
        self.calls.append(('initialize', kwargs))
        return False
    def last_error(self): return (1, 'synthetic fixture failure')
    def __getattr__(self, name):
        if name in ('order_send','order_check','login','logout','positions_close'):
            raise AssertionError('Forbidden real-operation method '+name)
        raise AttributeError(name)

def bridge(version='observed'):
    fake = FakeTerminal()
    with patch.dict(sys.modules, {'MetaTrader5': fake}):
        obj = load('fixture_bridge_'+version, OUT/(version+'-mt5_bridge.py'))
    # Do not enter TestClient lifespan: even fixture shutdown is tested explicitly.
    return obj, fake, TestClient(obj.app)

PARAMS = dict(balance=10000, risk_percent=1, entry=2, stop_loss=1)

class BridgeDriftTests(unittest.TestCase):
    def test_exact_delta_and_recovered_hashes(self):
        result = audit.source_audit()
        self.assertEqual(result['old_sha256'], audit.OLD)
        self.assertEqual(result['current_sha256'], audit.CURRENT)
        self.assertTrue(result['normalized_executable_rest_equal'])

    def test_route_import_and_no_order_surface_unchanged(self):
        old, _, oc = bridge('approved'); new, _, nc = bridge()
        self.assertEqual(oc.get('/openapi.json').json(), nc.get('/openapi.json').json())
        self.assertEqual({r.path for r in old.app.routes}, {r.path for r in new.app.routes})
        tree = ast.parse((OUT/'observed-mt5_bridge.py').read_text())
        self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr in
                            {'order_send','order_check','login','logout'} for n in ast.walk(tree)))

    def test_all_19_chart_aliases_fixture_only(self):
        obj, fake, client = bridge()
        for symbol in sorted(obj.SYMBOLS):
            with self.subTest(symbol=symbol):
                response = client.get('/api/candles', params={'symbol':symbol, 'limit':3})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['symbol'], symbol)
                self.assertIn(('copy_rates_from_pos', symbol+'c','M5',0,3), fake.calls)

    def test_all_19_metadata_aliases_fixture_only(self):
        obj, _, client = bridge()
        for symbol in obj.SYMBOLS:
            with self.subTest(symbol=symbol):
                data = client.get('/api/symbol-spec', params={'symbol':symbol}).json()
                self.assertEqual(data['symbol'], symbol)
                self.assertEqual(data['account_currency'], 'USC')
                self.assertNotIn('login', data)
                self.assertNotIn('balance', data)

    def test_original_four_contracts_differential(self):
        old, of, oc = bridge('approved'); new, nf, nc = bridge()
        of.now = nf.now = 1800000000
        for symbol in old.SYMBOLS:
            for route in ('/api/candles','/api/symbol-spec'):
                with self.subTest(symbol=symbol, route=route):
                    a = oc.get(route, params={'symbol':symbol}).json()
                    b = nc.get(route, params={'symbol':symbol}).json()
                    a.pop('captured_at_utc',None); b.pop('captured_at_utc',None)
                    if route.endswith('candles'):
                        a['tick'].pop('time'); b['tick'].pop('time')
                    self.assertEqual(a,b)

    def test_four_risk_contracts_buy_sell_differential(self):
        old, _, oc = bridge('approved'); _, _, nc = bridge()
        for symbol in old.SYMBOLS:
            for side in ('BUY','SELL'):
                query = {**PARAMS, 'symbol':symbol, 'direction':side,
                         'stop_loss':1 if side=='BUY' else 3}
                a = oc.get('/api/risk-preview', params=query)
                b = nc.get('/api/risk-preview', params=query)
                self.assertEqual(a.status_code,200)
                self.assertEqual(a.json(),b.json())
                self.assertLessEqual(b.json()['estimated_loss_at_sl'],100)
                self.assertFalse(b.json()['order_sent'])

    def test_added_15_risk_symbols_rejected_before_terminal(self):
        obj, fake, client = bridge()
        for symbol in obj.SYMBOLS-obj.RISK_SYMBOLS:
            with self.subTest(symbol=symbol):
                self.assertEqual(client.get('/api/risk-preview',params={**PARAMS,'symbol':symbol}).status_code,400)
        self.assertEqual(fake.calls,[])

    def test_bad_symbol_and_timeframe_rejected_without_terminal(self):
        _, fake, client = bridge()
        for path in ('/api/candles?symbol=BAD','/api/symbol-spec?symbol=BAD',
                     '/api/candles?timeframe=M2'):
            self.assertEqual(client.get(path).status_code,400)
        self.assertEqual(fake.calls,[])

    def test_query_bounds_validation_without_terminal(self):
        _, fake, client = bridge()
        for query in ({'limit':0},{'limit':501}):
            self.assertEqual(client.get('/api/candles',params=query).status_code,422)
        self.assertEqual(client.get('/api/risk-preview',params={**PARAMS,'risk_percent':11}).status_code,422)
        self.assertEqual(fake.calls,[])

    def test_chart_forming_bar_and_cache_contract(self):
        _, fake, client = bridge()
        response = client.get('/api/candles')
        self.assertEqual(response.headers['cache-control'],'no-store')
        stamps = [c['time'] for c in response.json()['candles']]
        self.assertEqual(stamps,sorted(stamps))
        self.assertEqual(stamps[-1],fake.now) # chart includes forming bar by design

    def test_cors_fixed_origin(self):
        _, _, client = bridge()
        good = client.get('/api/health',headers={'Origin':'http://127.0.0.1:5173'})
        bad = client.get('/api/health',headers={'Origin':'https://unknown.invalid'})
        self.assertEqual(good.headers['access-control-allow-origin'],'http://127.0.0.1:5173')
        self.assertNotIn('access-control-allow-origin',bad.headers)

    def test_disconnected_health_is_passive(self):
        _, fake, client = bridge(); fake.connected=False
        self.assertFalse(client.get('/api/health').json()['connected'])
        self.assertEqual(fake.calls,[('terminal_info',)])

    def test_preexisting_reconnect_and_throttle_fixture_only(self):
        _, fake, client = bridge(); fake.connected=False
        self.assertEqual(client.get('/api/candles').status_code,503)
        self.assertEqual(client.get('/api/candles').status_code,503)
        self.assertEqual(sum(c[0]=='initialize' for c in fake.calls),1)
        self.assertIn(('initialize',{'timeout':5000}),fake.calls)
        self.assertIn(('shutdown',),fake.calls)

    def test_preexisting_marketwatch_mutation_fixture_only(self):
        _, fake, client = bridge(); fake.visible=False
        self.assertEqual(client.get('/api/symbol-spec').status_code,200)
        self.assertIn(('symbol_select','XAUUSDc',True),fake.calls)

    def test_preexisting_real_prefix_guard_and_misleading_demo_label(self):
        _, fake, client = bridge()
        fake.account.server='Exness-OtherReal'
        response=client.get('/api/risk-preview',params=PARAMS)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['demo_only'])
        fake.account.currency='USD'
        self.assertEqual(client.get('/api/risk-preview',params=PARAMS).status_code,403)

    def test_market_metadata_has_no_real_account_guard(self):
        _, fake, client = bridge(); fake.account.currency='USD'
        self.assertEqual(client.get('/api/symbol-spec').json()['account_currency'],'USD')
        fake.info.volume_step=0
        self.assertEqual(client.get('/api/symbol-spec').status_code,503)

    def test_risk_oracle_failure_and_below_minimum(self):
        _, fake, client = bridge(); fake.profit=None
        self.assertEqual(client.get('/api/risk-preview',params=PARAMS).status_code,503)
        fake.profit=-100000.
        data=client.get('/api/risk-preview',params=PARAMS).json()
        self.assertEqual(data['status'],'below_minimum')
        self.assertIsNone(data['suggested_lot'])

    def test_v5_exact_account_guard_and_no_real_balance_read(self):
        from forex.providers import MT5Provider
        from forex.core import DataError
        fake=FakeTerminal(); provider=MT5Provider(fake,{'EURUSD':'EURUSDc'}); provider.connected=True
        self.assertIsNone(provider.account_preflight('REAL_READONLY_DATA','Exness-MT5Real50','USC')['balance'])
        fake.account.server='Exness-OtherReal'
        with self.assertRaises(DataError):provider.metadata('EURUSD')

    def test_v5_closed_candles_and_invisible_real_refusal(self):
        from forex.providers import MT5Provider
        from forex.core import DataError
        fake=FakeTerminal(); provider=MT5Provider(fake,{'EURUSD':'EURUSDc'}); provider.connected=True
        provider.account_preflight('REAL_READONLY_DATA','Exness-MT5Real50','USC')
        bars=provider.candles('EURUSD','M5',2)
        self.assertTrue(all(b['time']+300<=time.time() for b in bars))
        self.assertNotIn(fake.now,[b['time'] for b in bars])
        fake.visible=False
        with self.assertRaises(DataError):provider.metadata('EURUSD')
        self.assertFalse(any(c[0]=='symbol_select' for c in fake.calls))

if __name__=='__main__':unittest.main(verbosity=2)
