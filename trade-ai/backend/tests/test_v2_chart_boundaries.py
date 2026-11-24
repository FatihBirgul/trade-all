from dataclasses import replace
from decimal import localcontext
from unittest import TestCase
from tests.test_v2_chart_research import base,chart
from tests.test_v2_chart_completion import append
from tests.test_v2_pattern_research import TF

def geometry(kind):
 b=base(67)
 for i in range(40):b[i]=replace(b[i],open=80+i*.5,high=81+i*.5,low=79+i*.5,close=80+i*.5)
 for j in range(40,67):
  t=j-40
  high,low=(110,94+.45*t) if kind=='ascending_triangle' else (110-.2*t,94+.2*t) if kind=='symmetrical_triangle' else (110+.15*t,94+.55*t) if kind=='rising_wedge' else (110,94) if kind=='rectangle' else (110+.2*t,94+.2*t)
  mid=(high+low)/2;width=high-low
  b[j]=replace(b[j],open=mid,high=high if j in (43,51,59) else mid+width/4,low=low if j in (47,55,63) else mid-width/4,close=mid)
 return b

def match(b,name):return [p for p in chart(b)['patterns'] if p['pattern_id']==name+'_boundary']
class ChartBoundaryTests(TestCase):
 def test_triangle_wedge_rectangle_channel_candidates_and_confirmation(self):
  for family in ('ascending_triangle','symmetrical_triangle','rising_wedge','rectangle','rising_channel'):
   b=geometry(family);p=match(b,family)[0]
   self.assertEqual(p['formed_at'],64*TF);self.assertEqual(p['known_at'],67*TF);self.assertIsNone(p['confirmed_at']);self.assertFalse(p['trade_permission'])
   b=append(b,120);self.assertIsNone(match(b,family)[0]['confirmed_at']);b=append(b,121)
   self.assertEqual(match(b,family)[0]['confirmed_at'],69*TF)
 def test_mirrored_variants_and_wedge_actual_break_interpretation(self):
  for family,other in (('ascending_triangle','descending_triangle'),('rising_wedge','falling_wedge'),('rising_channel','falling_channel')):
   b=[replace(x,open=230-x.open,high=230-x.low,low=230-x.high,close=230-x.close) for x in geometry(family)]
   self.assertTrue(match(b,other));b=append(append(b,90),89);self.assertEqual(match(b,other)[0]['direction'],'bearish')
  b=append(append(geometry('rising_wedge'),90),89)
  self.assertEqual(match(b,'rising_wedge')[0]['interpretation'],'reversal')
 def test_failed_breakout_and_closed_retest_are_not_backdated(self):
  b=geometry('ascending_triangle');b=append(append(b,112),105)
  p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='ascending_triangle_boundary_failure')
  self.assertEqual(p['known_at'],69*TF);self.assertEqual(p['confirmed_at'],69*TF)
  b=append(append(geometry('ascending_triangle'),112),113);b=append(b,112,low=110,high=113)
  self.assertTrue(any(p['pattern_id']=='ascending_triangle_boundary_retest' and p['known_at']==70*TF for p in chart(b)['patterns']))
 def test_negative_touch_equal_gap_and_insufficient_history(self):
  b=geometry('ascending_triangle');b[51]=replace(b[51],high=b[50].high)
  self.assertFalse(match(b,'ascending_triangle'))
  good=geometry('ascending_triangle')
  for bad in (good[:35],good[:50]+good[51:],good[:-1]+[replace(good[-1],is_final=False)]):self.assertEqual(chart(bad)['status'],'unavailable')
 def test_right_pivot_delay_and_prefix_identity(self):
  b=geometry('ascending_triangle');self.assertFalse(match(b[:66],'ascending_triangle'));old=chart(b)
  p=match(b,'ascending_triangle')[0];new=match(append(append(b,120),121),'ascending_triangle')[0]
  self.assertEqual(p['event_id'],new['event_id']);self.assertEqual(old,chart(b))
  with localcontext() as c:c.prec=3;self.assertEqual(chart(b),old)
 def test_equal_closed_boundary_is_not_a_break_and_extension_failure_is_isolated(self):
  from unittest.mock import patch
  b=append(append(geometry('ascending_triangle'),110),110)
  self.assertIsNone(match(b,'ascending_triangle')[0]['confirmed_at'])
  with patch('market_ai.v2.chart_research.boundaries',side_effect=RuntimeError('fixture boundary failure')):r=chart(b)
  self.assertEqual(r['boundary_status'],'unavailable');self.assertEqual(r['status'],'available')
  self.assertIn('boundary_engine_unavailable',r['issues'])
