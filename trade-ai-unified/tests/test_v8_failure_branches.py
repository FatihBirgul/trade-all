import unittest,json
from dataclasses import replace
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from unittest.mock import Mock,patch
from hashlib import sha256
from fixtures import fixture,NOW
from unified_forex.confluence import Observation,combine
from unified_forex.macro import RevisionCalendar,information_context
from unified_forex.services import Alerts
from unified_forex.engine import AnalysisEngine
from unified_forex.structure_ledger import StructureLedger,LedgerStore
from forex.contracts import canonical


class AdversarialFailures(unittest.TestCase):
    def test_invalid_confirmation_related_event_and_expired_state(self):
        base=dict(source='test',event_id='same',category='structure',direction='bullish',strength=20.,confirmed=True,
                  age_bars=0,timeframe='M15',known_at=100,algorithm_version='fixture')
        for changes in ({'confirmation_at':True},{'confirmation_at':99},{'related_event_id':True},{'state':'FORGED'}):
            with self.assertRaises(ValueError):Observation(**{**base,**changes})
        for state in ('INVALIDATED','EXPIRED','CANDIDATE'):
            self.assertFalse(combine([Observation(**{**base,'state':state})],as_of=100)['directional_context'])
        self.assertIn('same',combine([Observation(**{**base,'expires_at':100})],as_of=100)['rejected_events'])
        with self.assertRaises(ValueError):combine([],as_of=True)
    def test_equal_revision_conflict_is_not_hidden_by_later_retrieval(self):
        now=datetime.fromtimestamp(NOW,timezone.utc)
        row=dict(event_id='fixture',source='synthetic',url='https://example.org/data',currency='USD',event_type='CPI',importance='HIGH',
            release_at=now-timedelta(hours=2),published_at=now-timedelta(hours=1),retrieved_at=now-timedelta(minutes=30),actual=1.)
        bad={**row,'actual':2.,'retrieved_at':now-timedelta(minutes=20)}
        p=RevisionCalendar([row,bad])
        with self.assertRaises(ValueError):p.selected(now)
        self.assertEqual(information_context(p,as_of=now)['data_status'],'DATA_UNAVAILABLE')
    def test_structure_alert_event_identity_ignores_later_tick_snapshot(self):
        p=fixture();p.data['XAUUSD']['candles']['M15'][210]['high']=2023
        a=AnalysisEngine().analyze(p,'XAUUSD',now=NOW).model_dump()
        alerts=Alerts(cooldown_seconds=1);when=datetime.fromtimestamp(NOW,timezone.utc)
        first=alerts.evaluate(a,now=when)
        self.assertIn('STRUCTURE_CHANGE',{e['type'] for e in first})
        a['snapshot_id']='new-tick-same-closed-event'
        second=alerts.evaluate(a,now=when+timedelta(seconds=2))
        self.assertNotIn('STRUCTURE_CHANGE',{e['type'] for e in second})
    def test_checkpoint_invalid_envelopes_and_recomputed_hash_do_not_bypass_schema(self):
        from test_v8_structure_ledger import HistoricalFVG
        f=HistoricalFVG().frame();ledger=StructureLedger();ledger.consume(f,.01)
        with self.assertRaises(ValueError):StructureLedger.restore({})
        with self.assertRaises(ValueError):LedgerStore(capacity=0)
        original=ledger.checkpoint()
        for mutate in (lambda b:b.update(processed=-1),lambda b:b['events'][0].update(low=-1),
                       lambda b:b['events'][0].update(fill_fraction=2),lambda b:b['events'][0].update(algorithm_version='forged')):
            p=deepcopy(original);mutate(p['body']);p['sha256']=sha256(canonical(p['body']).encode()).hexdigest()
            with self.assertRaises(ValueError):StructureLedger.restore(p)
