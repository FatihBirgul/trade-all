# V8 release safety review

Only FatihBirgul/trade-ai-unified feature branch is written. Protected source/PWA/
Android/Gateway repos, main, production DB and private visibility are preserved.
Original MIT attribution and per-file migrated manifest retained. New V8 code has
its own dependency/provenance hashes in V8_SOURCE_PROVENANCE.json. No order paths,
account mutation, auto-paper or outbound notification/public deployment added.

SDK allowlist now adds only official order_calc_margin to retained read-only methods.
order_send/order_check/unauthorized operations still fail before SDK dispatch.
Initialization errors no longer echo raw last_error. Shareable Windows evidence
whitelists metadata/scalars, redacts path/email-shaped strings and genericizes errors.
It deliberately excludes account numbers, terminal/user paths and account cash data.

Local import root is operator-owned, not an HTTP input.8MB/2000 rows, strict format,
all-platform path/traversal/ADS/symlink/extension/hash/finality/source gates; no
archive extraction or unbounded Parquet decoding. Source identity/hashes are not
authentication. Cross-platform rooted path bug was found by real Windows CI, fixed
without weakening assertions, and retested. Hostile concurrent local writers and
public multi-tenant deployment are outside this local service threat model.

One active research job, request-only caches, locked provider init, bounded serial
alert/ledger/registry state, matching run-ID cancellation and failure cleanup constrain
shared state. Older analysis cannot consume future ledger context; malformed/revised
snapshots refuse rather than silently repair. Descriptive patterns cannot authorize
direction; stale/invalidated/future evidence rejected before actual V2 reducer.

Tests deny sockets/DNS and restrict SQLite to a new temp root. Source probes are
explicit separate read-only operations; official fetch has fixed hosts, no redirects,
8sec/512KB bounds, usage gate and no fixture fallback. No secret values were committed.
This is an offline engineering audit, not formal security/market/legal certification.
