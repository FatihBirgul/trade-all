from dataclasses import replace
from unittest import TestCase
from tests.test_v2_pattern_research import bars,detect,TF
from market_ai.v2.pattern_research import CATALOG
CASES={
 'three_stars_in_south':[(110,111,88,100),(105,106,95,101),(103,103.2,101.8,102)],
 'unique_three_river':[(110,111,99,100),(104,105,94,101),(98,101,97,100)],
 'advance_block':[(110,120.5,109.8,120),(117,126,116,124),(122,131,121,126)],
 'stalled_pattern':[(110,120.5,109.8,120),(118,129,117,128),(127.5,130,127,129)],
 'tristar':[(103,104,102,103),(100,101,99,100),(103,104,102,103)],
 'breakaway':[(110,111,99,100),(98,99,94,95),(96,97,91,92),(94,95,89,90),(90,100,89,99)]}
def fixture(name):
 b=bars(CASES[name]);up=name in ('advance_block','stalled_pattern')
 for i in range(30):
  price=100+i*.4 if up else 115-i*.4;b[i]=replace(b[i],open=price,high=price+1,low=price-1,close=price+.3)
 return b
def found(b,name):return [p for p in detect(b)['patterns'] if p['family']==name]
class CandleCompletion6Tests(TestCase):
 def test_all_six_real_definitions_positive_and_known_closed_times(self):
  for name in CASES:
   with self.subTest(name=name):
    b=fixture(name);p=found(b,name)[0];self.assertEqual(p['known_at'],b[-1].close_time_ms);self.assertIsNone(p['confirmed_at']);self.assertFalse(detect(b)['trade_permission']);self.assertEqual(CATALOG[name]['status'],'IMPLEMENTED')
 def test_confirmation_invalidation_and_prefix_invariance(self):
  for name in CASES:
   b=fixture(name);before=detect(b);p=found(b,name)[0];up=p['direction']=='bullish';price=b[-1].close
   nextbar=replace(b[-1],open_time_ms=b[-1].close_time_ms,close_time_ms=b[-1].close_time_ms+TF,open=price,close=price+(1 if up else -1),high=price+2,low=price-2)
   confirmed=found(b+[nextbar],name)[0];self.assertEqual(confirmed['confirmed_at'],nextbar.close_time_ms);self.assertEqual(before,detect(b))
   invalidprice=float(p['invalidation_level'])+(-1 if up else 1)
   bad=replace(nextbar,open=invalidprice,high=invalidprice+1,low=invalidprice-1,close=invalidprice)
   self.assertEqual(found(b+[bad],name)[0]['quality_status'],'invalidated')
 def test_equal_and_wrong_boundaries_reject_each_family(self):
  for name in CASES:
   b=fixture(name);b[-1]=replace(b[-1],open=b[-2].open,high=b[-2].high,low=b[-2].low,close=b[-2].close)
   self.assertFalse(found(b,name),name)
  b=fixture('tristar');b[-2]=replace(b[-2],high=b[-3].low);self.assertFalse(found(b,'tristar'))
 def test_mirrored_tristar_and_breakaway_direction(self):
  for name in ('tristar','breakaway'):
   b=[replace(x,open=230-x.open,high=230-x.low,low=230-x.high,close=230-x.close) for x in fixture(name)]
   self.assertEqual(found(b,name)[0]['direction'],'bearish')
 def test_insufficient_unfinished_and_gap_data_stay_unavailable(self):
  b=fixture('breakaway')
  for bad in (b[:20],b[:-1]+[replace(b[-1],is_final=False)],b[:-3]+b[-2:]):self.assertEqual(detect(bad)['status'],'unavailable')
 def test_confirmed_then_invalidated_pattern_is_not_supportive_evidence(self):
  from market_ai.v2.pattern_research import confluence_evidence
  b=fixture('unique_three_river');last=b[-1]
  a=replace(last,open_time_ms=last.close_time_ms,close_time_ms=last.close_time_ms+TF,open=100,high=103,low=99,close=101)
  z=replace(a,open_time_ms=a.close_time_ms,close_time_ms=a.close_time_ms+TF,open=93,high=94,low=92,close=93)
  p=found(b+[a,z],'unique_three_river')[0];self.assertIsNotNone(p['confirmed_at']);self.assertEqual(p['quality_status'],'invalidated')
  self.assertEqual(confluence_evidence({'status':'available','patterns':[p]}),[])
