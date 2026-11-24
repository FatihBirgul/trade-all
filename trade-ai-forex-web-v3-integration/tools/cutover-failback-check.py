"""Rehearse baseline restore on an owned random port; protect existing services."""
import json
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.artifacts/cutover'

def request(base,path,body=None):
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=20) as response:return response.status,json.load(response)

def main():
    config=json.loads((ROOT/'release/cutover/failback-config.json').read_text(encoding='utf-8'))
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    assert port not in (5173,8005,8006,8007)
    manifest=OUT/('failback-manifest-'+uuid.uuid4().hex+'.json')
    checks=[];result={'checks':checks,'symbols':{},'python':config['python_executable'],'numpy':config['numpy_version']}
    with (OUT/'failback-rehearsal-final.log').open('w') as log:
        child=subprocess.Popen([config['python_executable'],'-B',str(ROOT/'tools/cutover-failback.py'),'--port',str(port),'--manifest',str(manifest)],cwd=ROOT,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            for _ in range(150):
                if child.poll() is not None:raise RuntimeError('Owned failback exited')
                try:
                    status,data=request(f'http://127.0.0.1:{port}','/api/v1/health')
                    if status==200:break
                except OSError:pass
                time.sleep(.2)
            else:raise RuntimeError('Failback startup timeout')
            checks.append({'name':'health','pass':status==200 and data.get('provider')=='mt5'})
            for symbol in ['XAUUSD','EURUSD','GBPUSD','USDJPY']:
                body={'symbol':symbol,'timeframe':'M15','confirmations':['H4'],'require_private':False,'hypothetical_capital':10000,'hypothetical_currency':'USC','risk_pct':1}
                responses={}
                for label,base in [('baseline','http://127.0.0.1:8006'),('failback',f'http://127.0.0.1:{port}')]:
                    status,data=request(base,'/api/v5/analysis',body)
                    responses[label]={'http_status':status,**{k:data.get(k) for k in ['final_decision','execution_permission','account_currency','risk_balance_source','market_data_account_mode','entry_zone','stop_loss','take_profit_1','take_profit_2','lot_size','spread_status','broker_contract','chart_patterns','candlestick_patterns','decision_reasons']}}
                    checks.append({'name':symbol+'_'+label+'_safe','pass':status==200 and data.get('execution_permission') is False and data.get('account_currency')=='USC' and data.get('risk_balance_source')=='HYPOTHETICAL_CAPITAL' and all(data.get(k) is None for k in ['entry_zone','stop_loss','lot_size'])})
                checks.append({'name':symbol+'_safe_decision_matches','pass':responses['baseline']['final_decision']==responses['failback']['final_decision']})
                result['symbols'][symbol]=responses
            result['status']='PASS' if all(c['pass'] for c in checks) else 'FAIL'
            (OUT/'failback-manifest.json').write_text(manifest.read_text(),encoding='utf-8')
        except Exception as exc:result.update(status='FAIL',error=str(exc))
        finally:
            if child.poll() is None:
                subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));child.wait(timeout=10)
            with socket.socket() as s:s.settimeout(1);closed=s.connect_ex(('127.0.0.1',port))!=0
            checks.append({'name':'own_failback_port_closed','pass':closed})
            if not closed:result['status']='FAIL'
            (OUT/'failback-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'checks':len(checks),'error':result.get('error'),'own_port_closed':closed}))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
