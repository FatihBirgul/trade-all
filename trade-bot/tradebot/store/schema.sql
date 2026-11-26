-- Tum ifadeler tekrar calistirilabilir (IF NOT EXISTS). Zamanlar UTC epoch saniyedir.

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id TEXT NOT NULL UNIQUE,
    origin TEXT NOT NULL CHECK (origin IN ('bot', 'manual')),
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    volume REAL NOT NULL,
    initial_volume REAL,
    entry REAL NOT NULL,
    sl REAL,
    tp1 REAL,
    tp2 REAL,
    initial_risk_r_price REAL,
    risk_amount REAL,
    strategy_id TEXT,
    setup_id TEXT UNIQUE,
    score REAL,
    opened_at REAL NOT NULL,
    closed_at REAL,
    close_price REAL,
    pnl REAL NOT NULL DEFAULT 0,
    user_sl_override INTEGER NOT NULL DEFAULT 0,
    manage INTEGER NOT NULL DEFAULT 1,
    sltp_order_id TEXT,
    be_done INTEGER NOT NULL DEFAULT 0,
    partial_done INTEGER NOT NULL DEFAULT 0,
    last_sl REAL,     -- broker'in en son onayladigi SL (SL/TP emri iptal olsa da silinmez)
    planned_tp REAL,  -- planlanan TP (broker'daki TP kaybolursa yeniden kurmak icin)
    votes_json TEXT   -- giristeki modul oylari (karne icin)
);
CREATE INDEX IF NOT EXISTS trades_open ON trades (closed_at) WHERE closed_at IS NULL;

-- Gerceklesen kar/zarar: her kapanis deal'i tam bir kez (WS olayi ve mutabakat ayni deal'i getirebilir).
CREATE TABLE IF NOT EXISTS realized (
    deal_id TEXT PRIMARY KEY,
    trade_id INTEGER NOT NULL REFERENCES trades (id),
    at REAL NOT NULL,
    pnl REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS realized_at ON realized (at);

-- Sanal (golge) islemler: emir gonderilmeyen adaylarin izlenen sonucu.
CREATE TABLE IF NOT EXISTS shadow_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    strategy_id TEXT NOT NULL,
    setup_id TEXT NOT NULL UNIQUE,
    reason TEXT NOT NULL CHECK (reason IN ('shadow', 'low_score', 'paused')),
    entry REAL NOT NULL,
    sl REAL NOT NULL,
    tp REAL NOT NULL,
    score REAL,
    opened_at REAL NOT NULL,
    closed_at REAL,
    result_r REAL,
    spread REAL
);
CREATE INDEX IF NOT EXISTS shadow_open ON shadow_trades (symbol) WHERE closed_at IS NULL;

-- Para yatirma/cekme (balance turu deal): her biri tam bir kez islenir (WS olayi ve gecmis ayni deal'i
-- getirebilir). applied = 1 ise tutar kayip siniri tabanina (start_capital) eklenmistir.
CREATE TABLE IF NOT EXISTS balance_ops (
    deal_id TEXT PRIMARY KEY,
    at REAL NOT NULL,
    amount REAL NOT NULL,
    applied INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    idempotency_key TEXT PRIMARY KEY,
    setup_id TEXT,
    kind TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'bot',
    state TEXT NOT NULL CHECK (state IN ('PENDING', 'ACKED', 'FILLED', 'REJECTED', 'UNKNOWN', 'CANCELLED')),
    operation_id TEXT,
    position_id TEXT,
    error TEXT,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS orders_operation ON orders (operation_id);
CREATE INDEX IF NOT EXISTS orders_state ON orders (state);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at REAL NOT NULL,
    level TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    data_json TEXT
);

-- Son 30 dakikanin spread ornekleri (tick tick, ozetlenmeden): yeniden baslatmada "spread ornegi yok" bekleme
-- suresi olmasin diye saklanir. Kural degismez; yalnizca pencere icindeki ornekler geri yuklenir
-- (tradebot/market/quotes.py). Eski satirlar her kayitta silinir.
CREATE TABLE IF NOT EXISTS spread_ticks (
    symbol TEXT NOT NULL,
    at REAL NOT NULL,
    spread REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS spread_ticks_at ON spread_ticks (at);

-- Ozet ucu ve temizlik zamana gore okur.
CREATE INDEX IF NOT EXISTS events_at ON events (at);

CREATE TABLE IF NOT EXISTS equity (
    at REAL PRIMARY KEY,
    balance REAL NOT NULL,
    equity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    halted INTEGER NOT NULL DEFAULT 0,
    halt_reason TEXT,
    stopped INTEGER NOT NULL DEFAULT 0,
    start_capital REAL,
    start_at REAL,
    last_scan_at REAL,
    heartbeat_at REAL
);
INSERT OR IGNORE INTO bot_state (id) VALUES (1);

CREATE TABLE IF NOT EXISTS api_tokens (
    token_hash TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    label TEXT
);

CREATE TABLE IF NOT EXISTS pair_codes (
    code_hash TEXT PRIMARY KEY,
    expires_at REAL NOT NULL,
    used INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS devices (
    expo_token TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);
