"""Safe existing provider diagnostic; no order placement or terminal configuration."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unified_forex.providers import ContractMT5Provider
from unified_forex.diagnostics import diagnose
from forex.core import DataError
if __name__=='__main__':
    try:
        provider=ContractMT5Provider()
        try:print(json.dumps(diagnose(provider),indent=2,allow_nan=False))
        finally:provider.close()
    except DataError as exc:
        print(json.dumps({'status':'UNVERIFIED','reason':str(exc)}));raise SystemExit(1)
