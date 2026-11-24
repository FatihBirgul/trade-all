"""Opt-in source transitions; old follow behavior remains unchanged."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from tests.test_v2_analysis_follow import Switchable
from market_ai.v2.api import create_app
TOKEN='fixture-follow-source-policy-32'
class FollowSourcePolicyTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'follow.sqlite';self.now=1792584000000
        self.provider=Switchable();self.provider.offline=False
        self.app=create_app(self.path,mode='fixture',token=TOKEN,provider=self.provider,clock=lambda:self.now,domain_journal=True)
        self.client=TestClient(self.app,headers={'Authorization':'Bearer '+TOKEN});self.addCleanup(self.client.close)
        a=self.client.post('/api/v2/analyze',json={'idempotency_key':'source-policy-origin','data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1m'}).json()
        t=self.client.post('/api/v2/analysis-tracking',json={'analysis_id':a['analysis_id']}).json();self.key=t['tracking_id'];self.url='/api/v2/analysis-tracking/'+self.key+'/notification-policy'
    def enable(self):
        r=self.client.post(self.url,json={'notify_source_changes':True});self.assertEqual(r.status_code,200,r.text)
    def notes(self):return self.client.get('/api/v2/notifications').json()
    def test_policy_is_explicit_and_no_alert_when_disabled(self):
        r=self.client.get(self.url);self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['notify_source_changes'])
        self.provider.offline=True;self.app.state.tracking.tick();self.assertEqual(self.notes(),[])
    def test_outage_dedup_restart_recovery_and_expiry(self):
        self.enable();self.provider.offline=True;self.app.state.tracking.tick()
        notes=self.notes();self.assertEqual(len(notes),1);self.assertEqual(notes[0]['details']['change_kind'],'source_unavailable')
        self.assertEqual(notes[0]['details']['expires_at_ms'],self.now+900000)
        self.now+=60000;self.app.state.tracking.tick();self.assertEqual(len(self.notes()),1)
        self.app=create_app(self.path,mode='fixture',token=TOKEN,provider=self.provider,clock=lambda:self.now)
        self.now+=900000;self.app.state.tracking.tick();self.assertEqual(len(self.notes()),1)
        self.provider.offline=False;self.now+=900000;self.app.state.tracking.tick()
        self.assertEqual(len(self.notes()),2)
        self.assertEqual(self.notes()[0]['details']['change_kind'],'source_recovered')
        self.now+=60000;self.app.state.tracking.tick();self.assertEqual(len(self.notes()),2)
        self.assertFalse(self.app.state.tracking.get(self.key).worker_running)
        for account in ('AUTO','MANUAL'):self.assertEqual(self.client.get('/api/v2/portfolios/'+account+'/orders').json(),[])
    def test_outbox_failure_does_not_consume_transition(self):
        import sqlite3
        self.enable();self.provider.offline=True
        with patch.object(self.app.state.v2.scanner,'_notify',side_effect=sqlite3.OperationalError('fixture outbox failure')):
            with self.assertRaises(sqlite3.OperationalError):self.app.state.tracking.tick()
        self.assertEqual(self.notes(),[]);self.now+=60000;self.app.state.tracking.tick()
        self.assertEqual(len(self.notes()),1)
