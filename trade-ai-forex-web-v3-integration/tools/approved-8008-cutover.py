"""8008-only operation bound to the user's newly accepted bridge proposal.

Does not modify either sealed package, any original source, or other services.
prepare rehearses isolated runtimes; apply requires explicit operation flags.
"""
import argparse
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time
import urllib.error
import uuid
import zipfile
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
PROPOSAL_SHA='25de726317a2a04a60a37594d3d2fc6e32082d1bd76cce07e1c596cfe64409db'
RUNTIME_SHA='a7e21cfca44c0963b689ff88f6d7e3f85f8a39c8a5a3b47e2dbeeaece6f66ef9'
BUILD='56cbd7e05a40b106deda9298e2be28b488d0d952'
PROPOSAL=ROOT/'release/TRADE_AI_V3_BRIDGE9124_AUDIT_BASELINE_PROPOSAL.zip'
RUNTIME_ZIP=ROOT/'release/TRADE_AI_V3_ATTESTED_8008_56cbd7e_READY.zip'
BASE='release/bridge-drift-audit-9124/'

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name.replace('_','-')+'.py'))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,data):Path(path).write_text(json.dumps(data,indent=2,sort_keys=True),encoding='utf-8')
def now():return datetime.now(ZoneInfo('Europe/Istanbul')).isoformat()

def archive(path,expected,manifest_name):
    if sha(path)!=expected:raise ValueError('BLOCKED_ARCHIVE_HASH:'+path.name)
    with zipfile.ZipFile(path) as zipped:
        if zipped.testzip():raise ValueError('BLOCKED_ZIP_CRC')
        manifest=json.loads(zipped.read(manifest_name))
        for name,digest in manifest['files'].items():
            if hashlib.sha256(zipped.read(name)).hexdigest()!=digest:
                raise ValueError('BLOCKED_ZIP_ENTRY:'+name)
        return manifest

def proposal():
    manifest=archive(PROPOSAL,PROPOSAL_SHA,BASE+'source-manifest.json')
    for name,digest in manifest['files'].items():
        if not name.startswith('evidence/') and sha(ROOT/name)!=digest:
            raise ValueError('BLOCKED_PROPOSAL_DISK_DRIFT:'+name)
    with zipfile.ZipFile(PROPOSAL) as zipped:
        return (json.loads(zipped.read(BASE+'end.json')),
                json.loads(zipped.read(BASE+'protected-audit-after.json')),
                {name:json.loads(zipped.read(BASE+name+'-process-parameters.json'))
                 for name in ('bridge','v5')})

def require_processes(expected,actual,include8008=True):
    ports=('5173','8005','8006','8007','8008') if include8008 else ('5173','8005','8006','8007')
    if any(expected[p]!=actual[p] for p in ports):raise ValueError('BLOCKED_CONCURRENT_PROCESS_CHANGE')

def require_protected(expected,actual):
    if expected!=actual:raise ValueError('BLOCKED_CONCURRENT_SOURCE_CHANGE')

def identities():
    runtime=module('attested_runtime')
    return {str(port):runtime.process_identity(runtime.port_owner(port)) for port in (5173,8005,8006,8007,8008)}

def launch_inputs(c):
    runtime=module('attested_runtime')
    source=runtime.pinned_json(c['source_manifest'],c['source_sha256'])
    if source['build_sha']!=BUILD:raise ValueError('BLOCKED_BUILD')
    for key in ('release','failback_release'):runtime.verify_source(c[key],source)
    deps=runtime.dependencies()
    for key,hashkey in (('config','config_sha256'),('failback_config','failback_config_sha256')):
        config=runtime.pinned_json(c[key],c[hashkey]);runtime.validate_environment(config)
        if config['dependencies']!=deps:raise ValueError('BLOCKED_DEPENDENCIES')
    archive(RUNTIME_ZIP,RUNTIME_SHA,'release/attested-8008-56cbd7e/package-manifest.json')
    # Existing sealed controller verifies original operational tool/config pins.
    with zipfile.ZipFile(RUNTIME_ZIP) as zipped:
        manifest=json.loads(zipped.read('release/attested-8008-56cbd7e/package-manifest.json'))
    for name,digest in manifest['files'].items():
        if name.startswith('tools/') or name in ('release/attested-8008-56cbd7e/'+x for x in
            ('source.json','config.json','failback-config.json','launch-inputs.json',
             'reference-code-structure.json','current-runtime-backup.json','protected-before.json')):
            if sha(ROOT/name)!=digest:raise ValueError('BLOCKED_OPERATIONAL_FILE_DRIFT:'+name)
    return deps

