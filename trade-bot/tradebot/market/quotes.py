"""Son fiyatlar ve spread istatistigi."""

from __future__ import annotations

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
        # (zaman, spread, agirlik). Canli tick'in agirligi 1'dir; yeniden baslatmadan geri yuklenen bir ornek,
        # ozetledigi tick sayisi kadar agirlik tasir (bkz. snapshot).
        self._spreads: dict[str, deque[tuple[float, float, float]]] = {}

    def on_tick(self, tick: Tick) -> None:
        if not (tick.bid > 0 and tick.ask >= tick.bid):
            return
        self._last[tick.symbol] = tick
        samples = self._spreads.setdefault(tick.symbol, deque(maxlen=8000))
        samples.append((tick.time, tick.ask - tick.bid, 1.0))

    def quote(self, symbol: str) -> dict | None:
        tick = self._last.get(symbol)
        if tick is None:
            return None
        return {"bid": tick.bid, "ask": tick.ask, "spread": tick.ask - tick.bid, "time": tick.time}

    def age(self, symbol: str) -> float | None:
        tick = self._last.get(symbol)
        return None if tick is None else self._clock() - tick.time

    def snapshot(self, limit: int = 200) -> dict[str, list[tuple[float, float, float]]]:
        """Penceredeki spread orneklerinin kalici saklanacak ozeti: sembol basina en cok `limit` kayit.

        Ornek sayisi `limit`i asiyorsa ardisik ornekler `limit` kovaya bolunur; her kova AGIRLIKLI MEDYAN
        spread'i, orta zamani ve kovadaki toplam agirligi tasir. Boylece geri yuklenen gecmis, yeni gelen
        tick'ler karsisinda gercek agirligini korur: yeniden baslatilmis bot, hic durmamis botla ayni siniri
        hesaplar (yogun sembolde gecmisin 200 ornege inip yeni spread'e hizla teslim olmasi engellenir).
        Ornek sayisi `limit`ten azsa hepsi oldugu gibi saklanir: "en az min_ticks ornek" kurali, gercekte o
        kadar tick toplanmamis sembol icin geri yuklemeden sonra da saglanmaz.
        """
        cutoff = self._clock() - self._window
        out: dict[str, list[tuple[float, float, float]]] = {}
        for symbol, samples in self._spreads.items():
            recent = [item for item in samples if item[0] >= cutoff]
            if not recent:
                continue
            if len(recent) > limit:
                size = len(recent) / limit
                buckets = [recent[int(i * size):int((i + 1) * size)] for i in range(limit)]
                recent = [(bucket[len(bucket) // 2][0], _weighted_median(bucket), sum(w for _, _, w in bucket))
                          for bucket in buckets if bucket]
            out[symbol] = recent
        return out

    def restore(self, saved: dict[str, list[tuple[float, float, float]]]) -> int:
        """Yeniden baslatmadan onceki spread orneklerini geri yukler -> yuklenen kayit sayisi.

        Kural DEGISMEZ: `max_spread` yine yalnizca son `window` saniyenin orneklerine bakar ve en az
        `min_ticks` kayit ister; pencereden eski ya da gelecekten gorunen ornekler hic yuklenmez. Yalnizca
        spread ornekleri yuklenir; son fiyat (quote) yuklenmez, taze tick gelmeden islem degerlendirilmez.
        Ornegi zaten olan sembole yukleme yapilmaz: iki kez cagrilmasi ornekleri cogaltamaz.
        """
        now = self._clock()
        cutoff = now - self._window
        loaded = 0
        for symbol, items in saved.items():
            if self._spreads.get(symbol):
                continue
            fresh = sorted({(float(at), float(spread), float(weight)) for at, spread, weight in items
                            if cutoff <= float(at) <= now and float(spread) >= 0 and float(weight) >= 1})
            if not fresh:
                continue
            self._spreads[symbol] = deque(fresh, maxlen=8000)
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
        median = _weighted_median(samples)
        return median * self._factor if median > 0 else None


def _weighted_median(samples) -> float:
    """Agirlikli medyan; butun agirliklar 1 ise `statistics.median` ile ayni sonucu verir."""
    ordered = sorted((spread, weight) for _, spread, weight in samples)
    total = sum(weight for _, weight in ordered)
    running = 0.0
    for index, (spread, weight) in enumerate(ordered):
        running += weight
        if running > total / 2:
            return spread
        if running == total / 2:  # tam ortada: iki komsunun ortalamasi (cift sayida esit agirlik)
            return (spread + ordered[index + 1][0]) / 2
    return ordered[-1][0]
