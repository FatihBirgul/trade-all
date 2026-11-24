import unittest
from dataclasses import replace
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from fixtures import fixture
from unified_forex.research import dataset_from_provider,HistoricalDataset,ResearchConfig,run_backtest,run_oos
from unified_forex.costs import at_rules
from unified_forex.experiments import ExperimentRegistry
from unified_forex.research_control import CancellationToken,ResearchCancelled
from market_ai.v2.walk_forward import WalkForwardConfig,Candidate
from unified_forex.strategies import TREND


class DatedFinancialResearch(unittest.TestCase):
    def dataset(self):return dataset_from_provider(fixture(n=270,frames=('M15',)),'XAUUSD','M15',270)
    def test_fee_change_charges_entry_and_exit_halves_independent_oracle(self):
        d=self.dataset();rows=list(d.frames['15m'])
        for i in range(250,len(rows)):rows[i]=replace(rows[i],open=2000,high=2000.5,low=1999.5,close=2000)
        rows[251]=replace(rows[251],open=2000,high=2004.5,low=1999.5,close=2004)
        cut=rows[251].open_time_ms;meta=d.metadata()
        old={**meta,'cost_assumptions':{'commission_round_trip_per_lot':4.,'commission_currency':'USD','spread_price':0.,'slippage_price':0.}}
        new={**meta,'cost_assumptions':{'commission_round_trip_per_lot':10.,'commission_currency':'USD','spread_price':0.,'slippage_price':0.}}
        epochs=[dict(effective_from_ms=rows[0].open_time_ms,effective_to_ms=cut,source='synthetic',rules=old),
                dict(effective_from_ms=cut,effective_to_ms=rows[-1].close_time_ms+1,source='synthetic',rules=new)]
        d=HistoricalDataset({'15m':rows},old,data_kind='synthetic',data_version='cost-oracle',rule_epochs=epochs)
        candidate=SimpleNamespace(final_decision='BUY_CANDIDATE',legacy_signal='BUY',entry_zone={'low':2000},stop_loss=1999,
            take_profit_1=2004,routing={'strategy_id':TREND},regime={'regime':'trend'})
        config=ResearchConfig('15m',rows[250].open_time_ms,rows[-1].close_time_ms,analysis_every_bars=20)
        with patch('unified_forex.research.AnalysisEngine.analyze',return_value=candidate):
            result=run_backtest(d,config,fee_bps=0,spread_bps=0,slippage_bps=0)
        trade=result['closed_trades'][0]
        #100oz/lot: target400/lot; fee=2(entry)+5(exit)=7/lot.
        self.assertAlmostEqual(trade['round_trip_commission_account'],7*trade['lots'])
        self.assertAlmostEqual(float(trade['net_pnl_quote']),393*trade['lots'])
        self.assertAlmostEqual(trade['r'],393/104)
    def test_stress_assumptions_currency_and_conversion_fail_closed(self):
        d=self.dataset();m=d.metadata()
        with self.assertRaises(ValueError):at_rules({**m,'cost_assumptions':{'commission_round_trip_per_lot':5.,'commission_currency':'EUR'}},2000,[0,0,0])
        with self.assertRaises(ValueError):at_rules({**m,'cost_assumptions':{'spread_price':float('inf')}},2000,[0,0,0])
        from unified_forex.engine import AnalysisEngine
        from fixtures import NOW
        for fee,slip in [(1000,0),(0,20)]:
            r=AnalysisEngine().analyze(fixture(),'XAUUSD',now=NOW,commission_per_lot=fee,slippage_price=slip,balance=10000)
            self.assertEqual(r.final_decision,'NO_TRADE');self.assertIsNone(r.lot_size)
    def test_cancellation_discards_partial_results_and_registry_race(self):
        d=self.dataset();b=d.frames['15m'];token=CancellationToken();token.cancel()
        c=ResearchConfig('15m',b[250].open_time_ms,b[-1].close_time_ms)
        with self.assertRaises(ResearchCancelled):run_backtest(d,c,cancellation=token)
        registry=ExperimentRegistry(capacity=1);result={'experiment_id':'a'*64,'status':'PASS'}
        with ThreadPoolExecutor(max_workers=4) as pool:
            a=list(pool.map(lambda _:registry.record(result),range(8)))
        self.assertEqual(len({x['result_sha256'] for x in a}),1)
        registry.record({'experiment_id':'b'*64,'status':'PASS'})
        self.assertIsNone(registry.get('a'*64))
        with self.assertRaises(ValueError):registry.record({'experiment_id':'b'*64,'status':'CHANGED'})
        self.assertEqual(len(ExperimentRegistry().items),0)
