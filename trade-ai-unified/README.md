# Trade AI Unified Forex V9 release candidate engineering

Read-only Forex/XAUUSD analysis backend integrating pinned Day Trader
V1-V5 and selected Trade AI V2 source. One canonical engine uses real QC/regime/
price-action/pattern/confluence/MTF/router code and retained broker risk/planning.
No real/demo order, paper execution service, production DB or frontend is included
in the runtime. Vendored stock compatibility code is isolated from the V6 host.

Python3.11/3.12, Linux/Windows source checkout:

```bash
python -m pip install -r requirements-lock.txt
python -m unified_forex
```

Local API:http://127.0.0.1:8006/docs. No live provider is fabricated on Linux; install
MetaTrader5 separately on Windows and configure the explicit symbol/contract/hours
inputs from `.env.example`. Missing broker identity/accepted declared schedule blocks plans.
Operator schedule declarations are labelled DECLARED, never authenticated metadata.
Environment loading is explicit in the shell; no secret-bearing `.env` is imported.

```bash
python scripts/check_sources.py
python scripts/run_suite.py engine
python scripts/diagnose_mt5.py
```

Source provenance/attribution:docs/SOURCE_MANIFEST.md and NOTICE.md. Architecture,
API contract, Windows setup, validation, missing families and milestone evidence
are in docs/. Source repositories/old PRs remain read-only. The original release branch was
`codex/unified-forex-engine-v6`. This directory is its public monorepo snapshot.

PRIVATE_INTEGRATED describes source reuse, not market readiness. Synthetic tests,
backtests/OOS and heuristic confluence do not prove profitability. Real Windows MT5,
broker schedules/costs, historical source/license and forward validation remain
unverified. Full pattern-family validation and macro coverage remain incomplete.

Current delivery: [Turkish A–N report](docs/V9_DELIVERY_REPORT_TR.md),
[41-route inventory](docs/V9_ROUTES.md), [OpenAPI](docs/V9_OPENAPI.json),
[validation evidence](docs/V9_VALIDATION.json), [scoped RC gates](docs/V9_GATES.json)
and [benchmarks](docs/V9_BENCHMARK_RESULTS.json). V9 retains `/api/v6`/schema6.
Baseline682 and final702 tests pass in Ubuntu/Windows Python3.11/3.12.

V9 adds declared paired bid/ask replay, hardened bounded local import, source-bound
FVG checkpoint ownership, local research preregistration/trial disclosure, sanitized
pilot input validation and opt-in checkpoint/forward observation interfaces.
Optional state/journal is disabled by default. [Data capabilities](docs/V9_MARKET_DATA_CONTRACT.md),
[security limits](docs/V9_SECURITY_AUDIT.md) and [Windows handoff](docs/V9_PILOT_HANDOFF.md)
state what each interface can establish. Real MT5, authenticated historical/PIT
archives, labelled family studies and market evidence remain unverified; Gate L
is UNVERIFIED. V6–V8 artifacts remain historical recovery evidence.
