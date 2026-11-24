"""Windows read-only evidence export; redirect stdout to a NEW operator-owned JSON file."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from unified_forex.providers import ContractMT5Provider
from unified_forex.pilot import export

if __name__=='__main__':
    try:
        provider=ContractMT5Provider()
        try:report=export(provider)
        finally:provider.close()
    except Exception:report={'status':'DATA_UNAVAILABLE','mt5_validation':'UNVERIFIED','reason':'binding, terminal or configuration unavailable; inspect locally','execution_permission':False}
    print(json.dumps(report,indent=2,allow_nan=False))
    raise SystemExit(0 if report['status']=='READONLY_EVIDENCE_EXPORTED' else 1)
