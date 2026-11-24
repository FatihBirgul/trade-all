"""Causal pivot/legacy-oscillator comparisons; not market-performance evidence."""
from dataclasses import replace
from decimal import localcontext,ROUND_DOWN
from unittest import TestCase
from tests.test_v2_pattern_research import bars,TF
from market_ai.v2.divergence_research import detect_divergences

def fixture(mirror=False):
    origin=bars()[0];out=[]
    for i in range(60):
        close=100+i*.1;low=close-.2;high=close+.2
        if i==35:close,low,high=90,89,90.2
        if i==48:close,low,high=92,88,92.2
        if mirror:close,low,high=200-close,200-high,200-low
        out.append(replace(origin,open_time_ms=i*TF,close_time_ms=(i+1)*TF,open=close,close=close,high=high,low=low))
    return out

def run(b,**kwargs):return detect_divergences(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,tick_size='0.01',**kwargs)

class ConfirmedDivergenceTests(TestCase):
    def test_actual_rsi_and_macd_bullish_and_bearish_fixtures(self):
        for mirror,direction in ((False,'bullish'),(True,'bearish')):
            b=fixture(mirror);r=run(b)
            events=[p for p in r['events'] if p['direction']==direction and p['formed_at']==b[48].close_time_ms]
            self.assertEqual({p['method_id'] for p in events},{'legacy_rsi14_sma','legacy_macd_line_12_26'})
            for p in events:self.assertEqual(p['confirmed_at'],b[50].close_time_ms);self.assertFalse(p['trade_permission'])
    def test_right_pivot_bars_are_required_and_prefix_is_invariant(self):
        b=fixture();before=run(b[:50]);at=run(b[:51]);full=run(b)
        self.assertFalse(any(p['formed_at']==b[48].close_time_ms for p in before['events']))
        self.assertEqual(at['events'],[p for p in full['events'] if p['confirmed_at']<=b[50].close_time_ms])
        self.assertTrue(any(p['formed_at']==b[48].close_time_ms for p in at['events']))
    def test_tied_pivot_and_wrong_price_direction_do_not_emit_bullish_pair(self):
        b=fixture();b[47]=replace(b[47],low=88)
        self.assertFalse(any(p['formed_at']==b[48].close_time_ms and p['direction']=='bullish' for p in run(b)['events']))
        b=fixture();b[48]=replace(b[48],low=90)
        self.assertFalse(any(p['formed_at']==b[48].close_time_ms and p['direction']=='bullish' for p in run(b)['events']))
    def test_global_decimal_context_does_not_change_output(self):
        b=fixture();expected=run(b)
        with localcontext() as c:c.prec=3;c.rounding=ROUND_DOWN;self.assertEqual(run(b),expected)
    def test_bad_or_unfinished_data_and_warmup_never_produce_events(self):
        b=fixture()
        for bad in (b[:20],[*b[:-1],replace(b[-1],is_final=False)],b[:20]+b[21:]):
            r=run(bad);self.assertNotEqual(r['status'],'available');self.assertEqual(r['events'],[])
    def test_bounded_input_and_invalid_tick_fail_closed(self):
        b=fixture();long=(replace(b[0],open_time_ms=i*TF,close_time_ms=(i+1)*TF) for i in range(1000000))
        r=detect_divergences(long,timeframe='1m',as_of_ms=1000000*TF,max_age_ms=TF,tick_size='0.01')
        self.assertEqual(r['reason'],'resource_budget');self.assertEqual(r['events'],[])
        for tick in ('NaN','Infinity','0','-1'):
            r=detect_divergences(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,tick_size=tick)
            self.assertEqual(r['events'],[]);self.assertNotEqual(r['status'],'available')

    def test_identity_binds_instrument_source_and_actual_observations(self):
        b=fixture();original=run(b)['events']
        other=[replace(x,instrument=replace(x.instrument,symbol='ETHUSDT')) for x in b]
        self.assertTrue(original);self.assertNotEqual(original[0]['event_id'],run(other)['events'][0]['event_id'])
        altered=[replace(x,source='another_fixture_source') for x in b]
        self.assertNotEqual(original[0]['event_id'],run(altered)['events'][0]['event_id'])
    def test_product_diagnostics_materialize_closed_iterable_once(self):
        from market_ai.v2.analysis_diagnostics import compute_diagnostics
        b=fixture();args=dict(timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,tick_size='0.01',source_record_id='fixture-source')
        self.assertEqual(compute_diagnostics(iter(b),**args),compute_diagnostics(b,**args))
    def test_optional_divergence_failure_keeps_existing_research(self):
        from unittest.mock import patch
        from market_ai.v2.analysis_diagnostics import compute_diagnostics
        b=fixture();args=dict(timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,tick_size='0.01',source_record_id='fixture-source')
        original=compute_diagnostics(b,**args)
        with patch('market_ai.v2.analysis_diagnostics.detect_divergences',side_effect=RuntimeError('controlled optional failure')):
            result=compute_diagnostics(b,**args)
        self.assertEqual(result['patterns'],original['patterns']);self.assertEqual(result['methods'],original['methods'])
        self.assertEqual(result['divergences']['status'],'unavailable')
