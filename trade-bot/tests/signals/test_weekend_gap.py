"""Gercek Exness islem saatleri + hafta sonu boslugu olan mumlar: V9 seriyi veri hatasi sayip elememeli.

Canlida goruldu: 30 sembolun 28'i "missing candle during open or unknown broker hours" ile eleniyordu.
V9, piyasa acilmadan onceki 30 dakikayi (OPENING_SOON) "kapali" saymadigi icin hafta sonu boslugu iceren
her H1 serisini reddediyordu; H1 256 mum her zaman bir hafta sonu icerir.
"""
import json
import logging
import pathlib
from datetime import datetime, timezone

import pytest

import tests.fakes.exness as fx
from tests.app_helpers import NOW, feed_ticks, started
from tradebot.exness import schema

REAL = json.loads((pathlib.Path(__file__).parent.parent / "exness/fixtures/real/conditions/EURUSD.json").read_text())

def gapped(tf, hours, end, start_price=1.05, step=0.00005, count=256):
    from tradebot.signals import v9
    v9.engine()
    from forex.sessions import broker_status
    rows, t = [], end - tf
    def is_open(ts):
        return broker_status(datetime.fromtimestamp(ts, timezone.utc), "", True, hours)["status"] in ("OPEN", "CLOSING_SOON")
    while len(rows) < count:
        if is_open(t) or is_open(t + tf - 60):
            rows.append(t)
        t -= tf
    out, price = [], start_price
    for ts in reversed(rows):
        close = price + step
        out.append({"time": ts, "open": price, "high": max(price, close) + 0.0003, "low": min(price, close) - 0.0003, "close": close, "volume": 100.0})
        price = close
    return out

