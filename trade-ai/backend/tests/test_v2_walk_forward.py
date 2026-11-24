"""Frozen training choices, real execution and held-out isolation."""
from dataclasses import replace
from decimal import localcontext, ROUND_DOWN
from unittest import TestCase
from unittest.mock import patch
from tests.test_v2_research import dataset, RULES, TF
from market_ai.v2.research import HistoricalDataset
from market_ai.v2.walk_forward import Candidate, WalkForwardConfig, plan_folds, run_walk_forward


def data():
    d=dataset();b=list(d.frames['1m']);last=b[-1]
    for i in range(8):
        b.append(replace(last,open_time_ms=last.close_time_ms+i*TF,close_time_ms=last.close_time_ms+(i+1)*TF,open=110,high=111,low=109,close=110))
    return HistoricalDataset({'1m':b},RULES,data_kind='synthetic',data_version='walk-fixture-1')

def cfg(**kw):
    return WalkForwardConfig(**{'train_bars':303,'test_bars':3,'purge_bars':1,'label_horizon_bars':1,'embargo_bars':1,
        'max_folds':1,'simulate_orders':True,'candidates':(Candidate('ten',analysis_every_bars=10),),**kw})

class WalkForwardTests(TestCase):
    def test_expanding_rolling_purge_embargo_and_strict_configuration(self):
        for mode in ('expanding','rolling'):
            folds=plan_folds(1000,cfg(mode=mode,max_folds=3))
            self.assertEqual(folds[0],{'train_start':0,'train_end':303,'test_start':304,'test_end':307})
            self.assertEqual(folds[1]['test_start'],308)
            self.assertEqual(folds[1]['train_start'],0 if mode=='expanding' else 4)
        for kw in ({'purge_bars':0},{'label_horizon_bars':True},{'mode':'random'},{'simulate_orders':False},{'max_folds':99}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):cfg(**kw)
    def test_actual_audited_train_selection_then_oos_execution(self):
        r=run_walk_forward(data(),cfg())
        self.assertEqual(r['validation_status'],'OOS_EVALUATED',r)
        self.assertEqual(r['integrity_status'],'PASS',r)
        self.assertEqual(r['data_kind'],'synthetic');self.assertFalse(r['forward_validated'])
        self.assertEqual(r['evidence_status'],'INSUFFICIENT_EVIDENCE')
        f=r['folds'][0];self.assertEqual(f['selected_candidate'],'ten')
        self.assertGreater(f['training'][0]['scored_trades'],0)
        self.assertEqual(f['test']['events'],3);self.assertEqual(f['test']['audit']['status'],'PASS')
        self.assertTrue(f['frozen_parameters_hash'])
        self.assertEqual(run_walk_forward(data(),cfg()),r)
    def test_changed_held_out_prices_cannot_change_first_training_selection(self):
        d=data();b=list(d.frames['1m'])
        for i in range(304,len(b)):b[i]=replace(b[i],open=210,high=211,low=209,close=210)
        changed=HistoricalDataset({'1m':b},RULES,data_kind='synthetic',data_version='walk-fixture-1')
        a=run_walk_forward(d,cfg());z=run_walk_forward(changed,cfg())
        self.assertEqual(a['folds'][0]['training'],z['folds'][0]['training'])
        self.assertEqual(a['folds'][0]['frozen_parameters_hash'],z['folds'][0]['frozen_parameters_hash'])
        self.assertNotEqual(a['experiment_id'],z['experiment_id'])
    def test_training_runner_never_receives_test_rows_and_test_uses_frozen_choice(self):
        from market_ai.v2.walk_forward import run_backtest
        calls=[]
        def spy(d,c,**costs):
            calls.append((max(b.close_time_ms for b in d.frames['1m']),c,costs))
            return run_backtest(d,c,**costs)
        with patch('market_ai.v2.walk_forward.run_backtest',side_effect=spy):r=run_walk_forward(data(),cfg())
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0][0],data().frames['1m'][302].close_time_ms)
        self.assertEqual(calls[1][0],data().frames['1m'][306].close_time_ms)
        self.assertEqual(calls[0][1].analysis_every_bars,calls[1][1].analysis_every_bars)
        self.assertEqual(calls[0][2],calls[1][2])
    def test_no_training_sample_means_no_oos_claim(self):
        r=run_walk_forward(data(),cfg(minimum_training_trades=999))
        self.assertEqual(r['validation_status'],'DETECTION_IMPLEMENTED')
        self.assertEqual(r['folds'][0]['status'],'INSUFFICIENT_EVIDENCE');self.assertIsNone(r['folds'][0]['test'])
    def test_failed_test_audit_cannot_produce_successful_oos_status(self):
        from market_ai.v2.walk_forward import run_backtest
        calls=[]
        def fail_test(d,c,**kw):
            r=run_backtest(d,c,**kw)
            if calls:r['integrity_status']='MISMATCH'
            calls.append(1);return r
        with patch('market_ai.v2.walk_forward.run_backtest',side_effect=fail_test):r=run_walk_forward(data(),cfg())
        self.assertEqual(r['integrity_status'],'MISMATCH');self.assertNotEqual(r['validation_status'],'OOS_EVALUATED')
    def test_parameter_whitelist_duplicate_ids_and_budgets(self):
        for kw in ({'analysis_every_bars':True},{'strategy_ids':('fake',)},{'candidate_id':'bad id'}):
            with self.assertRaises(ValueError):Candidate(**kw)
        with self.assertRaises(ValueError):cfg(candidates=(Candidate('same'),Candidate('same')))
        with self.assertRaises(ValueError):run_walk_forward(data(),cfg(max_total_events=1))
    def test_decimal_context_does_not_affect_selection_or_experiment(self):
        r=run_walk_forward(data(),cfg())
        with localcontext() as c:
            c.prec=5;c.rounding=ROUND_DOWN;self.assertEqual(run_walk_forward(data(),cfg()),r)

    def test_rolling_training_is_cropped_and_ties_are_stable(self):
        from market_ai.v2.walk_forward import run_backtest
        starts=[]
        def spy(d,c,**costs):
            starts.append(d.frames['1m'][0].open_time_ms);return run_backtest(d,c,**costs)
        with patch('market_ai.v2.walk_forward.run_backtest',side_effect=spy):
            run_walk_forward(data(),cfg(mode='rolling',max_folds=2,minimum_training_trades=999))
        self.assertEqual(starts,[data().frames['1m'][0].open_time_ms,data().frames['1m'][4].open_time_ms])
        a=run_walk_forward(data(),cfg(candidates=(Candidate('b'),Candidate('a'))))
        self.assertEqual(a['folds'][0]['selected_candidate'],'a')
        self.assertIn('range_mean_reversion_v2',a['folds'][0]['training'][0]['breakdowns']['strategy_id'])

    def test_equivalent_candidate_order_and_cost_spellings_share_experiment_id(self):
        candidates=(Candidate('b'),Candidate('a'))
        a=run_walk_forward(data(),cfg(candidates=candidates,minimum_training_trades=999))
        b=run_walk_forward(data(),cfg(candidates=tuple(reversed(candidates)),fee_bps='5.00',spread_bps='2.0',minimum_training_trades=999))
        self.assertEqual(a['experiment_id'],b['experiment_id'])
        self.assertIn('analysis',a['engine_versions'])

    def test_zero_cost_canonicalization_normalizes_negative_zero(self):
        self.assertEqual(cfg(fee_bps='-0.000').fee_bps,'0')

    def test_cli_executes_real_frozen_fold_with_explicit_embargo_argument(self):
        from contextlib import redirect_stdout
        from io import StringIO
        import json
        from scripts.walk_forward_v2 import main
        output=StringIO()
        with patch('scripts.walk_forward_v2.load_dataset',return_value=data()),redirect_stdout(output):
            code=main(['explicit-synthetic.json','--train-bars','303','--test-bars','3','--horizon','1','--purge','1','--embargo','2','--max-folds','1','--paper'])
        r=json.loads(output.getvalue());self.assertEqual(code,0);self.assertEqual(r['configuration']['embargo_bars'],2)
        self.assertEqual(r['validation_status'],'OOS_EVALUATED');self.assertEqual(r['data_kind'],'synthetic')
