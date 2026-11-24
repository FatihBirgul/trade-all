"""Reproducible synthetic profiling; median timings separate from allocation run."""
from pathlib import Path
import json,sys,time,platform,tracemalloc,statistics
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from fixtures import fixture,multi_fixture,NOW
from unified_forex import __version__
from unified_forex.engine import AnalysisEngine,code_digest
from unified_forex.services import scan
from unified_forex.market import acquire
from unified_forex.confluence import Observation,combine
from unified_forex.research import dataset_from_provider,ResearchConfig,run_backtest,run_oos
from unified_forex.chart_geometry import detect as charts
from unified_forex.candle_extensions import detect as candles
from market_ai.v2.pattern_research import detect_patterns
from market_ai.v2.walk_forward import WalkForwardConfig,Candidate
from unified_forex.strategies import TREND
from forex.research import _bootstrap
from fastapi.testclient import TestClient
from unified_forex.api import app

output_name='V'+__version__.split('.')[0]+'_BENCHMARK_RESULTS.json'
result={'engine_version':__version__,'code_sha256':code_digest(),'data_kind':'SYNTHETIC_TEST',
 'market_performance_evidence':False,'environment':{'platform':platform.platform(),'python':platform.python_version()},
 'measurement':'3 sequential timing repetitions plus separate tracemalloc run; Python allocations are not process RSS or MT5 latency',
 'benchmarks':{}}
def measure(name,fn):
    times=[]
    for _ in range(3):
        start=time.perf_counter();last=fn();times.append(time.perf_counter()-start)
    tracemalloc.start();fn();_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    result['benchmarks'][name]={'repetitions':3,'median_seconds':statistics.median(times),'timings_seconds':times,'python_peak_bytes_separate_run':peak}
    print(name,round(statistics.median(times),6),flush=True)
    return last
engine=AnalysisEngine();engine.analyze(fixture(),'XAUUSD',now=NOW)
p=fixture()
with patch.object(p,'metadata',wraps=p.metadata) as m,patch.object(p,'quote',wraps=p.quote) as q,patch.object(p,'candles',wraps=p.candles) as c:
    measure('single_xauusd',lambda:engine.analyze(p,'XAUUSD',now=NOW))
    result['benchmarks']['single_xauusd']['provider_calls_per_run']={'metadata':m.call_count/4,'quote':q.call_count/4,'candles':c.call_count/4}
r=measure('four_symbol_scanner',lambda:scan(multi_fixture(),('XAUUSD','EURUSD','GBPUSD','USDJPY'),('M15',),now=NOW))
result['benchmarks']['four_symbol_scanner'].update(provider_calls=r['cached_resource_reads'],cache_stats=r['cache_stats'])
measure('three_timeframes',lambda:engine.analyze(fixture(frames=('H1','H4','M15')),'XAUUSD','H1',now=NOW,trigger_timeframe='M15'))
frame=acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')
measure('candlestick_catalogue',lambda:(detect_patterns(frame.bars,tick_size=.01,**frame.kwargs()),candles(frame,.01)))
measure('chart_geometry',lambda:charts(frame,.01))
observations=[Observation('synthetic',str(i),'trend','bullish',20.,True,0,'M15',NOW,'fixture-v1') for i in range(100)]
measure('v2_confluence_100',lambda:combine(observations,as_of=NOW))
for n in (500,2000):
    d=dataset_from_provider(fixture(n=n,frames=('M15',)),'XAUUSD','M15',n);bars=d.frames['15m']
    config=ResearchConfig('15m',bars[250].open_time_ms,bars[-1].close_time_ms,analysis_every_bars=20)
    r=measure(f'{n}_bar_replay',lambda:run_backtest(d,config,fee_bps='0',spread_bps='0',slippage_bps='0'))
    result['benchmarks'][f'{n}_bar_replay'].update(analyses=r['analyses'],closed_trades=len(r['closed_trades']))
d=dataset_from_provider(fixture(n=420,frames=('M15',)),'XAUUSD','M15',420)
config=WalkForwardConfig(train_bars=330,test_bars=40,warmup_bars=250,max_folds=2,simulate_orders=True,
 timeframe='15m',candidates=(Candidate('fast',(TREND,),10),Candidate('slow',(TREND,),20)),
 fee_bps='0',spread_bps='0',slippage_bps='0',validation_bars=20)
measure('two_fold_validation_oos',lambda:run_oos(d,config))
measure('monte_carlo_200_draws_100_trades',lambda:_bootstrap([{'r':v} for v in (1,-1,2,-2,1)*20],42))
app.state.provider=fixture()
with patch('unified_forex.engine.datetime') as clock:
    from datetime import datetime,timezone
    clock.now.return_value=datetime.fromtimestamp(NOW,timezone.utc);clock.fromtimestamp.side_effect=datetime.fromtimestamp
    client=TestClient(app)
    measure('api_analysis_testclient',lambda:client.post('/api/v6/analysis',json={'symbol':'XAUUSD','balance':10000}))
app.state.provider=None
if __version__.startswith('9.'):
    from unified_forex.ingestion import import_file
    from test_v8_ingestion import LocalHistoricalImport
    measure('four_bar_local_import',lambda:import_file(ROOT/'tests/data','v8_handmade.csv',LocalHistoricalImport().request()))
(ROOT/'docs'/output_name).write_text(json.dumps(result,indent=2)+'\n')
