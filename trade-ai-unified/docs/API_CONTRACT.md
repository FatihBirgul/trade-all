# V6 API contract

Start `python -m unified_forex`:127.0.0.1:8006 only. OpenAPI:/openapi.json, docs:/docs.
POST /api/v6/analysis takes symbol, timeframe, optional1..3 higher confirmations,
optional lower trigger, optional balance/risk<=5%, manual records, round-trip
commission/account-currency-per-lot, adverse stop slippage/price, enabled Forex IDs
and optional conservative declared-macro event window. Unknown fields and execution
requests are rejected. Request records and historical/scanner workloads are bounded.

Response AnalysisReport preserves V5 nullable fields and adds schema forex-analysis-6,
source/target code/parameter/snapshot hashes, explicit identity/provider/as-of,
freshness, regime/volatility, actual source technicals/structure/pattern/confluence/
MTF, complete setup assessments/router, candidate direction, final decision,
reasons/levels/verified lot/risk/policy, missing capabilities and integration state.
PRIVATE_INTEGRATED means real selected source integration, not market certification.
Invalid/refused plans have all price/lot fields null. Missing balance gives
NOT_EVALUATED account eligibility. Score strength is heuristic; success probability
is null. Declared-source macro events do not establish complete event coverage.

V6 routes: health, symbols, quotes/{symbol}, candles/{symbol}, sessions/{symbol},
POST indicators/structure/patterns/confluence, GET strategies, POST scanner,
POST risk/calculate, POST alerts, GET news/calendar, POST backtests,
POST research/oos, GET research/status. Analysis component routes call the same
canonical pipeline; they are not independent decision engines.

All20 V1/V5 paths remain. Analysis/signals/scanner/alerts and V5 analysis compatibility
routes now use V6; old data/risk/research routes retain their explicitly legacy
models/rules. V1 retains BUY/SELL/WAIT and field names; V5 retains enum/schema and
maps owned integration to PRIVATE_AVAILABLE/PARTIAL. Algorithms/decisions can change
with the reported engine version. No duplicate competing production pipeline is
used to choose a V6 result. There is no execution request/route or private product
API. HTTP422 covers invalid shapes/workload/protocol; provider construction may
return503, while analytical refusals normally return200 with explicit status.

Research and scanners are synchronous and bounded for local manual use, not a
public multi-tenant service. Remote hosting, authentication, HTTPS, persistent
storage and PWA deployment remain separate. No API result authorizes an order.

## V7 continuation — current behavior

Version7.0 preserves /api/v6 and forex-analysis-6; V1/V5 compatibility remains.
Actual inventory: V7_ROUTES.md; generated schema: V7_OPENAPI.json; explicitly
synthetic examples: V7_RESPONSE_EXAMPLES.json. New GET /api/v6/research/experiments/
{experiment_id}; OOS validation_bars; analysis strategy_parameters; additive
broker_schedule, lifecycle/divergence, provenance/cost/registry and cache_stats.
Strict V6 requests reject string-coerced numbers/unknown fields; typed analysis
and section envelopes retain source dictionaries with their own versions. Nested
vendor dictionaries are not claimed to be fully schema-typed. V1 unhealthy data
keeps HTTP503/WAIT; unsupported confirmation query returns422. Research one-active-
workload gate returns429, budget/contract422, unknown/evicted experiment404.
No arbitrary file path, command, provider import or order permission input exists.
