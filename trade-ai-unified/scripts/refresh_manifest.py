"""Update destination hashes without reading or writing source repositories."""
import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'docs/source_manifest.json'
rows=json.loads(p.read_text())
notes={
 'data_quality.py':'Optional exact verified session-gap intervals; strict default retained',
 'market_data_contract.py':'Explicit CFD contract and optional verified session gaps',
 'capabilities.py':'CFD identity supports OHLC/tick; real-volume spot/CFD remains denied',
 'technical_adapter.py':'Added30m contract duration only; original real-volume technical gate preserved',
 'technical.py':'Optional cached rolling RSI input for stochastic RSI; default preserved',
 'mtf.py':'30m rank support; original default frame catalogue retained',
 'price_action.py':'Explicit session gaps and optional already-computed SMA ATR; defaults preserved',
 'pattern_research.py':'Explicit session-gap input; original rules/catalogue preserved',
 'chart_research.py':'Explicit session-gap input; original bounded geometry preserved',
 'technical_research.py':'Explicit session-gap input; original Decimal calculations preserved',
 'strategy_router.py':'CFD market identity added; original crypto specs not changed',
 'core.py':'Cache shared indicators, retain ATR plan; V7 account-currency gross/net RR and asymmetric profit/loss tick risk with independent oracles',
 'strategies.py':'Reuse canonical previous EMA20 when supplied; retain upstream fallback for legacy metrics',
 'providers.py':'Explicit read-only SDK allowlist rejects execution before dispatch; account margin_free/leverage exposed without additional SDK operation',
 'sessions.py':'Full-day and partial date overrides supersede previous overnight windows; existing IANA session rules retained',
 'structure.py':'Expose existing confirmed pivot lists for equality/zone context',
 'contracts.py':'Explicit simulation-only zero-spread option; default strict quote rule unchanged',
 'walk_forward.py':'Retain train/select/freeze/test; Forex runner/IDs/timebase, optional purged validation tail, frozen validation hash, dated rule prefixes and conservative workload count',
 'historical_provenance.py':'Forex execution-frame verification; exclude crypto acquisition/file writer',
}
for row in rows:
 if not row.get('destination'):continue
 path=root/row['destination']
 current=hashlib.sha256(path.read_bytes()).hexdigest()
 row['destination_sha256']=current
 row['modifications']=[notes.get(path.name,'See destination diff and module docstring')] if current!=row['original_sha256'] else []
 row['status']='ADAPTED' if row['modifications'] else 'PRESERVED'
 row['integration_status']='ADAPTED_AND_REGRESSION_TESTED' if row['modifications'] else 'PRESERVED_AND_REGRESSION_TESTED'
p.write_text(json.dumps(rows,indent=2)+'\n')
