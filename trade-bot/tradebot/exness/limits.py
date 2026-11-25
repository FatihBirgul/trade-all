"""Yerel istek sayaci.

Limit degerleri koda gomulmez; `/limits` yanitindan gelir (`configure`). API kalan kotayi
soylemedigi icin gonderilen istekler burada kayan pencereyle sayilir ve kota dolacaksa beklenir.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from collections.abc import Awaitable, Callable, Iterable


class _Window:
    def __init__(self, limit: int, seconds: float):
        self.limit = max(1, int(limit))
        self.seconds = float(seconds)
        self.stamps: deque[float] = deque()

    def wait_time(self, now: float) -> float:
        while self.stamps and now - self.stamps[0] >= self.seconds:
            self.stamps.popleft()
        if len(self.stamps) < self.limit:
            return 0.0
        return self.stamps[0] + self.seconds - now

    def record(self, now: float) -> None:
        self.stamps.append(now)


class RateLimiter:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self._clock = clock
        self._sleep = sleep
        self._global: _Window | None = None
        self._methods: list[tuple[str, re.Pattern[str], _Window]] = []
        self._lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return self._global is not None

    def configure(self, *, global_rate: tuple[int, float] | None,
                  methods: Iterable[tuple[str, str, int, float]]) -> None:
        """methods: (HTTP metodu, OpenAPI yol sablonu, limit, pencere_sn)."""
        self._global = _Window(*global_rate) if global_rate else None
        self._methods = []
        for http_method, template, limit, seconds in methods:
            pattern = "".join("[^/]+" if part.startswith("{") else re.escape(part)
                              for part in re.split(r"(\{[^}]*\})", template))
            self._methods.append((http_method.upper(), re.compile("^" + pattern + "$"), _Window(limit, seconds)))

    def _windows(self, method: str, path: str) -> list[_Window]:
        bare = path.split("?", 1)[0]
        found = [w for m, pattern, w in self._methods if m == method.upper() and pattern.match(bare)]
        if self._global is not None:
            found.append(self._global)
        return found

    async def acquire(self, method: str, path: str) -> None:
        async with self._lock:
            windows = self._windows(method, path)
            while True:
                now = self._clock()
                wait = max((w.wait_time(now) for w in windows), default=0.0)
                if wait <= 0:
                    break
                await self._sleep(wait)
            now = self._clock()
            for window in windows:
                window.record(now)
