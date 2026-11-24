from dataclasses import replace,FrozenInstanceError
from decimal import localcontext
from unittest import TestCase
from tests.test_v2_pattern_research import bars,TF
from market_ai.v2.indicator_parameters import IndicatorParameters,compute_parameters
class IndicatorParameterTests(TestCase):
 def data(self):
  b=bars();return [replace(b[0],open_time_ms=i*TF,close_time_ms=(i+1)*TF,open=100+i*.2,high=101+i*.2,low=99+i*.2,close=100.1+i*.2) for i in range(100)]
 def calc(self,b,p=None):return compute_parameters(b,p or IndicatorParameters(),timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF)
 def test_immutable_identity_whitelist_bounds_and_versions(self):
  p=IndicatorParameters();self.assertEqual(p.parameter_id,IndicatorParameters().parameter_id)
  with self.assertRaises(FrozenInstanceError):p.ema_period=3
  for kw in ({'ema_period':True},{'rsi_period':0},{'sma_period':201},{'macd_fast':30,'macd_slow':20},{'supertrend_multiplier':'NaN'},{'bias_confirmation':True},{'implementation_version':'future'}):
   with self.assertRaises(ValueError):IndicatorParameters(**kw)
  with self.assertRaises(TypeError):IndicatorParameters(arbitrary_permission=True)
 def test_parameterized_values_preserve_legacy_defaults_and_no_permission(self):
  import pandas as pd
  from market_ai.engines import technical
  b=self.data();p=IndicatorParameters();r=self.calc(b,p);self.assertEqual(r['status'],'available');self.assertFalse(r['trade_permission'])
  series=pd.Series([x.close for x in b]);self.assertAlmostEqual(float(r['methods']['ema']),float(technical.ema(series,20).iloc[-1]))
  self.assertAlmostEqual(float(r['methods']['rsi_sma']),float(technical.rsi(series,14).iloc[-1]))
  self.assertAlmostEqual(float(r['methods']['macd_line']),float(technical.macd(series)[0].iloc[-1]))
  changed=self.calc(b,replace(p,ema_period=8));self.assertNotEqual(changed['parameter_id'],r['parameter_id']);self.assertNotEqual(changed['methods']['ema'],r['methods']['ema'])
 def test_global_decimal_context_prefix_and_source_binding(self):
  b=self.data();p=IndicatorParameters();before=self.calc(b[:80],p)
  with localcontext() as ctx:ctx.prec=3;self.assertEqual(self.calc(b[:80],p),before)
  self.calc(b,p);self.assertEqual(self.calc(b[:80],p),before)
  changed=b[:79]+[replace(b[79],close=b[79].close+.1)];self.assertNotEqual(self.calc(changed,p)['input_digest'],before['input_digest'])
 def test_warmup_closed_gap_and_missing_bias_fail_closed(self):
  b=self.data();p=IndicatorParameters(ema_period=100)
  self.assertEqual(self.calc(b,p)['status'],'unavailable')
  for bad in (b[:20]+b[21:],b[:-1]+[replace(b[-1],is_final=False)]):self.assertEqual(self.calc(bad)['status'],'unavailable')
  self.assertEqual(self.calc(b,IndicatorParameters(bias_timeframe='5m',bias_confirmation=True))['status'],'unavailable')

class ParameterWalkForwardTests(TestCase):
 def test_frozen_training_selection_and_held_out_isolation(self):
  from market_ai.v2.walk_forward import IndicatorCandidate,run_walk_forward
  from tests.test_v2_walk_forward import data,cfg
  from market_ai.v2.research import HistoricalDataset
  from unittest.mock import patch
  from market_ai.v2.walk_forward import run_backtest
  p=IndicatorParameters(ema_period=8)
  protocol=cfg(candidates=(IndicatorCandidate('research',parameters=p),))
  calls=[]
  def spy(d,c,**kw):
   calls.append((d,kw));return run_backtest(d,c,**kw)
  with patch('market_ai.v2.walk_forward.run_backtest',side_effect=spy):a=run_walk_forward(data(),protocol)
  self.assertEqual(len(calls),2)
  self.assertIs(calls[0][1]['indicator_parameters'],p);self.assertIs(calls[1][1]['indicator_parameters'],p)
  self.assertEqual(a['validation_status'],'OOS_EVALUATED')
  d=data();rows=list(d.frames['1m'])
  for i in range(304,len(rows)):rows[i]=replace(rows[i],open=210,high=211,low=209,close=210)
  b=run_walk_forward(HistoricalDataset({'1m':rows},dict(d.rules),data_kind=d.data_kind,data_version=d.data_version),protocol)
  self.assertEqual(a['folds'][0]['training'],b['folds'][0]['training'])
  self.assertEqual(a['folds'][0]['frozen_parameters_hash'],b['folds'][0]['frozen_parameters_hash'])
  self.assertNotEqual(a['experiment_id'],b['experiment_id'])
 def test_restriction_cannot_resurrect_wait_and_legacy_identity_unchanged(self):
  from dataclasses import asdict
  from market_ai.v2.indicator_parameters import parameter_filter
  from market_ai.v2.walk_forward import Candidate,IndicatorCandidate,run_walk_forward
  from tests.test_v2_walk_forward import data,cfg
  self.assertEqual(set(asdict(Candidate())),{'candidate_id','strategy_ids','analysis_every_bars'})
  self.assertFalse(parameter_filter({'status':'available'},'WAIT')['passes'])
  p=IndicatorParameters(ema_period=200)
  with self.assertRaises(ValueError):run_walk_forward(data(),cfg(candidates=(IndicatorCandidate('long',parameters=p),)))
  with self.assertRaises(ValueError):IndicatorCandidate(parameters={'ema_period':20})
 def test_registry_duplicate_returns_frozen_result_and_rejects_reoptimization(self):
  from tempfile import TemporaryDirectory
  from pathlib import Path
  from market_ai.v2.walk_forward import IndicatorCandidate,run_walk_forward
  from market_ai.v2.research_registry import ResearchRegistry
  from tests.test_v2_walk_forward import data,cfg
  with TemporaryDirectory() as root:
   registry=ResearchRegistry.create(Path(root)/'registry.sqlite')
   config=cfg(candidates=(IndicatorCandidate('research',parameters=IndicatorParameters()),))
   a=run_walk_forward(data(),config,registry=registry)
   self.assertEqual(run_walk_forward(data(),config,registry=registry),a)
   with self.assertRaises(ValueError):run_walk_forward(data(),cfg(candidates=(IndicatorCandidate('research',parameters=IndicatorParameters(ema_period=8)),)),registry=registry)
 def test_higher_setup_frame_warmup_is_measured_in_execution_minutes(self):
  from market_ai.v2.walk_forward import IndicatorCandidate,run_walk_forward
  from tests.test_v2_walk_forward import data,cfg
  from market_ai.v2.research import HistoricalDataset
  from market_ai.v2.technical_research import resample_closed
  d=data();five=resample_closed(d.frames['1m'],source_timeframe='1m',target_timeframe='5m',as_of_ms=d.frames['1m'][-1].close_time_ms)
  # Only validation is under test: protocol has 250 minutes, requires 61*5.
  with self.assertRaises(ValueError):
   run_walk_forward(HistoricalDataset({'1m':d.frames['1m'],'5m':five},dict(d.rules),data_kind='synthetic',data_version=d.data_version),cfg(timeframe='5m',candidates=(IndicatorCandidate('five',parameters=IndicatorParameters()),)))
