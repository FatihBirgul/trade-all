from dataclasses import replace
from unittest import TestCase
from tests.test_v2_chart_research import base,chart
from tests.test_v2_chart_completion import append
from tests.test_v2_pattern_research import TF

def rounded(top=False):
 b=base(70);values=[110-i for i in range(10)]+[100+(i%2)*.05 for i in range(10)]+[101+i for i in range(10)]
 for j,price in enumerate(values,40):b[j]=replace(b[j],open=price-.1,high=price+.4,low=price-.4,close=price)
 return [replace(x,open=230-x.open,high=230-x.low,low=230-x.high,close=230-x.close) for x in b] if top else b
class RoundingResearchTests(TestCase):
 def test_bottom_top_need_two_later_closed_neckline_crosses(self):
  for top in (False,True):
   b=rounded(top);name='rounding_top_geometry' if top else 'rounding_bottom_geometry'
   p=next(p for p in chart(b)['patterns'] if p['pattern_id']==name and p['formed_at']==70*TF);self.assertIsNone(p['confirmed_at']);self.assertEqual(p['known_at'],70*TF)
   b=append(append(b,119 if top else 111),118 if top else 112)
   p=next(p for p in chart(b)['patterns'] if p['pattern_id']==name and p['formed_at']==70*TF);self.assertEqual(p['confirmed_at'],72*TF);self.assertFalse(p['trade_permission'])
 def test_flat_v_shape_and_unfinished_source_do_not_manufacture_a_rounding(self):
  self.assertFalse(any('rounding_' in p['pattern_id'] for p in chart(base(70))['patterns']))
  b=rounded();
  for j in range(50,60):b[j]=replace(b[j],open=95,high=105,low=94,close=95 if j%2 else 104)
  self.assertFalse(any(p['pattern_id']=='rounding_bottom_geometry' and p['formed_at']==70*TF for p in chart(b)['patterns']))
  self.assertEqual(chart(b[:-1]+[replace(b[-1],is_final=False)])['status'],'unavailable')
 def test_equal_neckline_is_not_confirmation_and_prefix_stays_immutable(self):
  b=rounded();old=chart(b);b2=append(append(b,110),110)
  self.assertIsNone(next(p for p in chart(b2)['patterns'] if p['pattern_id']=='rounding_bottom_geometry' and p['formed_at']==70*TF)['confirmed_at'])
  self.assertEqual(old,chart(b));self.assertEqual(chart(base(59))['rounding_status'],'insufficient_history')
 def test_invalidation_is_an_observed_later_close(self):
  b=append(rounded(),98)
  p=next(p for p in chart(b)['patterns'] if p['pattern_id']=='rounding_bottom_geometry' and p['formed_at']==70*TF)
  self.assertEqual(p['quality_status'],'invalidated');self.assertEqual(p['invalidated_at'],71*TF)
