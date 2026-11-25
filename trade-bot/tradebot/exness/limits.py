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


TRADING_RESERVE = 0.1  # genel kotanin bu orani emir istekleri (GET olmayanlar) icin ayrilir


class _Window:
    def __init__(self, limit: int, seconds: float):
        self.limit = max(1, int(limit))
        self.seconds = float(seconds)
        self.stamps: deque[float] = deque()

    def wait_time(self, now: float, reserve: int = 0) -> float:
        while self.stamps and now - self.stamps[0] >= self.seconds:
            self.stamps.popleft()
        allowed = max(1, self.limit - reserve)
        if len(self.stamps) < allowed:
            return 0.0
        return self.stamps[len(self.stamps) - allowed] + self.seconds - now

    def record(self, now: float) -> None:
        self.stamps.append(now)


class RateLimiter:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep):
        self._clock = clock
        self._sleep = sleep
        self._global: _Window | None = None
        self._methods: list[tuple[str, re.Pattern[str], _Window]] = []

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

    def _windows(self, method: str, path: str) -> list[tuple[_Window, int]]:
        bare = path.split("?", 1)[0]
        found = [(w, 0) for m, pattern, w in self._methods if m == method.upper() and pattern.match(bare)]
        if self._global is not None:
            # Veri okuma (mum taramasi) genel kotayi tuketip stop tasima / kapama isteklerini bekletmesin.
            reserve = int(self._global.limit * TRADING_RESERVE) if method.upper() == "GET" else 0
            found.append((self._global, reserve))
        return found

    async def acquire(self, method: str, path: str) -> None:
        """Kota dolacaksa bekler. Beklerken kilit tutulmaz: baska bir uca giden istek (or. pozisyon
        kapama) kendi penceresi bossa mum isteklerinin arkasinda sira beklemez."""
        windows = self._windows(method, path)
        while True:
            now = self._clock()
            wait = max((w.wait_time(now, reserve) for w, reserve in windows), default=0.0)
            if wait <= 0:
                for window, _ in windows:  # kontrol ile kayit arasinda await yok: yaris olmaz
                    window.record(now)
                return
            await self._sleep(wait)
