# Market AI — PRD

## Original Problem Statement
Production-oriented Android app "Market AI" that analyzes financial market charts and crypto market data using uploaded chart screenshots (AI vision), real market OHLCV data, technical indicators, candlestick & chart patterns, market structure, volume/momentum, support/resistance, news/sentiment and AI reasoning. V1 focuses on CRYPTO (Binance). Provider abstractions for market data, news and AI so stocks/other exchanges/providers can be added later. Analytical decision-support tool — never guarantees, always explains WHY.

## Architecture
- **Backend**: FastAPI (`/app/backend`), MongoDB (motor). Modular package `market_ai/`:
  - `config.py` — env-driven providers + supported assets + timeframes
  - `providers/market_data.py` — `MarketDataProvider` abstraction + `BinanceProvider` (public `data-api.binance.vision`, no key)
  - `providers/news_provider.py` — `NewsProvider` abstraction + `NullNewsProvider` (honestly reports UNAVAILABLE)
  - `providers/ai_provider.py` — AI abstraction using emergentintegrations (GPT `gpt-5.6-terra`): vision pass + reasoning pass
  - `engines/technical.py` — deterministic EMA/SMA/RSI/MACD/StochRSI/ATR/Bollinger/Volume MA, swing pivots, support/resistance, market structure
  - `engines/candlestick.py` — 20+ candlestick patterns (context-aware classification + strength + explanation)
  - `engines/chart_patterns.py` — double top/bottom, H&S, triangles, wedges, channels, breakout/breakdown
  - `engines/analysis.py` — component scores → final analytical score + direction + zones (entry/T1/T2/invalidation/RR). `calibration` field reserved for future backtesting.
  - `models.py` — Pydantic BaseDocument (PyObjectId, no ObjectId leaks)
  - `server.py` — routes: config, assets, markets, market detail, klines, technical, analysis, history CRUD, news
- **Frontend**: Expo Router (`/app/frontend/app`), dark financial-terminal theme (`src/theme`), API client (`src/api/client.ts`), `MarketContext`. Screens: Home, Markets, Analyze, News, History (tabs) + Settings + Result.

## Providers / Keys
- Market data: Binance public mirror — WORKING, no key.
- AI: Emergent Universal Key (`EMERGENT_LLM_KEY`), model `gpt-5.6-terra` — WORKING.
- News: none configured — labelled UNAVAILABLE (waiting for user's news API key).

## Implemented (2026-06)
- [x] App shell, 5-tab navigation + Settings + Result, dark theme, reusable components (Phase 1)
- [x] Market-data provider abstraction + Binance crypto integration, live prices w/ polling (Phase 2)
- [x] Deterministic technical-analysis engine (Phase 3)
- [x] Camera + gallery chart upload with permission handling (Phase 4)
- [x] AI vision pipeline for chart images (Phase 5)
- [x] Combined analysis result screen: scenarios, entry/targets/invalidation, R/R, patterns, indicators, reasons, uncertainty labelling (Phase 6)
- [x] News architecture (Phase 7) — UNAVAILABLE state, ready for provider
- [x] History persistence with thumbnails + delete (Phase 8)
- [x] Candlestick (20+) + chart pattern engines
- [x] Error handling for missing market data / AI (technical fallback narrative)

## Backlog / Not yet implemented
- P1: Real news provider integration (needs user API key)
- P1: Chart-image coordinate-accurate annotation overlay (currently structured explanation beside image — coordinate mapping intentionally not drawn to avoid misleading lines)
- P1: WebSocket live price stream (currently REST polling)
- P2: Full backtesting engine over long history (interfaces reserved via `calibration`; outcome tracking now live)
- P2: Additional asset classes (stocks/BIST/US equities) via new providers

## Added 2026-06 (iteration 2)
- [x] Outcome tracking: `engines/outcome.py` evaluates each analysis vs real Binance price action (Target 1 before Invalidation) → win/loss/pending/neutral; endpoints `POST /api/history/evaluate-all`, `GET /api/performance`; History screen shows hit-rate performance card + per-item outcome badge + "Refresh outcomes"
- [x] Watchlist: star coins (persisted via `storage`) pinned to top of Markets (WATCHLIST section) and reordered first in Home chip row

## Next tasks
- Connect a news provider when key is available
- Schedule periodic outcome evaluation (background) instead of manual refresh
