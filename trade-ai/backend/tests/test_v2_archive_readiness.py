from unittest import TestCase
from pathlib import Path
from contextlib import closing
import sqlite3
from fastapi.testclient import TestClient
from tests import test_v2_equity_history as fixtures
from market_ai.v2.archive_manifest import build_manifest
from market_ai.v2.archive_readiness import assess_copies
from market_ai.v2.api import create_app
from scripts.backup_v2 import copy_database

class ArchiveReadinessTests(TestCase):
 setUp=fixtures.EquityHistoryTests.setUp
 def populate(self):
  fixtures.EquityHistoryTests.order(self);fixtures.EquityHistoryTests.bar(self)
  self.manifest=build_manifest(self.path);self.assertEqual(self.manifest['status'],'PASS')
 def test_exact_copies_and_disposable_restore_rehearsal_preserve_account_and_audit(self):
  self.populate();before=self.path.read_bytes();copied=self.path.with_name('restored-fixture.sqlite')
  copy_database(self.path,copied);self.assertEqual(assess_copies([self.path,copied],self.manifest)['status'],'PASS')
  restored=create_app(copied,mode='fixture',token='fixture-restore-test-not-secret-32',clock=lambda:1800000000000,domain_journal=True)
  with TestClient(restored,headers={'Authorization':'Bearer fixture-restore-test-not-secret-32'}) as c:
   account=c.get('/api/v2/portfolios/MANUAL');self.assertEqual(account.status_code,200,account.text)
  self.assertEqual(build_manifest(copied),self.manifest)
  self.assertEqual(self.path.read_bytes(),before)
 def test_missing_partial_copy_and_different_cutoff_are_not_pass(self):
  self.populate();missing=self.path.with_name('missing.sqlite')
  self.assertEqual(assess_copies([self.path,missing],self.manifest)['status'],'INCOMPLETE');self.assertFalse(missing.exists())
  partial=self.path.with_name('partial.sqlite');partial.write_bytes(self.path.read_bytes()[:100])
  self.assertEqual(assess_copies([partial],self.manifest)['status'],'ERROR')
  # A new real fixture event changes the domain cutoff; do not merge histories.
  fixtures.EquityHistoryTests.bar(self)
  self.assertEqual(assess_copies([self.path],self.manifest)['status'],'MISMATCH')
 def test_budget_and_forged_manifest_or_corrupt_copy_fail_closed(self):
  self.populate();self.assertEqual(assess_copies([self.path],self.manifest,max_snapshots=1)['status'],'INCOMPLETE')
  self.assertEqual(assess_copies([self.path],{**self.manifest,'manifest_id':'0'*64})['status'],'CORRUPT')
  with self.assertRaises(ValueError):assess_copies([self.path,self.path],self.manifest)
  with self.assertRaises(ValueError):assess_copies([self.path]*9,self.manifest)
  with closing(sqlite3.connect(self.path)) as c:
   c.execute('DROP TRIGGER equity_snapshots_update');c.execute("UPDATE equity_snapshots SET body_hash=?",('0'*64,));c.commit()
  self.assertEqual(assess_copies([self.path],self.manifest)['status'],'CORRUPT')
 def test_explicit_cli_reports_missing_part_without_creating_it_or_logging_paths(self):
  from scripts.archive_readiness_v2 import main
  from contextlib import redirect_stdout
  from io import StringIO
  import json
  self.populate();manifest=self.path.with_name('reviewed.json');manifest.write_text(json.dumps(self.manifest))
  missing=self.path.with_name('private-name-missing.sqlite');output=StringIO()
  with redirect_stdout(output):code=main(['--expected',str(manifest),str(self.path),str(missing)])
  result=json.loads(output.getvalue());self.assertEqual(code,1);self.assertEqual(result['status'],'INCOMPLETE')
  self.assertNotIn(str(self.path),output.getvalue());self.assertNotIn('private-name',output.getvalue());self.assertFalse(missing.exists())
