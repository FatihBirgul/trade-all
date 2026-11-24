"""Read-only observations and a unique BLOCKED evidence bundle; never deploys."""
import argparse
from datetime import datetime
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import urllib.request
import urllib.error
import zipfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT.parent / 'trade-ai-forex-web'
BACKEND = ROOT.parent / 'trade-ai-v3-core'
BASE = '01c96bb950804ed11fdb512937a81b554ddd669c'
EXPECTED = '56cbd7e05a40b106deda9298e2be28b488d0d952'
OLD = ROOT / 'release/final-pwa-56cbd7e'

def sha(data): return hashlib.sha256(data).hexdigest()
def save(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
def git(root, *args): return subprocess.check_output(['git', '-C', str(root), *args])
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj
def files(root):
    result = []
    for folder in ('src', 'public'):
        result += [p for p in (root / folder).rglob('*') if p.is_file()]
    result += [root / n for n in ('package.json','package-lock.json','vite.config.ts','index.html','eslint.config.js','tsconfig.json','tsconfig.app.json','tsconfig.node.json','mt5_bridge.py','news_bridge.py') if (root / n).is_file()]
    return {p.relative_to(root).as_posix(): sha(p.read_bytes()) for p in sorted(result)}
def observe():
    cmd = 'Get-NetTCPConnection -State Listen -LocalPort 5173,8005,8006,8007,8008 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress'
    raw = subprocess.check_output(['powershell.exe','-NoProfile','-Command',cmd], text=True).strip()
    listeners = json.loads(raw) if raw else []
    if isinstance(listeners, dict): listeners = [listeners]
    runtime = module('attested-runtime'); inspect = module('cutover-process-inspect')
    processes = {str(p): None for p in (5173,8005,8006,8007,8008)}
    for row in listeners:
        owner = row['OwningProcess']; ident = runtime.process_identity(owner)
        cmd = f'Get-Process -Id {owner} | Select-Object @{{n="start_utc";e={{$_.StartTime.ToUniversalTime().ToString("o")}}}} | ConvertTo-Json -Compress'
        ident.update(json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-Command',cmd], text=True)))
        ident['source'] = inspect.inspect(owner)
        processes[str(row['LocalPort'])] = ident
    health = {}
    for port, route in ((5173,'/engine/api/v1/health'),(8005,'/api/health'),(8006,'/api/v1/health'),(8007,'/api/news'),(8008,'/api/v1/health'),(8008,'/openapi.json')):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}{route}', timeout=5) as response:
                body = response.read()
                health[f'{port}{route}'] = {'status':response.status,'sha256':sha(body),'body':json.loads(body) if port != 8007 else 'NEWS_AVAILABLE'}
        except (OSError, ValueError) as exc:
            health[f'{port}{route}'] = {'status':getattr(exc,'code',None),'error':type(exc).__name__}
    return {'time_istanbul':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(), 'processes':processes,'health':health,
            'original_hashes':files(ORIGINAL),'isolated_hashes':files(ROOT),
            'backend_sha':git(BACKEND,'rev-parse','HEAD').decode().strip(),
            'backend_status':git(BACKEND,'status','--porcelain').decode(),
            'head':git(ROOT,'rev-parse','HEAD').decode().strip(), 'git_status':git(ROOT,'status','--porcelain').decode(),
            'proxy_source':(ORIGINAL/'vite.config.ts').read_text(encoding='utf-8'),
            'live_apply':False,'service_mutations':False}

def snapshot(out):
    out.mkdir(parents=True, exist_ok=False)
    save(out/'begin.json', observe())
    for kind, root in (('current',ORIGINAL),('rc-before',ROOT)):
        for name in files(root):
            dest=out/'snapshots'/kind/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((root/name).read_bytes())
    print(out)

def finish(out):
    if (out/'sealed.json').exists(): raise ValueError('Immutable sealed release')
    before=json.loads((out/'begin.json').read_text(encoding='utf-8')); after=observe()
    save(out/'end.json',after)
    checks={key:before[key]==after[key] for key in ('processes','original_hashes','isolated_hashes','backend_sha','backend_status','proxy_source')}
    save(out/'preservation.json',{'checks':checks,'status':'PASS' if all(checks.values()) else 'BLOCKED_CONCURRENT_CHANGE'})
    print(json.dumps(checks))

def package(out):
    if (out/'sealed.json').exists(): raise ValueError('Immutable sealed release')
    before=json.loads((out/'begin.json').read_text(encoding='utf-8'))
    after=json.loads((out/'end.json').read_text(encoding='utf-8'))
    previous=json.loads((OLD/'manifest.json').read_text())
    decisions={r['file']:r for r in json.loads((OLD/'conflict-matrix.json').read_text(encoding='utf-8'))['decisions']}
    preservation=json.loads((out/'preservation.json').read_text())
    runtime_paths=[f['file'] for f in previous['files']]
    rows=[]; payload=[]
    for name in sorted(set(before['original_hashes'])|set(files(ROOT))):
        try: base=git(ROOT,'show',BASE+':'+name)
        except subprocess.CalledProcessError: base=None
        if base is not None:
            dest=out/'snapshots/base'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(base)
        current=(ORIGINAL/name).read_bytes() if (ORIGINAL/name).exists() else None
        rc=(ROOT/name).read_bytes() if (ROOT/name).exists() else None
        h=lambda b:None if b is None else sha(b)
        canon=lambda b:None if b is None else b.decode('utf-8',errors='replace').replace('\r\n','\n')
        row={'file':name,'base_sha256':h(base),'current_sha256':h(current),'rc_sha256':h(rc),
             'current_changed':canon(base)!=canon(current),'rc_changed':canon(base)!=canon(rc),
             'categories':decisions.get(name,{}).get('categories',['Mevcut davranışın korunması']),
             'resolution':decisions.get(name,{}).get('resolution','REVIEWED_RC_PAYLOAD' if name in runtime_paths else 'PRESERVE_DESTINATION_EXCLUDED')}
        rows.append(row)
        if name in runtime_paths:
            dest=out/'payload'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(rc)
            payload.append({'file':name,'source_sha256':h(rc),'expected_target_sha256':h(current)})
            diff=''.join(difflib.unified_diff(canon(current or b'').splitlines(True),canon(rc).splitlines(True),fromfile='CURRENT/'+name,tofile='RC/'+name))
            dest=out/'diffs'/(name+'.diff');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(diff,encoding='utf-8')
    for name,expected in before['original_hashes'].items():
        src=out/'snapshots/current'/name
        if sha(src.read_bytes())!=expected: raise ValueError('Snapshot backup mismatch')
    # Guard inventory follows the existing deployment tool; the independent snapshot above also covers .bak files.
    guards=[{'file':g['file'],'sha256':before['original_hashes'][g['file']]} for g in previous['guards']]
    if any(after['original_hashes'].get(g['file'])!=g['sha256'] for g in guards):raise ValueError('Target changed')
    save(out/'source-manifest.json',{'files':[{'file':f['file'],'sha256':f['source_sha256']} for f in payload]})
    save(out/'destination-manifest.json',{'target_root':str(ORIGINAL),'all_source_hashes':before['original_hashes'],'guards':guards})
    save(out/'conflict-matrix.json',{'base':BASE,'base_provenance':git(ROOT,'show','-s','--format=%s',BASE).decode().strip(),'automatic_merge':False,'files':rows})
    tests=json.loads((out/'quality-results.json').read_text(encoding='utf-8'))
    changed_ports=[p for p in before['processes'] if before['processes'][p]!=after['processes'][p]]
    reason='BLOCKED_CONCURRENT_RUNTIME_CHANGE; CURRENT_LOADED_FINGERPRINT_NOT_VERIFIED' if changed_ports else '8008_UNAVAILABLE; CURRENT_LOADED_FINGERPRINT_AND_LIVE_API_CANNOT_BE_VERIFIED'
    m={**previous,'source_head':after['head'],'deployment_readiness':'BLOCKED','blocking_reason':reason,
       'changed_service_ports':changed_ports,
       'created_at':after['time_istanbul'],'backend_sha':EXPECTED,'backend_live_identity_verified':False,
       'backend_loaded_fingerprint':None,'historical_loaded_fingerprint':previous['backend_loaded_fingerprint'],
       'backend_process':after['processes']['8008'],'backend_startup':None,'files':payload,'guards':guards,
       'guard_inventory':sorted(g['file'] for g in guards),'tests':tests,
       'backup_validation':{'status':'PASS','root':'snapshots/current','files':len(before['original_hashes']),'live_apply_backup':'NOT_RUN'},
       'rollback_readiness':'FIXTURE_TESTED; LIVE_NOT_RUN','preservation':preservation,'approval_received':False,'pwa_apply_authorized':False}
    save(out/'manifest.json',m);(out/'manifest.sha256').write_text(sha((out/'manifest.json').read_bytes()))
    command="import {dryRun} from './tools/final-pwa-promotion.mjs'; console.log(JSON.stringify(dryRun(process.argv[1])))"
    dry=json.loads(subprocess.check_output(['node','--input-type=module','-e',command,str(out)],cwd=ROOT,text=True))
    if dry['writes']!=0 or dry['deletes']!=0 or dry['status']!='BLOCKED':raise ValueError('Unsafe dry run')
    save(out/'dry-run.json',dry)
    save(out/'sealed.json',{'status':'BLOCKED','files':{p.relative_to(out).as_posix():sha(p.read_bytes()) for p in out.rglob('*') if p.is_file()}})
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
        for p in out.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(out))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None: raise ValueError('Archive CRC failed')
        for p in out.rglob('*'):
            if p.is_file() and sha(z.read(p.relative_to(out).as_posix()))!=sha(p.read_bytes()):raise ValueError('Archive hash failed')
    digest=sha(archive.read_bytes());Path(str(archive)+'.sha256').write_text(digest+'\n')
    print(json.dumps({'status':'BLOCKED','zip':str(archive),'sha256':digest,'payload_files':len(payload)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['snapshot','finish','package']);parser.add_argument('output')
    args=parser.parse_args();out=Path(args.output).resolve()
    if out.parent!=ROOT/'release':raise ValueError('Isolated release directory required')
    {'snapshot':snapshot,'finish':finish,'package':package}[args.action](out)
