# V9 official macro coverage

Fresh fixed official URL probes on2026-11-06 are recorded with retrieval times,
payload hashes and event IDs in V9_OFFICIAL_SOURCE_PROBE.json. Fed57 (V8 was54),
ECB34, BEA169; BLS313 total/20 future. These are parser outputs for retrieved
payloads, not expected constants or an assertion of complete coverage.

Fed cross-month/year ranges (April/May, December/January) now preserve actual
meeting dates and DATE_ONLY semantics. An unknown release time is not replaced
with an invented precise instant. coverage_snapshot reports current/upcoming,
added/removed IDs, schema issues and payload identity against a supplied previous
snapshot. First retrieval has no previous-diff claim. This is observed change
monitoring, not authenticated vintage history or historical result revisions.

BLS/Fed/ECB/BEA adapters are retained. Source calendar dates, first retrieval and
actual published time remain separate; unavailable actual/previous releases are
not reconstructed. As-of cutoffs protect declared records, but an authenticated
historical release-vintage archive was not acquired. Macro remains risk context/
NO_TRADE veto only, never an independent BUY/SELL source.

BoE direct route remains unavailable (prior403); no access restriction bypass or
unverified substitute enabled. BoJ retrieval/redistribution remains disabled
USAGE_REVIEW_REQUIRED. No institutional permission was requested. Official URLs
and checksums do not grant source authentication or redistribution rights.
Default provider still requires explicit local configuration; no background
fetch. Coverage is partial and cannot protect against all material events.
