"""Reproduce the observed baseline from frozen source/config; no live operation by default."""
import argparse
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import sys

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--operator-approved-live',action='store_true')
    args=p.parse_args()
    if args.port in (5173,8005,8007) or (args.port==8006 and not args.operator_approved_live):p.error('Live port requires explicit separate approval')
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'release/cutover/failback-config.json').read_text(encoding='utf-8'))
    release=root/'release/cutover/backend-3c8adb8'
    files={str(f.relative_to(release)).replace('\\','/'):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((release/'forex').glob('*.py'))}
    if files!=config['forex_sha256']:raise ValueError('Failback source drift')
    for k in list(os.environ):
        if k.startswith(('MT5_','V2_')):del os.environ[k]
    os.environ.update(config['environment'])
    sys.path.insert(0,str(release))
    import numpy
    if numpy.__version__!=config['numpy_version']:raise ValueError('Baseline dependency drift')
    for name,version in config['dependencies'].items():
        if importlib.metadata.version(name)!=version:raise ValueError('Baseline dependency drift')
    spec=importlib.util.spec_from_file_location('cutover_readonly',root/'tools/cutover-runtime.py')
    guard=importlib.util.module_from_spec(spec);spec.loader.exec_module(guard)
    import MetaTrader5 as mt5
    from forex.api import app
    from forex.providers import MT5Provider
    from forex.v2_bridge import configured_v2_extension
    from tools.runtime_acceptance.build_fingerprint import loaded_fingerprint
    provider=MT5Provider(mt5=guard.ReadOnlyTerminal(mt5))
    gate=provider.account_preflight('REAL_READONLY_DATA','Exness-MT5Real50','USC')
    if gate['balance'] is not None:raise ValueError('Real balance must not be used')
    app.state.provider=provider;app.state.analytical_extension=configured_v2_extension()
    manifest={'mode':'OBSERVED_BASELINE_REPRODUCTION_NOT_EXACT_OLD_MEMORY_ATTESTATION','pid':os.getpid(),'source_head':config['source_head'],'numpy':numpy.__version__,'port':args.port,'loaded':loaded_fingerprint(),'execution_permission':False}
    with args.manifest.open('x',encoding='utf-8') as out:json.dump(manifest,out,indent=2)
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False,log_level='warning')

if __name__=='__main__':main()
