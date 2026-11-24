# Pinned source migration

| Source | Branch | Commit | Destination | License |
|---|---|---|---|---|
| FatihBirgul/day-trader-skill | codex/forex-xauusd-backend-v1 | fdcdd418d96d05e71453e70c1f39956dd1cfe9d5 | vendor/day_trader | Original MIT and copyright retained |
| FatihBirgul/trade-ai | codex/trade-ai-v2-master-continuation | b69111608ea3c2e78609fd84a0d81dee2781c980 | vendor/trade_ai | Owner-authorized private reuse; no public license inferred |

`source_manifest.json` records every original/destination path, original SHA256,
source repository/branch/commit, license, test provenance and modifications. Source
A's full 155-file tracked snapshot preserves all423 tests and the eleven original
stock skill implementations. V6 only calls its analytical helpers; broker stock
approval code is outside the host. Source B is a selected41-file extraction: pure
technical/analysis/MTF/confluence/candle/chart, canonical QC, regime, price action,
router/strategies, immutable pure records/risk and continuation research methods.
No original paper ledger/product DB/service, automatic execution, Android/Gateway,
frontend or protected backup was copied. Pure paper_risk is computation, not order
execution. No source repository or old PR was modified.

Migrated validation:423 source A tests and152 selected pure source B tests pass.
The full original381 V2 baseline also passed in its isolated read-only source
checkout; excluded tests exercise excluded product/database/auto-paper components.
They are not represented as transferred or silently weakened.
