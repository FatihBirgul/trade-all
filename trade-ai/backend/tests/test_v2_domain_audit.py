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
from market_ai.v2.paper_audit import audit_database


class DomainAuditTests(DomainFixture, TestCase):
    def test_independent_domain_replay_verifies_cancel_stop_and_control_history(self):
        from market_ai.v2.paper_audit import audit_database
        o,_=self.order();self.event(volume='200')
        self.post('portfolios/MANUAL/orders/'+o['order_id']+'/cancel',{'idempotency_key':'audit-domain-cancel'})
        self.event(open='128',high='129',low='127',close='128',volume='0')
        self.event(open='130',high='130.5',low='129.8',close='130')
        report=audit_database(self.path,require_domain=True)
        self.assertEqual(report['status'],'PASS',report)
        self.assertEqual(report['domain']['status'],'PASS',report)
        with patch('market_ai.v2.domain_journal.digest',side_effect=AssertionError('must be independent')):
            self.assertEqual(audit_database(self.path,require_domain=True),report)

    def test_same_bar_tp1_tp2_compares_numeric_quantities_not_decimal_spelling(self):
        from decimal import Decimal
        o,_=self.order(quantity='10.000003')
        self.event()
        with self.app.state.v2.db.transaction() as c:
            target=self.app.state.v2.db.get(c,'orders',o['order_id'])['levels']['target_2']
        self.event(open='130',low='129.9',high=str(Decimal(target)+1),close=target)
        report=audit_database(self.path,require_domain=True)
        self.assertEqual(report['status'],'PASS',report)
        with self.app.state.v2.db.transaction() as c:
            journal=self.app.state.v2.db.rows(c,'transactions','MANUAL')
        self.assertEqual({t['kind'] for t in journal},{'entry','take_profit_1','take_profit_2'})

    def copy(self,name):
        from scripts.backup_v2 import copy_database
        target=Path(self.tmp.name)/(name+'.sqlite');copy_database(self.path,target);return target

    def rewrite(self,path,transform,remove=None):
        """Rehash only disposable fixtures to exercise semantics beyond checksums."""
        with closing(sqlite3.connect(path)) as c,c:
            guards=c.execute("SELECT name,sql FROM sqlite_master WHERE name IN ('domain_events_update','domain_events_delete','domain_head_update')").fetchall()
            for name,sql in guards:c.execute('DROP TRIGGER '+name)
            rows=c.execute('SELECT sequence,body FROM domain_events ORDER BY sequence').fetchall()
            previous='0'*64;sequence=0
            for old,raw in rows:
                body=json.loads(raw)
                if remove and remove(body):
                    c.execute('DELETE FROM domain_events WHERE sequence=?',(old,));continue
                sequence+=1;transform(body)
                body['sequence']=sequence;body['previous_event_hash']=previous
                h=domain.digest(body);eid=domain.digest({'schema_version':1,'sequence':sequence,'event_hash':h})
                c.execute('UPDATE domain_events SET sequence=?,event_id=?,event_hash=?,portfolio_id=?,source_id=?,body=? WHERE sequence=?',
                          (sequence,eid,h,body['portfolio_id'],(body['source'] or {}).get('event_id'),domain.canonical(body),old))
                previous=h
            c.execute('UPDATE domain_head SET sequence=?,event_hash=?',(sequence,previous))
            for name,sql in guards:c.execute(sql)

    def codes(self,r):return {f['code'] for f in r['findings']}

    def stop_history(self):
        self.order();self.event()
        self.event(open='128',high='129',low='127',close='128',volume='0')
        self.event(open='130',high='130.5',low='129.8',close='130')

    def test_sequence_previous_hash_and_tail_loss_are_corrupt(self):
        self.order();self.event()
        for fault in ('gap','previous','tail'):
            with self.subTest(fault=fault):
                target=self.copy(fault)
                with closing(sqlite3.connect(target)) as c,c:
                    guard_name='domain_events_delete' if fault in ('gap','tail') else 'domain_events_update'
                    guard=c.execute('SELECT sql FROM sqlite_master WHERE name=?',(guard_name,)).fetchone()[0]
                    if fault in ('gap','tail'):
                        c.execute('DROP TRIGGER domain_events_delete')
                        c.execute('DELETE FROM domain_events WHERE sequence=(SELECT '+('MIN' if fault=='gap' else 'MAX')+'(sequence) FROM domain_events)')
                    else:
                        c.execute('DROP TRIGGER domain_events_update')
                        row=c.execute('SELECT sequence,body FROM domain_events ORDER BY sequence DESC LIMIT 1').fetchone()
                        b=json.loads(row[1]);b['previous_event_hash']='f'*64
                        c.execute('UPDATE domain_events SET body=? WHERE sequence=?',(json.dumps(b),row[0]))
                    c.execute(guard)
                r=audit_database(target,require_domain=True)
                self.assertEqual(r['status'],'CORRUPT',r)

    def test_rehashed_wrong_preimage_and_account_are_mismatches(self):
        self.order();self.event()
        cases=('preimage','account')
        for case in cases:
            with self.subTest(case=case):
                target=self.copy('bad-'+case)
                def change(b):
                    if case=='preimage' and b['event_type']=='command.accepted' and b['command']['scope']=='order:MANUAL':
                        b['payload']['preimage']['quantity']='9'
                    if case=='account' and b['event_type']=='state.changed' and b['payload']['table']=='positions':
                        b['portfolio_id']='AUTO'
                self.rewrite(target,change)
                r=audit_database(target,require_domain=True)
                self.assertEqual(r['status'],'MISMATCH',r)
                self.assertIn('domain_request_digest' if case=='preimage' else 'domain_account',self.codes(r))

    def test_missing_financial_fact_or_ack_is_not_a_pass(self):
        self.order();self.event()
        for table in ('transactions','commands'):
            target=self.copy('missing-'+table)
            self.rewrite(target,lambda b:None,remove=lambda b:(b['event_type']=='record.created' and b['payload']['table']==table))
            r=audit_database(target,require_domain=True)
            self.assertEqual(r['status'],'MISMATCH',r)
            self.assertIn('domain_fact_coverage',self.codes(r))
        target=self.copy('missing-accepted')
        self.rewrite(target,lambda b:None,remove=lambda b:b['event_type']=='command.accepted')
        r=audit_database(target,require_domain=True)
        self.assertEqual(r['status'],'MISMATCH',r)
        self.assertIn('domain_ack_coverage',self.codes(r))

    def test_unknown_event_version_and_missing_decision_are_incomplete(self):
        self.stop_history()
        for version in ('schema','kind','decision','invalid_type'):
            target=self.copy('future-'+version)
            def change(b):
                if b['event_type']=='protective.evaluated':
                    if version=='schema':b['schema_version']=99
                    if version=='invalid_type':b['schema_version']=True
                    if version=='kind':b['event_type']='future.protective'
            self.rewrite(target,change,remove=(lambda b:b['event_type']=='protective.evaluated') if version=='decision' else None)
            r=audit_database(target,require_domain=True)
            expected='CORRUPT' if version=='invalid_type' else 'INCOMPLETE'
            self.assertEqual(r['status'],expected,r)
            self.assertEqual(r['domain']['status'],expected)

    def test_prior_stop_quantity_and_pause_request_tampering_are_detected(self):
        self.stop_history()
        self.post('portfolios/MANUAL/pause',{'paused':False})
        for case in ('prior','quantity','pause'):
            target=self.copy('semantic-'+case)
            def change(b):
                if case=='prior' and b['event_type']=='protective.evaluated' and b['payload']['prior_stop']:
                    b['payload']['prior_stop']=False
                if case=='quantity' and b['event_type']=='exit.decision':b['payload']['quantity']='9'
                if case=='pause' and b['event_type']=='control.requested' and (b['source'] or {}).get('control')=='account_pause':
                    b['payload']['paused']=not b['payload']['paused']
            self.rewrite(target,change);r=audit_database(target,require_domain=True)
            self.assertEqual(r['status'],'MISMATCH',r)
            self.assertIn({'prior':'domain_prior_stop','quantity':'domain_decision_quantity','pause':'domain_pause_source'}[case],self.codes(r))

    def test_duplicate_id_and_unjournaled_projection_changes_are_blocked(self):
        self.order();self.event()
        target=self.copy('duplicate')
        with closing(sqlite3.connect(target)) as c:
            c.create_function('domain_internal',0,lambda:1)
            row=c.execute('SELECT * FROM domain_events ORDER BY sequence DESC LIMIT 1').fetchone()
            with self.assertRaises(sqlite3.IntegrityError):
                c.execute('INSERT INTO domain_events VALUES(?,?,?,?,?,?)',(row[0]+1,*row[1:]))
            c.rollback()
        target=self.copy('projection')
        with closing(sqlite3.connect(target)) as c,c:
            sql=c.execute("SELECT sql FROM sqlite_master WHERE name='domain_capture_accounts_update'").fetchone()[0]
            c.execute('DROP TRIGGER domain_capture_accounts_update')
            raw=c.execute("SELECT body FROM accounts WHERE id='MANUAL'").fetchone()[0]
            b=json.loads(raw);b['paused']=True
            c.execute("UPDATE accounts SET body=?,body_hash=? WHERE id='MANUAL'",(domain.canonical(b),domain.digest(b)))
            c.execute(sql)
        r=audit_database(target,require_domain=True)
        self.assertEqual(r['status'],'MISMATCH',r);self.assertIn('domain_projection',self.codes(r))

    def test_legacy_and_boundary_reports_do_not_invent_history(self):
        from scripts.migrate_v2_domain import copy_upgrade
        legacy=Path(self.tmp.name)/'legacy.sqlite'
        app=create_app(legacy,mode='fixture',token=TOKEN,clock=lambda:self.now)
        r=audit_database(legacy,require_domain=True)
        self.assertEqual(r['status'],'INCOMPLETE');self.assertEqual(r['domain']['coverage'],'legacy')
        migrated=Path(self.tmp.name)/'migrated.sqlite';copy_upgrade(legacy,migrated,clock=lambda:self.now)
        r=audit_database(migrated,require_domain=True)
        self.assertEqual(r['status'],'INCOMPLETE',r)
        self.assertIn('domain_legacy_history',self.codes(r));self.assertEqual(r['domain']['coverage'],'legacy_boundary')

    def test_missing_schema_index_and_invalid_version_fail_closed(self):
        self.order()
        for fault in ('index','table','version'):
            target=self.copy('schema-'+fault)
            with closing(sqlite3.connect(target)) as c,c:
                if fault=='index':c.execute('DROP INDEX domain_source_sequence')
                elif fault=='table':c.execute('DROP TABLE domain_head')
                else:
                    c.execute('DROP TRIGGER domain_meta_update')
                    c.execute('UPDATE domain_meta SET version=99')
            r=audit_database(target,require_domain=True)
            self.assertIn(r['status'],('CORRUPT','INCOMPLETE'),r)
            with self.assertRaises((ValueError,sqlite3.DatabaseError)):
                create_app(target,mode='fixture',token=TOKEN,domain_journal=True)

    def test_decimal_context_cannot_change_domain_report(self):
        from decimal import localcontext,ROUND_UP
        self.stop_history();normal=audit_database(self.path,require_domain=True)
        with localcontext() as ctx:
            ctx.prec=3;ctx.rounding=ROUND_UP
            self.assertEqual(audit_database(self.path,require_domain=True),normal)

    def test_valid_partial_refill_after_protective_evaluation_is_not_a_mismatch(self):
        self.order();self.event(volume='200');self.event(volume='300')
        report=audit_database(self.path,require_domain=True)
        self.assertEqual(report['status'],'PASS',report)

    def test_baseline_account_header_and_control_source_are_verified(self):
        self.stop_history()
        for fault in ('baseline','control_source'):
            target=self.copy('relation-'+fault)
            def change(b):
                if fault=='baseline' and b['event_type']=='state.baseline' and b['payload']['table']=='accounts' and b['portfolio_id']=='MANUAL':
                    b['portfolio_id']='AUTO'
                if fault=='control_source' and b['event_type']=='state.changed' and b['payload']['table']=='accounts' and b['payload']['after'].get('paused') is True:
                    b['source']={'event_id':'f'*64}
            self.rewrite(target,change);r=audit_database(target,require_domain=True)
            self.assertEqual(r['status'],'MISMATCH' if fault=='baseline' else 'INCOMPLETE',r)
            self.assertIn('domain_baseline_account' if fault=='baseline' else 'domain_market_source',self.codes(r))

    def test_missing_zero_liquidity_stop_evaluation_is_not_excused_by_later_exit(self):
        self.stop_history();target=self.copy('missing-zero-stop-proof')
        self.rewrite(target,lambda b:None,remove=lambda b:b['event_type']=='protective.evaluated' and b['payload']['available']=='0.00000000')
        r=audit_database(target,require_domain=True)
        self.assertEqual(r['status'],'INCOMPLETE',r)
        self.assertIn('domain_order_evaluation_missing',self.codes(r))

    def test_unfinished_analysis_attempt_is_incomplete_until_explicit_retry(self):
        from market_ai.v2.api_models import AnalyzeRequest
        request=AnalyzeRequest(data_mode='fixture',idempotency_key='interrupted-analysis-key')
        with patch.object(self.app.state.v2.analysis.provider,'rules',side_effect=RuntimeError('controlled crash after request probe')):
            with self.assertRaises(RuntimeError):self.app.state.v2.analysis.analyze(request)
        report=audit_database(self.path,require_domain=True)
        self.assertEqual(report['status'],'INCOMPLETE',report)
        self.assertIn('domain_command_outcome_missing',self.codes(report))
        self.restart();self.post('analyze',request.model_dump(mode='json'))
        self.assertEqual(audit_database(self.path,require_domain=True)['status'],'PASS')
