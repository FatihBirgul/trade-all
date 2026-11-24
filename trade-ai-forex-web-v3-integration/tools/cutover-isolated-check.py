"""Finite read-only acceptance against an owned production candidate, never port 8006."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
import hashlib
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'.artifacts/cutover'

def request(base, path, body=None):
    req = urllib.request.Request(base+path, data=json.dumps(body).encode() if body else None,
                                 headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        return exc.code, json.load(exc)

def main():
    import MetaTrader5 as mt5
    if not mt5.initialize(): raise RuntimeError('Existing terminal read-only IPC unavailable')
    account=mt5.account_info()
    if account is None: raise RuntimeError('Read-only account unavailable')
    # The login is compared only in RAM and is never written or printed.
    account_before=(account.login,account.server,account.currency,account.trade_mode)
    if account.server!='Exness-MT5Real50' or account.currency!='USC' or account.trade_mode!=mt5.ACCOUNT_TRADE_MODE_REAL:
        raise RuntimeError('Expected REAL server/currency unavailable')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
    assert port not in (5173,8005,8006,8007)
    manifest = OUT/('candidate-manifest-'+uuid.uuid4().hex+'.json')
    command = [sys.executable, '-B', str(ROOT/'tools/cutover-runtime.py'),
               '--release', str(ROOT/'release/reconciled-56cbd7e/backend-56cbd7e'),
               '--config', str(ROOT/'release/reconciled-56cbd7e/runtime-config.json'),
               '--config-sha256', hashlib.sha256((ROOT/'release/reconciled-56cbd7e/runtime-config.json').read_bytes()).hexdigest(),
               '--manifest', str(manifest), '--port', str(port)]
    checks = []
    result = {'mode':'OWNED_PRODUCTION_READONLY_CANDIDATE', 'live_changed':False, 'port':port, 'symbols':{}}
    def check(name, condition):
        checks.append({'name':name,'pass':bool(condition)})
        if not condition: raise AssertionError(name)
    with (OUT/'candidate.log').open('w', encoding='utf-8') as log:
        child = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log,
                                 creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(150):
                if child.poll() is not None: raise RuntimeError('Owned candidate exited; inspect local log')
                try:
                    status, health = request(f'http://127.0.0.1:{port}', '/api/v1/health')
                    if status == 200: break
                except OSError: pass
                time.sleep(.2)
            else: raise RuntimeError('Owned candidate startup timeout')
            check('production_health',status==200 and health['provider']=='mt5' and health['data_status']=='OK')
            check('existing_real_account_identity',True)
            base = f'http://127.0.0.1:{port}'
            status,schema = request(base,'/openapi.json')
            check('new_schema',status==200 and 'broker_contract' in json.dumps(schema) and 'spread_status' in json.dumps(schema))
            check('no_order_routes',not any('order' in p for p in schema['paths']))
            for symbol in ['XAUUSD','EURUSD','GBPUSD','USDJPY']:
                status,meta = request(base,f'/api/v1/symbols/{symbol}/metadata')
                check(symbol+'_metadata',status==200)
                data = meta['data']
                status,bridge = request('http://127.0.0.1:8005',f'/api/symbol-spec?symbol={symbol}')
                check(symbol+'_bridge_spec',status==200 and all(data[k]==bridge[k] for k in ('digits','point','tick_size','contract_size','volume_min','volume_max','volume_step','account_currency')))
                check(symbol+'_identity',data['broker_symbol']==symbol+'c' and data['account_currency']=='USC' and data['broker_server']=='Exness-MT5Real50')
                status,analysis = request(base,'/api/v5/analysis',{'symbol':symbol,'timeframe':'M15','confirmations':['H4'], 'require_private':False,'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1})
                check(symbol+'_manual_response',status==200)
                check(symbol+'_execution_false',analysis.get('execution_permission') is False)
                check(symbol+'_historical_missing_block',analysis.get('historical_session_evidence',{}).get('status')=='SOURCE_NOT_SUPPLIED' and analysis.get('historical_session_evidence',{}).get('historical_gap_authorized') is False)
                check(symbol+'_real_hypothetical_usc',analysis.get('market_data_account_mode')=='REAL' and analysis.get('account_currency')=='USC' and analysis.get('risk_balance_source')=='HYPOTHETICAL_CAPITAL')
                check(symbol+'_broker_spread_fields',isinstance(analysis.get('broker_contract'),dict) and isinstance(analysis.get('spread_status'),dict))
                spread=analysis['spread_status']
                check(symbol+'_unapproved_block',spread.get('policy_status')=='UNAPPROVED' and spread.get('decision')=='BLOCK' and spread.get('max_allowed_price') is None)
                check(symbol+'_no_plan',all(analysis.get(k) is None for k in ['entry_zone','stop_loss','take_profit_1','take_profit_2','lot_size']))
                result['symbols'][symbol]={k:analysis.get(k) for k in ['broker_symbol','final_decision','market_data_account_mode','account_currency','execution_permission','risk_balance_source','market_status','data_status','entry_zone','stop_loss','take_profit_1','take_profit_2','lot_size','spread_status','broker_contract','chart_patterns','candlestick_patterns','decision_reasons']}
            startup=json.loads(manifest.read_text(encoding='utf-8'))
            (OUT/'candidate-manifest.json').write_text(json.dumps(startup,indent=2),encoding='utf-8')
            check('loaded_startup_identity',startup['mode']=='PRODUCTION_READONLY_NOT_FIXTURE' and startup['source_head']=='56cbd7e05a40b106deda9298e2be28b488d0d952' and startup['numpy']=='2.2.6' and startup['loaded']['function_count']>0)
            after=mt5.account_info()
            check('same_account_before_after_ram_only',after is not None and account_before==(after.login,after.server,after.currency,after.trade_mode))
            result['status']='PASS'
        except Exception as exc:
            result['status']='FAIL'; result['error']=str(exc)
        finally:
            if child.poll() is None:
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                child.wait(timeout=10)
            with socket.socket() as sock:
                sock.settimeout(1); closed=sock.connect_ex(('127.0.0.1',port))!=0
            checks.append({'name':'own_candidate_port_closed','pass':closed})
            result['checks']=checks;result['count']=len(checks)
            if not closed:result['status']='FAIL'
            (OUT/'candidate-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            mt5.shutdown()  # Detach this process's IPC; never logs out the terminal account.
    print(json.dumps({'status':result['status'],'checks':len(checks),'error':result.get('error'),'own_port_closed':closed}))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
