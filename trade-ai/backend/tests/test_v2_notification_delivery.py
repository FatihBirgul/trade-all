"""Disabled-by-default transport foundation; fake acceptance is not delivery."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from market_ai.v2.api import create_runtime
from market_ai.v2.notification_delivery import NotificationDispatcher,AdapterResult
TOKEN='fixture-notification-dispatch-32'
class Adapter:
    mode='fixture';supports_idempotency=True
    def __init__(self):self.calls=[];self.receipts={};self.fail=False;self.lose=False
    def send(self,notification,*,idempotency_key,timeout_seconds):
        self.calls.append(idempotency_key)
        if self.fail:raise TimeoutError('fixture transport timeout')
        self.receipts.setdefault(idempotency_key,'fixture-receipt')
        if self.lose:self.lose=False;raise TimeoutError('fixture lost acknowledgement')
        return AdapterResult('accepted','fixture-receipt')
class NotificationDeliveryTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.now=1800000000000
        self.runtime=create_runtime(Path(self.tmp.name)/'fixture.sqlite',mode='fixture',token=TOKEN,clock=lambda:self.now,domain_journal=True)
        self.db=self.runtime.db;self.adapter=Adapter()
        with self.db.transaction() as c:self.runtime.scanner._notify(c,'fixture-notice','analysis',{'portfolio_id':'MANUAL','expires_at_ms':self.now+900000})
    def dispatcher(self):return NotificationDispatcher(self.db,self.adapter,clock=lambda:self.now,authorization=lambda c,n,t:True)
    def test_default_has_no_sender_no_writes_and_no_delivery_claim(self):
        before=self.db.path.read_bytes();r=NotificationDispatcher(self.db,clock=lambda:self.now).tick()
        self.assertEqual(r['status'],'not_configured');self.assertEqual(before,self.db.path.read_bytes())
    def test_accepted_is_not_delivered_and_restart_does_not_resend(self):
        d=self.dispatcher();self.assertEqual(d.tick()['accepted'],1);self.assertEqual(self.dispatcher().tick()['accepted'],0)
        self.assertEqual(len(self.adapter.calls),1)
        with self.db.transaction() as c:
            self.assertEqual(self.db.get(c,'notifications','fixture-notice')['delivery_status'],'pending')
            rows=self.db.rows(c,'notification_delivery_attempts');self.assertTrue(all(r['outcome']!='delivered' for r in rows))
        from market_ai.v2.paper_audit import audit_database
        report=audit_database(self.db.path,require_domain=True);self.assertEqual(report['checks']['CORRUPT'],0,report);self.assertEqual(report['checks']['MISMATCH'],0,report)
    def test_retry_backoff_and_lost_ack_use_same_provider_key(self):
        d=self.dispatcher();self.adapter.lose=True;self.assertEqual(d.tick()['retryable'],1)
        self.assertEqual(d.tick()['accepted'],0);self.now+=5000
        self.assertEqual(self.dispatcher().tick()['accepted'],1)
        self.assertEqual(len(self.adapter.receipts),1);self.assertEqual(self.adapter.calls[0],self.adapter.calls[1])
    def test_expiry_blocks_sender_and_retains_outbox(self):
        self.now+=900001;self.assertEqual(self.dispatcher().tick()['expired'],1);self.assertEqual(self.adapter.calls,[])
        with self.db.transaction() as c:self.assertIsNotNone(self.db.get(c,'notifications','fixture-notice'))
    def test_parallel_workers_claim_once(self):
        d=self.dispatcher();other=self.dispatcher()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda x:x.tick(),(d,other)))
        self.assertEqual(len(self.adapter.calls),1)
    def test_receipt_failure_recovery_keeps_remote_idempotency(self):
        import sqlite3
        d=self.dispatcher()
        with patch.object(d,'_finish',side_effect=sqlite3.OperationalError('fixture receipt disk failure')):
            with self.assertRaises(sqlite3.OperationalError):d.tick()
        self.now+=30001;self.assertEqual(self.dispatcher().tick()['accepted'],1)
        self.assertEqual(len(self.adapter.receipts),1);self.assertEqual(len(self.adapter.calls),2)
    def test_invalid_or_cross_mode_adapter_rejected_before_writes(self):
        before=self.db.path.read_bytes();self.adapter.mode='live'
        with self.assertRaises(ValueError):self.dispatcher()
        self.assertEqual(before,self.db.path.read_bytes())
        with self.assertRaises(ValueError):AdapterResult('delivered','fixture')
    def test_retry_budget_is_finite_and_permanent_outcomes_stop(self):
        self.adapter.fail=True;d=self.dispatcher()
        for i in range(5):d.tick();self.now+=5000*2**i
        self.now+=300000;d.tick();self.assertEqual(len(self.adapter.calls),5)
    def test_auditor_rejects_forged_delivered_fact_even_with_valid_checksum(self):
        from market_ai.v2.paper_audit import audit_database
        from market_ai.v2.product_db import fingerprint
        self.dispatcher()
        with self.db.transaction() as c:
            notice=self.db.get(c,'notifications','fixture-notice')
            body={'schema_version':1,'notification_id':'fixture-notice','outbox_hash':fingerprint(notice),'attempt':1,'outcome':'delivered','time_ms':self.now,'data_mode':'fixture','receipt_ref':'fixture','error_code':'','idempotency_key':'notification:fixture-notice'}
            key=fingerprint({'notification':'fixture-notice','attempt':1,'outcome':'delivered'})
            self.db.put(c,'notification_delivery_attempts',key,body)
        report=audit_database(self.db.path,require_domain=True);self.assertGreater(report['checks']['CORRUPT'],0,report)
    def test_invalid_expiry_is_not_sent_or_falsely_called_expired(self):
        with self.db.transaction() as c:self.runtime.scanner._notify(c,'invalid-expiry','analysis',{'expires_at_ms':'not-a-time'})
        r=self.dispatcher().tick();self.assertEqual(r['invalid_source'],1);self.assertEqual(r['expired'],0)
        self.assertEqual(len(self.adapter.calls),1)
    def test_revoked_follow_preference_suppresses_queued_source_notice(self):
        from market_ai.v2.tracking import TrackingService
        from market_ai.v2.api_models import AnalyzeRequest
        service=TrackingService(self.runtime)
        a=self.runtime.analysis.analyze(AnalyzeRequest(idempotency_key='delivery-preference-origin',data_mode='fixture',risk_portfolio='MANUAL',timeframe='1m'))
        track=service.start(a.analysis_id);service.source_policy(track.tracking_id,True)
        with self.db.transaction() as c:self.runtime.scanner._notify(c,'revoked-source-notice','analysis',{'tracking_id':track.tracking_id,'change_kind':'source_unavailable','expires_at_ms':self.now+900000})
        service.source_policy(track.tracking_id,False)
        report=self.dispatcher().tick();self.assertEqual(report['preference_blocked'],1);self.assertEqual(len(self.adapter.calls),1)
        with self.db.transaction() as c:self.assertIsNotNone(self.db.get(c,'notifications','revoked-source-notice'))
    def test_verified_backup_restore_retains_acceptance_without_resending(self):
        from scripts.backup_v2 import copy_database
        self.dispatcher().tick()
        target=self.db.path.with_name('restored.sqlite');copy_database(self.db.path,target)
        restored=create_runtime(target,mode='fixture',token=TOKEN,clock=lambda:self.now)
        r=NotificationDispatcher(restored.db,self.adapter,clock=lambda:self.now,authorization=lambda c,n,t:True).tick()
        self.assertEqual(r['accepted'],0);self.assertEqual(len(self.adapter.calls),1)
