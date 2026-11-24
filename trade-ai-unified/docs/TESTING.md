# Reproducible offline validation

Runtime/test/transitive requirements are pinned in requirements-lock.txt, generated
universally from requirements-test.txt. Python3.11/3.12 are supported for the unified
numerical package; old standalone stock compatibility is not a promise that the
complete V6 package supports3.8/3.10. Original public3.10 CI source evidence is retained.

Run `python scripts/check_sources.py` (423 V5 and152 selected pure V2 tests) and
`python scripts/run_suite.py engine` (new host integration/financial/security tests).
Each suite runs separately to prevent original tests namespace collisions. All use
the retained offline guard: socket/DNS denied, SQLite only in a new temporary root.
No MetaTrader5 terminal, production service or live price is necessary. Complete
original381 V2 source tests were also rerun against the read-only original checkout;
product/ledger tests are excluded from the extracted target because those modules
are deliberately not shipped. They are not counted as transferred tests.

CI: Windows/Ubuntu x Python3.11/3.12, compile plus the three suites, read-only token,
no broker/AI secrets or private source fetch. V2 source is already inside this private
repository. Exact source/fixture bytes are preserved across OSes by .gitattributes.

Independent goldens and mathematical variant tests live in the retained source
suites. New tests additionally prove actual source QC/regime/pattern/confluence/
router execution, all four Forex family positives, conflict/risk/session/MTF/finality/
identity guards, retained OOS with held-out mutation, metadata immutability, gap loss,
macro provenance, API compatibility, scanner caching and no product/order imports.
Source test assertions were not weakened or removed. Feature gaps stay explicit.

Coverage command: `python -m coverage run --branch --source=unified_forex scripts/run_suite.py engine`.
Benchmark: `python scripts/benchmark.py`; one synthetic Cloud run measures wall time
and Python allocation peak, not process RSS or Windows/market performance. Actual
results are docs/BENCHMARK_RESULTS.json. Source data/fees/licenses and profitability
are not validated by successful mechanics tests.

## V7 continuation — current behavior

Recovery622=423+152+47 passed. V7 retains both vendor suites unchanged and extends
host tests with red/green financial/session/dedup regressions, per-family candle
causality, chart geometry/pivot knowledge, aligned divergence, historical epoch/
retrieval boundaries, validation freeze/held-out mutation, registry, macro revisions/
DST/network failure, alert concurrency and API strict/budget/security invariants.
Final totals/coverage/CI are in V7_DELIVERY_REPORT_TR.md and V7_VALIDATION.json.
Coverage source=unified_forex only; vendor/Windows/live market coverage not implied.
Run python scripts/benchmark_v7.py for3 medians plus a separate Python allocation
measurement (not RSS); results V7_BENCHMARK_RESULTS.json. python scripts/export_contract.py
regenerates actual OpenAPI/routes and synthetic examples. Old V6 artifacts retained
as recovery evidence, not current release schemas. Compilation and original four
CI jobs remain required. Failing/skipped counts are reported, never hidden.
