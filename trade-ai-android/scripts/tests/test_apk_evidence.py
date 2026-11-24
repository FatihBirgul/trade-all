"""Parser fixtures only; actual signature validation requires the CI apksigner."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile
spec=importlib.util.spec_from_file_location('apk_evidence',Path(__file__).resolve().parents[1]/'apk-evidence.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.apk=Path(self.tmp.name)/'synthetic-parser-fixture.zip'
  self.config={'version':'0.7.2','android':{'package':'com.fatihbirgul.tradeai','versionCode':11}}
  self.badging="package: name='com.fatihbirgul.tradeai' versionCode='11' versionName='0.7.2'"
  self.signature='Verified using v2 scheme (APK Signature Scheme v2): true\nV2 Signer: certificate SHA-256 digest: '+module.REFERENCE_CERT
  with zipfile.ZipFile(self.apk,'w') as z:z.writestr('assets/index.android.bundle',b'synthetic test bundle');z.writestr('lib/arm64-v8a/libfixture.so',b'parser fixture, not an executable')
 def inspect(self,**changes):return module.inspect(self.apk,changes.get('config',self.config),changes.get('badging',self.badging),changes.get('signature',self.signature),changes.get('commit','a'*40))
 def test_actual_package_version_and_reference_certificate(self):
  r=self.inspect();self.assertTrue(r['certificate_matches_reference']);self.assertEqual(r['device_validation'],'UNVERIFIED');self.assertEqual(r['version_code'],11)
 def test_wrong_package_and_wrong_source_version_rejected(self):
  with self.assertRaises(ValueError):self.inspect(badging=self.badging.replace('tradeai','other'))
  with self.assertRaises(ValueError):self.inspect(badging=self.badging.replace("versionCode='11'","versionCode='10'"))
 def test_certificate_mismatch_is_reported_without_update_promise(self):
  r=self.inspect(signature=self.signature.replace(module.REFERENCE_CERT,'b'*64));self.assertFalse(r['certificate_matches_reference']);self.assertIn('unverified',r['update_claim'])
 def test_unsigned_or_failed_verifier_not_accepted(self):
  with self.assertRaises(ValueError):self.inspect(signature=self.signature.replace(': true',': false'))
 def test_wrong_architecture_or_missing_bundle_rejected(self):
  with zipfile.ZipFile(self.apk,'w') as z:z.writestr('lib/x86/libfixture.so',b'fixture')
  with self.assertRaises(ValueError):self.inspect()
 def test_source_hash_must_be_exact(self):
  with self.assertRaises(ValueError):self.inspect(commit='main')
