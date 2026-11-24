# Premium Android — FINAL verified handoff (2026-11-03)

This supersedes pending-build statements below. Android DraftPR14:
https://github.com/FatihBirgul/trade-ai-android/pull/14 , branch
`codex/android-premium-health-brand`, exact source `4be11a66e3f45e0a119db3647d5c7ce40c3f58e0`.
Backend docs-only DraftPR16 https://github.com/FatihBirgul/trade-ai/pull/16 , branch
`codex/v2-premium-experience-handoff`; enclosing documentation HEAD is final.
Backend runtime remains PR15/4e5bb9bb3b5079bc7a8201a7b16b202ff6db8249.
Gateway unchanged PR9/d1c0e4d2263626a30e81af9e2b40d5e952cb7b76; no companion change needed.
All Drafts remain open/unmerged; old branches/APKs preserved, no main or force push.

IMPLEMENTED: real supported-catalogue search/filter/favorites with account-owned
recent-analysis labels; existing named profile/strategy/MTF/interval editor retained;
explicit passive save vs activation/pause retained; observation-based10-state health,
source freshness and approximate failure/recovery labels; page-local opportunity
filters/latest-ID dedup and TTL-age warnings without rewriting lifecycle history;
Turkish navigation title and geometric silver/gold T home/settings/adaptive branding.
One config/account and existing caps remain. No new API, execution grant, worker-
start endpoint, app-open mutation, provider, automatic sender or financial formula.

Verified on final Android source:213 Jest/47 suites, TS/lint,17 local Expo checks,
Android JS export and10 Python APK/brand tooling tests. Frontend CI:
https://github.com/FatihBirgul/trade-ai-android/actions/runs/41586572598 .
Native CI: https://github.com/FatihBirgul/trade-ai-android/actions/runs/41586565749 .
Backend official offline runner567 passed with ResourceWarning-as-error; separate
pytest V2 glob569 passed (different collection), quote/outcome11 passed. Gateway60
passed with real Backend fixture modules; standalone44 passed/16 explicitly skipped.
No skipped tests counted as passes. Prior exact Backend runtime Windows/Ubuntu ×
Python3.11/3.12 matrix41545746693 remains applicable to unchanged code; no claim that
new Android UI ran on Windows or a phone. Online Expo Doctor not executed.

Final clean-source compiled client→certificate-verified loopback HTTPS→production
Gateway→Backend ASGI:16 scenarios/100 requests PASS. Pins: Backend7b99f729343e1144da3c1c03c36cf567a8f28e86
(documentation-only successor to tested runtime), Android4be11a66e3f45e0a119db3647d5c7ce40c3f58e0,
Gatewayd1c0e4d2263626a30e81af9e2b40d5e952cb7b76. Two independent audit checkpoints:
PASS25184 each, mismatch/corrupt/error/incomplete0; automatic/mobile orders0.
Only fixture administrator seeds two isolated orders. No user database or service.
Repro from common parent:
`python trade-ai/backend/scripts/release_candidate_e2e.py --android trade-ai-android --gateway trade-ai-gateway --output /tmp/premium.json`.
UI browser smoke at390x844, both themes: no page exceptions, no non-loopback requests,
UNKNOWN in demo and unsupported activation absent. This is web/render testing,
not installed native/device acceptance. React tests cover authorized live UI paths.

Actual APK: internal0.7.6/code15, packagecom.fatihbirgul.tradeai,
arm64-v8a, minSDK24/targetSDK36, embedded JS/fonts/ZIP CRC verified.
SHA256 `7eab5e92c95969f7a10d4deca2dd6a20597f5ba59c57f010adac096f156bd4d1`.
V2 signature independently verified in CI; actual certificate matches prior actual
0.7.5/code14 APK: `fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c`.
Actual compiled launcher AND round/adaptive XML references foreground/background/
monochrome IDs. Packaged raster layers independently resolved and compared to approved
source PNGs (opaque alpha>=128 IoU>0.99; RGBA mean absolute error<5/255, all densities).
At432px native silhouette IoU1.0. Sources fit313px radius safe circle (max305.235px).
This proves source/native packaging, not physical launcher rendering or update safety.
Artifact (GitHub access required): https://github.com/FatihBirgul/trade-ai-android/actions/runs/41586565749/artifacts/13209320440
Expiry `2026-11-10T06:08:34Z`; seven-day retention, no permanent APK promise.
Internal debug signing retained, not a production signing key or deployment.

Contract unchanged40paths/58schemas; all3 OpenAPI copies equal SHA256
729f422ae44c146a71b4bcd75f2f1df1c68ad07dddd9e9ed50619a80fa8f24eb.
Native build supersedes cancelled2054383 build; source4be11a6 is the verified APK.

Limits / NEXT: npm audit46 findings (1low/42moderate/3high; @expo/cli,node-forge,zod).
Dependency graph unchanged; only app version changed in package-lock. No automated
fix or exploitability/build-vs-runtime assessment claimed. Prioritize a bounded
advisory/reachability and Expo-compatible upgrade review with repeated APK checks.
Then separately authorized physical small-screen/light-dark, launcher mask,
installation/session/SecureStore continuity smoke test. Never uninstall/wipe data.
Original concept6 image absent: T is a vector interpretation of its textual brief.
OFFLINE/Gateway failure need explicit trusted evidence; generic NETWORK staysUNKNOWN.
No phone network sensor, external monitor, real provider/push, Windows autostart,
private PC/runtime access or deployment: UNVERIFIED/NOT_ACTIVATED. Host process must
be independently operator-started; mobile account activation does not start it or
expand AUTO. Profile revisions remain frozen. Protected backups unchanged.

# Premium Android / scanner health handoff — 2026-11-03

Read before historical notes. This is a bounded Android product continuation;
Backend/Gateway API, financial records and worker execution semantics are unchanged.

Sources: Backend tested code PR15 `4e5bb9bb3b5079bc7a8201a7b16b202ff6db8249`;
Gateway PR9 `d1c0e4d2263626a30e81af9e2b40d5e952cb7b76`;
Android new branch `codex/android-premium-health-brand`, code
`4be11a66e3f45e0a119db3647d5c7ce40c3f58e0` based on PR13/d3a2e9d.
Draft https://github.com/FatihBirgul/trade-ai-android/pull/14 .
Backend docs Draft https://github.com/FatihBirgul/trade-ai/pull/16 .
Backend new branch `codex/v2-premium-experience-handoff` contains handoff only.
Query the branches' Draft PRs for exact final documentation SHAs and CI/artifact.

IMPLEMENTED: supported-catalogue search/filter/favorites, current-account last20
saved-analysis labels, opportunity page filters/newest-ID dedup, timed stale/TTL
warnings without changing immutable lifecycle events. Existing profile name,
strategy revision/MTF roles, bounded interval and passive save/explicit activation
remain intact. No worker-start endpoint or app-open configuration/tick write.

IMPLEMENTED: evidence-based10-state health classification, last verified connection,
last service observation, provider scan freshness, planned next_due (not guaranteed
execution), account enablement and backlog. Fresh configuration GET cannot refresh
old provider evidence. Generic network failure stays UNKNOWN; OFFLINE requires an
explicit trusted network observation and Gateway-unavailable an explicit diagnosis.
No phone sensor/external monitor installed. Approximate failure duration is scoped
to this screen/account/session, with a30sec display clock; not true outage duration.
No polling/network write is performed by that clock. Existing401/403/capability
fail-closed and lost-ACK replay retained. One current scan config/account remains.

IMPLEMENTED: reviewed silver/gold geometric T SVG +1024 PNG full/adaptive foreground,
background and monochrome layers, manifest hashes, home/settings BrandMark, source/
native/APK graph verification. Original concept6 image unavailable; vector design
interprets the supplied description. Internal0.7.6/code15; package and signing policy
unchanged. Prior0.7.5/14 and earlier APK artifacts were not overwritten.

