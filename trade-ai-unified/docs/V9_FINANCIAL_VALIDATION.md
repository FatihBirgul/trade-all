# V9 financial and point-in-time validation

VERIFIED_OFFLINE mechanical accounting; IMPLEMENTED_UNVERIFIED_IN_MARKET.
Retained V7/V8 independent goldens cover XAUUSD/EURUSD/GBPUSD/USDJPY, USD/EUR/JPY,
asymmetric tick profit/loss, lot grid/minimum risk, missing conversion, fee/spread
jumps, cost-inclusive net-RR and frozen absolute stop/target. Existing production
calculator is not used to derive expected oracle values. V8_FINANCIAL_VALIDATION.md
records retained commission 2+5=7 and 400 gross ->393 net dated-fee oracle.

V9 paired-side BUY enters ask open plus declared slippage, exits bid OHLC;
SELL enters bid open minus slippage, exits ask OHLC. SELL mark uses ask close.
New independent oracle: bid2000/ask2000.2, BUY stop1999/target2004 gives380*lots
net and380/120 R with100 currency units/price/lot and zero costs. Independent
SELL ask spike reaches2001 while bid high remains2000.5: stop triggers on ask,
loss100*lots. No inferred constant spread replaces supplied ask extrema.
Stop/target overlap uses conservative stop-first and an explicit ambiguity flag.
Gap execution and entry/stop slippage remain declared simulation, not broker fill.
Commission charges half each side's effective round-trip schedule; entry risk
cannot guarantee later gaps/fee jumps remain under the original risk cap.

HistoricalDataset now refuses epoch broker/server/source/contract/price-side
mismatch and account-currency redenomination even while flat. Tick-value currency
must match account evidence; unsupported conversion fails closed. Retained open
position contract/tick/currency/margin/swap-mode changes and intrabar rule changes
are refused. The historical quote timestamp is the last actual closed bar, never
advanced to the replay clock. This avoids creating synthetic quote freshness.

Margin and swap remain UNAVAILABLE in replay. Trading hours, holidays, spread,
slippage, commissions and rule effective bounds are operator-declared, not an
authenticated PIT broker archive. Actual rollover settlement, historical conversion,
margin and profit reconciliation require real terminal/archive evidence. No
verified broker net performance or live financial validation is claimed.

Evidence: test_cost_oracle.py, test_v7_financial.py, test_v7_api_invariants.py,
test_v8_research_costs.py, test_v9_bidask.py, test_v9_pit_safety.py.
