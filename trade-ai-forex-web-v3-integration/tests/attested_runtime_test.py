"""New-startup guards. No injection into any existing process."""
import asyncio
import copy
import importlib.util
import json
import os
import subprocess
import sys
import types
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('attested',ROOT/'tools/attested-runtime.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class SourceGuards(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.file=self.root/'unit.py';self.file.write_text('VALUE=1\n')
        self.manifest={'build_sha':audit.BUILD,'files':{'unit.py':audit.file_hash(self.file)}}

    def test_exact_inventory_and_hash(self):self.assertEqual(len(audit.verify_source(self.root,self.manifest)),64)
    def test_wrong_build_refused(self):
        self.manifest['build_sha']='wrong'
        with self.assertRaises(audit.IntegrityError):audit.verify_source(self.root,self.manifest)
    def test_missing_source_refused(self):
        self.manifest['files']['missing.py']='0'*64
        with self.assertRaises(audit.IntegrityError):audit.verify_source(self.root,self.manifest)
    def test_extra_source_refused(self):
        (self.root/'extra.py').write_text('unexpected')
        with self.assertRaises(audit.IntegrityError):audit.verify_source(self.root,self.manifest)
    def test_changed_after_freeze_does_not_change_frozen_record(self):
        frozen=copy.deepcopy(self.manifest);self.file.write_text('VALUE=2\n')
        with self.assertRaises(audit.IntegrityError):audit.verify_source(self.root,self.manifest)
        self.assertEqual(self.manifest,frozen)
    def test_old_bytecode_cache_refused(self):
        (self.root/'unit.pyc').write_bytes(b'bad')
        with self.assertRaisesRegex(audit.IntegrityError,'cache'):audit.verify_source(self.root,self.manifest)
    def test_config_digest_corruption(self):
        with self.assertRaises(audit.IntegrityError):audit.pinned_json(self.file,'0'*64)
    def test_dependency_drift_refused_before_dependency_or_forex_import(self):
        source=self.root/'source';source.mkdir();(source/'unit.py').write_text('VALUE=1\n')
        document={'build_sha':audit.BUILD,'files':{'unit.py':audit.file_hash(source/'unit.py')}}
        source_manifest=self.root/'source.json';source_manifest.write_text(json.dumps(document))
        config=json.loads((ROOT/'release/attested-8008-56cbd7e/config.json').read_text())
        config['dependencies']['critical_entry_files']={str(self.file):'0'*64}
        config_file=self.root/'config.json';config_file.write_text(json.dumps(config))
        with patch.object(audit,'dependencies') as dependencies:
            with self.assertRaisesRegex(audit.IntegrityError,'Dependency bytes drift'):
                audit.main(['reference','--release',str(source),'--source-manifest',str(source_manifest),
                            '--source-sha256',audit.file_hash(source_manifest),'--config',str(config_file),
                            '--config-sha256',audit.file_hash(config_file)])
            dependencies.assert_not_called()
    def test_junction_refused(self):
        target=self.root/'target';target.mkdir();other=self.root/'alias'
        subprocess.run(['cmd.exe','/c','mklink','/J',str(other),str(target)],
                       check=True,stdout=subprocess.DEVNULL)
        with self.assertRaises(audit.IntegrityError):audit.no_links(other)

class StartupGuards(unittest.TestCase):
    def setUp(self):
        self.config={'release_id':'SYNTHETIC_TEST_ONLY','dependencies':{'numpy':'2.2.6'}}
        self.reference={'loaded':{'function_count':1,'loaded_function_code_sha256':'fake'},
                        'module_origins':{'SYNTHETIC_TEST_ONLY':'verified'}}
        self.identity={'pid':123,'creation_filetime_100ns':456,'os_executable':'fake'}
        self.record={'mode':'LOCAL_FROZEN_STARTUP_PROVENANCE','build_sha':audit.BUILD,
            'release_id':self.config['release_id'],'source_manifest_sha256':'source',
            'config_sha256':'config','port':18008,'process':self.identity,'execution_permission':False,
            'loaded':self.reference['loaded'],'module_origins':self.reference['module_origins'],
            'dependencies':self.config['dependencies']}
        self.rebind()
    def rebind(self):
        self.record.pop('binding_sha256',None)
        self.record['binding_sha256']=audit.digest(audit.canonical(self.record))
    def check(self):
        audit.validate_startup(self.record,self.config,'source','config',self.reference,18008,self.identity)
    def test_exact_new_record(self):self.check()
    def test_missing_fingerprint_refused(self):
        self.record.pop('loaded');self.rebind()
        with self.assertRaises(audit.IntegrityError):self.check()
    def test_other_pid_creation_identity_refused(self):
        self.record['process']={**self.identity,'creation_filetime_100ns':789};self.rebind()
        with self.assertRaises(audit.IntegrityError):self.check()
    def test_wrong_runtime_build_refused(self):
        self.record['build_sha']='old';self.rebind()
        with self.assertRaises(audit.IntegrityError):self.check()
    def test_changed_loaded_code_refused(self):
        self.record['loaded']={'loaded_function_code_sha256':'changed'};self.rebind()
        with self.assertRaises(audit.IntegrityError):self.check()
    def test_module_origin_change_refused(self):
        self.record['module_origins']={};self.rebind()
        with self.assertRaises(audit.IntegrityError):self.check()
    def test_corrupt_record_refused(self):
        self.record['release_id']='changed'
        with self.assertRaises(audit.IntegrityError):self.check()
    def test_protected_service_ports(self):
        for port in (5173,8005,8006,8007,8008):
            with self.subTest(port=port),self.assertRaises(audit.IntegrityError):audit.check_port(port)
        audit.check_port(18008);audit.check_port(8008,True)
        with self.assertRaises(audit.IntegrityError):audit.check_port(8006,True)
    def test_order_and_account_write_methods_not_exposed(self):
        proxy=audit.ReadOnlyTerminal(object())
        for name in ('order_send','order_check','login','logout','symbol_select'):
            with self.subTest(name=name),self.assertRaises(AttributeError):getattr(proxy,name)
    def test_os_process_identity_is_stable(self):
        self.assertEqual(audit.process_identity(os.getpid()),audit.process_identity(os.getpid()))
    def test_integrity_failure_503_has_no_private_details(self):
        messages=[]
        async def unused(*args):raise AssertionError('Downstream must not run')
        def corrupt():raise ValueError('private-path-must-not-leak')
        async def send(value):messages.append(value)
        asyncio.run(audit.IntegrityGuard(unused,corrupt)({'type':'http'},None,send))
        self.assertEqual(messages[0]['status'],503)
        self.assertNotIn(b'private-path',messages[1]['body'])

class LoadedCodeGuards(unittest.TestCase):
    def test_normal_execution_and_interning_do_not_change_semantic_fingerprint(self):
        name='forex.__synthetic_attestation_fixture';module=types.ModuleType(name)
        exec("def calculate(value):\n    return {'stable-name': value+1}\n",module.__dict__)
        sys.modules[name]=module
        try:
            before=audit.loaded_fingerprint()
            for i in range(100):module.calculate(i)
            self.assertEqual(before,audit.loaded_fingerprint())
        finally:sys.modules.pop(name)

class CutoverApprovalGuards(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('cutover_guard',ROOT/'tools/attested-cutover.py')
        self.controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.controller)
    def test_live_flag_without_new_approval_and_digest_is_refused(self):
        for approved,expected in ((False,None),(True,None),(False,'0'*64)):
            with self.assertRaises(ValueError):self.controller.approval_gate(True,approved,expected)
    def test_no_apply_is_read_only(self):self.controller.approval_gate(False,False,None)
    def test_default_refuses_apply_before_preflight_or_subprocess(self):
        with patch.object(sys,'argv',['attested-cutover.py','--apply-runtime']), \
             patch.object(self.controller,'preflight') as preflight, \
             patch.object(self.controller.subprocess,'run') as run:
            with self.assertRaises(ValueError):self.controller.main()
            preflight.assert_not_called();run.assert_not_called()

    def rehearsal(self,fail_primary=False,foreign_owner=False):
        temp=TemporaryDirectory();self.addCleanup(temp.cleanup)
        acceptance=SimpleNamespace(owned=lambda *args: {'status':'PASS'})
        primary=object();fallback=object();startup=Path(temp.name)/'startup.json'
        def accept(*args):
            if args[1] is primary and fail_primary:raise ValueError('simulated owned startup failure')
            return {'checks':['safe'],'execution_permission':False}
        with patch.object(sys,'argv',['cutover','--apply-runtime','--operator-approved','--package-sha256','0'*64]), \
             patch.object(self.controller,'OUT',Path(temp.name)), \
             patch.object(self.controller,'preflight',return_value=({}, {'pid':123})) as preflight, \
             patch.object(self.controller,'module',side_effect=lambda name:acceptance if name=='attested_acceptance' else object()), \
             patch.object(self.controller.subprocess,'run') as run, \
             patch.object(self.controller,'port_free',side_effect=[True,not foreign_owner]), \
             patch.object(self.controller,'launch',side_effect=[(primary,startup),(fallback,startup)]) as launch, \
             patch.object(self.controller,'await_acceptance',side_effect=accept), \
             patch.object(self.controller,'stop_owned') as stop:
            if foreign_owner:
                with self.assertRaisesRegex(ValueError,'Unexpected 8008 owner'):self.controller.main()
            else:self.controller.main()
            self.assertEqual(preflight.call_count,2)
            self.assertEqual(run.call_count,1)
            self.assertEqual(run.call_args.args[0][2],'123')
            if fail_primary:stop.assert_called_once_with(primary,startup)
            else:stop.assert_not_called()
            self.assertEqual(launch.call_count,2 if fail_primary and not foreign_owner else 1)
            if not foreign_owner:
                record=json.loads(next(Path(temp.name).glob('cutover-result-*.json')).read_text())
                self.assertFalse(record['pwa_apply_authorized'])
    def test_simulated_primary_success_keeps_pwa_unauthorized(self):self.rehearsal()
    def test_simulated_primary_failure_uses_separate_failback(self):self.rehearsal(True)
    def test_simulated_foreign_owner_is_never_killed_or_overwritten(self):self.rehearsal(True,True)

    def test_memory_code_replacement_changes_fingerprint_without_disk_reads(self):
        name='forex.__synthetic_attestation_fixture';module=types.ModuleType(name)
        exec('def calculate(value):\n    return value+1\n',module.__dict__)
        sys.modules[name]=module
        try:
            before=audit.loaded_fingerprint()
            def changed(value):return value+2
            module.calculate.__code__=changed.__code__
            self.assertNotEqual(before,audit.loaded_fingerprint())
        finally:sys.modules.pop(name)

if __name__=='__main__':unittest.main(verbosity=2)
