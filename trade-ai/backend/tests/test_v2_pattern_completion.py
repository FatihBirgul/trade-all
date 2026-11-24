"""Explicit engineering definitions, not TA-Lib equivalence or trade signals."""
from dataclasses import replace
from unittest import TestCase
from tests.test_v2_pattern_research import bars,detect,TF
from market_ai.v2.pattern_research import CATALOG
TAIL=[(100,110,90,100),(100,108,92,92.5),(100,106,94,100),(99,105,93,94)]
def family(data,name):return [p for p in detect(data)['patterns'] if p['family']==name]
class PatternCompletionTests(TestCase):
    def test_modified_hikkake_both_directions_delay_and_prefix(self):
        for mirrored in (False,True):
            tail=TAIL if not mirrored else [(200-o,200-l,200-h,200-c) for o,h,l,c in TAIL]
            b=bars(tail);before=detect(b);p=family(b,'hikkake_modified')[0]
            self.assertEqual(p['direction'],'bearish' if mirrored else 'bullish');self.assertIsNone(p['confirmed_at']);self.assertEqual(p['known_at'],b[-1].close_time_ms)
            new=(94,108,93,107) if not mirrored else (106,107,92,93)
            b+= [replace(b[-1],open_time_ms=b[-1].close_time_ms,close_time_ms=b[-1].close_time_ms+TF,open=new[0],high=new[1],low=new[2],close=new[3])]
            p=family(b,'hikkake_modified')[0];self.assertEqual(p['confirmed_at'],b[-1].close_time_ms);self.assertFalse(detect(b)['trade_permission']);self.assertEqual(before,detect(b[:-1]))
    def test_modified_requires_both_strict_inside_and_near_close(self):
        for tail in (TAIL[:1]+[(100,110,92,92.5)]+TAIL[2:],TAIL[:1]+[(100,108,92,100)]+TAIL[2:]):
            self.assertFalse(family(bars(tail),'hikkake_modified'))
    def test_modified_expiry_equal_threshold_and_invalid_source(self):
        b=bars(TAIL)
        for _ in range(3):b.append(replace(b[-1],open_time_ms=b[-1].close_time_ms,close_time_ms=b[-1].close_time_ms+TF,open=99,high=106,low=93,close=106))
        p=family(b,'hikkake_modified')[0];self.assertIsNone(p['confirmed_at']);self.assertEqual(p['quality_status'],'confirmation_expired')
        self.assertEqual(detect(b[:-1]+[replace(b[-1],is_final=False)])['status'],'unavailable')
        self.assertEqual(detect(b[:20])['status'],'unavailable')
    def test_neck_continuations_distinct_levels_gap_and_midpoint_boundary(self):
        first=(110,111,99,100)
        for name,close in [('on_neck',99),('in_neck',100.25),('thrusting',103)]:
            b=bars([first,(98,104,97,close)])
            self.assertTrue(family(b,name),name)
            self.assertFalse(family(bars([first,(100,104,99,close if close>=100 else 100)]),name))
        self.assertFalse(family(bars([first,(98,106,97,105)]),'thrusting'))
    def test_separating_lines_need_trend_equal_open_and_directional_body(self):
        prefix=bars()
        prefix=[replace(x,open=100+i*.4,high=101+i*.4,low=99+i*.4,close=100.3+i*.4) for i,x in enumerate(prefix)]
        tail=bars([(112,113,107,108),(112,118,112,118)])[-2:];b=prefix+tail
        p=family(b,'separating_lines')[0];self.assertEqual(p['direction'],'bullish')
        self.assertFalse(family(prefix+[tail[0],replace(tail[1],open=112.02)],'separating_lines'))
        self.assertFalse(family(bars([(112,113,107,108),(112,118,112,118)]),'separating_lines'))
        mirror=[replace(x,open=220-x.open,high=220-x.low,low=220-x.high,close=220-x.close) for x in b]
        self.assertEqual(family(mirror,'separating_lines')[0]['direction'],'bearish')
    def test_catalog_and_version_are_bound_to_real_new_detections(self):
        p=family(bars(TAIL),'hikkake_modified')[0]
        self.assertEqual(CATALOG['hikkake_modified']['status'],'IMPLEMENTED')
        self.assertEqual(p['pattern_version'],'v2-hikkake-modified-1')
        self.assertIn('prior5',p['explanation']);self.assertGreaterEqual(p['required_closed_bars'],25)
