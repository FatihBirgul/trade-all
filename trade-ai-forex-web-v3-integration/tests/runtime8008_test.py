"""8008 safety/route guards and new-manifest backup rehearsal; no live writes."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('audit8008',ROOT/'tools/runtime8008-preflight.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

def schema(new=True):
    return {'paths':{'/api/v5/analysis':{}},'components':{'schemas':{'UnifiedAnalysis':{
        'properties':{'historical_session_evidence':{}} if new else {}}}}}

class RouteSafety(unittest.TestCase):
    def test_actual8008_and_old8006_remain_distinguishable(self):
        audit.validate_route(schema(),schema(),schema(False),'http://127.0.0.1:8008')

    def test_wrong_proxy_target_refused(self):
        with self.assertRaisesRegex(ValueError,'Wrong proxy'):
            audit.validate_route(schema(),schema(),schema(False),'http://127.0.0.1:8006')

    def test_old_schema_not_new_runtime(self):
        with self.assertRaisesRegex(ValueError,'Old schema'):
            audit.validate_route(schema(False),schema(False),schema(False),'http://127.0.0.1:8008')

    def test_proxy_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError,'Proxy schema'):
            audit.validate_route(schema(),schema(False),schema(False),'http://127.0.0.1:8008')

    def test_public_disk_match_or_json_cannot_approve_loaded_code(self):
        self.assertEqual(audit.version_gate(disk_sha=audit.SHA,public_digest_matches=True,
                                           startup_attestation={'verified':True}),'VERSION_UNVERIFIED')
        self.assertEqual(audit.version_gate(disk_sha='wrong',public_digest_matches=True,
                                           startup_attestation=None),'VERSION_MISMATCH')

    def test_live_missing_evidence_safety_and_negative_controls(self):
        data=json.loads((audit.OUT/'api-acceptance.json').read_text())['responses']['XAUUSD']
        audit.validate_analysis('XAUUSD',data)
        for key,value in [('execution_permission',True),('lot_size',.01),
                          ('account_currency','USD'),('risk_balance_source','REAL_BALANCE')]:
            altered=copy.deepcopy(data);altered[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): audit.validate_analysis('XAUUSD',altered)
        for state in ('UNVERIFIED','UNAPPROVED'):
            altered=copy.deepcopy(data);altered['spread_status']['policy_status']=state
            audit.validate_analysis('XAUUSD',altered)
            altered['spread_status']['decision']='PASS'
            with self.assertRaises(ValueError):audit.validate_analysis('XAUUSD',altered)
        altered=copy.deepcopy(data);altered['historical_session_evidence']['historical_gap_authorized']=True
        with self.assertRaises(ValueError):audit.validate_analysis('XAUUSD',altered)

class FreshManifestBackup(unittest.TestCase):
    def setUp(self):
        parent=ROOT/'.artifacts/runtime8008-labs';parent.mkdir(exist_ok=True)
        self.temp=TemporaryDirectory(dir=parent);self.addCleanup(self.temp.cleanup)
        self.target=Path(self.temp.name)/'target';self.target.mkdir()
        self.manifest=json.loads((audit.OUT/'manifest.json').read_text())
        for row in self.manifest['guards']:
            dest=self.target/row['file'];dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(audit.OUT/'backup'/row['file'],dest)

    def test_fresh8008_manifest_dryrun_has_zero_writes(self):
        before={str(p):audit.file_hash(p) for p in self.target.rglob('*') if p.is_file()}
        self.assertEqual(audit.dry_run(self.target)['writes'],0)
        self.assertEqual(before,{str(p):audit.file_hash(p) for p in self.target.rglob('*') if p.is_file()})

    def test_proxy_guard_drift_refused(self):
        with (self.target/'vite.config.ts').open('a') as out:out.write('\n// changed proxy')
        with self.assertRaisesRegex(ValueError,'guard drift'):audit.dry_run(self.target)

    def test_backup_apply_restore_rehearsal_preserves_news_chart_and_proxy(self):
        audit.dry_run(self.target)
        for row in self.manifest['files']:
            dest=self.target/row['file'];dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(audit.OUT/'payload'/row['file'],dest)
            self.assertEqual(audit.file_hash(dest),row['source_sha256'])
        for row in reversed(self.manifest['files']):
            dest=self.target/row['file']
            if row['destination_sha256'] is None:
                retained=Path(self.temp.name)/'retained'/row['file'];retained.parent.mkdir(parents=True,exist_ok=True)
                shutil.move(str(dest),str(retained))
            else:shutil.copyfile(audit.OUT/'backup'/row['file'],dest)
        audit.dry_run(self.target)
        for row in self.manifest['guards']:
            self.assertEqual(audit.file_hash(self.target/row['file']),row['sha256'])

if __name__=='__main__':unittest.main(verbosity=2)