Local executed:213 Jest/47 suites, TS, ESLint,17 local Expo compatibility checks,
Android JS export,10 Python APK/brand-tool tests; disposable native prebuild and
actual generated WebP alpha silhouette matchIoU1.0. Online Expo Doctor not executed.
Clean checkpoint2054383 HTTPS acceptance passed16 scenarios/100 requests with
two independent PASS25184 audits, no mismatch/corrupt/error/incomplete, no automatic
orders. Turkish route title subsequently corrected to Tarayıcı ve Fırsatlar;213
tests re-passed, exported web UI checked at390x844 in both themes without page
errors or non-loopback traffic. Final source HTTPS/native evidence remains pending
at this checkpoint; final evidence will be appended after execution.

OpenAPI unchanged40paths/58schemas, all active copies SHA256:
729f422ae44c146a71b4bcd75f2f1df1c68ad07dddd9e9ed50619a80fa8f24eb.
No Gateway source changes/new PR required. Backend documentation only; baseline
567 V2/11 quote and four-environment CI were independently verified on PR15.

Next safe operation: clean-source production-module fixture harness:
`python trade-ai/backend/scripts/release_candidate_e2e.py --android trade-ai-android --gateway trade-ai-gateway --output /tmp/premium-e2e.json`.
Then verify the new native APK exact source/hash/manifest/certificate against actual
previous0.7.5, embedded JS/fonts and compiled adaptive resources; check exact SHA CI.
Physical install/update, small-screen/dark-light phone review, real provider/push,
Windows autostart and production remain UNVERIFIED. No PC, phone, user database,
private network, running service, production setting, AUTO grant or protected backup
was accessed/changed. No main writes, merges, rebase or force push.

# Scanner profile / activation follow-up — 2026-11-02

Read this before older Continuation9 notes. Current task completes its documented
profile/timeframe editor gap, without PC/device/service access or deployment.

- Backend branch `codex/v2-scanner-activation`, base PR14/137c0844de4f9246ba488c899aaea481707cceaa.
  Code checkpoint03a4feaaf8453a0c54dc42f9c8931ae57cbe4687; enclosing handoff commit is
  the final source. Query `gh pr list --head codex/v2-scanner-activation --repo FatihBirgul/trade-ai` for its new dependent Draft PR and exact final HEAD.
- Gateway `codex/gateway-scanner-activation`, Draft https://github.com/FatihBirgul/trade-ai-gateway/pull/9
  d1c0e4d2263626a30e81af9e2b40d5e952cb7b76; base PR8/18d8e9b.
- Android `codex/android-scanner-activation`, Draft https://github.com/FatihBirgul/trade-ai-android/pull/13
  d3a2e9ddccef7fe507dc43977147897a08c14ff7; base PR12/dce8b22.
  Internal0.7.5/code14, same package/signing policy. Historical0.7.2/11, RC8 and
 0.7.4/code13 branches/artifacts were not overwritten or deployed.
- OpenAPI40paths/58schemas, optional name/runtime_mode only, active copies equal:
 729f422ae44c146a71b4bcd75f2f1df1c68ad07dddd9e9ed50619a80fa8f24eb.

IMPLEMENTED: named current scan configuration/account, favorites, bounded interval,
passive save/update, disable, single timeframe or frozen strategy-profile MTF roles,
link to existing strategy editor. Modes off/selected_profile/supported_markets.
No new parallel scheduler, formula or financial authority. New explicit-mode
activation checks a current operator-started host lease/heartbeat, profile/scope
prerequisites; config save and app startup never start a worker. No mobile process-
start endpoint. Legacy null-mode API/receipts retain compatibility. A single active
scan configuration/account remains the intended architecture, not arbitrary many
simultaneous scan profiles. Profile history is preserved; disable instead of delete.

Connection UI distinguishes offline/unverified, partial Backend/worker connection,
connected but unauthorized and ready-for-explicit-activation. 403 preserves session;
network failure does not establish phone-internet failure or worker shutdown.
Missing capability or invalid runtime observation blocks activation. Explicit retry
and settings actions; no optimistic success or automatic tick. Save remains passive;
activation/pause use saved fields, and uncertain writes replay the exact original key.

Evidence: SCANNER_ACTIVATION_ACCEPTANCE.json,16 scenarios/100 real HTTPS requests
from clean committed sources. Keeps all15 prior scenarios; actual compiled Android
client→certificate-verified loopback HTTPS→production Gateway→Backend ASGI with
controlled fixture inputs. New scenario covers named/frozen MTF save, blocked host-
absent activation, explicit test-operator runtime start, account activation replay,
stop/pause and no automatic revision replacement. Two audits each PASS25184,
corrupt/error/mismatch/incomplete0, mobile/automatic orders0. The original harness
administrator seeds only two isolated fixture orders; no user DB is read or changed.

Local validation: Backend566/566 passed before the final legacy-edit regression;
37 targeted discovery/activation tests pass, final567 rerun is being checked.
Android190/44 suites, TS/lint (no local warnings), doctor17, JS export and6 APK-tool
unit tests pass. Gateway60 actual local integrated; standalone44pass/16 private-
Backend skips. Gateway CI41544797288 successful. Final Backend matrix and Android
CI/APK completion are to be checked on the exact final sources; final PR bodies/checks
record their completion rather than assuming success at this documentation commit.

Actual state bug fixed: a second stop() on an already stopped worker set
worker_stopping=true permanently. A red test reproduced it; stop is now idempotent
and truthful. During new UI development, pause also initially copied unsaved notice
flags; the negative test failed and the corrected pause uses saved flags only.
A final red regression also showed an old client omitting new fields could erase
the new name/mode and bypass its activation gate. Omitted metadata now preserves
the existing explicit policy; legacy receipts/configs still retain compatibility.
These are runtime/UI/control issues; no ledger/risk calculation was changed.

APK: workflow41544588109 source d3a2e9d, running at document construction:
https://github.com/FatihBirgul/trade-ai-android/actions/runs/41544588109 . Verify actual
artifact, manifest, V2 cert, bundle/fonts/hash before claiming native delivery. Final
actual evidence will be in AndroidPR13. Prior actual0.7.4 certificate SHA256:
fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c.
Physical installation/update, SecureStore continuity, live provider, push and Windows
autostart remain UNVERIFIED; none activated. No signing key or production setting change.

Safe repro from common parent: `python trade-ai/backend/scripts/release_candidate_e2e.py --android trade-ai-android --gateway trade-ai-gateway --output /tmp/activation.json`.
Targeted isolated worker lifecycle: from Backend `python -m pytest -c tests/pytest-v2.ini tests/test_v2_scanner_activation.py tests/test_v2_discovery.py -q`.
The host CLI --discovery is still an explicit operator choice; do not run it against
user data or install a Windows service without later authorization. Account config
and discovery:write grant are separate gates; activating scanning never grants AUTO.

Remaining: first20 strategy records plus exact bound revision (no unbounded picker),
one active scan config/account; full multi-profile scheduling is outside this task.
Existing finite provider/read/job/event limits remain; no destructive retention or
financial history change. Real provider throughput/push/Windows/device validation
cannot be inferred from fixtures or an APK. Protected AGENTS backups untouched.

Next safe prompt: verify these Drafts and exact CI/artifact evidence; add cold-start
read-only reconciliation for uncertain scanner activation/pause commands, with scoped
storage and explicit retry only. Then bounded outage/restart acceptance using these
modes. Physical rollout/push/Windows startup require separate authorization. No main
merge, force push, deployment or private PC/network operation occurred.

---

# Continuation 9 — bounded autonomous opportunity discovery (2026-11-02)

Preserve RC8 0.7.3/code12 and its three source branches unchanged. No deployment,
main write, merge, private-PC operation, financial grant or real push activation.

## Sources and dependent Draft PRs

