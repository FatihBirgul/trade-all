# Final Android UX Polish — verified delivery

Android Draft https://github.com/FatihBirgul/trade-ai-android/pull/15 .
Branch `codex/android-final-startup-ux`, APK/code source `41e47d013b1c9881ba4ffda62ddfcea91677988a`.
Enclosing final commit adds documentation evidence only; do not confuse its HEAD
with the earlier immutable APK source. Base PR14/4be11a6 and0.7.6/code15 retained.
Backend cb3eaa1f9cbd857eb2fe0563ddaa81f501d75e87 and Gateway
 d1c0e4d2263626a30e81af9e2b40d5e952cb7b76 untouched. No companion API/permission changes.

Resource-level root cause confirmed in actual old0.7.6 APK: white splash color,
Expo grey guide/grid PNG and old launch theme inheriting AppTheme. New actual APK
uses Theme.SplashScreen, dark#111316 day/night, post-splash window, MainActivity's
native manager and existing transparent T. Compiled checks reject old APK; new APK
passes. All packaged splash PNG variants match generated unchanged T pixels. No
new launcher/logo geometry/colors; original SVG/PNG/manifest hashes unchanged.
No video attachment/emulator/phone: actual native animation/first-frame display
remains UNVERIFIED. Raw drawables/web pictures are explicitly labelled below.

Local/CI:223 Jest/49 suites, TS/lint,19 local Expo checks, Android/web exports,
16 Python brand/APK/startup-tool tests; exact-source frontend41600968167 and native
41600894140 successful. Clean compiled-client HTTPS→real Gateway→Backend ASGI with
controlled fixtures:16scenarios/100requests, two independent audits PASS25184 each,
no mismatches/corruption/errors/incomplete; automatic orders0. Only fixture admin
seeds2 isolated orders. Source pins equal final code41e47d0/Backendcb3eaa1/Gatewayd1c0e4d.
This is not real provider, actual paper user history or phone evidence.

APK internal0.7.7/code16, com.fatihbirgul.tradeai, arm64-v8a,
minSDK24/targetSDK36. Actual native manifest/resources, embedded
JS/new startup strings, fonts/ZIP CRC and in-app/launcher/adaptive T checked.
SHA256 `365f54a9556efdc9cfb441c1d82524a40618b0dfbf1677c4f4d264f320b4153b`.
V2 certificate `fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c` matches previous ACTUAL0.7.6 APK.
Internal debug signing, not production signing or proof of in-place device update.
Artifact: https://github.com/FatihBirgul/trade-ai-android/actions/runs/41600894140/artifacts/13214444468
Expiry `2026-11-10T08:21:51Z` (7days; authenticated GitHub access required).
Native CI https://github.com/FatihBirgul/trade-ai-android/actions/runs/41600894140
Frontend CI https://github.com/FatihBirgul/trade-ai-android/actions/runs/41600968167

Loading: no artificial dwell. Native hides at first branded React layout. Theme
wait bounded750ms with late-response rejection/dark fallback; font error or2500ms
limit enables usable text navigation, then icons recover if font loads.6sec guard
only covers absent first-layout callback. No network/session/backend/worker readiness
gate, no app-open scan/order writes, no fake ONLINE or token/permission changes.
Foreground re-applies actual chosen local system appearance; no forced theme reset.
Root failure retry never clears data. Installed-device behavior still UNVERIFIED.

UX finalized: compact home/context; explicit account/profile analysis; decision and
real conditional levels before optional evidence; research catalogue deferred until
expansion (0 initial requests vs1 after user action); scanner primary warnings visible
and diagnostics expandable; settings grouping/visible live-access lock; shared48dp
controls, readable light/charcoal tokens and tabular numeric rows. Routes/financial
math/WAIT/401/403 and immutable history unchanged. No new pattern/strategy or cosmetic
rewrite planned. Both320/360px themes and controlled-font-stall web smoke passed;
no horizontal overflow/page errors/external requests. No physical startup timing,
FPS or RAM measurements claimed. No emulator was available. Online Doctor not run.

Known audit47 (1low/43moderate/3high), including @expo/cli,node-forge,zod, remains;
no general audit fix/exposure claim. Required SDK-matched splash/navigation modules
and3 associated Expo build-tool patches are documented, not hidden. Review security
reachability before production; native/Node/transitive deprecations remain visible.
OpenAPI40/58/hash729f422ae44c146a71b4bcd75f2f1df1c68ad07dddd9e9ed50619a80fa8f24eb unchanged.
No PC/private network/live DB/services/push/autostart/deployment/main/merge/force push.

