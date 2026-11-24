"""Synthetic guard/lease tests. No listeners or live processes are changed."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('coord',ROOT/'tools/operation-coordination.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(dir=ROOT/'.artifacts');self.addCleanup(self.t.cleanup)
        self.root=Path(self.t.name);self.state=self.root/'operator';self.patch=patch.object(c,'STATE_ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.owner={'pid':111,'creation_filetime_100ns':999,'os_executable':'synthetic'};self.identity=lambda pid:self.owner
    def take(self):return c.acquire(self.state,self.owner,'a'*64,self.identity,now=100)
    def test_exclusive_acquire_retains_existing_owner(self):
        self.take();before=(self.state/'lease.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'EXISTING'):self.take()
        self.assertEqual((self.state/'lease.json').read_bytes(),before)
    def test_expired_lease_reports_stale_without_deletion(self):
        self.take();self.assertIn('STALE',c.lease_status(self.state/'lease.json',self.identity,1001));self.assertTrue((self.state/'lease.json').exists())
    def test_pid_reuse_reports_stale(self):
        self.take();self.assertIn('STALE',c.lease_status(self.state/'lease.json',lambda pid:{**self.owner,'creation_filetime_100ns':1000},101))
    def test_wrong_token_cannot_release(self):
        self.take()
        with self.assertRaisesRegex(ValueError,'OWNERSHIP'):c.release(self.state,'wrong',self.identity)
        self.assertFalse((self.state/'lease.released.json').exists())
    def test_release_retains_lock_and_requires_new_operation(self):
        r=self.take();c.release(self.state,r['token'],self.identity);self.assertTrue((self.state/'lease.json').exists())
        with self.assertRaisesRegex(ValueError,'EXISTING'):self.take()
    def test_outside_state_refused(self):
        with self.assertRaisesRegex(ValueError,'LOCATION'):c.acquire(self.root.parent/'outside',self.owner,'a'*64,self.identity)
    def test_owner_changed_before_acquire_refused(self):
        with self.assertRaisesRegex(ValueError,'OWNER'):c.acquire(self.state,self.owner,'a'*64,lambda pid:{})
        self.assertFalse(self.state.exists())
    def test_corrupt_lease_not_taken_over(self):
        self.state.mkdir();(self.state/'lease.json').write_text('bad')
        self.assertIn('CORRUPT',c.lease_status(self.state/'lease.json',self.identity,101))
    def test_advisory_limitation_explicit(self):self.assertFalse(self.take()['enforces_external_exclusion'])
class GuardTests(unittest.TestCase):
    def fixture(self):
        p={str(x):{'pid':x,'creation_filetime_100ns':123,'os_executable':'synthetic'} for x in (5173,8005,8006,8007,8008)}
        health={k:{'http':200,'sha256':'a'*64,'safe_summary':{'data_status':'OK'}} for k in ('5173/engine/api/v1/health','8005/api/health','8006/api/v1/health','8007/api/news','8008/api/v1/health','5173/engine/openapi.json','8008/openapi.json')}
        return {'identities':p,'ports':{k:[v] for k,v in p.items()},'original_hashes':{'AnalysisPanel':'x'},'isolated_hashes':{'AnalysisPanel':'y'},'backend_sha':c.EXPECTED_BUILD,'backend_status':'','pwa_head':'pinned','release_pins':{'expected':'frozen'},'health':health}
    def test_same_baseline_passes_without_claiming_loaded_version(self):
        a=self.fixture();self.assertTrue(c.compare(a,copy.deepcopy(a)));self.assertFalse(c.acceptance('A_PLAN',{},None,lambda:False)['apply_allowed'])
    def test_pid_reuse_on_same_port_blocked(self):
        a=self.fixture();b=copy.deepcopy(a);b['identities']['8008']['creation_filetime_100ns']+=1
        with self.assertRaisesRegex(ValueError,'DRIFT'):c.compare(a,b)
    def test_external_user_edit_blocked(self):
        a=self.fixture();b=copy.deepcopy(a);b['original_hashes']['AnalysisPanel']='external'
        with self.assertRaisesRegex(ValueError,'DRIFT'):c.compare(a,b)
    def test_release_pin_change_blocked(self):
        a=self.fixture();b=copy.deepcopy(a);b['release_pins']['expected']='external'
        with self.assertRaisesRegex(ValueError,'DRIFT'):c.compare(a,b)
    def test_multiple_listeners_not_assumed_same_service(self):
        a=self.fixture();b=copy.deepcopy(a);b['ports']['8008'].append({'pid':12})
        with self.assertRaisesRegex(ValueError,'AMBIGUOUS'):c.compare(a,b)
    def test_proxy_schema_mismatch_blocked(self):
        a=self.fixture();b=copy.deepcopy(a);b['health']['5173/engine/openapi.json']['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'PROXY'):c.compare(a,b)
    def test_health_failure_blocked(self):
        a=self.fixture();b=copy.deepcopy(a);b['health']['8008/api/v1/health']['http']=503
        with self.assertRaisesRegex(ValueError,'HEALTH'):c.compare(a,b)
    def test_http200_is_not_provider_acceptance(self):
        a=self.fixture();b=copy.deepcopy(a);b['health']['8008/api/v1/health']['safe_summary']['data_status']='UNAVAILABLE'
        with self.assertRaisesRegex(ValueError,'PROVIDER_HEALTH'):c.compare(a,b)
    def test_stage_b_needs_same_process_attestation(self):
        with self.assertRaisesRegex(ValueError,'UNVERIFIED'):c.acceptance('B',{},None,lambda:True)
    def test_fingerprint_not_assignable_to_foreign_pid(self):
        a={'process':{'pid':1},'loaded':{'loaded_function_code_sha256':c.EXPECTED_FINGERPRINT}}
        with self.assertRaisesRegex(ValueError,'IDENTITY'):c.acceptance('B',{'pid':2},a,lambda:True)
    def test_unverified_record_refused_even_if_hash_matches(self):
        a={'process':{},'loaded':{'loaded_function_code_sha256':c.EXPECTED_FINGERPRINT},'build_sha':c.EXPECTED_BUILD,'execution_permission':False}
        with self.assertRaisesRegex(ValueError,'VERIFICATION'):c.acceptance('B',{},a,lambda:False)
if __name__=='__main__':unittest.main(verbosity=2)
