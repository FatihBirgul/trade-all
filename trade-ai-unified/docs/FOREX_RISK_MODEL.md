# Retained broker financial model

Actual V5 build_plan (extracted from analyze), risk_check, size_lots and policy.assess
serve V6. BUY enters ask, SELL bid; stops/targets round outward on broker tick grid.
ATR1.5 and broker stop-level/spread/tick floor are retained. A strategy invalidation
can only widen the stop; size then decreases under the same risk cap. TP1/2 retain
2R/3R geometry. Broker direction/session/spread and manual daily loss/count/risk
records retain veto. No balance yields no verified lot/account eligibility.

Round-trip commission is account currency per lot; stop slippage is adverse price
allowance. Spread is already in executable price sides and not added again. A
positive broker result cannot be called stop loss; minimum lot above cap blocks;
final lot stays on min+step grid. Daily aggregate compares unrounded loss. Account
currency must be an explicit uppercase3-letter identity; declared tick value must
be in it unless the actual broker profit callback supplies account-currency loss.
Fixtures use tick/currency validation instead of pretending their linear helper
is a real broker oracle. Margin/swap/leverage remain unavailable unless verified.

Retained independent financial/golden and new end-to-end BUY/SELL/risk cases run.
Gap losses can exceed planned risk and even account equity; historical results
preserve that loss instead of clamping it away. Caller records and schedule
assertions are declarations, not broker reconciliation. Real Windows MT5 validation
is UNVERIFIED; no real/demo order or position-close path is connected.

Final net-RR gate: account-currency TP1 reward subtracts round-trip commission;
adverse-stop loss includes that commission and stop-only slippage. Verified broker
profit samples are used when available; otherwise verified account-currency tick
value is required. net_reward_risk must be>=1.5 even for an unsized candidate.
Gross and net ratios are separate fields. Independent BUY/SELL oracle:195/115=39/23
for $200 gross reward, $100 stop, $10 adverse-stop and $5 commission per lot. Known
excessive costs veto instead of producing a superficially attractive gross2R plan.
Historical replay applies the same gate on known signal costs and actual next-open
fill costs. Unknown margin/swap/true historical costs remain unavailable/unverified.

## V7 continuation — current behavior

forex-cost-netrr-v7-1 preserves v6-2 cost mathematics for equal tick values, adds
separate tick_value_profit/loss fallback when declared, and keeps authoritative
read-only broker profit calculation when available. Positive stop profit is denied.
Gross ACCOUNT-CURRENCY R/R and geometric price R/R are distinct when conversions
differ. Commission is one round trip per lot, subtracted ONCE from reward and added
to planned loss; stop-only adverse exit slippage enters loss. Historical execution
also applies adverse entry slippage. Independent BUY/SELL gold oracle195/115 and
asymmetric95/225 pass, as do EURUSD/GBPUSD/USDJPY and non-USD synthetic account-unit
oracles, min-lot/grid/currency guards. No missing metadata invents a lot.

Replay preserves known absolute stop/TP at next open; SELL ask execution levels are
converted to bid trigger levels. Unfavorable fills fail geometry/net-RR gates rather
than moving targets. Realized R is net account PnL/initial cost-inclusive risk.
Negative gap equity is preserved. Fees are reported; legacy *_quote monetary fields
are explicit ACCOUNT_CURRENCY aliases. Swap/margin remain UNAVAILABLE; leverage/
free margin in diagnostics are information only. No solvency guarantee or real
broker conversion/swap/margin verification is claimed.
