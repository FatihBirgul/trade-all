import pytest

from tests.signals.helpers import (ALL_WEEK, NOW, Catalog, Candles, account, book, instrument,
                                   provider_from_fixture, v9_fixtures)
from tradebot.signals.provider import ExnessV9Provider, RateConverter

MT5_KEYS = {"symbol", "broker_symbol", "asset_type", "source", "digits", "market_type", "contract_type",
            "price_kind", "trade_calc_mode", "trade_mode", "allowed_directions", "base_currency",
            "profit_currency", "margin_currency", "freeze_level", "tick_value_profit", "tick_value_loss",
            "broker_server", "margin_free", "leverage", "max_spread", "contract_size", "tick_size",
            "tick_value", "point", "volume_min", "volume_max", "volume_step", "stops_level",
            "trade_allowed", "broker_hours", "account_currency", "tick_value_currency"}


def test_metadata_keys_superset_of_mt5_provider():
    v9_fixtures()
    import inspect
    from forex.providers import MT5Provider
    source = inspect.getsource(MT5Provider.metadata)
    assert all(f"'{key}'" in source for key in MT5_KEYS)  # liste V9 ile ayni kalsin
    meta = provider_from_fixture().metadata("XAUUSD")
    assert MT5_KEYS <= set(meta)
    assert meta["broker_server"] == "exness-api" and meta["schedule_source"] == "exness-api"
    assert meta["broker_hours_trust"] == "DECLARED" and meta["price_kind"] == "bid"
    assert (meta["market_type"], meta["contract_type"]) == ("cfd", "cfd")
    assert meta["max_spread"] == pytest.approx(0.6)
    assert (meta["tick_size"], meta["point"], meta["stops_level"]) == (0.01, 0.01, 0)
    assert meta["tick_value"] == pytest.approx(1.0) and meta["tick_value_currency"] == "USD"
    assert meta["trade_allowed"] is True and meta["allowed_directions"] == ["BUY", "SELL"]


def test_market_identity_per_kind():
    forex = instrument("EURUSD", kind="forex", tick_size=0.00001, digits=5, contract_size=100000.0)
    crypto = instrument("BTCUSD", kind="crypto", contract_size=1.0)
    for inst, expected in ((forex, ("forex_spot", "spot")), (crypto, ("cfd", "cfd"))):
        provider = ExnessV9Provider(Catalog(inst), Candles({}), book(inst.symbol, 1.0, 1.1), lambda: account())
        meta = provider.metadata(inst.symbol)
        assert (meta["market_type"], meta["contract_type"]) == expected


def test_crypto_hours_cover_weekend():
    v9_fixtures()
    from datetime import datetime, timezone
    from forex.sessions import broker_status
    crypto = instrument("BTCUSD", kind="crypto", contract_size=1.0, trading_hours=ALL_WEEK)
    forex = instrument("EURUSD", kind="forex", trading_hours={"timezone": "UTC", "weekly": {
        str(d): [["00:00", "24:00"]] for d in range(5)}})
    provider = ExnessV9Provider(Catalog(crypto, forex), Candles({}), book("BTCUSD", 1.0, 1.1), lambda: account())
    saturday = datetime(2027, 1, 16, 12, 0, tzinfo=timezone.utc)
    assert saturday.weekday() == 5
    for symbol, expected in (("BTCUSD", "OPEN"), ("EURUSD", "CLOSED")):
        meta = provider.metadata(symbol)
        assert broker_status(saturday, symbol, meta["trade_allowed"], meta["broker_hours"])["status"] == expected


def test_trade_not_allowed_when_account_or_instrument_blocked():
    blocked = provider_from_fixture(acct=account(can_open=False))
    assert blocked.metadata("XAUUSD")["trade_allowed"] is False
    disabled = provider_from_fixture(inst=instrument(tradable=False))
    assert disabled.metadata("XAUUSD")["trade_allowed"] is False