- Backend `codex/v2-opportunity-discovery`, https://github.com/FatihBirgul/trade-ai/pull/14
  from RC8 `195af2ee62bf77083e1bcb12bec9a8511bba475d`; implemented source/test checkpoint
  `7e2bc4e54dc07c70aeeb8e69a9b8ab37b5e3a638`. Enclosing handoff commit is the
  final HEAD: retrieve PR14 headRefOid rather than infer a self-referential hash.
- Gateway `codex/gateway-opportunity-discovery`, https://github.com/FatihBirgul/trade-ai-gateway/pull/8
  exact `18d8e9b125276954f78b1606caa13ce774f85fb3`, base RC8 PR7/e63ac56.
- Android `codex/android-opportunity-discovery`, https://github.com/FatihBirgul/trade-ai-android/pull/12
  exact `dce8b22028e730a342c1d89a1c8d4a2c761daf20`, base RC8 PR11/761bec0.
  Internal 0.7.4/code13, same package. Old APK/branch not replaced.
- Additive shared OpenAPI **40 paths/58 schemas**, SHA256
  `651a4315646dda90fe6569528767df7e719485ae35ff74a81c3a8ed71ecab28c`.
  Existing endpoints/requests remain unchanged. Incorporate companions together
  only after human stack review; do not automatically merge any PR.

## IMPLEMENTED within explicit bounds

Account-owned favorites + supported-spot discovery use the same AnalysisService;
legacy watchlist/quota untouched. Universe only BTC/ETH/SOL USDT spot, with actual
provider rules, source/venue/volume/finality/continuity checks. Discovery screen:
positive real volume and closed price change at least a verified tick. No spread/
liquidity feed is available, so those filters are not claimed. Favorites priority,
rotation, bounded persistent queue, per-symbol failure isolation, durable account
schedule, missed scans, fenced lease, restart/retry and clock-rollback safeguards.
Worker starts only explicitly; import/HTTP configuration never starts one.

Opportunity version1: EARLY=closed reclaim, existing failed-breakout follow-through
still missing; CONFIRMED=existing selected strategy + restrictive profile + MTF +
risk gates. Always trade_permission=false. Fresh condition loss INVALIDATED;
provider/source failure UNAVAILABLE; explicit TTL EXPIRED. Same-source retries and
both modes share one opportunity; provenance records both without duplicate alerts.
first_known_ms is actual evaluation; first_source_ms is closed source time.
Immutable event chain and saved analysis/source references support traceability;
checksum chains are not signatures or trusted external anchors. Opt-in lifecycle
outbox flags default false, and existing owned-recipient/category delivery controls
remain necessary. Nothing is DELIVERED and no sender/device registration is enabled.

Gateway exposes account reads and an independent explicit `discovery:write` grant.
Old scanner/paper/profile grants do not imply it; no paper grant is added. Turkish
Android screen supports favorites, discovery, pause/configuration, interval selection,
notification flags, actual worker/source health, bounded opportunity pages and saved
evidence/analysis links. Old Gateways show unavailable, without fabricated results.

## Executed evidence

`DISCOVERY_ACCEPTANCE.json`: **15 integrated scenarios /87 actual HTTPS requests**
from clean committed checkouts, retaining all13 RC8 scenarios. Real compiled Android
API/session/renewal → certificate-verified loopback HTTPS → production Gateway →
production Backend ASGI → explicitly controlled fixture provider. Explicit fixture
worker runs independently of client polling, then stops; reads/restart/outage/recovery
and configuration lost-ACK replay are checked. Two independent financial audits each
PASS25128, mismatch/corrupt/error/incomplete0. No automatic orders; the unchanged
RC8 accounting fixture administrator seeds only two isolated test orders.

Backend targeted28 new tests, including a genuine causal OHLC EARLY→CONFIRMED
through the real engine (no mocked classifier), actual range invalidation, expiry,
rollback, chain tampering, overlapping lease, source outage, old candle, concurrent
configuration, stopped-worker recovery and non-blocking health during slow fetch.
Full local suite at preceding checkpoint:557 PASS; final558 rerun is in progress at
handoff construction. The final PR checks/body records exact final completion.
An existing follow test failed once (zero alerts at a real minute expiry boundary);
its factory still uses real modules/worker, now with the fixture clock and unchanged
behavioural assertions. Do not treat the failed run as green.
Android178/43 suites, TS/lint, local Expo doctor17, Android JS export, six APK parser
tests passed. Gateway59 actual local integrations; standalone44PASS/15 private-
Backend skips. Skips are not successes. Gateway final CI41502461575 successful;
Android frontend CI41501998584 successful. Final Backend four-environment CI is
still in progress when this document is committed; verify exact final SHA in PR14.

Capacity rehearsal: four deterministic fixture cycles, eight full analyses,
mean1.2251s/max1.2735s with tracemalloc, peak2,686,079bytes, DB1,687,552bytes;
independent financial audit PASS432 and both account event chains PASS. This is
controlled-fixture cost, not live provider capacity. See JSON for measured conditions.

The new worker's stop guard was also regression-tested with a provider call still
blocked after the2s join deadline: before the fix a later manual tick stayed
superseded forever. Worker-finally now releases the guard only after its in-flight
tick exits; the negative test failed before and all28 targeted tests pass after.
These were defects found during development of the new scanner, not claims of
previous production ledger defects. No financial/risk formula was changed.

## Runtime safeguards and reproducible commands

From common parent, clean sources and installed dependencies:
`python trade-ai/backend/scripts/release_candidate_e2e.py --android trade-ai-android --gateway trade-ai-gateway --output /tmp/c9-acceptance.json`

Disposable fixture rehearsal, no user DB or service:
`python trade-ai/backend/scripts/soak_v2_discovery.py --cycles 4 --output /tmp/c9-capacity.json`

Explicit standalone worker flag is `backend/start_v2.py --discovery`; account config
must also be enabled. It binds existing loopback only and stops on normal process
shutdown. Tests call runtime.discovery.start()/stop() only on temporary fixtures.
Do not run against the user's Windows DB or install startup services without later
approval. Stop joins for2s; an outstanding bounded provider call may finish later,
and fencing prevents late state commits. No public listener or transport is started.

Limits:2 deep analyses/tick globally;3 eligible symbols/account;12 logical provider
reads/cycle;24/minute; checked30s cycle deadline. Provider's existing HTTP timeout
still applies (Binance can try two8s hosts); no hard thread pre-emption guarantee.
Intervals60–3600s, TTL300–86400s. Limits/account:256 revisions/opportunities,
10000 jobs/events. Exhaustion blocks new work; no deletion/compaction/backfill.
Paused accounts retain history; reads flag stale TTL/source records, and persisted
expiry transitions occur on a later enabled due tick. Work can wait until the next
configured interval; no catch-up storm or retroactive historical opportunity.

## PARTIAL / UNAVAILABLE / UNVERIFIED and next safe milestone

- Android currently preserves/displays a frozen profile revision and timeframe;
  new profile/timeframe binding is available through the validated Backend API.
  A dedicated profile/timeframe editor on this new screen remains PARTIAL; legacy
  strategy selector is preserved. Opportunity detail events are bounded to latest50.
- Fine-grained authenticated liquidity/spread ranking, larger provider catalogues,
  archive rollover beyond hard caps and signed external event anchoring are missing.
- Only the named three spot instruments, not Forex/XAU/futures/global discovery.
- Real market discovery quality/throughput, profitable strategy performance,
  physical phone/update, SecureStore and real notification delivery UNVERIFIED.
- No Windows unattended service, BIOS/Tailscale or external monitor was configured.
- Native APK workflow41501771525 source dce8b22 is running at document construction.
  Link: https://github.com/FatihBirgul/trade-ai-android/actions/runs/41501771525
  Do not assume APK/signature success. Final actual artifact/hash/certificate/bundle/
  expiry is recorded in AndroidPR12 after independent verification. Prior actual
  RC8 certificate DER SHA256 fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c.
