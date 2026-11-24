"""Default read-only preflight; live 8008 replacement requires NEW approval.

No proxy/PWA write, no other service management. Not executed live in preparation.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import socket
import time
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/attested-8008-56cbd7e'
ARCHIVE=ROOT/'release/TRADE_AI_V3_ATTESTED_8008_56cbd7e_READY.zip'

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name.replace('_','-')+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def approval_gate(apply,approved,expected):
    if apply and (not approved or not expected):raise ValueError('NEW operator approval and exact package digest required')

def port_free():
    try:
        with socket.socket() as sock:sock.bind(('127.0.0.1',8008))
        return True
    except OSError:return False

def preflight(expected=None):
    runtime=module('attested_runtime');build=module('attested_release')
    c=json.loads((OUT/'launch-inputs.json').read_text())
    source=runtime.pinned_json(c['source_manifest'],c['source_sha256'])
    config=runtime.pinned_json(c['config'],c['config_sha256'])
    fallback=runtime.pinned_json(c['failback_config'],c['failback_config_sha256'])
    runtime.verify_source(c['release'],source)
    runtime.verify_source(c['failback_release'],source)
    runtime.validate_environment(config);runtime.validate_environment(fallback)
    if runtime.dependencies()!=config['dependencies'] or fallback['dependencies']!=config['dependencies']:
        raise ValueError('Deployment dependencies changed')
    observation=json.loads((OUT/'current-runtime-backup.json').read_text())['current_8008']
    if runtime.port_owner(8008)!=observation['pid'] or runtime.process_identity(observation['pid'])!=observation:
        raise ValueError('Active 8008 process changed; do not use old stop identity')
    gate=module('runtime8008_preflight')
    before=json.loads((OUT/'protected-before.json').read_text());current=gate.protected()
    # This controller has NO frontend write capability. Preserve the independent
    # PWA gate; unrelated user edits must not become a frontend approval.
    critical=[name for name in before if name.startswith(str(gate.BACKEND))
              or name==str(gate.ORIGINAL/'vite.config.ts')]
    if any(current.get(name)!=before[name] for name in critical):
        raise ValueError('Backend/proxy source drift')
    if expected:
        if runtime.file_hash(ARCHIVE)!=expected:raise ValueError('Reviewed ZIP digest mismatch')
        with zipfile.ZipFile(ARCHIVE) as zipped:
            sealed=json.loads(zipped.read('release/attested-8008-56cbd7e/package-manifest.json'))
        for name,digest in sealed['files'].items():
            if name.startswith('tools/') or name in (
                'release/attested-8008-56cbd7e/source.json','release/attested-8008-56cbd7e/config.json',
                'release/attested-8008-56cbd7e/failback-config.json',
                'release/attested-8008-56cbd7e/launch-inputs.json',
                'release/attested-8008-56cbd7e/current-runtime-backup.json',
                'release/attested-8008-56cbd7e/protected-before.json',
                'release/attested-8008-56cbd7e/reference-code-structure.json'):
                if runtime.file_hash(ROOT/name)!=digest:raise ValueError('Operational tool/config drift')
    return c,observation

def launch(c,fallback=False):
    build=module('attested_release')
    startup=OUT/('live-'+('failback-' if fallback else '')+uuid.uuid4().hex+'.json')
    log=ROOT/'.artifacts'/('attested-live-'+uuid.uuid4().hex+'.log')
    handle=log.open('w',encoding='utf-8')
    child=subprocess.Popen([c['python'],'-B',c['launcher'],'serve',*build.arguments(c,fallback),
        '--reference',c['reference'],'--startup',str(startup),'--port','8008','--operator-approved-cutover'],
        cwd=ROOT,stdout=handle,stderr=handle,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    handle.close();return child,startup

def await_acceptance(c,child,startup,fallback=False):
    acceptance=module('attested_acceptance');runtime=module('attested_runtime')
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        if child.poll() is not None:raise ValueError('New owned runtime exited')
        if startup.exists():
            try:record=json.loads(startup.read_text())
            except (OSError,json.JSONDecodeError):
                time.sleep(.1);continue  # Exclusive startup file may still be flushing.
            if record['process']['pid']!=child.pid and record['parent_pid']!=child.pid:
                raise ValueError('Startup manifest does not belong to owned launch')
            try:
                if runtime.port_owner(8008)==record['process']['pid']:
                    return acceptance.checks(c,8008,startup,fallback)
            except (subprocess.CalledProcessError,runtime.IntegrityError):pass
        time.sleep(.1)
    raise ValueError('New owned runtime acceptance timeout')

def stop_owned(child,startup):
    runtime=module('attested_runtime')
    if child.poll() is not None:return
    if not startup.exists():
        # This exact Popen process tree is ours even when startup failed early.
        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],check=True,
                       stdout=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    else:
        record=json.loads(startup.read_text())
        if record['parent_pid']!=child.pid and record['process']['pid']!=child.pid:
            raise ValueError('Owned stop identity mismatch')
        if runtime.process_identity(record['process']['pid'])!=record['process']:
            raise ValueError('Owned process identity changed')
        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],check=True,
                       stdout=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    child.wait(timeout=10)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-runtime',action='store_true')
    parser.add_argument('--operator-approved',action='store_true')
    parser.add_argument('--package-sha256')
    args=parser.parse_args()
    approval_gate(args.apply_runtime,args.operator_approved,args.package_sha256)
    c,old=preflight(args.package_sha256)
    if not args.apply_runtime:
        print(json.dumps({'status':'RUNTIME_ONLY_PREFLIGHT_PASS','live_writes':0,
                          'pwa_apply_authorized':False,'pwa_gate':'SEPARATE_REVIEW_REQUIRED'}));return
    acceptance=module('attested_acceptance');runtime=module('attested_runtime')
    # Both new code and failback are rehearsed before touching the old process.
    acceptance.owned(c);acceptance.owned(c,True)
    c,old=preflight(args.package_sha256)
    subprocess.run(['taskkill','/PID',str(old['pid']),'/T','/F'],check=True,
                   stdout=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        if port_free():break
        time.sleep(.1)
    else:raise ValueError('8008 is still owned; do not kill another process')
    primary=startup=None
    try:
        primary,startup=launch(c)
        result=await_acceptance(c,primary,startup)
        status='PRIMARY_ACCEPTED'
    except Exception:
        if primary is not None:stop_owned(primary,startup)
        # Refuse to overwrite any unexpected port owner.
        if not port_free():raise ValueError('Unexpected 8008 owner; failback stopped')
        fallback,backup_manifest=launch(c,True)
        result=await_acceptance(c,fallback,backup_manifest,True)
        status='FAILBACK_ACCEPTED'
    result.update(status=status,pwa_apply_authorized=False)
    path=OUT/('cutover-result-'+uuid.uuid4().hex+'.json')
    path.write_text(json.dumps(result,indent=2),encoding='utf-8');print(status,path)

if __name__=='__main__':main()
