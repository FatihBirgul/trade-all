"""Gercek Exness islem saatleri + hafta sonu boslugu olan mumlar: V9 seriyi veri hatasi sayip elememeli.

Canlida goruldu: 30 sembolun 28'i "missing candle during open or unknown broker hours" ile eleniyordu.
V9, piyasa acilmadan onceki 30 dakikayi (OPENING_SOON) "kapali" saymadigi icin hafta sonu boslugu iceren
her H1 serisini reddediyordu; H1 256 mum her zaman bir hafta sonu icerir.
"""
import json
import logging
import pathlib
from datetime import datetime, timezone

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
