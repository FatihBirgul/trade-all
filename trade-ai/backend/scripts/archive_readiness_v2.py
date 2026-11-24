"""Read-only exact-copy readiness; explicit reviewed manifest and paths only."""
import argparse,json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.archive_readiness import assess_copies

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected',type=Path,required=True)
    p.add_argument('--max-snapshots',type=int,default=10000)
    p.add_argument('copies',type=Path,nargs='+')
    a=p.parse_args(argv)
    try:
        with a.expected.open('rb') as f:raw=f.read(65537)
        if len(raw)>65536:raise ValueError('Manifest budget')
        result=assess_copies(a.copies,json.loads(raw),max_snapshots=a.max_snapshots)
    except (ValueError,TypeError,OSError):
        p.exit(2,'Invalid reviewed archive input; no files created or modified.\n')
    print(json.dumps(result,sort_keys=True,allow_nan=False))
    return 0 if result['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
