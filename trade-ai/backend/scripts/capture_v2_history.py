"""Bounded public Binance normalized capture to NEW JSON files; no SQLite."""
import argparse
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.spot_provider import BinanceSpotProvider,ProviderUnavailable
from market_ai.v2.historical_provenance import capture_history,write_capture

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--symbol',choices=('BTCUSDT','ETHUSDT','SOLUSDT'),required=True)
    p.add_argument('--start-ms',type=int,required=True);p.add_argument('--end-ms',type=int,required=True)
    p.add_argument('--dataset-output',type=Path,required=True);p.add_argument('--manifest-output',type=Path,required=True)
    a=p.parse_args(argv)
    if a.dataset_output.exists() or a.manifest_output.exists():p.exit(2,'Existing output is never overwritten.\n')
    try:
        d,m=capture_history(BinanceSpotProvider(),a.symbol,a.start_ms,a.end_ms,as_of_ms=int(time.time()*1000))
        write_capture(d,m,a.dataset_output,a.manifest_output)
    except (ValueError,TypeError,OSError,ProviderUnavailable):p.exit(2,'Historical capture unavailable or invalid; no partial output or fallback.\n')
    print('Normalized capture saved; license and historical rules remain UNVERIFIED.')
    return 0
if __name__=='__main__':raise SystemExit(main())
