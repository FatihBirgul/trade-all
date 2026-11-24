# V8 financial and dated-rule validation

V7 asymmetric profit/loss tick conversion, cost-inclusive lot grid, gross/account-
currency vs geometric R/R, frozen absolute stop/TP, net1.5 minimum and gap losses
remain. Independent gold39/23 and asymmetric95/225 BUY/SELL oracles and four-asset/
non-USD fixtures were retained; fee/slippage stress and malformed conversion tests
were extended. No expected oracle calls the production calculation to derive itself.

costs.at_rules selects explicit declared epoch commission_round_trip_per_lot plus
currency, spread_price and slippage_price, falling back only to declared fixed-bps
simulation assumptions. Currency mismatch/nonfinite/negative/budget values refuse.
Entry and exit each charge half their effective round-trip commission. Independent
4→10 fee schedule oracle:2+5=7 per lot,400 gross→393 net, realized R393/104. Dated
SELL ask spread updates bid stop/target trigger mapping; levels remain frozen.
Current stop slippage and mark spread use effective assumptions. Entry risk caps
cannot guarantee later fee/spread/gap losses stay bounded; report preserves excess.

Tick/contract/currency and leverage/margin/swap-mode changes across open positions
are blocked pending explicit settlement/revalidation. Intrabar rule boundaries
are unsupported and refused. Historical gap rules use their effective time, not
today's broker hours. Actual swap/margin/PIT fee histories remain UNVERIFIED; no
source-uncertain net PnL is advertised as observed broker performance.

Official order_calc_margin(action,symbol,volume,price) is now allowlisted only for
read-only pilot estimates. It is not order_check/order_send, ignores existing
positions/pending orders per MT5 documentation and is not an execution approval.
https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcmargin_py
Actual terminal output was not available here; mock margin/profit and rejection
regressions passed. Tests: test_cost_oracle.py, test_v7_financial.py,
test_v7_api_invariants.py, test_v8_research_costs.py, test_v8_windows_pilot.py.
