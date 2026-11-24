"""All persistence tests are confined to a fresh TemporaryDirectory."""
from dataclasses import replace
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase

from market_ai.v2.record_store import RecordStore
from market_ai.v2.decision_record import replay_analysis
from tests.test_v2_decision_record import analysis, risk


class RecordStoreTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="trade-ai-v2-records-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "isolated.sqlite"

    def test_snapshot_survives_close_reopen_and_replay_is_idempotent(self):
        record = analysis()
        with RecordStore.create_new(self.path) as store:
            self.assertTrue(store.save(record))
            self.assertFalse(store.save(record))
            self.assertEqual(store.record_ids(), (record.record_id,))
        with RecordStore.open_existing(self.path) as store:
            self.assertEqual(store.get(record.record_id), record)
            self.assertFalse(store.save(record))
            self.assertEqual(replay_analysis(store.get(record.record_id)).status, "matched")

    def test_reanalysis_and_paper_risk_append_without_replacing_original(self):
        first, second = analysis(), analysis(data_version="revised")
        paper = risk(first)
        with RecordStore.create_new(self.path) as store:
            for record in (first, second, paper):
                self.assertTrue(store.save(record))
            self.assertEqual(len(store.record_ids()), 3)
            self.assertEqual(store.get(first.record_id), first)
            self.assertEqual(store.get(paper.record_id).payload()["analysis_record_id"], first.record_id)

    def test_existing_file_is_never_overwritten(self):
        self.path.write_bytes(b"fixture-content-to-preserve")
        with self.assertRaises(FileExistsError):
            RecordStore.create_new(self.path)
        self.assertEqual(self.path.read_bytes(), b"fixture-content-to-preserve")

    def test_foreign_database_is_refused_without_modification(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("CREATE TABLE fixture_data (value TEXT)")
            connection.execute("INSERT INTO fixture_data VALUES ('preserve')")
        before = self.path.read_bytes()
        with self.assertRaises(ValueError):
            RecordStore.open_existing(self.path)
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_database_is_not_silently_created(self):
        with self.assertRaises(sqlite3.OperationalError):
            RecordStore.open_existing(self.path)
        self.assertFalse(self.path.exists())

    def test_update_and_delete_are_blocked_by_database(self):
        record = analysis()
        with RecordStore.create_new(self.path) as store:
            store.save(record)
            with closing(sqlite3.connect(self.path)) as connection, connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("UPDATE decision_records SET body_json='{}'")
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("DELETE FROM decision_records")
            self.assertEqual(store.get(record.record_id), record)

    def test_corrupt_record_is_rejected_and_no_row_is_saved(self):
        record = replace(analysis(), record_id="corrupt")
        with RecordStore.create_new(self.path) as store:
            with self.assertRaises(ValueError):
                store.save(record)
            self.assertEqual(store.record_ids(), ())

    def test_sqlite_consistent_backup_and_restore_preserve_records(self):
        record = analysis()
        backup = Path(self.directory.name) / "backup.sqlite"
        with RecordStore.create_new(self.path) as store:
            store.save(record)
            store.backup_to_new(backup)
            with self.assertRaises(FileExistsError):
                store.backup_to_new(backup)
        with RecordStore.open_existing(backup) as restored:
            self.assertEqual(restored.get(record.record_id), record)
            self.assertFalse(restored.save(record))

    def test_unknown_record_returns_explicit_missing_result(self):
        with RecordStore.create_new(self.path) as store:
            self.assertIsNone(store.get("missing"))

    def test_database_corruption_is_detected_on_read(self):
        record = analysis()
        with RecordStore.create_new(self.path) as store:
            store.save(record)
            # Intentional corruption of this disposable fixture only.
            with closing(sqlite3.connect(self.path)) as connection, connection:
                connection.execute("DROP TRIGGER immutable_records_update")
                connection.execute("UPDATE decision_records SET body_json='{}'")
            with self.assertRaises(ValueError):
                store.get(record.record_id)
        with self.assertRaises(ValueError):
            RecordStore.open_existing(self.path)
