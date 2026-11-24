"""Opt-in domain extension v1. Same-connection trigger capture, never a side DB.

Sequence follows SQLite's write lock, not wall time. SHA-256 is a checksum chain,
not an authenticated signature. No HTTP/security/session payload is accepted.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
import sqlite3

VERSION = 1
ZERO_HASH = '0'*64
MUTABLE = ('accounts', 'orders', 'positions', 'scanner_state', 'watchlist', 'scanner_jobs',
           'analysis_tracking', 'analysis_tracking_state', 'notification_delivery_state')
FACTS = ('transactions', 'events', 'commands', 'analyses', 'notifications', 'strategy_profiles', 'equity_snapshots', 'notification_delivery_attempts','notification_controls')
CORE = ('accounts', 'orders', 'positions', 'transactions', 'events', 'commands', 'analyses')
FIELDS = {
    'notification':{'portfolio_id','preferences_digest'},
    'profile': {'portfolio_id','profile_digest','parent_id'},
    'order': {'analysis_id', 'quantity'},
    'cancel': {'order_id'},
    'close': {'quantity', 'idempotency_key'},
    'analyze': {'symbol', 'market', 'timeframe', 'timeframes', 'data_mode', 'risk_portfolio',
                'fixture_case', 'auto_paper', 'idempotency_key', 'profile_id'},
}


class Connection(sqlite3.Connection):
    domain_session = None

    def close(self):
        self.domain_session = None
        super().close()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode()).hexdigest()


def marker(c):
    columns = {r[1] for r in c.execute('PRAGMA table_info(product_meta)')}
    version = c.execute('SELECT domain_version FROM product_meta').fetchone()[0] if 'domain_version' in columns else 0
    present = c.execute("SELECT 1 FROM sqlite_master WHERE name LIKE 'domain_%' LIMIT 1").fetchone()
    if version not in (0, VERSION) or (version == 0 and present):
        raise sqlite3.DatabaseError('Unsupported or partial domain extension')
    return bool(version)


def _capture_sql(table, action):
    old = 'NULL' if action == 'insert' else 'OLD.body'
    identity = "json_object('scope',NEW.scope,'key',NEW.key)" if table == 'commands' else 'NEW.id'
    return (f'CREATE TRIGGER domain_capture_{table}_{action} AFTER {action.upper()} ON {table} '
            + ('WHEN OLD.body IS NOT NEW.body ' if action == 'update' else '')
            + f"BEGIN SELECT domain_capture('{table}',{identity},{old},NEW.body); END")


def _delete_sql(table):
    return f"CREATE TRIGGER domain_capture_{table}_delete BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT,'domain deletion forbidden'); END"


def _guard_sql(table, action):
    return (f'CREATE TRIGGER {table}_{action} BEFORE {action.upper()} ON {table} BEGIN '
            + ("SELECT domain_internal(); END" if action == 'insert' or table == 'domain_head'
               else "SELECT RAISE(ABORT,'immutable domain history'); END"))


def validate_schema(c):
    """Fail closed on partial schema, missing capture/immutable guards or head."""
    if not marker(c):
        raise sqlite3.DatabaseError('Domain journal is required')
    objects = {r[0]: (r[1], r[2]) for r in c.execute('SELECT name,type,sql FROM sqlite_master')}
    for name in ('domain_meta', 'domain_head', 'domain_tables', 'domain_events'):
        if objects.get(name, (None,))[0] != 'table':
            raise sqlite3.DatabaseError('Missing domain table')
    for name in ('domain_account_sequence', 'domain_source_sequence'):
        expected_columns = ['portfolio_id','sequence'] if name=='domain_account_sequence' else ['source_id','sequence']
        if objects.get(name, (None,))[0] != 'index' or [r[2] for r in c.execute(f'PRAGMA index_info({name})')] != expected_columns:
            raise sqlite3.DatabaseError('Missing or changed domain index')
    meta = c.execute('SELECT version,body,body_hash FROM domain_meta').fetchall()
    if len(meta) != 1 or meta[0][0] != VERSION or digest(json.loads(meta[0][1])) != meta[0][2]:
        raise sqlite3.DatabaseError('Invalid domain metadata')
    tables = {r[0] for r in c.execute('SELECT name FROM domain_tables')}
    if not set(CORE).issubset(tables) or not tables.issubset(set(MUTABLE+FACTS)):
        raise sqlite3.DatabaseError('Invalid domain table registry')
    expected = []
    for table in tables:
        if objects.get(table, (None,))[0] != 'table':
            raise sqlite3.DatabaseError('Missing protected table')
        expected += [_capture_sql(table, 'insert'), _delete_sql(table)]
        if table in MUTABLE:
            expected.append(_capture_sql(table, 'update'))
    for table in ('domain_events', 'domain_meta', 'domain_tables', 'domain_head'):
        expected += [_guard_sql(table, action) for action in ('insert', 'update', 'delete')]
    for action in ('insert', 'update', 'delete'):
        expected.append(f"CREATE TRIGGER domain_product_meta_{action} BEFORE {action.upper()} ON product_meta BEGIN SELECT RAISE(ABORT,'immutable domain mode'); END")
    for sql in expected:
        name = sql.split()[2]
        actual = objects.get(name, (None, None))[1]
        if not actual or ''.join(actual.split()) != ''.join(sql.split()):
            raise sqlite3.DatabaseError('Missing or changed domain guard')
    head = c.execute('SELECT id,sequence,event_hash FROM domain_head').fetchall()
    tail = c.execute('SELECT sequence,event_hash FROM domain_events ORDER BY sequence DESC LIMIT 1').fetchone()
    if len(head) != 1 or head[0][0] != 1 or tail != head[0][1:]:
        raise sqlite3.DatabaseError('Domain head does not match tail')


def append(c, event_type, payload, *, effective_at=None, portfolio_id=None, source=None):
    session = c.domain_session
    if session is None:
        return None
    if not c.in_transaction:
        raise sqlite3.ProgrammingError('Domain append requires an existing transaction')
    now = session.clock()
    effective = session.effective if effective_at is None else effective_at
    if type(now) is not int or now < 0 or type(effective) is not int or effective < 0:
        raise ValueError('UTC epoch integer required')
    seq, previous = c.execute('SELECT sequence,event_hash FROM domain_head WHERE id=1').fetchone()
    if portfolio_id is None and session.command:
        parts = session.command['scope'].split(':')
        portfolio_id = parts[1] if len(parts)>1 and parts[1] in ('AUTO','MANUAL') else None
    body = dict(schema_version=VERSION, sequence=seq+1, event_type=event_type,
                recorded_at_ms=now, effective_at_ms=effective, portfolio_id=portfolio_id,
                source=source if source is not None else session.source,
                command=session.command, payload=payload, previous_event_hash=previous)
    event_hash = digest(body)
    event_id = digest({'schema_version':VERSION, 'sequence':seq+1, 'event_hash':event_hash})
    raw = canonical(body)
    if len(raw.encode()) > 2_097_152:
        raise ValueError('Domain event exceeds body budget')
    session.internal = True
    try:
        c.execute('INSERT INTO domain_events VALUES(?,?,?,?,?,?)',
                  (seq+1, event_id, event_hash, portfolio_id, (body['source'] or {}).get('event_id'), raw))
        c.execute('UPDATE domain_head SET sequence=?,event_hash=? WHERE id=1', (seq+1,event_hash))
    finally:
        session.internal = False
    return event_id


class Session:
    def __init__(self, c, clock):
        self.c, self.clock = c, clock
        self.internal = False
        self.effective = clock()
        self.source = None
        self.command = None
        self.pending = None
        self.failure = None

    def guard(self):
        if not self.internal:
            raise sqlite3.OperationalError('Direct domain mutation forbidden')
        return 1

    def capture(self, table, key, old_raw, new_raw):
        new = json.loads(new_raw)
        old = json.loads(old_raw) if old_raw is not None else None
        account = new.get('portfolio_id')
        if table == 'commands':
            identity = json.loads(key)
            ref = {'table':table, **identity, 'body_hash':digest(new)}
        else:
            ref = {'table':table, 'id':key, 'body_hash':digest(new)}
        if table in FACTS:
            append(self.c, 'record.created', ref, portfolio_id=account)
            return 1
        changed = set(new) | set(old or {})
        changed = {k for k in changed if old is None or old.get(k) != new.get(k) or (k in old) != (k in new)}
        payload = dict(table=table, id=key, before_hash=digest(old) if old is not None else None,
                       after_hash=digest(new), before={k:old[k] for k in changed if old is not None and k in old},
                       after={k:new[k] for k in changed if k in new})
        append(self.c, 'state.changed', payload, portfolio_id=account)
        return 1


def bind(c, clock):
    session = Session(c, clock)
    c.domain_session = session
    c.create_function('domain_internal', 0, session.guard)
    c.create_function('domain_capture', 4, session.capture)
    return session


def attach(c):
    """Protect newly introduced scanner/follow tables in their own transaction."""
    session = getattr(c, 'domain_session', None)
    if session is None:
        return
    existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    registered = {r[0] for r in c.execute('SELECT name FROM domain_tables')}
    for table in (*MUTABLE, *FACTS):
        if table not in existing or table in registered:
            continue
        session.internal = True
        try:
            c.execute('INSERT INTO domain_tables VALUES(?)', (table,))
        finally:
            session.internal = False
        append(c, 'schema.table_registered', {'table':table})
        c.execute(_capture_sql(table, 'insert'))
        c.execute(_delete_sql(table))
        if table in MUTABLE:
            c.execute(_capture_sql(table, 'update'))
            for key, raw, checksum in c.execute(f'SELECT id,body,body_hash FROM {table} ORDER BY rowid'):
                body = json.loads(raw)
                if digest(body) != checksum:
                    raise ValueError('Corrupt baseline projection')
                append(c, 'state.baseline', {'table':table, 'id':key, 'body':body, 'body_hash':checksum},
                       portfolio_id=body.get('portfolio_id'))


def install(c, clock, *, coverage='legacy_boundary'):
    """Explicit transaction only. Does not open paths, commit, or backfill history."""
    if not c.in_transaction:
        raise ValueError('An explicit migration transaction is required')
    if marker(c):
        validate_schema(c)
        return False
    columns = {r[1] for r in c.execute('PRAGMA table_info(product_meta)')}
    if 'domain_version' not in columns:
        c.execute('ALTER TABLE product_meta ADD COLUMN domain_version INTEGER NOT NULL DEFAULT 0')
    c.execute('UPDATE product_meta SET domain_version=?', (VERSION,))
    existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    cutoffs = {t:c.execute(f'SELECT COALESCE(MAX(rowid),0) FROM {t}').fetchone()[0] for t in (*CORE,'notifications','strategy_profiles','equity_snapshots','notification_delivery_attempts','notification_controls') if t in existing}
    meta = {'schema_version':VERSION, 'coverage':coverage, 'legacy_cutoffs':cutoffs,
            'execution_model':'next_closed_bar_touch_worst_edge_v1', 'api_contract':'v2-backend-1'}
    for sql in (
        'CREATE TABLE domain_meta(version INTEGER NOT NULL,body TEXT NOT NULL,body_hash TEXT NOT NULL)',
        'CREATE TABLE domain_head(id INTEGER PRIMARY KEY CHECK(id=1),sequence INTEGER NOT NULL,event_hash TEXT NOT NULL)',
        'CREATE TABLE domain_tables(name TEXT PRIMARY KEY)',
        'CREATE TABLE domain_events(sequence INTEGER PRIMARY KEY,event_id TEXT NOT NULL UNIQUE,event_hash TEXT NOT NULL UNIQUE,portfolio_id TEXT,source_id TEXT,body TEXT NOT NULL)',
        'CREATE INDEX domain_account_sequence ON domain_events(portfolio_id,sequence)',
        'CREATE INDEX domain_source_sequence ON domain_events(source_id,sequence)',
    ):
        c.execute(sql)
    c.execute('INSERT INTO domain_meta VALUES(?,?,?)', (VERSION,canonical(meta),digest(meta)))
    c.execute('INSERT INTO domain_head VALUES(1,0,?)', (ZERO_HASH,))
    for table in ('domain_events','domain_meta','domain_tables','domain_head'):
        for action in ('insert','update','delete'):
            c.execute(_guard_sql(table,action))
    for action in ('insert','update','delete'):
        c.execute(f"CREATE TRIGGER domain_product_meta_{action} BEFORE {action.upper()} ON product_meta BEGIN SELECT RAISE(ABORT,'immutable domain mode'); END")
    bind(c, clock)
    append(c, 'coverage.started', meta)
    attach(c)
    validate_schema(c)
    return True


def begin(c, *, effective_at, source=None, command=None):
    session = getattr(c, 'domain_session', None)
    if session:
        session.effective, session.source, session.command = effective_at, source, command
        session.pending = {'source':source, 'command':command, 'effective_at':effective_at}
    return session


def blocked(c, effective_at, source):
    session=getattr(c,'domain_session',None)
    if session is None:return
    if session.pending and session.pending.get('command') is not None:
        session.source=source;session.effective=effective_at
        session.pending['source']=source;session.pending['effective_at']=effective_at
    else:begin(c,effective_at=effective_at,source=source)


def request(c, scope, key, preimage):
    session = getattr(c, 'domain_session', None)
    if not session:
        return
    kind = scope.split(':', 1)[0]
    if kind not in FIELDS or not set(preimage).issubset(FIELDS[kind]):
        raise ValueError('Unapproved domain command fields')
    # JSON copy excludes mutable aliases. Fields are already normalized by models.
    if any(isinstance(v, dict) or (isinstance(v, str) and len(v)>128) for v in preimage.values()):
        raise ValueError('Unapproved domain command value')
    normalized = json.loads(canonical(preimage))
    command = dict(scope=scope, key=key, command_id=digest({'scope':scope,'key':key}), request_digest=digest(normalized))
    if session.pending and session.pending.get('command')==command and session.pending.get('preimage')==normalized:
        return
    begin(c, effective_at=session.clock(), command=command)
    session.pending['preimage'] = normalized
    append(c, 'command.requested', {'preimage':normalized})


def replayed(c, response):
    if getattr(c, 'domain_session', None):
        append(c, 'command.replayed', {'response_hash':digest(response)})
        c.domain_session.pending = None


def accepted(c, scope, key, preimage, response):
    session = getattr(c, 'domain_session', None)
    if not session:
        return
    kind = scope.split(':', 1)[0]
    if kind not in FIELDS or not set(preimage).issubset(FIELDS[kind]) or any(isinstance(v,dict) or (isinstance(v,str) and len(v)>128) for v in preimage.values()):
        raise ValueError('Unapproved domain command fields')
    # remember may follow nested AUTO placement; bind the original final scope.
    command = dict(scope=scope,key=key,command_id=digest({'scope':scope,'key':key}),request_digest=digest(preimage))
    session.command = command
    append(c, 'command.accepted', {'preimage':preimage, 'response_hash':digest(response)})
    session.pending = None


def note(c, event_type, payload, portfolio_id=None):
    if getattr(c, 'domain_session', None):
        if event_type == 'risk.evaluated' and c.domain_session.pending is not None:
            c.domain_session.pending['decision'] = payload
        return append(c, event_type, payload, portfolio_id=portfolio_id)


def validate_chain(c):
    """Backup/startup utility. Independent auditor implements its own checks."""
    validate_schema(c)
    previous, count = ZERO_HASH, 0
    for sequence, event_id, event_hash, portfolio, source, raw in c.execute('SELECT * FROM domain_events ORDER BY sequence'):
        body = json.loads(raw)
        count += 1
        if (sequence != count or type(body['schema_version']) is not int or body['schema_version'] != VERSION or body['sequence'] != count
                or body['previous_event_hash'] != previous or digest(body) != event_hash
                or event_id != digest({'schema_version':VERSION,'sequence':count,'event_hash':event_hash})
                or body['portfolio_id'] != portfolio or (body['source'] or {}).get('event_id') != source):
            raise ValueError('Domain chain integrity failed')
        previous = event_hash
    return count
