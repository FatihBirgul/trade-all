import unittest
from dataclasses import replace
from copy import deepcopy
from fixtures import fixture,NOW
from unified_forex.market import acquire
from unified_forex.structure_ledger import StructureLedger,LedgerStore


class HistoricalFVG(unittest.TestCase):
    def frame(self):
        f=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
        rows=[replace(b,open=100,high=101,low=99,close=100) for b in f.bars]
        values=[(100,101,99,100),(100,105,99.5,104.5),(105,107,104,106),
                (105,106,102.5,105),(103,105,100.5,103)]
        for i,(o,h,l,c) in enumerate(values,len(rows)-5):rows[i]=replace(rows[i],open=o,high=h,low=l,close=c)
        return replace(f,bars=tuple(rows))
    def prefix(self,f,n):return replace(f,bars=f.bars[:n],as_of_ms=f.bars[n-1].close_time_ms)
    def test_creation_partial_mitigation_and_replay_restart(self):
        f=self.frame();ledger=StructureLedger()
        before=ledger.consume(self.prefix(f,len(f.bars)-3),.01)
        self.assertEqual(before['events'],[])
        created=ledger.consume(self.prefix(f,len(f.bars)-2),.01)['events'][-1]
        self.assertEqual(created['state'],'CONFIRMED');self.assertEqual(created['first_known_at'],f.bars[-3].close_time_ms)
        partial=ledger.consume(self.prefix(f,len(f.bars)-1),.01)['events'][-1]
        self.assertEqual(partial['state'],'PARTIALLY_FILLED');self.assertAlmostEqual(partial['fill_fraction'],.5)
        restored=StructureLedger.restore(ledger.checkpoint())
        final=ledger.consume(f,.01);self.assertEqual(final,restored.consume(f,.01))
        self.assertEqual(final['events'][-1]['state'],'MITIGATED')
        self.assertEqual(final,StructureLedger().consume(f,.01))
        self.assertEqual(final,ledger.consume(f,.01))
    def test_invalidated_expired_and_bounded_identity(self):
        f=self.frame();rows=list(f.bars);rows[-2]=replace(rows[-2],open=102,high=103,low=99,close=100)
        invalid=StructureLedger().consume(replace(f,bars=tuple(rows)),.01)
        self.assertEqual(invalid['events'][-1]['state'],'INVALIDATED')
        for i in (-2,-1):rows[i]=replace(rows[i],open=106,high=107,low=105,close=106)
        expired=StructureLedger(expiry_bars=1).consume(replace(f,bars=tuple(rows)),.01)
        self.assertEqual(expired['events'][-1]['state'],'EXPIRED')
        ledger=StructureLedger();ledger.consume(f,.01)
        changed=list(f.bars);changed[-1]=replace(changed[-1],close=103.5)
        with self.assertRaises(ValueError):ledger.consume(replace(f,bars=tuple(changed)),.01)
        bad=deepcopy(ledger.checkpoint());bad['body']['processed']+=1
        with self.assertRaises(ValueError):StructureLedger.restore(bad)
        p=fixture();q=fixture();store=LedgerStore(capacity=1)
        self.assertIsNot(store.get(p,'XAUUSD','M15'),store.get(q,'XAUUSD','M15'))
    def test_rolling_window_preserves_prior_gap_and_no_future_transition(self):
        f=self.frame();ledger=StructureLedger();n=len(f.bars)-2
        first=ledger.consume(self.prefix(f,n),.01)['events'][-1]
        rolling=replace(f,bars=f.bars[-16:-1],as_of_ms=f.bars[-2].close_time_ms)
        after=ledger.consume(rolling,.01)['events'][-1]
        self.assertEqual(first['event_id'],after['event_id'])
        self.assertEqual(first['first_known_at'],after['first_known_at'])
        self.assertIsNone(after['terminal_at'])
    def test_older_request_cannot_observe_newer_shared_ledger_states(self):
        f=self.frame();ledger=StructureLedger();ledger.consume(f,.01)
        old=self.prefix(f,len(f.bars)-2)
        with self.assertRaisesRegex(ValueError,'ahead of snapshot'):ledger.consume(old,.01)