def test_quote_and_candles_come_from_caches():
    provider = provider_from_fixture()
    quote = provider.quote("XAUUSD")
    assert quote["provider"] == "exness" and quote["symbol"] == "XAUUSD"
    assert quote["ask"] - quote["bid"] == pytest.approx(0.2) and quote["time"] == NOW - 1
    rows = provider.candles("XAUUSD", "M15", 256)
    assert len(rows) == 220 and rows[-1]["time"] + 900 == NOW
    with pytest.raises(LookupError):
        provider.quote("EURUSD")


def test_max_spread_is_none_without_enough_ticks():
    assert provider_from_fixture(ticks=50).metadata("XAUUSD")["max_spread"] is None


def test_loss_for_usd_account():
    provider = provider_from_fixture()
    assert provider.loss_for("XAUUSD", "BUY", 0.1, 2000.0, 1995.0) == pytest.approx(-50.0)
    assert provider.loss_for("XAUUSD", "SELL", 0.1, 2000.0, 1995.0) == pytest.approx(50.0)


def test_cent_account_scales_by_100():
    provider = provider_from_fixture(acct=account("USC", 3000.0))
    assert provider.loss_for("XAUUSD", "BUY", 0.1, 2000.0, 1995.0) == pytest.approx(-5000.0)
    meta = provider.metadata("XAUUSD")
    assert meta["tick_value"] == pytest.approx(100.0) and meta["account_currency"] == "USC"


def test_cross_currency_conversion_is_conservative():
    usdjpy = instrument("USDJPY", kind="forex", tick_size=0.001, digits=3, contract_size=100000.0)
    quotes = book("USDJPY", 150.00, 150.03)
    provider = ExnessV9Provider(Catalog(usdjpy), Candles({}), quotes, lambda: account("USD"))
    # 1 lot, 1.000 JPY aleyhte: 100000 JPY zarar; zarar buyuk cikacak kurla (1/bid) cevrilir.
    assert provider.loss_for("USDJPY", "BUY", 1.0, 150.0, 149.0) == pytest.approx(-100000 / 150.00)
    assert provider.loss_for("USDJPY", "BUY", 1.0, 150.0, 151.0) == pytest.approx(100000 / 150.03)
    meta = provider.metadata("USDJPY")
    assert meta["tick_value_loss"] == pytest.approx(100000 * 0.001 / 150.00)
    assert meta["tick_value_profit"] == pytest.approx(100000 * 0.001 / 150.03)


def test_two_step_conversion_through_usd_and_missing_rate():
    eurgbp = instrument("EURGBP", kind="forex", tick_size=0.00001, digits=5, contract_size=100000.0)
    gbpusd = instrument("GBPUSD", kind="forex", tick_size=0.00001, digits=5, contract_size=100000.0)
    usdjpy = instrument("USDJPY", kind="forex", tick_size=0.001, digits=3, contract_size=100000.0)
    quotes = book("GBPUSD", 1.2500, 1.2502)
    for i in range(3):
        from tradebot.exness.schema import Tick
        quotes.on_tick(Tick("USDJPY", 150.00, 150.03, NOW - 1))
    converter = RateConverter(Catalog(eurgbp, gbpusd, usdjpy), quotes)
    assert converter.rate("GBP", "USD", "sell") == pytest.approx(1.2500)
    assert converter.rate("GBP", "USD", "buy") == pytest.approx(1.2502)
    assert converter.rate("USD", "GBP", "sell") == pytest.approx(1 / 1.2502)
    assert converter.rate("GBP", "JPY", "sell") == pytest.approx(1.2500 * 150.00)
    assert converter.rate("GBP", "USC", "buy") == pytest.approx(125.02)
    assert converter.rate("CHF", "USD", "sell") is None
    provider = ExnessV9Provider(Catalog(eurgbp), Candles({}), book("EURGBP", 0.85, 0.8502), lambda: account("USD"))
    with pytest.raises(LookupError):
        provider.loss_for("EURGBP", "BUY", 1.0, 0.85, 0.84)
    assert provider.metadata("EURGBP")["tick_value"] is None
