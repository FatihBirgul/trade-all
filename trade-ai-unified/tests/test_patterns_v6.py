import unittest
from dataclasses import replace
from fixtures import fixture,NOW
from unified_forex.market import acquire
from unified_forex.patterns import modified_hikkake,analyze


class CausalPatterns(unittest.TestCase):
    def frame(self):return acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
    def formation(self):
        f=self.frame();rows=list(f.bars)
        values=[(100,110,90,100),(99,106,94,100),(96,104,96,97),(97,103,95,96),(100,108,99,107)]
        for i,(o,h,l,c) in enumerate(values,len(rows)-5):rows[i]=replace(rows[i],open=o,high=h,low=l,close=c)
        return replace(f,bars=tuple(rows))
    def test_modified_hikkake_confirmation_and_first_knowledge(self):
        f=self.formation();before=modified_hikkake(replace(f,bars=f.bars[:-1]))
        p=next(p for p in before if p['pattern_id']=='modified_hikkake')
        self.assertIsNone(p['confirmed_at'])
        known=p['first_known_at'];after=modified_hikkake(f)
        p=next(p for p in after if p['formed_at']==known)
        self.assertEqual(p['confirmed_at'],f.bars[-1].close_time_ms)
        self.assertEqual(p['minimum_candles'],4)
        self.assertFalse(p['trade_permission'])
    def test_mirror_and_bad_condition_are_not_false_positives(self):
        f=self.formation()
        mirrored=replace(f,bars=tuple(replace(b,open=4000-b.open,high=4000-b.low,low=4000-b.high,close=4000-b.close) for b in f.bars))
        self.assertIn('bearish',{p['direction'] for p in modified_hikkake(mirrored)})
        rows=list(f.bars);rows[-3]=replace(rows[-3],close=100)
        self.assertEqual(modified_hikkake(replace(f,bars=tuple(rows))),[])
    def test_real_v2_patterns_keep_versions_and_invalidation(self):
        f=self.frame()
        candles,charts=analyze(f,{'atr14':1},.01)
        self.assertEqual(candles['status'],'available')
        for p in candles['patterns']:
            self.assertIn('invalidation',p);self.assertIn('minimum_candles',p)
        self.assertIn('bull_flag',charts['geometry_catalog'])
        self.assertEqual(charts['validation_status'],'PARTIAL_FAMILY_VALIDATION')
