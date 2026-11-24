"""Independent numeric oracles; fixture approvals are never live operator limits."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from forex.api import app
from forex.broker_contract import contract_observation
from forex.core import DataError, analyze, size_lots, risk_check
from forex.spread_policy import (ALIASES, SCHEMA, VERSION, bind_rule, load_policy,
                                 observed_spread, spread_status, validate_policy)
from forex.unified import unified_analyze
from forex.v2_chart_bridge import V2ChartPatternBridge
from forex.providers import MT5Provider
from test_forex import fixture, NOW
from test_real_readonly import RealTerminal


def policy(symbol='XAUUSD', maximum=.2, unit='PRICE', approved=True):
    return {'schema_version': SCHEMA, 'policy_version': VERSION, 'rules': [{
        'symbol': symbol, 'broker_symbol': ALIASES[symbol], 'broker_server': 'Exness-MT5Real50',
        'account_currency': 'USC', 'maximum': maximum, 'unit': unit,
        'effective_from_utc': '2026-01-01T00:00:00Z', 'effective_to_utc': '2028-01-01T00:00:00Z',
        'timeframes': ['M15', 'H4'], 'approval_status': 'OPERATOR_APPROVED' if approved else 'UNAPPROVED',
        'provenance': {'kind': 'OPERATOR_CONFIGURATION', 'reference': 'SYNTHETIC_TEST_ONLY'}}]}


def metadata(symbol='XAUUSD', maximum=.2, unit='PRICE'):
    meta = {**fixture().data['XAUUSD']['metadata'], 'symbol': symbol, 'broker_symbol': ALIASES[symbol],
            'broker_server': 'Exness-MT5Real50', 'account_currency': 'USC', 'tick_value_currency': 'USC',
            'base_currency': symbol[:3], 'profit_currency': symbol[3:], 'margin_currency': symbol[:3],
            'digits': 2, 'contract_size': 1, 'tick_value_profit': 1, 'tick_value_loss': 1,
            'trade_calc_mode_name': 'FOREX', 'trade_calc_mode': 0, 'trade_mode': 4, 'freeze_level': 0,
            'symbol_spread_points': 19, 'broker_contract_required': True, 'spread_policy_required': True}
    meta.update(_valuation_quote={'bid':100,'ask':100.2,'time':NOW-10},
                _valuation_as_of=NOW,_valuation_timeframe='M15')
    meta['broker_contract'] = contract_observation(meta, '2027-01-15T08:00:00Z')
    meta['spread_policy'] = bind_rule(policy(symbol, maximum, unit), symbol, ALIASES[symbol],
                                    'Exness-MT5Real50', 'USC')
    return meta


def quote(bid=100, ask=100.2):
    return {'bid': bid, 'ask': ask, 'time': NOW-10}


class SpreadPolicyTests(unittest.TestCase):
    def test_observed_price_points_and_symbol_spread_are_independent(self):
        # Expected 0.2 price / 20 points are hand-calculated, not production helpers.
        observed = observed_spread(quote(), metadata(), NOW)
        self.assertEqual(observed, {'price': .2, 'points': 20, 'symbol_spread_points': 19})

    def test_invalid_quotes_negative_zero_missing_ask_and_stale(self):
        for values in (quote(100,99), quote(100,100), {'bid':100,'time':NOW},
                       {**quote(), 'time': NOW-121}, {**quote(), 'bid': True}):
            with self.subTest(values=values):
                self.assertEqual(spread_status(metadata(), values, 'M15', NOW)['decision'], 'BLOCK')

    def test_wrong_point_and_missing_point_never_convert(self):
        for changes in ({'point': .1}, {'point': 0}, {'point': None}, {'digits': None}):
            with self.subTest(changes=changes):
                meta = metadata(unit='POINTS', maximum=20)
                meta.update(changes)
                self.assertEqual(spread_status(meta, quote(), 'M15', NOW)['decision'], 'BLOCK')

    def test_exact_price_boundary_and_spike(self):
        self.assertEqual(spread_status(metadata(), quote(), 'M15', NOW)['decision'], 'PASS')
        self.assertEqual(spread_status(metadata(), quote(100,100.21), 'M15', NOW)['decision'], 'BLOCK')

    def test_point_limit_conversion_exact(self):
        status = spread_status(metadata(maximum=20, unit='POINTS'), quote(), 'M15', NOW)
        self.assertEqual((status['decision'], status['max_allowed_price']), ('PASS', .2))

    def test_independent_gold_and_fx_limits(self):
        gold = metadata(maximum=.3)
        fx = metadata('EURUSD', maximum=.00015)
        fx.update(digits=5, point=.00001)
        self.assertEqual(spread_status(gold, quote(), 'M15', NOW)['decision'], 'PASS')
        self.assertEqual(spread_status(fx, quote(1.1,1.1002), 'M15', NOW)['decision'], 'BLOCK')

    def test_missing_max_cannot_use_observation_or_legacy_real_limit(self):
        meta = metadata(); meta.update(spread_policy=None, max_spread=999999)
        status = spread_status(meta, quote(), 'M15', NOW)
        self.assertEqual(status['decision'], 'BLOCK')
        self.assertIsNone(status['max_allowed_price'])

    def test_unapproved_draft_is_loadable_but_blocks(self):
        data=policy(maximum=None, approved=False)
        data['rules'][0]['effective_from_utc']=None
        data['rules'][0]['effective_to_utc']=None
        validate_policy(data)
        meta=metadata();meta['spread_policy']=bind_rule(data,'XAUUSD','XAUUSDc','Exness-MT5Real50','USC')
        self.assertEqual(spread_status(meta,quote(),'M15',NOW)['decision'],'BLOCK')

    def test_wrong_unit_pip_is_not_point(self):
        data=policy(unit='PIPS')
        with self.assertRaisesRegex(DataError,'unit'): validate_policy(data)

    def test_schema_and_policy_versions_rejected(self):
        for key in ('schema_version','policy_version'):
            data=policy();data[key]='unknown-version'
            with self.assertRaises(DataError): validate_policy(data)

    def test_wrong_symbol_server_and_currency_never_bind(self):
        for symbol,server,currency in [('XAUUSD','Other','USC'),('XAUUSD','Exness-MT5Real50','USD')]:
            bound=bind_rule(policy(),symbol,'XAUUSDc',server,currency)
            self.assertEqual(bound['status'],'CONFLICTING')
        meta=metadata();meta['spread_policy']['broker_symbol']='XAUUSD'
        self.assertEqual(spread_status(meta,quote(),'M15',NOW)['decision'],'BLOCK')

    def test_expiry_start_and_timeframe(self):
        for start,end,tf in [('2028-01-01T00:00:00Z',None,'M15'),
                             ('2025-01-01T00:00:00Z','2026-01-01T00:00:00Z','M15'),
                             ('2026-01-01T00:00:00Z',None,'H1')]:
            meta=metadata();meta['spread_policy'].update(effective_from_utc=start,effective_to_utc=end)
            self.assertEqual(spread_status(meta,quote(),tf,NOW)['decision'],'BLOCK')

    def test_loader_duplicate_keys_unknown_fields_budget_and_private_path(self):
        with TemporaryDirectory() as folder:
            file=Path(folder)/'operator-private.json'
            for text in ('{"schema_version":1,"schema_version":2}', '{}', 'x'*65537):
                file.write_text(text)
                with self.assertRaises(DataError) as error: load_policy(file)
                self.assertNotIn(folder,str(error.exception))
            data=policy();data['rules'][0]['unknown']=1;file.write_text(json.dumps(data))
            with self.assertRaises(DataError): load_policy(file)

    def test_loader_provenance_not_exposed(self):
        data=policy();data['rules'][0]['provenance']['reference']='private-operator-reference'
        bound=bind_rule(data,'XAUUSD','XAUUSDc','Exness-MT5Real50','USC')
        self.assertNotIn('private-operator-reference',json.dumps(bound))
        self.assertEqual(len(bound['provenance_sha256']),64)

    def test_committed_template_never_authorizes_any_symbol(self):
        template=Path(__file__).resolve().parents[1]/'docs/examples/exness_cent_spread_policy.unapproved.json'
        data=load_policy(template)
        for symbol in ALIASES:
            meta=metadata(symbol)
            meta['spread_policy']=bind_rule(data,symbol,ALIASES[symbol],'Exness-MT5Real50','USC')
            result=spread_status(meta,quote(),'M15',NOW)
            self.assertEqual((result['decision'],result['policy_status']),('BLOCK','UNAPPROVED'))
            self.assertIsNone(result['max_allowed_price'])

    def test_invalid_dates_and_incomplete_approval_are_rejected(self):
        for date in ('2026-01-01Z','2026-13-01T00:00:00Z','2026-01-01T00:00:00+01:00'):
            data=policy();data['rules'][0]['effective_from_utc']=date
            with self.assertRaises(DataError):validate_policy(data)
        for key,value in [('maximum',None),('effective_from_utc',None),('provenance',{'kind':'OPERATOR_CONFIGURATION','reference':''})]:
            data=policy();data['rules'][0][key]=value
            with self.assertRaises(DataError):validate_policy(data)


class BrokerTrustTests(unittest.TestCase):
    def test_each_field_is_current_not_historical(self):
        trust=metadata()['broker_contract']
        self.assertEqual(trust['status'],'CURRENT_MT5_OBSERVED')
        self.assertEqual(trust['historical_status'],'UNVERIFIED')
        self.assertTrue(all(v['trust']=='CURRENT_MT5_OBSERVED' for v in trust['fields'].values()))

    def test_missing_field_does_not_erase_other_fields(self):
        meta=metadata();meta.pop('freeze_level')
        trust=contract_observation(meta,'fixture')
        self.assertEqual(trust['missing_fields'],['freeze_level'])
        self.assertEqual(trust['fields']['contract_size']['trust'],'CURRENT_MT5_OBSERVED')
        self.assertEqual(trust['historical_status'],'UNVERIFIED')

    def test_identity_calc_mode_point_and_volume_conflicts(self):
        for key,value in [('broker_symbol','XAUUSD'),('broker_server','Other'),('account_currency','USDC'),
                          ('profit_currency','EUR'),('trade_calc_mode_name','FUTURES'),('point',.1),('volume_max',.001)]:
            meta=metadata();meta[key]=value
            with self.subTest(key=key):
                self.assertEqual(contract_observation(meta,'fixture')['status'],'CONFLICTING')

    def test_provider_exposes_observation_and_ignores_legacy_limit_in_real(self):
        class Terminal(RealTerminal):
            SYMBOL_CALC_MODE_FOREX=0
            def account_info(self):
                account=super().account_info();account.server='Exness-MT5Real50';return account
            def symbol_info(self,symbol):
                info=super().symbol_info(symbol)
                info.digits=3 if symbol in ('XAUUSDc','USDJPYc') else 5
                info.point=10**-info.digits;info.trade_tick_size=info.point
                info.trade_calc_mode=0;info.trade_freeze_level=0
                info.trade_tick_value_profit=info.trade_tick_value
                info.trade_tick_value_loss=info.trade_tick_value
                info.currency_margin=info.currency_base;info.spread=12
                return info
        provider=MT5Provider(Terminal(),ALIASES)
        provider.max_spread={'XAUUSD':999}
        provider.account_preflight('REAL_READONLY_DATA','Exness-MT5Real50','USC')
        for symbol in ALIASES:
            meta=provider.metadata(symbol)
            self.assertEqual(meta['broker_contract']['status'],'CURRENT_MT5_OBSERVED')
            self.assertIsNone(meta['max_spread'])
            self.assertTrue(meta['spread_policy_required'])


class FinancialReadinessTests(unittest.TestCase):
    def oracle(self, side,lots,entry,stop):
        # Independently specified 1 unit contract * 100 USC/USD, not tick metadata.
        return (stop-entry)*(1 if side=='BUY' else -1)*lots*100

    def test_usc_and_volume_rounding(self):
        result=size_lots(1234,1,100,99,metadata(),self.oracle,account_currency='USC')
        self.assertEqual(result['lots'],.12)
        self.assertEqual(result['estimated_risk'],12)
        self.assertEqual(result['currency'],'USC')

    def test_wrong_contract_size_and_tick_value_block(self):
        for key,value in [('contract_size',2),('tick_value_loss',2)]:
            meta=metadata();meta[key]=value
            with self.assertRaisesRegex(DataError,'disagrees'):
                size_lots(10000,1,100,99,meta,self.oracle,account_currency='USC')

    def test_wrong_currency_and_missing_oracle(self):
        for currency in ('USD','USDC'):
            with self.assertRaises(DataError): size_lots(10000,1,100,99,metadata(),self.oracle,account_currency=currency)
        meta=metadata();meta['profit_currency']='EUR'
        with self.assertRaisesRegex(DataError,'conversion'): size_lots(10000,1,100,99,meta,self.oracle,account_currency='USC')
        with self.assertRaisesRegex(DataError,'oracle'): size_lots(10000,1,100,99,metadata(),account_currency='USC')

    def test_minimum_volume_and_stop_level_veto(self):
        with self.assertRaisesRegex(DataError,'minimum lot'): size_lots(1,1,100,99,metadata(),self.oracle,account_currency='USC')
        plan={'direction':'BUY','entry':100,'stop_loss':99.99,'take_profit_1':101}
        self.assertEqual(risk_check(plan,{**metadata(),'spread':.2},.3)['decision'],'BLOCK')

    def test_jpy_conversion_requires_fresh_pair_quote(self):
        meta=metadata('USDJPY');meta.update(contract_size=1000,tick_size=.001,tick_value=.625,
                                           tick_value_loss=.625,point=.001,digits=3)
        meta['broker_contract']=contract_observation(meta,'fixture')
        meta.pop('_valuation_quote')
        oracle=lambda side,lots,entry,stop: -abs(entry-stop)*1000*lots*100/160
        with self.assertRaises(DataError): size_lots(10000,1,160,159,meta,oracle,account_currency='USC')
        meta.update(_valuation_quote={'bid':160,'ask':160.01,'time':NOW},_valuation_as_of=NOW)
        self.assertGreater(size_lots(10000,1,160,159,meta,oracle,account_currency='USC')['lots'],0)
        meta['_valuation_quote']['time']=NOW-500
        with self.assertRaisesRegex(DataError,'stale'): size_lots(10000,1,160,159,meta,oracle,account_currency='USC')


class ReadinessIntegration(unittest.TestCase):
    def provider(self):
        p=fixture();p.data['XAUUSD']['metadata']=metadata()
        return p

    def test_approved_boundary_buy_and_spread_block(self):
        p=self.provider();result=unified_analyze(p,'XAUUSD',now=NOW,balance=10000,balance_source='HYPOTHETICAL_CAPITAL')
        self.assertEqual(result.final_decision,'BUY_CANDIDATE')
        self.assertEqual(result.spread_status['decision'],'PASS')
        self.assertEqual(result.trading_eligibility,'NOT_EVALUATED')
        self.assertFalse(result.execution_permission)
        p.data['XAUUSD']['metadata']['spread_policy']['maximum']=.19
        blocked=unified_analyze(p,'XAUUSD',now=NOW,balance=10000)
        self.assertEqual(blocked.final_decision,'NO_TRADE')
        self.assertIsNone(blocked.lot_size)

    def test_missing_candles_keep_trust_and_unapproved_policy_diagnostics(self):
        p=self.provider();p.data['XAUUSD']['candles']['M15'].pop(-3)
        p.data['XAUUSD']['metadata']['spread_policy']['approval_status']='UNAPPROVED'
        result=unified_analyze(p,'XAUUSD',now=NOW)
        self.assertEqual(result.final_decision,'INSUFFICIENT_DATA')
        self.assertEqual(result.broker_contract['status'],'CURRENT_MT5_OBSERVED')
        self.assertEqual(result.spread_status['decision'],'BLOCK')

    def test_unknown_session_stays_blocked_and_other_symbol_not_global_blocked(self):
        p=self.provider();p.data['EURUSD']=copy.deepcopy(p.data['XAUUSD'])
        p.data['XAUUSD']['metadata']['broker_hours']=None
        p.data['EURUSD']['metadata']=metadata('EURUSD',maximum=.3)
        self.assertEqual(unified_analyze(p,'XAUUSD',now=NOW).final_decision,'NO_TRADE')
        self.assertEqual(unified_analyze(p,'EURUSD',now=NOW).final_decision,'BUY_CANDIDATE')

    def test_pattern_cannot_override_spread_block(self):
        p=self.provider();p.data['XAUUSD']['metadata']['spread_policy']['maximum']=.01
        bridge=V2ChartPatternBridge(Path(__file__).resolve().parents[2]/'trade-ai-v2-antigravity')
        base=unified_analyze(p,'XAUUSD',now=NOW,balance=10000)
        extended=unified_analyze(p,'XAUUSD',now=NOW,balance=10000,extension=bridge)
        self.assertEqual(base.final_decision,extended.final_decision)
        self.assertEqual(extended.final_decision,'NO_TRADE')
        self.assertIsNone(extended.entry_zone)

    def test_api_additive_trust_fields_and_no_execution(self):
        from datetime import datetime,timezone
        app.state.provider=self.provider()
        try:
            with patch('forex.unified.datetime') as clock:
                clock.now.return_value=datetime.fromtimestamp(NOW,timezone.utc)
                clock.fromtimestamp.side_effect=datetime.fromtimestamp
                response=TestClient(app).post('/api/v5/analysis',json={'symbol':'XAUUSD','balance':10000})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['schema_version'],'forex-analysis-5')
            self.assertEqual(response.json()['broker_contract']['historical_status'],'UNVERIFIED')
            self.assertFalse(response.json()['execution_permission'])
        finally: app.state.provider=None


class StartupFingerprintTests(unittest.TestCase):
    def test_loaded_code_fingerprint_does_not_read_disk(self):
        from tools.runtime_acceptance.build_fingerprint import loaded_fingerprint
        with patch.object(Path,'read_bytes',side_effect=AssertionError('disk read')):
            first=loaded_fingerprint();second=loaded_fingerprint()
        self.assertEqual(first,second)
        self.assertGreater(first['function_count'],0)

    def test_loaded_function_change_changes_startup_digest(self):
        from tools.runtime_acceptance.build_fingerprint import loaded_fingerprint
        from forex import spread_policy
        before=loaded_fingerprint()
        original=spread_policy.number.__code__
        def alternate(value): return 0
        try:
            spread_policy.number.__code__=alternate.__code__
            self.assertNotEqual(before['loaded_function_code_sha256'],loaded_fingerprint()['loaded_function_code_sha256'])
        finally: spread_policy.number.__code__=original


if __name__=='__main__': unittest.main()
