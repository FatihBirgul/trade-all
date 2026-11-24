# V8 retained research protocol and reliability

Actual V2 train/select/freeze/test and V7 Forex replay remain in place. Protocol and
frozen engine metadata now include exact code_sha256, input/rules/cost/strategy
versions, optional chronological validation hash, purge/embargo and deterministic
seed. Held-out price mutation tests still preserve earlier train/validation/frozen
selection. Historical revisions change dataset/experiment identity; same ID cannot
silently acquire a different result. Candidates are declared strategy-ID/cadence
choices; a general parameter optimizer is not claimed.

Multiple-testing disclosure records declared candidates/folds and explicitly leaves
cross-run search-budget control UNVERIFIED. Small sample, data snooping, nonstationary
markets, broker mismatch, multiple comparisons and selection bias remain limitations.
Strategies are replayed from their own filters/signals; breakdown labels are not
advertised as independent experiments. Fold accounts remain independent; no pooled
compounding/drawdown claim. Fixed-seed retained bootstrap is mechanics only.

ExperimentRegistry32 results/8MB by default, strict hash consistency, eviction and
restart loss remain. Concurrent duplicate records are tested. CancellationToken is
cooperative between bars/folds; cancellation raises ResearchCancelled and incomplete
results are not registered. API grants a per-run random request ID, separate from
deterministic experiment identity. Only matching active ID can cancel; stale IDs409,
overlapping workload429. Finally releases the slot/token after failure/cancel.
No durable production/old V2 ledger connection was added. No partial result is
published as PASS. Durable preregistration and multi-user orchestration remain external.
Tests: test_research_v6.py, test_v7_provenance.py, test_v8_research_costs.py and
test_v8_api_contract.py. All synthetic studies retain INSUFFICIENT_EVIDENCE.
