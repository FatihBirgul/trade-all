"""Advisory lease + fail-closed preflight. No live mutation capability."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
STATE_ROOT=ROOT/'.artifacts/operator-state'
EXPECTED_BUILD='56cbd7e05a40b106deda9298e2be28b488d0d952'
EXPECTED_FINGERPRINT='314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b'
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
def inside(root,path):
    root=Path(root).resolve();path=Path(path).absolute()
    if not path.is_relative_to(root) or path==root:raise ValueError('BLOCK_OPERATOR_STATE_LOCATION')
    for part in (path,*path.parents):
        if part.exists() and (part.is_symlink() or getattr(part.lstat(),'st_file_attributes',0)&0x400):raise ValueError('BLOCK_REPARSE_STATE')
    return path
def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
def lease_status(path,identity,now=None):
    now=time.time() if now is None else now
    if not path.exists():return 'UNACQUIRED'
    try:
        record=json.loads(path.read_text());current=identity(record['owner']['pid'])
        if record['expires_unix']<=now or current!=record['owner']:return 'STALE_LEASE_MANUAL_REVIEW_NO_TAKEOVER'
        if path.with_name('lease.released.json').exists():return 'RELEASED_RETAINED_NO_REUSE'
        return 'ACTIVE_ADVISORY_ONLY'
    except (OSError,ValueError,KeyError,TypeError):return 'STALE_OR_CORRUPT_MANUAL_REVIEW_NO_TAKEOVER'
def acquire(directory,owner,baseline_sha,identity,ttl=900,now=None):
    if not isinstance(ttl,int) or not 1<=ttl<=900:raise ValueError('BLOCK_LEASE_TTL')
    if len(baseline_sha)!=64 or any(c not in '0123456789abcdef' for c in baseline_sha):raise ValueError('BLOCK_BASELINE_HASH')
    if identity(owner['pid'])!=owner:raise ValueError('BLOCK_OWNER_IDENTITY')
    directory=inside(STATE_ROOT,directory);directory.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex;now=time.time() if now is None else now
    record={'format':1,'advisory_only':True,'enforces_external_exclusion':False,'token':token,'owner':owner,
            'baseline_sha256':baseline_sha,'created_unix':now,'expires_unix':now+ttl}
    try:write_new(directory/'lease.json',record)
    except FileExistsError:raise ValueError('BLOCK_EXISTING_LEASE_NO_AUTOMATIC_TAKEOVER')
    return record
def release(directory,token,identity):
    directory=inside(STATE_ROOT,directory);path=directory/'lease.json'
    record=json.loads(path.read_text())
    if token!=record['token'] or identity(record['owner']['pid'])!=record['owner']:raise ValueError('BLOCK_LEASE_OWNERSHIP')
    write_new(directory/'lease.released.json',{'token':token,'released_unix':time.time()})
    return 'RELEASED_WITHOUT_DELETING_LEASE'
def compare(expected,actual):
    for key in ('identities','original_hashes','isolated_hashes','backend_sha','backend_status','pwa_head','release_pins'):
        if expected[key]!=actual[key]:raise ValueError('BLOCK_BASELINE_DRIFT:'+key)
    if actual['backend_sha']!=EXPECTED_BUILD or actual['backend_status']:raise ValueError('BLOCK_BACKEND_SOURCE')
    if set(actual['identities'])!={'5173','8005','8006','8007','8008'}:raise ValueError('BLOCK_PORT_COVERAGE')
    if any(len(actual['ports'][p])!=1 for p in actual['identities']):raise ValueError('BLOCK_AMBIGUOUS_LISTENER')
    for key in ('5173/engine/api/v1/health','8005/api/health','8006/api/v1/health','8007/api/news','8008/api/v1/health','5173/engine/openapi.json','8008/openapi.json'):
        if actual['health'][key].get('http')!=200:raise ValueError('BLOCK_HEALTH:'+key)
    if actual['health']['5173/engine/openapi.json']['sha256']!=actual['health']['8008/openapi.json']['sha256']:raise ValueError('BLOCK_PROXY_SCHEMA')
    for key in ('5173/engine/api/v1/health','8006/api/v1/health','8008/api/v1/health'):
        if actual['health'][key].get('safe_summary',{}).get('data_status')!='OK':raise ValueError('BLOCK_PROVIDER_HEALTH:'+key)
    return True
def acceptance(stage,process,attestation,verify):
    if stage=='A_PLAN':return {'status':'PLAN_BASELINE_PASS','current_exact_runtime':'EXACT_RUNNING_VERSION_UNVERIFIED','apply_allowed':False}
    if not attestation:raise ValueError('EXACT_RUNNING_VERSION_UNVERIFIED')
    if attestation.get('process')!=process or attestation.get('loaded',{}).get('loaded_function_code_sha256')!=EXPECTED_FINGERPRINT:raise ValueError('BLOCK_ATTESTATION_IDENTITY')
    if attestation.get('build_sha')!=EXPECTED_BUILD or attestation.get('execution_permission') is not False:raise ValueError('BLOCK_ATTESTATION_POLICY')
    if verify() is not True:raise ValueError('BLOCK_ATTESTATION_VERIFICATION')
    return {'status':'ATTESTATION_VERIFIED','apply_allowed':False}
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    check=sub.add_parser('preflight');check.add_argument('--baseline',type=Path,required=True);check.add_argument('--baseline-sha256',required=True)
    check.add_argument('--stage',choices=['A_PLAN','B'],default='B')
    check.add_argument('--startup',type=Path)
    lease=sub.add_parser('lease-status');lease.add_argument('--state',type=Path,required=True)
    take=sub.add_parser('acquire');take.add_argument('--state',type=Path,required=True);take.add_argument('--owner-pid',type=int,required=True);take.add_argument('--baseline-sha256',required=True)
    close=sub.add_parser('release');close.add_argument('--state',type=Path,required=True);close.add_argument('--token',required=True)
    args=p.parse_args();runtime=module('attested-runtime')
    if args.action=='lease-status':result={'lease':lease_status(inside(STATE_ROOT,args.state)/'lease.json',runtime.process_identity)}
    elif args.action=='acquire':result=acquire(args.state,runtime.process_identity(args.owner_pid),args.baseline_sha256,runtime.process_identity)
    elif args.action=='release':result={'lease':release(args.state,args.token,runtime.process_identity)}
    else:
        raw=args.baseline.read_bytes()
        if runtime.digest(raw)!=args.baseline_sha256:raise ValueError('BLOCK_BASELINE_HASH')
        before=json.loads(raw);now=module('coordination-audit').snapshot();compare(before,now)
        # B requires a separately reviewed post-A baseline and the exact owned startup receipt.
        record=json.loads(args.startup.read_text()) if args.startup else None
        def verify():
            c=json.loads((ROOT/'release/attested-8008-56cbd7e/launch-inputs.json').read_text())
            module('attested-acceptance').verify(c,8008,args.startup)
            return True
        result=acceptance(args.stage,now['identities']['8008'],record,verify)
        result.update(writes=0,deletes=0,live_mutations=False,external_workflows_paused='NOT_PROVEN')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
