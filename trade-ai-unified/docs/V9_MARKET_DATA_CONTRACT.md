# V9 historical price-side contract

`data_sides.py` version fx-price-sides-v9-1 extends retained V8 ingestion/research;
it does not add another engine. Machine capabilities: V9_DATA_CAPABILITIES.json.

| Type | Canonical analysis | Replay capability |
|---|---|---|
| BID_OHLC | Yes | Bid with explicitly modelled spread |
| ASK_OHLC | No | Missing bid; refused |
| BID_ASK_OHLC | Yes, bid analysis | Declared paired side bars and costs |
| QUOTE_TICKS | No | Bounded schema/identity/chronology validation only; no tick executor |
| MID_ONLY | No | Execution side unknown; refused |
| MODELLED_SPREAD | No standalone candles | Assumption bound to declared price/rule dataset |
| EXECUTION_COST_ARCHIVE | No standalone candles | Must bind effective rules and prices; not autonomous execution evidence |

CSV/JSON import accepts BID_OHLC or BID_ASK_OHLC. Paired rows add ask_open,
ask_high, ask_low, ask_close, ask_source to retained bid fields. Ask source must
match declared bid source; instrument, venue, contract, volume kind, timeframe,
counts and UTC open/close times must agree. Every corresponding ask OHLC value
must be >= bid. Retained series QC validates OHLC/finality/gaps; dataset hash owns
both sides. Limits: raw 8,000,000 bytes; 1..2000 rows/frame; paired dataset <=6000
bars total. See ImportDeclaration for exact field whitelist and declared gaps.

Observed side bars are DECLARED_OBSERVED_SIDE_BARS. Their highs/lows are not
simultaneous tick quotes and cannot establish intrabar order or an actual fill.
Bid-only reports MODELLED_SPREAD; cost evidence remains DECLARED. Checksums,
license declarations and passed QC never authenticate a broker or legal rights.
No licensed market archive was supplied. VERIFIED_BID_ASK_REPLAY is unavailable.
Parquet remains UNAVAILABLE: no bounded decoded-row/size optional decoder or
cross-platform validation was established; no heavy mandatory dependency added.
