"""Independent audit acceptance; all inputs are disposable fixture databases."""
from contextlib import closing
from decimal import localcontext, ROUND_UP
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import json
import sqlite3

from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.paper_audit import audit_database

TOKEN = 'audit-fixture-token-not-a-secret-32'
NOW = 1800000000000


class PaperAuditTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(prefix='v2-audit-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'fixture.sqlite'
        self.now = NOW
        self.app = create_app(self.path, mode='fixture', token=TOKEN, clock=lambda: self.now)
        self.client = TestClient(self.app, headers={'Authorization': 'Bearer '+TOKEN})
        self.addCleanup(self.client.close)

    def post(self, path, body):
        r = self.client.post('/api/v2/'+path, json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def order(self, account='MANUAL', key='audit-order-first', qty='10'):
        a = self.post('analyze', {'data_mode': 'fixture', 'idempotency_key': 'analysis-'+key})
        return self.post('portfolios/'+account+'/orders', {'analysis_id': a['analysis_id'],
                         'quantity': qty, 'idempotency_key': key})

    def event(self, **changes):
        start = self.now
        self.now += 60000
        body = {'symbol':'BTCUSDT', 'open_time_ms':start, 'close_time_ms':self.now,
                'open':'129.9', 'high':'130.2', 'low':'129.5', 'close':'130', 'volume':'200'}
        body.update(changes)
        return self.post('paper/events', body)

    def test_empty_database_passes_without_writes_and_is_deterministic(self):
        before = self.path.read_bytes()
        first = audit_database(self.path)
        self.assertEqual(first['status'], 'PASS', first)
        self.assertEqual(first, audit_database(self.path))
        self.assertEqual(before, self.path.read_bytes())

    def test_partial_entry_reconciles_independently(self):
        self.order()
        self.event()
        result = audit_database(self.path)
        self.assertEqual(result['status'], 'PASS', result)
        self.assertGreater(result['checks']['PASS'], 0)
        with localcontext() as ctx:
            ctx.prec = 3
            ctx.rounding = ROUND_UP
            self.assertEqual(result, audit_database(self.path))

    def codes(self, report):
        return {x['code'] for x in report['findings']}

    def clone(self, name):
        from scripts.backup_v2 import copy_database
        target = Path(self.tmp.name)/(name+'.sqlite')
        copy_database(self.path, target)
        return target

    def edit(self, path, table, transform):
        """Corrupt only a disposable copy, then restore its immutable guards."""
        from hashlib import sha256
        def encode(value):
            return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
        with closing(sqlite3.connect(path)) as c, c:
            guards = c.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)).fetchall()
            for name, sql in guards:
                c.execute('DROP TRIGGER '+name)
            row = c.execute('SELECT rowid,* FROM '+table+' ORDER BY rowid DESC LIMIT 1').fetchone()
            if transform is not None:
                data = json.loads(c.execute('SELECT body FROM '+table+' WHERE rowid=?', (row[0],)).fetchone()[0])
                transform(data)
                raw = encode(data)
                c.execute('UPDATE '+table+' SET body=?,body_hash=? WHERE rowid=?',
                          (raw, sha256(raw.encode()).hexdigest(), row[0]))
            else:
                c.execute('DELETE FROM '+table+' WHERE rowid=?', (row[0],))
            for name, sql in guards:
                c.execute(sql)

    def filled(self):
        order = self.order()
        self.event(volume='10000')
        return order

    def reduced(self):
        o = self.filled()
        self.post('portfolios/MANUAL/positions/'+o['order_id']+'/close',
                  {'quantity':'2', 'idempotency_key':'audit-reduce-first'})
        self.event(open='130.5', high='130.8', low='130.3', close='130.6', volume='10000')
        return o

    def test_valid_partial_close_pending_close_cancel_and_ambiguity(self):
        o = self.reduced()
        self.assertEqual(audit_database(self.path)['status'], 'PASS')
        self.post('portfolios/MANUAL/positions/'+o['order_id']+'/close',
                  {'quantity':'1', 'idempotency_key':'audit-delayed-close'})
        result = audit_database(self.path)
        self.assertEqual(result['status'], 'PASS', result)
        self.event(high='134', low='128', open='130', close='131', volume='0')
        self.assertEqual(audit_database(self.path)['status'], 'PASS')
        cancelled = self.order(account='AUTO', key='audit-cancel-order')
        self.post('portfolios/AUTO/orders/'+cancelled['order_id']+'/cancel', {'idempotency_key':'audit-cancel-key'})
        result = audit_database(self.path)
        self.assertEqual(result['status'], 'INCOMPLETE', result)
        self.assertEqual(self.codes(result), {'cancellation_timeline_not_persisted'})
        self.assertEqual(result['checks']['MISMATCH'], 0)

    def test_valid_tp1_tp2_and_gap_stop_are_not_false_mismatches(self):
        self.filled()
        self.event(open='130', high='132', low='129.8', close='131.8', volume='10000')
        self.assertEqual(audit_database(self.path)['status'], 'PASS')
        self.event(open='132', high='134', low='131.8', close='133.8', volume='10000')
        self.assertEqual(audit_database(self.path)['status'], 'PASS')
        self.order(key='audit-stop-order')
        self.event(volume='10000')
        self.event(open='127', high='128', low='126', close='127', volume='10000')
        report = audit_database(self.path)
        self.assertEqual(report['status'], 'INCOMPLETE', report)
        self.assertIn('stop_trigger_sequence_not_replayed', self.codes(report))
        self.assertEqual(report['checks']['MISMATCH'], 0)

    def test_recomputed_hash_does_not_hide_financial_corruption(self):
        self.reduced()
        cases = [('cash', 'accounts', 'cash_quote', '9999', 'cash_quote'),
                 ('fee', 'transactions', 'fee_quote', '10', 'fee_quote'),
                 ('cash_delta', 'transactions', 'cash_delta_quote', '0', 'cash_delta_quote'),
                 ('price', 'transactions', 'price', '1', 'price'),
                 ('pnl', 'transactions', 'realized_pnl_quote', '50', 'realized_pnl_quote'),
                 ('quantity', 'positions', 'quantity', '7', 'quantity'),
                 ('basis', 'positions', 'cost_basis_quote', '1', 'cost_basis_quote'),
                 ('position_pnl', 'positions', 'realized_pnl_quote', '1', 'realized_pnl_quote'),
                 ('mark', 'positions', 'mark_price', '1', 'mark_price'),
                 ('status', 'positions', 'status', 'unknown', 'position_status'),
                 ('stop_level', 'positions', 'invalidation', '1', 'invalidation'),
                 ('reserve', 'orders', 'remaining_quantity', '1', 'terminal_reservation')]
        for name, table, field, value, code in cases:
            with self.subTest(name=name):
                target = self.clone(name)
                self.edit(target, table, lambda b: b.update({field:value}))
                result = audit_database(target)
                self.assertEqual(result['status'], 'MISMATCH', result)
                self.assertIn(code, self.codes(result))

    def test_missing_journal_is_detected_and_missing_event_is_incomplete(self):
        self.reduced()
        target = self.clone('missing-journal')
        self.edit(target, 'transactions', None)
        report = audit_database(target)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('quantity', self.codes(report))
        target = self.clone('missing-event')
        self.edit(target, 'events', None)
        report = audit_database(target)
        self.assertEqual(report['status'], 'INCOMPLETE', report)
        self.assertIn('event_source', self.codes(report))

    def test_duplicate_fill_and_cross_account_links_are_detected(self):
        self.filled()
        target = self.clone('duplicate-fill')
        from market_ai.v2.product_db import encode, fingerprint
        with closing(sqlite3.connect(target)) as c, c:
            body = json.loads(c.execute('SELECT body FROM transactions').fetchone()[0])
            body['transaction_id'] = 'f'*64
            c.execute('INSERT INTO transactions VALUES(?,?,?,?,?)',
                      (body['transaction_id'], body['portfolio_id'], body['event_id'], encode(body), fingerprint(body)))
        report = audit_database(target)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('transaction_identity', self.codes(report))
        self.assertIn('quantity_conservation', self.codes(report))
        target = self.clone('wrong-account')
        self.edit(target, 'transactions', lambda b:b.update(portfolio_id='AUTO'))
        report = audit_database(target)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('transaction_ownership', self.codes(report))

    def test_nan_infinity_hash_and_source_record_corruption(self):
        self.filled()
        for value in ('NaN', 'sNaN', 'Infinity', '-Infinity', 'garbage', '1e99999999'):
            with self.subTest(value=value):
                target = self.clone('bad-number-'+str(len(list(Path(self.tmp.name).glob('*.sqlite')))))
                self.edit(target, 'positions', lambda b:b.update(cost_basis_quote=value))
                report = audit_database(target)
                self.assertEqual(report['status'], 'CORRUPT', report)
                self.assertIn('invalid_decimal', self.codes(report))
        target = self.clone('hash')
        with closing(sqlite3.connect(target)) as c, c:
            c.execute("UPDATE positions SET body_hash='broken'")
        self.assertIn('body_hash', self.codes(audit_database(target)))
        target = self.clone('record-hash')
        with closing(sqlite3.connect(target)) as c, c:
            guard = c.execute("SELECT sql FROM sqlite_master WHERE name='immutable_records_update'").fetchone()[0]
            c.execute('DROP TRIGGER immutable_records_update')
            c.execute("UPDATE decision_records SET body_json='{}'")
            c.execute(guard)
        report = audit_database(target)
        self.assertEqual(report['status'], 'CORRUPT', report)
        self.assertIn('decision_record_hash', self.codes(report))

    def test_event_sequence_and_active_reservation_corruption(self):
        self.order()
        self.event()
        self.event()
        target = self.clone('event-order')
        with closing(sqlite3.connect(target)) as c, c:
            guard = c.execute("SELECT sql FROM sqlite_master WHERE name='events_update'").fetchone()[0]
            c.execute('DROP TRIGGER events_update')
            c.execute('UPDATE events SET rowid=100 WHERE rowid=1')
            c.execute(guard)
        report = audit_database(target)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('event_sequence', self.codes(report))
        target = self.clone('active-reserve')
        self.edit(target, 'orders', lambda b:b.update(remaining_quantity='9'))
        report = audit_database(target)
        self.assertIn('remaining_quantity', self.codes(report))

    def test_missing_ack_unsupported_model_and_resource_limits_are_incomplete(self):
        self.filled()
        target = self.clone('missing-ack')
        with closing(sqlite3.connect(target)) as c, c:
            guard = c.execute("SELECT sql FROM sqlite_master WHERE name='commands_delete'").fetchone()[0]
            c.execute('DROP TRIGGER commands_delete')
            c.execute("DELETE FROM commands WHERE scope='order:MANUAL'")
            c.execute(guard)
        self.assertIn('order_ack_source', self.codes(audit_database(target)))
        target = self.clone('future-model')
        self.edit(target, 'orders', lambda b:b.update(execution_model='future'))
        self.assertEqual(audit_database(target)['status'], 'INCOMPLETE')
        for args in ({'max_records':1}, {'max_body_bytes':10}, {'max_total_body_bytes':100}):
            report = audit_database(self.path, **args)
            self.assertEqual(report['status'], 'INCOMPLETE', report)
        target = self.clone('findings')
        self.edit(target, 'positions', lambda b:b.update(quantity='1', cost_basis_quote='1', realized_pnl_quote='1'))
        report = audit_database(target, max_findings=1)
        self.assertEqual(len(report['findings']), 1)
        self.assertGreater(report['findings_omitted'], 0)
        self.assertEqual(report['status'], 'MISMATCH')

    def test_readonly_query_guard_missing_file_and_redacted_error_cleanup(self):
        from market_ai.v2.paper_audit import _source, _Audit
        before = self.path.read_bytes()
        with _source(self.path) as c:
            with self.assertRaises(sqlite3.OperationalError):
                c.execute("UPDATE accounts SET body='{}'")
        self.assertEqual(self.path.read_bytes(), before)
        missing = Path(self.tmp.name)/'do-not-create.sqlite'
        report = audit_database(missing)
        self.assertEqual(report['status'], 'ERROR')
        self.assertFalse(missing.exists())
        with patch.object(_Audit, 'events', side_effect=sqlite3.OperationalError('private-record-secret-marker')):
            report = audit_database(self.path)
        self.assertEqual(report['status'], 'ERROR')
        self.assertNotIn('private-record-secret-marker', json.dumps(report))
        self.assertNotIn(str(self.path), json.dumps(report))
        moved = self.path.with_suffix('.moved')
        self.path.rename(moved)  # Also proves connection cleanup on Windows.
        moved.rename(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_wal_snapshot_is_consistent_and_sees_committed_data(self):
        from market_ai.v2.paper_audit import _Audit
        from market_ai.v2.product_db import encode, fingerprint
        with closing(sqlite3.connect(self.path)) as writer:
            writer.execute('PRAGMA journal_mode=WAL')
            original = _Audit.events
            def commit_after_snapshot(audit):
                body = json.loads(writer.execute("SELECT body FROM accounts WHERE id='MANUAL'").fetchone()[0])
                body['cash_quote'] = '1'
                writer.execute('UPDATE accounts SET body=?,body_hash=? WHERE id=?', (encode(body), fingerprint(body), 'MANUAL'))
                writer.commit()
                return original(audit)
            with patch.object(_Audit, 'events', commit_after_snapshot):
                self.assertEqual(audit_database(self.path)['status'], 'PASS')
            report = audit_database(self.path)
            self.assertEqual(report['status'], 'MISMATCH', report)
            self.assertIn('cash_quote', self.codes(report))

    def test_cli_exit_codes_redaction_and_no_implicit_path(self):
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        from scripts.audit_v2 import main
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([str(self.path)]), 0)
        report = json.loads(output.getvalue())
        self.assertNotIn('10000', output.getvalue())
        self.assertEqual(report['status'], 'PASS')
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as raised:
            main([])
        self.assertEqual(raised.exception.code, 2)
        for value in (0, -1, True):
            with self.assertRaises(ValueError):
                audit_database(self.path, max_records=value)

    def test_auditor_has_no_dependency_on_ledger_calculations(self):
        from market_ai.v2 import paper_audit
        import ast
        tree = ast.parse(Path(paper_audit.__file__).read_text())
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any(m and any(x in m for x in ('paper_ledger', 'paper_risk', 'product_db', 'api')) for m in imports))
        self.filled()
        with patch('market_ai.v2.paper_ledger.PaperLedger.account', side_effect=AssertionError('must be independent')):
            self.assertEqual(audit_database(self.path)['status'], 'PASS')

    def test_missing_ack_does_not_compare_partial_cash_as_a_verified_mismatch(self):
        self.filled()
        target = self.clone('ack-without-cash-source')
        with closing(sqlite3.connect(target)) as c, c:
            guard = c.execute("SELECT sql FROM sqlite_master WHERE name='commands_delete'").fetchone()[0]
            c.execute('DROP TRIGGER commands_delete')
            c.execute("DELETE FROM commands WHERE scope='order:MANUAL'")
            c.execute(guard)
        result = audit_database(target)
        self.assertEqual(result['status'], 'INCOMPLETE', result)
        self.assertNotIn('cash_quote', self.codes(result))

    def test_missing_intermediate_market_history_is_not_a_pass(self):
        self.filled()
        self.event(volume='0')
        self.event(volume='0')
        target = self.clone('market-gap')
        with closing(sqlite3.connect(target)) as c, c:
            guard = c.execute("SELECT sql FROM sqlite_master WHERE name='events_delete'").fetchone()[0]
            c.execute('DROP TRIGGER events_delete')
            c.execute('DELETE FROM events WHERE rowid=2')
            c.execute(guard)
        result = audit_database(target)
        self.assertEqual(result['status'], 'INCOMPLETE', result)
        self.assertIn('market_history_gap', self.codes(result))

    def test_cancel_ack_prevents_cancelled_order_from_becoming_active_silently(self):
        o = self.order()
        self.post('portfolios/MANUAL/orders/'+o['order_id']+'/cancel', {'idempotency_key':'cancel-proof-key'})
        target = self.clone('reactivated-cancel')
        self.edit(target, 'orders', lambda b:b.update(status='pending', remaining_quantity='10.00000000'))
        result = audit_database(target)
        self.assertEqual(result['status'], 'MISMATCH', result)
        self.assertIn('cancel_ack_state', self.codes(result))

    def test_cli_all_classifications_have_distinct_exit_codes(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from scripts.audit_v2 import main
        self.filled()
        mismatch = self.clone('cli-mismatch')
        self.edit(mismatch, 'accounts', lambda b:b.update(cash_quote='1'))
        corrupt = self.clone('cli-corrupt')
        with closing(sqlite3.connect(corrupt)) as c, c:
            c.execute("UPDATE positions SET body_hash='broken'")
        cases = [([str(self.path)], 0, 'PASS'), ([str(mismatch)], 1, 'MISMATCH'),
                 ([str(self.path), '--max-records', '1'], 2, 'INCOMPLETE'),
                 ([str(corrupt)], 3, 'CORRUPT'), ([str(Path(self.tmp.name)/'absent.sqlite')], 4, 'ERROR')]
        for args, exit_code, status in cases:
            with self.subTest(status=status):
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(args), exit_code)
                self.assertEqual(json.loads(output.getvalue())['status'], status)

    def test_missing_immutable_guard_is_corrupt_without_repair(self):
        target = self.clone('missing-guard')
        with closing(sqlite3.connect(target)) as c, c:
            c.execute('DROP TRIGGER transactions_delete')
        before = target.read_bytes()
        report = audit_database(target)
        self.assertEqual(report['status'], 'CORRUPT', report)
        self.assertIn('immutable_guard', self.codes(report))
        self.assertEqual(target.read_bytes(), before)

    def test_hand_calculated_fee_basis_cash_and_pnl_oracle(self):
        from decimal import Decimal
        self.reduced()
        p = self.client.get('/api/v2/portfolios/MANUAL/positions').json()[0]
        a = self.client.get('/api/v2/portfolios/MANUAL').json()
        # 10 @ 129.92598, fee .64962990 => basis 1299.90942990.
        # Sell 2 @ 130.4739, fee .13047390, allocated basis 259.98188598.
        self.assertEqual(Decimal(p['quantity']), Decimal('8'))
        self.assertEqual(Decimal(p['cost_basis_quote']), Decimal('1039.92754392'))
        self.assertEqual(Decimal(p['realized_pnl_quote']), Decimal('.83544012'))
        self.assertEqual(Decimal(a['cash_quote']), Decimal('8960.90789620'))
        self.assertEqual(Decimal(p['unrealized_pnl_quote']), Decimal('4.87245608'))
        self.assertEqual(Decimal(a['equity_quote']), Decimal('10005.70789620'))
        self.assertEqual(audit_database(self.path)['status'], 'PASS')

    def test_missing_entry_journal_and_nonzero_closed_basis_are_detected(self):
        o = self.filled()
        missing = self.clone('missing-entry')
        self.edit(missing, 'transactions', None)
        report = audit_database(missing)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('position_without_entry', self.codes(report))
        self.post('portfolios/MANUAL/positions/'+o['order_id']+'/close',
                  {'quantity':'10', 'idempotency_key':'close-completely-key'})
        self.event(volume='10000')
        self.assertEqual(audit_database(self.path)['status'], 'PASS')
        closed = self.clone('closed-basis')
        self.edit(closed, 'positions', lambda b:b.update(cost_basis_quote='1'))
        report = audit_database(closed)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('cost_basis_quote', self.codes(report))

    def test_incorrect_step_in_both_order_and_ack_is_checked_against_instrument(self):
        self.filled()
        target = self.clone('wrong-step')
        for table in ('orders', 'commands'):
            self.edit(target, table, lambda b:b.update(quantity_step='0.000002'))
        report = audit_database(target)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('instrument_quantity_step', self.codes(report))

    def test_position_under_a_different_primary_key_cannot_escape_reconciliation(self):
        order = self.order()
        target = self.clone('aliased-position')
        from market_ai.v2.product_db import encode, fingerprint
        with closing(sqlite3.connect(target)) as c, c:
            saved = json.loads(c.execute('SELECT body FROM orders').fetchone()[0])
            p = {'position_id':'e'*64, 'portfolio_id':'MANUAL', 'order_id':order['order_id'],
                 'symbol':'BTCUSDT', 'data_mode':'fixture', 'status':'open', 'quantity':'1',
                 'average_entry':'129.92598000', 'cost_basis_quote':'130', 'mark_price':'130',
                 'mark_time_ms':self.now, 'realized_pnl_quote':'0', 'opened_at_ms':self.now,
                 'tp1_done':False, **{k:saved['levels'][k] for k in ('invalidation','target_1','target_2')}}
            c.execute('INSERT INTO positions VALUES(?,?,?,?,?)',
                      (p['position_id'], 'MANUAL', p['order_id'], encode(p), fingerprint(p)))
        report = audit_database(target)
        self.assertEqual(report['status'], 'MISMATCH', report)
        self.assertIn('position_order_identity', self.codes(report))

    def test_financial_commands_cannot_hide_missing_position_or_wrong_account_scope(self):
        o = self.order()
        from market_ai.v2.product_db import encode, fingerprint
        for kind in ('close', 'cancel'):
            with self.subTest(kind=kind):
                target = self.clone('orphan-'+kind)
                key = 'counterfeit-fixture-key'
                scope = ('close:MANUAL:'+o['order_id']) if kind == 'close' else 'cancel:AUTO'
                if kind == 'close':
                    body = {'close_request_id':fingerprint({'scope':scope,'key':key}), 'position_id':o['order_id'],
                            'quantity':'1.00000000', 'status':'pending', 'created_at_ms':self.now}
                else:
                    body = {**o, 'status':'cancelled', 'remaining_quantity':'0'}
                with closing(sqlite3.connect(target)) as c, c:
                    c.execute('INSERT INTO commands VALUES(?,?,?,?,?)', (scope,key,'a'*64,encode(body),fingerprint(body)))
                result = audit_database(target)
                self.assertEqual(result['status'], 'MISMATCH', result)
                self.assertIn('close_command_position' if kind == 'close' else 'command_ownership', self.codes(result))
