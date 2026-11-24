# Four explicit Forex variants

Original private crypto strategy specs/setups are preserved, not edited to remove
real-volume or crypto-market requirements. New price-only IDs/version1 are:

| ID | Eligible regime | Objective confirmation |
|---|---|---|
| fx_trend_momentum_v6 | trend/breakout | Actual V5 EMA20/50/200 + Wilder RSI/MACD trend or closed pullback |
| fx_range_reversion_v6 | range | Prior20 range width>=3ATR, efficiency<=0.3, edge rejection then close beyond previous bar and RSI recovery below45/above55 |
| fx_confirmed_breakout_v6 | trend/breakout | Two closes outside prior20 +0.25ATR, first body>=0.5ATR, current extension<=3ATR, RSI55..80 rising/20..45 falling |
| fx_failed_breakout_v6 | range/trend/reversal | Actual V2 prior sweep/reclaim, next close beyond sweep bar, body>=0.25ATR and RSI recovery below/above50 |

These are independently defined engineering variants, not volume-equivalent
substitutes or calibrated improvements. V2 route_strategy is actually called with
Forex/CFD identities and OHLC/verified broker-calendar capabilities. Confirmed
opposite directions veto before operational priority (sweep>breakout>range>trend).
Higher bias/lower trigger, confluence, session, high volatility and financial risk
can still remove a candidate. UNKNOWN regime waits. All four families have positive
real-OHLC/real-indicator tests; range/breakout negatives and sweep end-to-end reversal
are tested. Real-market edge/parameter calibration remains UNVERIFIED.

## V7 continuation — current behavior

Four existing Forex IDs are retained at strategy version2 / fx-price-setups-v7-1.
Strict frozen fx-price-params-v7-1 bounds range window, range/ATR, efficiency,
breakout buffer/extension and maximum setup age. Deterministic setup IDs prevent
the same closed candle being counted as a new setup. Invalid/old setups remain
WAIT. Closed-candle/session/spread/MTF/regime/conflict/cost gates remain mandatory.
No crypto strategy requirement was loosened. Parameter changes are hashed; they
are not optimized live. OOS currently searches declared route/cadence candidates,
not arbitrary indicator parameter spaces.