NEXT: return to core engineering (scanner leases/capacity/provider rate/failure recovery,
real provider/data trust, opportunity lifecycle, secure notifications, independent
outage evidence, reviewed Windows unattended startup, historical/OOS/forward evidence).
Separately authorize phone cold/warm/relaunch, Android12+ launch mask/transition,
light/dark gesture+button bars, existing-session/SecureStore continuity and offline
recovery smoke. Never uninstall/wipe data or assume a binary downgrade is safe.

# Final Android UX Polish — 2026-11-03

Read this Android handoff before older cosmetic task notes. Backend's cross-project
handoff remains docs/TRADE_AI_V2_NEXT_ACTIONS.md at cb3eaa1 (unchanged this task).

Base Android PR14/4be11a66e3f45e0a119db3647d5c7ce40c3f58e0, internal0.7.6/code15.
New branch codex/android-final-startup-ux; dependent Draft PR and final exact source
are discoverable with `gh pr list --head codex/android-final-startup-ux`. Keep PR14
and previous APK as fallback. No main/merge/rebase/force push or deployment.
Backend cb3eaa1f9cbd857eb2fe0563ddaa81f501d75e87 and Gateway
 d1c0e4d2263626a30e81af9e2b40d5e952cb7b76 remain unchanged, no companion API change.

IMPLEMENTED: SDK58 expo-splash-screen native configuration, existing transparent T
foreground, matte#111316 day/night launch and post-splash window, explicit system
bar appearance and native-manager registration. Existing brand manifest and every
SVG/PNG hash unchanged. Old actual0.7.6 APK contained white splash color and Expo
circle/grid PNG. The new compiled-resource regression fails against that old APK.
No video file was attached to this task; its reported timing was not independently
measured. No Android emulator/phone available: native visual transition UNVERIFIED.

React startup uses same dark T asset; native splash releases on first branded layout,
not an internet check. No forced dwell. Theme read bounded750ms (dark fallback,
late response ignored); font wait at most2500ms (error/timeout enables text navigation,
no missing-font glyphs; later font readiness restores icons). Six-second native guard
is only a fail-safe for a missing layout callback. Root failure has actual retry;
never clears app/session data. Session restoration/network/worker not readiness gates;
no ONLINE inferred. System appearance is reapplied on foreground, not theme reset.

UX: compact home/context, explicit analysis account and secondary profile action,
conditional Pro chart immediately after decision, expensive research catalogue only
on expanded evidence, compact scanner health/detail disclosure with primary warnings
still visible. Settings connection lock remains visible; version details expandable.
Shared48dp controls, tabular numeric rows,14px body/21px line spacing, readable charcoal
and light surfaces; existing routes, Basit/Pro and all safety/401/403 gates preserved.

Executed before source checkpoint:223 Jest/49 suites; TypeScript/ESLint;19 local Expo
checks; Android+web JS exports;16 Python APK/brand/startup-tool tests; disposable native
prebuild/source verification. Web360px before/after fixtures and320/360px both-theme
smoke, no page errors/external requests/overflow. Controlled font stall exits loader.
Pictures docs/ux-before-* and ux-after-* are WEB renders. ux-native-resource-* are
DECODED DRAWABLES, not native screenshots. ux-react-loading-controlled.png is a WEB
font-stall capture, not Android cold-start footage. No phone performance/latency claim.

Internal0.7.7/code16, same package/signing policy. Required new Expo modules:
expo-splash-screen~58.0.11, expo-navigation-bar~58.0.4; install also updated three related
Expo build-tool patches. No general dependency overhaul/audit fix. Current npm audit47
(1low/43moderate/3high) remains; review @expo/cli,node-forge,zod reachability separately.
Online Expo Doctor not run. Final native CI/artifact/hash/certificate/source verification
must be read from the final Draft PR and appended evidence once completed.

Next safe step: verify exact-source native APK, compiled splash colors/style/MainActivity,
actual splash PNG vs unchanged T source, previous0.7.6 certificate, manifest/bundle/fonts,
artifact SHA256/expiry. Run existing clean-source HTTPS fixture harness if resources allow:
`python trade-ai/backend/scripts/release_candidate_e2e.py --android trade-ai-android --gateway trade-ai-gateway --output /tmp/final-ux.json`.
No financial/API changes. OpenAPI remains40paths/58schemas and hash729f422ae44c146a71b4bcd75f2f1df1c68ad07dddd9e9ed50619a80fa8f24eb.

After this bounded milestone, RETURN TO CORE ENGINEERING: scanner reliability/capacity,
provider/data quality, opportunity lifecycle, safe notifications, independent outage
monitoring, reviewed Windows unattended startup, historical/OOS/forward validation,
and separately authorized end-to-end physical-device continuity. No further general
cosmetic overhaul planned. Real provider/push/PC/autostart/device UNVERIFIED and not
activated. Do not access private systems, erase data, expand AUTO or alter risk rules.
