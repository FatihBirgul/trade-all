import unittest
from types import SimpleNamespace as B
from dataclasses import replace
from fixtures import fixture, NOW
from unified_forex.market import acquire
from unified_forex.candle_extensions import geometry, detect, FAMILIES

CASES={
 'separating_lines':[(100,101,95,96),(100,106,100,105)],
 'on_neck':[(110,111,99,100),(98,100,97,99)],
 'in_neck':[(110,111,99,100),(98,102,97,100.5)],
 'thrusting':[(110,111,99,100),(98,104,97,103)],
 'advance_block':[(100,108,99,106),(104,112,103,108),(107,114,106,109)],
 'stalled_pattern':[(100,107,99,106),(104,111,103,110),(109.995,112,109,110.5)],
 'tristar':[(100,101,99,100),(97,98,96,97),(100,101,99,100)],
 'three_line_strike':[(100,107,99,106),(103,110,102,109),(106,113,105,112),(114,115,98,99)],
 'breakaway':[(110,111,99,100),(97,98,94,95),(94,96,93,94.5),(94,95,92,93.5),(93,99,92,98.5)],
 'three_stars_in_south':[(110,110.1,94.5,100),(103,105,96,100.5),(102,104,98,100.6)],
 'unique_three_river':[(110,111,99,100),(102,104,95,101),(99,102,98,100)]}


class CandleCatalogue(unittest.TestCase):
    def rows(self,values):return [B(open=o,high=h,low=l,close=c) for o,h,l,c in values]
    def test_all_new_geometry_positive_negative_and_mirrors(self):
        self.assertEqual(set(CASES),set(FAMILIES))
        for family,values in CASES.items():
            with self.subTest(family=family):
                rows=self.rows(values)
                self.assertIn(family,{p[0] for p in geometry(rows,.01)})
                self.assertNotIn(family,{p[0] for p in geometry(rows,1000)})
                scaled=self.rows([(o*.001,h*.001,l*.001,c*.001) for o,h,l,c in values])
                self.assertIn(family,{p[0] for p in geometry(scaled,.00001)})
                self.assertNotIn(family,{p[0] for p in geometry(self.rows([(100,101,99,100)]*len(rows)),.01)})
                if family not in ('three_stars_in_south','unique_three_river'):
                    mirror=self.rows([(400-o,400-l,400-h,400-c) for o,h,l,c in values])
                    self.assertIn(family,{p[0] for p in geometry(mirror,.01)})

    def test_each_family_is_known_before_confirmation_and_never_backdated(self):
        f=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
        for family,values in CASES.items():
            with self.subTest(family=family):
                direction,trend=next((d,t) for name,d,t in geometry(self.rows(values),.01) if name==family)
                if family in ('on_neck','in_neck','thrusting','advance_block','stalled_pattern','three_line_strike'):
                    direction='bearish' if direction=='bullish' else 'bullish'
                rows=list(f.bars);start=len(rows)-len(values)-1
                for j in range(start-10,start):
                    v=100+trend*(j-(start-10));rows[j]=replace(rows[j],open=v,high=v+1,low=v-1,close=v)
                for j,(o,h,l,c) in enumerate(values,start):rows[j]=replace(rows[j],open=o,high=h,low=l,close=c)
                v=max(h for _,h,_,_ in values)+2 if direction=='bullish' else min(l for _,_,l,_ in values)-2
                rows[-1]=replace(rows[-1],open=v-1 if direction=='bullish' else v+1,high=v+2,low=v-2,close=v)
                before=detect(replace(f,bars=tuple(rows[:-1])),.01)
                p=next(p for p in before if p['pattern_id']==family and p['formed_at']==rows[-2].close_time_ms)
                self.assertIsNone(p['confirmed_at'])
                after=detect(replace(f,bars=tuple(rows)),.01)
                q=next(p for p in after if p['pattern_id']==family and p['formed_at']==rows[-2].close_time_ms)
                self.assertEqual(p['first_known_at'],q['first_known_at'])
                self.assertEqual(q['confirmed_at'],rows[-1].close_time_ms)

    def test_tick_boundary_and_trend_confirmation_timestamps(self):
        values=CASES['separating_lines'];rows=self.rows(values)
        rows[-1].open+=.011
        self.assertNotIn('separating_lines',{p[0] for p in geometry(rows,.01)})
        f=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
        bars=list(f.bars)
        # Ten closes strictly before formation trend upwards.
        for j in range(len(bars)-13,len(bars)-3):
            v=80+(j-(len(bars)-13));bars[j]=replace(bars[j],open=v,high=v+1,low=v-1,close=v)
        for j,(o,h,l,c) in enumerate(values,len(bars)-3):bars[j]=replace(bars[j],open=o,high=h,low=l,close=c)
        bars[-1]=replace(bars[-1],open=106,high=109,low=105,close=108)
        before=detect(replace(f,bars=tuple(bars[:-1])),.01)
        a=next(p for p in before if p['pattern_id']=='separating_lines')
        self.assertIsNone(a['confirmed_at'])
        after=detect(replace(f,bars=tuple(bars)),.01)
        b=next(p for p in after if p['pattern_id']=='separating_lines')
        self.assertEqual(a['first_known_at'],b['first_known_at'])
        self.assertEqual(b['confirmed_at'],bars[-1].close_time_ms)
        self.assertFalse(b['trade_permission']);self.assertEqual(b['role'],'DESCRIPTIVE')

    def test_retained_ladder_mat_hold_and_concealing_geometry(self):
        from market_ai.v2.pattern_research import detect_patterns
        f=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
        cases={
          'ladder_bottom':[(110,111,99,100),(108,109,97,98),(106,107,95,96),(94,101,92,93),(96,104,95,103)],
          'mat_hold':[(100,111,99,110),(112,113,108,109),(109,110,107,108),(108,109,106,107),(108,116,107,115)],
          'concealing_baby_swallow':[(110,110,100,100),(99,99,89,89),(87,90,84,85),(91,92,82,83),(92,96,91,95)]}
        for family,values in cases.items():
            for mirror in (False,True):
                if family=='concealing_baby_swallow' and mirror:continue
                rows=[replace(b,open=100,high=101,low=99,close=100.1) for b in f.bars]
                transformed=values if not mirror else [(400-o,400-l,400-h,400-c) for o,h,l,c in values]
                for j,(o,h,l,c) in enumerate(transformed,len(rows)-len(values)):rows[j]=replace(rows[j],open=o,high=h,low=l,close=c)
                r=detect_patterns(rows,tick_size=.01,**f.kwargs())
                wanted='ladder_top' if mirror and family=='ladder_bottom' else family
                self.assertIn(wanted,{p['pattern_id'] for p in r['patterns']},(family,mirror))
                flat=[replace(b,open=100,high=101,low=99,close=100.1) for b in rows]
                self.assertNotIn(wanted,{p['pattern_id'] for p in detect_patterns(flat,tick_size=.01,**f.kwargs())['patterns']})
