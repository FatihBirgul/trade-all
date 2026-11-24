"""Central configuration for Market AI backend.

Everything credential/provider related is read from environment variables so the
project stays deployable outside Emergent with no source changes.
"""
import os

# --- Providers (swappable via env) ---
AI_PROVIDER = os.environ.get("AI_PROVIDER", "openai")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-5.6-terra")
MARKET_DATA_PROVIDER = os.environ.get("MARKET_DATA_PROVIDER", "binance")
NEWS_PROVIDER = os.environ.get("NEWS_PROVIDER", "none")

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

# --- Supported crypto assets for V1 ---
SUPPORTED_ASSETS = [
    {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT", "name": "Bitcoin", "asset_class": "crypto"},
    {"symbol": "ETHUSDT", "base": "ETH", "quote": "USDT", "name": "Ethereum", "asset_class": "crypto"},
    {"symbol": "SOLUSDT", "base": "SOL", "quote": "USDT", "name": "Solana", "asset_class": "crypto"},
    {"symbol": "BNBUSDT", "base": "BNB", "quote": "USDT", "name": "BNB", "asset_class": "crypto"},
    {"symbol": "XRPUSDT", "base": "XRP", "quote": "USDT", "name": "XRP", "asset_class": "crypto"},
    {"symbol": "ADAUSDT", "base": "ADA", "quote": "USDT", "name": "Cardano", "asset_class": "crypto"},
    {"symbol": "DOGEUSDT", "base": "DOGE", "quote": "USDT", "name": "Dogecoin", "asset_class": "crypto"},
]

SUPPORTED_SYMBOLS = {a["symbol"] for a in SUPPORTED_ASSETS}

# UI timeframe -> provider interval
TIMEFRAMES = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1H": "1h",
    "4H": "4h",
    "1D": "1d",
}

DEFAULT_TIMEFRAME = "4H"

# ---------------------------------------------------------------------------
# Outcome tracking
#
# Each analysis timeframe is evaluated on a timeframe that is finer than or
# equal to the signal timeframe. This reduces intrabar ambiguity.
# ---------------------------------------------------------------------------
OUTCOME_EVAL_INTERVAL = {
    "1m": "1m",
    "5m": "1m",
    "15m": "5m",
    "1H": "15m",
    "4H": "1h",
    "1D": "4h",
}

# Maximum number of candles from the ORIGINAL analysis timeframe to use
# before the outcome remains pending/expired.
#
# These are initial safety defaults, not backtest-calibrated values.
OUTCOME_HORIZON_BARS = {
    "1m": 120,
    "5m": 120,
    "15m": 120,
    "1H": 120,
    "4H": 120,
    "1D": 120,
}