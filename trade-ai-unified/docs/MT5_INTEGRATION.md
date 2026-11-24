# Windows read-only handoff (real terminal: UNVERIFIED)

Use a separate checkout of this PRIVATE repository on the user's Windows machine;
no existing PWA/MT5 project is changed. Suggested shell steps:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.venv\Scripts\python.exe -m pip install MetaTrader5
.venv\Scripts\python.exe scripts\diagnose_mt5.py
.venv\Scripts\python.exe -m unified_forex
```

The optional official MetaTrader5 binding is not installed or required in Cloud CI;
its actual Windows version/terminal/broker compatibility must be recorded during
that pilot. Open the terminal and log in manually, preferably to the intended demo
account; do not pass credentials to this program or commit them. No order is needed
or authorized for the diagnostic. The retained provider uses initialize/health,
symbol mapping/select, quote, closed rates, metadata, order_calc_profit and shutdown
only. V6 closes the provider on API shutdown; reconnection/locking are retained.

Explicit environment declarations (see .env.example): MT5_SYMBOL_MAP,
MT5_MAX_SPREAD, MT5_BROKER_HOURS, MT5_INSTRUMENT_CONTRACTS. No file auto-load is
assumed: set variables in the shell. Real suffix and contract identity must match
the broker. Source/broker calendar verification requires broker_hours_verified=true
AND schedule_source evidence; the supplied example is intentionally false/empty
and blocks plans. Declarations cannot override broker tick/grid/currency/permissions.
Never guess spot versus CFD from XAUUSD or label tick volume real.

Local checks: GET http://127.0.0.1:8006/api/v6/health and /docs; POST
/api/v6/analysis with symbol/timeframe. Confirm source, broker symbol, fresh tick,
closed as-of history, lot grid/account currency, stops/spread and session boundary.
Missing provider may return503; analytical refusal remains explicit. The health
response does not certify financial/live readiness. Margin/swap/real fees and
broker D1/DST timestamps still require verification (D1 duration remains86400s).
PC/terminal off means no promised live data. HTTPS/auth/remote hosting are separate.

## V7 continuation — current behavior

Run python scripts/diagnose_mt5.py on the separate Windows terminal. It composes
the retained diagnostic and adds bid/ask/tick age, exact symbol/server, digits/point,
profit/loss tick values, contract/volume/stops/freeze/mode/directions, account currency,
free margin/leverage and read-only min-lot BUY/SELL loss-sign samples. No order_send,
order_check or account mutation is allowlisted. Operator schedules are DECLARED,
never authenticated. UNKNOWN schedule blocks new plans. Full-day/partial holiday
overrides supersede yesterday's overnight window. IANA session DST logic remains.
Real terminal/session/D1 broker-DST semantics, conversion and fee archives still
need the user's Windows pilot; mt5_validation remains UNVERIFIED.
