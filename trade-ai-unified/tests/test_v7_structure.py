import unittest
from dataclasses import replace
from fixtures import fixture,NOW
from unified_forex.market import acquire
from unified_forex.divergence import aligned,analyze as divergence
from unified_forex.structure_events import analyze
from market_ai.v2.price_action import compute_price_action


class CausalStructure(unittest.TestCase):
    def frame(self):return acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
    def test_all_divergence_directions_and_async_confirmation(self):
        f=self.frame();bars=[replace(b,open=100,high=101,low=99,close=100) for b in f.bars[:26]]
        for hidden in (False,True):
            rows=list(bars);rows[10]=replace(rows[10],low=90);rows[20]=replace(rows[20],low=95 if hidden else 85)
            values=[50]*26;values[11]=30 if hidden else 20;values[21]=20 if hidden else 30
            for mirror in (False,True):
                actual=rows if not mirror else [replace(b,open=200-b.open,high=200-b.low,low=200-b.high,close=200-b.close) for b in rows]
                v=values if not mirror else [100-x for x in values]
                frame=replace(f,bars=tuple(actual))
                events=aligned(frame,v,'independent_indicator',.01)
                self.assertEqual(len(events),1)
                e=events[0];self.assertEqual(e['kind'],'hidden' if hidden else 'regular')
                self.assertEqual(e['direction'],'bearish' if mirror else 'bullish')
                self.assertEqual(e['first_known_at'],actual[23].close_time_ms)
                self.assertEqual(aligned(replace(frame,bars=frame.bars[:23]),v[:23],'test',.01),[])
                self.assertEqual(aligned(frame,[50]*26,'flat',.01),[])
        self.assertEqual(divergence(replace(f,bars=f.bars[:20]),.01)['status'],'WARMUP')

    def test_structure_lifecycle_never_backdates_knowledge(self):
        f=self.frame();rows=list(f.bars)
        rows[210]=replace(rows[210],high=2023)
        f=replace(f,bars=tuple(rows))
        action=compute_price_action(f.bars,timeframe_ms=f.duration_ms,as_of_ms=f.as_of_ms,max_age_ms=f.duration_ms*2)
        result=analyze(f,action,.01,1)
        self.assertTrue(any(e['kind']=='BOS' for e in result['events']))
        for e in result['events']:
            self.assertLessEqual(e['origin_at'],e['first_known_at'])
            for key in ('confirmed_at','invalidated_at','expired_at','retested_at'):
                if e[key] is not None:self.assertLessEqual(e['first_known_at'],e[key])
            self.assertFalse(e['order_book_verified'])
        before=replace(f,bars=f.bars[:-1],as_of_ms=f.bars[-2].close_time_ms)
        old_action=compute_price_action(before.bars,timeframe_ms=f.duration_ms,as_of_ms=before.as_of_ms,max_age_ms=f.duration_ms*2)
        old=analyze(before,old_action,.01,1)
        ids={e['event_id']:e for e in old['events']}
        for e in result['events']:
            if e['event_id'] in ids:self.assertEqual(e['first_known_at'],ids[e['event_id']]['first_known_at'])

    def test_descriptive_correlated_evidence_has_no_directional_authority(self):
        from unified_forex.confluence import Observation,combine
        a=Observation('pattern','event','pattern','bullish',100,True,0,'M15',100,'v1')
        b=Observation('vol','event2','volatility','bullish',100,True,0,'H1',100,'v1')
        self.assertEqual(combine([a,b],as_of=100)['direction'],'neutral')
        future=replace(a,confirmation_at=101)
        self.assertEqual(combine([future],as_of=100)['rejections'][0]['reason'],'future_or_unconfirmed')
        x=replace(a,category='structure',related_event_id='underlying')
        y=replace(x,event_id='H1-other',timeframe='H1')
        self.assertEqual(combine([x,y],as_of=100)['event_deduplicated_count'],1)
        # A stronger descriptive label on one event cannot hide its opposite
        # authoritative structure/trend evidence before the veto is evaluated.
        rows=[replace(a,category='trend',strength=10),replace(a,strength=99),
              replace(a,event_id='opposite',category='structure',direction='bearish',strength=10)]
        self.assertTrue(combine(rows,as_of=100)['conflict_veto'])
