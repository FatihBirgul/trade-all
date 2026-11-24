"""Independent read-only V2 accounting replay, not a second execution engine.

No ledger/API/provider imports. Missing lifecycle evidence is never invented.
Reports expose fixed codes/counts, never bodies, keys, paths or financial values.
"""
from contextlib import closing, contextmanager
from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3

VERSION = 'v2-paper-audit-1'
STATES = ('PASS', 'INCOMPLETE', 'MISMATCH', 'CORRUPT', 'ERROR')
TABLES = ('accounts', 'orders', 'positions', 'transactions', 'events', 'commands', 'analyses')
UNIT, ZERO = Decimal('.00000001'), Decimal(0)
MODEL = 'next_closed_bar_touch_worst_edge_v1'
ACTIVE = ('pending', 'partially_filled')
TERMINAL = ('filled', 'cancelled', 'cancelled_gap', 'cancelled_remainder', 'expired', 'expired_remainder')


class AuditStop(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _decimal(value):
    if not isinstance(value, str) or len(value) > 128:
        raise AuditStop('CORRUPT', 'invalid_decimal')
    try:
        result = Decimal(value)
        if (not result.is_finite() or len(result.as_tuple().digits) > 60
                or not -60 <= result.as_tuple().exponent <= 48 or abs(result) > Decimal('1e48')):
            raise AuditStop('CORRUPT', 'invalid_decimal')
        return result
    except DecimalException:
        raise AuditStop('CORRUPT', 'invalid_decimal') from None


def _money(value):
    return value.quantize(UNIT)


def _time(value):
    if type(value) is not int or value < 0:
        raise AuditStop('CORRUPT', 'invalid_timestamp')
    return value


@contextmanager
def _source(path):
    target = Path(path).resolve(strict=True)
    if not target.is_file():
        raise OSError('not a regular file')
    # immutable=1 is deliberately avoided: it could ignore committed WAL data.
    with closing(sqlite3.connect(target.as_uri()+'?mode=ro', uri=True, isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON')
        c.execute('PRAGMA trusted_schema=OFF')
        c.execute('PRAGMA busy_timeout=1000')
        c.execute('PRAGMA cache_size=-2048')
        c.execute('BEGIN')
        try:
            yield c
        finally:
            c.rollback()


class _Audit:
    def __init__(self, source, scratch, max_records, max_body_bytes, max_findings, max_total_body_bytes, require_domain=False, metrics=None):
        self.c, self.s = source, scratch
        self.require_domain = require_domain
        self.metrics = metrics
        self.has_domain_proofs = False
        self.max_records, self.max_body_bytes, self.max_findings = max_records, max_body_bytes, max_findings
        self.report = {'version': VERSION, 'status': 'PASS', 'checks': {s: 0 for s in STATES},
                       'records': {}, 'findings': [], 'findings_omitted': 0,
                       'scope': 'journal_accounting_and_persisted_evidence',
                       'limitations': ['not_full_execution_or_risk_decision_replay',
                                       'hashes_are_not_authenticated_signatures',
                                       'coordinated_history_rewrite_or_total_erasure_not_provable',
                                       'request_digest_preimages_not_retained',
                                       'pause_and_cancel_timestamps_not_retained',
                                       'outbox_and_unreferenced_decision_records_outside_scope']}
        self.total = 0
        self.bytes_read = 0
        self.max_total_body_bytes = max_total_body_bytes
        self.cash = {a: Decimal('10000') for a in ('AUTO', 'MANUAL')}
        self.complete = {a: True for a in self.cash}
        self.reserve = {a: ZERO for a in self.cash}
        self.pnl = {a: ZERO for a in self.cash}
        self.marked = {a: ZERO for a in self.cash}
        self.basis = {a: ZERO for a in self.cash}

    def domain_proof(self, kind, key):
        if not self.has_domain_proofs:
            return None
        row = self.s.execute('SELECT value FROM domain_proof WHERE kind=? AND k=?', (kind,key)).fetchone()
        return row[0] if row else None

    def check(self, condition, code, table='', row=0, status='MISMATCH'):
        state = 'PASS' if condition else status
        self.report['checks'][state] += 1
        if STATES.index(state) > STATES.index(self.report['status']):
            self.report['status'] = state
        if not condition:
            if len(self.report['findings']) < self.max_findings:
                self.report['findings'].append({'status': state, 'code': code, 'table': table, 'row': row})
            else:
                self.report['findings_omitted'] += 1
        return condition

    def equal(self, body, field, expected, table, row):
        return self.check(_decimal(body[field]) == expected, field, table, row)

    def load(self):
        if self.c.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise AuditStop('CORRUPT', 'sqlite_integrity')
        if (self.c.execute('PRAGMA application_id').fetchone()[0] != 0x54563244
                or self.c.execute('PRAGMA user_version').fetchone()[0] != 1):
            raise AuditStop('INCOMPLETE', 'unsupported_schema')
        required = (*TABLES, 'decision_records', 'product_meta')
        for table in required:
            if self.c.execute('SELECT type FROM sqlite_master WHERE name=?', (table,)).fetchone() != ('table',):
                raise AuditStop('INCOMPLETE', 'missing_table')
        meta = self.c.execute('SELECT version,mode FROM product_meta LIMIT 2').fetchall()
        if len(meta) != 1 or meta[0][0] != 1 or meta[0][1] not in ('fixture', 'live'):
            raise AuditStop('INCOMPLETE', 'unsupported_schema')
        self.mode = meta[0][1]
        self.s.executescript('''
            PRAGMA cache_size=-2048;
            PRAGMA temp_store=FILE;
            PRAGMA max_page_count=65536;
            CREATE TABLE records(t TEXT,k TEXT,n INTEGER,b TEXT,account TEXT,owner TEXT,event TEXT,symbol TEXT,ms INTEGER,scope TEXT,request_hash TEXT,PRIMARY KEY(t,k));
            CREATE INDEX by_owner ON records(t,owner,n);
            CREATE INDEX owner_count ON records(owner);
            CREATE INDEX by_event ON records(t,event,account);
            CREATE INDEX by_time ON records(t,symbol,ms);
        ''')
        for table in ('analyses', 'commands', 'transactions', 'events', 'decision_records'):
            for action in ('update', 'delete'):
                name = ('immutable_records_' if table == 'decision_records' else table+'_')+action
                row = self.c.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=? AND tbl_name=?", (name, table)).fetchone()
                sql = ''.join(row[0].upper().split()) if row else ''
                self.check('RAISE(ABORT' in sql and 'BEFORE'+action.upper() in sql,
                           'immutable_guard', table, status='CORRUPT')
        for table in TABLES:
            self.report['records'][table] = 0
            if self.c.execute(f'SELECT 1 FROM {table} WHERE length(CAST(body AS BLOB))>? LIMIT 1', (self.max_body_bytes,)).fetchone():
                raise AuditStop('INCOMPLETE', 'body_budget')
            cursor = self.c.execute(f'SELECT rowid,* FROM {table} ORDER BY rowid')
            columns = [d[0] for d in cursor.description]
            for row in cursor:
                self.total += 1
                if self.total > self.max_records:
                    raise AuditStop('INCOMPLETE', 'record_budget')
                data = dict(zip(columns, row))
                raw = data['body']
                if not isinstance(raw, str) or len(raw.encode()) > self.max_body_bytes:
                    raise AuditStop('INCOMPLETE', 'body_budget')
                self.bytes_read += len(raw.encode())
                if self.bytes_read > self.max_total_body_bytes:
                    raise AuditStop('INCOMPLETE', 'total_body_budget')
                body = json.loads(raw)
                if not isinstance(body, dict) or _hash(body) != data['body_hash']:
                    raise AuditStop('CORRUPT', 'body_hash')
                if table == 'accounts' and body.get('portfolio_id') not in self.cash:
                    raise AuditStop('CORRUPT', 'unknown_account')
                self.report['records'][table] += 1
                key = data.get('id') if table != 'commands' else _hash({'scope': data['scope'], 'key': data['key']})
                identity = {'accounts': 'portfolio_id', 'orders': 'order_id', 'positions': 'position_id',
                            'transactions': 'transaction_id', 'events': 'event_id', 'analyses': 'analysis_id'}.get(table)
                if identity:
                    self.check(body[identity] == key, 'record_identity', table, row[0])
                if 'portfolio' in data:
                    self.check(data['portfolio'] == body['portfolio_id'], 'portfolio_column', table, row[0])
                if 'event_id' in data:
                    self.check(data['event_id'] == body['event_id'], 'event_column', table, row[0])
                for column in ('analysis_id', 'order_id'):
                    if column in data:
                        self.check(data[column] == body[column], column+'_column', table, row[0])
                if 'data_mode' in body:
                    self.check(body['data_mode'] == self.mode, 'data_mode', table, row[0])
                self.s.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (table, key, row[0], raw, body.get('portfolio_id'), body.get('order_id', body.get('position_id')),
                     body.get('event_id'), body.get('symbol'), data.get('close_ms'), data.get('scope'), data.get('hash')))
                if table == 'commands':
                    digest = data['hash']
                    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
                        raise AuditStop('CORRUPT', 'request_digest_format')
                if table == 'commands' and data['scope'].startswith('order:'):
                    self.check(body['order_id'] == _hash({'portfolio': data['scope'][6:], 'key': data['key']}),
                               'order_command_identity', table, row[0])
                if table == 'commands' and data['scope'].startswith('close:'):
                    self.check(body['close_request_id'] == _hash({'scope': data['scope'], 'key': data['key']}),
                               'close_command_identity', table, row[0])
        self.events()

    def rows(self, table, where='', args=()):
        for key, n, body in self.s.execute('SELECT k,n,b FROM records WHERE t=? '+where+' ORDER BY n', (table, *args)):
            yield key, n, json.loads(body)

    def get(self, table, key):
        row = self.s.execute('SELECT b FROM records WHERE t=? AND k=?', (table, key)).fetchone()
        return json.loads(row[0]) if row else None

    def events(self):
        last = {}
        for key, n, receipt in self.rows('events'):
            e = receipt['market_event']
            start, end = _time(e['open_time_ms']), _time(e['close_time_ms'])
            symbol = e['symbol']
            if symbol not in ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'):
                raise AuditStop('CORRUPT', 'event_symbol')
            self.check(start % 60000 == 0 and end-start == 60000 and e['is_final'] is True, 'event_time', 'events', n)
            self.check(start >= last.get(symbol, 0), 'event_sequence', 'events', n)
            last[symbol] = end
            v = {k: _decimal(e[k]) for k in ('open', 'high', 'low', 'close', 'volume')}
            self.check(all(v[k] > 0 for k in ('open', 'high', 'low', 'close')) and v['volume'] >= 0
                       and v['high'] >= max(v['open'], v['close']) and v['low'] <= min(v['open'], v['close']),
                       'event_ohlcv', 'events', n)
            self.check(key == _hash({'mode': self.mode, 'symbol': symbol, 'open': start}), 'event_identity', 'events', n)
            indexed = self.c.execute('SELECT hash,symbol,close_ms FROM events WHERE id=?', (key,)).fetchone()
            self.check(indexed == (_hash(e), symbol, end) and receipt['close_time_ms'] == end,
                       'event_metadata', 'events', n)
            self.s.execute('UPDATE records SET symbol=?,ms=? WHERE t=? AND k=?', (symbol, end, 'events', key))

    def commands(self, key, scope):
        return self.rows('commands', 'AND owner=? AND scope=?', (key, scope))

    def record(self, key):
        cached = self.get('decision_records', key)
        if cached is not None:
            return cached
        row = self.c.execute('SELECT length(CAST(body_json AS BLOB)) FROM decision_records WHERE record_id=?', (key,)).fetchone()
        if not self.check(row is not None, 'decision_record_source', 'decision_records', status='INCOMPLETE'):
            return None
        if row[0] > self.max_body_bytes:
            raise AuditStop('INCOMPLETE', 'body_budget')
        self.total += 1
        self.bytes_read += row[0]
        if self.total > self.max_records or self.bytes_read > self.max_total_body_bytes:
            raise AuditStop('INCOMPLETE', 'record_or_body_budget')
        raw = self.c.execute('SELECT body_json FROM decision_records WHERE record_id=?', (key,)).fetchone()[0]
        body = json.loads(raw)
        if not isinstance(body, dict) or _hash(body) != key or sha256(raw.encode()).hexdigest() != key:
            raise AuditStop('CORRUPT', 'decision_record_hash')
        self.check(body.get('schema') == 'v2-decision-record-1', 'decision_record_schema', 'decision_records')
        count = self.report['records'].get('decision_records', 0)+1
        self.report['records']['decision_records'] = count
        self.s.execute('INSERT INTO records(t,k,n,b) VALUES(?,?,?,?)', ('decision_records', key, count, raw))
        return body

    def order(self, key, n, order):
        account = order['portfolio_id']
        if account not in self.cash:
            raise AuditStop('CORRUPT', 'unknown_account')
        if order['execution_model'] != MODEL:
            raise AuditStop('INCOMPLETE', 'unsupported_execution_model')
        # Bound per-order working sets as well as total disk-backed input.
        count = self.s.execute("SELECT count(*) FROM records WHERE owner=?", (key,)).fetchone()[0]
        if count > 10000:
            raise AuditStop('INCOMPLETE', 'order_record_budget')
        initial = list(self.commands(key, 'order:'+account))
        if not self.check(len(initial) == 1, 'order_ack_source', 'orders', n, status='INCOMPLETE'):
            self.complete[account] = False
            return
        ack = initial[0][2]
        if ack['execution_model'] != MODEL:
            raise AuditStop('INCOMPLETE', 'unsupported_execution_model')
        for field in ('quantity', 'levels', 'fee_rate', 'adverse_rate', 'participation_fraction',
                      'quantity_step', 'reservation_per_unit', 'risk_per_unit', 'analysis_id',
                      'symbol', 'venue', 'created_at_ms', 'expires_at_ms', 'portfolio_id', 'execution_model'):
            self.check(order[field] == ack[field], 'order_snapshot_'+field, 'orders', n)
        a = self.get('analyses', ack['analysis_id'])
        if not self.check(a is not None, 'analysis_source', 'orders', n, status='INCOMPLETE'):
            self.complete[account] = False
            return
        self.check(a['symbol'] == ack['symbol'] and a['venue'] == ack['venue'] and a['quote_currency'] == 'USDT'
                   and a['contract_type'] == 'spot' and a['market'] == 'crypto_spot' and a['levels'] == ack['levels'],
                   'instrument_and_levels', 'orders', n)
        product = self.record(ack['analysis_id'])
        if product is not None:
            r = product['result']
            self.check(r['levels'] == ack['levels'] and r['symbol'] == ack['symbol']
                       and r['quote_currency'] == 'USDT', 'analysis_record_binding', 'orders', n)
            for source_id in product['source_records'].values():
                self.record(source_id)
        step, original = _decimal(ack['quantity_step']), _decimal(ack['quantity'])
        rate, adverse, fraction = (_decimal(ack[k]) for k in ('fee_rate', 'adverse_rate', 'participation_fraction'))
        if step <= 0 or original <= 0 or not 0 <= rate < 1 or not 0 <= adverse < 1 or not 0 < fraction <= 1:
            raise AuditStop('CORRUPT', 'invalid_execution_parameters')
        self.check(step == _decimal(a['market_rules']['quantity_step']), 'instrument_quantity_step', 'orders', n)
        self.check(original % step == 0, 'order_step', 'orders', n)
        z = {k: _decimal(ack['levels'][k]) for k in ('entry_low', 'entry_high', 'invalidation', 'target_1', 'target_2')}
        self.check(0 < z['invalidation'] < z['entry_low'] <= z['entry_high'] < z['target_1'] < z['target_2'],
                   'order_geometry', 'orders', n)
        cost = max(z['entry_high'], z['target_2'])*(2*rate+2*adverse)
        self.equal(order, 'reservation_per_unit', _money(z['entry_high']+cost), 'orders', n)
        self.equal(order, 'risk_per_unit', _money(z['entry_high']-z['invalidation']+cost), 'orders', n)
        state = {'entered': ZERO, 'quantity': ZERO, 'basis': ZERO, 'pnl': ZERO, 'first': None, 'last': None, 'manual': {}}
        for txkey, tn, t in self.rows('transactions', 'AND owner=?', (key,)):
            self.transaction(txkey, tn, t, ack, z, state, step, rate, adverse)
        qty, basis = state['quantity'], state['basis']
        self.check(state['entered'] <= original and qty >= 0, 'quantity_conservation', 'orders', n)
        remaining, status = _decimal(order['remaining_quantity']), order['status']
        self.check(status in (*ACTIVE, *TERMINAL), 'order_status', 'orders', n)
        if next(self.commands(key, 'cancel:'+account), None) is not None:
            self.check(status == 'cancelled', 'cancel_ack_state', 'orders', n)
        if status in ACTIVE:
            self.check(remaining > 0 and remaining+state['entered'] == original, 'remaining_quantity', 'orders', n)
            self.check((state['entered'] == 0) == (status == 'pending'), 'active_order_status', 'orders', n)
            self.reserve[account] += remaining*_decimal(ack['reservation_per_unit'])
        else:
            self.check(remaining == 0, 'terminal_reservation', 'orders', n)
            if status == 'filled':
                self.check(state['entered'] == original, 'filled_quantity', 'orders', n)
            else:
                self.check(self.domain_proof('cancel', key) is not None, 'cancellation_timeline_not_persisted', 'orders', n, status='INCOMPLETE')
        p = self.get('positions', key)
        if state['entered'] == 0:
            self.check(p is None, 'position_without_entry', 'orders', n)
            return
        if not self.check(p is not None, 'position_missing', 'orders', n):
            return
        self.check(p['order_id'] == key and p['portfolio_id'] == account and p['symbol'] == ack['symbol'],
                   'position_ownership', 'positions', n)
        for field, expected in (('quantity', qty), ('cost_basis_quote', basis), ('realized_pnl_quote', state['pnl']),
                                ('average_entry', _money(z['entry_high']*(1+adverse)))):
            self.equal(p, field, expected, 'positions', n)
        self.check(p['status'] in ('open', 'ambiguous', 'exit_pending', 'closed'), 'position_status', 'positions', n)
        for field in ('invalidation', 'target_1', 'target_2'):
            self.equal(p, field, z[field], 'positions', n)
        self.check(p['opened_at_ms'] == state['first']-60000, 'opened_at_ms', 'positions', n)
        if qty == 0:
            self.check(p['closed_at_ms'] == state['last'], 'closed_at_ms', 'positions', n)
        self.check((qty == 0) == (p['status'] == 'closed') and basis >= 0 and (qty > 0 or basis == 0),
                   'position_closed_state', 'positions', n)
        self.pending_closes(key, n, p, state, account, step)
        self.basis[account] += basis
        end = _time(p['closed_at_ms']) if qty == 0 else 9223372036854775807
        previous = None
        for (stamp,) in self.s.execute("SELECT ms FROM records WHERE t='events' AND symbol=? AND ms>=? AND ms<=? ORDER BY ms", (ack['symbol'], state['first'], end)):
            if previous is not None and stamp != previous+60000:
                self.check(False, 'market_history_gap', 'events', status='INCOMPLETE')
            previous = stamp
        mark = self.s.execute("SELECT b FROM records WHERE t='events' AND symbol=? AND ms>=? AND ms<=? ORDER BY ms DESC LIMIT 1",
                              (ack['symbol'], state['first'], end)).fetchone()
        if self.check(mark is not None, 'mark_source', 'positions', n, status='INCOMPLETE'):
            bar = json.loads(mark[0])['market_event']
            self.check(p['mark_time_ms'] == bar['close_time_ms'], 'mark_time_ms', 'positions', n)
            self.equal(p, 'mark_price', _decimal(bar['close']), 'positions', n)
            marked = qty*_decimal(bar['close'])
            self.marked[account] += marked
            self.check(True, 'unrealized_pnl_reconstructed', 'positions', n)
            if 'unrealized_pnl_quote' in p:
                self.equal(p, 'unrealized_pnl_quote', _money(marked-basis), 'positions', n)

    def transaction(self, key, n, t, order, z, state, step, rate, adverse):
        account, kind = order['portfolio_id'], t['kind']
        qty, actual_price = _decimal(t['quantity']), _decimal(t['price'])
        self.check(qty > 0 and qty % step == 0, 'fill_step', 'transactions', n)
        if qty <= 0:
            raise AuditStop('CORRUPT', 'nonpositive_fill')
        self.check(t['portfolio_id'] == account and t['position_id'] == order['order_id'],
                   'transaction_ownership', 'transactions', n)
        self.check(key == _hash({'event': t['event_id'], 'order': order['order_id'], 'kind': kind}),
                   'transaction_identity', 'transactions', n)
        stamp = _time(t['time_ms'])
        self.check(state['last'] is None or stamp >= state['last'], 'transaction_sequence', 'transactions', n)
        state['last'] = stamp
        receipt = self.get('events', t['event_id'])
        if receipt is None:
            raise AuditStop('INCOMPLETE', 'event_source')
        e = receipt['market_event']
        self.check(e['symbol'] == order['symbol'] and e['close_time_ms'] == stamp
                   and e['open_time_ms'] >= order['created_at_ms'], 'transaction_event', 'transactions', n)
        self.check(any(p['order_id'] == order['order_id'] for p in receipt['processed']), 'receipt_order', 'transactions', n)
        if kind == 'entry':
            price = _money(z['entry_high']*(1+adverse))
            self.check(e['close_time_ms'] <= order['expires_at_ms'] and _decimal(e['open']) > z['invalidation']
                       and _decimal(e['low']) <= z['entry_high'] and _decimal(e['high']) >= z['entry_low'],
                       'entry_bar_eligibility', 'transactions', n)
        elif kind in ('take_profit_1', 'take_profit_2'):
            target = z['target_1' if kind.endswith('1') else 'target_2']
            price = _money(target*(1-adverse))
            self.check(_decimal(e['high']) >= target, 'target_touch', 'transactions', n)
        elif kind.startswith('manual_close:'):
            price = _money(_decimal(e['open'])*(1-adverse))
            cid = kind.split(':', 1)[1]
            state['manual'][cid] = state['manual'].get(cid, ZERO)+qty
        elif kind == 'stop_loss':
            candidates = {_money(min(_decimal(e['open']), z['invalidation'])*(1-adverse)),
                          _money(_decimal(e['open'])*(1-adverse))}
            self.check(actual_price in candidates, 'stop_execution_price', 'transactions', n)
            proven = self.domain_proof('stop', key)
            self.check(proven is not None, 'stop_trigger_sequence_not_replayed', 'transactions', n, status='INCOMPLETE')
            price = _decimal(proven) if proven is not None else actual_price
        else:
            raise AuditStop('INCOMPLETE', 'unsupported_transaction_kind')
        self.equal(t, 'price', price, 'transactions', n)
        gross, fee = _money(qty*price), _money(_money(qty*price)*rate)
        self.equal(t, 'fee_quote', fee, 'transactions', n)
        if kind == 'entry':
            delta, pnl = -(gross+fee), ZERO
            state['entered'] += qty
            state['quantity'] += qty
            state['basis'] += gross+fee
            if state['first'] is None:
                state['first'] = stamp
        else:
            if not self.check(0 < qty <= state['quantity'], 'exit_exceeds_entry', 'transactions', n):
                raise AuditStop('MISMATCH', 'cannot_allocate_exit_basis')
            allocated = state['basis'] if qty == state['quantity'] else _money(state['basis']*qty/state['quantity'])
            delta = gross-fee
            pnl = delta-allocated
            state['basis'] -= allocated
            state['quantity'] -= qty
            state['pnl'] += pnl
        self.equal(t, 'cash_delta_quote', delta, 'transactions', n)
        self.equal(t, 'realized_pnl_quote', pnl, 'transactions', n)
        self.cash[account] += delta
        self.pnl[account] += pnl

    def pending_closes(self, key, n, p, state, account, step):
        requests = {b['close_request_id']: b for _, _, b in self.commands(key, 'close:'+account+':'+key)}
        reserved, seen = ZERO, set()
        for item in p.get('pending_closes', []):
            cid = item['close_request_id']
            self.check(cid not in seen, 'duplicate_close_request', 'positions', n)
            seen.add(cid)
            ack = requests.get(cid)
            if not self.check(ack is not None, 'close_ack_source', 'positions', n, status='INCOMPLETE'):
                continue
            qty, used = _decimal(ack['quantity']), state['manual'].get(cid, ZERO)
            self.check(item['quantity'] == ack['quantity'] and item['created_at_ms'] == ack['created_at_ms']
                       and item['position_id'] == key, 'close_snapshot', 'positions', n)
            self.check(0 <= used <= qty and qty > 0 and qty % step == 0, 'close_quantity', 'positions', n)
            self.equal(item, 'remaining_quantity', qty-used, 'positions', n)
            self.check(item['status'] in ('pending', 'filled', 'cancelled_position_closed'), 'close_status', 'positions', n)
            if item['status'] == 'pending':
                reserved += qty-used
                self.check(qty-used > 0 and state['quantity'] > 0, 'pending_close_state', 'positions', n)
            elif item['status'] == 'filled':
                self.check(qty == used, 'filled_close_state', 'positions', n)
            else:
                self.check(state['quantity'] == 0, 'cancelled_close_state', 'positions', n)
            for _, tn, tx in self.rows('transactions', 'AND owner=?', (key,)):
                if tx['kind'] == 'manual_close:'+cid:
                    self.check(self.get('events', tx['event_id'])['market_event']['open_time_ms'] >= ack['created_at_ms'],
                               'manual_close_time', 'transactions', tn)
        self.check(seen == set(requests) and set(state['manual']).issubset(seen), 'close_request_coverage', 'positions', n)
        self.check(reserved <= state['quantity'], 'close_reservation', 'positions', n)

    def run(self):
        self.load()
        from .domain_audit import verify
        from time import perf_counter
        domain_start = perf_counter()
        self.report['domain'] = verify(self, require=self.require_domain)
        if self.metrics is not None:self.metrics['domain_seconds'] = perf_counter()-domain_start
        if self.report['domain']['status']=='PASS' and self.report['domain']['coverage']=='genesis':
            self.report['limitations'] = [x for x in self.report['limitations'] if x not in ('request_digest_preimages_not_retained','pause_and_cancel_timestamps_not_retained')]
        self.has_domain_proofs = self.s.execute("SELECT 1 FROM sqlite_master WHERE name='domain_proof'").fetchone() is not None
        for key, n, order in self.rows('orders'):
            self.order(key, n, order)
        for key, n, command in self.rows('commands'):
            row = self.s.execute("SELECT scope FROM records WHERE t='commands' AND k=?", (key,)).fetchone()
            if row[0].startswith(('order:', 'cancel:', 'close:')):
                owner = command.get('order_id', command.get('position_id'))
                order = self.get('orders', owner)
                self.check(order is not None, 'orphan_command', 'commands', n)
                if order is not None:
                    prefix = row[0].split(':', 1)[0]
                    expected = prefix+':'+order['portfolio_id']
                    if prefix == 'close':
                        expected += ':'+owner
                        self.check(self.get('positions', owner) is not None, 'close_command_position', 'commands', n)
                    self.check(row[0] == expected, 'command_ownership', 'commands', n)
        for key, n, p in self.rows('positions'):
            self.check(key == p['order_id'], 'position_order_identity', 'positions', n)
            self.check(self.get('orders', p['order_id']) is not None, 'orphan_position', 'positions', n)
        for key, n, t in self.rows('transactions'):
            self.check(self.get('orders', t['order_id']) is not None, 'orphan_transaction', 'transactions', n)
        for event, account in self.s.execute("SELECT DISTINCT event,account FROM records WHERE t='transactions'"):
            receipt = self.get('events', event)
            if receipt is None:
                continue
            fraction, used = None, ZERO
            for _, n, t in self.rows('transactions', 'AND event=? AND account=?', (event, account)):
                order = self.get('orders', t['order_id'])
                if order:
                    f = _decimal(order['participation_fraction'])
                    fraction = f if fraction is None else min(fraction, f)
                used += _decimal(t['quantity'])
            if fraction is not None:
                self.check(used <= _decimal(receipt['market_event']['volume'])*fraction,
                           'account_bar_capacity', 'transactions')
        self.check({key for key, _, _ in self.rows('accounts')} == set(self.cash), 'account_set', 'accounts')
        for key, n, a in self.rows('accounts'):
            if key not in self.cash:
                raise AuditStop('CORRUPT', 'unknown_account')
            self.equal(a, 'seed_equity_quote', Decimal('10000'), 'accounts', n)
            if not self.complete[key]:
                self.check(False, 'account_replay_incomplete', 'accounts', n, status='INCOMPLETE')
                continue
            self.equal(a, 'cash_quote', self.cash[key], 'accounts', n)
            self.check(self.cash[key] >= 0 and self.cash[key]-self.reserve[key] >= 0,
                       'cash_and_reservations_nonnegative', 'accounts', n)
            equity = self.cash[key]+self.marked[key]
            unrealized = self.marked[key]-self.basis[key]
            self.check(equity == Decimal('10000')+self.pnl[key]+unrealized,
                       'equity_pnl_conservation', 'accounts', n)
        return self.report


def audit_database(path, *, max_records=1_000_000, max_body_bytes=2_097_152, max_findings=200,
                   max_total_body_bytes=134_217_728, require_domain=False, metrics=None):
    """Existing source only; disk scratch, bounded findings, deterministic result.

    I/O errors are redacted. Cancellation propagates after resource cleanup.
    Record/body budgets return INCOMPLETE rather than a partial PASS.
    """
    for value in (max_records, max_body_bytes, max_findings, max_total_body_bytes):
        if type(value) is not int or value < 1:
            raise ValueError('Audit limits must be positive integers')
    audit = None
    try:
        with localcontext(Context(prec=60, rounding=ROUND_HALF_EVEN)):
            with _source(path) as source, TemporaryDirectory(prefix='v2-audit-scratch-') as root:
                with closing(sqlite3.connect(Path(root)/'scratch.sqlite')) as scratch:
                    audit = _Audit(source, scratch, max_records, max_body_bytes, max_findings, max_total_body_bytes, require_domain, metrics)
                    return audit.run()
    except AuditStop as exc:
        status, code = exc.status, exc.code
    except sqlite3.DatabaseError as exc:
        status = 'CORRUPT' if 'malformed' in str(exc) or 'not a database' in str(exc) else 'ERROR'
        code = 'sqlite_failure'
    except OSError:
        status, code = 'ERROR', 'source_unavailable'
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, DecimalException, RecursionError):
        status, code = 'CORRUPT', 'invalid_record_structure'
    if audit is None:
        return {'version': VERSION, 'status': status, 'checks': {s: int(s == status) for s in STATES},
                'records': {}, 'findings': [{'status': status, 'code': code, 'table': '', 'row': 0}], 'findings_omitted': 0}
    audit.check(False, code, status=status)
    return audit.report
