# Execution-free private host review

This repository was verified PRIVATE before private source migration/publication.
Only this feature branch is writable. Source A/B and their PRs stay unchanged; no
new repo, visibility change, main merge, force push, backup deletion or production
DB is performed. Original MIT notice is retained; private code gets no inferred
public license. Hashes bind source content, not provider truth or legal permission.

Selected source excludes paper ledger, product DB, auto-paper, analysis service,
Gateway/Android/frontend and protected backups. An initially migrated unused V2
legacy aggregate was explicitly removed as a duplicate final-decision path; actual
V2 confluence/router remain. Pure record/risk math is preserved for source contracts
and tests, not execution. The old stock broker snapshot is compatibility-only and
not imported by V6. AST/runtime tests reject order methods and product imports.
No real/demo order, position close, external notification or hidden feed fallback
is connected. Research is in-memory simulated fills with orders=0, no ledger/SQLite.

API starts127.0.0.1 only, one worker. Provider calls and workloads are bounded;
request/scan cache avoids repeated quote/meta/frame reads. Broker profit calculation
is explicit read-only I/O. Shutdown closes provider resources. API errors redact
unexpected exception detail. Manual record/payload sizes and finite values are
bounded. Offline tests deny sockets/DNS and constrain temporary SQLite.

Source snapshots/historical metadata are owned; future/unfinished/mixed identity
or source is rejected. Verified exact session-gap intervals are explicit, not a
blanket removal of gap checks. Confluence preserves opposing evidence before bucket
ranking; no arbitrary confidence floor or success probability is produced. News
coverage and schedule assertions remain declarations until verified.

Authentication/HTTPS/public hosting and a concurrent hostile multi-tenant threat
model are not implemented or deployed here. Optional Windows binding/terminal,
real broker metadata/calendar/DST and source/license/cost archives remain unverified.
No claim of market or legal certification is made.

Final provider boundary additionally allowlists only the existing read-only SDK
operations before getattr dispatch. A requested order method is rejected before the
SDK mock can be called. Source regressions validate existing lifecycle/profit reads.
No execution permission can be enabled by an API field or operator contract map.

## V7 continuation — current behavior

V7 review preserves the read-only SDK allowlist and rejects forbidden operations
before dispatch. Actual source clones remain clean at pinned SHAs. Private visibility
and existing draft PR are retained. Strict bounded API input, request-local caches,
locked provider initialization, serialized bounded alert state and one-active research
slot constrain local workloads. Experiment registry is memory-only, no client file
paths and no product DB. BLS fetch is explicit, fixed official HTTPS URL, no redirects,
8-second timeout/512KB bound and no fixture fallback; analysis/startup never invokes
it implicitly. Forecast actual values cannot appear before release/knowledge time.
Public authenticated hosting, multi-tenant deployment, real MT5 and legal/source
certification remain outside delivered evidence. No order or external message sent.
