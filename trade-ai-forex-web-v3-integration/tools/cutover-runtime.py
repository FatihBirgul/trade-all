"""Private read-only production launcher. No fixture provider and no trading calls."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

READ_CALLS = {'initialize', 'shutdown', 'last_error', 'terminal_info', 'account_info',
              'symbol_info', 'symbol_info_tick', 'symbol_select', 'copy_rates_from_pos',
              'order_calc_profit'}

class ReadOnlyTerminal:
    def __init__(self, module): self.module = module
    def __getattr__(self, name):
        if name in READ_CALLS or name.startswith(('ACCOUNT_TRADE_MODE_', 'TIMEFRAME_', 'ORDER_TYPE_', 'SYMBOL_CALC_MODE_')):
            return getattr(self.module, name)
        raise AttributeError('Terminal operation is not allowlisted')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--release', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--config-sha256', required=True)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--operator-approved-live', action='store_true')
    args = parser.parse_args()
    if args.port in (5173, 8005, 8007) or (args.port == 8006 and not args.operator_approved_live):
        parser.error('Protected port requires explicit separate live operation approval')
    config_bytes = args.config.read_bytes()
    if hashlib.sha256(config_bytes).hexdigest() != args.config_sha256:
        raise ValueError('Exact approved runtime configuration required')
    config = json.loads(config_bytes)
    for key in list(os.environ):
        if key.startswith(('MT5_', 'V2_')): del os.environ[key]
    for key, value in config['environment'].items():
        if not key.startswith(('MT5_', 'V2_')): raise ValueError('Unexpected runtime config key')
        os.environ[key] = value
    if os.environ['MT5_ANALYSIS_POLICY'] != 'REAL_READONLY_DATA': raise ValueError('Read-only policy required')
    sys.path.insert(0, str(args.release))
    import numpy
    import MetaTrader5 as mt5
    if numpy.__version__ != '2.2.6': raise ValueError('Pinned NumPy required')
    import forex.api
    import forex.broker_contract
    import forex.spread_policy
    import forex.historical_sessions
    if forex.historical_sessions.PRODUCTION_REVIEWS:
        raise ValueError('This release requires an empty historical approval registry')
    from forex.providers import MT5Provider
    from forex.v2_bridge import configured_v2_extension
    from tools.runtime_acceptance.build_fingerprint import loaded_fingerprint
    runtime_files = {str(p.relative_to(args.release)).replace('\\','/'): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted((args.release/'forex').glob('*.py'))}
    if runtime_files != config['forex_sha256']: raise ValueError('Release source drift')
    provider = MT5Provider(mt5=ReadOnlyTerminal(mt5))
    if provider.historical_evidence.candidates:
        raise ValueError('This release requires no production historical evidence inputs')
    gate = provider.account_preflight('REAL_READONLY_DATA', 'Exness-MT5Real50', 'USC')
    if gate['status'] != 'PASS' or gate['balance'] is not None: raise ValueError('Account gate failed')
    forex.api.app.state.provider = provider
    forex.api.app.state.analytical_extension = configured_v2_extension()
    manifest = {'source_head': config['source_head'], 'source_sha256': hashlib.sha256(json.dumps(runtime_files,sort_keys=True).encode()).hexdigest(),
                'started_at_utc': datetime.now(timezone.utc).isoformat(), 'python_executable': sys.executable,
                'config_sha256': args.config_sha256, 'launcher_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'pid': os.getpid(), 'parent_pid': os.getppid(), 'python': sys.version.split()[0],
                'numpy': numpy.__version__, 'mt5_version': importlib.metadata.version('MetaTrader5'),
                'port': args.port, 'policy': 'REAL_READONLY_DATA', 'server': 'Exness-MT5Real50',
                'currency': 'USC', 'real_balance_used': False, 'execution_permission': False,
                'mode': 'PRODUCTION_READONLY_NOT_FIXTURE', 'loaded': loaded_fingerprint(),
                'candlestick_sha256': os.environ['V2_CANDLESTICK_SHA256'],
                'spread_policy_sha256': hashlib.sha256(Path(os.environ['MT5_SPREAD_POLICY_FILE']).read_bytes()).hexdigest()}
    with args.manifest.open('x',encoding='utf-8') as output:
        json.dump(manifest,output,indent=2)
    import uvicorn
    # No reload, no credentials, no account number in logs or manifests.
    uvicorn.run(forex.api.app, host='127.0.0.1', port=args.port, access_log=False, log_level='warning')

if __name__ == '__main__': main()
