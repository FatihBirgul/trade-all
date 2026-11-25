"""Haftalik ekonomik takvim (ForexFactory / faireconomy JSON akisi).

Takvim 6 saatte bir yenilenir ve SQLite'ta saklanir; servis yeniden baslasa da son gecerli takvim
kullanilir. Alinamayan ya da bozuk yanit mevcut takvimi silmez. 24 saatten uzun suredir yenilenemiyorsa
`stale()` True doner: bot calismaya devam eder, kullanici uyarilir (karar servis dongusundedir).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

import httpx

from ..store.repo import Repo

log = logging.getLogger(__name__)

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
REFRESH_SECONDS = 6 * 3600
RETRY_SECONDS = 900  # basarisiz denemeden sonra en erken yeniden deneme (kaynak sik istegi engeller)
STALE_SECONDS = 24 * 3600
_KEY = "news_calendar"
_IMPACTS = {"high": "high", "medium": "medium", "low": "low", "holiday": "holiday"}


@dataclass(frozen=True)
class NewsEvent:
    currency: str
    title: str
    at: float  # UTC epoch saniye
    impact: str  # high | medium | low | holiday


def parse_calendar(raw: Any) -> list[NewsEvent]:
    """Akis kayitlari -> olaylar (zamana gore sirali). Bozuk ya da saat dilimi belirsiz kayit atlanir."""
    events: list[NewsEvent] = []
    for row in raw if isinstance(raw, list) else []:
        if not isinstance(row, dict):
            continue
        currency, stamp, impact = row.get("country"), row.get("date"), row.get("impact")
        if not isinstance(currency, str) or not isinstance(stamp, str) or not isinstance(impact, str):
            continue
        level = _IMPACTS.get(impact.strip().lower())
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if level is None or moment.tzinfo is None or not 3 <= len(currency.strip()) <= 4:
            continue  # ofsetsiz zaman tahmin edilmez: yanlis saatte veto, hic veto olmamasindan kotudur
        events.append(NewsEvent(currency.strip().upper(), str(row.get("title") or "")[:120], moment.timestamp(), level))
    return sorted(events, key=lambda e: (e.at, e.currency, e.title))


class NewsCalendar:
    def __init__(self, repo: Repo, *, transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], float] = time.time, url: str = FF_URL):
        self._repo = repo
        self._clock = clock
        self._url = url
        self._http = httpx.AsyncClient(transport=transport, timeout=15.0, follow_redirects=True)
        self._first_attempt: float | None = None
        self._last_attempt: float | None = None

    async def aclose(self) -> None:
        await self._http.aclose()

    def _stored(self) -> dict:
        value = self._repo.get_setting(_KEY)
        return value if isinstance(value, dict) else {}

    def events(self) -> list[NewsEvent]:
        events = []
        for row in self._stored().get("events") or []:
            try:  # bozuk ya da eski bicimli kayit taramayi durdurmamali
                events.append(NewsEvent(**row))
            except TypeError:
                continue
        return events

    def fetched_at(self) -> float | None:
        return self._stored().get("fetched_at")

    def age(self) -> float | None:
        """Son basarili yenilemeden bu yana gecen sure; hic alinamadiysa None."""
        fetched = self.fetched_at()
        return None if fetched is None else self._clock() - fetched

    def due(self) -> bool:
        now = self._clock()
        if self._last_attempt is not None and now - self._last_attempt < RETRY_SECONDS:
            return False
        age = self.age()
        return age is None or age >= REFRESH_SECONDS

    def never_fetched(self) -> bool:
        return self.fetched_at() is None

    def stale(self) -> bool:
        """Gecerli bir takvim yok mu? Hic alinamadiysa hemen, alindiysa 24 saat yenilenemeyince.

        Hic alinamamis takvim "eski" degil, YOKtur: haber penceresi korumasi calismaz ve kullanici
        bunu 24 saat beklemeden (ve servis yeniden baslasa da) gormelidir.
        """
        age = self.age()
        return age is None or age >= STALE_SECONDS

    async def refresh(self) -> bool:
        now = self._clock()
        self._last_attempt = now
        if self._first_attempt is None:
            self._first_attempt = now
        try:
            response = await self._http.get(self._url, headers={"Accept": "application/json"})
            response.raise_for_status()
            events = parse_calendar(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("haber takvimi alinamadi: %s", type(exc).__name__)
            return False
        if not events:
            log.warning("haber takvimi bos ya da taninmayan bicimde geldi; mevcut takvim korunuyor")
            return False
        self._repo.set_setting(_KEY, {"fetched_at": now, "events": [asdict(e) for e in events]})
        return True