def direct_provider():
    gate=module('runtime8008_preflight')
    candidate=(Path.home() / 'trade-ai-v3-runtime-candidate')
    for root in (gate.BACKEND,candidate):
        if gate.git(root,'rev-parse','HEAD')!=BUILD or gate.git(root,'status','--porcelain'):
            raise ValueError('BLOCKED_BACKEND_HEAD_OR_DIRTY')
    deployed=ROOT/'release/attested-8008-56cbd7e/backend/forex/providers.py'
    paths=[gate.BACKEND/'forex/providers.py',candidate/'forex/providers.py',deployed]
    if len({sha(p) for p in paths})!=1:raise ValueError('BLOCKED_PROVIDER_SOURCE_MISMATCH')
    code=deployed.read_text(encoding='utf-8')
    if 'import MetaTrader5 as mt5' not in code or '8005' in code or 'mt5_bridge' in code:
        raise ValueError('BLOCKED_UNEXPECTED_BRIDGE_DEPENDENCY')
    return {'provider_sha256':sha(deployed),'source_build':BUILD,
            'dependency':'DIRECT_MetaTrader5_NOT_HTTP8005','exact_old_loaded_version':'UNVERIFIED'}

def side_health():
    req=module('bridge_drift_audit').request
    if req(8005,'/api/health').get('connected') is not True:raise ValueError('BLOCKED_BRIDGE_HEALTH')
    if req(8006,'/api/v1/health').get('data_status')!='OK':raise ValueError('BLOCKED_8006_HEALTH')
    req(8007,'/api/news')

