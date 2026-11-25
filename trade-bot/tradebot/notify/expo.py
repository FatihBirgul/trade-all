"""Expo push bildirimleri.

Bildirim hicbir zaman bot akisini durdurmaz: gonderim hatalari loglanir, yukari tasinmaz.
Ayni olay (tur + sembol + pozisyon) 10 dakika icinde yalnizca bir kez bildirilir.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

import httpx

from ..store.repo import Repo

log = logging.getLogger(__name__)

EXPO_URL = "https://exp.host/--/api/v2/push/send"
DEDUP_SECONDS = 600.0
BATCH = 100
MAX_DATA_BYTES = 2500  # Expo yuk siniri ~4 KB; baslik ve govdeye yer kalsin


def _safe_data(kind: str, data: dict | None) -> dict:
    result: dict = {"kind": kind}
    for key, value in (data or {}).items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            candidate = {**result, str(key): value}
            if len(json.dumps(candidate)) <= MAX_DATA_BYTES:
                result = candidate
    return result


class ExpoNotifier:
    def __init__(self, repo: Repo, *, transport: httpx.AsyncBaseTransport | None = None,
                 clock: Callable[[], float] = time.time, dedup_seconds: float = DEDUP_SECONDS):
        self._repo = repo
        self._clock = clock
        self._dedup = dedup_seconds
        self._sent: dict[tuple, float] = {}
        self._http = httpx.AsyncClient(transport=transport, timeout=10.0)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def send(self, kind: str, title: str, body: str, data: dict | None = None) -> None:
        now = self._clock()
        key = (kind, (data or {}).get("symbol"), (data or {}).get("position_id"))
        last = self._sent.get(key)
        if last is not None and now - last < self._dedup:
            return
        tokens = self._repo.devices()
        if not tokens:
            return
        payload = _safe_data(kind, data)
        delivered = False
        for start in range(0, len(tokens), BATCH):
            batch = tokens[start:start + BATCH]
            messages = [{"to": token, "title": title, "body": body, "sound": "default", "priority": "high",
                         "channelId": "default", "data": payload} for token in batch]
            try:
                response = await self._http.post(EXPO_URL, json=messages,
                                                 headers={"Accept": "application/json"})
                response.raise_for_status()
                results = response.json().get("data", [])
            except (httpx.HTTPError, ValueError, AttributeError) as exc:
                log.warning("bildirim gonderilemedi (%s): %s", kind, type(exc).__name__)
                continue
            delivered = True
            for token, result in zip(batch, results if isinstance(results, list) else []):
                details = result.get("details") if isinstance(result, dict) else None
                if isinstance(details, dict) and details.get("error") == "DeviceNotRegistered":
                    self._repo.remove_device(token)  # uygulama kaldirilmis ya da token yenilenmis
        if delivered:
            self._sent[key] = now
            if len(self._sent) > 2000:
                cutoff = now - self._dedup
                self._sent = {k: v for k, v in self._sent.items() if v >= cutoff}
