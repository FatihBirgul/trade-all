"""Compare a bounded sanitized pilot export to operator-supplied contract expectations."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unified_forex.pilot import reconcile

def read(path):
    with Path(path).open('rb') as f:raw=f.read(262145)
    if len(raw)>262144:raise ValueError('Input budget exceeded')
    return json.loads(raw)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',required=True);p.add_argument('--reference',required=True)
    args=p.parse_args()
    try:print(json.dumps(reconcile(read(args.reference),read(args.evidence)),indent=2,allow_nan=False))
    except (ValueError,TypeError,KeyError,OSError):
        print(json.dumps({'status':'COMPARISON_REFUSED','reason':'invalid bounded sanitized evidence/reference'}));raise SystemExit(1)
