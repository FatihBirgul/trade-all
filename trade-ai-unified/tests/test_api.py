import unittest
from unittest.mock import patch
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from fixtures import fixture,NOW
from unified_forex.api import app


class APIContract(unittest.TestCase):
    def setUp(self):
        app.state.provider=fixture();self.client=TestClient(app)
        self.clock=patch('unified_forex.engine.datetime');clock=self.clock.start()
        clock.now.return_value=datetime.fromtimestamp(NOW,timezone.utc);clock.fromtimestamp.side_effect=datetime.fromtimestamp
    def tearDown(self):self.clock.stop();app.state.provider=None
    def test_v6_v5_v1_all_use_canonical_decision(self):
        data={'symbol':'XAUUSD','balance':10000}
        r=self.client.post('/api/v6/analysis',json=data)
        self.assertEqual(r.status_code,200,r.text);body=r.json()
        self.assertEqual(body['final_decision'],'BUY_CANDIDATE')
        old=self.client.post('/api/v5/analysis',json=data)
        self.assertEqual(old.status_code,200,old.text)
        self.assertEqual(old.json()['final_decision'],body['final_decision'])
        self.assertEqual(self.client.get('/api/v1/analysis/XAUUSD').json()['signal'],'BUY')
        paths=self.client.get('/openapi.json').json()['paths']
        self.assertIn('/api/v6/research/oos',paths)
        self.assertIn('/api/v1/walk-forward',paths)
        self.assertEqual(self.client.post('/api/v6/analysis',json={**data,'execute':True}).status_code,422)
    def test_component_routes_and_unavailable_news(self):
        for route in ('indicators','structure','patterns','confluence','alerts'):
            response=self.client.post('/api/v6/'+route,json={'symbol':'XAUUSD'})
            self.assertEqual(response.status_code,200,(route,response.text))
        self.assertEqual(self.client.get('/api/v6/calendar').json()['data_status'],'DATA_UNAVAILABLE')
        self.assertEqual(self.client.post('/api/v6/backtests',json={'symbol':'XAUUSD','count':2001}).status_code,422)
        app.state.provider.data['XAUUSD']['quote']['time']=NOW-500
        stale=self.client.get('/api/v1/analysis/XAUUSD')
        self.assertEqual(stale.status_code,503)
        self.assertEqual(stale.json()['signal'],'WAIT')

    def test_research_and_legacy_scanner_contract(self):
        app.state.provider=fixture(n=420,frames=('M15','H4'))
        response=self.client.post('/api/v6/backtests',json={'symbol':'XAUUSD','count':420,'cadence':10,'fee_bps':0,'spread_bps':0,'slippage_bps':0})
        self.assertEqual(response.status_code,200,response.text)
        self.assertGreater(len(response.json()['closed_trades']),1)
        response=self.client.get('/api/v1/scanner')
        self.assertEqual(response.status_code,200,response.text)
        self.assertIn('signal',response.json()['results'][0])
        response=self.client.post('/api/v6/research/oos',json={'symbol':'XAUUSD','count':420,'cadence':10,'fee_bps':0,'spread_bps':0,'slippage_bps':0,'train_bars':330,'test_bars':40})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['validation_status'],'OOS_EVALUATED')

    def test_local_server_shutdown_closes_owned_provider(self):
        from unittest.mock import Mock
        p=fixture();p.close=Mock();app.state.provider=p
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/v6/health').status_code,200)
        p.close.assert_called_once();self.assertIsNone(app.state.provider)
