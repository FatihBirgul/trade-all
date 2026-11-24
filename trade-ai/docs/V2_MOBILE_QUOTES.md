# Additive read-only mobile quotes

`GET /api/v2/quotes`, existing V2 bearer authentication. No user-supplied URL,
symbol list or execution action. Fixed BTCUSDT/ETHUSDT/SOLUSDT public spot reads.
The existing V2 paths/schemas and analysis/ledger/scanner algorithms are unchanged.
No DB writes, migrations or additional workers are introduced.

One 24hr ticker batch per 30 seconds per process. Source closeTime is the rolling
statistics end, not a claimed last-trade timestamp. History is at most 24 final
1H closes, refreshed at most every five minutes. Missing charts remain empty.
Public host/path allowlist, no redirects/environment proxy, bounded body/timeouts,
finite decimal validation and source-time checks. No API key or trading endpoint.
All shared cache fetches are serialized; failures are also throttled. Previously
successful rows can be returned with stale=true/provider_status=unavailable;
without a valid cache a 503 is returned. Fixture mode never returns live quotes.
The Android caller must independently mark old cached data as not current.

Primary API reference checked 26 October 2026:
https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints

Upgrade requires this branch's backend files plus gateway/Android contract update.
Existing Windows processes are NOT automatically upgraded. Stop gracefully, keep
the existing V2 DB and environment, deploy reviewed files, restart the same local
127.0.0.1:8002 service. Never reset/copy over the DB or change execution policy.
Do not expose a public listener. New endpoint physical phone/provider verification
is pending; controlled HTTP fixtures and temporary DBs are used for automation.