- Next: inspect final PR14/8/12 checks and artifact evidence; rehearse authorization,
  prolonged provider outage and history-cap exhaustion before any deployment plan.
  Then complete the bounded profile/timeframe editor without automatic revision
  updates. Real push and Windows unattended startup each require separate approval.
- First continuation command: `gh pr view 14 --repo FatihBirgul/trade-ai --json headRefOid,statusCheckRollup`.
  Read this section and the frontend contract before coding. Keep protected AGENTS
  backups and the RC8 branches/artifact untouched. All worktrees clean at checkpoints.

---

# Continuation 8 — internal release candidate handoff (2026-11-02)

Priority changed to integration/release reliability, **not feature expansion**.
Read [RELEASE_CANDIDATE.md](RELEASE_CANDIDATE.md),
[RC8_ACCEPTANCE.json](RC8_ACCEPTANCE.json), and
[RC8_DEPENDENCIES.json](RC8_DEPENDENCIES.json) before new work.

## Exact candidate

- Backend branch`codex/v2-release-candidate`, Draft
  https://github.com/FatihBirgul/trade-ai/pull/13 ; basePR12
  33e4ef5f1f9830648f414f0554c638edd0addffb; code checkpoint
  **8280ea82c447be1921309a3f01b608f4a9e9f9ca**. Enclosing evidence/docs commit is
  the final published Backend HEAD; retrieve PR13 headRefOid rather than infer it.
- Android`codex/android-release-candidate`, Draft
  https://github.com/FatihBirgul/trade-ai-android/pull/11 ; basePR10 ca0f901;
  exact source **761bec051de2d61ca234e48b4f86b12079fbdb46**,
  **0.7.3 / versionCode12**, same packagecom.fatihbirgul.tradeai.
- Gateway`codex/gateway-release-candidate`, Draft
  https://github.com/FatihBirgul/trade-ai-gateway/pull/7 ; basePR6 b75cb79;
  exact source **e63ac56cd0dbe7139624766b0a8f289b852c712c**.
- Active OpenAPI unchanged36paths/51schemas, all3 copies SHA256
  **676a3558503dcbdab7535bfdfa5e89f5f8c355a058e09d52067a62a674d128c2**.

## Actual integration evidence

Clean committed checkouts:13 scenarios,74 real certificate-verified HTTPS requests,
actual compiled Android API/session/renewal modules→loopback Gateway→Backend ASGI.
Two independent accounting audits each PASS24996, mismatch/corrupt/error/incomplete0.
Fixture administrator seeds two test orders and201 actual ledger events; mobile
paper grants and automatic orders remainzero. Provider clearlyRC_CONTROLLED_FIXTURE,
not real data; Backend clock starts current UTC minute to preserve real session
expiry semantics. No public listener, sender, background follow worker or private PC.

Covers markets, saved closed snapshots, research/anchors/parameters, profile
create/revise/bind/frozen follow revision, account scopes, scanner reads/manualtick,
source outage/recovery/dedup/pending outbox, paper/history/cursor pages, restart,
renewal lost ACK/replay/revocation,401/403, malformed reply, actual15s timeout and
actual Gateway shutdown. Read the scorecard for fault-injection and native limits.

Real blocker fixed: older Backend research/profile route404 was labelled generic
Backend outage. Red real-client HTTPS and Gateway tests reproduced it; Gateway
maps capability absence to BACKEND_UPDATE_REQUIRED while real PROFILE_NOT_FOUND/
403 remain distinct. No financial/risk/schema change.

Reproduce from common parent, all3 **clean** checkouts with dependencies/Node/
OpenSSL installed:
`python trade-ai/backend/scripts/release_candidate_e2e.py --android trade-ai-android --gateway trade-ai-gateway --output /tmp/rc8-acceptance.json`
Dirty sources returnPARTIAL_DIRTY_INPUTS/exit1. The market path is deterministic;
actual UTC session/UUID values and report hashes are not claimed identical across runs.

## Component tests and artifact evidence

- Backend baseline/full source runtime530 V2,11 quote/outcome, compile.
- Android172 Jest/42suites, TS/lint, local doctor17, JS export,6 APK parser tests.
- Gateway55 tests in integrated checkout:41 standalone plus14 private-Backend-
  dependent tests actually executed. Standalone41pass/14skip; skips not successes.
- Final exact-HEAD CI completion is recorded in the three PR bodies/checks.
  At handoff commit creation the final runs are in progress; no baseline success
  is substituted for final-HEAD success. Full-stack private3-checkout CI is not
  provisioned; the actual Cloud HTTPS report is a separate gate.
- Candidate APK workflow https://github.com/FatihBirgul/trade-ai-android/actions/runs/41490345414
  source761bec0, version0.7.3/code12. Build/metadata verification pending at this
  documentation commit. Final actual artifact/hash/certificate/bundle/expiry is
  permanently recorded in AndroidPR11 body and the artifact evidence JSON.
  Previous actual APK sourceca0f901, SHA256
  1b74b2a1772b42ba20aa812c887e9ca250b3e41a3c78a60a927b083700bb4bb5,
  actual V2 DER certSHA256fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c.

## Readiness and exact next action

- Code/client transport acceptancePASS; physical/native UI/runtime/SecureStore
  UNVERIFIED; production deploymentPARTIAL/not executed; real market evidence
  INSUFFICIENT_EVIDENCE; real pushBLOCKED. Do not invent a completion percentage.
- Existing stacks: BackendPR1..12 plus13 (roottrade-ai-v2, notmain), AndroidPR1..10
  plus11, GatewayPR1..6 plus7. All ancestry edges linear; main ancestors, no identical
  patch groups. Exact base SHAs and107/57/16 nonmerge-commit ranges are in JSON.
  No merges, retargeting, force push, main writes or production changes performed.
- Human-approved integration must preserve ancestry and rerun conflicts/contracts;
  Backend V2→main bridge needs explicit separate review. Do not cherry-pick all
  parent commits into a tip that already contains them. No destructive DB rollback.
- Follow the Windows copy-backup/version pin/start order/checklist in the release
  report only when the user is present and authorizes local action. This Cloud
  task executed none of those Windows deployment commands.
- **Next user action:** first review final artifact/certificate and installed app
  metadata, then authorize a normal non-destructive device install/update and the
  physical smoke matrix. Never uninstall or clear data. If the user remains away,
  preserve this frozen candidate; do not resume indicator/strategy expansion.

---

# Continuation 7 — safe handoff (2026-11-02)

Latest request: **MASTER DEVELOPMENT CONTINUATION 7**. Continue V2; do not
restart older tasks or regenerate the features below. Verified clean bases:

- BackendPR11/source9fe7a3aba800cfbfdd7bee2e99b830df3e3f2ed5.
  New branch`codex/v2-immutable-research-anchor`, dependent Draft
  https://github.com/FatihBirgul/trade-ai/pull/12 . Last **code** SHA
  `af4f78c4df72c3dba9775ca55ff69a5a397089a7`; enclosing handoff/docs commit is
  the final published branch HEAD (read headRefOid, do not infer its SHA).
- AndroidPR9/base776d21f0065a07384aea9ecd0e570345ae57d555.
  New branch`codex/android-snapshot-research`, Draft
  https://github.com/FatihBirgul/trade-ai-android/pull/10 . Exact app/APK source
  **ca0f9018ffbad83bd7d375b91001e13e83e89609**.
- GatewayPR5/basefca040c1a276e301c6a3c2eac97c77ce3a1efb35.
  New branch`codex/gateway-snapshot-research`, Draft
  https://github.com/FatihBirgul/trade-ai-gateway/pull/6 . Exact source
  **b75cb790bbb712a542a63085681c27036f057b3b**.

## Implemented — preserve

