"""Kapanmis mumlarin SQLite onbellegi ve artimli cekme.

Yalnizca kapanmis mumlar saklanir ve dondurulur (`time + sure <= simdi`). Eksik mumlar (hafta sonu,
gunluk ara) uydurulmaz; V9 bosluklari broker saatlerine gore kendisi dogrular.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable

from ..exness import schema

DURATIONS = {"M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
DEFAULT_MAX_CANDLES = 500  # limit bilinmiyorsa temkinli deger; gercegi /limits'ten gelir
KEEP = 1500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL, tf TEXT NOT NULL, time INTEGER NOT NULL,
    open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL,
    PRIMARY KEY (symbol, tf, time)
) WITHOUT ROWID;
"""


class CandleStore:
    def __init__(self, db: sqlite3.Connection, client, catalog, *, clock: Callable[[], float] = time.time,
                 max_candles: int | None = None):
        self._db = db
        self._client = client
        self._catalog = catalog
        self._clock = clock
        self.max_candles = max_candles or DEFAULT_MAX_CANDLES
        self._db.executescript(_SCHEMA)

    def cached(self, symbol: str, tf: str, count: int = 256) -> list[dict]:
        """Onbellekteki son `count` kapanmis mum (eskiden yeniye). Ag istegi yapmaz."""
        duration = DURATIONS[tf]
        rows = self._db.execute(
            "SELECT time, open, high, low, close, volume FROM candles "
            "WHERE symbol = ? AND tf = ? AND time + ? <= ? ORDER BY time DESC LIMIT ?",
            (symbol, tf, duration, self._clock(), int(count))).fetchall()
        return [{"time": int(r[0]), "open": r[1], "high": r[2], "low": r[3], "close": r[4], "tick_volume": r[5]}
                for r in reversed(rows)]

    def _last_time(self, symbol: str, tf: str) -> int | None:
        row = self._db.execute("SELECT MAX(time) FROM candles WHERE symbol = ? AND tf = ?", (symbol, tf)).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    async def get(self, symbol: str, tf: str, count: int = 256) -> list[dict]:
        """Gerekirse yalnizca eksik araligi ceker, sonra onbellekten son `count` kapanmis mumu dondurur."""
        duration = DURATIONS[tf]
        now = self._clock()
        current_open = int(now // duration) * duration  # su an olusan mumun acilisi (UTC hizali)
        oldest_allowed = current_open - (self.max_candles - 1) * duration
        last = self._last_time(symbol, tf)
        start = None
        if last is None or last + duration < oldest_allowed:
            start = oldest_allowed
        elif last + 2 * duration <= now:  # last'tan sonraki mum kapanmis olabilir
            start = last + duration
        if start is not None:
            broker_symbol = self._catalog.get(symbol).broker_symbol
            path = schema.candles_path(self._client.account_id, broker_symbol, tf, start, now)
            rows = schema.parse_candles(await self._client.get(path))
            closed = [(symbol, tf, r["time"], r["open"], r["high"], r["low"], r["close"], r["tick_volume"])
                      for r in rows if r["time"] + duration <= now]
            with self._db:
                self._db.executemany("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)", closed)
                self._db.execute(
                    "DELETE FROM candles WHERE symbol = ? AND tf = ? AND time < ?",
                    (symbol, tf, current_open - KEEP * duration))
        return self.cached(symbol, tf, count)
