"""Chart knowledge timestamps must not be backdated to a structural pivot."""
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from tests.test_v2_pattern_research import bars,TF
from market_ai.v2.chart_research import detect_charts

def chart(b):return detect_charts(b,timeframe='1m',as_of_ms=b[-1].close_time_ms,max_age_ms=TF,tick_size='0.01')
def base(n=65):
    b=bars()
    return [replace(b[0],open_time_ms=i*TF,close_time_ms=(i+1)*TF) for i in range(n)]

class ChartResearchTests(TestCase):
    def test_actual_double_top_requires_right_pivot_confirmation(self):
        b=base();b[45]=replace(b[45],high=110);b[57]=replace(b[57],high=110)
        self.assertNotIn('double_top',{p['pattern_id'] for p in chart(b[:60])['patterns']})
        p=next(p for p in chart(b[:61])['patterns'] if p['pattern_id']=='double_top')
        self.assertEqual(p['formed_at'],b[57].close_time_ms);self.assertEqual(p['known_at'],b[60].close_time_ms)
        self.assertFalse(p['trade_permission']);self.assertEqual(p['kind'],'structural_candidate')
    def test_current_price_condition_is_not_backdated_to_pivot_plus_three(self):
        b=base()
        def detector(rows):
            return [] if len(rows)<55 else [{'name':'Double Top','location':45,'classification':'bearish','confirmed':True,'base_confidence':62,'explanation':'fixture condition becomes known at55'}]
        with patch('market_ai.v2.chart_research.legacy._detect',side_effect=detector):r=chart(b)
        p=next(p for p in r['patterns'] if p['pattern_id']=='double_top')
        self.assertEqual(p['known_at'],b[54].close_time_ms);self.assertNotEqual(p['known_at'],b[48].close_time_ms)
    def test_breakout_uses_previous_range_and_next_closed_confirmation(self):
        b=base(40);b.append(replace(b[-1],open_time_ms=40*TF,close_time_ms=41*TF,open=100,high=104,low=99.5,close=103))
        p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='range_breakout');self.assertIsNone(p['confirmed_at'])
        b.append(replace(b[-1],open_time_ms=41*TF,close_time_ms=42*TF,open=103,high=104,low=102,close=103))
        p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='range_breakout' and p['formed_at']==41*TF)
        self.assertEqual(p['confirmed_at'],42*TF)
    def test_retest_and_failed_breakout_have_actual_observation_times(self):
        b=base(40)
        b.append(replace(b[-1],open_time_ms=40*TF,close_time_ms=41*TF,open=100,high=104,low=99.5,close=103))
        b.append(replace(b[-1],open_time_ms=41*TF,close_time_ms=42*TF,open=103,high=104,low=100.99,close=102))
        self.assertIn('range_retest',{p['pattern_id'] for p in chart(b)['patterns']})
        b[-1]=replace(b[-1],low=99,close=100)
        self.assertIn('failed_range_breakout',{p['pattern_id'] for p in chart(b)['patterns']})
    def test_future_unfinished_gapped_and_excessive_data_fail_closed(self):
        b=base()
        for bad in (b[:-2]+b[-1:],b[:-1]+[replace(b[-1],is_final=False)]):self.assertEqual(chart(bad)['status'],'unavailable')
        self.assertEqual(detect_charts(b,timeframe='1m',as_of_ms=TF,max_age_ms=TF,tick_size='0.01')['status'],'unavailable')
        with self.assertRaises(ValueError):chart(base(257))
    def test_unknown_legacy_pattern_does_not_become_a_verified_feature(self):
        with patch('market_ai.v2.chart_research.legacy._detect',return_value=[{'name':'Magic Pattern','location':45}]):
            self.assertEqual(chart(base())['patterns'],[])
    def test_snapshot_does_not_mutate_when_future_data_is_appended(self):
        b=base(40);before=chart(b)
        future=replace(b[-1],open_time_ms=40*TF,close_time_ms=41*TF,high=150,close=149)
        chart(b+[future]);self.assertEqual(chart(b),before)

    def test_legacy_core_failure_is_unavailable_and_no_partial_shapes(self):
        with patch('market_ai.v2.chart_research.legacy._detect',side_effect=RuntimeError('fixture error')):
            r=chart(base());self.assertEqual(r['status'],'unavailable');self.assertEqual(r['patterns'],[])

    def test_retest_does_not_hide_a_subsequent_failed_breakout(self):
        b=base(40)
        for i,(low,close) in enumerate(((99.5,103),(100.99,102),(99,100)),40):
            b.append(replace(b[-1],open_time_ms=i*TF,close_time_ms=(i+1)*TF,open=102,high=104,low=low,close=close))
        r=chart(b);names={p['pattern_id'] for p in r['patterns'] if p['formed_at']==41*TF}
        self.assertTrue({'range_retest','failed_range_breakout'}<=names,names)
