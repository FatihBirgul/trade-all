"""Haber penceresi vetosu: yuksek etkili haberin +/- penceresinde ilgili sembollerde yeni bot islemi yok."""

from __future__ import annotations

from collections.abc import Iterable

from ..exness.schema import Instrument
from .calendar import NewsEvent


def currencies(instrument: Instrument) -> set[str]:
    """Sembolun iki bacagi. BTCUSD -> {BTC, USD}: USD haberleri kriptoyu ve altini da kapsar."""
    legs = {instrument.currency_base, instrument.currency_profit}
    if not all(legs):
        legs |= {instrument.symbol[:3], instrument.symbol[3:]}
    return {leg for leg in legs if leg}


def blocking_event(instrument: Instrument, events: Iterable[NewsEvent], *, now: float,
                   window_minutes: int) -> NewsEvent | None:
    """Pencere icindeki en yakin yuksek etkili haber; yoksa None."""
    legs = currencies(instrument)
    window = window_minutes * 60
    hits = [e for e in events if e.impact == "high" and e.currency in legs and abs(e.at - now) <= window]
    return min(hits, key=lambda e: abs(e.at - now)) if hits else None
