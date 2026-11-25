"""Guven puani (spec §6.2, ikinci katman).

Tetik V9'undur: en az bir strateji CONFIRMED ve V9 kapilari gecilmis olmali. Buradaki moduller adayi
desteklemek, karsi cikmak ya da cekimser kalmak icin V9 raporunu OKUR; rapora ya da V9'a dokunmaz.
Puan islem basi riski yalnizca AZALTIR (0.5x / 0.75x / 1.0x); hicbir zaman artirmaz.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from ..config import FUSION_MODULES, FusionSettings
from ..exness.schema import Instrument

MODULES = FUSION_MODULES
_VALUE = {1: 1.0, 0: 0.5, -1: 0.0}
RECENT_BARS = 5


@dataclass(frozen=True)
class Vote:
    module: str
    value: int  # 1 destek, 0 cekimser, -1 karsi
    detail: str


def _get(data: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _direction(value: Any) -> str | None:
    """Farkli modullerin yon ifadelerini ('bullish', 'UP', 'BUY' ...) tek bicime indirger."""
    if not isinstance(value, str):
        return None
    text = value.lower()
    if text in ("bullish", "buy", "up", "uptrend", "long") or text.startswith("bull"):
        return "bullish"
    if text in ("bearish", "sell", "down", "downtrend", "short") or text.startswith("bear"):
        return "bearish"
    return None


def _agree(direction: str | None, wanted: str) -> int:
    return 0 if direction is None else (1 if direction == wanted else -1)


def _patterns(rows: Any, wanted: str, *, need_confirmation: bool) -> int:
    same = other = False
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("state") in ("INVALIDATED", "EXPIRED"):
            continue
        if need_confirmation and row.get("confirmed_at") is None:
            continue
        age = row.get("age_bars")
        if isinstance(age, (int, float)) and age > RECENT_BARS:
            continue
        direction = _direction(row.get("direction"))
        same = same or direction == wanted
        other = other or (direction is not None and direction != wanted)
    return 1 if same and not other else -1 if other and not same else 0


def collect_votes(report: Any, side: str, *, now: float, kind: str) -> list[Vote]:
    data = report if isinstance(report, dict) else report.model_dump()
    wanted = "bullish" if side == "BUY" else "bearish"
    votes: list[Vote] = []

    alignment = _get(data, "mtf", "source_context", "higher_timeframe_alignment") or {}
    ratio = alignment.get("agreement_ratio") if isinstance(alignment, dict) else None
    mtf_direction = _direction(alignment.get("direction")) if isinstance(alignment, dict) else None
    mtf = _agree(mtf_direction, wanted)
    if mtf == 1 and not (isinstance(ratio, (int, float)) and ratio >= 0.5):
        mtf = 0
    votes.append(Vote("mtf", mtf, f"ust zaman dilimi: {mtf_direction or 'belirsiz'}"))

    regime_direction = _direction(_get(data, "regime", "direction"))
    votes.append(Vote("regime", _agree(regime_direction, wanted), f"rejim: {_get(data, 'regime', 'regime') or '-'}"))

    votes.append(Vote("candle_pattern",
                      _patterns(_get(data, "candlestick_patterns", "patterns"), wanted, need_confirmation=True),
                      "son mumlardaki onayli formasyon"))
    votes.append(Vote("chart_pattern", _patterns(_get(data, "chart_patterns", "patterns"), wanted, need_confirmation=False),
                      "grafik formasyonu"))

    pivots = _get(data, "market_structure", "v5_pivots") or {}
    structure = _direction(pivots.get("break_of_structure")) or _direction(pivots.get("trend")) \
        if isinstance(pivots, dict) else None
    votes.append(Vote("structure", _agree(structure, wanted), "piyasa yapisi"))

    rsi, histogram = _get(data, "momentum", "rsi14_wilder"), _get(data, "momentum", "macd_histogram")
    momentum = None
    if isinstance(rsi, (int, float)) and isinstance(histogram, (int, float)):
        momentum = "bullish" if rsi > 50 and histogram > 0 else "bearish" if rsi < 50 and histogram < 0 else None
    votes.append(Vote("momentum", _agree(momentum, wanted), "RSI ve MACD"))

    bull, bear = _get(data, "confluence", "bullish_strength"), _get(data, "confluence", "bearish_strength")
    confluence = None
    if isinstance(bull, (int, float)) and isinstance(bear, (int, float)) and bull != bear:
        confluence = "bullish" if bull > bear else "bearish"
    votes.append(Vote("confluence", _agree(confluence, wanted), "kanit birlesimi"))

    routed = _get(data, "routing", "strategy_id")
    others = [s for s in data.get("strategies") or [] if isinstance(s, dict) and s.get("status") == "CONFIRMED"
              and s.get("strategy_id") != routed and s.get("direction") == side]
    votes.append(Vote("other_strategies", 1 if others else 0, f"ayni yonde {len(others)} baska strateji"))

    votes.append(Vote("session", _session(now, kind), "seans kalitesi"))
    return votes


def _session(now: float, kind: str) -> int:
    if kind == "crypto":
        return 0  # 7/24 piyasa: seans oy vermez
    from forex.sessions import active_sessions

    active = active_sessions(datetime.fromtimestamp(now, timezone.utc))
    if "London" in active or "New_York" in active:
        return 1
    return 0 if "Asian" in active else -1


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
