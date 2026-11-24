"""Validate untrusted, sanitized pilot evidence from an explicit local read-only root."""
from pathlib import Path
import sys,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unified_forex.ingestion import _read
from unified_forex.pilot_validation import validate
from unified_forex.engine import code_digest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--file',required=True)
    args=p.parse_args()
    try:
        _,raw=_read(args.root,args.file)
        print(json.dumps(validate(raw,expected_code_sha256=code_digest()),indent=2,allow_nan=False))
    except (ValueError,TypeError,OSError,KeyError):
        print(json.dumps({'status':'EVIDENCE_REFUSED','reason':'invalid, stale, sensitive, mismatched or oversized pilot evidence',
                          'real_terminal_validated':False,'automatic_contract_override':False}));raise SystemExit(1)
