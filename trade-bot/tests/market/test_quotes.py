import pytest

from tradebot.exness.schema import Tick
from tradebot.market.quotes import QuoteBook


def feed(book, n, spread, start=1000.0, symbol="EURUSD", bid=1.1):
    for i in range(n):
        book.on_tick(Tick(symbol, bid, bid + spread, start + i))


def test_quote_returns_latest():
    book = QuoteBook(clock=lambda: 2000.0)
    assert book.quote("EURUSD") is None
    book.on_tick(Tick("EURUSD", 1.1000, 1.1002, 1999.0))
    quote = book.quote("EURUSD")
    assert quote == {"bid": 1.1, "ask": 1.1002, "spread": pytest.approx(0.0002), "time": 1999.0}


def test_max_spread_none_until_100_ticks():
    book = QuoteBook(clock=lambda: 1100.0)
    feed(book, 99, 0.0002)
    assert book.max_spread("EURUSD") is None
    feed(book, 1, 0.0002, start=1099.0)
    assert book.max_spread("EURUSD") == pytest.approx(0.0006)


def test_max_spread_is_3x_median():
    book = QuoteBook(clock=lambda: 1200.0)
    feed(book, 60, 0.0001)
    feed(book, 41, 0.0003, start=1060.0)
    feed(book, 20, 0.0050, start=1101.0)  # haber aninda acilan spread medyani tasimaz
    assert book.max_spread("EURUSD") == pytest.approx(0.0009)


def test_max_spread_uses_only_last_30_minutes():
    now = {"t": 1000.0}
    book = QuoteBook(clock=lambda: now["t"])
    feed(book, 150, 0.0002, start=0.0)
    now["t"] = 150.0
    assert book.max_spread("EURUSD") is not None
    now["t"] = 149.0 + 1800.0 - 50  # eski tick'lerin cogu pencere disinda
    assert book.max_spread("EURUSD") is None


def test_invalid_ticks_are_ignored_and_symbols_are_independent():
    book = QuoteBook(clock=lambda: 1000.0)
    book.on_tick(Tick("EURUSD", 1.2, 1.1, 999.0))  # ask < bid
    book.on_tick(Tick("EURUSD", 0.0, 1.1, 999.0))
    assert book.quote("EURUSD") is None
    feed(book, 100, 0.5, symbol="XAUUSD", bid=2000.0, start=900.0)
    assert book.max_spread("XAUUSD") == pytest.approx(1.5)
    assert book.max_spread("EURUSD") is None
