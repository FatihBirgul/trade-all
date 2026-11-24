# V9 API compatibility

Version9.0.0-rc1 preserves schema6 and all41 paths (20 legacy,21 /api/v6).
No new endpoint. Actual generated inventory: V9_ROUTES.md; schema V9_OPENAPI.json;
strictly synthetic BUY/SELL/refusal examples: V9_RESPONSE_EXAMPLES.json.
The V8 path set and method sets are unchanged. Historical import/pilot/local
checkpoint configuration are Python/CLI interfaces, not public filesystem APIs.

Canonical engine, nested financial schemas, broker/data/market/risk/confluence/
pattern/macro/provenance refusals and retained V1/V5/V6 compatibility remain.
Optional app.state.decision_journal=None can record decisions when an operator
explicitly supplies a journal; default runtime has no persistent decision state.
Retained concurrency tests cover isolated scanner caches/provider keys, research
capacity/cancellation and FVG idempotence/readers; V9 owns exported/restored ledger
state under locks. Exhaustive distributed restart/multi-process safety is not
claimed. Authentication/HTTPS/public deployment need separate operational scope.
