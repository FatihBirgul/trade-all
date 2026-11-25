"""Bildirimler."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class NullNotifier:
    """Bildirim gondermeyen, yalnizca loglayan uygulama (testler ve push kurulmadan once)."""

    async def send(self, kind: str, title: str, body: str, data: dict | None = None) -> None:
        log.info("bildirim [%s] %s: %s", kind, title, body)
