# V6 engineering checkpoints

## M0 recovery
- Writable private target verified: FatihBirgul/trade-ai-unified, initial main 4df4b48556df0a5e8a32324fdbf6d9d3bf1e5203.
- Feature branch codex/unified-forex-engine-v6; no source repository writes or old PR changes.
- Source A fdcdd418d96d05e71453e70c1f39956dd1cfe9d5: 423 tests passed on Python3.12, 0 failures/skips.
- Source B b69111608ea3c2e78609fd84a0d81dee2781c980: 381 tests passed on Python3.12, sockets/DNS forbidden, temporary-root SQLite only.
- Original stock MIT notice retained. Private source reuse is owner-authorized only in this private target.

## M1/M2 migration
V5 source/test snapshot preserved under vendor/day_trader; selected V2 deterministic
modules and pure tests extracted under vendor/trade_ai. No product DB, paper ledger,
auto-paper service, Gateway, Android or old frontend was migrated. Pure paper_risk is
calculation-only and remains distinct from execution. The selected source must still
be adapted/integrated and tested; migration alone is not completion.

Migration validation: `python scripts/check_sources.py` passed423 retained V5 tests
and152 selected V2 pure tests. The original381 suite passed separately against the
read-only source snapshot. Missing product tests were not replaced with stubs.

## M3/M4 canonical data and technical integration
Canonical V5 snapshot + actual V2 QC/capabilities support explicitly classified CFD,
verified broker gaps and M30; lower trigger frames obey primary-close as-of. Main
technical formulas remain versioned; real V2 research and rolling RSI execute on
valid OHLC without pretending tick volume is exchange volume. The original
aggregate crypto technical adapter remains gated. Five market tests passed;
source regressions still423+152 after initial adaptations.

## M5/M6 structure/pattern/confluence
Real V2 price-action/candle/chart/MTF/confluence functions now execute in V6. V5
pivot zones/equality and one versioned modified-Hikkake engineering variant added.
Missing chart families and structural invalidation limits remain explicit. Tests
cover first-known/prefix/mirror/negative geometry and real event/bucket dedup plus
opposing-strength veto. Source crypto setup constraints remain unchanged.

## M7/M8 canonical strategies and financial veto
Four separately versioned price-only Forex families use real retained calculations
and actual V2 routing. Original crypto volume gates remain. Opposing eligible
strategy directions, price context and higher/lower TF context veto before V5
planning/sizing. BUY/SELL, high spread, absent metadata/schedule, stale/unfinished,
provider failure and risk-cap end-to-end tests pass. Range and breakout actual
indicator fixtures, plus sweep -> reversal -> BUY full pipeline, pass. Market
profitability, margin/swap and real terminal validation remain UNVERIFIED.

## M9 research
Retained continuation walk_forward orchestrates real Forex train/select/freeze/test;
only dataset/runner/strategy/version/timebase dependencies were adapted. Pure source
summary math extracted; no ledger/product code copied. Actual multi-trade, two-fold
OOS, first-fold held-out mutation, deterministic repeat, finality/budget/ownership
and negative-equity gap regressions passed. Real-market provenance remains unverified.

## M10/M11 services and API
Actual V5 macro/RSS/alert helpers reused. Scanner shares provider reads across
symbol/timeframe pairs and ranks transparent eligibility rather than fake confidence.
Local alerts add structure/session/breakout/risk/declared-macro contexts and never
execute. Optional declared-high-impact veto does not certify coverage. V6 typed API
and V1/V5 compatibility use the one decision engine. API and service tests passed;
localhost-only launcher and pinned requirements supplied. No live feed claimed.

