# Price action: integrated, market interpretation unverified

V2 compute_price_action supplies strict2/2 confirmed pivots, one-time BOS/CHoCH,
formed-time ATR FVG and previous-window sweep/reclaim. V5 market_structure supplies
its retained confirmed pivot lists/close-time availability. Both definitions are
labelled; no rolling extrema are presented as confirmed swings. V6 derives bounded
S/R bands (+/-max(tick,0.1ATR)) and equal last confirmed highs/lows within that
versioned tolerance. No order-book volume or institutional execution is inferred.

A prior closed sweep followed by a close beyond that bar's opposite extreme sets
REVERSAL_CANDIDATE context; this does not override MTF/risk/strategy confirmation.
The prior price-action result is computed once and reused by regime and setup.
Break/retest/failure events come from the actual bounded V2 chart adapter. Structure
invalidation remains a geometric closed-price rule; real broker validation and
broader zone-family calibration are UNVERIFIED. Positive/prefix/right-confirmation,
repeat-break and gap tests are retained; V6 sweep follow-through is tested end-to-end.

## V7 continuation — current behavior

fx-structure-lifecycle-v7-1 exposes HH/HL/LH/LL/equality, confirmed swing events,
BOS/CHoCH, retest, invalidation and expiry over retained confirmed pivots. Event IDs
bind instrument/frame/origin; origin and first-known are distinct UTC milliseconds.
Range boundaries are prior20 OHLC. FVG retains V2 ACTIVE-ONLY scope: a full historical
filled-gap/expiry ledger is still PARTIAL. Sweep is a closed reclaim candidate,
follow-through remains necessary. No order-book/institutional-liquidity evidence.