async def test_v9_accepts_series_with_weekend_gap_under_real_broker_hours(tmp_path, caplog, monkeypatch):
    caplog.set_level(logging.INFO)
    monkeypatch.setitem(fx.DEFAULT_INSTRUMENTS, "EURUSD", {**fx.conditions("EURUSD"), "trade_sessions": REAL["trade_sessions"]})
    app = await started(tmp_path)
    hours = schema._trading_hours(REAL["trade_sessions"])
    end = (int(NOW) // 900) * 900
    for name, tf in (("M15", 900), ("H1", 3600), ("H4", 14400)):
        app.fake.set_candles("EURUSD", name, gapped(tf, hours, (end // tf) * tf))
    last = app.fake.candles[("EURUSD", "M15")][-1]["close"]
    await feed_ticks(app, "EURUSD", last, last + 0.00002, NOW)
    series = app.fake.candles[("EURUSD", "H1")]
    assert any(b["time"] - a["time"] > 3600 for a, b in zip(series, series[1:]))  # seride gercekten bosluk var
    summary = await app.bot.on_bar_close()
    verdict = [r.message for r in caplog.records if r.message.startswith("aday yok EURUSD")]
    assert verdict and "missing candle" not in verdict[0], verdict
    assert not any(code in verdict[0] for code in ("INSUFFICIENT_DATA", "STALE_DATA", "PROVIDER_UNAVAILABLE")), verdict
    assert summary.errors == 0


ROLLOVER = NOW - 10 * 3600  # Persembe 22:00 UTC: gunluk devir, tarama anindan 10 saat once


async def scan_with_missing_m15(tmp_path, caplog, monkeypatch, missing):
    caplog.set_level(logging.INFO)
    monkeypatch.setitem(fx.DEFAULT_INSTRUMENTS, "EURUSD", {**fx.conditions("EURUSD"), "trade_sessions": REAL["trade_sessions"]})
    app = await started(tmp_path)
    hours = schema._trading_hours(REAL["trade_sessions"])
    end = (int(NOW) // 900) * 900
    for name, tf in (("M15", 900), ("H1", 3600), ("H4", 14400)):
        rows = gapped(tf, hours, (end // tf) * tf, count=256 + len(missing) if name == "M15" else 256)
        if name == "M15":
            assert all(any(r["time"] == t for r in rows) for t in missing)
            rows = [r for r in rows if r["time"] not in missing]
        app.fake.set_candles("EURUSD", name, rows)
    last = app.fake.candles[("EURUSD", "M15")][-1]["close"]
    await feed_ticks(app, "EURUSD", last, last + 0.00002, NOW)
    caplog.clear()  # onceki cagrinin kaydi yeniden okunmasin
    await app.bot.on_bar_close()
    return [r.message for r in caplog.records if r.message.startswith("aday yok EURUSD")][-1]


async def test_v9_tolerates_one_quiet_m15_bar_at_the_daily_rollover(tmp_path, caplog, monkeypatch):
    """Canlida goruldu: gece 22:00 UTC devrinde bazi sembollerde 15 dakika hic fiyat gelmiyor; borsa o mumu
    hic uretmiyor ama islem saatlerini "acik" beyan ediyor. Tek mumluk bu bosluk veri hatasi sayilmaz."""
    verdict = await scan_with_missing_m15(tmp_path, caplog, monkeypatch, {ROLLOVER})
    assert not any(code in verdict for code in ("INSUFFICIENT_DATA", "STALE_DATA", "PROVIDER_UNAVAILABLE")), verdict
    # Art arda iki gecenin devri de olabilir.
    two_nights = await scan_with_missing_m15(tmp_path / "iki", caplog, monkeypatch, {ROLLOVER, ROLLOVER - 86400})
    assert "INSUFFICIENT_DATA" not in two_nights, two_nights


@pytest.mark.parametrize("missing, why", [
    ({ROLLOVER, ROLLOVER + 900}, "art arda iki mum"),
    ({NOW - 3600}, "son dort saatin icinde"),
    ({ROLLOVER - 8 * 3600}, "devir saati disinda (New York 09:00)"),
    ({ROLLOVER - d * 86400 + q * 1800 for d in range(3) for q in range(2)} - {ROLLOVER + 1800},
     "devir saatlerinde ama dortten fazla (bes) bosluk"),
])
async def test_v9_still_rejects_wider_recent_or_too_many_gaps(tmp_path, caplog, monkeypatch, missing, why):
    verdict = await scan_with_missing_m15(tmp_path, caplog, monkeypatch, missing)
    assert "INSUFFICIENT_DATA" in verdict and "missing candle" in verdict, (why, verdict)


def test_a_quiet_bar_is_tolerated_on_m15_only():
    from tradebot.signals import v9
    v9.engine()
    from forex import contracts
    from forex.core import DataError

    hours = schema._trading_hours(REAL["trade_sessions"])
    meta = {"broker_hours": hours, "trade_allowed": True}
    for name, tf in (("H1", 3600), ("H4", 14400)):
        end = (int(NOW) // tf) * tf
        rows = [{**r, "tick_volume": 10.0} for r in gapped(tf, hours, end, count=257)]
        for row in rows:
            row.pop("volume")
        hole = rows[-40]["time"]  # piyasa acikken, eski bir mum
        with pytest.raises(DataError, match="missing candle during open"):
            contracts._bars([r for r in rows if r["time"] != hole], name, end, meta, "EURUSD", "x")


def m15_series(hours, end, missing):
    rows = [{**r, "tick_volume": 10.0} for r in gapped(900, hours, end, count=256 + len(missing))]
    for row in rows:
        row.pop("volume")
    assert all(any(r["time"] == t for r in rows) for t in missing)
    return [r for r in rows if r["time"] not in missing]


def test_quiet_bar_limits_are_exact():
    """Sinirlar tek tek: bosluktan sonra en az 16 mum; seri basina en cok 4; yalnizca acik saatte."""
    from tradebot.signals import v9
    v9.engine()
    from forex import contracts
    from forex.core import DataError

    hours = schema._trading_hours(REAL["trade_sessions"])
    meta = {"broker_hours": hours, "trade_allowed": True}

    def accepted(end, missing, metadata=meta):
        try:
            contracts._bars(m15_series(hours, end, missing), "M15", end, metadata, "EURUSD", "x")
            return True
        except DataError:
            return False

    # Bosluktan sonra tam 16 mum: kabul; 15 mum: ret. (Devir mumu 22:00; tarama ani buna gore secilir.)
    assert accepted(ROLLOVER + 900 + 16 * 900, {ROLLOVER})
    assert not accepted(ROLLOVER + 900 + 15 * 900, {ROLLOVER})
    # Dort bosluk kabul, besincisi ret (uc gecenin devir saatleri icinde).
    nights = [ROLLOVER - d * 86400 + q * 1800 for d in range(3) for q in range(2)]
    assert accepted(NOW, set(nights[1:5])) and not accepted(NOW, set(nights[1:6]))
    # Islem saatleri "acik" demiyorsa (islem kapali ya da saatler okunamiyor) hos gorulmez.
    assert not accepted(NOW, {ROLLOVER}, {"broker_hours": hours, "trade_allowed": False})
    broken = {"timezone": "UTC", "weekly": {str(d): [["aa:bb", "24:00"]] for d in range(7)}}
    assert not accepted(NOW, {ROLLOVER}, {"broker_hours": broken, "trade_allowed": True})
    # M5 gibi baska zaman dilimlerinde de hos gorulmez (H1/H4 yukaridaki testte).
    m5 = [{**r, "tick_volume": 10.0} for r in gapped(300, hours, NOW, count=257)]
    for row in m5:
        row.pop("volume")
    hole = next(r["time"] for r in m5 if r["time"] == ROLLOVER)
    with pytest.raises(DataError):
        contracts._bars([r for r in m5 if r["time"] != hole], "M5", NOW, meta, "EURUSD", "x")
