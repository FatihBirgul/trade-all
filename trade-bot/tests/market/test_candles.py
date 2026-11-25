import sqlite3
from datetime import datetime, timezone

import pytest

from tradebot.exness import schema
from tradebot.market.candles import CandleStore

M15 = 900
T0 = int(datetime(2026, 3, 16, 12, 0, tzinfo=timezone.utc).timestamp())


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


class Catalog:
    def get(self, symbol):
        return type("I", (), {"symbol": symbol, "broker_symbol": symbol + "c"})()


class CandleClient:
    """`from` dahil, `to` haric: API ile ayni aralik anlami."""
    account_id = "123456"

    def __init__(self, first, last, step=M15, skip=()):
        self.first, self.last, self.step, self.skip = first, last, step, set(skip)
        self.paths = []

    async def get(self, path):
        self.paths.append(path)
        query = dict(part.split("=") for part in path.split("?")[1].split("&"))
        start = datetime.fromisoformat(query["from"]).timestamp()
        end = datetime.fromisoformat(query["to"]).timestamp()
        rows = []
        t = self.first
        while t <= self.last:
            if start <= t < end and t not in self.skip:
                rows.append({"time": iso(t), "open": 1.0, "high": 1.2, "low": 0.9, "close": 1.1, "volume": 7})
            t += self.step
        return {"candles": rows}


def store(client, now, **kwargs):
    clock = {"now": now}
    return CandleStore(sqlite3.connect(":memory:"), client, Catalog(), clock=lambda: clock["now"], **kwargs), clock


async def test_candles_drop_unclosed_bar():
    now = T0 + 5 * M15 + 300  # 13:20 -> 13:15 mumu hala aciliyor
    client = CandleClient(T0 - 400 * M15, T0 + 5 * M15)
    candles, _ = store(client, now)
    rows = await candles.get("EURUSD", "M15", 256)
    assert len(rows) == 256
    assert rows[-1]["time"] == T0 + 4 * M15  # 13:00 mumu: 13:15'te kapandi
    assert all(row["time"] + M15 <= now for row in rows)
    assert rows[0]["time"] < rows[-1]["time"] and type(rows[-1]["time"]) is int
    assert set(rows[-1]) == {"time", "open", "high", "low", "close", "tick_volume"}
    assert "instrument=EURUSDc" in client.paths[0]


async def test_candles_incremental_fetch_requests_only_new_range():
    client = CandleClient(T0 - 400 * M15, T0 + 50 * M15)
    candles, clock = store(client, T0 + 5 * M15 + 300)
    await candles.get("EURUSD", "M15", 256)
    assert len(client.paths) == 1

    await candles.get("EURUSD", "M15", 256)  # yeni kapanmis mum olamaz: istek yok
    assert len(client.paths) == 1

    clock["now"] = T0 + 7 * M15 + 10  # 13:15 ve 13:30 mumlari kapandi
    rows = await candles.get("EURUSD", "M15", 256)
    assert len(client.paths) == 2
    assert f"from={schema._iso(T0 + 5 * M15)}" in client.paths[1]
    assert rows[-1]["time"] == T0 + 6 * M15 and len(rows) == 256


async def test_first_load_stays_within_request_limit_and_cached_reads_are_sync():
    client = CandleClient(T0 - 5000 * M15, T0 + 10 * M15)
    candles, _ = store(client, T0 + 300, max_candles=300)
    rows = await candles.get("EURUSD", "M15", 256)
    query = dict(part.split("=") for part in client.paths[0].split("?")[1].split("&"))
    span = datetime.fromisoformat(query["to"]).timestamp() - datetime.fromisoformat(query["from"]).timestamp()
    assert span <= 300 * M15
    assert len(rows) == 256
    assert candles.cached("EURUSD", "M15", 10) == rows[-10:]
    assert candles.cached("GBPUSD", "M15", 10) == []


async def test_weekend_gap_is_preserved_not_filled():
    gap = {T0 + n * M15 for n in range(-20, -10)}
    client = CandleClient(T0 - 400 * M15, T0 + 5 * M15, skip=gap)
    candles, _ = store(client, T0 + 5 * M15 + 300)
    rows = await candles.get("EURUSD", "M15", 256)
    times = {row["time"] for row in rows}
    assert not times & gap and len(rows) == 256


async def test_fetch_failure_propagates_and_cache_survives():
    from tradebot.exness.errors import ExnessUnavailable
    client = CandleClient(T0 - 400 * M15, T0 + 50 * M15)
    candles, clock = store(client, T0 + 300)
    await candles.get("EURUSD", "M15", 256)

    async def broken(path):
        raise ExnessUnavailable("gecici")
    client.get = broken
    clock["now"] = T0 + 10 * M15
    with pytest.raises(ExnessUnavailable):
        await candles.get("EURUSD", "M15", 256)
    assert len(candles.cached("EURUSD", "M15", 256)) == 256
