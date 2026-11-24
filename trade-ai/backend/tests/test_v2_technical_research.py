"""Hand-computed indicator references and closed-frame boundaries."""
from dataclasses import replace
from decimal import Decimal as D, localcontext, ROUND_DOWN
from unittest import TestCase
from tests.test_v2_pattern_research import bars, TF
from market_ai.v2.technical_research import compute_methods, resample_closed


def methods(b):return compute_methods(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF)

class TechnicalResearchTests(TestCase):
    def test_roc_stochastic_and_previous_donchian_hand_reference(self):
        b=[replace(x,open=100+i,close=100+i,high=101+i,low=99+i) for i,x in enumerate(bars())]
        r=methods(b)['methods']
        self.assertEqual(D(r['donchian20_previous']['upper']),D('129'))
        self.assertEqual(D(r['donchian20_previous']['lower']),D('108'))
        with localcontext() as ctx:
            ctx.prec=60
            self.assertAlmostEqual(D(r['roc12']['percent']),D(1200)/117,places=50)
            self.assertAlmostEqual(D(r['stochastic14']['k']),D(1400)/15,places=50)
    def test_adx_wilder_trend_and_flat_zero_denominator(self):
        b=[replace(x,open=100+i,close=100+i,high=101+i,low=99+i) for i,x in enumerate(bars())]
        r=methods(b)['methods']['adx14_wilder']
        self.assertEqual(D(r['adx']),D('100'));self.assertEqual(D(r['plus_di']),D('50'));self.assertEqual(D(r['minus_di']),D('0'))
        flat=[replace(x,open=100,close=100,high=100,low=100) for x in bars()]
        r=methods(flat)['methods'];self.assertEqual(D(r['adx14_wilder']['adx']),0)
        self.assertEqual(r['stochastic14']['status'],'undefined_flat_range')
    def test_supertrend_is_causal_and_has_explicit_warmup(self):
        b=[replace(x,open=100+i,close=100+i,high=101+i,low=99+i) for i,x in enumerate(bars())]
        r=methods(b)['methods']['supertrend10_3']
        self.assertEqual(r['direction'],'bullish');self.assertLess(D(r['value']),D(str(b[-1].close)))
        self.assertEqual(methods(b[:10])['methods']['supertrend10_3']['status'],'warmup')
        self.assertEqual(methods(b[:27])['methods']['adx14_wilder']['status'],'warmup')
    def test_bandwidth_reuses_legacy_sample_standard_deviation(self):
        import pandas as pd
        from market_ai.engines.technical import bollinger
        b=[replace(x,open=100+i,close=100+i,high=101+i,low=99+i) for i,x in enumerate(bars())]
        u,m,l=bollinger(pd.Series([float(x.close) for x in b]))
        with localcontext() as ctx:
            ctx.prec=60
            expected=(D(str(u.iloc[-1]))-D(str(l.iloc[-1])))/D(str(m.iloc[-1]))*100
        self.assertEqual(D(methods(b)['methods']['bollinger_bandwidth20']['percent']),expected)
    def test_overflowing_legacy_bandwidth_is_unavailable_not_nan(self):
        b=[replace(x,open=(100+i)*1e200,close=(100+i)*1e200,high=(101+i)*1e200,low=(99+i)*1e200) for i,x in enumerate(bars())]
        r=methods(b)['methods']['bollinger_bandwidth20']
        self.assertEqual(r['status'],'unavailable_numeric_range')
        self.assertNotIn('percent',r)
    def test_invalid_future_unfinished_and_resource_gates(self):
        b=bars()
        for bad in (b[:-1]+[replace(b[-1],is_final=False)],b[:-2]+b[-1:]):self.assertEqual(methods(bad)['status'],'unavailable')
        self.assertEqual(compute_methods(b,timeframe='1m',as_of_ms=b[-1].close_time_ms-TF,max_age_ms=TF)['status'],'unavailable')
        with self.assertRaises(ValueError):methods(b*200)
    def test_missing_volume_is_not_synthesized_and_context_is_stable(self):
        b=[replace(x,volume=None,volume_kind='unavailable') for x in bars()]
        expected=methods(b);self.assertEqual(expected['status'],'available');self.assertFalse(expected['trade_permission'])
        with localcontext() as ctx:
            ctx.prec=4;ctx.rounding=ROUND_DOWN;self.assertEqual(methods(b),expected)
    def test_resampling_emits_only_full_closed_aligned_groups(self):
        b=bars();r=resample_closed(b,source_timeframe='1m',target_timeframe='5m',as_of_ms=b[-1].close_time_ms)
        self.assertEqual(len(r['candles']),6);self.assertEqual(r['dropped_partial_bars'],0)
        first=r['candles'][0];self.assertEqual(first.open_time_ms,0);self.assertEqual(first.close_time_ms,5*TF)
        self.assertEqual(D(str(first.volume)),D('500'))
        r=resample_closed(b[:-1],source_timeframe='1m',target_timeframe='5m',as_of_ms=29*TF)
        self.assertEqual(len(r['candles']),5);self.assertEqual(r['dropped_partial_bars'],4)
        for c in r['candles']:self.assertLessEqual(c.close_time_ms,29*TF)
    def test_resampling_rejects_bad_source_or_incompatible_frame(self):
        b=bars()
        for tf in ('1m','bogus'):
            with self.assertRaises(ValueError):resample_closed(b,source_timeframe='1m',target_timeframe=tf,as_of_ms=30*TF)
        with self.assertRaises(ValueError):resample_closed(b[:-2]+b[-1:],source_timeframe='1m',target_timeframe='5m',as_of_ms=30*TF)
        with self.assertRaises(ValueError):resample_closed(b,source_timeframe='1m',target_timeframe='5m',as_of_ms=29*TF)
    def test_unavailable_volume_resamples_as_unavailable(self):
        b=[replace(x,volume=None,volume_kind='unavailable') for x in bars()]
        r=resample_closed(b,source_timeframe='1m',target_timeframe='5m',as_of_ms=30*TF)
        self.assertTrue(all(x.volume is None and x.volume_kind=='unavailable' for x in r['candles']))

    def test_streaming_budget_limits_input_materialization(self):
        for resample,limit in ((False,4096),(True,30000)):
            consumed=[];bar=bars()[0]
            def source():
                for i in range(50000):consumed.append(i);yield bar
            with self.assertRaises(ValueError):
                if resample:resample_closed(source(),source_timeframe='1m',target_timeframe='5m',as_of_ms=TF)
                else:compute_methods(source(),timeframe='1m',as_of_ms=TF,max_age_ms=TF)
            self.assertEqual(len(consumed),limit+1)
