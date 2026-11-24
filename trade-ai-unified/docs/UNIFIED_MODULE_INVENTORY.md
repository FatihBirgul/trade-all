# Functional module register

Exact original/destination paths, source branches/SHAs, licenses, content hashes and
adaptation notes are in source_manifest.json. Both source trees remain unchanged.

| V6 module | Actual reused entry points | Contract / decision role | Status |
|---|---|---|---|
| market.py | V5 capture/Snapshot/provider_read; V2 Instrument/Candle/validate_series/candle_capabilities | Owned identity/finality/quote/session-gap/as-of data and capabilities | COMPLETE offline |
| technical.py | V5 indicators/scanner.rsi; V2 rsi/stoch_rsi/compute_methods/classify_regime | Named variants/warmup, non-directional volatility, regime | COMPLETE OHLC; volume methods unavailable |
| patterns.py | V2 compute_price_action/detect_patterns/detect_charts; V5 market_structure | Confirmed structure/zones/equality, catalogue and one modified-Hikkake variant | PARTIAL catalogue/geometry |
| mtf.py | V2 mtf.analyze/normalization/rank | Primary/higher/lower context over same decision-close view | COMPLETE offline |
| confluence.py | V2 Evidence/build_confluence | Provenance/event and correlation dedup, conflict-preserving veto | COMPLETE offline; calibration unverified |
| strategies.py | V5 candidates/closed_bar_breakout; V2 route_strategy | Four versioned price-only Forex families, original crypto gates preserved | COMPLETE engineering; market edge unverified |
| engine.py | Above plus V5 build_plan/risk_check/policy.assess/size_lots | Single canonical decision/risk/plan/report | COMPLETE selected integration |
| research.py | V5 first_exit/microstructure/grid/bootstrap; actual V2 walk_forward/Manifest/summarize | In-memory replay, training-only selection and frozen test | PARTIAL real-data provenance |
| services.py | V5 AlertEngine, parse_rss, macro contracts | Cached scanner/local alerts/declared information | PARTIAL live providers/delivery |
| providers.py | V5 MT5Provider lifecycle/lock/profit | Strict declared identity/schedule, broker metadata retained | UNVERIFIED actual Windows |
| api.py | V5 FastAPI models/data/risk routes, V6 engine | Versioned typed report and old route mapping | COMPLETE offline; hosting separate |

Required original Day Trader calls remain real: scanner.rsi, entry.closed_bar_breakout,
exit.atr_of, timemachine.first_exit, news.parse_rss/dedupe. Stock share/NYSE/broker/
SEC/disclosure modules stay compatible references, not Forex inputs. The private
crypto pipeline/strategies/technical adapter remain unchanged in their default
eligibility: absent real volume/calendar does not silently become a valid FX route.
Only separately tested new Forex IDs add OHLC alternatives. Original analysis_service,
ledger and auto-paper are absent from the runtime and cannot place orders.
