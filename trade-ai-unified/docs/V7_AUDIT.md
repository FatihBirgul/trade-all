# V7 recovery and severity audit

Recovery starts at `ce01eb8933e45e8cd25af6b34418d19f0026c26c`, equal to the
remote feature branch. No tracked or staged differences; three untracked V6 JSON
evidence files preserved. Main remains `4df4b48`. Existing PR1 stays draft.
Local Python3.12 rerun:423+152+47=622, no failures/skips. Actions42144724852:
Windows/Ubuntu ×3.11/3.12 all successful; Windows3.11 log independently reports
423,152,47. Net-RR39/23 independent oracle and unsized cost veto pass.

| Severity | Finding | Required treatment |
|---|---|---|
| HIGH | Replay relocates stop/target at next open instead of honoring known geometry | Keep frozen absolute levels; reject unfavorable fills; independent oracle |
| HIGH | Declared broker schedule called verified | Separate DECLARED/UNAVAILABLE trust from authenticated provenance |
| HIGH | Generic tick value used despite asymmetric profit/loss values | Use explicit side-of-PnL value; reject invalid values/currency |
| MEDIUM | Overnight schedule can spill into a full-day holiday override | Explicit closure must veto previous-day overnight spill |
| MEDIUM | Alert state lacks hard cardinality and stable setup dedup | Bounded state, event identity, restart semantics |
| MEDIUM | Chart pivot confirmation can be read as neckline confirmation | Versioned geometric adapter with explicit candidate/breakout states |
| MEDIUM | Candle context includes formation; descriptive patterns still receive directional score | Separate pre-formation context and descriptive evidence |
| MEDIUM | Data/rule hashes do not prove historical authenticity | Explicit provenance trust and point-in-time coverage |
| MEDIUM | Research lacks registry and independent direction/cost attribution | Bounded in-memory registry, frozen protocol and per-trade cost metrics |
| LOW | Benchmarks single repetition; docs/PR reflect older counts | Median repetitions, regenerated schemas/evidence, final CI |

No CRITICAL issue established in the reviewed offline surface. Real MT5, licenses,
historical rules and macro coverage remain external evidence requirements.

Module review: `market` owns bounded immutable snapshot/QC and request-only cache;
`technical` names numerical variants; `patterns` retains actual V2 detectors and
V5 confirmed pivots; `confluence` uses V2 reducer; `strategies` retains crypto gates
and four separate FX rules; `engine` nulls vetoed plans; `research` executes causal
prefixes through the same engine/V2 fold protocol; `services` has no order paths;
`providers` retains locked MT5 reads; `api` uses the same host with V1/V5 adapters.
Vendor tests remain isolated by process and unmodified. Financial uncertainty is
reported, never replaced with synthetic broker assertions. Each subsequent commit
records regressions and algorithm version changes in DEVELOPMENT_PROGRESS.
