"""Seal the unique BLOCKED coordination evidence bundle; no live operations."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/coordinated-operation-20261112-01'
ARCHIVE=ROOT/'release/TRADE_AI_V3_COORDINATED_OPERATION_20261112_01_BLOCKED.zip'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def main():
    if (OUT/'sealed.json').exists() or ARCHIVE.exists():raise ValueError('BLOCK_IMMUTABLE_EXISTING_PACKAGE')
    before=json.loads((OUT/'begin.json').read_text(encoding='utf-8'));after=json.loads((OUT/'end.json').read_text(encoding='utf-8'))
    preservation={k:before[k]==after[k] for k in ('identities','original_hashes','isolated_hashes','backend_sha','backend_status')}
    save(OUT/'preservation.json',{'checks':preservation,'status':'PASS' if all(preservation.values()) else 'BLOCKED_CONCURRENT_CHANGE'})
    save(OUT/'coordination.json',{'status':'ADVISORY_UNACQUIRED','external_workflow_freeze':'NOT_ACKNOWLEDGED',
         'operator_state_root':str(ROOT/'.artifacts/operator-state'),'maximum_lease_seconds':900,
         'automatic_stale_takeover':False,'deletes_other_workflow_files':False,'stops_external_agents':False,
         'actual_access_control':False,'new_operator_binding_controller':'REQUIRES_REVIEWED_IMPLEMENTATION_AND_ISOLATED_QA',
         'live_apply_authorized':False})
    tests={'coordination_guards':{'pass':20,'fail':0,'source':'coordinated-guard-tests.log'},
           'attested_runtime_unit':{'pass':28,'fail':0,'source':'coordinated-attestation-tests.log'},
           'pwa_promotion_rollback_fixture':{'pass':17,'fail':0,'source':'coordinated-pwa-guard-tests.log'},
           'prior_frontend_checks':'REFERENCED_ONLY_NOT_RERUN; UNCHANGED_PAYLOAD',
           'counts_are_separate_groups':'NO_UNIQUE_AGGREGATE_CLAIM',
           'current_running_exact_version':'UNVERIFIED','physical_phone':'NOT_TESTED'}
    evidence=OUT/'evidence';evidence.mkdir(exist_ok=True)
    for name in ('coordinated-guard-tests.log','coordinated-attestation-tests.log','coordinated-pwa-guard-tests.log','coordinated-legacy-preflight.log'):
        source=ROOT/'.artifacts'/name;text=source.read_text(encoding='utf-8')
        if name=='coordinated-guard-tests.log' and not ('Ran 20 tests' in text and '\nOK' in text):raise ValueError('BLOCK_GUARD_TESTS')
        if name=='coordinated-attestation-tests.log' and not ('Ran 28 tests' in text and '\nOK' in text):raise ValueError('BLOCK_ATTESTED_TESTS')
        if name=='coordinated-pwa-guard-tests.log' and not ('pass 17' in text and 'fail 0' in text):raise ValueError('BLOCK_PROMOTION_TESTS')
        shutil.copy2(source,evidence/name)
    save(OUT/'tests.json',tests)
    names=['docs/V3_RUNTIME_STABILITY_COORDINATION_TR.md','docs/V3_COORDINATED_OPERATION_PLAN_TR.md','docs/V3_COORDINATED_APPROVAL_DRAFT_TR.md',
           'tools/coordination-audit.py','tools/operation-coordination.py','tools/package-coordinated-operation.py','tests/operation_coordination_test.py',
           'tools/attested-runtime.py','tools/attested-acceptance.py','tools/attested-cutover.py','tools/attested-release.py','tools/final-pwa-promotion.mjs','tools/final-pwa-release.py','tools/release-package.mjs']
    for name in names:
        dest=OUT/'review-source'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    shutil.copy2(ROOT/'docs/V3_RUNTIME_STABILITY_COORDINATION_TR.md',OUT/'REPORT_TR.md')
    backend=ROOT/'release/TRADE_AI_V3_ATTESTED_8008_56cbd7e_READY.zip'
    if sha(backend)!='a7e21cfca44c0963b689ff88f6d7e3f85f8a39c8a5a3b47e2dbeeaece6f66ef9':raise ValueError('BLOCK_BACKEND_ARCHIVE_CHANGED')
    pwa_old=ROOT/'release/TRADE_AI_V3_PWA_8008_BLOCKED_EVIDENCE_78907154.zip'
    if sha(pwa_old)!='cf446b8957e0b3c27804cf8621382051c2a489de43620c8c91df5f7df3682130':raise ValueError('BLOCK_OLD_PWA_ARCHIVE_CHANGED')
    shutil.copy2(backend,OUT/'backend-attested-reference.zip')
    pwa=OUT/'pwa';m=json.loads((pwa/'manifest.json').read_text());m['source_head']=after['pwa_head'];m['operation_source_head']=after['pwa_head']
    save(pwa/'manifest.json',m);(pwa/'manifest.sha256').write_text(sha(pwa/'manifest.json'))
    command="import {dryRun} from './tools/final-pwa-promotion.mjs'; console.log(JSON.stringify(dryRun(process.argv[1])))"
    dry=json.loads(subprocess.check_output(['node','--input-type=module','-e',command,str(pwa)],cwd=ROOT,text=True))
    if dry['writes']!=0 or dry['deletes']!=0 or dry['files']!=9:raise ValueError('BLOCK_DRY_RUN')
    save(OUT/'pwa-dry-run.json',dry)
    baseline=OUT/'baseline.json'
    if not baseline.exists():raise ValueError('BLOCK_MISSING_REVIEWED_BASELINE')
    commands=f"# Read-only preparation commands; no APPLY capability\n\nBaseline SHA-256: `{sha(baseline)}`\n\n```powershell\npython -B tools/operation-coordination.py preflight --stage A_PLAN --baseline release/coordinated-operation-20261112-01/baseline.json --baseline-sha256 {sha(baseline)}\n```\n\nA_PLAN passing does not prove current loaded code or authorize execution. B requires a separately reviewed post-A baseline and its owned startup record. No advisory lease has been acquired.\n"
    (OUT/'READ_ONLY_PREFLIGHT.md').write_text(commands,encoding='utf-8')
    save(OUT/'operation-manifest.json',{'status':'BLOCKED','backend_sha':after['backend_sha'],'pwa_head':after['pwa_head'],
        'frontend_source_head':m['frontend_source_head'],'baseline_sha256':sha(baseline),'current_8008':after['identities']['8008'],
        'current_loaded_fingerprint':None,'current_attestation_status':'EXACT_RUNNING_VERSION_UNVERIFIED',
        'target_reference_fingerprint':'314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b',
        'root_cause_status':'ROOT_CAUSE_UNVERIFIED','confirmed_mechanism':'PLAIN_UVICORN_POWERSHELL_PARENT',
        'blockers':['HUMAN_EXTERNAL_WORKFLOW_FREEZE_NOT_ACKNOWLEDGED','CURRENT_8008_UNATTESTED',
                    'CURRENT_SPREAD_UNVERIFIED_BLOCK_NOT_EXPECTED_UNAPPROVED_BLOCK','OLD_LIVE_CONTROLLERS_STALE; NEW_OPERATOR_BINDING_AND_OWNED_QA_REQUIRED'],
        'two_stage_plan':'review-source/docs/V3_COORDINATED_OPERATION_PLAN_TR.md','approval_draft':'review-source/docs/V3_COORDINATED_APPROVAL_DRAFT_TR.md',
        'preservation':preservation,'dry_run':dry,'tests':tests,'live_mutations':False,'approval_received':False})
    pins={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file()}
    save(OUT/'sealed.json',{'status':'BLOCKED','files':pins})
    with zipfile.ZipFile(ARCHIVE,'x',zipfile.ZIP_DEFLATED) as z:
        for p in OUT.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(OUT))
    with zipfile.ZipFile(ARCHIVE) as z:
        if z.testzip() is not None:raise ValueError('BLOCK_ZIP_CRC')
        for p in OUT.rglob('*'):
            if p.is_file() and hashlib.sha256(z.read(p.relative_to(OUT).as_posix())).hexdigest()!=sha(p):raise ValueError('BLOCK_ZIP_ENTRY_HASH')
    checksum=sha(ARCHIVE);Path(str(ARCHIVE)+'.sha256').write_text(checksum+'\n')
    print(json.dumps({'status':'BLOCKED','archive':str(ARCHIVE),'sha256':checksum,'preservation':preservation,'dry_run':dry},indent=2))
if __name__=='__main__':main()
