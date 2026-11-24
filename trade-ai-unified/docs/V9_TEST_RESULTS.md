# V9 reproducible validation evidence

Baseline at d2bf026:423 V5+152 V2+107 host=682, failed0/skipped0. Final code
f1cf856d34dd3d1b0f8fbbcbc8d806ab3909b858:423+152+127=702, failed0/skipped0. Twenty new host tests address actual
ownership/source/import/side/PIT/protocol/pilot/macro risks; no original test was
deleted, skipped or weakened. Linux Python3.11.17/3.12.14 local runs passed.
Compileall and pinned-source checks passed in CI. Commands:

```bash
python scripts/check_sources.py
python scripts/run_suite.py engine
python -m compileall -q unified_forex vendor/day_trader/forex vendor/trade_ai/backend/market_ai scripts
python -m coverage run --branch --source=unified_forex scripts/run_suite.py engine
python -m coverage json
```

Code CI https://github.com/FatihBirgul/trade-ai-unified/actions/runs/42244153003
passed Ubuntu/Windows Python3.11/3.12. Job IDs127981848593,127981848678,
127981848748,127981849006; each log contains423/152/127 and the same SOURCE_SHA256
04f874f4b085ec212686a86553fa6f840a3138d653a8ce517e8bd77ab56d7c59. Intermediate failed Windows3.12 run42243686985 is disclosed in
V9_SECURITY_AUDIT.md; corrected at f1cf856, no skips. Final documentation commit
is checked separately in GitHub; code checkpoint remains stable for reproduction.

Coverage scope is only unified_forex, not the vendored/whole repository.
Statements2470/2578=95.8107% (V8 95.4901%); branches782/1026=76.2183%
(V8 78.6070%). Branch percentage fell as new refusal/state paths expanded scope;
this is an open QA gap, not a coverage improvement claim. Missing lines/branches
by file: V9_COVERAGE.json. Priorities: journal collision/eviction/concurrent reads,
registry publication failure races, checkpoint OS/persistence errors, pilot hostile
shape combinations and official parser schema shifts. Native descriptor traversal
is only exercised on supported OS; strict unsupported mode refuses.

Benchmarks use synthetic fixtures, three sequential timing samples and separate
tracemalloc run; allocations are not RSS. Whole benchmark checkpoint57b0927,
local import rerun at f1cf856 after only importer Windows-comparison changes.
V9_BENCHMARK_RESULTS.json records row-specific hashes. Shared Linux cloud load,
not a controlled hardware experiment: ratios below are descriptive, not an
algorithmic speedup/regression conclusion. Real Windows MT5 latency UNVERIFIED.

| Operation | V8 median s | V9 median s | V9/V8 |
|---|---:|---:|---:|
| single_xauusd | 0.066972 | 0.109900 | 1.641 |
| four_symbol_scanner | 0.364654 | 0.568586 | 1.559 |
| three_timeframes | 0.183461 | 0.167781 | 0.915 |
| candlestick_catalogue | 0.002701 | 0.004097 | 1.517 |
| chart_geometry | 0.011258 | 0.013195 | 1.172 |
| v2_confluence_100 | 0.001308 | 0.001858 | 1.420 |
| 500_bar_replay | 1.271573 | 1.329063 | 1.045 |
| 2000_bar_replay | 8.858609 | 8.020516 | 0.905 |
| two_fold_validation_oos | 1.339277 | 1.309979 | 0.978 |
| monte_carlo_200_draws_100_trades | 0.009772 | 0.009027 | 0.924 |
| api_analysis_testclient | 0.086515 | 0.077731 | 0.898 |

Four-row CSV import median 0.000795s;
no comparable V8 import measurement exists. Larger licensed import performance
remains unmeasured. Replay synthetic trade counts measure plumbing, not edge.
