"""Explicit test-only ASGI wrapper. Never connects to a terminal or broker."""
import asyncio
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]


def main():
    if len(sys.argv) != 5 or sys.argv[1] != '--fixture-only':
        raise SystemExit('Disabled by default; invoke through run.py --run-fixture-acceptance')
    import numpy
    import uvicorn
    from forex.api import app
    from forex import broker_contract, spread_policy  # Include lazy trust modules in startup attestation.
    import forex.api as api
    from forex.providers import MT5Provider
    from forex.core import DataError
    from forex.unified import unified_analyze, public_code_digest
    from forex.v2_chart_bridge import V2ChartPatternBridge, SOURCE_SHA256, V2DescriptiveComposite
    from forex.v2_bridge import V2CandlestickBridge
    from test_forex import NOW, fixture
    from test_v2_chart_bridge import double_top, double_bottom
    from build_fingerprint import loaded_fingerprint
    assert numpy.__version__ == '2.2.6'
    port, manifest, source_root = int(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    chart = V2ChartPatternBridge(source_root)
    # Extract an independently pinned immutable blob into QA output, never write V2.
    candle_file = manifest.parent / 'engines' / 'candlestick.py'
    candle_file.parent.mkdir(exist_ok=True)
    if source_root.resolve() == ROOT.parent / 'trade-ai-v2-antigravity' and (source_root / 'SOURCE.md').is_file():
        candle_blob = (source_root / 'backend/market_ai/engines/candlestick.py').read_bytes()
    else:
        candle_blob = subprocess.check_output(['git', '-C', str(source_root), 'show',
            'c80c97f227a2c233a610df669919ba2f464e4f9f:backend/market_ai/engines/candlestick.py'])
    candle_sha256 = '45ee833fd3a5ffd178a4ee565e5914f79e9fb0b1c2aa62fe16b703057f63542c'
    assert hashlib.sha256(candle_blob).hexdigest() == candle_sha256
    candle_file.write_bytes(candle_blob)
    composite = V2DescriptiveComposite(V2CandlestickBridge(
        candle_file, hashlib.sha256(candle_blob).hexdigest()), chart)
    os.environ.update(MT5_ANALYSIS_POLICY='REAL_READONLY_DATA',
                      MT5_EXPECTED_REAL_SERVER='QA-NO-BROKER', MT5_EXPECTED_REAL_CURRENCY='USC')
    for key in ('V2_CANDLESTICK_FILE', 'V2_CANDLESTICK_SHA256', 'V2_CHART_GIT_ROOT'):
        os.environ.pop(key, None)

    class ReadOnlyFixture(MT5Provider):
        name = 'fixture-test-only'

        def __init__(self, data):
            self.data = data

        def account_preflight(self, policy, server, currency):
            expected_server=self.data['XAUUSD']['metadata'].get('broker_server','QA-NO-BROKER')
            assert (policy, server, currency) == ('REAL_READONLY_DATA', expected_server, 'USC')
            return {'status': 'PASS', 'balance': None, 'currency': 'USC'}

        def metadata(self, symbol):
            return copy.deepcopy({'symbol': symbol, 'source': self.name,
                                  'price_kind': 'bid', **self.data[symbol]['metadata']})

        def quote(self, symbol):
            return copy.deepcopy(self.data[symbol]['quote'])

        def candles(self, symbol, timeframe, count=220):
            return copy.deepcopy(self.data[symbol]['candles'][timeframe][-count:])

        def loss_for(self, symbol, side, lots, entry, stop):
            meta = self.metadata(symbol)
            return (stop-entry)*(1 if side == 'BUY' else -1)*lots*meta['tick_value']/meta['tick_size']

        def health(self):
            return {'connected': False, 'fixture': True}

    lock = asyncio.Lock()
    actual_unified = unified_analyze
    class FixtureClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.fromtimestamp(NOW, tz or timezone.utc)

    @app.middleware('http')
    async def fixture_context(request, call_next):
        async with lock:
            scenario = request.headers.get('x-qa-scenario', 'top')
            provider = double_bottom() if scenario == 'bottom' else double_top()
            if scenario in ('empty', 'sell'):
                provider = fixture()
            if scenario == 'sell':
                for tf in ('M15', 'H4'):
                    for i, bar in enumerate(provider.data['XAUUSD']['candles'][tf]):
                        close = 2100-i*.1-(5 if i == 219 else 0)
                        bar.update(open=close+.05, high=close+.2, low=close-.1, close=close)
                provider.data['XAUUSD']['quote'].update(bid=2073, ask=2073.2)
            data = provider.data['XAUUSD']
            data['metadata'].update(account_currency='USC', tick_value_currency='USC', broker_symbol='XAUUSDc')
            if scenario.startswith('broker_'):
                from test_broker_readiness import metadata
                data['metadata']=metadata(maximum=20,unit='POINTS') if scenario=='broker_points' else metadata()
                if scenario=='broker_unapproved':
                    data['metadata']['spread_policy'].update(approval_status='UNAPPROVED',maximum=None)
                elif scenario=='broker_spike':
                    data['metadata']['spread_policy']['maximum']=.19
                elif scenario=='broker_conflict':
                    from forex.broker_contract import contract_observation
                    data['metadata']['profit_currency']='EUR'
                    data['metadata']['broker_contract']=contract_observation(data['metadata'],'SYNTHETIC_ONLY')
            os.environ['MT5_EXPECTED_REAL_SERVER']=data['metadata'].get('broker_server','QA-NO-BROKER')
            if scenario == 'missing':
                data['candles']['M15'].pop(-3)
            if scenario == 'unknown_session':
                data['metadata']['broker_hours'] = None
            if scenario == 'close_only':
                data['metadata'].update(trade_allowed=False, allowed_directions=[], trade_mode=3)
            if scenario == 'opening_soon':
                now = datetime.fromtimestamp(NOW, timezone.utc)
                start = now.hour*60+now.minute+15
                data['metadata']['broker_hours'] = {'timezone': 'UTC', 'weekly':
                    {str(day): [[f'{start//60:02}:{start%60:02}', '24:00']] for day in range(7)}}
            if scenario == 'stale':
                data['quote']['time'] = NOW-500
            for symbol in ('EURUSD', 'GBPUSD', 'USDJPY'):
                provider.data[symbol] = copy.deepcopy(data)
                provider.data[symbol]['metadata']['broker_symbol'] = symbol+'c'
            app.state.provider = ReadOnlyFixture(provider.data)
            app.state.analytical_extension = (None if scenario == 'off' or
                request.headers.get('x-qa-patterns') == 'off' else composite)

            def evaluate(p, symbol, timeframe='M15', **kwargs):
                kwargs['now'] = NOW
                if scenario == 'wait':
                    # Controlled conflicting core fixture on the same captured data.
                    import forex.unified as unified
                    original = unified.analyze

                    def conflict(*args, **kw):
                        result = original(*args, **kw)
                        result['strategies'].append({'strategy': 'qa-conflict',
                                                     'direction': 'SELL', 'reason': 'fixture only'})
                        return result
                    with patch('forex.unified.analyze', side_effect=conflict):
                        return actual_unified(p, symbol, timeframe, **kwargs)
                return actual_unified(p, symbol, timeframe, **kwargs)

            def configured():
                if scenario == 'source_mismatch':
                    with patch('forex.v2_chart_bridge.SOURCE_SHA256', '0'*64):
                        return V2ChartPatternBridge(source_root)
                if scenario == 'source_missing':
                    return V2ChartPatternBridge(manifest.parent / 'missing-source')
                return None

            with patch.object(api, 'unified_analyze', side_effect=evaluate), \
                    patch.object(api, 'datetime', FixtureClock), \
                    patch('forex.v2_bridge.configured_v2_extension', side_effect=configured):
                if scenario in ('source_mismatch', 'source_missing'):
                    app.state.analytical_extension = None
                return await call_next(request)

    manifest.write_text(json.dumps({
        'mode': 'FIXTURE_ONLY_NO_TERMINAL', 'pid': os.getpid(), 'parent_pid': os.getppid(),
        'run_nonce': os.environ['V3_QA_RUN_NONCE'], 'port': port,
        'source_head': subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'startup_public_code_sha256': public_code_digest(), 'numpy': numpy.__version__,
        'chart_source_sha256': SOURCE_SHA256,
        'candlestick_source_sha256': candle_sha256,
        'loaded_code_fingerprint': loaded_fingerprint(),
        'loaded_modules': {name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                           for name, module in list(sys.modules.items())
                           if name.startswith('forex.') and getattr(module, '__file__', None)},
    }, indent=2), encoding='utf-8')
    uvicorn.run(app, host='127.0.0.1', port=port, log_level='error', access_log=False)


if __name__ == '__main__':
    main()
