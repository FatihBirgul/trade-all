import unittest
from dataclasses import replace
from fixtures import fixture,NOW
from unified_forex.market import acquire
from unified_forex.structure_events import analyze
from unified_forex.confluence import Observation,combine


class V8CausalAudit(unittest.TestCase):
    def test_later_atr_cannot_reclassify_existing_swings(self):
        f=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
        rows=list(f.bars)
        for i,v in ((190,2021),(200,2022)):rows[i]=replace(rows[i],high=v)
        f=replace(f,bars=tuple(rows));action={'fvg':{'active_gaps':[]},'liquidity_sweep':{}}
        a=analyze(f,action,.01,.1);b=analyze(f,action,.01,100)
        self.assertEqual([(e['kind'],e['origin_at']) for e in a['events']],[(e['kind'],e['origin_at']) for e in b['events']])
    def test_expired_evidence_cannot_veto_a_fresh_setup(self):
        old=Observation('old','old-event','structure','bearish',90,True,100,'M15',100,'test')
        new=Observation('new','new-event','trend','bullish',20,True,0,'M15',1000,'test')
        r=combine([old,new],as_of=1000)
        self.assertFalse(r['conflict_veto'])
        self.assertIn('old-event',r['rejected_events'])
