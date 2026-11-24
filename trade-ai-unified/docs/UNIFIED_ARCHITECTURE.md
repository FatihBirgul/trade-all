# One canonical private engine

`AnalysisEngine.analyze` owns the only V6 decision. It calls V5 capture/provider,
actual V2 whole-batch QC/capabilities, cached canonical V5 technicals and named V2
variants, actual V2 regime/price action/candles/charts/MTF/confluence/router, then
V5 plan/risk/lot functions. Source files are owned in this private checkout. There
is no optional private import fallback, second competing final BUY/SELL engine,
AI direction override, ledger, worker or execution gateway.

Data and candle timestamps come from one owned snapshot. Higher and lower frames
are intentionally cut at primary close; malformed primary data is rejected.
Broker-schedule provenance is explicit; exact gaps are passed to V2 QC only after
V5's schedule-aware checks. M30 and explicit CFD identity are supported. Tick
volume never becomes real volume. Per-request/scanner resource cache reads each
provider resource once. Optional broker profit calculation remains explicit I/O.

Strategies use separately versioned price-only Forex IDs. Original crypto setups
retain their market/volume constraints. V2 router chooses analytical eligibility;
confirmed opposing evidence/setups, MTF, session, spread and risk retain veto.
Pattern/MTF/volatility context cannot become extra independent price forecasts.
The same existing V5 ATR/tick plan helper serves compatibility and V6 paths.

Runtime: source checkout, `python -m unified_forex`,127.0.0.1:8006. Numerical/ASGI
dependencies are pinned, Python3.11/3.12 supported. Original source tests run in
separate processes to preserve their import namespace and expectations. No source
repo, production database or existing local Windows/PWA application is modified.

## V7 continuation — current behavior

Engine7.0 retains the canonical host and /api/v6 schema6 compatibility. New modules
extend, rather than replace, the pinned source algorithms: candle_extensions,
chart_geometry (V2 pivots/slope), structure_events (V5 pivots/V2 action), divergence,
provenance, experiments, macro and diagnostics. No second final decision engine.
Optional historical epochs are selected at event time. API research has one active
workload slot, provider construction is locked, alert evaluation serialized. Cache
is request-only and reports hits/misses. Algorithm/source hashes remain explicit.
