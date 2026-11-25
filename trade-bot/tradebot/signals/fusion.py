"""Guven puani (spec §6.2, ikinci katman).

Tetik V9'undur: en az bir strateji CONFIRMED ve V9 kapilari gecilmis olmali. Buradaki moduller adayi
desteklemek, karsi cikmak ya da cekimser kalmak icin V9 raporunu OKUR; rapora ya da V9'a dokunmaz.
Puan islem basi riski yalnizca AZALTIR (0.5x / 0.75x / 1.0x); hicbir zaman artirmaz.
"""

from __future__ import annotations

import logging
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from ..config import FUSION_MODULES, FusionSettings
from ..exness.schema import Instrument
from .modules import Context, Vote, modules

log = logging.getLogger(__name__)

MODULES = FUSION_MODULES
_VALUE = {1: 1.0, 0: 0.5, -1: 0.0}


def collect_votes(report: Any, side: str, *, now: float, kind: str, symbol: str = "") -> list[Vote]:
    """Kayitli tum oy modullerini calistirir. Hata veren modul cekimser sayilir: tek bir modul taramayi
    dusurmemeli ve yanlislikla destek de vermemeli."""
    data = report if isinstance(report, dict) else report.model_dump()
    context = Context(symbol=symbol, now=now, kind=kind, side=side, report=data)
    votes: list[Vote] = []
    for module in modules("vote"):
        try:
            vote = module.evaluate(context)
        except Exception:  # noqa: BLE001 - modul hatasi cekimserdir
            log.exception("oy modulu hata verdi: %s", module.id)
            vote = None
        votes.append(vote if isinstance(vote, Vote) else Vote(module.id, 0, "hesaplanamadi"))
    return votes


def score(votes: list[Vote], weights: dict[str, float]) -> float:
    """0-100. Destek 1, cekimser 0.5, karsi 0 puan; modul agirligiyla ortalanir."""
    total = earned = 0.0
    for vote in votes:
        weight = float(weights.get(vote.module, 1.0))
        if weight <= 0:
            continue
        total += weight
        earned += weight * _VALUE[vote.value]
    return 50.0 if total == 0 else round(100.0 * earned / total, 6)


def risk_multiplier(value: float, settings: FusionSettings) -> float | None:
    """Puan -> islem basi risk carpani. Esigin alti None: islem acilmaz, yalnizca gozlem kaydedilir."""
    if value < settings.min_score:
        return None
    if value < settings.mid_score:
        return 0.5
    if value < settings.high_score:
        return 0.75
    return 1.0


def scale_lots(lots: float, multiplier: float, instrument: Instrument) -> float | None:
    """Lotu carpanla kucultur; adima ASAGI yuvarlar. En kucuk lotun altina duserse None (yukari yuvarlanmaz)."""
    step = Decimal(str(instrument.volume_step))
    units = (Decimal(str(lots)) * Decimal(str(multiplier)) / step + Decimal("1e-9")).to_integral_value(rounding=ROUND_FLOOR)
    scaled = float(units * step)
    return scaled if scaled >= instrument.volume_min - 1e-12 else None
