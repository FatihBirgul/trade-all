import json
from pathlib import Path

import pytest

from tradebot.exness import schema
from tradebot.market.catalog import InstrumentCatalog

FIXTURES = Path(__file__).parents[1] / "exness" / "fixtures"


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


class StubClient:
    account_id = "123456"

    def __init__(self, conditions, fail=()):
        self.conditions = conditions
        self.fail = set(fail)
        self.paths = []

    async def get(self, path):
        self.paths.append(path)
        if path.endswith("/instruments"):
            return {"instruments": list(self.conditions)}
        name = path.split("/")[-2]
        if name in self.fail:
            from tradebot.exness.errors import ExnessUnavailable
            raise ExnessUnavailable("gecici")
        return self.conditions[name]


def conditions():
    ltc = load("instrument_btcusd") | {"instrument": "LTCUSD", "base_currency": "LTC"}
    eth = load("instrument_btcusd") | {"instrument": "ETHUSD", "base_currency": "ETH"}
    btcxau = load("instrument_btcusd") | {"instrument": "BTCXAU", "quote_currency": "XAU"}
    closed = load("instrument_eurusd") | {"instrument": "GBPUSD", "base_currency": "GBP", "trade_mode": "trading_disabled"}
    return {"EURUSDc": load("instrument_cent_eurusd"), "XAUUSD": load("instrument_xauusd"),
            "BTCUSD": load("instrument_btcusd"), "ETHUSD": eth, "LTCUSD": ltc, "BTCXAU": btcxau,
            "AAPL": load("instrument_stock"), "US30": load("instrument_index"), "GBPUSD": closed}


async def test_universe_excludes_other_and_includes_btc_eth():
    catalog = InstrumentCatalog(StubClient(conditions()))
    assert await catalog.refresh() == {}
    assert [i.symbol for i in catalog.universe()] == ["BTCUSD", "ETHUSD", "EURUSD", "XAUUSD"]


async def test_universe_respects_enabled_filter_and_lookup_by_both_names():
    catalog = InstrumentCatalog(StubClient(conditions()))
    await catalog.refresh()
    assert [i.symbol for i in catalog.universe({"EURUSD", "BTCUSD", "AAPL"})] == ["BTCUSD", "EURUSD"]
    assert catalog.get("EURUSD").broker_symbol == "EURUSDc"
    assert catalog.by_broker("EURUSDc").symbol == "EURUSD"
    assert catalog.by_broker("NOPE") is None
    with pytest.raises(KeyError):
        catalog.get("NOPE")


async def test_refresh_keeps_going_when_one_instrument_fails_and_keeps_old_entry():
    client = StubClient(conditions())
    catalog = InstrumentCatalog(client)
    await catalog.refresh()
    client.fail = {"XAUUSD"}
    errors = await catalog.refresh()
    assert list(errors) == ["XAUUSD"]
    assert catalog.get("XAUUSD").kind == "metal"  # onceki bilgi korunur


async def test_update_from_instrument_event():
    catalog = InstrumentCatalog(StubClient(conditions()))
    await catalog.refresh()
    changed = schema.parse_instrument(load("instrument_xauusd") | {"trade_mode": "trading_disabled"})
    catalog.update(changed)
    assert "XAUUSD" not in [i.symbol for i in catalog.universe()]