## M12 offline test/CI program
Pinned universal transitive lock; Windows/Linux x Python3.11/3.12 CI added. Source
suites remain423+152, and V6 functional/security tests grew to44. Linux3.11/3.12
passed; no failures/skips. Offline socket/DNS/temporary-SQLite guard reused. Added
wrong currency/min-lot, actual BOS -> deduplicated confluence, UNKNOWN/MTF refusal,
API cleanup and operator metadata-boundary cases. Live acquisition now freezes its
as-of AFTER cached reads; explicit historical cutoffs do not advance. Source quote/
contract/interval identity mismatches fail closed. Coverage/benchmarks are measured
separately and will be recorded in final delivery; remote CI not assumed before runs.

## M13 security/financial audit
Source/interval/provider/contract, cached live acquisition timing, broker-direction/
loss/currency/grid, negative-gap-equity and frozen-history/OOS boundaries reviewed.
The SDK boundary now rejects non-allowlisted operations BEFORE dispatch; a negative
order-method test verifies the SDK is never called. Same-event dropped evidence
remains in input_observations so structure -> confluence provenance is auditable
without adding another vote. Unused legacy V2 aggregate excluded with manifest reason.
No source repo or old PR changed. Remaining catalogue/live-data gaps stay explicit.

Final financial audit also added an independent net-RR oracle and cost-adjusted
plan veto, including unsized candidates and historical fills. Gross2R is no longer
accepted when known round-trip costs make net TP1 reward inadequate. The risk
algorithm version is forex-cost-netrr-v6-2; zero-cost legacy math remains unchanged.

## V7 M0–M1 / financial and session corrections
Recovery622/622 passed at ce01eb8; tracked changes absent, three JSON artifacts
preserved. Audit in V7_AUDIT.md. New independent regressions first failed3/4,
then4/4 passed: asymmetric loss/profit tick values, holiday overnight override,
next-open frozen levels and broker profit-sign/currency rejection. Root51 tests
pass. Net-RR version becomes forex-cost-netrr-v7-1; original v6-2 mathematics
remains when profit/loss tick values coincide. Replay freezes absolute stop/TP,
uses stop-only exit slippage, R=actual net PnL/initial cost-inclusive risk and
side-specific tick conversion. Commission is one round trip per completed trade.
Schedule provenance now explicitly DECLARED/UNAVAILABLE and never authenticated;
legacy verified opt-in remains compatible as a declared policy acceptance.

## V7 M2–M6 / causal analysis extensions
Added11 absent engineering candle geometries, independently table-tested positive,
flat negative and mirrors (symmetric families); tick boundary and causal later-close
confirmation regression. Retained Ladder/Mat Hold/Concealing tests now exercise
actual V2 code. Added16 chart family geometry catalogue using retained V2 pivot and
slope functions: explicit lines, width-scaled thresholds, pole requirement, neckline,
two later close breakout, retest/failure/expiry. Positive/negative geometric tests,
rounding-vs-linear rejection and real OHLC pivot timing tests pass. Catalogue is
DESCRIPTIVE with PARTIAL_FAMILY_VALIDATION, not a completed market validation claim.
Added aligned regular/hidden RSI/MACD divergence and asynchronous pivot knowledge
regressions, V5 confirmed pivot lifecycle/BOS/CHoCH/range/FVG/sweep context. FVG
lifecycle retains V2 active-only scope. Confluence still executes actual V2 reducer;
descriptive patterns cannot authorize direction, related-event identity spans
frames, rejected future/confirmation observations retain reasons. First analysis
checkpoint60 root tests passed; one retained-family test subsequently added.

## V7 M7–M11 / setups, provenance and research protocol
Four FX family IDs retained; version2 parameters are frozen/strict/bounded, setup
IDs bind instrument/frame/closed candle, maximum age is enforced. Crypto strategy
specs and real-volume gates unchanged. Dataset manifest records exact identity,
frame hashes/counts/ranges, retrieval/timezone/license/use declarations and rule
history uncertainty. Optional non-overlapping rule epochs are selected at historical
time; open-position contract changes require an explicit settlement model and
are refused. Trust cannot be raised by a caller's verification flag. Retained V2
walk-forward now optionally purges a chronological validation segment before
selection; validation data hash joins frozen parameters. Future held-out mutations
leave frozen selection unchanged. Added bounded isolated in-memory result registry,
repeat-result consistency and Monte Carlo seed/sample warnings.65 root tests passed
before six additional operations regressions (6/6 pass). No real market edge claim.

