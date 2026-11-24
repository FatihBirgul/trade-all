"""Explicit offline train/select/freeze/test; owned temporary SQLite only."""
import argparse
import json
import sqlite3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.research import load_dataset
from market_ai.v2.historical_provenance import load_manifest
from market_ai.v2.walk_forward import Candidate, IndicatorCandidate, WalkForwardConfig, run_walk_forward
from market_ai.v2.indicator_parameters import IndicatorParameters,VERSION as PARAMETER_VERSION,versions


def load_indicator_candidates(path,dataset):
    """Explicit bounded source/version binding; reject duplicate JSON keys."""
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError('Duplicate protocol key')
            out[key]=value
        return out
    with Path(path).open('rb') as f:raw=f.read(16385)
    if len(raw)>16384:raise ValueError('Parameter candidate budget exceeded')
    body=json.loads(raw,object_pairs_hook=unique)
    if (not isinstance(body,dict) or set(body)!={'schema_version','implementation_version','strategy_versions','dataset_digest','source','candidates'}
            or type(body['schema_version']) is not int or body['schema_version']!=1 or body['implementation_version']!=PARAMETER_VERSION
            or body['strategy_versions']!=dict(versions()) or body['dataset_digest']!=dataset.digest or body['source']!=dataset.source
            or type(body['candidates']) is not list or not 1<=len(body['candidates'])<=4):
        raise ValueError('Parameter protocol source/version mismatch')
    candidates=[]
    for row in body['candidates']:
        if not isinstance(row,dict) or not {'candidate_id','parameters'}<=set(row)<={'candidate_id','parameters','strategy_ids','analysis_every_bars'} or not isinstance(row['parameters'],dict):raise ValueError('Invalid candidate fields')
        fields={k:v for k,v in row.items() if k!='parameters'}
        if 'strategy_ids' in fields:
            if type(fields['strategy_ids']) is not list:raise ValueError('Strategy list required')
            fields['strategy_ids']=tuple(fields['strategy_ids'])
        candidates.append(IndicatorCandidate(**fields,parameters=IndicatorParameters(**row['parameters'])))
    return tuple(candidates)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path)
    p.add_argument('--manifest',type=Path)
    p.add_argument('--train-bars',type=int,required=True);p.add_argument('--test-bars',type=int,required=True)
    p.add_argument('--warmup-bars',type=int,default=250);p.add_argument('--horizon',type=int,required=True)
    p.add_argument('--purge',type=int,required=True);p.add_argument('--embargo',type=int,default=0)
    p.add_argument('--rolling',action='store_true');p.add_argument('--max-folds',type=int,default=3)
    p.add_argument('--fee-bps',default='5');p.add_argument('--spread-bps',default='2');p.add_argument('--slippage-bps',default='1')
    p.add_argument('--parameter-candidates',type=Path,help='Explicit source/version-bound JSON; max4 frozen research candidates')
    p.add_argument('--cadences',default='10');p.add_argument('--paper',action='store_true')
    p.add_argument('--registry',type=Path,help='Explicit standalone registry, never a financial DB')
    p.add_argument('--create-registry',action='store_true',help='Exclusive new registry creation; existing files refused')
    a=p.parse_args(argv)
    try:
        dataset=load_dataset(a.dataset)
        if a.parameter_candidates and a.cadences!='10':raise ValueError('Use parameter candidates OR cadence list')
        candidates=load_indicator_candidates(a.parameter_candidates,dataset) if a.parameter_candidates else tuple(Candidate('cadence-'+x,analysis_every_bars=int(x)) for x in a.cadences.split(','))
        c=WalkForwardConfig(train_bars=a.train_bars,test_bars=a.test_bars,warmup_bars=a.warmup_bars,
            label_horizon_bars=a.horizon,purge_bars=a.purge,embargo_bars=a.embargo,
            mode='rolling' if a.rolling else 'expanding',fee_bps=a.fee_bps,spread_bps=a.spread_bps,slippage_bps=a.slippage_bps,max_folds=a.max_folds,candidates=candidates,simulate_orders=a.paper)
        manifest=None
        if a.manifest is not None:
            manifest=load_manifest(a.manifest)
        registry=None
        if a.create_registry and a.registry is None:raise ValueError('Explicit registry path required')
        if a.registry is not None:
            from market_ai.v2.research_registry import ResearchRegistry
            registry=ResearchRegistry.create(a.registry) if a.create_registry else ResearchRegistry(a.registry)
        r=run_walk_forward(dataset,c,manifest=manifest,registry=registry)
    except (ValueError,TypeError,KeyError,OSError,sqlite3.DatabaseError):p.exit(2,'Invalid or insufficient offline walk-forward input; no fallback.\n')
    print(json.dumps(r,sort_keys=True,allow_nan=False))
    return 0 if r['validation_status']=='OOS_EVALUATED' else 1

if __name__=='__main__':raise SystemExit(main())
