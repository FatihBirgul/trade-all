"""Public spot-data adapters only. No signed/trading endpoints or credentials."""
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from time import monotonic
from math import sin
from typing import Protocol
import httpx

from .market_data_contract import Candle, Instrument, from_binance_spot_kline
from .technical_adapter import TIMEFRAME_MS


class ProviderUnavailable(Exception):
    pass


class SpotProvider(Protocol):
    name: str
    venue: str
    mode: str
    source_name: str

    def candles(self, symbol: str, timeframe: str, as_of_ms: int) -> list[Candle]: ...
    def rules(self, symbol: str) -> dict: ...


class BinanceSpotProvider:
    name, venue, mode = "binance_public_spot", "binance", "live"
    source_name = "binance_spot"

    def __init__(self, transport=None):
        self.transport = transport
        self._rules = {}

    def _public_get(self, path, params):
        if path not in ("/api/v3/klines", "/api/v3/exchangeInfo"):
            raise ValueError("Only allowlisted public spot reads are supported")
        for host in ("https://data-api.binance.vision", "https://api.binance.com"):
            try:
                with httpx.Client(timeout=8, transport=self.transport, follow_redirects=False) as client:
                    response = client.get(host + path, params=params)
                if response.status_code in (403, 418, 429, 451):
                    raise ProviderUnavailable("provider_access_or_rate_limit")
                response.raise_for_status()
                return response.json()
            except ImportError as exc:
                # Respect an environment-configured proxy; do not bypass it or
                # turn a missing optional transport dependency into API 500.
                raise ProviderUnavailable("proxy_transport_unavailable") from exc
            except (httpx.HTTPError, ValueError):
                continue
        raise ProviderUnavailable("all_spot_mirrors_unavailable")

    def rules(self, symbol):
        if symbol in self._rules and monotonic()-self._rules[symbol][0] < 300:
            return dict(self._rules[symbol][1])
        try:
            item = self._public_get("/api/v3/exchangeInfo", {"symbol": symbol})["symbols"][0]
            base = {"BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL"}.get(symbol)
            if (item["symbol"] != symbol or item["status"] != "TRADING" or item["isSpotTradingAllowed"] is not True
                    or not base or item["baseAsset"] != base or item["quoteAsset"] != "USDT"):
                raise ProviderUnavailable("spot_instrument_not_trading")
            filters = {f["filterType"]: f for f in item["filters"]}
            lot = filters["LOT_SIZE"]
            notional = filters.get("NOTIONAL", filters.get("MIN_NOTIONAL", {}))
            result = {"quantity_step": lot["stepSize"], "minimum_quantity": lot["minQty"],
                      "maximum_quantity": lot["maxQty"], "minimum_notional": notional["minNotional"],
                      "maximum_notional": notional.get("maxNotional", "1000000000000000000000000"),
                      "price_tick": filters["PRICE_FILTER"]["tickSize"], "source": "binance_exchange_info"}
            for key in ("quantity_step", "minimum_quantity", "maximum_quantity", "minimum_notional", "price_tick"):
                value = Decimal(result[key])
                if not value.is_finite() or value <= 0:
                    raise ProviderUnavailable("invalid_instrument_rules")
            if Decimal(result["minimum_quantity"]) > Decimal(result["maximum_quantity"]):
                raise ProviderUnavailable("invalid_instrument_rules")
            self._rules[symbol] = (monotonic(), dict(result))
            return result
        except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, InvalidOperation) as exc:
            raise ProviderUnavailable("instrument_rules_unavailable") from exc

    def candles(self, symbol, timeframe, as_of_ms):
        interval = {"1H": "1h", "4H": "4h", "1D": "1d"}.get(timeframe, timeframe)
        # End before the current interval: no filtering after analysis to hide
        # unfinished bars. Both hosts represent the SAME Binance spot venue.
        end = as_of_ms // TIMEFRAME_MS[timeframe] * TIMEFRAME_MS[timeframe] - 1
        try:
            raw = self._public_get("/api/v3/klines", {"symbol": symbol, "interval": interval, "limit": 300, "endTime": end})
            if not isinstance(raw, list) or not raw:
                raise ProviderUnavailable("empty_provider_response")
            return [from_binance_spot_kline(k, symbol=symbol, quote_currency="USDT", as_of_ms=as_of_ms) for k in raw]
        except (ValueError, TypeError, IndexError, OverflowError) as exc:
            raise ProviderUnavailable("malformed_spot_response") from exc


    def candle_window(self, symbol, start_ms, end_ms):
        """Read <=300 historical final 1m bars from an exact half-open window.

        No calendar guessing, synthesized prices or retry of access restrictions.
        The poller verifies full continuity, identity and exact boundaries.
        """
        if (not isinstance(start_ms, int) or not isinstance(end_ms, int)
                or start_ms < 0 or start_ms % 60000 or end_ms % 60000
                or not 0 < end_ms-start_ms <= 300*60000):
            raise ValueError("An aligned positive window of at most 300 minutes is required")
        try:
            raw = self._public_get("/api/v3/klines", {"symbol": symbol, "interval": "1m", "limit": 300,
                                                     "startTime": start_ms, "endTime": end_ms-1})
            if not isinstance(raw, list) or not raw:
                raise ProviderUnavailable("empty_historical_window")
            return [from_binance_spot_kline(k, symbol=symbol, quote_currency="USDT", as_of_ms=end_ms) for k in raw]
        except (ValueError, TypeError, IndexError, OverflowError) as exc:
            raise ProviderUnavailable("malformed_historical_window") from exc


class FixtureSpotProvider:
    """Explicit test/demo input, never selected as a live-provider fallback."""
    name, venue, mode = "fixture_spot", "fixture", "fixture"
    source_name = "fixture_spot"

    def __init__(self, case="trend"):
        self.case = case

    def rules(self, symbol):
        return {"quantity_step": "0.000001", "minimum_quantity": "0.000001", "maximum_quantity": "100000",
                "minimum_notional": "1", "maximum_notional": "1000000000", "price_tick": "0.0001", "source": "fixture_rules_not_exchange_rules"}

    def candles(self, symbol, timeframe, as_of_ms):
        tf = TIMEFRAME_MS[timeframe]
        last = as_of_ms // tf * tf
        if self.case == "stale":
            last -= 10 * tf
        identity = Instrument(symbol, "crypto_spot", self.venue, "last", "spot", "USDT")
        result = []
        for i in range(300):
            price = 100 + .1 * i if self.case != "range" else 100 + sin(i)
            result.append(Candle(identity, last - (300-i)*tf, last - (299-i)*tf, True,
                                 price-.05, price+.5, price-.5, price,
                                 100.0 if i < 299 else 300.0, "real", self.name))
        if self.case == "unfinished":
            result[-1] = replace(result[-1], is_final=False)
        if self.case == "mixed":
            result[-1] = replace(result[-1], instrument=replace(identity, symbol="OTHERUSDT"))
        if self.case == "gap":
            result.pop(280)
        return result
