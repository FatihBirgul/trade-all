"""Historical causal boundaries, execution reuse and independently checked metrics."""
from dataclasses import replace
from decimal import Decimal as D, localcontext, ROUND_DOWN
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from market_ai.v2.research import (HistoricalDataset, HistoricalProvider, ResearchConfig,
    run_backtest, summarize, walk_forward_splits, load_dataset)
from market_ai.v2.spot_provider import FixtureSpotProvider
from scripts.v2_scenario_fixtures import fixture
TF=60000
NOW=1800000000000
RULES=FixtureSpotProvider().rules('BTCUSDT')

def dataset(kind='range'):
    history=fixture(kind,'1m',NOW)
    # Explicit synthetic future, after decision; neither target nor stop on entry bar.
    prices=[(92,92.3,91.7,92),(93,96,92.8,95),(100,111,99.5,110)]
    future=[replace(history[-1],open_time_ms=NOW+i*TF,close_time_ms=NOW+(i+1)*TF,open=o,high=h,low=l,close=c,volume=100000) for i,(o,h,l,c) in enumerate(prices)]
    return HistoricalDataset({'1m':history+future},RULES,data_kind='synthetic',data_version='test-fixture-1')

def config(**kwargs):return ResearchConfig(**{'timeframe':'1m','start_ms':NOW,'end_ms':NOW+3*TF,'analysis_every_bars':10,**kwargs})

