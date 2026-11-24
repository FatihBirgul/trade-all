import unittest
from dataclasses import replace
from unittest.mock import patch
from fixtures import fixture,NOW
from unified_forex.research import dataset_from_provider,ResearchConfig,run_backtest,run_oos,HistoricalDataset
from market_ai.v2.walk_forward import WalkForwardConfig,Candidate
from unified_forex.strategies import TREND


class HistoricalIntegration(unittest.TestCase):
    def dataset(self,n=420):return dataset_from_provider(fixture(n=n,frames=('M15',)),'XAUUSD','M15',n)
    def test_actual_canonical_strategy_multitrade_and_prefix(self):
        d=self.dataset();bars=d.frames['15m']
        c=ResearchConfig('15m',bars[250].open_time_ms,bars[-1].close_time_ms,analysis_every_bars=10)
        a=run_backtest(d,c,fee_bps='0',spread_bps='0',slippage_bps='0')
        self.assertGreater(len(a['closed_trades']),1)
        self.assertTrue(all(t['known_at']<=t['entry_time']<=t['exit_time'] for t in a['closed_trades']))
        self.assertEqual(a['orders'],0)
        self.assertEqual(a,run_backtest(d,c,fee_bps='0',spread_bps='0',slippage_bps='0'))

    def test_original_v2_train_select_freeze_test_runs_without_ledger(self):
        d=self.dataset()
        c=WalkForwardConfig(train_bars=330,test_bars=40,warmup_bars=250,purge_bars=2,label_horizon_bars=2,
                            max_folds=2,simulate_orders=True,timeframe='15m',fee_bps='0',spread_bps='0',slippage_bps='0',
                            candidates=(Candidate('trend-only',(TREND,),5),Candidate('trend-slower',(TREND,),10)))
        a=run_oos(d,c)
        self.assertEqual(a['validation_status'],'OOS_EVALUATED',a['folds'])
        self.assertEqual(len(a['folds']),2)
        self.assertTrue(all(len(f['training'])==2 for f in a['folds']))
        self.assertTrue(all(f['frozen_parameters_hash'] for f in a['folds']))
        self.assertFalse(a['continuous_equity_available'])
        self.assertFalse(a['forward_validated'])
        self.assertEqual(a,run_oos(d,c))
        cutoff=a['folds'][0]['indices']['test_start']
        altered=list(d.frames['15m'])
        for i in range(cutoff,len(altered)):
            b=altered[i];altered[i]=replace(b,open=b.open+10,high=b.high+10,low=b.low+10,close=b.close+10)
        other=HistoricalDataset({'15m':altered},d.metadata(),data_kind=d.data_kind,data_version=d.data_version)
        b=run_oos(other,c)
        self.assertEqual(a['folds'][0]['frozen_parameters_hash'],b['folds'][0]['frozen_parameters_hash'])

    def test_history_bounds_and_unfinished_rejected(self):
        d=self.dataset();rows=list(d.frames['15m']);rows[-1]=replace(rows[-1],is_final=False)
        with self.assertRaises(ValueError):HistoricalDataset({'15m':rows},d.metadata(),data_kind='synthetic',data_version='test')
        with self.assertRaises(ValueError):dataset_from_provider(fixture(),'XAUUSD','M15',2001)

    def test_dataset_nested_metadata_cannot_mutate_frozen_experiment(self):
        d=self.dataset();before=d.digest
        changed=d.rules['broker_hours'];changed['weekly'].clear()
        self.assertTrue(d.metadata()['broker_hours']['weekly'])
        self.assertEqual(d.digest,before)

    def test_gap_loss_is_not_clamped_to_zero_equity(self):
        d=self.dataset();rows=list(d.frames['15m'])
        rows[251]=replace(rows[251],open=1000,high=1001,low=999,close=1000)
        d=HistoricalDataset({'15m':rows},d.metadata(),data_kind=d.data_kind,data_version=d.data_version)
        config=ResearchConfig('15m',rows[250].open_time_ms,rows[-1].close_time_ms,analysis_every_bars=5)
        result=run_backtest(d,config,fee_bps='0',spread_bps='0',slippage_bps='0')
        self.assertLess(float(result['equity_curve'][-1]['equity_quote']),0)
        self.assertGreater(float(result['metrics']['maximum_drawdown_fraction']),1)
        self.assertLess(result['closed_trades'][0]['r'],-1)

    def test_retained_fold_planner_keeps_declared_purge_and_embargo(self):
        from market_ai.v2.walk_forward import plan_folds
        c=WalkForwardConfig(train_bars=330,test_bars=40,warmup_bars=250,purge_bars=2,label_horizon_bars=2,
                            embargo_bars=3,mode='rolling',max_folds=2,simulate_orders=True,timeframe='15m')
        folds=plan_folds(500,c)
        self.assertEqual(folds[0]['test_start']-folds[0]['train_end'],2)
        self.assertEqual(folds[1]['test_start']-folds[0]['test_end'],3)
        self.assertEqual(folds[1]['train_end']-folds[1]['train_start'],330)