def preflight():
    frozen,protected,params=proposal()
    gate=module('runtime8008_preflight');runtime=module('attested_runtime')
    observed=identities();require_processes(frozen['processes'],observed)
    require_protected(protected,gate.protected())
    inspector=module('cutover_process_inspect');actual_params={}
    for name,port in (('bridge','8005'),('v5','8008')):
        actual_params[name]=inspector.inspect(observed[port]['pid'])
        if actual_params[name]!=params[name]:raise ValueError('BLOCKED_PROCESS_CONFIG_DRIFT:'+port)
    controller=module('attested_cutover');c,old=controller.preflight(RUNTIME_SHA)
    deps=launch_inputs(c);provider=direct_provider();side_health()
    req=module('bridge_drift_audit').request
    gate.validate_route(req(8008,'/openapi.json'),req(5173,'/engine/openapi.json'),
                        req(8006,'/openapi.json'),'http://127.0.0.1:8008')
    # Safe analytic POST rechecks actual account guard and all no-plan gates before stop.
    for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY'):
        data=req(8008,'/api/v5/analysis',{'symbol':symbol,'timeframe':'M15','confirmations':['H4'],
            'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1})
        gate.validate_analysis(symbol,data)
    return c,{'time_istanbul':now(),'processes':observed,'process_parameters':actual_params,
              'backend_sha':BUILD,'provider':provider,'dependencies':deps,
              'proposal_sha256':PROPOSAL_SHA,'runtime_zip_sha256':RUNTIME_SHA,
              'protected_inventory_sha256':runtime.digest(runtime.canonical(protected)),
              'old_8008':old,'all_four_analysis_safety':'PASS','status':'PREFLIGHT_PASS'}

def extra_acceptance(c,child,startup,fallback=False):
    controller=module('attested_cutover');acceptance=module('attested_acceptance')
    runtime=module('attested_runtime');gate=module('runtime8008_preflight')
    result=controller.await_acceptance(c,child,startup,fallback)
    frozen,protected,_=proposal()
    require_processes(frozen['processes'],identities(),False)
    require_protected(protected,gate.protected());side_health()
    req=module('bridge_drift_audit').request
    gate.validate_route(req(8008,'/openapi.json'),req(5173,'/engine/openapi.json'),
                        req(8006,'/openapi.json'),'http://127.0.0.1:8008')
    result['checks'].append('actual_engine_proxy_matches_attested8008')
    extra={}
    for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY'):
        quote=req(8008,f'/api/v1/quotes/{symbol}')['data']
        age=datetime.now(ZoneInfo('UTC')).timestamp()-quote['time']
        if not (-5<=age<=120 and quote['freshness']=='FRESH' and quote['ask']>quote['bid']>0):
            raise ValueError('BLOCKED_QUOTE:'+symbol)
        bars=req(8008,f'/api/v1/candles/{symbol}?timeframe=M5&count=5')['data']
        stamps=[b['time'] for b in bars]
        if len(stamps)!=5 or stamps!=sorted(set(stamps)) or not all(
            t+300<=datetime.now(ZoneInfo('UTC')).timestamp() for t in stamps):
            raise ValueError('BLOCKED_CLOSED_CANDLES:'+symbol)
        extra[symbol]={'quote_age_seconds':age,'closed_candle_timestamps':stamps}
        result['checks'] += [symbol+'_fresh_quote',symbol+'_closed_candles']
    # Real end-to-end proxy POST, bounded to the original four-symbol request contract.
    proxy_data=req(5173,'/engine/api/v5/analysis',{'symbol':'XAUUSD','timeframe':'M15','confirmations':['H4'],
        'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1})
    gate.validate_analysis('XAUUSD',proxy_data)
    if proxy_data['spread_status']['policy_status']!='UNAPPROVED':raise ValueError('BLOCKED_SPREAD_POLICY')
    result['checks'].append('actual_engine_proxy_analysis_readonly_gates')
    try:req(8008,'/api/v1/symbols/AUDUSD/metadata')
    except urllib.error.HTTPError as exc:
        if exc.code!=422:raise
    else:raise ValueError('BLOCKED_EXPANDED_SYMBOL_SCOPE')
    result['checks'].append('new_symbols_remain_outside_v5_contract')
    acceptance.verify(c,8008,startup,fallback)
    record=json.loads(startup.read_text())
    if runtime.process_identity(runtime.port_owner(8008))!=record['process']:
        raise ValueError('BLOCKED_NEW_PROCESS_IDENTITY')
    result.update(extra=extra,startup_record=record,time_istanbul=now(),
                  preserved_services='PASS',source_files_unchanged=True,
                  loaded_identity='PASS_LOCAL_FROZEN_STARTUP_PROVENANCE')
    return result

def prepare():
    c,before=preflight()
    operation=ROOT/'release'/('approved-8008-'+uuid.uuid4().hex);operation.mkdir()
    save(operation/'authorization.json',{'scope':'8008_RUNTIME_ONLY','new_operator_approval_received':True,
        'proposal_sha256':PROPOSAL_SHA,'runtime_zip_sha256':RUNTIME_SHA,'pwa_apply_authorized':False,
        'bridge_acceptance':'Existing PID9124/source delta only; no new symbols or loaded-code trust claim',
        'time_istanbul':now(),'operation_tool_sha256':sha(__file__)})
    save(operation/'preflight-before.json',before)
    acceptance=module('attested_acceptance')
    primary=acceptance.owned(c);fallback=acceptance.owned(c,True)
    save(operation/'rehearsal.json',{'primary':primary,'failback':fallback,'live_8008_changed':False})
    _,after=preflight();save(operation/'preflight-after-rehearsal.json',after)
    print('PREPARED',operation,flush=True)

def apply(operation,approved,expected):
    if not approved or expected!=PROPOSAL_SHA:raise ValueError('NEW_EXPLICIT_APPROVAL_REQUIRED')
    operation=operation.resolve()
    if operation.parent!=ROOT/'release' or not operation.name.startswith('approved-8008-'):
        raise ValueError('Unexpected operation directory')
    authorization=json.loads((operation/'authorization.json').read_text())
    if authorization['operation_tool_sha256']!=sha(__file__):raise ValueError('OPERATION_TOOL_CHANGED')
    rehearsal=json.loads((operation/'rehearsal.json').read_text())
    if rehearsal['primary']['status']!='PASS' or rehearsal['failback']['status']!='PASS':
        raise ValueError('REHEARSAL_NOT_PASSED')
    c,before=preflight();save(operation/'preflight-immediately-before-stop.json',before)
    controller=module('attested_cutover');runtime=module('attested_runtime')
    old=before['old_8008'];result={'old_8008':old,'new_operator_approval_received':True,
        'pwa_apply_authorized':False,'proposal_sha256':PROPOSAL_SHA,'runtime_zip_sha256':RUNTIME_SHA,
        'time_istanbul':now(),'status':'STOP_INTENT_RECORDED','live_stop_started':False}
    save(operation/'result.json',result)
    frozen,protected,_=proposal()
    require_processes(frozen['processes'],identities())
    require_protected(protected,module('runtime8008_preflight').protected())
    # Final ownership check immediately adjacent to the only existing-process stop.
    if runtime.port_owner(8008)!=old['pid'] or runtime.process_identity(old['pid'])!=old:
        raise ValueError('BLOCKED_LAST_MOMENT_8008_CHANGE')
    primary=startup=fallback=fallback_startup=None
    try:
        result['live_stop_started']=True;save(operation/'result.json',result)
        subprocess.run(['taskkill','/PID',str(old['pid']),'/T','/F'],check=True,
            capture_output=True,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if controller.port_free():break
            time.sleep(.1)
        else:raise ValueError('BLOCKED_UNEXPECTED_8008_OWNER')
        launch_inputs(c)
        primary,startup=controller.launch(c)
        accepted=extra_acceptance(c,primary,startup)
        result.update(status='PRIMARY_ACCEPTED',acceptance=accepted,failback='NOT_NEEDED')
    except Exception as exc:
        result['primary_error']=str(exc);save(operation/'result.json',result)
        try:
            if primary is not None:controller.stop_owned(primary,startup)
            # A foreign listener is never killed to make space for failback.
            if not controller.port_free():raise ValueError('UNEXPECTED_8008_OWNER_FAILBACK_UNSAFE')
            launch_inputs(c)
            fallback,fallback_startup=controller.launch(c,True)
            accepted=extra_acceptance(c,fallback,fallback_startup,True)
            result.update(status='FAILBACK_ACCEPTED',acceptance=accepted,failback='APPLIED_VERIFIED_SOURCE')
        except Exception as fallback_error:
            if fallback is not None:controller.stop_owned(fallback,fallback_startup)
            result.update(status='BLOCKED_FAILBACK_UNSAFE_OR_FAILED',failback_error=str(fallback_error))
    finally:
        result['finished_istanbul']=now()
        save(operation/'result.json',result)
    print(result['status'],operation/'result.json',flush=True)
    if result['status'] not in ('PRIMARY_ACCEPTED','FAILBACK_ACCEPTED'):raise RuntimeError(result['status'])

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','prepare','apply'])
    parser.add_argument('--operation',type=Path)
    parser.add_argument('--operator-approved',action='store_true')
    parser.add_argument('--proposal-sha256')
    args=parser.parse_args()
    if args.action=='preflight':print(json.dumps(preflight()[1],indent=2))
    elif args.action=='prepare':prepare()
    else:apply(args.operation,args.operator_approved,args.proposal_sha256)
