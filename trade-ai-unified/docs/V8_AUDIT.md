# V8 recovery and severity matrix

Start/remote HEAD f22190a575dfb8426a7f66d3df34c6290c7a57a2, branch
codex/unified-forex-engine-v6, clean worktree. Private/draft PR1 preserved; main4df4b48.
Baseline rerun:423+152+76=651, no failures/skips. Existing V7 financial/as-of fixes
retained. Source repositories are read-only; no migration repeated.

| Severity | Finding | Evidence/treatment |
|---|---|---|
| HIGH | Latest ATR reclassifies historical swings/zone tolerances | Red/green V8CausalAudit; freeze tolerance at first-known |
| HIGH | Stale/invalidated evidence can block a fresh setup | Red/green V8CausalAudit; explicit age/lifecycle gate before V2 reducer |
| HIGH | Rule epochs change fee/spread metadata but replay ignores them | Bind explicit dated costs; reject unsupported settlement |
| MEDIUM | FVG active-only; rolling history disappears | Bounded causal checkpoint/replay ledger |
| MEDIUM | Missing local-file ingestion boundary | Bounded root-owned CSV/JSON import with explicit source/license/hash |
| MEDIUM | OOS identity omits exact source content | Include code digest in frozen protocol |
| MEDIUM | Diagnostic exception strings/terminal payload can disclose fields | Whitelisted export and generic errors |
| MEDIUM | Source publication missing; compatible macro published field is knowledge time | Separate canonical public release/knowledge timestamps |
| LOW | Family tests mostly geometry rather than adversarial OHLC | Seeded validation lab, metamorphic invariants and honest statuses |

Existing inventory: core capture/QC/financial math/router/compatibility VERIFIED_OFFLINE;
market edge/actual MT5 IMPLEMENTED_UNVERIFIED_IN_MARKET/BLOCKED_BY_EXTERNAL_DATA;
FVG history/import/official provider coverage PARTIAL or MISSING at start; rounding
and unvalidated chart families EXPERIMENTAL. No function existence implies market
validation. Review covers current unified modules, selected source contracts and
tests; duplicate final decision engine was not found. Additional fixes/tests and
remaining statuses are recorded in V8 delivery documents.

## Final module inventory/status

| Module | Review/status |
|---|---|
|engine/market |Single decision, owned QC/as-of/cache; VERIFIED_OFFLINE |
|technical/divergence |Retained variants/causal aligned pivots; VERIFIED_OFFLINE; market utility unverified |
|patterns/candle_extensions/chart_geometry |Closed-entry guards/QA metadata; PARTIAL family OHLC validation; rounding EXPERIMENTAL |
|structure_events/structure_ledger |Frozen tolerance + bounded causal FVG transitions/checkpoints; VERIFIED_OFFLINE; durable history PARTIAL |
|confluence |Actual V2 reducer, stale/lifecycle rejection and dedup/veto; VERIFIED_OFFLINE |
|strategies |Four retained Forex families/risk veto; IMPLEMENTED_UNVERIFIED_IN_MARKET |
|provenance/ingestion |CSV/JSON declared identity/rules/hash checks; VERIFIED_OFFLINE; Parquet MISSING |
|research/experiments/research_control |Actual V2 protocol, dated costs, code freeze, race/eviction/cancel; VERIFIED_OFFLINE mechanics |
|macro/official_calendar |BLS/Fed/ECB/BEA parsers; PARTIAL coverage; BoE/BoJ external blocks |
|providers/pilot |Read-only mocked SDK/profit/margin/export; real Windows BLOCKED_BY_EXTERNAL_DATA |
|services/api/schemas |Bounded shared state, typed financial envelope, old routes/examples; VERIFIED_OFFLINE |

Additional HIGH as-of defect in shared-ledger out-of-order requests was red/green
fixed. Windows CI found rooted-path portability error; fixed without weakening
assertions and all four jobs passed. No unresolved HIGH defect established in the
reviewed offline surface; external market/broker/source evidence remains absent.
Exact final test/coverage/scope are V8_VALIDATION.json and V8_TEST_RESULTS.md.
