"""Son fiyatlar ve spread istatistigi."""

from __future__ import annotations

import statistics
import time
from collections import deque
from collections.abc import Callable

from ..exness.schema import Tick


class QuoteBook:
    """`max_spread`: son `window` saniyedeki tick spread medyaninin `factor` kati.

    Yeterli ornek yoksa None doner; V9 bu durumda islem acmaz (spread politikasi dogrulanamadi).
    """

    def __init__(self, *, clock: Callable[[], float] = time.time, window: float = 1800.0,
                 min_ticks: int = 100, factor: float = 3.0):
        self._clock = clock
        self._window = window
        self._min_ticks = min_ticks
        self._factor = factor
        self._last: dict[str, Tick] = {}
        self._spreads: dict[str, deque[tuple[float, float]]] = {}

    def on_tick(self, tick: Tick) -> None:
        if not (tick.bid > 0 and tick.ask >= tick.bid):
            return
        self._last[tick.symbol] = tick
        samples = self._spreads.setdefault(tick.symbol, deque(maxlen=8000))
        samples.append((tick.time, tick.ask - tick.bid))

    def quote(self, symbol: str) -> dict | None:
        tick = self._last.get(symbol)
        if tick is None:
            return None
        return {"bid": tick.bid, "ask": tick.ask, "spread": tick.ask - tick.bid, "time": tick.time}

    def age(self, symbol: str) -> float | None:
        tick = self._last.get(symbol)
        return None if tick is None else self._clock() - tick.time

    def max_spread(self, symbol: str) -> float | None:
        samples = self._spreads.get(symbol)
        if not samples:
            return None
        cutoff = self._clock() - self._window
        while samples and samples[0][0] < cutoff:
            samples.popleft()
        if len(samples) < self._min_ticks:
            return None
        median = statistics.median(spread for _, spread in samples)
        return median * self._factor if median > 0 else None
