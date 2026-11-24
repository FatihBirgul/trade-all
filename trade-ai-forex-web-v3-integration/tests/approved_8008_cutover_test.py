"""Operation guards and failback decisions; all service operations mocked."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('approved_cutover',ROOT/'tools/approved-8008-cutover.py')
op=importlib.util.module_from_spec(spec);spec.loader.exec_module(op)

class ApprovedCutoverTests(unittest.TestCase):
    def test_missing_approval_stops_before_preflight(self):
        with patch.object(op,'preflight') as check, self.assertRaises(ValueError):
            op.apply(None,False,op.PROPOSAL_SHA)
        check.assert_not_called()

    def test_wrong_package_approval_stops_before_preflight(self):
        with patch.object(op,'preflight') as check, self.assertRaises(ValueError):
            op.apply(None,True,'0'*64)
        check.assert_not_called()

    def test_each_changed_service_identity_is_refused(self):
        expected={str(p):{'pid':p,'creation':1} for p in (5173,8005,8006,8007,8008)}
        for port in expected:
            actual={**expected,port:{'pid':int(port),'creation':2}}
            with self.subTest(port=port),self.assertRaises(ValueError):op.require_processes(expected,actual)

    def test_post_cutover_exempts_only_8008(self):
        expected={str(p):p for p in (5173,8005,8006,8007,8008)}
        op.require_processes(expected,{**expected,'8008':123},False)
        with self.assertRaises(ValueError):op.require_processes(expected,{**expected,'8005':123},False)

    def test_new_missing_changed_files_are_refused(self):
        for actual in ({},{'a':'changed'},{'a':'same','b':'new'}):
            with self.subTest(actual=actual),self.assertRaises(ValueError):op.require_protected({'a':'same'},actual)

    def rehearsal(self,fail_primary=False,foreign_owner=False,preflight_failure=False,last_change=False,fail_fallback=False):
        with TemporaryDirectory(prefix='approved-8008-fixture-',dir=ROOT/'release') as temp:
            path=Path(temp)
            op.save(path/'authorization.json',{'operation_tool_sha256':op.sha(op.__file__)})
            op.save(path/'rehearsal.json',{'primary':{'status':'PASS'},'failback':{'status':'PASS'}})
            old={'pid':13988,'creation':1};primary=object();fallback=object()
            controller=NS(port_free=Mock(return_value=not foreign_owner),launch=Mock(
                side_effect=[(primary,path/'primary.json'),(fallback,path/'fallback.json')]),stop_owned=Mock())
            runtime=NS(port_owner=Mock(return_value=999 if last_change else 13988),
                       process_identity=Mock(return_value=old))
            protected=NS(protected=lambda:{'source':'same'})
            modules={'attested_cutover':controller,'attested_runtime':runtime,'runtime8008_preflight':protected}
            expected={str(p):p for p in (5173,8005,8006,8007,8008)}
            check=Mock(return_value=({}, {'old_8008':old}))
            if preflight_failure:check.side_effect=ValueError('unexpected drift')
            accepted=Mock(side_effect=[ValueError('primary acceptance failure'),
                ValueError('fallback failure') if fail_fallback else {'startup_record':{'process':{'pid':222}}}]
                if fail_primary else None, return_value={'startup_record':{'process':{'pid':111}}})
            with patch.object(op,'preflight',check),patch.object(op,'module',side_effect=lambda name:modules[name]), \
                 patch.object(op,'launch_inputs'),patch.object(op,'extra_acceptance',accepted), \
                 patch.object(op,'proposal',return_value=({'processes':expected},{'source':'same'},{})), \
                 patch.object(op,'identities',return_value=expected),patch.object(op.subprocess,'run') as run:
                if preflight_failure or last_change or foreign_owner or fail_fallback:
                    with self.assertRaises((ValueError,RuntimeError)):op.apply(path,True,op.PROPOSAL_SHA)
                else:op.apply(path,True,op.PROPOSAL_SHA)
                if preflight_failure or last_change:
                    run.assert_not_called();controller.launch.assert_not_called();return
                self.assertEqual(run.call_count,1)
                self.assertEqual(run.call_args.args[0],['taskkill','/PID','13988','/T','/F'])
                result=json.loads((path/'result.json').read_text())
                self.assertFalse(result['pwa_apply_authorized'])
                if foreign_owner:
                    self.assertEqual(result['status'],'BLOCKED_FAILBACK_UNSAFE_OR_FAILED')
                    self.assertEqual(controller.launch.call_count,0)
                elif fail_fallback:
                    self.assertEqual(result['status'],'BLOCKED_FAILBACK_UNSAFE_OR_FAILED')
                    self.assertEqual(controller.stop_owned.call_count,2)
                elif fail_primary:
                    self.assertEqual(result['status'],'FAILBACK_ACCEPTED')
                    controller.stop_owned.assert_called_once_with(primary,path/'primary.json')
                    self.assertEqual(controller.launch.call_count,2)
                else:
                    self.assertEqual(result['status'],'PRIMARY_ACCEPTED')
                    controller.stop_owned.assert_not_called()
                    self.assertEqual(controller.launch.call_count,1)

    def test_primary_success(self):self.rehearsal()
    def test_primary_failure_uses_separate_failback(self):self.rehearsal(fail_primary=True)
    def test_foreign_owner_is_never_killed(self):self.rehearsal(fail_primary=True,foreign_owner=True)
    def test_preflight_failure_does_not_stop_anything(self):self.rehearsal(preflight_failure=True)
    def test_last_moment_pid_change_does_not_stop_anything(self):self.rehearsal(last_change=True)
    def test_failed_failback_is_stopped_and_reported(self):self.rehearsal(fail_primary=True,fail_fallback=True)

if __name__=='__main__':unittest.main(verbosity=2)
