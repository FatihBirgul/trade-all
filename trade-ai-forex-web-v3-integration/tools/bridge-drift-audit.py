"""Bridge source/runtime audit only. No restart, APPLY, or active rebaseline."""
import ast
import copy
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

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/bridge-drift-audit-9124'
ORIGINAL=(Path(__file__).resolve().parents[2] / 'trade-ai-forex-web')
BACKEND=(Path(__file__).resolve().parents[2] / 'day-trader-skill')
SHA='56cbd7e05a40b106deda9298e2be28b488d0d952'
OLD='1a47e33f13c929612f811a71c8bd1734ad1a74eb6b58c3d55473b579a3037718'
CURRENT='1a74d26f8b6ec217ff3122bfeb9bdda5db2839db6aab0d3af7f3d2a4163f8ef7'
ARCHIVE=ROOT/'release/TRADE_AI_V3_ATTESTED_8008_56cbd7e_READY.zip'
ARCHIVE_SHA='a7e21cfca44c0963b689ff88f6d7e3f85f8a39c8a5a3b47e2dbeeaece6f66ef9'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):Path(path).write_text(json.dumps(value,indent=2,sort_keys=True),encoding='utf-8')
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name.replace('_','-')+'.py'))
    item=importlib.util.module_from_spec(spec);spec.loader.exec_module(item);return item
def request(port,path,body=None):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+path,
        data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:return json.load(response)

def constants(tree):
    return {n.targets[0].id:ast.literal_eval(n.value) for n in tree.body
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)
        and n.targets[0].id in ('SYMBOLS','RISK_SYMBOLS','MT5_SYMBOL_MAP')}

def normalize(tree):
    tree=copy.deepcopy(tree)
    tree.body=[n for n in tree.body if not(isinstance(n,ast.Assign)
        and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('SYMBOLS','RISK_SYMBOLS','MT5_SYMBOL_MAP'))]
    risk=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='risk_preview')
    for node in ast.walk(risk):
        if isinstance(node,ast.Name) and node.id=='RISK_SYMBOLS':node.id='SYMBOLS'
    return ast.dump(tree,include_attributes=False)

def source_audit():
    before=OUT/'approved-mt5_bridge.py';after=OUT/'observed-mt5_bridge.py'
    a=ast.parse(before.read_text());b=ast.parse(after.read_text())
    old=constants(a);new=constants(b)
    calls=sorted({n.func.attr for n in ast.walk(b) if isinstance(n,ast.Call)
        and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='mt5'})
    forbidden={'order_send','order_check','login','logout','positions_close','orders_send'}
    suspicious=[ast.unparse(n) for n in ast.walk(b) if isinstance(n,ast.Call)
        and isinstance(n.func,ast.Name) and n.func.id in ('eval','exec','compile','__import__')]
    assert not set(calls)&forbidden and not suspicious
    assert normalize(a)==normalize(b),'Unexpected executable logic outside audited hunks'
    assert old['SYMBOLS']==new['RISK_SYMBOLS'] and old['MT5_SYMBOL_MAP'].items()<=new['MT5_SYMBOL_MAP'].items()
    assert new['SYMBOLS']==set(new['MT5_SYMBOL_MAP']) and len(new['SYMBOLS'])==19
    result={'old_sha256':sha(before),'current_sha256':sha(after),
        'normalized_executable_rest_equal':True,'old_symbols':sorted(old['SYMBOLS']),
        'added_chart_symbols':sorted(new['SYMBOLS']-old['SYMBOLS']),
        'risk_scope_preserved':sorted(new['RISK_SYMBOLS']),'mt5_calls':calls,
        'new_imports':False,'new_order_or_account_write_paths':False,
        'changes':[{'change':'Chart symbol/map expansion 4 -> 19','classification':'REQUIRES_REVIEW',
                    'scope':'Software delta bounded; added broker product/visibility scope not live-authorized'},
                   {'change':'Separate RISK_SYMBOLS keeps effective risk scope at original four','classification':'SAFE'}],
        'preexisting_review_items':['Conditional symbol_select mutates MarketWatch',
            'Reconnect uses shutdown/initialize on lost IPC','Forming chart candle is included',
            'No exact REAL_READONLY_DATA/server guard on market-data routes',
            'Risk preview permits REAL USC Exness-* but still labels demo_only=true'],
        'bridge_loaded_version':'BRIDGE_LOADED_VERSION_UNVERIFIED','actor':'UNVERIFIED'}
    save(OUT/'source-audit.json',result)
    (OUT/'bridge.diff').write_text(''.join(difflib.unified_diff(before.read_text().splitlines(True),
        after.read_text().splitlines(True),fromfile='approved/mt5_bridge.py',tofile='observed/mt5_bridge.py')),encoding='utf-8')
    return result