## V7 M12–M16 / operational and contract hardening
Actual official-source research identified BLS ICS/public-domain policy, Fed RSS,
ECB/BoE/BoJ official schedules. Explicit bounded BLS fetch/parser retrieved313 events
with21 future records in the observed response (V7_BLS_PROBE.json), no fixtures.
BLS omits per-event DTSTAMP and uses US-Eastern: source publication stays explicitly
unavailable, knowledge time is first retrieval, timezone mapping is versioned.
Coverage/authenticity stay unverified. Macro revisions choose only as-of-known
records; asymmetric windows supported. Alerts retain V5 composition, add stable
setup IDs/invalidation, bounded dedup and documented process restart semantics;
concurrent same-setup evaluation emits once. Scanner partial failure isolation,
strict API inputs, V1 invalid-query422, research concurrency429, registry404 and
read-only MT5 diagnostic extensions tested. Root74/74 and retained423+152 pass at
pre-release checkpoint. Engine version7.0 retains /api/v6 and schema6 compatibility;
additional fields/endpoints are explicitly documented. Real MT5 remains UNVERIFIED.

## V7 M15–M17 / final veto and profiling audit
Independent final regression exposed a descriptive pattern with a larger heuristic
strength replacing authoritative same-event trend evidence before conflict-veto
calculation. Red test reproduced it; reducer now computes veto from all confirmed
authoritative inputs before dedup and prefers authoritative representatives.
Regression green; patterns remain neutral in V2 scoring. Scanner reports request
cache hits/misses; no persistent quote cache. Final release profiling uses3 timing
repetitions and a separate allocation run across analysis/scan/MTF/candle/chart/
confluence/replay/OOS/Monte Carlo/API. No live MT5 latency inference is made.

## V7 final temporal boundary review
Full-day and partial holiday overrides supersede yesterday's overnight schedule
(red/green regression). Historical session-gap validation uses rules effective at
that historical minute. Intrabar contract changes and pre-candle retrieval claims
are rejected; epoch coverage is explicit. Added per-family causal confirmation,
minimum-tick exclusion and price-unit scaling invariants for the11 candle extensions.
Final test totals and CI evidence are recorded in V7_DELIVERY_REPORT_TR.md.

## V7 M18 — release checkpoint

Code a108c9d:423+152+76=651 tests,0 failures/skips. Windows/Ubuntu×3.11/3.12 run42208624107 all green; each log independently checked. Local3.11/3.12 and compile passed. Unified-only coverage93.56% statements/75.27% branches. Three-repeat profiling and actual40-path schema/examples exported. Source clones/PRs and main unchanged; private draft PR retained. Comprehensive Turkish A–J delivery and explicit PARTIAL/UNVERIFIED milestones: V7_DELIVERY_REPORT_TR.md. Final documentation commit receives the same CI matrix.

## V8 M0–M12 continuation
Start f22190a, clean/pinned private feature branch, original651 tests reproduced.
1314a7f: red/green historical ATR reclassification and stale-authority evidence veto.
9d5a8e5: closed-snapshot pattern QA, bounded FVG transitions/checkpoint/rolling store.
63a3e2f: bounded read-only CSV/JSON importer, explicit Parquet refusal, dated fee/
spread assumptions, independent4→10 fee oracle, frozen code hash and cooperative
research cancellation/registry cleanup.0aa7cac: date-safe official adapters and
sanitized Windows pilot/margin calculation. a2c224f: typed financial nested schema
with V7 compatibility, as-of revision conflict, stable structure alerts, cancellation
IDs and adversarial state guards. Full handoff and actual final test/coverage/CI
results are recorded in V8_DELIVERY_REPORT_TR.md and V8_VALIDATION.json.
Latest targeted/full host checkpoint103 passes; three provider/error branches added
and pass. Vendor suite assertions were not removed or weakened. Pattern QA and
random-path diagnostics do not establish market precision/edge. BoE HTTP403 and
BoJ usage restrictions remain explicit. No protected repo/DB/order/public deployment.

