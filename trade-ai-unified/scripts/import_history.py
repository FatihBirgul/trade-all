"""Operator CLI: local root, relative files, read-only dataset/manifest validation."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unified_forex.ingestion import import_file,_read,_unique

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',required=True);p.add_argument('--file',required=True)
    p.add_argument('--declaration',required=True);args=p.parse_args()
    try:
        suffix,raw=_read(args.root,args.declaration)
        if suffix!='.json' or len(raw)>262144:raise ValueError('Bounded JSON declaration required')
        declaration=json.loads(raw,object_pairs_hook=_unique)
        dataset,report=import_file(args.root,args.file,declaration)
        print(json.dumps(report,indent=2,allow_nan=False))
    except (ValueError,OSError,KeyError):
        print(json.dumps({'status':'IMPORT_REFUSED','reason':'invalid path, declaration, source identity, file bounds or candle data'}))
        raise SystemExit(1)
