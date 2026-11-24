from unittest import TestCase
from unittest.mock import patch
from contextlib import closing
import sqlite3
from tests import test_v2_equity_history as fixtures
from market_ai.v2.archive_manifest import build_manifest,verify_manifest
class ArchiveManifestTests(TestCase):
 setUp=fixtures.EquityHistoryTests.setUp
 def populate(self):fixtures.EquityHistoryTests.order(self);fixtures.EquityHistoryTests.bar(self)
 def test_independent_audit_source_and_verified_copy_have_same_manifest(self):
  from scripts.backup_v2 import copy_database
  self.populate();before=self.path.read_bytes();manifest=build_manifest(self.path);self.assertEqual(manifest['accounts']['MANUAL']['count'],2);self.assertEqual(manifest['status'],'PASS',manifest)
  self.assertEqual(manifest,build_manifest(self.path));self.assertEqual(before,self.path.read_bytes())
  copied=self.path.with_name('backup.sqlite');copy_database(self.path,copied)
  self.assertEqual(manifest,build_manifest(copied));self.assertEqual(verify_manifest(copied,manifest)['status'],manifest['status'])
 def test_budget_never_emits_partial_pass_and_missing_file_not_created(self):
  self.populate();r=build_manifest(self.path,max_snapshots=1);self.assertEqual(r['status'],'INCOMPLETE');self.assertIsNone(r['accounts'])
  missing=self.path.with_name('missing.sqlite');self.assertEqual(build_manifest(missing)['status'],'ERROR');self.assertFalse(missing.exists())
 def test_hash_tampering_and_account_sequence_corruption_detected(self):
  self.populate();m=build_manifest(self.path);m['accounts']['MANUAL']['count']+=1;self.assertEqual(verify_manifest(self.path,m)['status'],'CORRUPT')
  with closing(sqlite3.connect(self.path)) as c:
   c.execute('DROP TRIGGER equity_snapshots_update');c.execute("UPDATE equity_snapshots SET body_hash=? WHERE portfolio='MANUAL'",('0'*64,));c.commit()
  self.assertEqual(build_manifest(self.path)['status'],'CORRUPT')
 def test_wal_write_during_audit_reports_incomplete_and_releases_readers(self):
  from market_ai.v2.archive_manifest import audit_database
  self.populate()
  with closing(sqlite3.connect(self.path)) as c:c.execute('PRAGMA journal_mode=WAL')
  def race(*args,**kwargs):
   r=self.c.post('/api/v2/analyze',json={'data_mode':'fixture','idempotency_key':'manifest-concurrent-analysis'});self.assertEqual(r.status_code,200)
   return audit_database(*args,**kwargs)
  with patch('market_ai.v2.archive_manifest.audit_database',side_effect=race):r=build_manifest(self.path)
  self.assertEqual(r['status'],'INCOMPLETE');self.assertEqual(r['reason'],'source_changed_during_audit')
  self.assertIn(build_manifest(self.path)['status'],('PASS','INCOMPLETE'))
 def test_metadata_query_budget_rejects_expensive_untrusted_view(self):
  # Controlled bounded recursion only in a newly-created fixture database.
  with closing(sqlite3.connect(self.path)) as c:
   c.execute('DROP TABLE product_meta')
   c.execute("CREATE VIEW product_meta AS WITH RECURSIVE numbers(n) AS (SELECT 0 UNION ALL SELECT n+1 FROM numbers WHERE n<160000) SELECT CASE WHEN MAX(n)>=0 THEN 'fixture' END AS mode FROM numbers")
   c.commit()
  r=build_manifest(self.path);self.assertEqual(r['status'],'INCOMPLETE');self.assertEqual(r['reason'],'query_budget')
