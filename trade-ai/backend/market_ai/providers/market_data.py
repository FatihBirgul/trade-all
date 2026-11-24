"""Market data provider abstraction.

`MarketDataProvider` is the contract. `BinanceProvider` is the first concrete
implementation using Binance public market data without an API key.

Spot candle/ticker data remains available through the original endpoints.

USDⓈ-M Futures market data is exposed separately for the intelligence layer:
- order book / depth
- aggregate trades
- current open interest
- historical open interest
- funding rate
- force orders / liquidation data

Raw market data is intentionally kept separate from scoring/evidence engines.
Those engines consume normalized provider output and remain deterministic.
"""
from __future__ import annotations

import asyncio
import time
from typing import List, Optional

import requests

from ..config import MARKET_DATA_PROVIDER


class MarketDataError(Exception):
    pass


class MarketDataProvider:
    name = "abstract"

    async def get_ticker(
        self,
        symbol: str,
    ) -> dict:
        raise NotImplementedError

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 300,
    ) -> List[dict]:
        raise NotImplementedError

    async def get_klines_since(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        limit: int = 1000,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        raise NotImplementedError

    async def get_order_book(
        self,
        symbol: str,
        limit: int = 100,
    ) -> dict:
        raise NotImplementedError

    async def get_aggregate_trades(
        self,
        symbol: str,
        limit: int = 500,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        from_id: Optional[int] = None,
    ) -> List[dict]:
        raise NotImplementedError

    async def get_open_interest(
        self,
        symbol: str,
    ) -> dict:
        raise NotImplementedError

    async def get_open_interest_history(
        self,
        symbol: str,
        period: str = "5m",
        limit: int = 30,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        raise NotImplementedError

    async def get_funding_rate(
        self,
        symbol: str,
        limit: int = 100,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        raise NotImplementedError

    async def get_force_orders(
        self,
        symbol: str,
        limit: int = 100,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        raise NotImplementedError


class BinanceProvider(MarketDataProvider):
    name = "binance"

    SPOT_BASE = (
        "https://data-api.binance.vision/api/v3"
    )

    FUTURES_BASE = (
        "https://fapi.binance.com"
    )

    # ------------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------------
    def _get(
        self,
        path: str,
        params: dict,
        base: Optional[str] = None,
    ) -> object:
        try:
            r = requests.get(
                f"{base or self.SPOT_BASE}{path}",
                params=params,
                timeout=12,
            )

            if r.status_code != 200:
                try:
                    payload = r.json()
                except ValueError:
                    payload = None

                detail = ""

                if isinstance(
                    payload,
                    dict,
                ):
                    code = payload.get(
                        "code"
                    )

                    message = payload.get(
                        "msg"
                    )

                    if code is not None:
                        detail += (
                            f" code={code}"
                        )

                    if message:
                        detail += (
                            f" msg={message}"
                        )

                raise MarketDataError(
                    f"Binance responded "
                    f"{r.status_code}{detail}"
                )

            return r.json()

        except requests.RequestException as e:
            raise MarketDataError(
                f"Market data unreachable: {e}"
            )

    @staticmethod
    def _now_ms() -> int:
        return int(
            time.time()
            * 1000
        )

    # ------------------------------------------------------------------------
    # Spot candle parsing
    # ------------------------------------------------------------------------
    @classmethod
    def _parse_candles(
        cls,
        raw: list,
        only_closed: bool = True,
    ) -> List[dict]:
        candles = []

        now_ms = cls._now_ms()

        for k in raw:
            close_time = int(
                k[6]
            )

            if (
                only_closed
                and close_time > now_ms
            ):
                continue

            candles.append(
                {
                    "time": int(
                        k[0]
                    ),
                    "open": float(
                        k[1]
                    ),
                    "high": float(
                        k[2]
                    ),
                    "low": float(
                        k[3]
                    ),
                    "close": float(
                        k[4]
                    ),
                    "volume": float(
                        k[5]
                    ),
                    "close_time": close_time,
                }
            )

        return candles

    # ------------------------------------------------------------------------
    # Ticker
    # ------------------------------------------------------------------------
    async def get_ticker(
        self,
        symbol: str,
    ) -> dict:
        """Return the current live Spot ticker snapshot."""
        data = await asyncio.to_thread(
            self._get,
            "/ticker/24hr",
            {
                "symbol": symbol,
            },
            self.SPOT_BASE,
        )

        return {
            "symbol": symbol,
            "price": float(
                data["lastPrice"]
            ),
            "change_24h_pct": float(
                data["priceChangePercent"]
            ),
            "high_24h": float(
                data["highPrice"]
            ),
            "low_24h": float(
                data["lowPrice"]
            ),
            "volume_24h": float(
                data["volume"]
            ),
            "quote_volume_24h": float(
                data["quoteVolume"]
            ),
        }

    # ------------------------------------------------------------------------
    # Spot klines
    # ------------------------------------------------------------------------
    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 300,
    ) -> List[dict]:
        raw = await asyncio.to_thread(
            self._get,
            "/klines",
            {
                "symbol": symbol,
                "interval": interval,
                "limit": min(
                    max(
                        int(limit),
                        1,
                    ),
                    1000,
                ),
            },
            self.SPOT_BASE,
        )

        return self._parse_candles(
            raw,
            only_closed=True,
        )

    async def get_klines_since(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        limit: int = 1000,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        """Fetch fully closed Spot candles from start_ms forward."""
        page_limit = min(
            max(
                int(limit),
                1,
            ),
            1000,
        )

        cursor_ms = int(
            start_ms
        )

        collected: List[dict] = []

        max_pages = 100

        for _ in range(
            max_pages
        ):
            params = {
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor_ms,
                "limit": page_limit,
            }

            if end_ms is not None:
                params["endTime"] = int(
                    end_ms
                )

            raw = await asyncio.to_thread(
                self._get,
                "/klines",
                params,
                self.SPOT_BASE,
            )

            page = self._parse_candles(
                raw,
                only_closed=True,
            )

            if not page:
                break

            collected.extend(
                page
            )

            if (
                len(page)
                < page_limit
            ):
                break

            last_open_time = page[-1][
                "time"
            ]

            if (
                last_open_time
                <= cursor_ms
            ):
                break

            cursor_ms = (
                last_open_time
                + 1
            )

            if (
                end_ms is not None
                and cursor_ms
                > int(end_ms)
            ):
                break

        unique = {}

        for candle in collected:
            unique[
                candle["time"]
            ] = candle

        result = [
            unique[k]
            for k in sorted(
                unique.keys()
            )
        ]

        if end_ms is not None:
            result = [
                c
                for c in result
                if c["time"]
                <= int(end_ms)
            ]

        return result

    # ------------------------------------------------------------------------
    # Futures order book
    # ------------------------------------------------------------------------
    async def get_order_book(
        self,
        symbol: str,
        limit: int = 100,
    ) -> dict:
        """Return normalized USDⓈ-M Futures order-book depth."""
        allowed_limits = {
            5,
            10,
            20,
            50,
            100,
            500,
            1000,
        }

        if limit not in allowed_limits:
            limit = 100

        data = await asyncio.to_thread(
            self._get,
            "/fapi/v1/depth",
            {
                "symbol": symbol,
                "limit": limit,
            },
            self.FUTURES_BASE,
        )

        bids = [
            {
                "price": float(
                    row[0]
                ),
                "quantity": float(
                    row[1]
                ),
            }
            for row in data.get(
                "bids",
                [],
            )
        ]

        asks = [
            {
                "price": float(
                    row[0]
                ),
                "quantity": float(
                    row[1]
                ),
            }
            for row in data.get(
                "asks",
                [],
            )
        ]

        return {
            "symbol": symbol,
            "last_update_id": int(
                data.get(
                    "lastUpdateId",
                    0,
                )
            ),
            "bids": bids,
            "asks": asks,
            "timestamp": self._now_ms(),
        }

    # ------------------------------------------------------------------------
    # Futures aggregate trades
    # ------------------------------------------------------------------------
    async def get_aggregate_trades(
        self,
        symbol: str,
        limit: int = 500,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        from_id: Optional[int] = None,
    ) -> List[dict]:
        """Return normalized USDⓈ-M aggregate trades."""
        params = {
            "symbol": symbol,
            "limit": min(
                max(
                    int(limit),
                    1,
                ),
                1000,
            ),
        }

        if start_ms is not None:
            params["startTime"] = int(
                start_ms
            )

        if end_ms is not None:
            params["endTime"] = int(
                end_ms
            )

        if from_id is not None:
            params["fromId"] = int(
                from_id
            )

        data = await asyncio.to_thread(
            self._get,
            "/fapi/v1/aggTrades",
            params,
            self.FUTURES_BASE,
        )

        result = []

        for trade in data:
            result.append(
                {
                    "id": int(
                        trade["a"]
                    ),
                    "price": float(
                        trade["p"]
                    ),
                    "quantity": float(
                        trade["q"]
                    ),
                    "first_trade_id": int(
                        trade["f"]
                    ),
                    "last_trade_id": int(
                        trade["l"]
                    ),
                    "timestamp": int(
                        trade["T"]
                    ),
                    "buyer_maker": bool(
                        trade["m"]
                    ),
                }
            )

        return result

    # ------------------------------------------------------------------------
    # Futures current Open Interest
    # ------------------------------------------------------------------------
    async def get_open_interest(
        self,
        symbol: str,
    ) -> dict:
        """Return current USDⓈ-M Futures open interest."""
        data = await asyncio.to_thread(
            self._get,
            "/fapi/v1/openInterest",
            {
                "symbol": symbol,
            },
            self.FUTURES_BASE,
        )

        return {
            "symbol": data.get(
                "symbol",
                symbol,
            ),
            "open_interest": float(
                data["openInterest"]
            ),
            "timestamp": int(
                data.get(
                    "time",
                    self._now_ms(),
                )
            ),
        }

    # ------------------------------------------------------------------------
    # Futures historical Open Interest
    # ------------------------------------------------------------------------
    async def get_open_interest_history(
        self,
        symbol: str,
        period: str = "5m",
        limit: int = 30,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        """Return normalized historical USDⓈ-M Futures open interest.

        Binance currently exposes Open Interest Statistics through
        /futures/data/openInterestHist.

        Supported periods include:
            5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h

        Binance documents a maximum of 500 records and availability for the
        latest month.
        """
        allowed_periods = {
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "12h",
        }

        if period not in allowed_periods:
            period = "5m"

        params = {
            "symbol": symbol,
            "period": period,
            "limit": min(
                max(
                    int(limit),
                    1,
                ),
                500,
            ),
        }

        if start_ms is not None:
            params["startTime"] = int(
                start_ms
            )

        if end_ms is not None:
            params["endTime"] = int(
                end_ms
            )

        data = await asyncio.to_thread(
            self._get,
            "/futures/data/openInterestHist",
            params,
            self.FUTURES_BASE,
        )

        result = []

        if not isinstance(
            data,
            list,
        ):
            return result

        for item in data:
            timestamp = item.get(
                "timestamp"
            )

            sum_oi = item.get(
                "sumOpenInterest"
            )

            sum_oi_value = item.get(
                "sumOpenInterestValue"
            )

            if (
                timestamp is None
                or sum_oi is None
            ):
                continue

            result.append(
                {
                    "symbol": item.get(
                        "symbol",
                        symbol,
                    ),
                    "open_interest": float(
                        sum_oi
                    ),
                    "open_interest_value": (
                        float(
                            sum_oi_value
                        )
                        if sum_oi_value
                        not in (
                            None,
                            "",
                        )
                        else None
                    ),
                    "timestamp": int(
                        timestamp
                    ),
                    "period": period,
                }
            )

        result.sort(
            key=lambda x: x["timestamp"]
        )

        return result

    # ------------------------------------------------------------------------
    # Futures funding history
    # ------------------------------------------------------------------------
    async def get_funding_rate(
        self,
        symbol: str,
        limit: int = 100,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        """Return normalized USDⓈ-M Futures funding-rate history."""
        params = {
            "symbol": symbol,
            "limit": min(
                max(
                    int(limit),
                    1,
                ),
                1000,
            ),
        }

        if start_ms is not None:
            params["startTime"] = int(
                start_ms
            )

        if end_ms is not None:
            params["endTime"] = int(
                end_ms
            )

        data = await asyncio.to_thread(
            self._get,
            "/fapi/v1/fundingRate",
            params,
            self.FUTURES_BASE,
        )

        result = []

        for item in data:
            result.append(
                {
                    "symbol": item.get(
                        "symbol",
                        symbol,
                    ),
                    "funding_rate": float(
                        item["fundingRate"]
                    ),
                    "funding_time": int(
                        item["fundingTime"]
                    ),
                    "mark_price": (
                        float(
                            item["markPrice"]
                        )
                        if item.get(
                            "markPrice"
                        )
                        not in (
                            None,
                            "",
                        )
                        else None
                    ),
                    "rate_type": item.get(
                        "rateType"
                    ),
                }
            )

        return result

    # ------------------------------------------------------------------------
    # Futures force orders / liquidation data
    # ------------------------------------------------------------------------
    async def get_force_orders(
        self,
        symbol: str,
        limit: int = 100,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
    ) -> List[dict]:
        """Return normalized USDⓈ-M Futures force-order data."""
        params = {
            "symbol": symbol,
            "limit": min(
                max(
                    int(limit),
                    1,
                ),
                1000,
            ),
        }

        if start_ms is not None:
            params["startTime"] = int(
                start_ms
            )

        if end_ms is not None:
            params["endTime"] = int(
                end_ms
            )

        data = await asyncio.to_thread(
            self._get,
            "/fapi/v1/forceOrders",
            params,
            self.FUTURES_BASE,
        )

        result = []

        for item in data:
            result.append(
                {
                    "symbol": item.get(
                        "symbol",
                        symbol,
                    ),
                    "price": float(
                        item["price"]
                    ),
                    "average_price": float(
                        item.get(
                            "avgPrice",
                            item["price"],
                        )
                    ),
                    "original_quantity": float(
                        item["origQty"]
                    ),
                    "executed_quantity": float(
                        item.get(
                            "executedQty",
                            item["origQty"],
                        )
                    ),
                    "side": item["side"],
                    "status": item.get(
                        "status"
                    ),
                    "time_in_force": item.get(
                        "timeInForce"
                    ),
                    "trade_time": int(
                        item.get(
                            "time",
                            0,
                        )
                    ),
                    "update_time": int(
                        item.get(
                            "updateTime",
                            0,
                        )
                    ),
                    "order_type": item.get(
                        "type"
                    ),
                    "position_side": item.get(
                        "positionSide"
                    ),
                }
            )

        return result


_provider: Optional[
    MarketDataProvider
] = None


def get_provider() -> MarketDataProvider:
    global _provider

    if _provider is None:
        if (
            MARKET_DATA_PROVIDER
            == "binance"
        ):
            _provider = BinanceProvider()
        else:
            _provider = BinanceProvider()

    return _provider