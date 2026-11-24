import json,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from datetime import datetime,timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from unified_forex.api import app
from unified_forex.engine import AnalysisReport
from unified_forex.schemas import RiskPolicy
from fixtures import fixture,NOW


class V8ContractCompatibility(unittest.TestCase):
    def test_v7_examples_and_all_routes_remain_compatible(self):
        root=Path(__file__).resolve().parents[1]
        saved=json.loads((root/'docs/V7_RESPONSE_EXAMPLES.json').read_text())
        for body in saved['examples'].values():AnalysisReport.model_validate(body)
        schema=app.openapi();old=json.loads((root/'docs/V7_OPENAPI.json').read_text())
        self.assertTrue(set(old['paths'])<=set(schema['paths']))
        self.assertIn('RiskPolicy',schema['components']['schemas'])
        policy=dict(saved['examples']['BUY']['risk_policy']);policy['sizing']={**policy['sizing'],'lots':-1}
        with self.assertRaises(ValueError):RiskPolicy.model_validate(policy)
    def test_cooperative_api_cancellation_id_and_failure_cleanup(self):
        app.state.provider=fixture(n=270,frames=('M15',));started=Event();release=Event()
        def work(*args,**kwargs):
            started.set();release.wait(5);kwargs['cancellation'].check()
            raise AssertionError('Cancellation should abort')
        try:
            client=TestClient(app)
            with patch('unified_forex.research.run_backtest',side_effect=work),ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(client.post,'/api/v6/backtests',json={'symbol':'XAUUSD','count':270})
                self.assertTrue(started.wait(5))
                run_id=client.get('/api/v6/research/status').json()['active_run_id'];self.assertEqual(len(run_id),32)
                self.assertEqual(client.post('/api/v6/research/cancel',json={'run_id':'0'*32}).status_code,409)
                self.assertEqual(client.post('/api/v6/research/cancel',json={'run_id':run_id}).status_code,200)
                release.set();result=future.result(timeout=5)
                self.assertEqual(result.status_code,422);self.assertIn('cancelled',result.json()['detail'])
            self.assertIsNone(client.get('/api/v6/research/status').json()['active_run_id'])
            self.assertEqual(client.post('/api/v6/research/cancel',json={'run_id':run_id}).status_code,409)
            self.assertIsNone(app.state.research_cancellation)
        finally:release.set();app.state.provider=None
    def test_concurrent_analysis_symbols_and_error_contract(self):
        from fixtures import multi_fixture
        app.state.provider=multi_fixture();client=TestClient(app)
        try:
            with patch('unified_forex.engine.datetime') as clock:
                clock.now.return_value=datetime.fromtimestamp(NOW,timezone.utc);clock.fromtimestamp.side_effect=datetime.fromtimestamp
                symbols=['XAUUSD','EURUSD','GBPUSD','USDJPY']
                with ThreadPoolExecutor(max_workers=4) as pool:
                    responses=list(pool.map(lambda s:client.post('/api/v6/analysis',json={'symbol':s}),symbols))
                for symbol,response in zip(symbols,responses):
                    self.assertEqual(response.status_code,200);self.assertEqual(response.json()['symbol'],symbol)
                    AnalysisReport.model_validate(response.json())
                bad=client.post('/api/v6/analysis',json={'symbol':'XAUUSD','execute':True})
                self.assertEqual(bad.status_code,422);self.assertIn('detail',bad.json())
        finally:app.state.provider=None
