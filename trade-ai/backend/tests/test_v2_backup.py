"""Verified SQLite copies preserve source, modes and user files."""
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import closing
from unittest import TestCase
import sqlite3
from scripts.backup_v2 import copy_database, validate
from market_ai.v2.api import create_app
from market_ai.v2.errors import V2Error


class BackupTests(TestCase):
    def test_backup_restore_reopen_preserves_mode_accounts_and_source(self):
        with TemporaryDirectory(prefix="v2-backup-test-") as root:
            root=Path(root);source=root/"source.sqlite";backup=root/"backup.sqlite";restore=root/"restored.sqlite"
            create_app(source,mode="fixture",token="backup-test-token-not-a-secret-32")
            before=source.read_bytes()
            self.assertEqual(copy_database(source,backup)["mode"],"fixture")
            self.assertEqual(source.read_bytes(),before)
            copy_database(backup,restore)
            app=create_app(restore,mode="fixture",token="backup-test-token-not-a-secret-32")
            with app.state.v2.db.transaction() as c:
                self.assertEqual(len(app.state.v2.db.rows(c,"accounts")),2)
            with closing(sqlite3.connect(restore)) as c:self.assertEqual(validate(c),"fixture")

    def test_existing_target_never_overwritten_and_source_never_created(self):
        with TemporaryDirectory(prefix="v2-backup-test-") as root:
            root=Path(root);source=root/"source.sqlite";target=root/"user-file.txt"
            create_app(source,mode="fixture",token="backup-test-token-not-a-secret-32")
            target.write_text("preserve this user file")
            with self.assertRaises(FileExistsError):copy_database(source,target)
            self.assertEqual(target.read_text(),"preserve this user file")
            with self.assertRaises(ValueError):copy_database(root/"missing.sqlite",root/"out.sqlite")
            self.assertFalse((root/"missing.sqlite").exists())
            with self.assertRaises(ValueError):copy_database(source,source)

    def test_corrupt_projection_rejected_and_only_new_output_cleaned_up(self):
        with TemporaryDirectory(prefix="v2-backup-test-") as root:
            root=Path(root);source=root/"source.sqlite";target=root/"bad-copy.sqlite"
            create_app(source,mode="fixture",token="backup-test-token-not-a-secret-32")
            with closing(sqlite3.connect(source)) as c:
                c.execute("UPDATE accounts SET body_hash='broken' WHERE id='AUTO'");c.commit()
            before=source.read_bytes()
            with self.assertRaises(V2Error):copy_database(source,target)
            self.assertFalse(target.exists());self.assertEqual(source.read_bytes(),before)
