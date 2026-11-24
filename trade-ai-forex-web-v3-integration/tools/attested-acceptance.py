"""Owned ephemeral-process rehearsal and separately gated live read-only check."""
import argparse
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'release/attested-8008-56cbd7e'

def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/(name.replace('_','-')+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def request(port,route,body=None):
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+route,
        data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=30) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)

def verify(c,port,startup,fallback=False):
    build=module('attested_release')
    subprocess.run([c['python'],'-B',c['launcher'],'verify',*build.arguments(c,fallback),
        '--reference',c['reference'],'--startup',str(startup),'--port',str(port)],
        cwd=ROOT,check=True,capture_output=True,text=True)

def checks(c,port,startup,fallback=False):
    verify(c,port,startup,fallback)
    results=['startup_same_process_source_reference']
    status,health=request(port,'/api/v1/health')
    assert status==200 and health['provider']=='mt5' and health['data_status']=='OK'
    results.append('health')
    status,schema=request(port,'/openapi.json')
    assert status==200 and 'historical_session_evidence' in schema['components']['schemas']['UnifiedAnalysis']['properties']
    assert not any('order' in name for name in schema['paths'])
    results += ['new_schema','no_order_routes']
    live=module('runtime8008_preflight');responses={}
    for symbol in ('XAUUSD','EURUSD','GBPUSD','USDJPY'):
        status,meta=request(port,f'/api/v1/symbols/{symbol}/metadata')
        assert status==200,('metadata HTTP',symbol,status,meta)
        assert (meta['data']['broker_symbol'],meta['data']['broker_server'],meta['data']['account_currency'])==(symbol+'c','Exness-MT5Real50','USC')
        results.append(symbol+'_identity')
        status,data=request(port,'/api/v5/analysis',{'symbol':symbol,'timeframe':'M15',
            'confirmations':['H4'],'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1})
        assert status==200;live.validate_analysis(symbol,data)
        assert data['spread_status']['policy_status']=='UNAPPROVED'
        results.append(symbol+'_readonly_spread_historical_null_plan')
        responses[symbol]=data
    verify(c,port,startup,fallback)
    results.append('post_http_source_memory_identity')
    return {'checks':results,'responses':responses,'startup':str(startup),'port':port}

def owned(c,fallback=False):
    build=module('attested_release');runtime=module('attested_runtime')
    with socket.socket() as reserved:reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
    assert port not in runtime.PROTECTED
    name='failback' if fallback else 'primary'
    startup=OUT/(name+'-startup-'+uuid.uuid4().hex+'.json')
    command=[c['python'],'-B',c['launcher'],'serve',*build.arguments(c,fallback),
             '--reference',c['reference'],'--startup',str(startup),'--port',str(port)]
    with (ROOT/'.artifacts'/('attested-'+name+'.log')).open('w',encoding='utf-8') as log:
        child=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=log,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            deadline=time.monotonic()+35
            while time.monotonic()<deadline:
                if child.poll() is not None:raise RuntimeError('Owned runtime exited; inspect private log')
                try:
                    if request(port,'/api/v1/health')[0]==200:break
                except OSError:pass
                time.sleep(.1)
            else:raise RuntimeError('Owned runtime startup timeout')
            record=json.loads(startup.read_text())
            assert record['process']['pid']==child.pid or record['parent_pid']==child.pid
            result=checks(c,port,startup,fallback)
            if not fallback:
                frozen_hash=runtime.file_hash(startup)
                path=Path(c['release'])/'forex/sessions.py';original=path.read_bytes()
                try:
                    path.write_bytes(original+b'\n# OWNED_DRIFT_REHEARSAL\n')
                    assert request(port,'/api/v1/health')[0]==503
                    try:verify(c,port,startup)
                    except subprocess.CalledProcessError:pass
                    else:raise AssertionError('Source drift was accepted')
                    assert runtime.file_hash(startup)==frozen_hash
                    result['checks'] += ['disk_drift_http503','operator_drift_rejection','startup_record_remains_frozen']
                finally:path.write_bytes(original)
                assert request(port,'/api/v1/health')[0]==200
                result['checks'].append('restored_owned_source_is_consistent')
            result['status']='PASS'
        finally:
            if child.poll() is None:
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                child.wait(timeout=10)
            with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0
    result['checks'].append('owned_process_listener_closed')
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accept-live-startup',type=Path)
    parser.add_argument('--operator-approved-live',action='store_true')
    args=parser.parse_args()
    c=json.loads((OUT/'launch-inputs.json').read_text())
    if args.accept_live_startup:
        if not args.operator_approved_live:parser.error('Separate live operation approval required')
        result=checks(c,8008,args.accept_live_startup)
        result.update(status='PASS',pwa_apply_authorized=False)
        path=OUT/('live-accepted-'+uuid.uuid4().hex+'.json')
        path.write_text(json.dumps(result,indent=2),encoding='utf-8');print('PASS',path);return
    primary=owned(c);fallback=owned(c,True)
    result={'status':'PASS','primary':primary,'failback':fallback,
            'live_changed':False,'pwa_apply_authorized':False}
    (OUT/'acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'status':'PASS','primary_checks':len(primary['checks']),
        'failback_checks':len(fallback['checks']),'live_changed':False}))

if __name__=='__main__':main()
