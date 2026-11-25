"""Kademeli stop kararlari (spec §6.5). Saf fonksiyon: I/O yok, durum degistirmez.

R = |giris - ilk SL|. Cikis fiyati BUY icin bid, SELL icin ask'tir; boylece spread kendiliginden
hesaba girer (BUY'da SL bid'e gore tetiklenir). `cost_per_unit` komisyon gibi ek maliyetlerin fiyat
karsiligidir ve basa bas seviyesine eklenir.

Asamalar:
  1. Kar >= be_at_r      -> SL girise + maliyet (basa bas).
  2. Kar >= partial_at_r -> hacmin `partial_fraction` kadari kapatilir (adim ve en kucuk lot izin verirse).
  3. Sonrasinda          -> SL fiyati ATR(M15) x trail_atr_mult mesafeyle izler.
SL yalnizca lehte hareket eder; bu, kullanicinin elle koydugu SL'in zarar yonune alinmamasini da saglar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Literal

from ..config import ManageSettings
from ..exness.schema import Instrument
from ..store.repo import Trade


@dataclass(frozen=True)
class MoveSL:
    price: float
    stage: Literal["breakeven", "trail"]


@dataclass(frozen=True)
class PartialClose:
    volume: float


@dataclass(frozen=True)
class NoOp:
    reason: str  # "partial_skipped": hacim bolunemedi; asama yine de tamamlanmis sayilir


Action = MoveSL | PartialClose | NoOp


def _grid(value: float, step: float, rounding: str) -> float:
    quantum = Decimal(str(step))
    units = (Decimal(str(value)) / quantum).to_integral_value(rounding=rounding)
    return float(units * quantum)


def decide(trade: Trade, *, bid: float, ask: float, atr_m15: float | None, cost_per_unit: float,
           instrument: Instrument, settings: ManageSettings) -> list[Action]:
    risk = trade.initial_risk_r_price
    if not trade.manage or not trade.is_open or not risk or risk <= 0 or trade.volume <= 0:
        return []
    tick = instrument.tick_size
    if tick <= 0 or bid <= 0 or ask <= 0:
        return []
    buy = trade.side == "BUY"
    sign = 1.0 if buy else -1.0
    price = bid if buy else ask
    gain = (price - trade.entry) * sign

    def reached(multiple: float) -> bool:
        # Kayan nokta hatasi tam esikteki fiyati kacirmasin diye tick'in binde biri kadar pay.
        return gain >= multiple * risk - tick * 1e-3

    toward_profit, toward_loss = (ROUND_CEILING, ROUND_FLOOR) if buy else (ROUND_FLOOR, ROUND_CEILING)

    def better(candidate: float, reference: float | None) -> bool:
        return reference is None or (candidate - reference) * sign > tick / 2

    # Broker'in kabul edecegi en siki SL: fiyattan stops_level (en az bir tick) uzakta.
    distance = max(instrument.stops_level, 1) * tick
    limit = _grid(price - sign * distance, tick, toward_loss)

    actions: list[Action] = []
    target: MoveSL | None = None
    if settings.be_enabled and reached(settings.be_at_r):
        level = _grid(trade.entry + sign * max(cost_per_unit, 0.0), tick, toward_profit)
        if not trade.be_done or better(level, trade.sl):
            target = MoveSL(level, "breakeven")
    # Iz suren stop kismi kapatmadan sonra baslar; kismi kapatma kapaliysa ayni esige (partial_at_r) ulasinca.
    trailing = trade.partial_done or (not settings.partial_enabled and reached(settings.partial_at_r))
    if settings.trail_enabled and trailing and atr_m15 is not None and atr_m15 >= 0:
        level = _grid(price - sign * atr_m15 * settings.trail_atr_mult, tick, toward_loss)
        if target is None or better(level, target.price):
            target = MoveSL(level, "trail")
    if target is not None:
        if (target.price - limit) * sign > 0:  # broker mesafesinden daha yakin: izin verilen sinira cek
            target = MoveSL(limit, target.stage)
        if better(target.price, trade.sl):
            actions.append(target)

    if settings.partial_enabled and reached(settings.partial_at_r) and not trade.partial_done:
        volume = _grid(trade.volume * settings.partial_fraction, instrument.volume_step, ROUND_FLOOR)
        remaining = trade.volume - volume
        if volume >= instrument.volume_min - 1e-12 and remaining >= instrument.volume_min - 1e-12:
            actions.append(PartialClose(volume))
        else:
            actions.append(NoOp("partial_skipped"))
    return actions
