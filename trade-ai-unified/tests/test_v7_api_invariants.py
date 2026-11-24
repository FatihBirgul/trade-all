import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from fixtures import fixture,NOW,META
from unified_forex.api import app,_research_gate
from unified_forex.engine import AnalysisEngine
from forex.core import size_lots,reward_risk_after_costs,DataError


class ReleaseInvariants(unittest.TestCase):
    def test_multicurrency_lot_and_cost_oracles_on_broker_grid(self):
        # Values are explicit synthetic account-currency tick conversions, not
        # assertions that every broker's EUR/JPY conversion is constant.
        examples=[('XAUUSD',2000,.01,1),('EURUSD',1.1,.00001,1),('GBPUSD',1.3,.00001,1),('USDJPY',150,.001,.67)]
        for currency in ('USD','EUR','JPY'):
            for symbol,entry,tick,tick_value in examples:
                for side in ('BUY','SELL'):
                    sign=1 if side=='BUY' else -1
                    m={**META,'symbol':symbol,'account_currency':currency,'tick_value_currency':currency,
                       'tick_size':tick,'tick_value':tick_value}
                    stop=entry-sign*100*tick;target=entry+sign*200*tick
                    result=size_lots(10000,1,entry,stop,m,side=side,commission_per_lot=5,slippage_price=10*tick)
                    per_lot=110*tick_value+5
                    self.assertAlmostEqual(result['unrounded_risk'],result['lots']*per_lot,places=7)
                    self.assertLessEqual(result['unrounded_risk'],100+1e-8)
                    self.assertAlmostEqual((result['lots']-.01)/.01,round((result['lots']-.01)/.01),places=7)
                    r=reward_risk_after_costs(dict(direction=side,entry=entry,stop_loss=stop,take_profit_1=target),m,5,10*tick)
                    self.assertAlmostEqual(r['net_reward_risk'],(200*tick_value-5)/per_lot,places=7)

    def test_full_buy_sell_grid_and_veto_null_invariants(self):
        for side in ('BUY','SELL'):
            r=AnalysisEngine().analyze(fixture(side),'XAUUSD',now=NOW,balance=10000,commission_per_lot=5,slippage_price=.01)
            self.assertEqual(r.final_decision,side+'_CANDIDATE')
            sign=1 if side=='BUY' else -1;entry=r.entry_zone['low']
            self.assertGreater((entry-r.stop_loss)*sign,0);self.assertGreater((r.take_profit_1-entry)*sign,0)
            self.assertLessEqual(r.risk_amount,100);self.assertGreaterEqual(r.net_risk_reward,1.5)
            for value in (r.stop_loss,r.take_profit_1,r.take_profit_2):self.assertAlmostEqual(value/.01,round(value/.01),places=6)
        p=fixture();p.data['XAUUSD']['metadata']['tick_value_loss']=0
        r=AnalysisEngine().analyze(p,'XAUUSD',now=NOW,balance=10000)
        self.assertEqual(r.final_decision,'NO_TRADE');self.assertEqual(r.candidate_direction,'WAIT')
        self.assertTrue(all(getattr(r,k) is None for k in ('entry_zone','stop_loss','take_profit_1','lot_size','risk_amount')))

    def test_api_strict_contract_budget_and_legacy_validation(self):
        app.state.provider=fixture()
        try:
            with patch('unified_forex.engine.datetime') as clock:
                clock.now.return_value=datetime.fromtimestamp(NOW,timezone.utc);clock.fromtimestamp.side_effect=datetime.fromtimestamp
                client=TestClient(app)
                self.assertEqual(client.post('/api/v6/analysis',json={'symbol':'XAUUSD','risk_pct':'1'}).status_code,422)
                self.assertEqual(client.get('/api/v1/analysis/XAUUSD?confirmations=BAD').status_code,422)
                _research_gate.acquire()
                try:self.assertEqual(client.post('/api/v6/backtests',json={'symbol':'XAUUSD'}).status_code,429)
                finally:_research_gate.release()
                schema=client.get('/openapi.json').json()
                self.assertIn('/api/v6/research/experiments/{experiment_id}',schema['paths'])
                self.assertEqual(client.get('/api/v6/research/experiments/../../secret').status_code,404)
                self.assertEqual(client.get('/api/v6/research/experiments/'+'a'*64).status_code,404)
                self.assertFalse(client.get('/api/v6/sessions/XAUUSD').json()['broker']['provenance']['authenticated'])
        finally:app.state.provider=None
