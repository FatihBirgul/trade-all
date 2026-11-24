# True V2 confluence with provenance and veto

V6 Observation carries source/event/category/direction/strength/confirmation/age,
timeframe/known-at/algorithm/bucket. Future/unconfirmed observations are rejected.
Same-event same-direction duplicates are collapsed before actual V2
build_confluence; correlated OHLC categories share one price bucket even if a
caller changes the bucket name. Original V2 recency/confirmation/dedup math runs.
Input/removed/retained counts and source observations explain the transformation.

Opposing confirmed price observations veto before a bucket winner can conceal
conflict, even at unequal strength. Source V2 bucket confidence ratios are
heuristics, never success probabilities. Trend magnitude=min(100,20*EMA50 distance
in ATR); momentum magnitude=2*abs(WilderRSI-50), with no floors/bonuses. In range or
reversal context, trend is neutral and momentum direction follows RSI recovery,
not the trend-regime midpoint rule. Pattern is context; MTF/volatility/news and
unavailable volume cannot add independent directional forecasts. MTF conflicts
are checked separately against the selected setup.

Tests exercise the real reducer, duplicate events with spoofed buckets, opposing
unequal strength, future/unconfirmed evidence, and no volatility-only direction.
Pattern context may describe an opposing shape but cannot replace the canonical
strategy direction. Calibration and profitability remain UNVERIFIED.

## V7 continuation — current behavior

fx-provenance-confluence-v7-1 still executes the actual V2 reducer. Confirmed
trend/momentum/structure conflict is evaluated BEFORE event/bucket winner selection;
a strong descriptive pattern cannot hide opposing authority. related_event_id can
collapse the same underlying event across frames. Future/unconfirmed items include
rejection provenance; optional confirmation_at must also be as-of-known. Pattern,
MTF, news, volume and volatility are neutral context. Heuristic recency/strength
is not calibrated success probability. Default OHLC events remain correlated.
