# V8 verification results

Baseline651=423 V5+152 selected V2+76 host,0 failures/skips. Final682=423+152+107,
0 failures/skips. Vendor test suites preserved;31 new meaningful host cases, including
red/green causal ATR, expired evidence and older-request/newer-ledger regressions.
Local Linux Python3.11.17/3.12.14 full compile/source/host runs pass. Offline guard:
sockets/DNS denied; SQLite restricted to isolated temporary root.

Actual code checkpoint a7927c100717a8f3de535da92f2c19bcbe80fefb matrix run42214034689:
Windows/Ubuntu×3.11/3.12 all four successful. Each log contains423/152/107 and that
SHA. Initial run42213715258 failed on Windows at rooted-path rejection; it was fixed
and rerun, no test was deleted/weakened/skipped. Final documentation commit is also
checked by the matrix; its exact SHA/run is in PR checks and the final delivery.

Coverage ONLY unified_forex:2075/2173 statements95.4901%;632/804 branches78.6070%;
combined90.9305%. Baseline93.5647%/75.2747%, gains1.93/3.33 percentage points.
No vendor or real market/terminal coverage claim. Branch-driven tests target
provider/fetch/encoding/path/macro revision, registry race/cancel, pilot privacy,
financial failure, concurrent API symbols and ledger lifecycle/time boundaries.

Reproduce: python scripts/check_sources.py; python scripts/run_suite.py engine;
python -m coverage run --branch --source=unified_forex -m scripts.run_suite engine;
python -m compileall -q unified_forex vendor/day_trader/forex vendor/trade_ai/backend/market_ai scripts.
Schema export: python scripts/export_contract.py. Pattern diagnostic and source
hash evidence: V8_PATTERN_LAB_RESULTS.json / V8_SOURCE_PROVENANCE.json.

Profiling reuses scripts/benchmark_v7.py (version-aware V8 output),3 repetitions
plus a separate allocation run. P95 omitted:3 samples insufficient. Source checkpoint
d6f98af is recorded; only the unmeasured local importer path guard differs in final
code. All measured modules were verified byte-identical. Median seconds: analysis
.066972, four-symbol .364654, MTF .183461, candle .002701, chart .011258, confluence100
.001308,500 bars1.271573,2000 bars8.858609, OOS1.339277, Monte Carlo.009772, API.086515.
Full repetitions/environment/memory/cache/provider counts in V8_BENCHMARK_RESULTS.json.
Python allocation peak is not process RSS, Windows MT5 or live latency. Concurrent
Cloud validation load existed; no cross-machine latency guarantee or market claim.
