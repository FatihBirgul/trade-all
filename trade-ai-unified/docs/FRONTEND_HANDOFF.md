# Backend handoff; frontend untouched

Use POST /api/v6/analysis and its generated OpenAPI. Display final decision, candidate,
data health, broker session, account eligibility and source integration separately.
Do not render null levels as0 or interpret candidate/ELIGIBLE as permission to trade.
Show provider/test labels, primary close/as-of, algorithm/source versions, conflict
and veto reasons, missing capabilities and the unverified-market warning.

V5 clients can keep POST /api/v5/analysis; V1 three-state clients retain their paths.
Canonical strategy IDs are new Forex variants, not renamed crypto methods. Explicit
method variants differ in seed/smoothing/variance and should retain those labels.
News/calendar may be unavailable or source-declared with unverified coverage. Pattern
missing families and structural geometry gaps remain explicit.

No PWA, Android, Gateway or local Windows project files were changed. API defaults
to localhost. MT5 must be running on the actual Windows machine for live data; a
powered-off PC cannot provide live prices. This task does not deploy public hosting,
HTTPS/auth or external alert delivery. Real Windows validation is a separate chat.

## V7 continuation — current behavior

Use V7_OPENAPI.json / V7_ROUTES.md / V7_RESPONSE_EXAMPLES.json. Engine7.0 retains
schema6 paths; frontend changes are not made here. Render broker_schedule.trust
and authenticated separately from open/closed state; DECLARED is not source-verified.
Patterns DESCRIPTIVE/CANDIDATE/CONFIRMED refer to geometry, never order permission.
Show rule-history/coverage, dataset license uncertainty, cost model, actual source
and all refusal/null states. Numeric confidence is not future win probability.
Research429 should offer a later retry; experiments404 means not present in the
bounded memory registry. Alerts dedup resets on process restart. API remains local.
