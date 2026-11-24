"""Actual V1-family fixtures, not mocked detector outputs or market validation.

Legacy families remain STRUCTURAL_CANDIDATE: formation start/invalidation are
not inferred from a name. Narrow neckline/boundary lifecycle tests live beside
this matrix in chart_completion/chart_boundaries.
"""
from dataclasses import replace
from unittest import TestCase
from tests.test_v2_chart_boundaries import geometry
from tests.test_v2_chart_research import base,chart
from tests.test_v2_pattern_research import TF
from market_ai.v2.chart_research import STRUCTURAL
from market_ai.v2.pattern_research import slug

def mirror(b):return [replace(x,open=230-x.open,high=230-x.low,low=230-x.high,close=230-x.close) for x in b]
def fixtures():
 double=base(65)
 for i in (45,57):double[i]=replace(double[i],high=110)
 hs=base(75)
 for i,h in ((45,110),(55,115),(65,110)):hs[i]=replace(hs[i],high=h)
 hs[50]=replace(hs[50],low=95);hs[60]=replace(hs[60],low=97)
 return {'double_top':double,'double_bottom':mirror(double),'head_and_shoulders':hs,'inverse_head_and_shoulders':mirror(hs),
  'ascending_triangle':geometry('ascending_triangle'),'descending_triangle':mirror(geometry('ascending_triangle')),
  'symmetrical_triangle':geometry('symmetrical_triangle'),'rising_wedge':geometry('rising_wedge'),
  'falling_wedge':mirror(geometry('rising_wedge')),'channel':geometry('rising_channel'),'rectangle':geometry('rectangle')}

class StructuralFixtureMatrixTests(TestCase):
 def test_each_v1_family_has_real_positive_negative_and_insufficient_fixture(self):
  self.assertEqual(set(fixtures()),{slug(n) for n in STRUCTURAL})
  for family,b in fixtures().items():
   with self.subTest(family=family):
    matches=[p for p in chart(b)['patterns'] if p['pattern_id']==family]
    self.assertTrue(matches,family)
    self.assertNotIn(family,{p['pattern_id'] for p in chart(base(len(b)))['patterns']})
    self.assertEqual(chart(b[:39])['status'],'unavailable')
    for p in matches:
     self.assertLessEqual(p['formed_at'],p['known_at']);self.assertLessEqual(p['known_at'],b[-1].close_time_ms)
     self.assertFalse(p['trade_permission']);self.assertEqual(p['kind'],'structural_candidate')
 def test_first_observation_is_causal_and_has_no_future_closed_confirmation(self):
  for family,b in fixtures().items():
   with self.subTest(family=family):
    p=next(p for p in chart(b)['patterns'] if p['pattern_id']==family)
    n=p['known_at']//TF
    prefix=b[:n]
    same=lambda r:[x for x in r['patterns'] if x['pattern_id']==family and x['formed_at']==p['formed_at']]
    self.assertTrue(same(chart(prefix)))
    if n>40:self.assertFalse(same(chart(b[:n-1])))
    before=chart(prefix);chart(b);self.assertEqual(chart(prefix),before)
    for item in before['patterns']:
     self.assertTrue(item['confirmed_at'] is None or item['confirmed_at']<=prefix[-1].close_time_ms)
 def test_equal_pivots_missing_candles_and_volume_availability_are_explicit(self):
  for family,b in fixtures().items():
   with self.subTest(family=family):
    self.assertEqual(chart(b[:42]+b[43:])['status'],'unavailable')
    self.assertEqual(chart(b[:-1]+[replace(b[-1],is_final=False)])['status'],'unavailable')
    # Geometry uses price only; unavailable real volume must not manufacture a
    # different pattern or a volume-confirmed/execution claim.
    no_volume=[replace(x,volume=None,volume_kind='unavailable') for x in b]
    self.assertEqual(chart(no_volume)['patterns'],chart(b)['patterns'])
  double=fixtures()['double_top'];double[46]=replace(double[46],high=110)
  self.assertFalse(any(p['pattern_id']=='double_top_neckline' for p in chart(double)['patterns']))
 def test_falling_wedge_requires_convergence_not_divergence(self):
  b=fixtures()['falling_wedge']
  self.assertTrue(any(p['pattern_id']=='falling_wedge' for p in chart(b)['patterns']))
  # Reverse slope ordering: both fall, but the width grows. V1 incorrectly
  # calls this Falling Wedge. Correct only the descriptive V2 adapter.
  divergent=[]
  for i,x in enumerate(b):
   shift=(i-40)*.4 if i>=40 else 0
   divergent.append(replace(x,high=x.high+shift,low=x.low-shift))
  self.assertFalse(any(p['pattern_id']=='falling_wedge' for p in chart(divergent)['patterns']))
