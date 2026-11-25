"""Exness verisini V9 saglayici arayuzuyle sunar.

Senkron ve I/O'suzdur: yalnizca onceden doldurulmus onbelleklerden (katalog, mum deposu, fiyat
defteri, hesap) okur. Eksik veri uydurulmaz; V9 eksigi gorur ve islem acmaz.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from ..exness.schema import Account, Instrument

# Cent hesap para birimleri: 1 ana birim = 100 cent birimi.
CENT_CURRENCIES = {"USC": "USD", "EUC": "EUR", "GBC": "GBP"}
_IDENTITY = {"forex": ("forex_spot", "spot"), "metal": ("cfd", "cfd"), "crypto": ("cfd", "cfd")}
Direction = Literal["buy", "sell"]


class RateConverter:
    """Exness donusum kurallari: dogrudan parite, ters parite, sonra USD uzerinden iki adim.

    Sell yonu: baz→kote = bid, kote→baz = 1/ask.  Buy yonu: baz→kote = ask, kote→baz = 1/bid.
    """

    def __init__(self, catalog, quotes):
        self._catalog = catalog
        self._quotes = quotes

    def _pair(self, base: str, quote_ccy: str) -> dict | None:
        try:
            self._catalog.get(base + quote_ccy)
        except KeyError:
            return None
        return self._quotes.quote(base + quote_ccy)

    def _single(self, src: str, dst: str, direction: Direction) -> float | None:
        if src == dst:
            return 1.0
        direct = self._pair(src, dst)
        if direct:
            return direct["bid"] if direction == "sell" else direct["ask"]
        reverse = self._pair(dst, src)
        if reverse:
            return 1.0 / reverse["ask"] if direction == "sell" else 1.0 / reverse["bid"]
        return None

    def rate(self, src: str, dst: str, direction: Direction) -> float | None:
        if dst in CENT_CURRENCIES:
            major = self.rate(src, CENT_CURRENCIES[dst], direction)
            return None if major is None else major * 100.0
        if src in CENT_CURRENCIES:
            major = self.rate(CENT_CURRENCIES[src], dst, direction)
            return None if major is None else major / 100.0
        single = self._single(src, dst, direction)
        if single is not None:
            return single
        first, second = self._single(src, "USD", direction), self._single("USD", dst, direction)
        return None if first is None or second is None else first * second

    def bounds(self, src: str, dst: str) -> tuple[float, float] | None:
        """(en dusuk, en yuksek) kur; zarar yuksekle, kar dusukle cevrilir (temkinli)."""
        buy, sell = self.rate(src, dst, "buy"), self.rate(src, dst, "sell")
        if buy is None or sell is None or min(buy, sell) <= 0:
            return None
        return min(buy, sell), max(buy, sell)


class ExnessV9Provider:
    name = "exness"

    def __init__(self, catalog, candles, quotes, account: Callable[[], Account | None]):
        self._catalog = catalog
        self._candles = candles
        self._quotes = quotes
        self._account = account
        self.rates = RateConverter(catalog, quotes)

    def _bounds(self, instrument: Instrument, account: Account | None) -> tuple[float, float] | None:
        if account is None or not instrument.currency_profit:
            return None
        return self.rates.bounds(instrument.currency_profit, account.currency)

    def metadata(self, symbol: str) -> dict:
        instrument: Instrument = self._catalog.get(symbol)
        account = self._account()
        bounds = self._bounds(instrument, account)
        per_tick = instrument.contract_size * instrument.tick_size
        market_type, contract_type = _IDENTITY.get(instrument.kind, ("unverified", "unverified"))
        allowed = ["BUY", "SELL"] if instrument.tradable else []
        return {
            "symbol": symbol, "broker_symbol": instrument.broker_symbol, "asset_type": instrument.kind,
            "source": self.name, "digits": instrument.digits,
            "market_type": market_type, "contract_type": contract_type, "price_kind": "bid",
            "trade_calc_mode": instrument.calc_mode, "trade_mode": "enabled" if instrument.tradable else "disabled",
            "allowed_directions": allowed,
            "base_currency": instrument.currency_base, "profit_currency": instrument.currency_profit,
            "margin_currency": instrument.currency_margin, "freeze_level": 0,
            "tick_value": per_tick * bounds[1] if bounds else None,
            "tick_value_loss": per_tick * bounds[1] if bounds else None,
            "tick_value_profit": per_tick * bounds[0] if bounds else None,
            "tick_value_currency": account.currency if account else None,
            "account_currency": account.currency if account else None,
            "broker_server": "exness-api",
            "margin_free": account.margin_free if account else None,
            "leverage": account.leverage if account else None,
            "max_spread": self._quotes.max_spread(symbol),
            "contract_size": instrument.contract_size, "tick_size": instrument.tick_size,
            "point": instrument.tick_size, "volume_min": instrument.volume_min,
            "volume_max": instrument.volume_max, "volume_step": instrument.volume_step,
            "stops_level": instrument.stops_level,
            "trade_allowed": bool(allowed) and account is not None and account.can_open,
            "broker_hours": instrument.trading_hours, "broker_hours_trust": "DECLARED",
            "schedule_source": "exness-api",
        }

    def quote(self, symbol: str) -> dict:
        quote = self._quotes.quote(symbol)
        if quote is None:
            raise LookupError("fiyat yok")
        return {"symbol": symbol, "bid": quote["bid"], "ask": quote["ask"], "spread": quote["spread"],
                "time": quote["time"], "provider": self.name}

    def candles(self, symbol: str, timeframe: str, count: int = 256) -> list[dict]:
        return self._candles.cached(symbol, timeframe, count)

    def loss_for(self, symbol: str, side: str, lots: float, entry: float, stop: float) -> float:
        """`entry`den `stop` fiyatina gidisin hesap para birimindeki sonucu (zarar negatif)."""
        instrument: Instrument = self._catalog.get(symbol)
        bounds = self._bounds(instrument, self._account())
        if bounds is None:
            raise LookupError("hesap para birimine donusum kuru yok")
        sign = 1.0 if side == "BUY" else -1.0
        pnl = (stop - entry) * sign * lots * instrument.contract_size
        return pnl * (bounds[1] if pnl < 0 else bounds[0])

    def pnl(self, symbol: str, side: str, lots: float, entry: float, exit_price: float) -> float | None:
        """Acik pozisyonun yerel kar/zarar tahmini; kur yoksa None."""
        try:
            return self.loss_for(symbol, side, lots, entry, exit_price)
        except (LookupError, KeyError):
            return None
