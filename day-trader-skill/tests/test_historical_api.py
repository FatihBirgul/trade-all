"""V5 API acceptance, no MT5 connection. Fixtures explicitly synthetic."""
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from forex.api import app
from forex.contracts import capture, bind_historical
from forex.core import DataError
from forex.unified import unified_analyze
from historical_api_fixture import AS_OF, ENV, HistoricalApiProvider
from test_unified import StubExtension


class HistoricalApi(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(); self.addCleanup(self.temp.cleanup)

    def request(self,scenario,extra=None,extension=None):
        provider=HistoricalApiProvider(self.temp.name,scenario)
        def analyze(*args,**kwargs): return unified_analyze(*args,**kwargs,now=AS_OF)
        with patch.object(app.state,'provider',provider), patch.dict('os.environ',ENV), \
             patch.object(app.state,'analytical_extension',extension), \
             patch('forex.api.configured_v2_extension',create=True,return_value=None), \
             patch('forex.v2_bridge.configured_v2_extension',return_value=None), \
             patch('forex.api.unified_analyze',side_effect=analyze):
            response=TestClient(app).post('/api/v5/analysis',json={
                'symbol':'XAUUSD','timeframe':'M15','confirmations':['M15'],**(extra or {})})
        self.assertEqual(provider.calls,[])
        return response

    def blocked(self,scenario):
        response=self.request(scenario)
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body['trading_eligibility'],'BLOCKED')
        self.assertFalse(body['execution_permission'])
        for key in ('entry_zone','stop_loss','take_profit_1','take_profit_2','lot_size'):
            self.assertIsNone(body[key])
        return body

    def test_missing_historical_evidence_blocks(self):
        body=self.blocked('none')
        self.assertEqual(body['historical_session_evidence']['status'],'SOURCE_NOT_SUPPLIED')
        self.assertEqual(body['final_decision'],'INSUFFICIENT_DATA')
        self.assertEqual(body['data_status'],'DATA_UNAVAILABLE')

    def test_weekly_evidence_blocks(self):
        body=self.blocked('weekly')
        self.assertEqual(body['historical_session_evidence']['status'],'CURRENT_WEEKLY_ONLY')

    def test_wrong_symbol_blocks(self): self.blocked('wrong_symbol')
    def test_wrong_broker_blocks(self): self.blocked('wrong_broker')
    def test_unreviewed_blocks(self): self.blocked('unreviewed')
    def test_operator_declaration_blocks(self): self.blocked('operator')
    def test_partial_evidence_blocks(self): self.blocked('partial')
    def test_conflicting_evidence_blocks(self):
        self.assertEqual(self.blocked('conflicting')['historical_session_evidence']['status'],
                         'CONFLICTING_EVIDENCE')

    def test_synthetic_valid_history_is_data_ok_no_execution(self):
        response=self.request('valid'); self.assertEqual(response.status_code,200)
        body=response.json()
        self.assertEqual(body['data_status'],'OK')
        self.assertEqual(body['final_decision'],'WAIT')
        self.assertFalse(body['execution_permission'])
        self.assertTrue(body['historical_session_evidence']['historical_gap_authorized'])
        self.assertEqual(body['account_currency'],'USC')
        self.assertEqual(body['market_data_account_mode'],'REAL')

    def test_synthetic_evidence_does_not_explain_open_gap(self): self.blocked('open_gap')

    def test_spread_unapproved_still_blocks(self):
        body=self.blocked('spread_unapproved')
        self.assertEqual(body['spread_status']['decision'],'BLOCK')
        self.assertTrue(body['historical_session_evidence']['historical_gap_authorized'])
        self.assertTrue(any('spread' in s for s in body['decision_reasons']))

    def test_broker_contract_still_blocks(self):
        body=self.blocked('bad_contract')
        self.assertTrue(any('broker contract' in s for s in body['decision_reasons']))

    def test_pattern_context_cannot_bypass_missing_data(self):
        extension=StubExtension({'chart_patterns':{'mode':'DESCRIPTIVE_ONLY'},
                                 'strategy_candidates':[{'strategy':'synthetic','direction':'BUY','reason':'fixture'}]})
        plain=self.request('none').json()
        extended=self.request('none',extension=extension).json()
        for key in ('final_decision','entry_zone','stop_loss','take_profit_1','lot_size','execution_permission'):
            self.assertEqual(plain[key],extended[key])

    def test_malformed_evidence_cannot_enter_api(self):
        for key in ('historical_evidence','historical_gap_authorized','reviews'):
            response=self.request('none',{key:True})
            self.assertEqual(response.status_code,422)

    def test_snapshot_retains_audit_and_real_candles_without_filling(self):
        p=HistoricalApiProvider(self.temp.name)
        snap=capture(p,'XAUUSD','M15',AS_OF,('M15',)).payload()
        self.assertEqual(len(snap['frames']['M15']),len(p.rows))
        self.assertEqual([r['time'] for r in snap['frames']['M15']],[r['time'] for r in p.rows])
        self.assertTrue(snap['metadata']['historical_session_evidence']['historical_gap_authorized'])

    def test_legacy_non_real_declared_hours_survive_empty_evidence_store(self):
        p=HistoricalApiProvider(self.temp.name,'none')
        p.meta['broker_contract_required']=False
        p.meta['broker_hours']={'timezone':'UTC','weekly':{
            str(day):[['00:00','22:00'],['23:00','24:00']] for day in range(7)}}
        snap=capture(p,'XAUUSD','M15',AS_OF,('M15',)).payload()
        self.assertEqual(len(snap['frames']['M15']),220)
        self.assertFalse(snap['metadata']['historical_session_evidence']['historical_gap_authorized'])

    def test_metadata_cannot_change_policy_identity(self):
        p=HistoricalApiProvider(self.temp.name)
        meta=p.metadata('XAUUSD'); meta['broker_symbol']='XAUUSD'
        with self.assertRaisesRegex(DataError,'identity'):
            bind_historical(p,'XAUUSD',meta,AS_OF)

    def test_retrospective_capability_cannot_enter_live_snapshot(self):
        p=HistoricalApiProvider(self.temp.name)
        retro=p.store.evaluate(broker='Exness',server='Exness-MT5Real50',product='Standard Cent',
                              currency='USC',broker_symbol='XAUUSDc',canonical_symbol='XAUUSD',
                              as_of=AS_OF,knowledge_as_of=AS_OF,retrospective=True)
        with patch.object(p,'historical_session_policy',return_value=retro), self.assertRaisesRegex(DataError,'as-of'):
            capture(p,'XAUUSD','M15',AS_OF,('M15',))


if __name__=='__main__': unittest.main()
