"""Son fiyatlar ve spread istatistigi."""

from __future__ import annotations

import statistics
import time
from collections import deque
from collections.abc import Callable

from ..exness.schema import Tick


SAMPLE_CAP = 8000  # sembol basina tutulan en yeni spread ornegi sayisi


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
        self._unsaved: dict[str, list[tuple[float, float]]] = {}  # son `drain_new`den beri gelen ornekler

    def on_tick(self, tick: Tick) -> None:
        if not (tick.bid > 0 and tick.ask >= tick.bid):
            return
        self._last[tick.symbol] = tick
        sample = (tick.time, tick.ask - tick.bid)
        self._spreads.setdefault(tick.symbol, deque(maxlen=SAMPLE_CAP)).append(sample)
        fresh = self._unsaved.setdefault(tick.symbol, [])
        fresh.append(sample)
        if len(fresh) > SAMPLE_CAP:  # kayit uzun sure yapilamadiysa bellek buyumesin
            del fresh[:-SAMPLE_CAP]

    def quote(self, symbol: str) -> dict | None:
        tick = self._last.get(symbol)
        if tick is None:
            return None
        return {"bid": tick.bid, "ask": tick.ask, "spread": tick.ask - tick.bid, "time": tick.time}

    def age(self, symbol: str) -> float | None:
        tick = self._last.get(symbol)
        return None if tick is None else self._clock() - tick.time

    def drain_new(self) -> dict[str, list[tuple[float, float]]]:
        """Son cagridan beri gelen spread ornekleri (kalici saklamak icin); cagri listeyi bosaltir."""
        fresh, self._unsaved = self._unsaved, {}
        return {symbol: items for symbol, items in fresh.items() if items}

    def restore(self, saved: dict[str, list[tuple[float, float]]]) -> int:
        """Yeniden baslatmadan onceki spread orneklerini geri yukler -> yuklenen ornek sayisi.

        Ornekler OZETLENMEDEN, tick tick saklanir ve aynen geri yuklenir: yeniden baslatilmis bot, hic durmamis
        botun elindeki orneklerin (kesinti sirasinda kacanlar disinda) aynisina sahip olur. Kural DEGISMEZ:
        `max_spread` yine yalnizca son `window` saniyenin orneklerine bakar ve en az `min_ticks` ornek ister;
        pencereden eski ya da gelecekten gorunen ornekler hic yuklenmez; sembol basina en yeni SAMPLE_CAP ornek
        tutulur (canlidaki sinirla ayni). Son fiyat (quote) yuklenmez: taze tick gelmeden islem degerlendirilmez.
        Ornegi zaten olan sembole yukleme yapilmaz: iki kez cagrilmasi ornekleri cogaltamaz.
        """
        now = self._clock()
        cutoff = now - self._window
        loaded = 0
        for symbol, items in saved.items():
            if self._spreads.get(symbol):
                continue
            fresh = sorted((float(at), float(spread)) for at, spread in items
                           if cutoff <= float(at) <= now and float(spread) >= 0)
            if not fresh:
                continue
            self._spreads[symbol] = deque(fresh, maxlen=SAMPLE_CAP)
            loaded += len(self._spreads[symbol])
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
