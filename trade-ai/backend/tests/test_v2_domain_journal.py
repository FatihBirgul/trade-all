"""Versioned journal acceptance; fixture databases only."""
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import sqlite3

from market_ai.v2.domain_journal import install, validate_schema, bind
from market_ai.v2.product_db import ProductDatabase

NOW = 1800000000000


class DomainJournalTests(TestCase):
    def test_explicit_new_database_has_atomic_chained_mutations(self):
        with TemporaryDirectory(prefix='v2-domain-') as root:
            db = ProductDatabase(Path(root)/'new.sqlite', 'fixture', domain_journal=True, clock=lambda:NOW)
            with db.transaction() as c:
                a = db.get(c, 'accounts', 'MANUAL')
                a['paused'] = True
                db.update(c, 'accounts', 'MANUAL', a)
            with closing(sqlite3.connect(db.path)) as c:
                rows = c.execute('SELECT sequence,event_hash,body FROM domain_events ORDER BY sequence').fetchall()
                self.assertGreater(len(rows), 1)
                self.assertEqual([r[0] for r in rows], list(range(1, len(rows)+1)))
                self.assertEqual(c.execute('SELECT sequence,event_hash FROM domain_head').fetchone(), rows[-1][:2])

    def test_old_database_is_not_upgraded_implicitly(self):
        with TemporaryDirectory(prefix='v2-domain-') as root:
            path = Path(root)/'old.sqlite'
            ProductDatabase(path, 'fixture')
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                ProductDatabase(path, 'fixture', domain_journal=True)
            self.assertEqual(path.read_bytes(), before)

    def test_projection_and_event_failures_rollback_together(self):
        from unittest.mock import patch
        from market_ai.v2 import domain_journal as domain
        with TemporaryDirectory(prefix='v2-domain-') as root:
            db = ProductDatabase(Path(root)/'new.sqlite', 'fixture', domain_journal=True, clock=lambda:NOW)
            before = db.path.read_bytes()
            with patch.object(domain, 'append', side_effect=sqlite3.OperationalError('injected disk failure')):
                with self.assertRaises(sqlite3.OperationalError), db.transaction() as c:
                    a = db.get(c,'accounts','MANUAL');a['paused']=True
                    db.update(c,'accounts','MANUAL',a)
            self.assertEqual(db.path.read_bytes(), before)
            with self.assertRaises(sqlite3.OperationalError), db.transaction() as c:
                domain.note(c,'control.requested',{'paused':True},'MANUAL')
                c.execute('UPDATE missing_projection SET value=1')
            self.assertEqual(db.path.read_bytes(), before)

    def test_copy_upgrade_repeat_backup_and_failed_migration_preserve_source(self):
        from unittest.mock import patch
        from scripts.migrate_v2_domain import copy_upgrade
        from scripts.backup_v2 import copy_database
        from market_ai.v2 import domain_journal as domain
        with TemporaryDirectory(prefix='v2-domain-') as root:
            root=Path(root);source=root/'old.sqlite';new=root/'new.sqlite'
            ProductDatabase(source,'fixture');before=source.read_bytes()
            copy_database(source,root/'before.sqlite')
            copy_upgrade(source,new,clock=lambda:NOW)
            self.assertEqual(source.read_bytes(),before)
            db=ProductDatabase(new,'fixture',domain_journal=True,clock=lambda:NOW)
            with db.transaction() as c:self.assertGreater(domain.validate_chain(c),0)
            copy_upgrade(new,root/'repeat.sqlite',clock=lambda:NOW)
            copy_database(new,root/'restore.sqlite')
            ProductDatabase(root/'restore.sqlite','fixture',domain_journal=True)
            with patch.object(domain,'attach',side_effect=sqlite3.OperationalError('migration midpoint')):
                with self.assertRaises(sqlite3.OperationalError):copy_upgrade(source,root/'failed.sqlite',clock=lambda:NOW)
            self.assertFalse((root/'failed.sqlite').exists())
            self.assertEqual(source.read_bytes(),before)
            with self.assertRaises(FileExistsError):copy_upgrade(source,new)

    def test_direct_old_writer_and_missing_guard_are_rejected(self):
        with TemporaryDirectory(prefix='v2-domain-') as root:
            db=ProductDatabase(Path(root)/'new.sqlite','fixture',domain_journal=True,clock=lambda:NOW)
            with closing(sqlite3.connect(db.path)) as c:
                with self.assertRaises(sqlite3.OperationalError):
                    c.execute("UPDATE accounts SET body='{}' WHERE id='MANUAL'")
                c.execute('DROP TRIGGER domain_capture_accounts_update');c.commit()
            with self.assertRaises(sqlite3.DatabaseError):ProductDatabase(db.path,'fixture')

    def test_unapproved_preimage_is_rejected_even_without_command_lookup(self):
        with TemporaryDirectory(prefix='v2-domain-') as root:
            db=ProductDatabase(Path(root)/'new.sqlite','fixture',domain_journal=True,clock=lambda:NOW)
            before=db.path.read_bytes()
            with self.assertRaises(ValueError),db.transaction() as c:
                db.remember(c,'order:MANUAL','fixture-key',{'authorization':'never-store-this-fixture-marker'},{})
            self.assertEqual(db.path.read_bytes(),before)

    def test_migration_ddl_failure_leaves_a_verified_copy_as_legacy(self):
        from unittest.mock import patch
        from scripts.backup_v2 import copy_database
        from market_ai.v2 import domain_journal as domain
        with TemporaryDirectory(prefix='v2-domain-') as root:
            root=Path(root);source=root/'old.sqlite';target=root/'copy.sqlite'
            ProductDatabase(source,'fixture');before=source.read_bytes();copy_database(source,target)
            original=domain.append;calls=[]
            def fail_third(*args,**kwargs):
                calls.append(1)
                if len(calls)==3:raise sqlite3.OperationalError('controlled DDL midpoint failure')
                return original(*args,**kwargs)
            with closing(sqlite3.connect(target,isolation_level=None,factory=domain.Connection)) as c:
                c.execute('BEGIN IMMEDIATE')
                with patch.object(domain,'append',side_effect=fail_third),self.assertRaises(sqlite3.OperationalError):
                    domain.install(c,lambda:NOW)
                c.rollback()
                self.assertFalse(domain.marker(c))
                self.assertEqual(c.execute("SELECT count(*) FROM sqlite_master WHERE name LIKE 'domain_%'").fetchone()[0],0)
                self.assertEqual(c.execute('SELECT count(*) FROM accounts').fetchone()[0],2)
            self.assertEqual(source.read_bytes(),before)
            ProductDatabase(target,'fixture')

    def test_legacy_outbox_boundary_and_corrupt_source_migration(self):
        from market_ai.v2.api import create_app
        from scripts.migrate_v2_domain import copy_upgrade
        from market_ai.v2.paper_audit import audit_database
        with TemporaryDirectory(prefix='v2-domain-') as root:
            root=Path(root);source=root/'legacy.sqlite';target=root/'upgraded.sqlite'
            app=create_app(source,mode='fixture',token='legacy-domain-fixture-token-32',clock=lambda:NOW)
            with app.state.v2.db.transaction() as c:app.state.v2.scanner._notify(c,'legacy-note','analysis',{'fixture':True})
            before=source.read_bytes();copy_upgrade(source,target,clock=lambda:NOW)
            self.assertEqual(source.read_bytes(),before)
            report=audit_database(target,require_domain=True)
            self.assertEqual(report['status'],'INCOMPLETE',report)
            self.assertEqual(report['checks']['MISMATCH'],0)
            with closing(sqlite3.connect(source)) as c,c:
                c.execute("UPDATE accounts SET body_hash='corrupt' WHERE id='MANUAL'")
            with self.assertRaises(ValueError):copy_upgrade(source,root/'bad.sqlite',clock=lambda:NOW)
            self.assertFalse((root/'bad.sqlite').exists())
