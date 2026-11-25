"""V9 fixture verisini Exness saglayicisina besleyen test yardimcilari."""
import sys
from pathlib import Path

from tradebot.exness.schema import Account, Instrument, Tick
from tradebot.market.quotes import QuoteBook

V9_ROOT = Path(__file__).resolve().parents[3] / "trade-ai-unified"
NOW = 1_800_000_000
TF = {"M15": 900, "H1": 3600, "H4": 14400}
ALL_WEEK = {"timezone": "UTC", "weekly": {str(d): [["00:00", "24:00"]] for d in range(7)}}


def v9_fixtures():
    from tradebot.signals.v9 import load_v9
    load_v9(V9_ROOT)
    tests = str(V9_ROOT / "tests")
    if tests not in sys.path:
        sys.path.append(tests)
    import fixtures
    return fixtures


def instrument(symbol="XAUUSD", **overrides):
    values = dict(symbol=symbol, broker_symbol=symbol, kind="metal", tick_size=0.01, contract_size=100.0,
                  volume_min=0.01, volume_max=10.0, volume_step=0.01, stops_level=0, digits=2,
                  currency_base=symbol[:3], currency_profit=symbol[3:], currency_margin=symbol[:3],
                  calc_mode="cfd_leverage", exec_mode="market", trading_hours=ALL_WEEK, tradable=True)
    values.update(overrides)
    return Instrument(**values)


def account(currency="USD", equity=10_000.0, can_open=True):
    return Account(currency=currency, balance=equity, equity=equity, margin=0.0, margin_free=equity,
                   leverage=2000.0, can_open=can_open, can_trade=True)


class Catalog:
    def __init__(self, *instruments):
        self.items = {i.symbol: i for i in instruments}

    def get(self, symbol):
        return self.items[symbol]


class Candles:
    def __init__(self, data):
        self.data = data

    def cached(self, symbol, tf, count=256):
        return [dict(row) for row in self.data.get(symbol, {}).get(tf, [])[-count:]]


def book(symbol, bid, ask, now=NOW, ticks=120):
    quotes = QuoteBook(clock=lambda: now)
    for i in range(ticks):
        quotes.on_tick(Tick(symbol, bid, ask, now - ticks + i))
    return quotes


def provider_from_fixture(direction="BUY", *, symbol="XAUUSD", acct=None, inst=None, ticks=120):
    """V9 fixture'indaki XAUUSD verisi, Exness saglayicisi uzerinden."""
    from tradebot.signals.provider import ExnessV9Provider
    data = v9_fixtures().fixture(direction, frames=("M15", "H1", "H4")).data["XAUUSD"]
    inst = inst or instrument(symbol)
    quotes = book(symbol, data["quote"]["bid"], data["quote"]["ask"], ticks=ticks)
    acct = acct or account()
    return ExnessV9Provider(Catalog(inst), Candles({symbol: data["candles"]}), quotes, lambda: acct)
