"""Explicit standalone append-only preregistration/result registry.

This local registry controls only experiments routed through it. It cannot prove
that a user never inspected data elsewhere, authenticate a provider, or turn a
synthetic OOS result into market/forward validation. No financial DB is opened.
"""
from contextlib import closing,contextmanager
from pathlib import Path
import json,sqlite3
from .product_db import encode,fingerprint

class ResearchRegistry:
    def __init__(self,path):
        self.path=Path(path).resolve(strict=True)
        with closing(sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)) as c:
            try:
                if c.execute('SELECT version FROM research_registry_meta').fetchall()!=[(1,)]:raise ValueError()
                objects={r[0] for r in c.execute("SELECT name FROM sqlite_master")}
                required={'research_protocols','research_windows','research_results','research_stream_time'}|{f'{t}_{op}' for t in ('research_protocols','research_windows','research_results','research_registry_meta') for op in ('update','delete')}
                if not required<=objects:raise ValueError()
            except sqlite3.DatabaseError:raise ValueError('Not a supported standalone research registry') from None

    @classmethod
    def create(cls,path):
        path=Path(path).resolve()
        with path.open('xb'):pass  # Explicit new file only; never migrate any existing DB.
        try:
            with closing(sqlite3.connect(path)) as c:
                c.execute('BEGIN IMMEDIATE')
                c.execute('CREATE TABLE research_registry_meta(version INTEGER NOT NULL)');c.execute('INSERT INTO research_registry_meta VALUES(1)')
                c.execute('CREATE TABLE research_protocols(id TEXT PRIMARY KEY,body TEXT NOT NULL,body_hash TEXT NOT NULL)')
                c.execute('CREATE TABLE research_windows(experiment_id TEXT NOT NULL,stream TEXT NOT NULL,start_ms INTEGER NOT NULL,end_ms INTEGER NOT NULL,PRIMARY KEY(experiment_id,start_ms,end_ms))')
                c.execute('CREATE INDEX research_stream_time ON research_windows(stream,start_ms,end_ms)')
                c.execute('CREATE TABLE research_results(id TEXT PRIMARY KEY,body TEXT NOT NULL,body_hash TEXT NOT NULL)')
                for table in ('research_protocols','research_windows','research_results','research_registry_meta'):
                    for op in ('UPDATE','DELETE'):
                        c.execute(f"CREATE TRIGGER {table}_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable research registry'); END")
                c.commit()
            return cls(path)
        except BaseException:
            path.unlink(missing_ok=True);raise  # Only this exclusive newly-created file.

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.path.as_uri()+'?mode=rw',uri=True)) as c:
            c.execute('PRAGMA busy_timeout=5000');c.execute('BEGIN IMMEDIATE')
            try:yield c;c.commit()
            except BaseException:c.rollback();raise

    @staticmethod
    def decode(row):
        body=json.loads(row[0])
        if fingerprint(body)!=row[1]:raise ValueError('Research registry checksum mismatch')
        return body

    def register(self,protocol,stream,windows):
        key=fingerprint(protocol)
        if not windows or len(windows)>10 or any(type(a) is not int or type(b) is not int or not 0<=a<b for a,b in windows):raise ValueError('Bounded UTC held-out windows required')
        registration={'schema_version':1,'protocol':json.loads(encode(protocol)),'stream':stream,'windows':[list(w) for w in windows]}
        with self.transaction() as c:
            old=c.execute('SELECT body,body_hash FROM research_protocols WHERE id=?',(key,)).fetchone()
            if old:
                if self.decode(old)!=registration:raise ValueError('Protocol registration mismatch')
                return key
            for start,end in windows:
                if c.execute('SELECT 1 FROM research_windows WHERE stream=? AND start_ms<? AND end_ms>? LIMIT 1',(stream,end,start)).fetchone():
                    raise ValueError('Held-out interval already preregistered for this instrument/source; cross-protocol optimization is not new OOS evidence')
            c.execute('INSERT INTO research_protocols VALUES(?,?,?)',(key,encode(registration),fingerprint(registration)))
            c.executemany('INSERT INTO research_windows VALUES(?,?,?,?)',[(key,stream,a,b) for a,b in windows])
        return key

    def result(self,key):
        with closing(sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)) as c:
            row=c.execute('SELECT body,body_hash FROM research_results WHERE id=?',(key,)).fetchone()
            return self.decode(row) if row else None

    def save_result(self,key,report):
        serialized=encode(report)
        if len(serialized)>4*1024*1024:raise ValueError('Registry result exceeds4MiB budget')
        with self.transaction() as c:
            source=c.execute('SELECT body,body_hash FROM research_protocols WHERE id=?',(key,)).fetchone()
            if source is None:raise ValueError('Preregister before evaluation')
            protocol=self.decode(source)['protocol']
            if key!=report.get('experiment_id') or fingerprint({k:report.get(k) for k in protocol})!=fingerprint(protocol):raise ValueError('Result does not match immutable protocol')
            row=c.execute('SELECT body,body_hash FROM research_results WHERE id=?',(key,)).fetchone()
            if row:
                if self.decode(row)!=report:raise ValueError('Frozen result conflict')
                return
            c.execute('INSERT INTO research_results VALUES(?,?,?)',(key,serialized,fingerprint(report)))
