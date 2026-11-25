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

    def snapshot(self, limit: int = 200) -> dict[str, list[tuple[float, float]]]:
        """Penceredeki spread orneklerinin kalici saklanacak ozeti: sembol basina en cok `limit` ornek.

        Ornekler pencereye ESIT ARALIKLA yayilir (yalnizca son saniyeler degil), boylece medyan korunur.
        Ornek sayisi `limit`ten azsa hepsi saklanir: geri yuklemede "en az min_ticks ornek" kurali, gercekte
        o kadar ornek toplanmis sembol icin saglanir, toplanmamis sembol icin saglanmaz.
        """
        cutoff = self._clock() - self._window
        out: dict[str, list[tuple[float, float]]] = {}
        for symbol, samples in self._spreads.items():
            recent = [item for item in samples if item[0] >= cutoff]
            if not recent:
                continue
            if len(recent) > limit:
                step = len(recent) / limit
                recent = [recent[int(i * step)] for i in range(limit)]
            out[symbol] = recent
        return out

    def restore(self, saved: dict[str, list[tuple[float, float]]]) -> int:
        """Yeniden baslatmadan onceki spread orneklerini geri yukler -> yuklenen ornek sayisi.

        Kural DEGISMEZ: `max_spread` yine yalnizca son `window` saniyenin orneklerine bakar ve en az
        `min_ticks` ornek ister; pencereden eski ya da gelecekten gorunen ornekler hic yuklenmez. Yalnizca
        spread ornekleri yuklenir; son fiyat (quote) yuklenmez, taze tick gelmeden islem degerlendirilmez.
        """
        now = self._clock()
        cutoff = now - self._window
        loaded = 0
        for symbol, items in saved.items():
            fresh = sorted((float(at), float(spread)) for at, spread in items
                           if cutoff <= float(at) <= now and float(spread) >= 0)
            if not fresh:
                continue
            samples = self._spreads.setdefault(symbol, deque(maxlen=8000))
            existing = list(samples)
            samples.clear()
            samples.extend(sorted(fresh + existing))
            loaded += len(fresh)
        return loaded

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