1. Frozen IndicatorParameters: strict whitelist/type/period and decimal-multiplier
   bounds, implementation/strategy version binding, declared warmup, closed-data
   quality, input/parameter/config IDs and fixed Decimal context for research
   arithmetic. EMA/SMA/RSI/MACD/ATR-SMA/Bollinger reuse legacy pandas definitions;
   ADX/Supertrend use existing research Wilder seeding; never claim all indicators
   use Wilder or full TA-Lib equivalence. No mutable global/default strategy change.
2. Optional IndicatorCandidate walk-forward subtype preserves legacy candidate
   serialization/protocol identity. Training-only scoring, immutable winner/test
   parameters, held-out isolation, registry cache and overlap denial. Restrictive
   parameter filter can only narrow an existing allowed route; cannot reviveWAIT.
   CLI`backend/scripts/walk_forward_v2.py DATASET.json --parameter-candidates
   PROTOCOL.json --train-bars 303 --test-bars 3 --horizon 1 --purge 1 --max-folds 1
   --paper`. Protocol<=16KiB,
   schema_version1, implementation_version`v2-indicator-parameters-1`, exact
   strategy_versions/dataset_digest/source and1..4 candidates. Candidate fields:
   candidate_id,parameters, optional strategy_ids/analysis_every_bars. Rejected
   duplicate JSON keys, source/version mismatch, unknown settings and bool periods.
   Costs remain explicit frozen CLI/protocol assumptions, not historical evidence.
3. GET/POST`/api/v2/analyses/{analysis_id}/research`: no provider fetch or financial
   writes; SQLite mode=ro/query_only/deferred consistent read. Saved decision hash,
   symbol/account/frame/as-of/strategy version, closed continuity and actual volume
   required. Explicit anchor is an actual source open timestamp with>=2 closed
   candles from anchor. Same existing typical-price VWAP math reused independently
   of UTC-day prefix. Catalogue<=300 eligible anchors; calculation source<=1024.
   Bias research needs a separately saved higher frame; no invented resampling.
4. Android research-only anchor navigation and13 period editors. Final client
   hardeningca0f901 rejects invalid UTC dates, reversed/duplicate anchors and>300
   anchors before rendering. New negative oracle failed on0555b6a and passes now;
   this was a new-interface defect, not an old financial-engine defect. Shows real source,
   UTC time, fixture label when applicable, availability/reasons and IDs. Selection
   changes clear old results; account/source validation and old Gateway capability
   gate retained. Themes and existing immutable chart/WAIT levels unchanged.
5. Actual fixture matrix for all11 V1 structural family names (not mocks), plus
   negative/insufficient/gap/unfinished/no-volume/first-knowledge/prefix cases.
   Found inverted legacy Falling Wedge slope ordering: fixed only in V2 research
   adapter, version`v2-falling-wedge-convergence-1`; upper falls faster than lower.
   V1/live detector untouched. Existing narrow lifecycle tests retained.
6. Read-only exact archive-copy readiness:
   `python backend/scripts/archive_readiness_v2.py --expected REVIEWED.json
   COPY1.sqlite COPY2.sqlite` uses<=8 explicit existing copies and independent
   financial audit. Same logical manifest/account sequence/hash/domain cutoff;
   missing part=>INCOMPLETE, different cutoff=>MISMATCH, corrupt=>CORRUPT, truncated
   SQLite=>ERROR. No paths/tokens in ordinary result. Disposable fixture restore
   rehearsal only; never merges, repairs, deletes or restores user history.

## Executed validation and CI identity

- Final local Backend **530/530 V2 (130.563s)** +11 quote/outcome; compile passed.
  New27 methods vs503 baseline; imported TestCase duplication was avoided.
  Extra saved4H-bias assertion was then targeted7/7; full suite count unchanged.
- Gateway **53/53 actual local ASGI** against sibling Backend; standalone
  **40 passed/13 skipped** (private Backend checkout absent). Skips are not passes.
- Android **172/172 Jest,42suites**, TS/lint/local doctor17 compatibility checks,
  Android JS export,6 Python APK verification-tool tests. Full online Expo Doctor
  not executed; no physical-device validation.
- OpenAPI **36paths/51schemas**, all3 active copies SHA256
  **676a3558503dcbdab7535bfdfa5e89f5f8c355a058e09d52067a62a674d128c2**.
  Every previous35path/47schema definition is semantically identical.
- Exact code CI: https://github.com/FatihBirgul/trade-ai/actions/runs/41470856587
  (af4f78c; Ubuntu3.11/3.12 already succeeded at handoff creation; Windows pending).
  Final published HEAD checks: https://github.com/FatihBirgul/trade-ai/pull/12/checks .
  Gateway source CI41469896631 succeeded; final Android source CI41472874946 /
  41472886035 and APK41472875138 are checked separately from initial0555b6a checks.
  Final completion is verified in PR bodies/checks; do not infer later SHA success
  from an earlier run. Expected injected SQLite-error logs are not hidden.
- New APK run https://github.com/FatihBirgul/trade-ai-android/actions/runs/41472875138
  sourceca0f901, internal0.7.2/code11/packagecom.fatihbirgul.tradeai. Build and actual
  artifact metadata verification were pending when this handoff was committed.
  Earlier0555b6a APK run41469755756 was superseded/cancelled by this final source.
  Read AndroidPR10 body for final artifact ID, expiry, hash, certificate and bundle
  evidence. No install/update safety claim before actual certificate comparison;
  installed-device update alwaysUNVERIFIED. Previous actual APK source776d21f,
  SHA2565fd5dbc3fd84ab8333b4360d5b2fd93b549584b428565718993520a95c40133c,
  V2 DER certSHA256fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c.

## Partial / missing / unavailable

- Parameter/anchor output is deterministic and content-addressed, but no persistent
  product research-result/history store or general live optimization. Android edits
  periods only; multiplier/MTF/anchor-on-chart gesture UI remainsPARTIAL. No route,
  risk, privilege, worker or AUTO-paper activation. None of this proves profitability.
- Full structural lifecycle metadata for generic V1 families remainsPARTIAL;
  existing boundary/neckline variants are narrow geometry, not universal taxonomy.
  No claim of full fixture coverage for every lifecycle/volume concept in every
  generic family. No TA-Lib conformance or new confluence/trade activation.
- Historical licensed/authenticated source/rule/fee evidence remains incomplete;
  no new public historical download or forward test. INSUFFICIENT_EVIDENCE retained.
- Archive readiness covers exact logical copies only, not discovery/split segments,
  continuous cross-file atomicity, trusted external signature/anchor or real restore.
- Real push provider/device credentials, delivery, physical phone and private PC
  testsUNAVAILABLE/UNVERIFIED. No production changes, deployment, secrets or sender.
- Scanner/follow/recovery controls preserved; no additional lifecycle changes in
  this continuation. Do not rebuild notification/profile/archive prior milestones.

## Exact next safe priority

First verify the three Draft HEADs/checks and AndroidPR10 artifact evidence.
Then strengthen **source/version-bound immutable product research history** (read
scope/account isolation, bounded persistence separate from financial journal), and
add explicit multiplier/MTF UI only through the same frozen source contract. If
focusing on research quality, extend actual neckline/failure/retest fixtures and
report formation-start limits honestly. No new automatic execution permissions.
For archive follow-up, design explicitly declared split-part manifests with trusted
cutoff evidence before any archive discovery/merge concept; never merge user files.

First local commands: `git status --short`, `gh pr view 12 --repo
FatihBirgul/trade-ai --json headRefOid,statusCheckRollup`; read this section, then targeted tests for the selected gap. All mutations
remain in new temporary fixtures, no protected AGENTS backups touched.

---

# Continuation 6 — current safe handoff (2026-11-01)

Backend: `FatihBirgul/trade-ai`, branch `codex/trade-ai-v2-notification-controls`,
Draft https://github.com/FatihBirgul/trade-ai/pull/11, base verified
c5202ef2b94e8ddb870e3d6aca5004ef5f76a166 (PR10).
Actual code checkpoint HEAD: **2bfc85caae8a8a05ad89cad031959566e223f203**;
this handoff's enclosing docs commit/PR11 headRefOid is final published HEAD.
Other checkpoints227489b controls,78e46a5 research,85848d1 logical manifest.

