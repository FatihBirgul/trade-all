"""Explicit offline historical research; never opens a user's SQLite database."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.research import load_dataset, ResearchConfig, run_backtest
from market_ai.v2.strategy_profiles import load_profile


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path,help='Existing version1 historical/synthetic JSON; no network fetch')
    p.add_argument('--start-ms',type=int,required=True);p.add_argument('--end-ms',type=int,required=True)
    p.add_argument('--profile',type=Path)
    p.add_argument('--timeframe');p.add_argument('--paper',action='store_true',help='Simulate candidates only in owned temporary DB')
    p.add_argument('--every',type=int);p.add_argument('--fee-bps',default='5')
    p.add_argument('--spread-bps',default='2');p.add_argument('--slippage-bps',default='1')
    args=p.parse_args(argv)
    try:
        profile=load_profile(args.profile) if args.profile else None
        if profile and ((args.timeframe and args.timeframe!=profile.setup_timeframe) or (args.every is not None and args.every!=profile.analysis_every_bars)):
            raise ValueError('Profile/CLI mismatch')
        tf=profile.setup_timeframe if profile else args.timeframe or '1m'
        every=profile.analysis_every_bars if profile else args.every if args.every is not None else 5
        extra={'timeframes':tuple(t for t in profile.timeframes if t!=tf),'strategy_ids':profile.strategy_ids} if profile else {}
        report=run_backtest(load_dataset(args.dataset),ResearchConfig(timeframe=tf,start_ms=args.start_ms,end_ms=args.end_ms,
            simulate_orders=args.paper,analysis_every_bars=every,**extra),profile=profile,fee_bps=args.fee_bps,spread_bps=args.spread_bps,slippage_bps=args.slippage_bps)
    except (ValueError,TypeError,KeyError,OSError):p.exit(2,'Research input/configuration invalid or unavailable; no live fallback.\n')
    print(json.dumps(report,sort_keys=True,allow_nan=False))
    return 0 if report['integrity_status']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
