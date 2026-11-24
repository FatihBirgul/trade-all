import unittest
from dataclasses import replace
from fixtures import fixture
from unified_forex.research import dataset_from_provider,HistoricalDataset,run_oos
from unified_forex.provenance import describe,DatasetDeclaration
from unified_forex.experiments import ExperimentRegistry
from market_ai.v2.walk_forward import WalkForwardConfig,Candidate,prefix
from unified_forex.strategies import TREND


class HistoricalTrust(unittest.TestCase):
    def dataset(self):return dataset_from_provider(fixture(n=420,frames=('M15',)),'XAUUSD','M15',420)
    def test_manifest_identity_and_untrusted_declarations(self):
        d=self.dataset();m=describe(d)
        self.assertEqual(m['trust'],'SYNTHETIC_TEST');self.assertFalse(m['source_authenticated'])
        self.assertEqual(m['frames']['15m']['candle_count'],420)
        with self.assertRaises(ValueError):DatasetDeclaration.model_validate({**d.declaration,'trust':'SOURCE_VERIFIED'})
        rows=list(d.frames['15m']);rows[-1]=replace(rows[-1],close=rows[-1].close-.01)
        other=HistoricalDataset({'15m':rows},d.metadata(),data_kind='historical',data_version='test',declaration=d.declaration)
        self.assertNotEqual(d.digest,other.digest);self.assertEqual(describe(other)['trust'],'DECLARED_HISTORICAL')

    def test_point_in_time_rules_and_future_rules_do_not_change_training(self):
        d=self.dataset();b=d.frames['15m'];cut=b[330].open_time_ms
        epochs=[dict(effective_from_ms=b[0].open_time_ms,effective_to_ms=cut,source='declared-archive',rules=d.metadata()),
                dict(effective_from_ms=cut,effective_to_ms=b[-1].close_time_ms+1,source='declared-archive',rules={**d.metadata(),'tick_value':2})]
        a=HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='epoch-test',rule_epochs=epochs)
        self.assertEqual(a.metadata(cut-1)['tick_value'],1);self.assertEqual(a.metadata(cut)['tick_value'],2)
        with self.assertRaises(ValueError):a.metadata(b[0].open_time_ms-1)
        epochs[1]['rules']['tick_value']=3
        other=HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='epoch-test',rule_epochs=epochs)
        self.assertEqual(prefix(a,cut).digest,prefix(other,cut).digest)
        epochs[1]['effective_from_ms']=cut-1
        with self.assertRaises(ValueError):HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='bad',rule_epochs=epochs)

    def test_actual_validation_selection_freeze_and_registry(self):
        d=self.dataset();registry=ExperimentRegistry(capacity=1)
        c=WalkForwardConfig(train_bars=330,test_bars=40,warmup_bars=250,validation_bars=20,
            max_folds=1,simulate_orders=True,timeframe='15m',candidates=(Candidate('trend',(TREND,),10),),fee_bps='0',spread_bps='0',slippage_bps='0')
        a=run_oos(d,c,registry=registry);f=a['folds'][0]
        self.assertEqual(f['status'],'OOS_EVALUATED')
        self.assertIn('validation',f['training'][0]);self.assertTrue(f['frozen_parameters']['validation_input_digest'])
        self.assertLess(f['training_cutoff_ms'],f['training'][0]['validation']['start_ms'])
        self.assertFalse(a['registry']['independent_evidence'])
        from forex.contracts import canonical
        self.assertEqual(canonical(registry.get(a['experiment_id'])['folds']),canonical(a['folds']))
        b=list(d.frames['15m']);start=f['indices']['test_start']
        for i in range(start,len(b)):b[i]=replace(b[i],open=b[i].open+3,high=b[i].high+3,low=b[i].low+3,close=b[i].close+3)
        other=HistoricalDataset({'15m':b},d.metadata(),data_kind=d.data_kind,data_version=d.data_version,declaration=d.declaration)
        result=run_oos(other,c)
        self.assertEqual(f['frozen_parameters_hash'],result['folds'][0]['frozen_parameters_hash'])
        with self.assertRaises(ValueError):registry.record({**registry.get(a['experiment_id']),'integrity_status':'CORRUPT'})

    def test_monte_carlo_seed_and_small_sample_warning(self):
        from forex.research import _bootstrap
        trades=[{'r':r} for r in (1,-1,2,-2,1)]
        a=_bootstrap(trades,42)
        self.assertEqual(a,_bootstrap(trades,42));self.assertIn('small',a['warning'])
        self.assertLessEqual(a['p5_total_r'],a['p95_total_r'])

    def test_intrabar_contract_change_and_early_retrieval_fail_closed(self):
        from unified_forex.research import ResearchConfig,run_backtest
        d=self.dataset();b=d.frames['15m'];cut=b[250].open_time_ms+1
        epochs=[dict(effective_from_ms=b[0].open_time_ms,effective_to_ms=cut,source='declared',rules=d.metadata()),
                dict(effective_from_ms=cut,effective_to_ms=b[-1].close_time_ms+1,source='declared',rules=d.metadata())]
        other=HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='boundary',rule_epochs=epochs)
        c=ResearchConfig('15m',b[250].open_time_ms,b[-1].close_time_ms)
        with self.assertRaisesRegex(ValueError,'inside execution candle'):run_backtest(other,c)
        with self.assertRaisesRegex(ValueError,'retrieval precedes'):
            HistoricalDataset(dict(d.frames),d.metadata(),data_kind='synthetic',data_version='early',
                              declaration={**d.declaration,'retrieved_at':'2000-01-01T00:00:00+00:00'})