def observe():
    runtime=module('attested_runtime')
    identities={str(port):runtime.process_identity(runtime.port_owner(port)) for port in (5173,8005,8006,8007,8008)}
    code=(ORIGINAL/'vite.config.ts').read_text()
    return {'time_istanbul':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),
        'processes':identities,'bridge_sha256':sha(ORIGINAL/'mt5_bridge.py'),
        'bridge_mtime_utc':datetime.fromtimestamp((ORIGINAL/'mt5_bridge.py').stat().st_mtime,ZoneInfo('UTC')).isoformat(),
        'proxy8008':"target: 'http://127.0.0.1:8008'" in code,'proxy_sha256':sha(ORIGINAL/'vite.config.ts'),
        'bridge_health':request(8005,'/api/health'),'v5_health':request(8008,'/api/v1/health'),
        'old_api_health':request(8006,'/api/v1/health'),
        'news_available':bool(request(8007,'/api/news') is not None),
        'backend_head':git(BACKEND,'rev-parse','HEAD'),'backend_clean':not git(BACKEND,'status','--porcelain')}

def recover():
    OUT.mkdir()
    if sha(ARCHIVE)!=ARCHIVE_SHA:raise ValueError('Original approved archive changed')
    with zipfile.ZipFile(ARCHIVE) as zipped:
        old=zipped.read('release/runtime8008-56cbd7e/backup/mt5_bridge.py')
    if hashlib.sha256(old).hexdigest()!=OLD:raise ValueError('Approved backing bytes mismatch')
    current=(ORIGINAL/'mt5_bridge.py').read_bytes()
    if hashlib.sha256(current).hexdigest()!=CURRENT:raise ValueError('New concurrent source change')
    (OUT/'approved-mt5_bridge.py').write_bytes(old);(OUT/'observed-mt5_bridge.py').write_bytes(current)
    save(OUT/'begin.json',observe());source_audit()
    print('PASS exact approved/current backing bytes and baseline observation recovered')

