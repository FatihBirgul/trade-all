import unittest
from dataclasses import replace
from fixtures import fixture,NOW
from unified_forex.market import acquire
from unified_forex.pattern_lab import randomized_report
from unified_forex.candle_extensions import detect as candles
from unified_forex.chart_geometry import detect as charts,candidates
import test_v7_charts as chart_fixtures
from test_v7_candles import CASES


class PatternAdversarial(unittest.TestCase):
    def frame(self):return acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
    def test_malformed_future_unfinished_and_missing_bar_fail_closed(self):
        f=self.frame();rows=f.bars
        variants=[rows[:-2]+rows[-1:],rows[:-1]+(replace(rows[-1],is_final=False),),
                  rows[:-1]+(replace(rows[-1],high=float('nan')),),rows[:-1]+(replace(rows[-1],source='wrong-source'),)]
        for bars in variants:
            bad=replace(f,bars=bars)
            self.assertEqual(candles(bad,.01),[]);self.assertEqual(charts(bad,.01),[])
        future=replace(f,as_of_ms=rows[-1].close_time_ms-1)
        self.assertEqual(candles(future,.01),[]);self.assertEqual(charts(future,.01),[])
    def test_chart_translation_scale_noise_and_geometry_prefix(self):
        builder=chart_fixtures.ChartGeometry()
        for family,hs,ls in [('rectangle',0,0),('channel',.2,.2),('ascending_triangle',0,.4),('descending_triangle',-.4,0),('symmetrical_triangle',-.2,.2),('rising_wedge',.1,.5),('falling_wedge',-.5,-.1)]:
            b,h,l=builder.channel(hs,ls)
            for scale,offset in [(1,500),(1e-3,0),(10,1000)]:
                from types import SimpleNamespace as B
                rows=[B(open=x.open*scale+offset,high=x.high*scale+offset,low=x.low*scale+offset,close=x.close*scale+offset) for x in b]
                hp=[(i,p*scale+offset) for i,p in h];lp=[(i,p*scale+offset) for i,p in l]
                self.assertIn(family,{p['family'] for p in candidates(rows,hp,lp,.01*scale)},family)
            # Tiny interior-close perturbation does not change frozen boundaries.
            b[30].close+=.000001
            self.assertIn(family,{p['family'] for p in candidates(b,h,l,.01)})
    def test_all_candles_translation_and_similar_invalid_final_body(self):
        from unified_forex.candle_extensions import geometry
        from types import SimpleNamespace as B
        for family,values in CASES.items():
            rows=[B(open=o+1000,high=h+1000,low=l+1000,close=c+1000) for o,h,l,c in values]
            self.assertIn(family,{p[0] for p in geometry(rows,.01)})
            # Destroy the decisive final geometry without changing earlier bars.
            rows[-1]=B(open=5000,high=5000,low=5000,close=5000)
            self.assertNotIn(family,{p[0] for p in geometry(rows,.01)})
    def test_seeded_random_diagnostics_are_reproducible_not_market_metrics(self):
        f=self.frame();a=randomized_report(f,paths=3,seed=81)
        self.assertEqual(a,randomized_report(f,paths=3,seed=81))
        self.assertIsNone(a['market_false_positive_rate'])
        self.assertTrue(all(0<=v<=1 for v in a['detection_rates'].values()))
