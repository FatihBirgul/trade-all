from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
OWNER='a'*64;OTHER='b'*64;TOKEN='fixture-notification-controls-32'
class NotificationControlTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.now=1800000000000;self.path=Path(self.tmp.name)/'fixture.sqlite'
        self.app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:self.now,domain_journal=True)
        self.c=TestClient(self.app,headers={'Authorization':'Bearer '+TOKEN,'X-V2-Notification-Owner':OWNER,'X-V2-Recipient-Expires':str(self.now+86400000)})
        self.addCleanup(self.c.close);self.url='/api/v2/portfolios/MANUAL/notification-preferences'
    def write(self,**fields):
        return self.c.post(self.url,json={'idempotency_key':'control-change-one','expected_revision':0,'enabled':True,'categories':{'analysis':True,'source':True,'risk':False,'system':False},**fields})
    def test_read_default_has_no_writes_or_delivery_claim(self):
        before=self.path.read_bytes();r=self.c.get(self.url);self.assertEqual(r.status_code,200,r.text)
        self.assertFalse(r.json()['enabled']);self.assertEqual(r.json()['push_status'],'NOT_CONFIGURED');self.assertEqual(before,self.path.read_bytes())
        self.assertEqual(self.c.get(self.url,headers={'X-V2-Notification-Owner':''}).status_code,403)
    def test_revisions_replay_conflict_ownership_and_account_isolation(self):
        r=self.write();self.assertEqual(r.status_code,200,r.text);a=r.json();self.assertEqual(self.write().json(),a)
        self.assertEqual(self.write(idempotency_key='conflicting-control').status_code,409)
        self.assertEqual(self.c.get(self.url,headers={'X-V2-Notification-Owner':OTHER}).json()['revision'],0)
        self.assertEqual(self.c.get(self.url.replace('MANUAL','AUTO')).json()['revision'],0)
        self.assertNotIn(OWNER,r.text)
        from market_ai.v2.paper_audit import audit_database
        report=audit_database(self.path,require_domain=True);self.assertEqual(report['checks']['CORRUPT'],0,report);self.assertEqual(report['checks']['MISMATCH'],0,report)
    def test_revoke_replace_and_expiry_require_explicit_new_recipient(self):
        a=self.write().json();old=a['recipient_id']
        b=self.write(idempotency_key='revoke-control-one',expected_revision=1,recipient_action='revoke').json();self.assertEqual(b['recipient_status'],'revoked')
        c=self.write(idempotency_key='keep-control-revoked',expected_revision=2).json();self.assertEqual(c['recipient_status'],'revoked')
        d=self.write(idempotency_key='replace-control-new',expected_revision=3,recipient_action='replace').json();self.assertNotEqual(old,d['recipient_id'])
        self.now+=86400001;self.assertEqual(self.c.get(self.url).status_code,403)
        self.c.headers['X-V2-Recipient-Expires']=str(self.now+86400000)
        self.assertEqual(self.c.get(self.url).json()['recipient_status'],'expired')
    def test_rejects_secrets_unknown_fields_and_non_strict_types(self):
        for values in ({'enabled':'true'},{'device_token':'fixture-must-not-store'},{'owner_id':OTHER},{'expected_revision':True}):self.assertEqual(self.write(**values).status_code,422)
        self.assertEqual(self.c.get(self.url).json()['revision'],0)
        self.assertNotIn(b'fixture-must-not-store',self.path.read_bytes())
    def test_write_error_rolls_back_revision_and_receipt(self):
        import sqlite3
        db=self.app.state.v2.db;original=db.remember
        with patch.object(db,'remember',side_effect=sqlite3.OperationalError('controlled fixture write failure')):self.assertEqual(self.write().status_code,503)
        self.assertEqual(self.c.get(self.url).json()['revision'],0);self.assertEqual(self.write().status_code,200)
    def test_dispatcher_requires_explicit_authority_before_schema_writes(self):
        from market_ai.v2.notification_delivery import NotificationDispatcher
        from tests.test_v2_notification_delivery import Adapter
        before=self.path.read_bytes()
        with self.assertRaises(ValueError):NotificationDispatcher(self.app.state.v2.db,Adapter())
        self.assertEqual(before,self.path.read_bytes())
    def test_owned_category_account_recipient_and_revoked_session_guards(self):
        from market_ai.v2.notification_delivery import NotificationDispatcher
        from tests.test_v2_notification_delivery import Adapter
        control=self.app.state.v2.notification_controls;db=self.app.state.v2.db;adapter=Adapter();a=self.write().json()
        authority=control.authorizer(owner=OWNER,account='MANUAL',recipient_id=a['recipient_id'],session_valid=lambda:True)
        with db.transaction() as c:
            self.app.state.v2.scanner._notify(c,'owned-notice','analysis',{'portfolio_id':'MANUAL'})
            self.app.state.v2.scanner._notify(c,'foreign-notice','analysis',{'portfolio_id':'AUTO'})
            self.app.state.v2.scanner._notify(c,'risk-notice','risk',{'portfolio_id':'MANUAL'})
        d=NotificationDispatcher(db,adapter,clock=lambda:self.now,authorization=authority)
        r=d.tick();self.assertEqual(r['accepted'],1);self.assertEqual(r['preference_blocked'],2);self.assertEqual(len(adapter.calls),1)
        with db.transaction() as c:self.app.state.v2.scanner._notify(c,'revoked-session-notice','analysis',{'portfolio_id':'MANUAL'})
        revoked=control.authorizer(owner=OWNER,account='MANUAL',recipient_id=a['recipient_id'],session_valid=lambda:False)
        self.assertEqual(NotificationDispatcher(db,adapter,clock=lambda:self.now,authorization=revoked).tick()['preference_blocked'],1)
        self.assertEqual(len(adapter.calls),1)
    def test_revocation_between_claim_and_send_blocks_adapter(self):
        from market_ai.v2.notification_delivery import NotificationDispatcher
        from tests.test_v2_notification_delivery import Adapter
        a=self.write().json();db=self.app.state.v2.db;adapter=Adapter();calls=[]
        authority=self.app.state.v2.notification_controls.authorizer(owner=OWNER,account='MANUAL',recipient_id=a['recipient_id'],session_valid=lambda:len(calls)<2)
        def guarded(c,n,t):calls.append(1);return authority(c,n,t)
        with db.transaction() as c:self.app.state.v2.scanner._notify(c,'claim-then-revoke','analysis',{'portfolio_id':'MANUAL'})
        r=NotificationDispatcher(db,adapter,clock=lambda:self.now,authorization=guarded).tick()
        self.assertEqual(r['preference_blocked'],1);self.assertEqual(adapter.calls,[])
    def test_preferences_restart_backup_and_retired_recipient_rejection(self):
        from scripts.backup_v2 import copy_database
        a=self.write().json();old=a['recipient_id'];self.write(idempotency_key='replace-old-recipient',expected_revision=1,recipient_action='replace')
        target=self.path.with_name('copy.sqlite');copy_database(self.path,target)
        app=create_app(target,mode='fixture',token=TOKEN,clock=lambda:self.now)
        control=app.state.v2.notification_controls
        with app.state.v2.db.transaction() as c:
            self.assertFalse(control.authorizer(owner=OWNER,account='MANUAL',recipient_id=old,session_valid=lambda:True)(c,{'kind':'analysis','details':{'portfolio_id':'MANUAL'}},self.now))
        self.assertEqual(control.read('MANUAL',OWNER,self.now+86400000).revision,2)
    def test_truthy_non_boolean_authority_never_sends(self):
        from market_ai.v2.notification_delivery import NotificationDispatcher
        from tests.test_v2_notification_delivery import Adapter
        db=self.app.state.v2.db;adapter=Adapter()
        with db.transaction() as c:self.app.state.v2.scanner._notify(c,'bad-authority','analysis',{'portfolio_id':'MANUAL'})
        r=NotificationDispatcher(db,adapter,clock=lambda:self.now,authorization=lambda c,n,t:'yes').tick()
        self.assertEqual(r['preference_blocked'],1);self.assertEqual(adapter.calls,[])
    def test_global_fixture_rate_budget_is_persistent_and_bounded(self):
        from market_ai.v2.notification_delivery import NotificationDispatcher
        from tests.test_v2_notification_delivery import Adapter
        db=self.app.state.v2.db;adapter=Adapter()
        with db.transaction() as c:
            for i in range(61):self.app.state.v2.scanner._notify(c,'rate-notice-'+str(i),'analysis',{'portfolio_id':'MANUAL'})
        def dispatcher():return NotificationDispatcher(db,adapter,clock=lambda:self.now,authorization=lambda c,n,t:True)
        for _ in range(7):r=dispatcher().tick()
        self.assertEqual(len(adapter.calls),60);self.assertEqual(r['rate_limited'],1)
        self.now+=60001;self.assertEqual(dispatcher().tick()['accepted'],1)
    def test_preemptive_revoke_cannot_be_implicitly_undone(self):
        a=self.write(enabled=False,recipient_action='revoke').json();self.assertEqual(a['recipient_status'],'revoked')
        b=self.write(idempotency_key='keep-after-initial-revoke',expected_revision=1).json();self.assertIsNone(b['recipient_id']);self.assertEqual(b['recipient_status'],'revoked')
    def test_live_transport_without_provider_device_configuration_is_refused(self):
        from market_ai.v2.notification_delivery import NotificationDispatcher
        from tests.test_v2_notification_delivery import Adapter
        db=self.app.state.v2.db;adapter=Adapter();adapter.mode='live';before=self.path.read_bytes()
        with patch.object(db,'mode','live'):
            with self.assertRaises(ValueError):NotificationDispatcher(db,adapter,authorization=lambda c,n,t:True)
        self.assertEqual(before,self.path.read_bytes())
