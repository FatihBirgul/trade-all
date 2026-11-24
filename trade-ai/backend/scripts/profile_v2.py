"""Create a NEW versioned research profile; never changes runtime permissions."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.strategy_profiles import StrategyProfile,load_profile
from market_ai.v2.decision_record import _canonical

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--parent',type=Path)
    p.add_argument('--strategies');p.add_argument('--methods',default='roc12')
    p.add_argument('--bias',default='1m');p.add_argument('--setup',default='1m');p.add_argument('--trigger',default='1m')
    p.add_argument('--confirmations',type=int,default=2);p.add_argument('--every',type=int,default=10)
    a=p.parse_args(argv)
    if a.output.exists():p.exit(2,'Existing profile is never overwritten.\n')
    owned=False
    try:
        parent=load_profile(a.parent) if a.parent else None
        extra={'strategy_ids':tuple(a.strategies.split(','))} if a.strategies else {}
        profile=StrategyProfile(required_methods=tuple(filter(None,a.methods.split(','))),bias_timeframe=a.bias,
            setup_timeframe=a.setup,trigger_timeframe=a.trigger,minimum_confirmations=a.confirmations,
            analysis_every_bars=a.every,revision=parent.revision+1 if parent else 1,parent_id=parent.profile_id if parent else None,**extra)
        with a.output.open('x',encoding='utf-8') as f:
            owned=True;f.write(_canonical(profile.body())+'\n')
    except (ValueError,TypeError,OSError):
        if owned:a.output.unlink(missing_ok=True)
        p.exit(2,'Invalid profile or unavailable new output.\n')
    print(profile.profile_id);return 0
if __name__=='__main__':raise SystemExit(main())
