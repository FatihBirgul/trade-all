"""Ayristiricilarin VPS kesfinden gelen GERCEK Exness yanitlariyla dogrulanmasi (cent hesap, USC)."""
import json
from pathlib import Path

import pytest

from tradebot.exness import schema
from tradebot.market.catalog import in_universe
from tradebot.signals.provider import RateConverter

REAL = Path(__file__).parent / "fixtures" / "real"


def load(name):
    return json.loads((REAL / f"{name}.json").read_text(encoding="utf-8"))


def instruments():
    names = schema.parse_instrument_names(load("instruments"))
    return {name: schema.parse_instrument(load(f"conditions/{name}")) for name in names}


def test_every_real_instrument_parses_and_is_classified():
    parsed = instruments()
    assert len(parsed) == 58
    kinds = {}
    for instrument in parsed.values():
        kinds[instrument.kind] = kinds.get(instrument.kind, 0) + 1
    assert kinds == {"forex": 26, "metal": 2, "crypto": 4, "other": 26}
    # Cent hesapta semboller eksiz gelir (EURUSD); kanonik ad ile broker adi aynidir.
    assert all(i.symbol == i.broker_symbol == name for name, i in parsed.items())


def test_bot_universe_from_real_account():
    parsed = instruments()
    universe = sorted(name for name, i in parsed.items() if in_universe(i))
    assert len(universe) == 30  # 26 forex + XAUUSD, XAGUSD + BTCUSD, ETHUSD
    assert {"EURUSD", "USDJPY", "USDHKD", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD"} <= set(universe)
    for excluded in ("BTCUSDT", "ETHBTC", "US30", "US500", "USTEC", "UKOIL", "USOIL",  # evren disi turler
                     "USDUSC", "EUREUC", "MBTUSD", "TETUSD"):  # cent/donusum yardimci enstrumanlari
        assert excluded not in universe, excluded
    # Islem kapali enstruman hicbir zaman evrende olmaz.
    assert all(parsed[name].tradable for name in universe)


def test_cent_contract_sizes_and_volume_rules():
    parsed = instruments()
    eurusd, gold, silver, btc = parsed["EURUSD"], parsed["XAUUSD"], parsed["XAGUSD"], parsed["BTCUSD"]
    # Cent hesap: 1 lot EURUSD = 1000 EUR (standart hesabin 1/100'u).
    assert eurusd.contract_size == 1000.0 and eurusd.digits == 5 and eurusd.tick_size == pytest.approx(1e-5)
    assert (eurusd.currency_base, eurusd.currency_profit, eurusd.currency_margin) == ("EUR", "USD", "EUR")
    assert (eurusd.volume_min, eurusd.volume_step, eurusd.volume_max) == (0.01, 0.01, 200.0)
    assert gold.contract_size == 1.0 and gold.digits == 3 and gold.kind == "metal"
    assert silver.contract_size == 50.0
    assert btc.contract_size == 0.01 and btc.digits == 2 and btc.kind == "crypto"
    assert parsed["USDJPY"].digits == 3 and parsed["USDJPY"].currency_profit == "JPY"
    # Kosullarda komisyon ve stop mesafesi alani yok: komisyon bilinmiyor (None), stop mesafesi 0.
    assert eurusd.commission_type is None and eurusd.stops_level == 0


def test_real_trading_sessions():
    parsed = instruments()
    forex = parsed["EURUSD"].trading_hours
    assert forex["timezone"] == "UTC"
    weekly = forex["weekly"]  # 0 = Pazartesi ... 6 = Pazar
    assert weekly["0"] == [["00:00", "24:00"]]
    assert weekly["4"] == [["00:00", "21:59"]]  # Cuma 21:58:59'da kapanir
    assert "5" not in weekly  # Cumartesi kapali
    assert weekly["6"] == [["22:05", "24:00"]]  # Pazar 22:05 acilis
    gold = parsed["XAUUSD"].trading_hours["weekly"]
    assert gold["0"] == [["00:00", "21:58"], ["23:01", "24:00"]]  # gunluk ara
    assert parsed["BTCUSD"].trading_hours["weekly"]["5"] == [["00:00", "24:00"]]  # kripto hafta sonu acik
    assert parsed["USDUSC"].trading_hours is None and parsed["USDUSC"].tradable is False


def test_real_account_snapshot_and_limits():
    account = schema.parse_account(load("account"), load("snapshot")["account_state"])
    assert account.currency == "USC" and account.leverage == 2000.0
    assert account.can_open is True and account.can_trade is True
    assert account.balance == 0.0 and account.equity == 0.0  # kesif aninda hesap bostu
    snapshot = schema.parse_snapshot(load("snapshot"))
    assert snapshot.positions == () and snapshot.orders == ()
    limits = schema.parse_limits(load("limits"))
    assert limits.global_rate == (15, 1.0)
    assert limits.max_candles == 1000 and limits.history_range_days == 30 and limits.history_age_days == 30
    methods = {(method, path): (limit, window) for method, path, limit, window in limits.methods}
    assert methods[("GET", "/v1/market-data/accounts/{account_id}/candles")] == (2, 1.0)
    assert methods[("POST", "/v1/trading/accounts/{account_id}/positions")] == (4, 1.0)
    assert methods[("GET", "/v1/trading/accounts/{account_id}/snapshot")] == (2, 1.0)
    assert limits.tick_subscription_rate == (25, 1.0, 100)
    assert limits.websocket["global_account_limits"]["max_active_connections"] == 5


@pytest.mark.parametrize("name, step", [("EURUSD_H1", 3600), ("XAUUSD_M15", 900), ("BTCUSD_H4", 14400)])
def test_real_candles(name, step):
    rows = schema.parse_candles(load(f"candles/{name}"))
    assert len(rows) == 20
    times = [row["time"] for row in rows]
    assert times == sorted(times) and all(t % step == 0 for t in times)  # eskiden yeniye, UTC hizali
    assert all(isinstance(t, int) for t in times)
    for row in rows:
        assert row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]
        assert row["tick_volume"] > 0


def test_real_empty_deal_history():
    assert schema.parse_deals(load("deals")) == ([], None)


def test_every_universe_profit_currency_converts_to_the_cent_account_currency():
    """Risk hesabi icin kar para birimi USC'ye cevrilebilmeli; cevrim evrendeki paritelerden yapilir."""
    parsed = instruments()
    universe = {name: i for name, i in parsed.items() if in_universe(i)}

    class Catalog:
        def get(self, symbol):
            return parsed[symbol]

    class Quotes:  # yalnizca evrendeki semboller icin fiyat akisi vardir
        def quote(self, symbol):
            return {"bid": 2.0, "ask": 2.0} if symbol in universe else None

    rates = RateConverter(Catalog(), Quotes())
    for name, instrument in universe.items():
        assert rates.bounds(instrument.currency_profit, "USC") is not None, name
    assert rates.rate("USD", "USC", "sell") == 100.0  # 1 USD = 100 USC
    assert rates.rate("JPY", "USC", "sell") == pytest.approx(100.0 / 2.0)  # USDJPY uzerinden
