"""Explicit bounded chart snapshot; no network, database or trading endpoint."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.research import load_dataset,HistoricalProvider
from market_ai.v2.chart_research import detect_charts
from market_ai.v2.technical_adapter import TIMEFRAME_MS

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path);p.add_argument('--timeframe',choices=tuple(TIMEFRAME_MS),default='1m')
    p.add_argument('--as-of-ms',type=int);p.add_argument('--bars',type=int,default=200)
    a=p.parse_args(argv)
    try:
        if not 40<=a.bars<=256:raise ValueError('Chart budget')
        d=load_dataset(a.dataset);asof=d.frames[a.timeframe][-1].close_time_ms if a.as_of_ms is None else a.as_of_ms
        bars=HistoricalProvider(d).candles(d.identity.symbol,a.timeframe,asof)[-a.bars:]
        r=detect_charts(bars,timeframe=a.timeframe,as_of_ms=asof,max_age_ms=TIMEFRAME_MS[a.timeframe],tick_size=d.rules['price_tick'])
        r.update(dataset_digest=d.digest,data_kind=d.data_kind,as_of_ms=asof)
    except (ValueError,TypeError,KeyError,OSError):p.exit(2,'Invalid or insufficient chart research input.\n')
    print(json.dumps(r,sort_keys=True,allow_nan=False));return 0 if r['status']=='available' else 1
if __name__=='__main__':raise SystemExit(main())
