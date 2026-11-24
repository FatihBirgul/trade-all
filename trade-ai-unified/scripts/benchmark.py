"""One bounded synthetic mechanics measurement; Python peak is not process RSS."""
from pathlib import Path
import sys,json,time,tracemalloc
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from fixtures import fixture,multi_fixture,NOW
from unified_forex.engine import AnalysisEngine,code_digest
from unified_forex.services import scan
from unified_forex.confluence import Observation,combine
from unified_forex.research import dataset_from_provider,ResearchConfig,run_backtest,run_oos
from market_ai.v2.walk_forward import WalkForwardConfig,Candidate
from unified_forex.strategies import TREND

result={'engine_version':'6.0.0','code_sha256':code_digest(),'data_kind':'synthetic','market_performance_evidence':False,'measurement':'single bounded Cloud run; Python allocations, not RSS','benchmarks':{}}
def measure(name,fn):
    tracemalloc.start();started=time.perf_counter();value=fn();elapsed=time.perf_counter()-started
    _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    result['benchmarks'][name]={'seconds':round(elapsed,6),'python_peak_bytes':peak}
    return value
engine=AnalysisEngine();engine.analyze(fixture(),'XAUUSD',now=NOW)
measure('single_symbol',lambda:engine.analyze(fixture(),'XAUUSD',now=NOW))
measure('four_symbol_scanner',lambda:scan(multi_fixture(),('XAUUSD','EURUSD','GBPUSD','USDJPY'),('M15',),now=NOW))
measure('three_timeframes',lambda:engine.analyze(fixture(frames=('H1','H4','M15')),'XAUUSD','H1',now=NOW,trigger_timeframe='M15'))
observations=[Observation('fixture',str(i),'trend','bullish',20.0,True,0,'M15',NOW,'fixture-v1') for i in range(100)]
measure('true_confluence_100_observations',lambda:combine(observations,as_of=NOW))
for n in (500,2000):
    d=dataset_from_provider(fixture(n=n,frames=('M15',)),'XAUUSD','M15',n);b=d.frames['15m']
    c=ResearchConfig('15m',b[250].open_time_ms,b[-1].close_time_ms,analysis_every_bars=20)
    measured=measure(str(n)+'_bar_backtest',lambda:run_backtest(d,c,fee_bps='0',spread_bps='0',slippage_bps='0'))
    result['benchmarks'][str(n)+'_bar_backtest']['closed_trades']=len(measured['closed_trades'])
d=dataset_from_provider(fixture(n=420,frames=('M15',)),'XAUUSD','M15',420)
c=WalkForwardConfig(train_bars=330,test_bars=40,warmup_bars=250,max_folds=2,simulate_orders=True,timeframe='15m',
                    candidates=(Candidate('trend-fast',(TREND,),10),Candidate('trend-slow',(TREND,),20)),fee_bps='0',spread_bps='0',slippage_bps='0')
measure('two_fold_oos',lambda:run_oos(d,c))
(ROOT/'docs/BENCHMARK_RESULTS.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
