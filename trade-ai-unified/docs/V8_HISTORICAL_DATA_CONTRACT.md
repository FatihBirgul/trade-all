# V8 local historical import and trust

Use scripts/import_history.py --root <operator-owned-root> --file <relative.csv>
--declaration <relative.json>. It reads files only and writes a report to stdout.
No API endpoint accepts a local path. Root is chosen by the local operator, not a
remote client. CSV/JSON are implemented. Parquet is deliberately UNAVAILABLE:
no bounded decoder is installed, no new mandatory dependency and no decompression
before resource validation. Export Parquet to reviewed CSV/JSON as a separate step.

Strict rows: open_time_ms,close_time_ms,open,high,low,close,is_final,symbol,source,
contract_type, optional declared tick volume. Times are integer UTC milliseconds;
CSV finality is true; JSON finality is boolean true. Only explicit bid candles are
accepted; ask/mid require a different execution model and are rejected. Timeframe
is declared5m/15m/30m/1H/4H/1D. OHLC/source/contract/venue/symbol, finality, chronological
order/duplicates, alignment, finite positive prices, future/acquisition time and
permitted closed-session gaps are validated. Input is never silently sorted/fixed.

Bound8MB/2000 candles, no archives/extraction. Reject POSIX absolute/rooted, Windows
drive/rooted/UNC/drive-relative/ADS paths, both traversal separator forms, symlinks,
unsupported extension, oversized/changing input, duplicate JSON keys/CSV headers,
NaN/Infinity and raw-hash mismatch. Windows CI exposed /etc/passwd rooted-path
semantics; the boundary was fixed, assertions retained, then matrix rerun.
Operator-owned root is assumed; hostile concurrent local filesystem writers are
not a multi-tenant sandbox model. O_NOFOLLOW is used where supported.

ImportDeclaration binds source/venue/symbol/contract, broker symbol, acquisition,
timezone/license/use declaration, version, rules and optional epochs. Report carries
raw hash and normalized dataset hash separately. Spread history is unavailable and
requires explicit modelling. Strong SOURCE_VERIFIED/POINT_IN_TIME_VERIFIED remain
reserved; no input flag grants authentication. Tests/data/v8_handmade.csv is an
original hand-written CC0 synthetic fixture, not downloaded Forex data. CSV/JSON
normalization and adversarial imports are tested in test_v8_ingestion.py.
