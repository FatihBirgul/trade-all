"""Kapanmis mumlarin SQLite onbellegi ve artimli cekme.

Yalnizca kapanmis mumlar saklanir ve dondurulur (`time + sure <= simdi`). Eksik mumlar (hafta sonu,
gunluk ara) uydurulmaz; V9 bosluklari broker saatlerine gore kendisi dogrular.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from collections.abc import Awaitable, Callable

from ..exness import schema
from ..exness.errors import ExnessAuthError
from ..store.db import transaction

log = logging.getLogger(__name__)

RETRY_DELAY = 1.0  # tek seferlik mum reddinden sonra yineleme oncesi bekleme (sn)
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
                 max_candles: int | None = None, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self._db = db
        self._client = client
        self._catalog = catalog
        self._clock = clock
        self._sleep = sleep
        self.transient_rejections = 0  # ikinci denemede gecen AUTH_INVALID_API_KEY retleri
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

    async def _fetch(self, path: str) -> dict:
        """Mum istegi. Canli sunucu ilk mum istegini ara sira AUTH_INVALID_API_KEY (1000) ile reddediyor,
        ayni bicimdeki sonraki istekler geciyor (kesif 2026-11-25: 9 istekten yalnizca ilki). Bu yuzden
        bu salt-okuma istegi yalnizca bu kod icin BIR kez yinelenir; ikinci ret cagirana aynen gider
        (kimlik kilidi devreye girer). Emir istekleri bu yoldan gecmez ve asla yinelenmez."""
        try:
            return await self._client.get(path)
        except ExnessAuthError as exc:
            if exc.code != schema.AUTH_INVALID_API_KEY:
                raise
            log.warning("mum istegi reddedildi (%s); bir kez yinelenecek", exc)
        await self._sleep(RETRY_DELAY)
        data = await self._client.get(path)
        self.transient_rejections += 1
        return data

    async def heal(self, symbol: str, tf: str, missing: int) -> bool:
        """Onbellekte eksik gorunen mumu (acilis zamani `missing`) borsadan yeniden ister -> geldi mi?

        `get` yalnizca son mumdan sonrasini ceker; arada kalmis bir bosluk kendiliginden kapanmaz. Burada
        yalnizca boslugun cevresi istenir (tek istek). Borsa da mum vermiyorsa bosluk gercektir (o surede
        hic fiyat gelmemistir) ve False doner.
        """
        duration = DURATIONS[tf]
        slot = int(missing // duration) * duration
        now = self._clock()
        broker_symbol = self._catalog.get(symbol).broker_symbol
        path = schema.candles_path(self._client.account_id, broker_symbol, tf, slot - 2 * duration,
                                   min(now, slot + 3 * duration))
        rows = schema.parse_candles(await self._fetch(path))
        closed = [(symbol, tf, r["time"], r["open"], r["high"], r["low"], r["close"], r["tick_volume"])
                  for r in rows if r["time"] + duration <= now]
        with transaction(self._db):
            self._db.executemany("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)", closed)
        return any(row[2] == slot for row in closed)

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
            rows = schema.parse_candles(await self._fetch(path))
            closed = [(symbol, tf, r["time"], r["open"], r["high"], r["low"], r["close"], r["tick_volume"])
                      for r in rows if r["time"] + duration <= now]
            with transaction(self._db):
                self._db.executemany("INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?,?)", closed)
                self._db.execute(
                    "DELETE FROM candles WHERE symbol = ? AND tf = ? AND time < ?",
                    (symbol, tf, current_open - KEEP * duration))
        return self.cached(symbol, tf, count)
