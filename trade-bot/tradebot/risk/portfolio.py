"""Portfoy giris kapisi.

V9 tek islemi degerlendirir; bu kapi botun acik islemlerinin toplamina bakar. Yalnizca botun
kendi islemleri sayilir: elle acilanlar (`origin='manual'`) limitlere dahil degildir (spec §6.4).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..config import RiskSettings
from ..exness.schema import Instrument
from ..signals.adapter import Candidate
from ..store.repo import Trade


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str
    should_halt: bool = False  # toplam kayip siniri asildi: bot durmali ve onay beklemeli


def currency_legs(symbol: str, side: str, instruments: Mapping[str, Instrument]) -> tuple[tuple[str, str], ...]:
    """BUY EURUSD -> (EUR, long), (USD, short). Enstruman bilinmiyorsa sembolun iki yarisi kullanilir."""
    instrument = instruments.get(symbol)
    base = instrument.currency_base if instrument and instrument.currency_base else symbol[:3]
    quote = instrument.currency_profit if instrument and instrument.currency_profit else symbol[3:]
    long, short = ("long", "short") if side == "BUY" else ("short", "long")
    return (base, long), (quote, short)


def check_entry(candidate: Candidate, *, open_bot: Sequence[Trade], bot_pnl_today: float,
                bot_pnl_total: float, start_capital: float | None, halted: bool, settings: RiskSettings,
                instruments: Mapping[str, Instrument]) -> Verdict:
    """`bot_pnl_*`: botun gerceklesen + acik kar/zarari (hesap para birimi)."""
    if halted:
        return Verdict(False, "bot durduruldu")
    if start_capital is None or start_capital <= 0:
        return Verdict(False, "başlangıç sermayesi bilinmiyor")
    if bot_pnl_total <= -settings.total_loss_pct / 100.0 * start_capital:
        return Verdict(False, f"toplam kayıp sınırı (%{settings.total_loss_pct:g}) aşıldı", should_halt=True)
    if bot_pnl_today <= -settings.daily_loss_pct / 100.0 * start_capital:
        return Verdict(False, f"günlük kayıp sınırı (%{settings.daily_loss_pct:g}) doldu")
    bot_trades = [t for t in open_bot if t.origin == "bot" and t.is_open]
    if len(bot_trades) >= settings.max_open_bot:
        return Verdict(False, f"açık bot işlemi sınırı ({settings.max_open_bot}) dolu")
    if sum(1 for t in bot_trades if t.symbol == candidate.symbol) >= settings.per_symbol:
        return Verdict(False, f"{candidate.symbol} için zaten açık bot işlemi var")
    exposure: Counter = Counter()
    for trade in bot_trades:
        exposure.update(currency_legs(trade.symbol, trade.side, instruments))
    for leg in currency_legs(candidate.symbol, candidate.side, instruments):
        if exposure[leg] >= settings.per_currency_side:
            return Verdict(False, f"{leg[0]} {leg[1]} yönünde zaten {exposure[leg]} açık işlem var")
    return Verdict(True, "ok")
