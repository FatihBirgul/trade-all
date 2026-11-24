import unittest
from types import SimpleNamespace as B
from dataclasses import replace
from fixtures import fixture,NOW
from unified_forex.market import acquire
from unified_forex.chart_geometry import candidates,detect


class ChartGeometry(unittest.TestCase):
    def channel(self,hs,ls,upper=120,lower=100,pole=0):
        bars=[B(open=110,high=111,low=109,close=110) for _ in range(64)]
        start,end=24,48
        hp=[(i,upper+hs*(i-start)) for i in (24,36,48)]
        lp=[(i,lower+ls*(i-start)) for i in (28,40,52)]
        for i in range(24,53):
            u=upper+hs*(i-start);d=lower+ls*(i-start)
            bars[i]=B(open=(u+d)/2,high=u,low=d,close=(u+d)/2)
        for i in range(16,24):
            v=110+pole*(i-16)/7;bars[i]=B(open=v,high=v+.1,low=v-.1,close=v)
        return bars,hp,lp

    def test_line_families_and_flat_random_range_does_not_form_flag(self):
        cases=[('rectangle',0,0),('channel',.2,.2),('ascending_triangle',0,.4),
               ('descending_triangle',-.4,0),('symmetrical_triangle',-.2,.2),
               ('rising_wedge',.1,.5),('falling_wedge',-.5,-.1)]
        for family,hs,ls in cases:
            with self.subTest(family=family):
                b,h,l=self.channel(hs,ls)
                result=candidates(b,h,l,.01)
                self.assertIn(family,{p['family'] for p in result})
                self.assertNotIn(family,{p['family'] for p in candidates(b,h[:1],l[:1],.01)})
        b,h,l=self.channel(0,0)
        self.assertFalse({'bull_flag','bear_flag','pennant'}&{p['family'] for p in candidates(b,h,l,.01)})
        for pole,hs,ls,wanted in [(60,-.2,-.2,'bull_flag'),(-60,.2,.2,'bear_flag'),(60,-.2,.2,'pennant')]:
            b,h,l=self.channel(hs,ls,pole=pole)
            self.assertIn(wanted,{p['family'] for p in candidates(b,h,l,.01)})

    def test_neckline_reversal_geometry_and_mirrors(self):
        bars=[B(open=110,high=111,low=109,close=110) for _ in range(64)]
        cases=[('double_top',[(12,120),(24,120)],[(18,100)]),
               ('head_and_shoulders',[(12,115),(24,130),(36,115)],[(18,100),(30,100)])]
        for family,h,l in cases:
            self.assertIn(family,{p['family'] for p in candidates(bars,h,l,.01)})
            mirror=[B(open=400-b.open,high=400-b.low,low=400-b.high,close=400-b.close) for b in bars]
            mh=[(i,400-p) for i,p in l];ml=[(i,400-p) for i,p in h]
            wanted='double_bottom' if family=='double_top' else 'inverse_head_and_shoulders'
            self.assertIn(wanted,{p['family'] for p in candidates(mirror,mh,ml,.01)})
            self.assertNotIn(family,{p['family'] for p in candidates(bars,h,[],.01)})

    def test_rounding_curvature_rejects_linear_noise(self):
        for sign,wanted in [(1,'rounding_bottom'),(-1,'rounding_top')]:
            bars=[B(close=100+sign*.02*(i-15.5)**2) for i in range(32)]
            bars=[B(close=100)]*8+bars
            self.assertIn(wanted,{p['family'] for p in candidates(bars,[],[],.01)})
        self.assertEqual(candidates([B(close=100+i) for i in range(40)],[],[],.01),[])

    def test_confirmed_pivot_first_knowledge_and_two_close_breakout(self):
        f=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
        rows=[]
        # Independent triangular wave, repeated equal highs and lows.
        for i,b in enumerate(f.bars):
            v=110+8*(1-abs((i%12)-6)/3)
            rows.append(replace(b,open=v,high=v+.1,low=v-.1,close=v))
        prefix=replace(f,bars=tuple(rows[:-2]))
        a=detect(prefix,.01)
        self.assertTrue(a)
        self.assertTrue(all(p['first_known_at']>=rows[max(p['pivot_indices'])+3].close_time_ms for p in a))
        last=rows[-3]
        rows[-2]=replace(rows[-2],open=130,high=132,low=129,close=131)
        rows[-1]=replace(rows[-1],open=131,high=133,low=130,close=132)
        b=detect(replace(f,bars=tuple(rows)),.01)
        before={p['event_id']:p for p in a}
        common=[p for p in b if p['event_id'] in before]
        self.assertTrue(common)
        for p in common:
            self.assertEqual(p['first_known_at'],before[p['event_id']]['first_known_at'])
            if p['confirmed_at']:self.assertGreater(p['confirmed_at'],p['first_known_at'])
            self.assertFalse(p['trade_permission'])
