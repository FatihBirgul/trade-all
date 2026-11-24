"""Journal-enabled ASGI scenarios, no sockets or existing database paths."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3
import httpx

from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2 import domain_journal as domain

NOW=1800000000000
TOKEN='domain-fixture-token-not-a-secret-32'


from tests.domain_fixture import DomainFixture


class DomainAPITests(DomainFixture, TestCase):
    def test_commands_preimages_cancel_pause_scanner_and_follow(self):
        o,args=self.order()
        self.post('portfolios/MANUAL/orders/'+o['order_id']+'/cancel',{'idempotency_key':'domain-cancel-key'})
        self.post('portfolios/MANUAL/pause',{'paused':True})
        self.post('portfolios/MANUAL/pause',{'paused':False})
        self.post('scanner/pause',{'paused':False});self.post('scanner/pause',{'paused':True})
        a=self.post('analyze',{'data_mode':'fixture','idempotency_key':'follow-source-key'})
        follow=self.post('analysis-tracking',{'analysis_id':a['analysis_id']})
        self.post('analysis-tracking/'+follow['tracking_id'],{'enabled':False})
        self.post('analysis-tracking/'+follow['tracking_id'],{'enabled':True})
        rows=self.rows();self.assert_chain()
        commands=[r for r in rows if r['event_type']=='command.accepted']
        self.assertTrue(any(r['command']['scope']=='order:MANUAL' and r['payload']['preimage']['quantity']=='10' for r in commands))
        self.assertTrue(any(r['event_type']=='state.changed' and r['payload']['table']=='analysis_tracking' for r in rows))
        for r in commands:
            self.assertEqual(domain.digest(r['payload']['preimage']),r['command']['request_digest'])
        self.assertNotIn(TOKEN,json.dumps(rows))

    def test_rejection_commits_only_evidence_and_duplicate_does_not_post_twice(self):
        o,args=self.order()
        before=self.client.get('/api/v2/portfolios/MANUAL').json()
        bad={**args,'quantity':'100000','idempotency_key':'rejected-order-key'}
        r=self.client.post('/api/v2/portfolios/MANUAL/orders',json=bad)
        self.assertEqual(r.status_code,422,r.text)
        self.assertEqual(self.client.get('/api/v2/portfolios/MANUAL').json(),before)
        rejected=[r for r in self.rows() if r['event_type']=='command.rejected']
        self.assertEqual(rejected[-1]['payload']['reason'],'INVALID_PAPER_SIZE')
        self.assertEqual(rejected[-1]['payload']['preimage']['quantity'],'100000')
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:self.post('portfolios/MANUAL/orders',args),range(2)))
        self.assertEqual(responses,[o,o])
        receipt,bar=self.event()
        tx_before=len([r for r in self.rows() if r['event_type']=='record.created' and r['payload']['table']=='transactions'])
        self.restart()
        self.assertEqual(self.post('paper/events',bar),receipt)
        self.assertEqual(self.post('portfolios/MANUAL/orders',args),o)
        self.assertEqual(len([r for r in self.rows() if r['event_type']=='record.created' and r['payload']['table']=='transactions']),tx_before)
        self.assert_chain()

    def test_domain_write_failure_rolls_back_completed_financial_mutations(self):
        self.order();before=self.rows()
        original=domain.append
        def fail_transaction(c,kind,payload,**kwargs):
            if kind=='record.created' and payload.get('table')=='transactions':
                raise sqlite3.OperationalError('controlled domain disk failure')
            return original(c,kind,payload,**kwargs)
        with patch.object(domain,'append',side_effect=fail_transaction),self.assertLogs('market_ai.v2.api',level='ERROR'):
            start=self.now;self.now+=60000
            bar={'symbol':'BTCUSDT','open_time_ms':start,'close_time_ms':self.now,'open':'129.9','high':'130.2','low':'129.5','close':'130','volume':'10000'}
            r=self.client.post('/api/v2/paper/events',json=bar)
        self.assertEqual(r.status_code,503,r.text)
        self.assertEqual(self.rows(),before)
        self.assertEqual(self.client.get('/api/v2/portfolios/MANUAL/positions').json(),[])
        self.post('paper/events',bar);self.assert_chain()

    def test_tp1_manual_reduction_and_zero_volume_stop_have_decision_evidence(self):
        o,_=self.order();self.event()
        self.event(open='130',high='132',low='129.8',close='131.8',volume='200')
        self.post('portfolios/MANUAL/positions/'+o['order_id']+'/close',{'quantity':'6','idempotency_key':'domain-reduce-key'})
        self.event(open='130',high='130.5',low='129.8',close='130',volume='600')
        self.event(open='130',high='132',low='129.8',close='131.8')
        self.assertEqual(self.client.get('/api/v2/portfolios/MANUAL/positions').json(),[])
        self.order(key='zero-stop-order');self.event()
        self.event(open='128',high='129',low='127',close='128',volume='0')
        self.event(open='130',high='130.5',low='129.8',close='130')
        evals=[r for r in self.rows() if r['event_type']=='protective.evaluated']
        self.assertTrue(any(r['payload']['stop'] and r['payload']['available']=='0.00000000' for r in evals))
        self.assertTrue(any(r['payload']['prior_stop'] for r in evals))
        self.assert_chain()

    def test_lost_response_after_commit_retries_same_command(self):
        a=self.post('analyze',{'data_mode':'fixture','idempotency_key':'lost-ack-analysis'})
        args={'analysis_id':a['analysis_id'],'quantity':'1','idempotency_key':'lost-ack-command'}
        def lose(response):
            response.read();raise httpx.ReadTimeout('controlled fixture loss')
        self.client.event_hooks['response'].append(lose)
        try:
            with self.assertRaises(httpx.ReadTimeout):self.client.post('/api/v2/portfolios/MANUAL/orders',json=args)
        finally:self.client.event_hooks['response'].remove(lose)
        self.restart();self.post('portfolios/MANUAL/orders',args)
        self.assertEqual(len(self.client.get('/api/v2/portfolios/MANUAL/orders').json()),1)
        self.assert_chain()


    def test_missing_analysis_and_schema_validation_leave_only_safe_rejection_evidence(self):
        args={'analysis_id':'a'*64,'quantity':'1','idempotency_key':'unknown-analysis-key'}
        r=self.client.post('/api/v2/portfolios/MANUAL/orders',json=args)
        self.assertEqual(r.status_code,404,r.text)
        rejected=[x for x in self.rows() if x['event_type']=='command.rejected']
        self.assertTrue(rejected,'Accepted-shape order rejections need a preimage too')
        self.assertEqual(rejected[-1]['payload']['reason'],'ANALYSIS_NOT_FOUND')
        marker='private-fixture-invalid-body-marker'
        r=self.client.post('/api/v2/portfolios/MANUAL/orders',json={**args,'quantity':'NaN','authorization':marker})
        self.assertEqual(r.status_code,422)
        self.assertNotIn(marker,json.dumps(self.rows()))
        self.assertTrue(any(x['event_type']=='request.validation_rejected' for x in self.rows()))
        before=self.rows()
        r=self.client.post('/api/v2/portfolios/MANUAL/orders',json=args,headers={'Authorization':'Bearer invalid'})
        self.assertEqual(r.status_code,401)
        self.assertEqual(self.rows(),before)

    def test_ambiguous_manual_partial_exit_is_in_market_receipt(self):
        from market_ai.v2.paper_audit import audit_database
        for enabled in (False,True):
            with self.subTest(domain=enabled):
                self.client.close();self.path=Path(self.tmp.name)/('ambiguous-'+str(enabled)+'.sqlite');self.now=NOW
                self.app=create_app(self.path,mode='fixture',token=TOKEN,clock=lambda:self.now,domain_journal=enabled)
                self.client=TestClient(self.app,headers={'Authorization':'Bearer '+TOKEN});self.addCleanup(self.client.close)
                order,_=self.order();self.event(open='130',high='134',low='128',close='131')
                self.post('portfolios/MANUAL/positions/'+order['order_id']+'/close',{'quantity':'1','idempotency_key':'ambiguous-partial-close'})
                receipt,_=self.event()
                self.assertIn(order['order_id'],[x['order_id'] for x in receipt['processed']])
                self.assertEqual(audit_database(self.path)['status'],'PASS')

    def test_commit_failure_has_no_durable_financial_or_domain_effect(self):
        self.order();before=self.rows();start=self.now;self.now+=60000
        bar={'symbol':'BTCUSDT','open_time_ms':start,'close_time_ms':self.now,'open':'129.9','high':'130.2','low':'129.5','close':'130','volume':'10000'}
        with patch.object(domain.Connection,'commit',side_effect=sqlite3.OperationalError('controlled commit failure')),self.assertLogs('market_ai.v2.api',level='ERROR'):
            r=self.client.post('/api/v2/paper/events',json=bar)
        self.assertEqual(r.status_code,503)
        self.assertEqual(self.rows(),before)
        self.assertEqual(self.client.get('/api/v2/portfolios/MANUAL/positions').json(),[])
        self.post('paper/events',bar);self.assert_chain()

    def test_pause_rejection_and_manual_then_sticky_stop_share_liquidity(self):
        from market_ai.v2.paper_audit import audit_database
        o,_=self.order();self.event()
        self.event(open='128',high='129',low='127',close='128',volume='200')
        rejected=self.client.post('/api/v2/portfolios/MANUAL/pause',json={'paused':False})
        self.assertEqual(rejected.status_code,409)
        self.post('portfolios/MANUAL/positions/'+o['order_id']+'/close',{'quantity':'1','idempotency_key':'manual-sticky-close'})
        self.event(open='130',high='130.5',low='129.8',close='130',volume='300')
        r=audit_database(self.path,require_domain=True)
        self.assertEqual(r['status'],'PASS',r)
        self.assertTrue(any(x['event_type']=='operation.rejected' and x['payload']['reason']=='UNRESOLVED_PAPER_EXIT' for x in self.rows()))
