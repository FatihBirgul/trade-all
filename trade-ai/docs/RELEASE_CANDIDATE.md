# Trade AI 2.0 — Continuation 8 internal release candidate

Scope: installed-source integration and an installable **test** artifact, not a new
feature release, deployment, investment validation or physical-phone approval.
Candidate version **0.7.3 / versionCode12**, package`com.fatihbirgul.tradeai`.

## Exact source and dependency target

| Repository | Verified base | RC code SHA | Dependent Draft |
|---|---|---|---|
| Backend |33e4ef5f1f9830648f414f0554c638edd0addffb (PR12)|8280ea82c447be1921309a3f01b608f4a9e9f9ca|[PR13](https://github.com/FatihBirgul/trade-ai/pull/13)|
| Gateway |b75cb790bbb712a542a63085681c27036f057b3b (PR6)|e63ac56cd0dbe7139624766b0a8f289b852c712c|[PR7](https://github.com/FatihBirgul/trade-ai-gateway/pull/7)|
| Android |ca0f9018ffbad83bd7d375b91001e13e83e89609 (PR10)|761bec051de2d61ca234e48b4f86b12079fbdb46|[PR11](https://github.com/FatihBirgul/trade-ai-android/pull/11)|

The enclosing Backend evidence/docs commit is the published PR13 HEAD; its runtime
code is the8280ea8 checkpoint above. Final-HEAD checks and final clean-source
rerun are verified separately in PR bodies. Do not silently substitute older SHA
success. `RC8_ACCEPTANCE.json` records the clean code-checkpoint execution.

All active contracts remain **36paths/51schemas**, SHA256
`676a3558503dcbdab7535bfdfa5e89f5f8c355a058e09d52067a62a674d128c2`.
No contract, financial formula, strategy, sender or execution grant changed.

## Reproduce the real-source integration

Clean sibling checkouts; Python3.11/3.12, Node with Android npm dependencies,
OpenSSL, Backend test requirements and Gateway test dependencies are prerequisites.
Use already-authorized repository access; no new secret is required/requested.

```sh
python trade-ai/backend/scripts/release_candidate_e2e.py --android trade-ai-android --gateway trade-ai-gateway --output /tmp/trade-ai-rc-acceptance.json
```

Run from their common parent. On Windows choose a new disposable report path and
ensure Node/OpenSSL are installed; this exact full-stack command was executed on
Cloud Linux, not Windows/phone. A dirty input checkout produces
`PARTIAL_DIRTY_INPUTS` and exit1; no release PASS from uncommitted code.

The controller compiles the actual Android API/gateway/renewal TypeScript modules,
creates disposable Backend/Gateway DBs and an ephemeral one-day CA, binds only
127.0.0.1, and uses a certificate/SAN-verified real HTTPS connection. The production
Gateway authenticates mobile sessions and forwards its private bearer to the
actual Backend ASGI app. Neither TLS, auth nor response validation is disabled.
Host`rc.example.test` is pinned to loopback only inside the injected HTTPS test
transport; no DNS/hosts/Tailscale/public-port configuration is changed.

The provider is explicitly named`RC_CONTROLLED_FIXTURE`, with deterministic
synthetic OHLC/volume/rules. It exercises the **live wire schema**, because the
unmodified mobile client correctly rejects fixture-mode responses. This is not
live-market data, a fallback provider, an APK demo mode or profitability evidence.
The controlled Backend clock starts at current UTC minute (recorded in JSON) so
real session/recipient expiry validation remains enabled, then advances explicitly.
No exact cross-run UUID/timestamp/report-hash equality is claimed.

**Fixture prerequisite:** two explicit administrator-created test paper orders
(one per account) seed actual fills/fees/marks and201 consecutive ledger events.
The real ledger creates the immutable observations. Android receives **no paper
write grant**; `auto_paper=false` throughout. Empty accounts legitimately have no
historic equity points until an actual capture source exists; no backfill occurs.

Faults are explicit: old-route404 at the Backend transport; real successful HTTP
ACK discarded by client transport after commit; corrupted Gateway output after
real auth; deferred HTTPS response until the actual15-second client timeout;
actual Gateway listener shutdown. These are controlled failures, not normal API
successes or mocks of the production Android response validator.

## Product acceptance scorecard

Clean code run: **13 scenarios /74 real HTTPS requests**, statusPASS; two independent
financial audit checkpoints each PASS24996 /MISMATCH0 /CORRUPT0 /ERROR0 /
INCOMPLETE0. Those are invariant checks, not independent trades or market evidence.

| Product workflow | Status | Executed evidence / explicit limit |
|---|---|---|
| Pairing/scoped session/market catalogue |PASS|Actual pairDevice/mobileSession client and TLS Gateway, scopes checked; no paper/notification write inferred|
| Analysis/saved immutable closed candles |PASS|Actual analyze/detail/candles, source record identity and closed-time checks|
| Technical research/Anchored VWAP/parameter errors |PASS|Saved source, real fixture volume, deterministic retry,422 and false trade_permission|
| Profile create/revise/select/evaluate |PASS|Actual API, old follow revision remains frozen after a newer revision, cross-account403 and missing404|
| Watchlist/scanner/profile binding |PASS|Actual authorized watch/pause/manual tick/read; auto_paper remainsfalse|
| Follow/source outage/recovery/dedup |PASS|Actual follow API and explicit one-shot server service ticks, pending source-unavailable/recovered outbox records; no background worker started|
| Autonomous scheduling/continuous follow worker |UNVERIFIED|worker_running=false accurately reported; no production worker activation|
| AUTO/MANUAL balances/history/archive |PASS|Actual client reads, account filtering,200-point cursor page then non-overlapping/repeatable next page, real seeded ledger sources|
| Financial audit/restart |PASS|Independent read-only audits before/after actual Backend/Gateway object reopen over disposable DBs|
| Notification preferences/pending status |PASS|NOT_CONFIGURED, no sender, unauthorized client/server writes403; pending never interpreted as delivered|
| Real push delivery |BLOCKED|No provider/device authorization or credentials; no sender started|
| Session renewal/lost ACK/revocation |PASS|Production renewal module, actual committed rotation replay, old session401,403 does not revoke; save callback is RAM fixture|
| Physical SecureStore/session continuity |UNVERIFIED|No installed device or native SecureStore used|
| Backend/Gateway outages, malformed reply, timeout |PASS|Actual HTTPS error paths, client rejects malformed200 and actual15-second timeout|
| APK manifest/signature/assets |PARTIAL at report commit|Native workflow41490345414 running; final verified evidence is recorded in AndroidPR11 body/artifact|
| Native app startup/navigation/device networking |UNVERIFIED|Jest/render/typecheck/build are not a physical-phone/emulator smoke test|
| Historical/forward research validation |BLOCKED|Only controlled fixture evidence; real licensing/historical fees/rules/forward results absent|
| Deployment |PARTIAL|Source versions pinned and copy-only checklist below; no production deployment or live DB validation|

CategoryA(code/tests):PASS for the above implemented paths. CategoryB(integrated
product):PASS for actual compiled client transport; PARTIAL for native UI/runtime.
CategoryC(deployment):PARTIAL pending human review/compatible-copy rehearsal.
CategoryD(device):UNVERIFIED. CategoryE(market evidence):INSUFFICIENT_EVIDENCE.
No project-completion percentage is assigned.

### Real defect fixed

Medium UX/integration severity: missing research/profile endpoints on an older
Backend were mapped to generic BACKEND_UNAVAILABLE, misleading the app into a
service-outage explanation. The new HTTPS old-route scenario and a separate
Gateway regression failed first. `trade_gateway/app.py` now maps route absence to
BACKEND_UPDATE_REQUIRED; actual PROFILE_NOT_FOUND, parent auth and403 remain
unchanged. A further real-Backend negative regression caught an intermediate
false update classification for RESEARCH_UNAVAILABLE. The final explicit public
allowlist preserves source absence, source mismatch, invalid parameter and invalid
anchor codes; missing capability still requires update.13 real-source scenarios
pass again against finale63ac56. Gateway55 tests in the integrated checkout;
standalone41 passed/14 explicit private-checkout skips. No risk/math correction.

Initial harness mistakes (market field`items`, profile ID not a direct follow
response field, no equity history without capture sources) were corrected against
existing contracts, not reported as production bugs or solved by expanding APIs.
Clock-skew fixture failure confirmed recipient authority is fail-closed; Backend
and Gateway clocks must agree during rollout.

### Component checks and limitations

Backend530/530 V2 baseline,11 quote/outcome, compile. Android172/42suites,
TypeScript/ESLint, local Expo doctor17, JS export and6 APK-tool tests. Gateway55 in the integrated checkout (41 standalone +14 Backend-dependent
executed); standalone41/14skips. Exact final OS/Python CI and APK verification
results appear in the three PR check pages/bodies, not inferred from baseline.
Full-stack CI across three private checkouts is not provisioned with extra secrets:
Cloud command/result is the integrated evidence; per-repo CI is a different gate.
Existing Node/npm/Kotlin/Gradle/Starlette deprecations remain visible in CI logs.

## Stacked PR integration readiness — no merges executed

[RC8_DEPENDENCIES.json](RC8_DEPENDENCIES.json) contains every full base/head SHA,
ref, state and Git ancestry result at the audit. All original PRs remain open,
unmerged; every current base is an ancestor of its head, and main is an ancestor
of each candidate. This establishes current linear ancestry, not future conflict
immunity or approval of an entire historical diff. Stable patch-ID comparison found
zero identical patch groups in107 Backend/57 Android/16 Gateway nonmerge commits
above their pinned main ancestors.

| Repo | Parent chain, oldest first | Candidate | Target caveat |
|---|---|---|---|
| Backend |PR1→2→3→4→5→6→7→8→9→10→11→12|PR13|PR1 targets`trade-ai-v2` at022e3e2173..., not main. No reviewed bridge PR from that V2 root to main exists. Main promotion is a separate human decision.|
| Android |PR1→2→3→4→5→6→7→8→9→10|PR11|PR1 targets main; later PRs target previous feature refs.|
| Gateway |PR1→2→3→4→5→6|PR7|PR1 targets main; later PRs target previous feature refs.|

The candidate tips already contain the entire parent histories: do not cherry-pick
all parents again or combine independent partial versions. Oldest-first human
review/incorporation must preserve ancestry; squash/rebase changes require a new
range/conflict audit. After approved incorporation of a parent, a human may
retarget the next PR to the reviewed integration target and rerun checks. This
plan changes no bases or branches itself. Re-fetch and repeat ancestry/diff/schema
checks immediately before any human merge. CI branch allowlists also require
review before post-merge promotion; do not assume main push runs all V2 checks.

Cross-repo rollout must pin all three candidate SHAs together. No missing companion
code remains for this contract/fix. Candidate report/CI/APK proof does not approve
legacy DB migration, public exposure, default workers or production install.

## Safe Windows rollout preparation — instructions only, never executed here

1. Human inventories the existing services, repo paths/branches/HEADs, Python3.11
   or3.12 venvs, DB locations/schema/domain markers, gateway origin and existing
   authorized permissions. Do not print environment variables, tokens or full
   process command lines. Preserve protected AGENTS backups.
2. Human chooses a maintenance window and stops mobile writes first, Gateway then
   Backend using their existing console/service stop mechanism. Do not use
   force-kill or change firewall/Tailscale. No stop commands are automated here.
3. Verify **new, separate** consistent copies of Backend SQLite and sensitive
   Gateway session DB using existing approved backup practice. Do not copy only
   a live SQLite main file while WAL is active. Audit reviewed copies; retain
   original binaries, config, venv and immutable history. Do not overwrite backups.
4. Pin reviewed candidate SHAs and install dependencies into a new explicitly
   chosen venv, never mutate the running venv in place. Verify Python versions,
   active3 contract hashes and all checks before choosing any service switch.
5. Rehearse against a **copy**. Existing copy-upgrade tool is
   `backend/scripts/migrate_v2_domain.py`, never an in-place live migration. Existing
   records are not backfilled; missing legacy evidence remainsINCOMPLETE. Stop on
   ERROR/CORRUPT/MISMATCH or unexplainedINCOMPLETE; no automatic repair.
6. Only after separate approval, start Backend on127.0.0.1:8002 using an explicit
   reviewed working-copy path and existing protected V2_API_TOKEN configuration.
   Existing `backend/start_v2.py` binds loopback. Do not pass`--scanner` or
   `--tracking` by default; domain-journal flag only for reviewed compatible copy.
7. Start the pinned Gateway using its existing HTTPS termination/origin policy and
   existing secret configuration, then local health/scope checks. No new Tailscale,
   DNS, port-forwarding or public listener. Backend bearer stays server-side.
8. Human pairs Android with a short-lived single-use code, least-privilege read/
   analyze accounts first. Optional profile/scanner writes require separate local
   grants. No paper grant or notification sender/device registration is implied.
9. Smoke test markets→analysis→WAIT/outage→saved research→profiles→account reads→
   archive→notifications→renewal/restart. Check UTC clock alignment and that
   worker_running/push status accurately report reality. Compare independent
   financial audit and immutable roots before/after. No real-money testing.
10. Failure: stop new writers, preserve failed working copy/logs, restore service
    configuration only after compatibility review. Older binaries may not read
    newer financial records; roll back with the reviewed matching binary+copy,
    never downgrade/overwrite the only financial DB or discard new history.

Safe read-only PowerShell inventory examples (operator supplies existing paths):

```powershell
# These commands do not stop services, write Git history, or expose credentials.
git -C $Backend status --short
git -C $Backend rev-parse HEAD
git -C $Gateway rev-parse HEAD
git -C $Android rev-parse HEAD
& $BackendPython --version
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 8002,8787 } |
    Select-Object LocalAddress,LocalPort,OwningProcess
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python' } |
    Select-Object ProcessId,Name,ExecutablePath
```

Copy-only rehearsal commands, **only after explicit operator selection of an
existing reviewed copy and a new destination**, never a live/default path:

```powershell
if (-not (Test-Path $ReviewedCopy -PathType Leaf)) { throw 'Reviewed copy required' }
if (Test-Path $NewBackup) { throw 'Destination must not exist' }
& $BackendPython "$Backend\backend\scripts\backup_v2.py" $ReviewedCopy $NewBackup
& $BackendPython "$Backend\backend\scripts\audit_v2.py" $NewBackup --require-domain
```

Read-only local health with an already configured secret (never print its value):

```powershell
if (-not $env:V2_API_TOKEN) { throw 'Existing secure local configuration required' }
Invoke-RestMethod 'http://127.0.0.1:8002/api/v2/health' -Headers @{Authorization="Bearer $env:V2_API_TOKEN"}
```

Next physical-device action: with the user present and separately authorized,
compare the installed package/version/certificate to the actual candidate APK;
perform a normal non-destructive installation/update only if compatible. Then
startup, existing session/renewal, Basit/Pro analysis/research, account/archive,
scanner/follow state, preferences, offline and app-restart smoke tests. Record
actual results. Do not uninstall, clear data or assume matching source certificate
proves installed-device compatibility.
