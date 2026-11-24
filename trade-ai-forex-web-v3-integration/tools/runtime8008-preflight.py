"""Read-only 8008 reconciliation. No APPLY, restart or source-version promotion."""
import os
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/runtime8008-56cbd7e'
ORIGINAL=(Path(__file__).resolve().parents[2] / 'trade-ai-forex-web')
BACKEND=(Path(__file__).resolve().parents[2] / 'day-trader-skill')
SHA='56cbd7e05a40b106deda9298e2be28b488d0d952'
RC='34c6ec2e1a02893cd1d8301d8bf6c5048c6aeb05'
RC_MANIFEST_SHA='1035c98420554d268c32f1a38bd0ed19379c18a67c53d93362edee216105b715'
PLAN_FIELDS=('entry_zone','stop_loss','take_profit_1','take_profit_2','lot_size')

def digest(raw): return hashlib.sha256(raw).hexdigest()
def file_hash(p): return digest(p.read_bytes())
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':')).encode()
def save(p,data): p.write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8')
def git(root,*args): return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def original_rc():
    path=ROOT/'release/rc/manifest.json'
    if file_hash(path)!=RC_MANIFEST_SHA: raise ValueError('Reviewed RC manifest changed')
    return json.loads(path.read_text())
def request(base,route,body=None):
    req=urllib.request.Request(base+route,data=canonical(body) if body else None,
                              headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as response:
        if response.status!=200: raise ValueError('HTTP acceptance failed')
        return json.load(response)

def validate_route(direct,proxy,old,target):
    if target!='http://127.0.0.1:8008': raise ValueError('Wrong proxy target')
    fields=direct['components']['schemas']['UnifiedAnalysis']['properties']
    if 'historical_session_evidence' not in fields: raise ValueError('Old schema is not new runtime')
    if canonical(direct)!=canonical(proxy): raise ValueError('Proxy schema mismatch')
    if canonical(direct)==canonical(old): raise ValueError('Old runtime must remain distinguishable')
    if any('order' in route for route in direct['paths']): raise ValueError('Order routes refused')

def validate_analysis(symbol,data):
    if (data.get('symbol')!=symbol or data.get('provider')!='mt5'
            or data.get('market_data_account_mode')!='REAL'
            or data.get('account_currency')!='USC'
            or data.get('risk_balance_source')!='HYPOTHETICAL_CAPITAL'
            or data.get('execution_permission') is not False
            or data.get('trading_eligibility')!='BLOCKED'):
        raise ValueError('Read-only/hypothetical identity mismatch')
    if any(data.get(k) is not None for k in PLAN_FIELDS): raise ValueError('Unsafe plan exposure')
    spread=data.get('spread_status',{})
    if (spread.get('policy_status') not in ('UNAPPROVED','UNVERIFIED') or spread.get('decision')!='BLOCK'
            or spread.get('max_allowed_price') is not None): raise ValueError('Spread gate mismatch')
    hist=data.get('historical_session_evidence',{})
    if hist.get('status')!='SOURCE_NOT_SUPPLIED' or hist.get('historical_gap_authorized') is not False:
        raise ValueError('Historical evidence gate mismatch')
    if data.get('broker_contract',{}).get('status')!='CURRENT_MT5_OBSERVED':
        raise ValueError('Current contract observation mismatch')
    for name in ('chart_patterns','candlestick_patterns'):
        context=data.get(name)
        if context is not None and not isinstance(context,dict): raise ValueError('Pattern shape mismatch')
        role=(context or {}).get('role')
        if role not in (None,'DESCRIPTIVE_ONLY'): raise ValueError('Pattern role mismatch')

def version_gate(*,disk_sha,public_digest_matches,startup_attestation):
    # This task found a plain uvicorn process, without same-process loaded-code
    # attestation. Caller-supplied JSON, disk and public digests cannot upgrade it.
    if disk_sha!=SHA or not public_digest_matches: return 'VERSION_MISMATCH'
    return 'VERSION_UNVERIFIED'

def protected():
    files=list((ORIGINAL/'src').rglob('*'))+list((ORIGINAL/'public').rglob('*'))
    files += [p for p in ORIGINAL.iterdir() if p.suffix in ('.py','.json','.ts','.js','.html')]
    result={str(p):file_hash(p) for p in files if p.is_file()}
    result.update({str(BACKEND/p):file_hash(BACKEND/p) for p in git(BACKEND,'ls-files').splitlines()})
    return result

def acceptance():
    direct=request('http://127.0.0.1:8008','/openapi.json')
    old=request('http://127.0.0.1:8006','/openapi.json')
    proxy=request('http://127.0.0.1:5173','/engine/openapi.json')
    config=(ORIGINAL/'vite.config.ts').read_text(encoding='utf-8')
    if "target: 'http://127.0.0.1:8008'" not in config: raise ValueError('Proxy disk drift')
    validate_route(direct,proxy,old,'http://127.0.0.1:8008')
    checks=['new_schema','old_schema_distinguished','no_order_routes','disk_proxy8008','actual_proxy_matches8008']
    remote=request('https://' + os.environ['TRADE_TAILSCALE_HOST'],'/engine/openapi.json')
    if canonical(remote)!=canonical(direct): raise ValueError('Tailscale schema mismatch')
    checks.append('tailscale_proxy_matches8008')
    health=request('http://127.0.0.1:8008','/api/v1/health')
    if health.get('provider')!='mt5' or health.get('data_status')!='OK': raise ValueError('V5 health failed')
    checks.append('health')
    responses={}
    for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY'):
        meta=request('http://127.0.0.1:8008',f'/api/v1/symbols/{symbol}/metadata')['data']
        if (meta.get('broker_symbol')!=symbol+'c' or meta.get('broker_server')!='Exness-MT5Real50'
                or meta.get('account_currency')!='USC'): raise ValueError('Broker metadata mismatch')
        checks.append(symbol+'_exact_identity')
        data=request('http://127.0.0.1:8008','/api/v5/analysis',{
            'symbol':symbol,'timeframe':'M15','confirmations':['H4'],
            'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1})
        validate_analysis(symbol,data)
        checks.append(symbol+'_readonly_safety')
        # Public UnifiedAnalysis has no account login or REAL balance fields.
        # Keep the actual wire response for independent RC parser acceptance.
        responses[symbol]=data
    # A fresh interpreter here computes a disk-content comparison ONLY.
    candidate=(Path.home() / 'trade-ai-v3-runtime-candidate')
    command=[str((Path.home() / 'AppData/Local/TradeAI/V5CandidateRuntime/Scripts/python.exe')),
             '-B','-c',"from forex.unified import public_code_digest;print(public_code_digest())"]
    expected=subprocess.check_output(command,cwd=candidate,text=True).strip()
    match=all(d['source_versions'].get('public_code_sha256')==expected for d in responses.values())
    version=version_gate(disk_sha=git(candidate,'rev-parse','HEAD'),public_digest_matches=match,startup_attestation=None)
    result={'http_status':'PASS','checks':checks,'count':len(checks),'responses':responses,
            'public_disk_digest_matches':match,'expected_public_disk_digest':expected,
            'runtime_version_status':version,'status':'BLOCKED_BACKEND_RUNTIME',
            'reason':'No same-process loaded-code attestation for PID 13988',
            'schema_sha256':digest(canonical(direct)),'old_schema_sha256':digest(canonical(old)),
            'proxy_target':'http://127.0.0.1:8008','execution_permission':False}
    save(OUT/'api-acceptance.json',result)
    print(json.dumps({k:result[k] for k in ('http_status','count','runtime_version_status','status')}))

def stage():
    OUT.mkdir()
    save(OUT/'protected-before.json',protected())
    old=original_rc()
    rows=[]
    for row in old['files']:
        source=ROOT/row['file']; dest=ORIGINAL/row['file']
        if file_hash(source)!=row['source_sha256']: raise ValueError('RC source changed')
        output=OUT/'payload'/row['file'];output.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,output)
        rows.append({'file':row['file'],'source_sha256':file_hash(source),
                     'destination_sha256':file_hash(dest) if dest.is_file() else None})
    guards=[]
    for row in old['guards']:
        source=ORIGINAL/row['file']; output=OUT/'backup'/row['file']
        output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,output)
        if file_hash(source)!=file_hash(output): raise ValueError('Backup verification failed')
        guards.append({'file':row['file'],'sha256':file_hash(source)})
    manifest={'format':'PWA8008_REVIEW_1','backend_sha':SHA,'pwa_ui_sha':RC,
        'files':rows,'guards':guards,'proxy_target':'http://127.0.0.1:8008',
        'proxy_config_in_payload':False,'status':'BLOCKED_BACKEND_RUNTIME','deployable':False,
        'approval_received':False,'prerequisites':['Reliable same-process runtime version evidence',
        'Fresh file/process/proxy preflight','New explicit PWA-only operator approval']}
    save(OUT/'manifest.json',manifest)
    (OUT/'manifest.sha256').write_text(file_hash(OUT/'manifest.json'))
    print('PASS new 8008 manifest, 9 payload files, 27 verified backup guards')

def dry_run(target=ORIGINAL):
    raw=(OUT/'manifest.json').read_bytes()
    if digest(raw)!=(OUT/'manifest.sha256').read_text(): raise ValueError('Manifest corruption')
    manifest=json.loads(raw)
    previous=original_rc()
    allowed=sorted(row['file'] for row in previous['files'])
    if sorted(row['file'] for row in manifest['files'])!=allowed: raise ValueError('Allowlist mismatch')
    if sorted(row['file'] for row in manifest['guards'])!=sorted(row['file'] for row in previous['guards']):
        raise ValueError('Guard coverage mismatch')
    for row in manifest['guards']:
        if file_hash(target/row['file'])!=row['sha256']: raise ValueError('Target guard drift')
        if file_hash(OUT/'backup'/row['file'])!=row['sha256']: raise ValueError('Backup corruption')
    for row in manifest['files']:
        if file_hash(OUT/'payload'/row['file'])!=row['source_sha256']: raise ValueError('Payload corruption')
        dest=target/row['file']; actual=file_hash(dest) if dest.is_file() else None
        if actual!=row['destination_sha256']: raise ValueError('Destination drift')
    return {'file_preflight':'PASS','writes':0,'deletes':0,'files':9,'guards':27,
            'runtime_gate':'BLOCKED_BACKEND_RUNTIME','deployable':False}

def seal():
    dry_run()
    if protected()!=json.loads((OUT/'protected-before.json').read_text()): raise ValueError('Protected source drift')
    result=json.loads((OUT/'api-acceptance.json').read_text())
    manifest={'status':'BLOCKED_BACKEND_RUNTIME','deployable':False,'approval_received':False,
              'backend_sha':SHA,'pwa_ui_sha':RC,'pwa_tooling_sha':git(ROOT,'rev-parse','HEAD'),
              'runtime_version_status':result['runtime_version_status'],'proxy_target':'http://127.0.0.1:8008'}
    files={}
    for name in ('tools/runtime8008-preflight.py','tests/runtime8008_test.py',
                 'tests/runtime8008-client.test.mjs','docs/V3_RUNTIME8008_RECONCILIATION_TR.md',
                 'docs/V3_RUNTIME8008_RELEASE_PLAN.md'):
        files[name]=ROOT/name
    for source in OUT.rglob('*'):
        if source.is_file() and source.name!='source-manifest.json': files[source.relative_to(ROOT).as_posix()]=source
    files['evidence/runtime8008-initial.json']=ROOT/'.artifacts/runtime8008-initial.json'
    for name in ('runtime8008-tests.log','runtime8008-client.log','runtime8008-actual-client.log',
                 'runtime8008-lint.log','runtime8008-build.log'):
        files['evidence/'+name]=ROOT/'.artifacts'/name
    manifest['files']={name:file_hash(source) for name,source in sorted(files.items())}
    save(OUT/'source-manifest.json',manifest)
    files['release/runtime8008-56cbd7e/source-manifest.json']=OUT/'source-manifest.json'
    archive=ROOT/'release/TRADE_AI_V3_PWA_8008_56cbd7e_BLOCKED_RUNTIME.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as zipped:
        for name,source in files.items(): zipped.write(source,name)
    with zipfile.ZipFile(archive) as zipped:
        if zipped.testzip(): raise ValueError('ZIP CRC failed')
        if any(digest(zipped.read(name))!=value for name,value in manifest['files'].items()): raise ValueError('ZIP hash mismatch')
    archive.with_suffix('.zip.sha256').write_text(file_hash(archive)+'  '+archive.name+'\n')
    print('PASS new ZIP',file_hash(archive),len(files),'files; BLOCKED_BACKEND_RUNTIME')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['stage','accept','dry-run','seal'])
    args=parser.parse_args()
    if args.action=='stage': stage()
    elif args.action=='accept': acceptance()
    elif args.action=='dry-run': print(json.dumps(dry_run()))
    elif args.action=='seal': seal()

if __name__=='__main__':main()