def live():
    """No chart/spec/risk-preview calls on bridge: conditional mutation is possible."""
    gate=module('runtime8008_preflight');checks=[];responses={}
    health=request(8005,'/api/health');assert health['connected'] is True
    checks.append('bridge_passive_health')
    schema=request(8005,'/openapi.json')
    assert set(schema['paths'])=={'/api/health','/api/candles','/api/symbol-spec','/api/risk-preview'}
    assert all(set(item)=={'get'} for item in schema['paths'].values())
    checks.append('bridge_observed_four_get_routes_no_order_routes')
    # Input rejection has no terminal calls in the audited old and new sources.
    for path in ('/api/candles?symbol=INVALID','/api/candles?timeframe=INVALID'):
        try:request(8005,path)
        except urllib.error.HTTPError as exc:assert exc.code==400
        else:raise ValueError('Expected safe input rejection')
        checks.append('bridge_invalid_input_400:'+path)
    direct=request(8008,'/openapi.json')
    gate.validate_route(direct,request(5173,'/engine/openapi.json'),request(8006,'/openapi.json'),
                        'http://127.0.0.1:8008')
    checks.append('actual_engine_proxy_matches8008_and_differs8006')
    for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY'):
        meta=request(8008,f'/api/v1/symbols/{symbol}/metadata')['data']
        assert meta['broker_symbol']==symbol+'c' and meta['broker_server']=='Exness-MT5Real50'
        assert meta['account_currency']=='USC' and meta['broker_contract']['status']=='CURRENT_MT5_OBSERVED'
        checks.append(symbol+':exact_metadata_USC')
        quote=request(8008,f'/api/v1/quotes/{symbol}')['data']
        assert quote['freshness']=='FRESH' and quote['ask']>quote['bid']>0
        age=datetime.now(ZoneInfo('UTC')).timestamp()-quote['time']
        assert -5<=age<=120
        checks.append(symbol+':fresh_quote')
        candles=request(8008,f'/api/v1/candles/{symbol}?timeframe=M5&count=5')['data']
        stamps=[row['time'] for row in candles]
        assert stamps==sorted(set(stamps)) and len(stamps)==5
        assert all(stamp+300<=datetime.now(ZoneInfo('UTC')).timestamp() for stamp in stamps)
        checks.append(symbol+':UTC_epoch_closed_candles')
        data=request(8008,'/api/v5/analysis',{'symbol':symbol,'timeframe':'M15',
            'confirmations':['H4'],'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1})
        gate.validate_analysis(symbol,data)
        checks.append(symbol+':REAL_readonly_null_plan_spread_historical_V2')
        responses[symbol]={'metadata':meta,'quote':quote,'candles':candles,'analysis':data,
                           'quote_age_seconds':age}
    save(OUT/'http-evidence.json',{'status':'PASS','checks':checks,'count':len(checks),
        'responses':responses,'time_istanbul':datetime.now(ZoneInfo('Europe/Istanbul')).isoformat(),
        'bridge_market_data_routes_live_tested':False,'added_15_symbols_live_tested':False,
        'bridge_limit':'Conditional MarketWatch/reconnect effects excluded from live tests; contracts fixture-tested',
        'bridge_loaded_version':'BRIDGE_LOADED_VERSION_UNVERIFIED',
        'v5_loaded_version':'UNVERIFIED_NO_SAME_PROCESS_STARTUP_ATTESTATION'})
    print('PASS localhost read-only checks',len(checks))

def backups():
    runtime=module('attested_runtime');base=ROOT/'release/attested-8008-56cbd7e'
    assert sha(ARCHIVE)==ARCHIVE_SHA
    with zipfile.ZipFile(ARCHIVE) as zipped:
        assert zipped.testzip() is None
        manifest=json.loads(zipped.read('release/attested-8008-56cbd7e/package-manifest.json'))
        assert all(hashlib.sha256(zipped.read(n)).hexdigest()==v for n,v in manifest['files'].items())
        # Verify the operational tooling/config files still match the sealed package.
        critical=[n for n in manifest['files'] if n.startswith('tools/') or n in
            ['release/attested-8008-56cbd7e/'+x for x in
             ('source.json','config.json','failback-config.json','launch-inputs.json',
              'reference-code-structure.json','protected-before.json','current-runtime-backup.json')]]
        assert all(sha(ROOT/n)==manifest['files'][n] for n in critical)
    c=json.loads((base/'launch-inputs.json').read_text())
    source=runtime.pinned_json(c['source_manifest'],c['source_sha256'])
    primary=runtime.verify_source(c['release'],source)
    fallback=runtime.verify_source(c['failback_release'],source)
    assert primary==fallback
    config=runtime.pinned_json(c['config'],c['config_sha256'])
    failback_config=runtime.pinned_json(c['failback_config'],c['failback_config_sha256'])
    runtime.validate_environment(config);runtime.validate_environment(failback_config)
    assert runtime.dependencies()==config['dependencies']==failback_config['dependencies']
    for path in (ROOT/'release/runtime8008-56cbd7e/backup/mt5_bridge.py',
                 ROOT/'release/reconciled-56cbd7e/preapproval-backup/mt5_bridge.py'):
        assert sha(path)==OLD
    save(OUT/'backup-audit.json',{'status':'PASS','old_archive_sha256':sha(ARCHIVE),
        'archive_crc_and_all_manifest_entries_verified':True,'critical_disk_files_match_sealed_package':True,
        'primary_source_inventory_sha256':primary,'failback_source_inventory_sha256':fallback,
        'source_build_sha':source['build_sha'],'pinned_config_and_dependencies_verified':True,
        'actual_old_bridge_bytes_from_three_independent_locations_match':True,
        'failback_scope':'Verified-source separate launch; NOT exact old RAM/process restoration',
        'new_live_processes_started':False,'global_packages_changed':False,
        'fixture_rehearsals':'28 startup/guard incl mock failback + 9 backup/restore guards'})
    print('PASS immutable old ZIP, source/failback inventories, pinned configuration/dependencies and backups')

def finish():
    before=json.loads((OUT/'begin.json').read_text());after=observe()
    protected=module('runtime8008_preflight').protected()
    protected_before=json.loads((OUT/'protected-audit-before.json').read_text())
    save(OUT/'protected-audit-after.json',protected)
    stable=all(before[k]==after[k] for k in ('processes','bridge_sha256','proxy_sha256','proxy8008','backend_head','backend_clean'))
    stable=stable and protected==protected_before and sha(ARCHIVE)==ARCHIVE_SHA
    stable=stable and after['backend_head']==SHA and after['backend_clean'] and after['proxy8008']
    save(OUT/'end.json',after)
    status='BLOCKED_CONCURRENT_CHANGE' if not stable else 'AUDIT_COMPLETE_NO_OPERATIONAL_REBASELINE'
    proposal={'status':'PROPOSED_NOT_APPROVED','operational_baseline_activated':False,
        'approval_received':False,'source_audit':'source-audit.json','processes':after['processes'],
        'bridge_sha256':after['bridge_sha256'],'backend_sha':SHA,
        'old_approved_archive_sha256':ARCHIVE_SHA,'runtime_version_confidence':'BRIDGE_LOADED_VERSION_UNVERIFIED',
        'pwa_apply_authorized':False,'requirements':['Operator acceptance of audited bridge delta and process change',
        'Explicit acceptance of bounded loaded-version confidence for independent chart bridge',
        'Fresh stable source/process/proxy preflight','New explicit 8008 runtime-only operation approval'],
        'scope':'Evidence proposal only; no replacement for active controller baseline or deployable release',
        'bridge_dependency_on_v5':'NONE_DIRECT_MT5_PROVIDER; shared-terminal interference remains possible',
        'audit_disposition':'BOUNDED_SOURCE_DELTA_ACCEPTABLE_FOR_INDEPENDENT_8008_REVIEW; added chart products not approved'}
    save(OUT/'proposed-baseline.json',proposal)
    save(OUT/'result.json',{'status':status,'stable':stable,'live_changes':False,'old_approval_reused':False})
    print(status)
    if not stable:raise ValueError(status)

def check():
    """Fresh read-only guard; never replaces a stored observation or approval."""
    frozen=json.loads((OUT/'end.json').read_text());current=observe()
    names=('processes','bridge_sha256','proxy_sha256','proxy8008','backend_head','backend_clean')
    if any(frozen[k]!=current[k] for k in names):raise ValueError('BLOCKED_CONCURRENT_CHANGE')
    protected=json.loads((OUT/'protected-audit-after.json').read_text())
    if protected!=module('runtime8008_preflight').protected():raise ValueError('BLOCKED_CONCURRENT_CHANGE')
    if sha(ARCHIVE)!=ARCHIVE_SHA:raise ValueError('BLOCKED_APPROVED_ARCHIVE_CHANGED')
    if current['bridge_health'].get('connected') is not True or current['v5_health'].get('data_status')!='OK':
        raise ValueError('BLOCKED_HEALTH')
    print('READONLY_PROPOSAL_GUARD_PASS; NOT_OPERATION_APPROVAL; BRIDGE_LOADED_VERSION_UNVERIFIED')

def seal():
    result=json.loads((OUT/'result.json').read_text())
    if not result['stable']:raise ValueError('Concurrent change prevents stable proposal package')
    files={}
    for path in OUT.rglob('*'):
        if path.is_file() and path.name!='source-manifest.json':files[path.relative_to(ROOT).as_posix()]=path
    for name in ('tools/bridge-drift-audit.py','tests/bridge_drift_test.py','docs/V3_MT5_BRIDGE_DRIFT_AUDIT_TR.md'):
        files[name]=ROOT/name
    for name in ('bridge-drift-tests.log','bridge-startup-guards.log','bridge-backup-fixtures.log'):
        files['evidence/'+name]=ROOT/'.artifacts'/name
    for name in ('release/attested-8008-56cbd7e/operator-approved-preflight-stop.json',):
        files[name]=ROOT/name
    manifest={'status':'REBASELINE_PROPOSAL_REQUIRES_APPROVAL','deployable':False,
              'old_approved_package_unchanged':sha(ARCHIVE)==ARCHIVE_SHA,
              'base_repository_head':git(ROOT,'rev-parse','HEAD'),
              'audit_changes_committed':False,'files':{name:sha(p) for name,p in files.items()}}
    save(OUT/'source-manifest.json',manifest);files['release/bridge-drift-audit-9124/source-manifest.json']=OUT/'source-manifest.json'
    archive=ROOT/'release/TRADE_AI_V3_BRIDGE9124_AUDIT_BASELINE_PROPOSAL.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as zipped:
        for name,path in files.items():zipped.write(path,name)
    with zipfile.ZipFile(archive) as zipped:
        assert not zipped.testzip()
        assert all(hashlib.sha256(zipped.read(n)).hexdigest()==value for n,value in manifest['files'].items())
    archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
    print('PASS proposal ZIP',sha(archive))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['recover','live','backups','finish','check','seal'])
    args=parser.parse_args();{'recover':recover,'live':live,'backups':backups,'finish':finish,'check':check,'seal':seal}[args.action]()