Gateway: `codex/gateway-notification-controls`, Draft
https://github.com/FatihBirgul/trade-ai-gateway/pull/5, actual source HEAD
**fca040c1a276e301c6a3c2eac97c77ce3a1efb35**, basec9fca90(PR4).
Android: `codex/android-notification-controls`, Draft
https://github.com/FatihBirgul/trade-ai-android/pull/9, actual source HEAD
**776d21f0065a07384aea9ecd0e570345ae57d555**, basec4b3df2(PR8).

## Implemented — do not regenerate

- Owner/account notification preferences: strict categories, opt-in defaultoff,
  immutable revisions/cap256, optimistic concurrency/idempotent receipts,
  logical recipient revoke/replace and <=24h lease. Gateway asserts principal from
  server-owned renewal family (or nonrenewable session), never client device UUID.
  notifications:write is separate opt-in pairing grant; old grants unchanged.
  No device/provider tokens accepted/stored/returned. Read observation timestamp;
  exact replay is immutable historical receipt, GET gives current status.
- Dispatcher authority required at claim and immediately before fixture adapter,
  boolTrue only; category/account/recipient/preference/session checks, persistent
  global60attempt/min budget, retries/TTL/leases/idempotency remain. Live adapters
  hard-refused: provider/device authority integration UNAVAILABLE. Runtime starts
  no sender. ACCEPTED is not DELIVERED. Multi-recipient fanout and real delivery
  receipts/preferences orchestration remain PARTIAL; old unscoped notices denied.
- Six missing engineering candle definitions, each versioned, causal and tested:
  three_stars_in_south,unique_three_river,advance_block,stalled_pattern,tristar,
  breakaway.55catalogue IDs/families now; NOT TA-Lib61function equivalence. New
  invalidated findings excluded from supportive diagnostic confluence.
- Three-touch3left/3right V1 pivot geometry: ascending/descending/symmetric
  triangle, rising/falling wedge, rectangle, rising/falling channel boundaries.
  Two closed crosses after first knowledge;12bar bounded confirmation, separate
  failure/retest. Wedge continuation/reversal follows actual break vs prior trend.
  Narrow30bar three-stage rounding top/bottom with10bar base,60bar warmup, two
  later neckline crosses. Not universal pattern classification/validated strategy.
  Android shows formation/knowledge/confirmation/invalidation and interpretation.
- Read-only logical archive manifest CLI `backend/scripts/archive_manifest_v2.py
  EXPLICIT_REVIEWED_COPY.sqlite [--expected MANIFEST.json]`. Account sequence/body
  roots, last snapshot anchor, actual UTC extrema, domain head/cutoffs, independent
  accounting audit. Consistent copy backup gives same logical manifest. WAL change
  during audit=>INCOMPLETE; row/bytes/VM/input budgets; missing source never created.
  Hashes are not signatures; no physical/WAL file hash or archive deletion claim.

## Actual validation and artifact

Local final **503 V2 tests /101.787s**,11quote/outcome,51realBackendGatewayASGI,
167Android/40suites, typecheck/lint, localdoctor17checks, Android JS export and
6APK parser tests passed. Initial controls227489b fourOS/Python CI passed; final
Backend docs/source HEAD matrix must be checked from PR11 before claiming it.
Gateway final Python3.11/3.12 CI passed; standalone39pass/12conditionalBackend
skips (verify logs), distinct from51actual local integration tests. Android final
frontend source776d21f CI passed. Native APK run41335742921 requested for that exact
source; actual artifact/hash/cert/expiry results are recorded in PR9 at delivery.
Do not relabel older c4b3df2 APKs. Packagecom.fatihbirgul.tradeai/0.7.2/code11 remains
internal testing; installed-device certificate/runtime/update UNVERIFIED. No wipe.

Authoritative active OpenAPI **35paths/47schemas**, SHA256
`4e415c18786e29f932c94a25a06439c6f7f315b899cd6ca3605798476ebb8c4d` at Backend
docs/V2_OPENAPI.json, Gateway trade_gateway/openapi.json, Android docs/backend/
V2_OPENAPI.json. Old34paths/44schemas structurally unchanged. New preference writes
are not paper writes. No worker/order permission/risk/financial formula changes.

## Next safe milestone

1. Real provider/device tokens, recipient hardware ownership, authoritative family
   revocation service, per-recipient outbox namespace/fanout and delivery evidence
   require a separately reviewed explicit integration. Keep sender off; prefer
   fixture tests. New settings are logical preferences, not phone registration.
2. Add explicit immutable anchoredVWAP source selection UX/API and research-only
   indicator parameter/protocol binding without global patching. Existing OOS
   registry/strategy execution unchanged; historical license/rules/fees trust,
   external anchors and real market/forward validation remain INSUFFICIENT_EVIDENCE.
3. More real positive/negative fixtures for each OLD V1 structural taxonomy;
   new boundary/rounding definitions are deliberately narrow. Session noncrypto/
   nonUTC calendars/providers still UNAVAILABLE. No TA-Lib or profitability claim.
4. Archive-read manifests currently validate intact reviewed copies; no archive
   restore/merge/reader spanning multiple files. Keep sequence, body hashes,
   cutoffs/heads/cursor anchors; never delete/VACUUM/rowid-rewrite financial history.
5. Physical-device matrix below in VALIDATION_MATRIX is future authorized work,
   not a test result. No PC/private network/deployment/real-money access authorized.

First actions: clean git statuses; `gh pr view 11 -R FatihBirgul/trade-ai --json
headRefOid,statusCheckRollup` and GatewayPR5/AndroidPR9; verify final artifact source.
New optional notification facts require compatible binary and reviewed copy backup
for rollback. Never delete domain tables/history to run an old binary. Main/oldPR
histories/protected AGENTS backups untouched. Below is historical Continuation5.

# Devam noktası — Continuation 5

Backend Draft PR10 branch `codex/trade-ai-v2-history-research` from verified
b541198 (PR9). Gateway Draft PR4 branch `codex/gateway-history-pagination` from
a57556b (PR3), source c9fca90. Android Draft PR8 branch
`codex/android-history-pagination` from2a60c99 (PR7), latest source c4b3df2.
No main/old PR history changes. Exact final HEAD/CI/artifact: query these PRs.

Implemented checkpoints: 29e1136 read-only cursor archive/minmax; c9fca90 Gateway;
b4490c9 mobile archive; a723f1d causal candles/chart/session; c7ab5c9 mobile research;
c4b3df2 invalid-UTC response guard. Final Backend registry/clock-extreme/docs
checkpoint follows a723f1d; PR10 is authoritative for its exact SHA.

Local checkpoint A:441V2+11quote,159Android,49actualGatewayASGI passed.
Analysis checkpoint B:461V2 and160Android passed. Final local source passed469V2 in91.812s,11quote,161Android/39suites and
49realGateway. Includes clock-sampling regression, seven registry tests and mobile
UTC guard. Final remote source CI must be checked in PR10 before claiming platforms. Six APK evidence parser tests and localdoctor17/export
passed. Android native workflow sourcec4b3df2 run41329082021 requested; do not reuse
oldAPK as this source. Final actual artifact/hash/cert/expiry recorded in PR8.
PreviousAPK certificate fingerprint is fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c;
matching a reference does not prove installed-device compatibility. Device remains
UNVERIFIED; never uninstall or erase data. 0.7.2/code11 internal build unchanged.

Do not repeat these features. Read new modules/equity_archive.py,
chart_confirmations.py,session_research.py,research_registry.py and regressions.
Active OpenAPI34paths/44schemas is equal at Backend docs/V2_OPENAPI.json,
Gateway trade_gateway/openapi.json, Android docs/backend/V2_OPENAPI.json.
Old API/immutable analyses/accounting/risk/AUTO grants preserved.

