"""Yeniden baglanan WebSocket akisi.

Akislar kalici degildir: kopan baglantida kacirilan olaylar tekrar gelmez. Bu yuzden her yeniden
baglanmada abonelikler bastan gonderilir; durum toparlama cagiranin isidir (snapshot ile mutabakat).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from . import schema

log = logging.getLogger(__name__)

Connect = Callable[[str, dict[str, str]], Awaitable[Any]]


async def _default_connect(url: str, headers: dict[str, str]):
    from websockets.asyncio.client import connect

    return await connect(url, additional_headers=headers, subprotocols=[schema.WS_SUBPROTOCOL],
                         open_timeout=15, ping_interval=20, ping_timeout=20, max_size=4 * 1024 * 1024)


class Stream:
    def __init__(self, client, path: str, on_message: Callable[[dict], Awaitable[None]], *,
                 connect: Connect | None = None, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 clock: Callable[[], float] = time.monotonic, backoff_start: float = 1.0,
                 backoff_max: float = 60.0, name: str | None = None):
        self.client = client
        self.path = path
        self.name = name or path.rsplit("/", 1)[-1]
        self.connected = False
        self.connections = 0  # basarili baglanti sayisi; artisi yeniden baglanmayi gosterir
        self.last_message_at: float | None = None
        self.disconnected_since: float | None = None
        self._on_message = on_message
        self._connect = connect or _default_connect
        self._sleep = sleep
        self._clock = clock
        self._backoff = (backoff_start, backoff_max)
        self._subscriptions: list[dict] = []
        self.subscription_delay = 0.0  # abonelik mesajlari arasinda bekleme (abonelik hiz siniri icin)
        self._socket = None
        self._stopped = False
        self.disconnected_since = clock()

    def add_subscription(self, message: dict) -> None:
        """Her (yeniden) baglanmada gonderilecek abonelik mesaji."""
        self._subscriptions.append(message)

    def set_subscriptions(self, messages: list[dict]) -> None:
        self._subscriptions = list(messages)

    async def subscribe(self, message: dict) -> None:
        """Aboneligi kaydeder; baglanti aciksa hemen de gonderir."""
        self.add_subscription(message)
        if self._socket is not None and self.connected:
            await self._socket.send(json.dumps(message))

    def disconnected_for(self) -> float:
        return 0.0 if self.connected or self.disconnected_since is None else self._clock() - self.disconnected_since

    def stop(self) -> None:
        self._stopped = True
        socket = self._socket
        if socket is not None:
            asyncio.ensure_future(socket.close())

    async def run(self) -> None:
        start, maximum = self._backoff
        delay = start
        while not self._stopped:
            received = False
            socket = None
            try:
                url, headers = await self.client.ws_endpoint(self.path)
                socket = await self._connect(url, headers)
                self._socket = socket
                for index, message in enumerate(list(self._subscriptions)):
                    if index and self.subscription_delay > 0:
                        await self._sleep(self.subscription_delay)
                    await socket.send(json.dumps(message))
                self.connected = True
                self.connections += 1
                self.disconnected_since = None
                log.info("akis baglandi: %s", self.name)
                async for raw in socket:
                    received = True
                    self.last_message_at = self._clock()
                    try:
                        message = json.loads(raw)
                    except (ValueError, TypeError):
                        continue
                    try:
                        await self._on_message(message)
                    except asyncio.CancelledError:
                        raise
                    except Exception:  # tek bir mesajin hatasi akisi dusurmemeli
                        log.exception("akis mesaji islenemedi: %s", self.name)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # baglanti/el sikisma hatalari: bekle ve yeniden dene
                log.warning("akis koptu: %s (%s)", self.name, type(exc).__name__)
            finally:
                was_connected = self.connected
                self.connected = False
                self._socket = None
                if was_connected or self.disconnected_since is None:
                    self.disconnected_since = self._clock()
                if socket is not None:
                    try:
                        await socket.close()
                    except Exception:
                        pass
            if self._stopped:
                break
            if received:
                delay = start
            await self._sleep(delay)
            delay = min(delay * 2, maximum)
