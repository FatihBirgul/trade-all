# Indicator definitions and validation

Canonical V5 variants are unchanged: EMA9/20/21/50/100/200 use SMA seed then
2/(n+1); SMA20/50 trailing means; RSI14 uses14-change SMA-seeded Wilder recurrence;
MACD12/26/9 uses SMA-seeded EMAs; ATR14 uses trailing simple true-range mean;
Bollinger20/2 uses population variance. Minimum canonical history200 closed bars,
normal window220. Same-snapshot EMA scalars and ATR are cached rather than
recalculated for each output field. Previous-close indicators are separate as-of
observations, not future values.

Actual V2 rolling RSI14 and stochastic RSI14/3 are named separately; stochastic
RSI reuses the rolling RSI vector. V2 Decimal research retains ROC12, stochastic14,
previous20 Donchian, sample-variance BB bandwidth, ADX14/DMI/Wilder ATR and
Supertrend10/3. Original seeds, warmups and undefined-flat statuses remain. V6
momentum is MACD histogram change; volatility is current ATR14 / preceding20 TR
mean (>1.8 high,<0.55 low), non-directional and versioned. Real-volume/anchored VWAP
is UNAVAILABLE without appropriate source/anchor; tick volume is not substituted.

Independent arithmetic fixtures from V5 cover EMA linear sequence, MACD7/7/0,
ATR2, population variance33.25 and Wilder100*(13/14)^14. Retained V2 pure tests
check rolling RSI, seed differences, warmup, ADX/Supertrend/stochastic/Donchian/ROC,
Decimal context and sample/population differences. Default formulas were not
silently changed to force parity. Every report includes algorithm/source hashes.
Flat/zero RSI range yields null stochastic RSI, not a fabricated midpoint.

## V7 continuation — current behavior

fx-aligned-divergence-v7-1 adds regular/hidden bullish/bearish divergence over actual
SMA-seeded MACD and retained Wilder RSI. Price and indicator strict2-left/2-right
pivots align within2 bars; each indicator pivot is used once. Knowledge time is the
latest of all four confirmation times. Tests independently specify asynchronous
price/indicator extrema, all four directions, flat negative and prefix exclusion.
Divergence is descriptive, not a new independent momentum vote. Canonical variants,
original golden fixtures and warm-up gates are retained.