Next safe priorities:
1. Notification recipient/account/session authorization and preferences before any
   real adapter activation. Runtime still does not start transport. No device or
   provider tokens/permissions available: real push UNAVAILABLE/UNVERIFIED.
2. Chart triangle/wedge/rounding confirmation families and real fixtures for every
   old V1 structural family remain PARTIAL. Six candlestick catalogue gaps remain;
   no TA-Lib equivalence/strategy profitability claims. Current flags are narrow
   fixed geometry. RSI/MACD/candles/chart/session DETECTION_IMPLEMENTED only.
3. Research registry explicitly opt-in (`walk_forward_v2.py --registry PATH`, first
   create with `--create-registry`). It records before training and caches frozen
   results; different protocols cannot reuse overlapping held-out periods within
   the same instrument/source registry, even if dataset hash changes. It cannot
   police experiments outside that file, authenticate historical rules/fees or
   establish real-world profitability. Arbitrary indicator optimization, profile
   binding, external anchors and formal protocol review remain open.
4. Crypto UTC-day session is not a trading-session calendar. Forex/XAU/non-UTC
   market calendars UNAVAILABLE; anchored VWAP requires explicit source candle,
   currently research function only. Mobile does not invent an anchor.
5. Archive sampling <=10000observations/16MiB scanned, <=200points/2MiB response,
   SQLite VM budget; broader range returns incomplete or requires raw pages.
   Improve profiling/archive-read manifests with retained account sequence/body
   hash/domain cutoffs. No deletion, rowid rewrite, VACUUM or financial compaction.

First action: clean statuses, `gh pr view 10 -R FatihBirgul/trade-ai --json
headRefOid,statusCheckRollup`, corresponding GatewayPR4/AndroidPR8, actual APK
artifact/source evidence. No live deployment/migration/private network/PC access.

Below is historical Continuation4 context, superseded by the entry above.

# Devam noktası — Continuation4 M18–M20

**Güncel teslimat:** Backend DraftPR9 (`codex/trade-ai-v2-equity-history`, base07f1878),
Gateway DraftPR3 (`codex/gateway-equity-history`, HEADa57556bcfe76bb2365317a7281059b5b41c6ef72),
Android DraftPR7 (`codex/android-equity-apk`, HEAD2a60c994b70d30021051636b02ba686c4b197c57).
Backend checkpoint9a19360/48ead16/e396a60/29d81dd + final M20 foundation/docs;
exact HEAD/CI from PR9 is authoritative. All worktrees clean after delivery.

Final local433V2+11quote,49realASGI Gateway,155Android+6APK-parser tests passed.
29d81dd4OS/Python CI passed; final Backend M20 HEAD must be rechecked. Gateway and
Android final pinned CI passed. Native APK run41312282983/artifact13086452241,
source2a60c99 verified (actual binary/hash/cert/bundle), expires2026-11-08T13:52:14Z.
APK SHA256cc3a6e4e8b7bd6a55d58e2d69a07e485cceb7cf001e72eadb213fa4d63b62f1a.
Package0.7.2/code11 unchanged, cert matches old actual APK; device/in-place update
UNVERIFIED, no uninstall/data wipe. First92e4e3e APK also verified, predates M18.

**Do not repeat:** M18 forward-only immutable observations/independent domain replay,
UTC periods/Android panel; opt-in source notices/dedup/TTL/recovery; frozen follow
revision; confirmed legacyRSI14SMA/MACD12/26 divergence research; standalone default-
disabled notification transport foundation. Read modules/tests before extending.

**Next priorities:**
1. Production push adapter/recipient authorization and user preferences need an
   explicitly authorized provider/device setup. Do not assume credentials, device
   permissions or delivery. Dispatcher is NOT started by Runtime; accepted≠delivered.
   Future adapter must prove idempotency and enforce timeout; local FakeAdapter is
   fixture-only. No automatic orders or sender activation.
2. M18 old history is not filled. Improve actual-point paging/downsampling beyond
   latest200, query/growth measurements and archive-read design. Preserve every
   financial/event/attempt record; no cleanup/VACUUM/rowid rewrite added. Legacy
   drawdown prefix staysINCOMPLETE; hashes are not signatures.
3. M19 ModifiedHikkake/flags/pennants/rounding/session/anchoredVWAP/ORB remain open.
   Existing confirmed divergence isDETECTION_IMPLEMENTED, not backtested or forward
   validated. Do not make it an execution trigger or count momentum twice.
4. Real phone/PC/private network/native app runtime validation requires separate
   explicit authorization. Downloaded APK metadata is not physical-device proof.

First commands: `gh pr view 9 -R FatihBirgul/trade-ai --json headRefOid,statusCheckRollup`
and equivalent GatewayPR3/AndroidPR7, then clean status/remote refs. Main and old
PR histories unchanged; protected AGENTS backup files remain untouched. No live
SQLite, real money, private network, production or secret changes authorized.

Below is historical Mission3 context; the Continuation4 entry above supersedes
its old next-work ordering and counts.

# Historical — Mission3 M14–M17

**Güncel:** Backend PR8, Gateway PR2, Android PR6 (üçü de Draft). M0–M13 ve
ürün profilleri yeniden geliştirilmez. Backend kod65233fa; Gateway
8b1cf0a1e26e18462d6703c6bc838181338d6a67; Android
92e4e3ea4d7a8ad03c069cf41275b1a17f2b6a4d. Son Backend HEAD belge checkpoint'i
olabilir; PR8 headRefOid/statusCheckRollup kaynak otoritesidir.

Yerel397V2+11quote,48gerçekASGI Gateway ve146Android testi geçti. Gateway
CI3.11/3.12 ve Android frontend CI son kodda geçti. Backend65233fa Ubuntu3.11/
3.12 ve Windows3.12 geçti; Windows3.11 sonucu/final belge HEAD CI için PR8'i
kontrol et. İlk Windows3.12 işi10dakika sınırında iptal edildi; yeni sınır20dakika,
hiçbir test/finansal kural gevşetilmedi. Ayrıntı VALIDATION_MATRIX'te.

**İlk güvenli iş:** M18 kalıcı, kaynak/zaman/hesap bağlı immutable mark/equity
snapshot tasarımı ve geçici DB regresyonu. Önce var olan fiyat kayıtlarını doğrula;
geçmiş grafik noktası üretme. M14 ileri parametre ayarı, M17 yeni TTL/outage olayları,
M19 yeni dedektörler ve M20 gerçek push henüz bitmedi. Cihaz/üretim testi yok.

Aşağıdaki M7–M13 bölümü tarihsel bağlamdır; en sondaki Mission3 devir notları da
geçerlidir. Yeni ajan önce yukarıdaki PR HEAD/CI'ları doğrular; main'e yazmaz.


Bu dosya ve MASTER_PROGRESS, FEATURE_INVENTORY, VALIDATION_MATRIX okunarak devam
edilir. Önceki M0–M6 veya yeni M7–M13 yeniden yazılmaz. Yeni uzun prompt gerekmez.

## Doğrulanmış referans ve ilk işlemler

- Repo: `FatihBirgul/trade-ai`.
- Dal: `codex/trade-ai-v2-master-continuation`.
- Base: PR#6 `4ae1fdc7b33c38a83f4b2316a9659aa5a7ff8537`.
- Son kod: `4c97f4f6947f48f03510c198b89fae19569cae43`.
- Draft PR: https://github.com/FatihBirgul/trade-ai/pull/7 ; base master-development.
- Son belge HEAD ve nihai CI için PR7 `headRefOid/statusCheckRollup` yetkilidir.
- Android a14c11775288051b54c8a8fcb78749167a9b0304; Gateway
  19038bdecd5ef472ff7826bb074208d300d682f8. Kaynakları bu continuation'da değişmedi.

