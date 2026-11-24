# V8 additive API contract

Engine8.0 retains /api/v6 + forex-analysis-6, all40 V7 paths and V1/V5 adapters.
Actual generated inventory41 paths=20 legacy+21 v6. One needed endpoint added:
POST /api/v6/research/cancel with strict32-hex active run_id. Research status exposes
active_run_id. Wrong/stale ID409; overloaded workload429; cancelled/invalid request422;
unknown/evicted experiment404; provider unavailable503. Cancellation is cooperative,
not a thread kill, and partial results never become registered PASS results.

Nested EntryZone, LotSizing, CostAdjustedPlan and RiskPolicy schemas validate
financial responses. JSON field names are retained; dict-style Python field access
is preserved. Vendor pattern/technical dictionaries remain versioned and partially
typed; this is not a claim of total nested schema coverage. V7 saved examples and
all old paths are regression-tested. Null plan on veto remains mandatory.

V8_OPENAPI.json, V8_ROUTES.md and V8_RESPONSE_EXAMPLES.json are generated from actual
app/models, not a desired route list. test_v8_api_contract.py validates historical
V7 examples, new responses, financial invalid examples, error/status contracts,
concurrent symbol isolation and run-ID cancellation cleanup. No file import path
is exposed over HTTP. Request budgets/local host/default no cross-origin allowance
remain. Public auth/HTTPS/deployment and durable multi-user job scheduling not added.
