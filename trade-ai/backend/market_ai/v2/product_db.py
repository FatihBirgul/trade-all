"""Explicit V2-only database. Short atomic transactions, append-only audit.

Never opens MongoDB or migrates a prototype/user database automatically.
Runtime mode is fixed on creation to prevent fixture/live history mixing.
"""
from contextlib import contextmanager
from pathlib import Path
from hashlib import sha256
import json
import sqlite3
import time

from . import domain_journal as domain

from .record_store import RecordStore
from .errors import V2Error


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return sha256(encode(value).encode()).hexdigest()


class ProductDatabase:
    def __init__(self, path, mode, *, domain_journal=False, clock=None):
        self.path = Path(path).resolve()
        self.clock = clock or (lambda: int(time.time()*1000))
        self.domain_enabled = False
        created = not self.path.exists()
        if mode not in ("live", "fixture"):
            raise ValueError("Explicit live/fixture mode required")
        if not self.path.exists():
            # Parent creation is explicit application state, never a user DB migration.
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with RecordStore.create_new(self.path):
                pass
            with self.transaction() as c:
                for sql in (
                    "CREATE TABLE product_meta(version INTEGER NOT NULL, mode TEXT NOT NULL)",
                    "CREATE TABLE accounts(id TEXT PRIMARY KEY, body TEXT NOT NULL, body_hash TEXT NOT NULL)",
                    "CREATE TABLE analyses(id TEXT PRIMARY KEY, created_ms INTEGER NOT NULL, body TEXT NOT NULL, body_hash TEXT NOT NULL)",
                    "CREATE TABLE commands(scope TEXT, key TEXT, hash TEXT NOT NULL, body TEXT NOT NULL, body_hash TEXT NOT NULL, PRIMARY KEY(scope,key))",
                    "CREATE TABLE orders(id TEXT PRIMARY KEY, portfolio TEXT NOT NULL, analysis_id TEXT NOT NULL, signal_key TEXT NOT NULL, body TEXT NOT NULL, body_hash TEXT NOT NULL)",
                    "CREATE UNIQUE INDEX auto_closed_bar_signal ON orders(signal_key) WHERE portfolio='AUTO'",
                    "CREATE TABLE positions(id TEXT PRIMARY KEY, portfolio TEXT NOT NULL, order_id TEXT NOT NULL UNIQUE, body TEXT NOT NULL, body_hash TEXT NOT NULL)",
                    "CREATE TABLE transactions(id TEXT PRIMARY KEY, portfolio TEXT NOT NULL, event_id TEXT NOT NULL, body TEXT NOT NULL, body_hash TEXT NOT NULL)",
                    "CREATE TABLE events(id TEXT PRIMARY KEY, hash TEXT NOT NULL, symbol TEXT NOT NULL, close_ms INTEGER NOT NULL, body TEXT NOT NULL, body_hash TEXT NOT NULL)",
                    "CREATE INDEX analysis_time ON analyses(created_ms DESC,id)",
                    "CREATE INDEX order_account ON orders(portfolio,id)",
                    "CREATE INDEX position_account ON positions(portfolio,id)",
                    "CREATE INDEX transaction_account ON transactions(portfolio,id)",
                ):
                    c.execute(sql)
                for table in ("analyses", "commands", "transactions", "events"):
                    for operation in ("UPDATE", "DELETE"):
                        c.execute(f"CREATE TRIGGER {table}_{operation.lower()} BEFORE {operation} ON {table} "
                                  "BEGIN SELECT RAISE(ABORT, 'immutable audit history'); END")
                c.execute("INSERT INTO product_meta VALUES(1,?)", (mode,))
                for name in ("AUTO", "MANUAL"):
                    self.put(c, "accounts", name, {"portfolio_id": name, "cash_quote": "10000",
                        "seed_equity_quote": "10000", "paused": False, "data_mode": mode})
        else:
            with RecordStore.open_existing(self.path):
                pass
            with self.transaction() as c:
                try:
                    metadata = c.execute("SELECT version,mode FROM product_meta").fetchone()
                except sqlite3.DatabaseError as exc:
                    raise ValueError("Not a V2 product DB; automatic migration refused") from exc
                if metadata != (1, mode):
                    raise ValueError("Product schema or live/fixture mode mismatch")
        self.mode = mode
        with self.transaction() as c:
            enabled = domain.marker(c)
            if domain_journal and not enabled:
                if not created:
                    raise ValueError('Explicit copy migration required for existing legacy database')
                domain.install(c, self.clock, coverage='genesis')
                enabled = True
            if enabled:
                domain.validate_chain(c)
        self.domain_enabled = enabled

    @contextmanager
    def transaction(self):
        c = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, isolation_level=None, factory=domain.Connection)
        try:
            c.execute("PRAGMA busy_timeout=5000")
            c.execute("BEGIN IMMEDIATE")
            if self.domain_enabled:
                domain.validate_schema(c)
                domain.bind(c, self.clock)
                c.execute('SAVEPOINT domain_work')
            try:
                yield c
            except V2Error as exc:
                session = c.domain_session
                if session is None or session.pending is None:
                    raise
                pending = session.pending
                c.execute('ROLLBACK TO domain_work')
                session.source, session.command = pending['source'], pending['command']
                session.effective = pending['effective_at']
                domain.append(c, 'command.rejected' if pending['command'] else 'operation.rejected',
                              {'reason':exc.code, 'preimage':pending.get('preimage'), 'decision':pending.get('decision')})
                c.commit()
                raise
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    @staticmethod
    def decode(row):
        try:
            body=json.loads(row[0])
            if not isinstance(body,dict) or fingerprint(body) != row[1]:
                raise ValueError("checksum mismatch")
            return body
        except (ValueError,TypeError) as exc:
            raise V2Error("STORAGE_CORRUPT", "Stored state failed integrity checks; no automatic repair", 503) from exc

    @staticmethod
    def get(c, table, key):
        # Table names are internal constants, never request parameters.
        row = c.execute(f"SELECT body,body_hash FROM {table} WHERE id=?", (key,)).fetchone()
        return ProductDatabase.decode(row) if row else None

    @staticmethod
    def rows(c, table, portfolio=None):
        if portfolio is None:
            rows = c.execute(f"SELECT body,body_hash FROM {table} ORDER BY rowid")
        else:
            rows = c.execute(f"SELECT body,body_hash FROM {table} WHERE portfolio=? ORDER BY rowid", (portfolio,))
        return [ProductDatabase.decode(row) for row in rows]

    @staticmethod
    def put(c, table, key, body, **columns):
        names = ["id", "body", "body_hash", *columns]
        values = [key, encode(body), fingerprint(body), *columns.values()]
        c.execute(f"INSERT INTO {table}({','.join(names)}) VALUES({','.join('?' for _ in values)})", values)

    @staticmethod
    def update(c, table, key, body):
        if table not in ("orders", "positions", "accounts", "watchlist", "scanner_state", "scanner_jobs"):
            raise ValueError("Immutable table")
        c.execute(f"UPDATE {table} SET body=?,body_hash=? WHERE id=?", (encode(body), fingerprint(body), key))

    @staticmethod
    def command(c, scope, key, request):
        domain.request(c, scope, key, request)
        row = c.execute("SELECT hash,body,body_hash FROM commands WHERE scope=? AND key=?", (scope, key)).fetchone()
        if row:
            if row[0] != fingerprint(request):
                raise V2Error("IDEMPOTENCY_CONFLICT", "This key already belongs to a different request")
            response = ProductDatabase.decode((row[1],row[2]))
            domain.replayed(c, response)
            return response

    @staticmethod
    def remember(c, scope, key, request, response):
        c.execute("INSERT INTO commands VALUES(?,?,?,?,?)", (scope, key, fingerprint(request), encode(response), fingerprint(response)))
        domain.accepted(c, scope, key, request, response)

    @staticmethod
    def record(c, record):
        if not record.verify():
            raise ValueError("Invalid immutable record")
        cursor = c.execute("INSERT INTO decision_records VALUES(?,?) ON CONFLICT(record_id) DO NOTHING",
                           (record.record_id, record.body_json))
        if cursor.rowcount == 0:
            saved = c.execute("SELECT body_json FROM decision_records WHERE record_id=?", (record.record_id,)).fetchone()[0]
            if saved != record.body_json:
                raise V2Error("STORAGE_CORRUPT", "Immutable snapshot content mismatches its identifier", 503)
