"""Read-only live evidence and isolated frontend release staging. Never APPLY."""
from datetime import datetime
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import urllib.error
import zipfile
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/final-pwa-56cbd7e-revision2'
ORIGINAL=(Path(__file__).resolve().parents[2] / 'trade-ai-forex-web')
BACKEND=(Path(__file__).resolve().parents[2] / 'day-trader-skill')
BASE='01c96bb950804ed11fdb512937a81b554ddd669c'
BUILD='56cbd7e05a40b106deda9298e2be28b488d0d952'
LOADED='314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b'
OPERATION=ROOT/'release/approved-8008-62c78b12170f4c8a88896846f4ff152f'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):Path(path).write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8')
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True).strip()
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name.replace('_','-')+'.py'))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def observe():
    audit=module('bridge_drift_audit');runtime=module('attested_runtime');gate=module('runtime8008_preflight')
    ids={str(p):runtime.process_identity(runtime.port_owner(p)) for p in (5173,8005,8006,8007,8008)}
    expected=json.loads((OPERATION/'postflight.json').read_text())['processes']
    if ids!=expected:raise ValueError('BLOCKED_CONCURRENT_PROCESS_CHANGE')
    protected=gate.protected()
    if gate.git(BACKEND,'rev-parse','HEAD')!=BUILD or gate.git(BACKEND,'status','--porcelain'):
        raise ValueError('BLOCKED_BACKEND_SOURCE_CHANGE')
    c=json.loads((ROOT/'release/attested-8008-56cbd7e/launch-inputs.json').read_text())
    result=json.loads((OPERATION/'result.json').read_text());startup=Path(result['acceptance']['startup'])
    record=json.loads(startup.read_text())
    if record['loaded']['loaded_function_code_sha256']!=LOADED:raise ValueError('BLOCKED_LOADED_CODE')
    module('attested_acceptance').verify(c,8008,startup)
    direct=audit.request(8008,'/openapi.json');proxy=audit.request(5173,'/engine/openapi.json')
    gate.validate_route(direct,proxy,audit.request(8006,'/openapi.json'),'http://127.0.0.1:8008')
    health=audit.request(8008,'/api/v1/health')
    if health['data_status']!='OK':raise ValueError('BLOCKED_V5_HEALTH')
    params=module('cutover_process_inspect').inspect(ids['5173']['pid'])
    if Path(params['cwd']).resolve()!=ORIGINAL.resolve():raise ValueError('BLOCKED_5173_SOURCE_ROOT')
    return {'time_istanbul':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),
        'processes':ids,'protected_files':protected,'backend_sha':BUILD,'loaded_fingerprint':LOADED,
        'pwa_head':git('rev-parse','HEAD'),'pwa_status':git('status','--porcelain'),
        'health8008':health,'bridge_health':audit.request(8005,'/api/health'),
        'legacy_health':audit.request(8006,'/api/v1/health'),'news_available':audit.request(8007,'/api/news') is not None,
        'proxy':'http://127.0.0.1:8008','pwa_process_parameters':params,'startup':str(startup)}

def snapshot():
    OUT.mkdir()
    observation=observe();save(OUT/'begin.json',observation)
    save(OUT/'preexisting-worktree.json',{'head':git('rev-parse','HEAD'),'status':git('status','--porcelain')})
    for name in ('AnalysisPanel.tsx','App.tsx','MarketChart.tsx','NewsPanel.tsx','RiskCalculator.tsx',
                 'AnalysisNewsRisk.tsx','CalendarPanel.tsx'):
        relative='src/'+name
        base=subprocess.check_output(['git','-C',str(ROOT),'show',BASE+':'+relative])
        for kind,content in [('base',base),('current',(ORIGINAL/relative).read_bytes()),('rc-before',(ROOT/relative).read_bytes())]:
            dest=OUT/'snapshots'/kind/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
    for relative in ('package.json','package-lock.json','vite.config.ts','index.html'):
        dest=OUT/'snapshots/current'/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ORIGINAL/relative).read_bytes())
    print('PASS initial source/process/backend snapshot',OUT)

