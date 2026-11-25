from tests.signals.helpers import instrument
from tradebot.news.calendar import NewsEvent
from tradebot.news.gate import blocking_event

T = 1_800_000_000.0
EURUSD = instrument("EURUSD", kind="forex")
EURGBP = instrument("EURGBP", kind="forex")
XAUUSD = instrument("XAUUSD")
BTCUSD = instrument("BTCUSD", kind="crypto")
ETHUSD = instrument("ETHUSD", kind="crypto")


def event(currency="USD", at=T, impact="high"):
    return NewsEvent(currency=currency, title="NFP", at=at, impact=impact)


def blocked(inst, events, now=T, window=30):
    return blocking_event(inst, events, now=now, window_minutes=window)


def test_only_high_impact_blocks():
    assert blocked(EURUSD, [event()]) is not None
    for impact in ("medium", "low", "holiday"):
        assert blocked(EURUSD, [event(impact=impact)]) is None


def test_window_is_symmetric_30_minutes():
    assert blocked(EURUSD, [event(at=T + 29 * 60 + 59)]) is not None  # haberden once
    assert blocked(EURUSD, [event(at=T - 29 * 60 - 59)]) is not None  # haberden sonra
    assert blocked(EURUSD, [event(at=T + 30 * 60)]) is not None
    assert blocked(EURUSD, [event(at=T + 30 * 60 + 1)]) is None
    assert blocked(EURUSD, [event(at=T - 30 * 60 - 1)]) is None
    assert blocked(EURUSD, [event(at=T + 45 * 60)], window=60) is not None


def test_usd_news_blocks_btc_eth_and_gold_not_eurgbp():
    usd = [event("USD")]
    for inst in (EURUSD, XAUUSD, BTCUSD, ETHUSD):
        assert blocked(inst, usd) is not None, inst.symbol
    assert blocked(EURGBP, usd) is None
    assert blocked(EURGBP, [event("GBP")]) is not None and blocked(EURGBP, [event("EUR")]) is not None
    assert blocked(BTCUSD, [event("EUR")]) is None


def test_returns_nearest_event_and_handles_empty():
    far, near = event(at=T + 20 * 60), event(at=T - 5 * 60)
    assert blocked(EURUSD, [far, near]) is near
    assert blocked(EURUSD, []) is None
