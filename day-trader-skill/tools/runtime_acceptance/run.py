"""Opt-in loopback acceptance; starts/stops only its own fixture subprocess."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-fixture-acceptance', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--broker-readiness', action='store_true', help='Add typed broker/spread fixture HTTP checks')
    parser.add_argument('--v2-root', type=Path, default=ROOT.parent/'trade-ai-v2-antigravity')
    args = parser.parse_args()
    if not args.run_fixture_acceptance or args.output is None:
        parser.error('disabled by default; explicit --run-fixture-acceptance and --output required')
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output/'fixture-manifest.json'
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        port = reserved.getsockname()[1]
    assert port not in (5173, 8005, 8006, 8007)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('MT5_', 'V2_'))}
    env['PYTHONPATH'] = str(ROOT)
    env['V3_QA_RUN_NONCE'] = uuid.uuid4().hex
    checks, responses, result = [], {}, None

    def request(path, body=None, scenario='top', patterns=True):
        req = urllib.request.Request(f'http://127.0.0.1:{port}'+path,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json', 'x-qa-scenario': scenario,
                                              'x-qa-patterns': 'on' if patterns else 'off'})
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    with (args.output/'fixture-server.log').open('w', encoding='utf-8') as log:
        child = subprocess.Popen([sys.executable, str(Path(__file__).with_name('fixture_server.py')),
                                  '--fixture-only', str(port), str(manifest), str(args.v2_root)],
                                 cwd=ROOT, env=env, stdout=log, stderr=log,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            for _ in range(100):
                if child.poll() is not None:
                    raise RuntimeError('Own fixture process exited; inspect fixture-server.log')
                try:
                    status, health = request('/api/v1/health')
                    break
                except (OSError, urllib.error.URLError):
                    time.sleep(.1)
            else:
                raise RuntimeError('Own fixture startup timeout')
            check('health_fixture_label', status == 200 and health['data_status'] == 'TEST_ONLY')
            status, symbols = request('/api/v1/symbols')
            check('four_symbols', status == 200 and set(symbols['symbols']) == {'XAUUSD','EURUSD','GBPUSD','USDJPY'})
            status, schema = request('/openapi.json')
            check('schema_backward_compatibility', status == 200 and '/api/v1/analysis/{symbol}' in schema['paths']
                  and '/api/v5/analysis' in schema['paths'])
            check('no_order_endpoints', not any('order' in path for path in schema['paths']))
            for symbol in symbols['symbols']:
                status, candles = request(f'/api/v1/candles/{symbol}?timeframe=M15&count=220')
                check('closed_candles_'+symbol, status == 200 and len(candles['data']) == 220)
            body = {'symbol': 'XAUUSD', 'timeframe': 'M15', 'confirmations': ['H4'],
                    'require_private': False, 'hypothetical_capital': 10000,
                    'hypothetical_currency': 'USC', 'risk_pct': 1}
            for scenario, expected in [('top','BUY_CANDIDATE'), ('bottom','BUY_CANDIDATE'),
                                       ('sell','SELL_CANDIDATE'), ('wait','WAIT'),
                                       ('missing','INSUFFICIENT_DATA'), ('unknown_session','NO_TRADE'),
                                       ('opening_soon','NO_TRADE'), ('close_only','MARKET_CLOSED'),
                                       ('stale','STALE_DATA'), ('empty','BUY_CANDIDATE'), ('off','BUY_CANDIDATE')]:
                status, response = request('/api/v5/analysis', body, scenario)
                responses[scenario] = response
                check(scenario+'_decision '+str((status, response.get('final_decision'), response.get('decision_reasons'))),
                      status == 200 and response['final_decision'] == expected)
                check(scenario+'_no_execution', response['execution_permission'] is False)
            for scenario, family in [('top','Double Top'), ('bottom','Double Bottom')]:
                chart = responses[scenario]['chart_patterns']
                check(scenario+'_serialized_pattern', chart['role'] == 'DESCRIPTIVE_ONLY' and
                      any(item['name'] == family and item['first_known_utc'] > item['formed_at_utc']
                          for item in chart['items']))
                check(scenario+'_candlestick_abi_context', responses[scenario]['candlestick_patterns']['role'] == 'DESCRIPTIVE_ONLY')
            check('empty_patterns', responses['empty']['chart_patterns']['items'] == [])
            from_fields = ('snapshot_id','final_decision','decision_reasons','trading_eligibility','data_status',
                           'entry_zone','stop_loss','take_profit_1','take_profit_2','spread','account_currency',
                           'lot_size','risk_amount','risk_reward','risk_policy','market_status','execution_permission')
            check('same_snapshot_pattern_on_off', all(responses['top'][k] == responses['off'][k] for k in from_fields))
            for scenario in ('top','bottom','sell','wait','missing','unknown_session',
                             'opening_soon','close_only','stale','empty'):
                status, without = request('/api/v5/analysis', body, scenario, patterns=False)
                check(scenario+'_same_snapshot_full_invariance', status == 200 and
                      all(responses[scenario][k] == without[k] for k in from_fields))
            check('opening_soon_status', responses['opening_soon']['market_status'] == 'OPENING_SOON')
            check('close_only_new_positions_disabled', responses['close_only']['market_status'] == 'DISABLED')
            check('usc_hypothetical_identity', responses['top']['account_currency'] == 'USC' and
                  responses['top']['risk_balance_source'] == 'HYPOTHETICAL_CAPITAL' and
                  responses['top']['trading_eligibility'] == 'NOT_EVALUATED')
            for scenario in ('source_mismatch', 'source_missing'):
                status, response = request('/api/v5/analysis', body, scenario)
                check(scenario+'_503', status == 503 and response['detail']['status'] == 'DATA_UNAVAILABLE')
            small = {**body, 'hypothetical_capital': .01}
            status, response = request('/api/v5/analysis', small)
            check('minimum_lot_refusal', status == 200 and response['final_decision'] == 'NO_TRADE' and response['lot_size'] is None)
            legacy = {'symbol':'XAUUSD', 'balance':10000}
            status, response = request('/api/v5/analysis', legacy)
            check('legacy_balance_ignored_real_policy', status == 200 and response['risk_balance_source'] == 'NOT_PROVIDED' and response['lot_size'] is None)
            status, risk = request('/api/v1/risk/calculate', {'symbol':'XAUUSD','direction':'BUY',
                                  'balance':10000,'risk_pct':1,'entry':2000,'stop_loss':1999,'account_currency':'USC'})
            check('risk_endpoint_usc', status == 200 and risk['currency'] == 'USC')
            if args.broker_readiness:
                for scenario,decision,spread_decision in (
                        ('broker_approved','BUY_CANDIDATE','PASS'),
                        ('broker_points','BUY_CANDIDATE','PASS'),
                        ('broker_unapproved','NO_TRADE','BLOCK'),
                        ('broker_spike','NO_TRADE','BLOCK'),
                        ('broker_conflict','INSUFFICIENT_DATA','PASS')):
                    status,response=request('/api/v5/analysis',body,scenario)
                    responses[scenario]=response
                    check(scenario+'_typed_api',status==200 and response['final_decision']==decision and
                          response['spread_status']['decision']==spread_decision and not response['execution_permission'])
                risk_body={'symbol':'XAUUSD','direction':'BUY','balance':10000,'risk_pct':1,
                           'entry':2000,'stop_loss':1999,'account_currency':'USC','timeframe':'M15'}
                for scenario,expected_status in (('broker_approved',200),('broker_unapproved',503)):
                    status,response=request('/api/v1/risk/calculate',risk_body,scenario)
                    check(scenario+'_risk_route',status==expected_status)
            runtime = json.loads(manifest.read_text(encoding='utf-8'))
            check('own_process_identity', child.pid in (runtime['pid'], runtime['parent_pid']) and
                  runtime['run_nonce'] == env['V3_QA_RUN_NONCE'] and
                  runtime['mode'] == 'FIXTURE_ONLY_NO_TERMINAL')
            result = {'checks': checks, 'count': len(checks), 'runtime': runtime, 'responses': responses,
                      'scope':'REAL_HTTP_FIXTURE_ONLY_NOT_LIVE_BROKER'}
            (args.output/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(f'PASS {len(checks)} HTTP acceptance checks; fixture PID={child.pid}, port={port}')
        finally:
            # Popen handle belongs exclusively to this invocation; never enumerate/kill by port.
            if child.poll() is None:
                if os.name == 'nt':
                    # Windows venv uses a launcher parent; stop its owned tree, too.
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                else:
                    child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
            print(f'Own fixture process stopped: PID={child.pid}, exit={child.returncode}')
    with socket.socket() as probe:
        probe.settimeout(1)
        check('own_fixture_port_closed', probe.connect_ex(('127.0.0.1', port)) != 0)
    result.update(checks=checks, count=len(checks), own_process_stopped=True)
    (args.output/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'PASS {len(checks)} total checks including owned-process cleanup')


if __name__ == '__main__':
    main()