def api():
    req=module('bridge_drift_audit').request;gate=module('runtime8008_preflight');responses={}
    for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY'):
        data=req(8008,'/api/v5/analysis',{'symbol':symbol,'timeframe':'M15','confirmations':['H4'],
            'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1})
        gate.validate_analysis(symbol,data)
        if data['spread_status']['policy_status']!='UNAPPROVED':raise ValueError('BLOCKED_SPREAD')
        responses[symbol]=data
    save(OUT/'live-api.json',{'status':'PASS','responses':responses,'fixture':False,'backend_sha':BUILD,'loaded':LOADED})
    print('PASS all four real8008 safe refusal responses')

def finish():
    before=json.loads((OUT/'begin.json').read_text());after=observe()
    for key in ('processes','protected_files','backend_sha','loaded_fingerprint','proxy','pwa_process_parameters'):
        if before[key]!=after[key]:
            save(OUT/'end.json',after);raise ValueError('BLOCKED_CONCURRENT_CHANGE:'+key)
    save(OUT/'end.json',after);print('PASS original sources and five service identities unchanged')

def guard():
    before=json.loads((OUT/'begin.json').read_text());after=observe()
    for key in ('processes','protected_files','backend_sha','loaded_fingerprint','proxy','pwa_process_parameters'):
        if before[key]!=after[key]:raise ValueError('BLOCKED_CONCURRENT_CHANGE:'+key)
    print('PASS_READONLY_RUNTIME_AND_DESTINATION_GUARD')

def source_guard():
    before=json.loads((OUT/'begin.json').read_text());gate=module('runtime8008_preflight')
    if before['protected_files']!=gate.protected():raise ValueError('BLOCKED_CONCURRENT_SOURCE_CHANGE')
    if gate.git(BACKEND,'rev-parse','HEAD')!=BUILD or gate.git(BACKEND,'status','--porcelain'):
        raise ValueError('BLOCKED_BACKEND_SOURCE_CHANGE')
    print('PASS_SOURCE_ONLY; LIVE_READINESS_NOT_VERIFIED')

def blocked():
    runtime=module('attested_runtime');gate=module('runtime8008_preflight');audit=module('bridge_drift_audit')
    ps="Get-NetTCPConnection -State Listen -LocalPort 5173,8005,8006,8007,8008 -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess | ConvertTo-Json -Compress"
    listeners=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-Command',ps],text=True))
    processes={str(p):None for p in (5173,8005,8006,8007,8008)}
    for row in listeners:processes[str(row['LocalPort'])]=runtime.process_identity(row['OwningProcess'])
    health={}
    for port,route in ((5173,'/engine/api/v1/health'),(8005,'/api/health'),(8006,'/api/v1/health'),(8007,'/api/news'),(8008,'/api/v1/health')):
        try:
            value=audit.request(port,route)
            health[str(port)]={'available':True,'response':value if port not in (8007,) else 'news_available'}
        except urllib.error.HTTPError as exc:health[str(port)]={'available':False,'http_status':exc.code}
        except (OSError,TimeoutError):health[str(port)]={'available':False,'reason':'CONNECTION_UNAVAILABLE'}
    before=json.loads((OUT/'begin.json').read_text());protected=gate.protected()
    changed=[name for name in sorted(set(protected)|set(before['protected_files'])) if protected.get(name)!=before['protected_files'].get(name)]
    params=module('cutover_process_inspect').inspect(processes['5173']['pid']) if processes['5173'] else None
    reason=('8008_UNAVAILABLE_AND_PROTECTED_SERVICE_PID_CHANGES' if processes['8008'] is None
            else 'NEW_UNEXPECTED_8008_RUNTIME_AND_PROTECTED_SERVICE_PID_CHANGES')
    data={'status':'BLOCKED_CONCURRENT_CHANGE','reason':reason,
        'time_istanbul':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),'processes':processes,'listeners':listeners,
        'health':health,'protected_files':protected,'source_changes':changed,'original_sources_unchanged':not changed,
        'pwa_process_parameters':params,'backend_sha':gate.git(BACKEND,'rev-parse','HEAD'),
        'backend_clean':not gate.git(BACKEND,'status','--porcelain'),'pwa_apply':False,
        'service_operations_by_this_task':False,'new_runtime_baseline_accepted':False}
    save(OUT/'end-blocked.json',data);print(json.dumps({k:data[k] for k in ('status','reason','original_sources_unchanged','processes')},indent=2))

def quality():
    jobs={'typescript':['node','node_modules/typescript/bin/tsc','-b','--pretty','false'],
          'lint':['node','node_modules/eslint/bin/eslint.js','.'],
          'build':['node','node_modules/vite/bin/vite.js','build'],
          'client':['node','--test','tests/contract.test.mjs'],
          'client-extra':['node','--test','tests/final-pwa-client.test.mjs','tests/runtime8008-client.test.mjs','tests/attested-client.test.mjs'],
          'promotion':['node','--test','tests/promotion.test.mjs','tests/apply-rollback.test.mjs','tests/live-accept.test.mjs','tests/reconciled-release.test.mjs','tests/final-pwa-promotion.test.mjs']}
    results={}
    for name,command in jobs.items():
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
        (ROOT/'.artifacts'/('final-pwa-'+name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        results[name]={'status':'PASS' if result.returncode==0 else 'FAIL','exit_code':result.returncode}
        print(name,results[name]['status'],flush=True)
    browser=json.loads((OUT/'browser-core-results.json').read_text())['stats']
    preview=json.loads((ROOT/'.artifacts/preview-browser-results.json').read_text())['stats']
    cache=json.loads((OUT/'cache-upgrade.json').read_text())
    results.update(browser={'status':'PASS' if browser['expected']==40 and browser['unexpected']==0 else 'FAIL','stats':browser},
        preview={'status':'PASS' if preview['expected']==3 and preview['unexpected']==0 else 'FAIL','stats':preview},
        cache_upgrade={'status':cache['status'],'checks':len(cache['checks'])},
        current_live8008={'status':'FAIL','reason':'NO_LISTENER; isolated proxy503; active engine proxy502'},
        physical_phone={'status':'NOT_TESTED'})
    save(OUT/'quality.json',{'status':'PARTIAL','results':results,'source_fixture_gates_pass':all(
        r['status']=='PASS' for n,r in results.items() if n not in ('current_live8008','physical_phone')),
        'time_istanbul':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat()})
    if any(results[n]['status']!='PASS' for n in jobs):raise ValueError('BLOCKED_SOURCE_QUALITY_GATE')

def seal_blocked():
    source_guard()
    state=json.loads((OUT/'end-blocked.json').read_text());q=json.loads((OUT/'quality.json').read_text())
    if state['status']!='BLOCKED_CONCURRENT_CHANGE' or not q['source_fixture_gates_pass']:
        raise ValueError('Unexpected evidence state')
    manifest=json.loads((OUT/'manifest.json').read_text())
    if manifest['deployment_readiness']!='BLOCKED':raise ValueError('Must not seal a READY live release')
    for row in manifest['files']:
        if sha(ROOT/row['file'])!=row['source_sha256'] or sha(OUT/'payload'/row['file'])!=row['source_sha256']:
            raise ValueError('RC payload source changed')
    manifest.update(source_head=git('rev-parse','HEAD'),tests=q,deployable=False,
        current_services=state['processes'],backend_live_identity_verified=False,
        backend_expected_process=json.loads((OUT/'begin.json').read_text())['processes']['8008'],backend_process=state['processes']['8008'],
        previously_verified_backend_loaded_fingerprint=LOADED,backend_loaded_fingerprint=None,
        backend_loaded_fingerprint_status='CURRENT_PROCESS_UNVERIFIED; PRIOR_FINGERPRINT_IS_REFERENCE_ONLY',
        blocking_reason=state['reason'],rollback_readiness='FIXTURE_PASS; LIVE_APPLY_PROHIBITED')
    save(OUT/'manifest.json',manifest);(OUT/'manifest.sha256').write_text(sha(OUT/'manifest.json'))
    run=subprocess.run(['node','tools/final-pwa-promotion.mjs'],cwd=ROOT,capture_output=True,text=True,check=True)
    dry=json.loads(run.stdout)
    if dry['status']!='BLOCKED' or dry['writes'] or dry['deletes']:raise ValueError('Unexpected dry-run')
    save(OUT/'dry-run.json',dry)
    selected={p.relative_to(ROOT).as_posix():p for p in OUT.rglob('*') if p.is_file() and p.name not in ('package-manifest.json','sealed.json')}
    for name in ('tools/final-pwa-release.py','tools/final-pwa-promotion.mjs','tools/stage-final-pwa.mjs',
                 'tests/final-pwa-client.test.mjs','tests/final-pwa-live.mjs','tests/final-pwa-promotion.test.mjs',
                 'tests/frozen-target.mjs','tests/browser/final-pwa.spec.mjs','docs/V3_FINAL_PWA_RECONCILIATION_TR.md'):
        selected[name]=ROOT/name
    for path in (ROOT/'dist').rglob('*'):
        if path.is_file():selected['preview-build/'+path.relative_to(ROOT/'dist').as_posix()]=path
    for path in (ROOT/'.artifacts').glob('final-pwa-*.log'):selected['evidence/'+path.name]=path
    for name in ('manual-analysis-mobile.png','final-pwa-mobile-long-block.png','final-pwa-real8008-mobile.png'):
        path=ROOT/'.artifacts'/name
        if path.exists():selected['evidence/'+name]=path
    document={'status':'BLOCKED','deployable':False,'source_head':git('rev-parse','HEAD'),
        'live_apply_authorized':False,'reason':state['reason'],
        'preview_build_scope':'ISOLATED_BUILD_ONLY; NOT_LIVE_PAYLOAD',
        'earlier_real_browser_json':'Earlier success while9792 existed; NOT current readiness proof',
        'files':{n:sha(p) for n,p in selected.items()}}
    save(OUT/'package-manifest.json',document);selected['release/final-pwa-56cbd7e/package-manifest.json']=OUT/'package-manifest.json'
    archive=ROOT/'release'/('TRADE_AI_V3_PWA_8008_BLOCKED_EVIDENCE_'+git('rev-parse','--short=8','HEAD')+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as zipped:
        for name,path in selected.items():zipped.write(path,name)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip() or any(hashlib.sha256(zipped.read(n)).hexdigest()!=h for n,h in document['files'].items()):
            raise ValueError('Evidence ZIP integrity failed')
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
    save(OUT/'sealed.json',{'status':'BLOCKED','deployable':False,'archive':str(archive),'sha256':sha(archive)})
    print('PASS immutable BLOCKED evidence ZIP',archive,sha(archive))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['snapshot','api','finish','guard','source-guard','blocked','quality','seal-blocked'])
    a=p.parse_args();{'snapshot':snapshot,'api':api,'finish':finish,'guard':guard,'source-guard':source_guard,'blocked':blocked,'quality':quality,'seal-blocked':seal_blocked}[a.action]()
