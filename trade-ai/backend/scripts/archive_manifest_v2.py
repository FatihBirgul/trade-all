"""Manifest for an explicit existing reviewed V2 copy; never creates or edits DB."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.archive_manifest import build_manifest,verify_manifest

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('database',type=Path);p.add_argument('--expected',type=Path);p.add_argument('--max-snapshots',type=int,default=10000);a=p.parse_args(argv)
 try:
  if a.expected and a.expected.stat().st_size>65536:raise ValueError('Manifest budget')
  r=verify_manifest(a.database,json.loads(a.expected.read_text()),max_snapshots=a.max_snapshots) if a.expected else build_manifest(a.database,max_snapshots=a.max_snapshots)
 except (ValueError,OSError):p.exit(2,'Manifest input/budget invalid; no database created or changed.\n')
 print(json.dumps(r,sort_keys=True,allow_nan=False));return 0 if r['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