class ResearchTests(TestCase):
    def test_historical_provider_only_exposes_closed_prefix_and_no_fallback(self):
        d=dataset();p=HistoricalProvider(d)
        self.assertEqual(len(p.candles('BTCUSDT','1m',NOW)),300)
        self.assertEqual(p.candles('BTCUSDT','1m',NOW)[-1].close_time_ms,NOW)
        self.assertNotEqual(p.candles('BTCUSDT','1m',NOW+TF)[-1],p.candles('BTCUSDT','1m',NOW)[-1])
        from market_ai.v2.spot_provider import ProviderUnavailable
        with self.assertRaises(ProviderUnavailable):p.candles('BTCUSDT','4H',NOW)
    def test_exact_metrics_with_costs_drawdown_and_ambiguous_exclusion(self):
        curve=[{'equity_quote':x} for x in ('10000','11000','8800','9900')]
        closed=[{'net_pnl_quote':'100','ambiguous':False},{'net_pnl_quote':'-40','ambiguous':False},{'net_pnl_quote':'900','ambiguous':True}]
        r=summarize(curve,closed,seed=7)
        self.assertEqual(D(r['maximum_drawdown_fraction']),D('.2'))
        self.assertEqual(D(r['expectancy_quote']),D('30'))
        self.assertEqual(D(r['profit_factor']),D('2.5'))
        self.assertEqual(r['scored_trades'],2);self.assertEqual(r['ambiguous_trades'],1)
        self.assertEqual(r['evidence_status'],'INSUFFICIENT_EVIDENCE');self.assertIsNone(r['mean_pnl_interval'])
    def test_paper_execution_domain_audit_and_no_end_forced_liquidation(self):
        r=run_backtest(dataset(),config(simulate_orders=True))
        self.assertEqual(r['audit']['status'],'PASS',r['audit'])
        self.assertEqual(r['events'],3);self.assertGreater(r['journal_records'],0,r)
        self.assertGreater(D(r['fees_quote']),D('0'));self.assertEqual(r['data_kind'],'synthetic')
        self.assertEqual(r['validation_status'],'DETECTION_IMPLEMENTED')
        self.assertEqual(r['evidence_status'],'INSUFFICIENT_EVIDENCE')
        self.assertTrue(r['domain_events']>0);self.assertFalse(r['real_execution'])
        self.assertEqual(r,run_backtest(dataset(),config(simulate_orders=True)))
    def test_detection_only_does_not_create_any_order(self):
        r=run_backtest(dataset(),config())
        self.assertEqual(r['orders'],0);self.assertEqual(r['journal_records'],0)
        self.assertEqual(r['audit']['status'],'PASS',r['audit']);self.assertTrue(r['analyses'])
    def test_partial_entry_at_window_end_remains_open_and_unscored(self):
        d=dataset();b=list(d.frames['1m']);b[300]=replace(b[300],volume=200)
        d=HistoricalDataset({'1m':b},RULES,data_kind='synthetic',data_version='partial-fixture')
        r=run_backtest(d,config(simulate_orders=True,end_ms=NOW+TF))
        self.assertEqual(r['integrity_status'],'PASS',r['audit'])
        self.assertEqual(r['open_positions'],1);self.assertEqual(r['pending_orders'],1)
        self.assertEqual(r['metrics']['scored_trades'],0);self.assertEqual(r['journal_records'],1)
        self.assertEqual(r['closed_trades'],[])
    def test_ambiguous_entry_is_not_scored_as_a_profitable_outcome(self):
        d=dataset();b=list(d.frames['1m']);b[300]=replace(b[300],high=120,low=80)
        d=HistoricalDataset({'1m':b},RULES,data_kind='synthetic',data_version='ambiguous-fixture')
        r=run_backtest(d,config(simulate_orders=True,end_ms=NOW+TF))
        self.assertEqual(r['integrity_status'],'PASS',r['audit'])
        self.assertEqual(r['ambiguous_positions'],1);self.assertEqual(r['metrics']['scored_trades'],0)
    def test_seeded_bounded_multi_decision_replay_audits_every_checkpoint(self):
        from random import Random
        rng=Random(12);history=fixture('range','1m',NOW);last=D('92');future=[]
        for i in range(120):
            close=last+D(rng.randrange(-20,21))/100
            future.append(replace(history[-1],open_time_ms=NOW+i*TF,close_time_ms=NOW+(i+1)*TF,
                open=str(last),high=str(max(last,close)+D('.2')),low=str(min(last,close)-D('.2')),close=str(close),volume=100000))
            last=close
        d=HistoricalDataset({'1m':history+future},RULES,data_kind='synthetic',data_version='bounded-seed12')
        r=run_backtest(d,config(simulate_orders=True,end_ms=NOW+120*TF,analysis_every_bars=20,audit_every_bars=30))
        self.assertEqual(r['events'],120);self.assertEqual(len(r['analyses']),6)
        self.assertTrue(all(c['status']=='PASS' for c in r['checkpoints']),r['checkpoints'])
        self.assertGreater(r['domain_events'],120);self.assertEqual(r['evidence_status'],'INSUFFICIENT_EVIDENCE')
        with self.assertRaises(ValueError):run_backtest(d,config(end_ms=NOW+120*TF,audit_every_bars=1))
    def test_dataset_stream_is_bounded_before_hashing_or_sqlite(self):
        consumed=[];bar=dataset().frames['1m'][0]
        def source():
            for i in range(50000):consumed.append(i);yield bar
        with self.assertRaises(ValueError):HistoricalDataset({'1m':source()},RULES,data_kind='synthetic',data_version='budget')
        self.assertEqual(len(consumed),30001)
    def test_dataset_freezes_provenance_and_does_not_alias_input_containers(self):
        from dataclasses import FrozenInstanceError
        d=dataset();rows=list(d.frames['1m']);rules=dict(RULES)
        frozen=HistoricalDataset({'1m':rows},rules,data_kind='synthetic',data_version='frozen')
        digest=frozen.digest;rows.clear();rules['price_tick']='999'
        self.assertEqual(len(frozen.frames['1m']),303);self.assertEqual(frozen.rules['price_tick'],RULES['price_tick']);self.assertEqual(frozen.digest,digest)
        with self.assertRaises(FrozenInstanceError):frozen.data_kind='historical'
    def test_money_summaries_keep_eight_places_and_normalize_negative_zero(self):
        tiny=[{'net_pnl_quote':'-0.000000001','ambiguous':False}]
        r=summarize([{'equity_quote':'10000'}],tiny)
        self.assertEqual(r['expectancy_quote'],'0.00000000')
        self.assertEqual(run_backtest(dataset(),config())['fees_quote'],'0.00000000')
    def test_cost_sensitivity_cannot_improve_same_execution_cash(self):
        a=run_backtest(dataset(),config(simulate_orders=True),fee_bps='5')
        b=run_backtest(dataset(),config(simulate_orders=True),fee_bps='10')
        self.assertGreaterEqual(D(b['fees_quote']),D(a['fees_quote']))
        # Sizing may decrease at higher costs; no synthetic return superiority claim.
        self.assertNotEqual(a['execution_costs'],b['execution_costs'])
    def test_malformed_foreign_or_future_mixed_dataset_is_rejected(self):
        d=dataset()
        for mutate in ('gap','unfinished','identity','source','nonfinite','alignment'):
            b=list(d.frames['1m'])
            if mutate=='gap':b.pop(10)
            elif mutate=='unfinished':b[-1]=replace(b[-1],is_final=False)
            elif mutate=='identity':b[-1]=replace(b[-1],instrument=replace(b[-1].instrument,contract_type='perpetual'))
            elif mutate=='source':b[-1]=replace(b[-1],source='other')
            elif mutate=='nonfinite':b[-1]=replace(b[-1],close='NaN')
            else:b=[replace(x,open_time_ms=x.open_time_ms+1,close_time_ms=x.close_time_ms+1) for x in b]
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):HistoricalDataset({'1m':b},RULES,data_kind='synthetic',data_version='test')
    def test_research_configuration_and_resource_limits(self):
        for kw in ({'simulate_orders':'yes'},{'strategy_ids':('not-real',)},{'max_events':0},{'analysis_every_bars':True}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):config(**kw)
        with self.assertRaises(ValueError):run_backtest(dataset(),config(max_events=2))
        for value in ('NaN','Infinity','-1'):
            with self.assertRaises(ValueError):run_backtest(dataset(),config(),fee_bps=value)
    def test_missing_requested_frames_and_analysis_budget_fail_before_writing(self):
        with self.assertRaises(ValueError):run_backtest(dataset(),config(timeframes=('4H',)))
        with self.assertRaises(ValueError):run_backtest(dataset(),config(analysis_every_bars=1,max_analyses=1))
    def test_an_earlier_failed_audit_cannot_be_hidden_by_final_pass(self):
        from unittest.mock import patch
        from market_ai.v2.research import audit_database
        calls=[]
        def first_failure(*args,**kwargs):
            r=audit_database(*args,**kwargs)
            if not calls:r['status']='MISMATCH'
            calls.append(1);return r
        with patch('market_ai.v2.research.audit_database',side_effect=first_failure):
            r=run_backtest(dataset(),config())
        self.assertEqual(r['audit']['status'],'PASS')
        self.assertEqual(r['integrity_status'],'MISMATCH')
    def test_empty_metrics_do_not_invent_winrate_or_profit_factor(self):
        r=summarize([],[],seed=1)
        self.assertEqual(r['scored_trades'],0);self.assertIsNone(r['expectancy_quote']);self.assertIsNone(r['profit_factor'])
        for v in ('NaN','Infinity',True):
            with self.assertRaises(ValueError):summarize([{'equity_quote':v}],[],seed=1)
    def test_research_decimal_context_isolated(self):
        expected=run_backtest(dataset(),config(simulate_orders=True))
        with localcontext() as ctx:
            ctx.prec=5;ctx.rounding=ROUND_DOWN
            self.assertEqual(run_backtest(dataset(),config(simulate_orders=True)),expected)
    def test_walk_forward_purges_future_horizon_and_has_no_overlapping_tests(self):
        splits=walk_forward_splits(1000,train_bars=300,test_bars=100,purge_bars=10)
        self.assertEqual(splits[0],{'train_start':0,'train_end':300,'test_start':310,'test_end':410})
        for a,b in zip(splits,splits[1:]):self.assertLessEqual(a['test_end'],b['test_start'])
        for s in splits:self.assertEqual(s['test_start']-s['train_end'],10)
        for kw in ({'train_bars':True},{'test_bars':0},{'purge_bars':-1}):
            with self.assertRaises(ValueError):walk_forward_splits(1000,**kw)
    def test_bootstrap_is_seeded_and_does_not_imply_forward_validation(self):
        trades=[{'net_pnl_quote':str((i%7)-3),'ambiguous':False} for i in range(40)]
        a=summarize([{'equity_quote':'10000'}],trades,seed=12)
        self.assertEqual(a,summarize([{'equity_quote':'10000'}],trades,seed=12));self.assertIsNotNone(a['mean_pnl_interval'])
        self.assertEqual(a['evidence_status'],'INSUFFICIENT_EVIDENCE')
    def test_cli_runs_only_on_explicit_input_and_preserves_source_bytes(self):
        from dataclasses import asdict
        from contextlib import redirect_stdout
        from io import StringIO
        import json
        from scripts.research_v2 import main
        d=dataset()
        rows=[]
        for bar in d.frames['1m']:
            row=asdict(bar);row.pop('instrument');row.pop('source');rows.append(row)
        body={'schema_version':1,'data_kind':'synthetic','data_version':'test',
              'instrument':asdict(d.identity),'source':d.source,'rules':dict(d.rules),'frames':{'1m':rows}}
        with TemporaryDirectory(prefix='research-cli-') as root:
            p=Path(root)/'source.json';p.write_text(json.dumps(body));before=p.read_bytes()
            output=StringIO()
            with redirect_stdout(output):code=main([str(p),'--start-ms',str(NOW),'--end-ms',str(NOW+3*TF),'--paper'])
            self.assertEqual(code,0);self.assertEqual(p.read_bytes(),before)
            report=json.loads(output.getvalue());self.assertEqual(report['integrity_status'],'PASS');self.assertEqual(report['data_kind'],'synthetic')
            for value in (None,[],{'1m':None}):
                body['frames']=value;p.write_text(json.dumps(body))
                with self.assertRaises(ValueError):load_dataset(p)
    def test_cli_loader_rejects_unknown_fields_and_never_creates_input(self):
        import json
        with TemporaryDirectory(prefix='research-load-') as root:
            p=Path(root)/'absent.json'
            with self.assertRaises(FileNotFoundError):load_dataset(p)
            self.assertFalse(p.exists());p.write_text(json.dumps({'token':'forbidden'}))
            with self.assertRaises(ValueError):load_dataset(p)
