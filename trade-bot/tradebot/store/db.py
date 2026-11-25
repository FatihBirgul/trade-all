"""SQLite baglantisi ve sema kurulumu."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from importlib import resources
from pathlib import Path


def connect(path: Path | str) -> sqlite3.Connection:
    """WAL modunda baglanti acar ve semayi kurar; tekrar calistirmak guvenlidir."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(resources.files(__package__).joinpath("schema.sql").read_text(encoding="utf-8"))
    _migrate(conn)
    return conn


# Sonradan eklenen sutunlar: mevcut veritabanlarinda ALTER TABLE ile tamamlanir.
_ADDED_COLUMNS = (("trades", "last_sl", "REAL"), ("trades", "planned_tp", "REAL"), ("trades", "votes_json", "TEXT"),
                  ("bot_state", "heartbeat_at", "REAL"), ("shadow_trades", "spread", "REAL"))


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, kind in _ADDED_COLUMNS:
        present = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in present:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Acik bir islem yoksa BEGIN IMMEDIATE ... COMMIT; hata olursa ROLLBACK."""
    if conn.in_transaction:
        yield
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