V8 final concurrency audit: a red/green regression showed an older request could
read newer shared FVG transitions after another request advanced the ledger. The
ledger now refuses ahead-of-snapshot reads; independent historical replay is
required. This preserves as-of safety under out-of-order request completion.
Final code/test/coverage/profiling reruns include this guard.

Windows CI42213715258 exposed a cross-platform import path bug: Windows treats
/etc/passwd as rooted without a drive, so is_absolute alone was insufficient.
The importer now rejects POSIX roots, Windows rooted/drive/UNC paths, drive-relative
paths, alternate streams and both separator forms of traversal before resolve.
No assertion was weakened/skipped. Path variants pass locally; four-job final CI
is required again. Profiling at d6f98af predates this importer-only guard change;
measured analysis/replay algorithms are unchanged and the checkpoint is explicit.

## V8 M14 release evidence

Code a7927c1:423+152+107=682,0 fail/skip. Local3.11/3.12 passed; four-job Windows/Ubuntu×3.11/3.12 run42214034689 green with exact SHA/count log verification. Unified-only coverage95.49% statements/78.61% branches. Actual41-path schema, V7 compatibility, pattern diagnostics, new-module provenance and full Turkish A–L report exported. Benchmark d6f98af differs only in unmeasured importer path guard. Documentation commit receives the same CI matrix; PR stays draft.

## V9 recovery/data/evidence continuation
Baseline682 reproduced at d2bf026.5dd7e4b fixes live-reference checkpoint mutation
and incremental provider-source switch with red/green tests.460c03e adds paired
bid/ask side capabilities/execution and bounded descriptor/read/nesting checks.
43c24f8 adds source/PIT rule binding, pilot validation, scoped optional persistence,
local preregistration/trial accounting and separate immutable forward observations.
Fed cross-month/year parsing and coverage change monitoring retain date-only
semantics. No source/provider authentication is inferred from hashes/flags. All V8
routes retained; optional journal/persistence disabled by default. Final RC code,
coverage, actual counts/CI and gate status are documented in V9 delivery artifacts.

V9 final audit additionally makes target code identity portable with POSIX-normalized
relative paths; otherwise Windows pilot and Linux backend could disagree on identical
source bytes. Each CI job now prints SOURCE_SHA256 for cross-OS comparison. Checkpoint
restore validates historical candle QC/watermark and event sequence, scoped persistence
rejects symlink roots, and fresh historical quote time is the actual last closed-bar
time rather than an advanced replay clock. RC source is9.0.0-rc1; schema6/41 routes
remain. Gate L stays UNVERIFIED even with offline release gates green.

Windows3.12 CI42243686985 exposed CPython stat/fstat ctime disagreement on an
unchanged atomically-written checkpoint (see python/cpython#157671). Cross-path
Windows comparisons now use device/inode/size/mtime; same-handle pre/post read
comparisons still include ctime and detect mutation. Independent platform-signature
regression added, no failure skipped. Final four-job matrix rerun is mandatory.

V9 evidence checkpoint f1cf856: baseline682 preserved, final423+152+127=702,
fail0/skip0. CI42244153003 four jobs passed with identical portable source hash.
Coverage unified-only statement95.8107%, branch76.2183%; lower branch percentage
and missing-branch detail disclosed. Full benchmark source57b0927, affected local
import remeasured at f1cf856; row identities explicit. V9 generated41-path/schema6
contract and A–N report/gates/handoffs published to the private draft branch.
Gate A–K are scoped offline assertions; incomplete family validation remains
PARTIAL/EXPERIMENTAL and Gate L UNVERIFIED. No order/main merge/public deployment.
