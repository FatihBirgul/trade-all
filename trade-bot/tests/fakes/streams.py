"""FakeExness'e bagli sahte akislar: gercek WebSocket yerine dinleyici kaydi."""

from __future__ import annotations

import asyncio


class FakeStream:
    def __init__(self, fake, path, on_message, name):
        self.path, self.name = path, name
        self.connected = True
        self.connections = 1
        self.subscriptions: list[dict] = []
        self._down_for = 0.0
        self._on_message = on_message
        (fake.tick_listeners if path.endswith("/ticks") else fake.event_listeners).append(self._deliver)

    async def _deliver(self, message):
        if self.connected:
            await self._on_message(message)

    def set_subscriptions(self, messages):
        self.subscriptions = list(messages)

    def add_subscription(self, message):
        self.subscriptions.append(message)

    async def subscribe(self, message):
        self.subscriptions.append(message)

    def disconnected_for(self) -> float:
        return 0.0 if self.connected else self._down_for

    def go_down(self, seconds=0.0):
        self.connected, self._down_for = False, seconds

    def come_up(self):
        self.connected, self._down_for = True, 0.0
        self.connections += 1

    async def run(self):
        await asyncio.Event().wait()

    def stop(self):
        pass


def stream_factory(fake):
    created: list[FakeStream] = []

    def factory(client, path, on_message, name):
        stream = FakeStream(fake, path, on_message, name)
        created.append(stream)
        return stream

    factory.created = created
    return factory
