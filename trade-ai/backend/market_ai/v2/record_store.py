"""Opt-in append-only SQLite prototype for V2 decision/candle snapshots.

No default path, startup hook, V1 import, environment lookup or migration.
Creation refuses existing files; opening refuses databases without this
prototype's application/schema markers. Used only with temporary test DBs so
far. Does not store/execute paper orders or modify legacy MongoDB history.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3

from .decision_record import ImmutableDecisionRecord


APPLICATION_ID = 0x54563244  # TV2D
SCHEMA_VERSION = 1


class RecordStore:
    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    @classmethod
    def create_new(cls, path: str | Path) -> "RecordStore":
        """Only create a new explicit file; never replace or migrate a DB."""
        target = Path(path).resolve()
        with target.open("xb"):
            pass
        connection = sqlite3.connect(target)
        try:
            connection.executescript(f"""
                PRAGMA application_id = {APPLICATION_ID};
                PRAGMA user_version = {SCHEMA_VERSION};
                CREATE TABLE decision_records (
                    record_id TEXT PRIMARY KEY NOT NULL,
                    body_json TEXT NOT NULL
                );
                CREATE TRIGGER immutable_records_update BEFORE UPDATE ON decision_records
                BEGIN SELECT RAISE(ABORT, 'decision records are immutable'); END;
                CREATE TRIGGER immutable_records_delete BEFORE DELETE ON decision_records
                BEGIN SELECT RAISE(ABORT, 'decision records are immutable'); END;
            """)
            return cls(connection)
        except Exception:
            connection.close()
            # A failed newly created file is preserved for diagnosis, not deleted.
            raise

    @classmethod
    def open_existing(cls, path: str | Path) -> "RecordStore":
        target = Path(path).resolve()
        # URI mode=rw prevents sqlite from silently creating a missing DB.
        connection = sqlite3.connect(target.as_uri() + "?mode=rw", uri=True)
        try:
            application_id = connection.execute("PRAGMA application_id").fetchone()[0]
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if application_id != APPLICATION_ID or version != SCHEMA_VERSION:
                raise ValueError("Refusing foreign or unsupported database; no migration performed")
            columns = connection.execute("PRAGMA table_info(decision_records)").fetchall()
            triggers = {r[0] for r in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'decision_records'")}
            if ([r[1] for r in columns] != ["record_id", "body_json"]
                    or not {"immutable_records_update", "immutable_records_delete"}.issubset(triggers)):
                raise ValueError("Invalid append-only store schema")
            return cls(connection)
        except Exception:
            connection.close()
            raise

    def save(self, record: ImmutableDecisionRecord) -> bool:
        """Insert once; identical replay is a no-op. Reject corrupt input."""
        if not record.verify():
            raise ValueError("Cannot save a corrupt decision record")
        with self._connection:
            cursor = self._connection.execute(
                "INSERT INTO decision_records(record_id, body_json) VALUES (?, ?) ON CONFLICT(record_id) DO NOTHING",
                (record.record_id, record.body_json),
            )
            if cursor.rowcount == 0:
                saved = self._connection.execute(
                    "SELECT body_json FROM decision_records WHERE record_id = ?", (record.record_id,),
                ).fetchone()[0]
                if saved != record.body_json:
                    raise ValueError("Stored content does not match its record ID")
                return False
            return True

    def get(self, record_id: str) -> ImmutableDecisionRecord | None:
        row = self._connection.execute(
            "SELECT body_json FROM decision_records WHERE record_id = ?", (record_id,),
        ).fetchone()
        if row is None:
            return None
        record = ImmutableDecisionRecord(record_id, row[0])
        if not record.verify():
            raise ValueError("Stored decision record failed integrity verification")
        return record

    def record_ids(self) -> tuple[str, ...]:
        return tuple(row[0] for row in self._connection.execute(
            "SELECT record_id FROM decision_records ORDER BY record_id"))

    def backup_to_new(self, path: str | Path) -> None:
        """SQLite-consistent backup; refuses any existing destination file."""
        target = Path(path).resolve()
        with target.open("xb"):
            pass
        destination = sqlite3.connect(target)
        try:
            self._connection.backup(destination)
        finally:
            destination.close()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
