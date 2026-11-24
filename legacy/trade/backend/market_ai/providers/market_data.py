"""Market data provider abstraction.

`MarketDataProvider` is the contract. `BinanceProvider` is the first concrete
implementation using Binance's public market-data mirror (no API key, no geo
restrictions). Additional providers (stocks / BIST / US equities) can be added
later by implementing the same interface and registering them in `get_provider`.
"""
from __future__ import annotations

import asyncio
from typing import List, Optional

import requests

from ..config import MARKET_DATA_PROVIDER


class MarketDataError(Exception):
    pass


class MarketDataProvider:
    name = "abstract"

    async def get_ticker(self, symbol: str) -> dict:
        raise NotImplementedError

    async def get_klines(self, symbol: str, interval: str, limit: int = 300) -> List[dict]:
        raise NotImplementedError


class BinanceProvider(MarketDataProvider):
    name = "binance"
    BASE = "https://data-api.binance.vision/api/v3"

    def _get(self, path: str, params: dict) -> object:
        try:
            r = requests.get(f"{self.BASE}{path}", params=params, timeout=12)
            if r.status_code != 200:
                raise MarketDataError(f"Binance responded {r.status_code}")
            return r.json()
        except requests.RequestException as e:
            raise MarketDataError(f"Market data unreachable: {e}")

    async def get_ticker(self, symbol: str) -> dict:
        data = await asyncio.to_thread(self._get, "/ticker/24hr", {"symbol": symbol})
        return {
            "symbol": symbol,
            "price": float(data["lastPrice"]),
            "change_24h_pct": float(data["priceChangePercent"]),
            "high_24h": float(data["highPrice"]),
            "low_24h": float(data["lowPrice"]),
            "volume_24h": float(data["volume"]),
            "quote_volume_24h": float(data["quoteVolume"]),
        }

    async def get_klines(self, symbol: str, interval: str, limit: int = 300) -> List[dict]:
        raw = await asyncio.to_thread(
            self._get, "/klines", {"symbol": symbol, "interval": interval, "limit": limit}
        )
        candles = []
        for k in raw:
            candles.append(
                {
                    "time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
            )
        return candles

    async def get_klines_since(self, symbol: str, interval: str, start_ms: int, limit: int = 1000) -> List[dict]:
        """Fetch candles from `start_ms` forward — used for outcome tracking."""
        raw = await asyncio.to_thread(
            self._get,
            "/klines",
            {"symbol": symbol, "interval": interval, "startTime": start_ms, "limit": min(limit, 1000)},
        )
        candles = []
        for k in raw:
            candles.append(
                {
                    "time": int(k[0]),
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),
                }
            )
        return candles


_provider: Optional[MarketDataProvider] = None


def get_provider() -> MarketDataProvider:
    global _provider
    if _provider is None:
        if MARKET_DATA_PROVIDER == "binance":
            _provider = BinanceProvider()
        else:
            _provider = BinanceProvider()
    return _provider