```sh
git status --short
gh pr view 7 --json headRefOid,baseRefName,isDraft,statusCheckRollup
git fetch origin codex/trade-ai-v2-master-continuation
# temiz ağaç + uzak HEAD doğrulandıktan sonra benzersiz yeni devam dalı
```

Main, Task13, PR6 dalı, kullanıcı diff/untracked ve AGENTS.md'deki üç korunan
analysis/confluence yedeği değiştirilmez. Live DB/servis/private network/PC/real
account/paid service/secrets yok. Otomatik paper izinleri genişletilmez.

## Tamamlanan dar milestone'lar

- M7: gerçek expanding/rolling train/select/freeze/test; label purge/inter-test gap,
  immutable cutoff, fixed costs/versions, budgets ve strategy/regime attribution.
- M8: standalone manifest, source/hash/rule/cost binding; bounded public capture ve
  iki NEW JSON dosyasının exclusive/rollback yazımı. Eksik trust INCOMPLETE.
- M9: Hikkake confirmation/expiry, LadderBottom/Top, MatHold, ConcealingBabySwallow.
- M10: bounded V1 structural chart adapter, ilk bilinebilir kapanış; ayrı causal
  range breakout/retest/fakeout, canonical experiment ID ve engine binding.
- M11: whitelist research profiles, yöntem/TF/regime/bucket gates, version history,
  file CLI ve research filter. API/mobile selector henüz yok.
- M12–M13: frozen profile versions, post-retest failure, gerçek CLI --embargo
  regresyonu. Yeni modüllerin hatalarıdır; eski ledger math hatası olarak sunulmaz.

## Sonraki P0 sırası

1. **OOS deney protokolünü güçlendir:** cadence/selected-route filter dışındaki
   güvenli indicator parametrelerini immutable config olarak engine'e geçir; global
   STRATEGIES/PARAMETERS patch etme. Parametre araması yalnız training'de; held-out
   tekrarlarını farklı protocol ID'lerinde de izleyen preregistration/result registry.
   Şimdiki embargo inter-test gap'tir; genel PurgedKFold CV olduğu iddia edilmez.
2. **Tarihsel trust:** source/license ve point-in-time instrument rules/fee schedule
   için doğrulanabilir archive refs. Current exchangeInfo geçmişi doğrulamaz.
   Değişen rule schedule şu an uygulanmaz; mismatch fail closed. Provider public
   erişimi veya reviewed declaration authenticated evidence değildir.
3. **Pattern/chart kapsamı:** kalan TA-Lib aileleri ve ModifiedHikkake; flags,
   pennants, rounding ve her V1 structural family için positive/negative/neckline
   fixture. Şimdiki chart confirmation structural/supplied-window'dur; emir değildir.
4. **Gerçek ürün seçici:** research profile API/server authorization/journal
   bağını ayrı tasarla; Backend/Gateway/Android sözleşmelerini birlikte doğrula.
   Şimdiki filter alternatif route seçmez, WAIT'i canlandırmaz. Public AnalyzeRequest
   hâlâ profile alanı kabul etmez; bunu sessizce değiştirme.

## Sonraki P1/P2

Confirmed RSI/MACD divergence, session/anchored VWAP/ORB ve calendar; OHLC SMC
sezgileri gerçek kurum emri diye sunulmaz. Scanner/follow profile binding, validity,
quality/outage ve dedup. Ürün equity curve için immutable mark kaynağı gerekir;
tarihsel nokta uydurma. Android diagnostic/selector/validation render ayrı dal/PR;
gerçek cihaz testi yok. Outbox pending/not_configured korunur; push adapter/izin
olmadan DELIVERED yok. Archive-read/restore/external anchor; financial geçmiş silinmez.

## Kalite kapısı ve gerçek sınırlar

Son yerel381/381 V2=334korunan+47yeni,11quote/outcome,Gateway42; compile/OpenAPI26/34
eşit. Son source/full HEAD CI PR7 checks/VALIDATION_MATRIX'te ayrıca doğrulanır.
Python3.11/3.12,Windows/Ubuntu ve ResourceWarning=error korunur. Financial journal,
AUTO/MANUAL ve hash invariant testleri eski suite içindedir; test/risk zayıflatılmaz.

Synthetic2fold/2candidate mekanik OOS ve CLI'ler geçti; piyasa doğrulaması değildir.
Public360closed1m capture+training çalıştı ama0training sample→0OOSfold. License,
historical rules/fees INCOMPLETE; sonuç INSUFFICIENT_EVIDENCE. Gerçek market kârlılığı,
forward validation, telefon/Windows servis ve production deployment yapılmadı.

## Mission3 active continuation (2026-11-01)

Backend branch `codex/trade-ai-v2-product-integration` from b691116. New product
profile API + optional narrowing AnalyzeRequest.profile_id. Separate Gateway
`codex/gateway-product-profiles` from19038bd; Android
`codex/android-product-integration` froma14c117. Do not restart M0–M13.

M14 fixed-period selection and revisions implemented. Read `profile_product.py`,
`test_v2_profile_product.py` and contract M14 section.12 isolated regressions,
including legacy copy-upgrade boundary; no historical domain events invented.
Profile migration has a cutoff for existing profile facts. Old journal-enabled
binaries do not understand the new optional fact registry: rollback uses a prior
verified DB copy plus old binary, never deletion of domain tables in place.

Next: finish source-head CI verification and cross-repo Draft PR references, then
M17 explicit immutable profile binding for scanner/follow (no AUTO grant expansion),
M18 persistent mark snapshots before equity history, M19 missing diagnostics,
M20 notification adapter. Android device/push/deployment remain UNVERIFIED.
Private backend checkout is required for Gateway integrated tests:
`TRADE_AI_BACKEND_REFERENCE=/path/to/pinned/trade-ai python -m pytest -q`.
Default Gateway CI lacks cross-private-repo credentials; never invent or add a
secret to bypass that boundary. Security unit tests still run without backend.

## Definitive Mission3 handoff

PR8 Backend, PR2 Gateway, PR6 Android (all Draft) are dependent on their existing
development bases; main unchanged. Fetch each PR head, do not reset/merge histories.
Source checkpoints: Backend c65c178/58aef3b; Gateway ed6e17e/ce84b19;
Android c604b78 + scanner compatibility commit. Final head SHA/CI from GitHub:

```sh
gh pr view 8 -R FatihBirgul/trade-ai --json headRefOid,statusCheckRollup
gh pr view 2 -R FatihBirgul/trade-ai-gateway --json headRefOid,statusCheckRollup
gh pr view 6 -R FatihBirgul/trade-ai-android --json headRefOid,statusCheckRollup
```

Local397V2/11quote,47Gatewayintegrated,145Android tests; no uncommitted user files
were consumed. Windows first3.12 timed out at10min; budget now20min, tests retained.
Read VALIDATION_MATRIX and final PR checks before asserting all platforms passed.

Next safe milestone: M18 immutable mark/equity snapshots with same financial
transaction + independent audit, account/mode/source/UTC binding. First inventory
existing price_time/mark persistence; do not reconstruct invented historical equity
points. Then period/strategy/exposure views, Android rendering solely server math.
Before bigger work: finish M14 precise field-validation UX and typed catalogue,
more scanner/follow TTL/outage/dedup fixture coverage, profile lineage import/version
rollout policy. Arbitrary tuning/alternative routes remain forbidden until validated.

M19 causal confirmed divergence/ModifiedHikkake/chart positive+negative fixtures;
M20 retry/backoff/outbox adapter, real push remainsUNVERIFIED without device/service.
No production rollout or live migration is authorized here. Existing domain-enabled
DB rollback needs a prior verified copy; do not drop new registry/history rows.
Protected AGENTS backup paths remain untouched. Development version0.7.2/11 remains
unreleased; no PC, private network, Android device or market performance claim.
