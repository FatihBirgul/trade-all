"""Opt-in real loopback HTTP acceptance using SYNTHETIC_TEST_EVIDENCE only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
import threading
import time
import urllib.error
import urllib.request
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-historical-fixtures',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if not args.run_historical_fixtures:
        parser.error('disabled by default; explicit --run-historical-fixtures required')
    import uvicorn
    from forex.api import app
    from forex.unified import unified_analyze
    from historical_api_fixture import AS_OF, ENV, HistoricalApiProvider

    def analyze(*pos,**kw): return unified_analyze(*pos,**kw,now=AS_OF)
    checks, responses = [], {}
    listener=socket.socket()
    listener.bind(('127.0.0.1',0))
    port=listener.getsockname()[1]
    assert port not in (5173,8005,8006,8007)
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,lifespan='off'))
    thread=threading.Thread(target=lambda:server.run(sockets=[listener]),daemon=True)

    def request(body):
        req=urllib.request.Request(f'http://127.0.0.1:{port}/api/v5/analysis',
                                   data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=10) as response:
                return response.status,json.load(response)
        except urllib.error.HTTPError as error:
            return error.code,json.load(error)

    with TemporaryDirectory() as folder, patch.dict('os.environ',ENV), \
         patch('forex.api.unified_analyze',side_effect=analyze), \
         patch('forex.v2_bridge.configured_v2_extension',return_value=None), \
         patch.object(app.state,'analytical_extension',None), patch.object(app.state,'provider',None):
        try:
            thread.start()
            deadline=time.monotonic()+10
            while not server.started and thread.is_alive() and time.monotonic()<deadline:
                time.sleep(.02)
            assert server.started,'fixture listener failed to start'
            for scenario in ('none','weekly','wrong_symbol','wrong_broker','operator','unreviewed',
                             'partial','conflicting','valid','open_gap','spread_unapproved','bad_contract'):
                app.state.provider=HistoricalApiProvider(folder,scenario)
                status,body=request({'symbol':'XAUUSD','timeframe':'M15','confirmations':['M15']})
                assert status==200,(scenario,status)
                assert body['execution_permission'] is False
                assert body['entry_zone'] is None and body['lot_size'] is None
                if scenario=='valid':
                    assert body['data_status']=='OK' and body['final_decision']=='WAIT'
                else:
                    assert body['trading_eligibility']=='BLOCKED'
                if scenario=='spread_unapproved':
                    assert body['spread_status']['decision']=='BLOCK'
                    assert body['historical_session_evidence']['historical_gap_authorized'] is True
                if scenario=='bad_contract':
                    assert any('broker contract' in s for s in body['decision_reasons'])
                checks.append(scenario)
                responses[scenario]=body
            status,_=request({'symbol':'XAUUSD','reviews':[{'verified':True}]})
            assert status==422
            checks.append('malformed_evidence_422')
        finally:
            server.should_exit=True
            thread.join(timeout=10)
            listener.close()
        assert not thread.is_alive(),'fixture thread did not stop'
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1',port))!=0,'fixture listener remains open'
    checks.append('owned_listener_closed')
    result={'scope':'SYNTHETIC_TEST_EVIDENCE_NOT_REAL_BROKER','count':len(checks),
            'checks':checks,'port':port,'responses':responses,'listener_closed':True}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True),encoding='utf-8')
    print(f'PASS {len(checks)} historical HTTP acceptance checks; fixture port={port}, closed=True')


if __name__=='__main__': main()
