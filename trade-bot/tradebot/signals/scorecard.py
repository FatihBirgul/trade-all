"""Canli karne ve otomatik duraklatma (spec §6.2).

Her strateji ve her modul oyu icin gercek sonuclar: islem sayisi, kazanma orani, ortalama R, kar
faktoru. R = gerceklesen kar/zarar / giristeki risk tutari. Bir strateji yeterli islemden sonra
ortalamada zarar ediyorsa duraklatilir (golge kipine alinir: izlenmeye devam eder, emir acmaz).
Modul agirliklari otomatik DEGISTIRILMEZ; karne yalnizca gosterir.
"""

from __future__ import annotations

import json

from ..config import FUSION_MODULES, BotSettings, strategy_mode
from ..store.repo import Repo, Trade
from . import v9
from .shadow import REASONS, ShadowBook

_RESUMED = "strategy_resumed_at"
_PAUSED = "paused_strategies"


def trade_r(trade: Trade) -> float | None:
    """Islemin R cinsinden sonucu; giristeki risk bilinmiyorsa None."""
    if not trade.risk_amount or trade.risk_amount <= 0:
        return None
    return trade.pnl / trade.risk_amount


def _stats(results: list[float]) -> dict:
    if not results:
        return {"trades": 0, "wins": 0, "win_rate": None, "avg_r": None, "profit_factor": None}
    wins = [r for r in results if r > 0]
    losses = -sum(r for r in results if r < 0)
    return {"trades": len(results), "wins": len(wins), "win_rate": len(wins) / len(results),
            "avg_r": sum(results) / len(results), "profit_factor": sum(wins) / losses if losses > 0 else None}


def _closed_bot_trades(repo: Repo) -> list[tuple[Trade, float]]:
    rows = []
    for trade in repo.closed_trades(limit=5000):
        result = trade_r(trade) if trade.origin == "bot" else None
        if result is not None:
            rows.append((trade, result))
    return rows


def paused(repo: Repo) -> dict:
    value = repo.get_setting(_PAUSED, {})
    return value if isinstance(value, dict) else {}


def mark_resumed(repo: Repo, strategy_id: str, now: float) -> None:
    """Strateji yeniden canliya alindi: karne denetimi bu andan sonraki islemlerle baslar."""
    resumed = repo.get_setting(_RESUMED, {})
    resumed[strategy_id] = now
    repo.set_setting(_RESUMED, resumed)
    remaining = paused(repo)
    if remaining.pop(strategy_id, None) is not None:
        repo.set_setting(_PAUSED, remaining)


def mark_paused(repo: Repo, strategy_id: str, now: float, stats: dict) -> None:
    current = paused(repo)
    current[strategy_id] = {"at": now, "trades": stats["trades"], "avg_r": stats["avg_r"]}
    repo.set_setting(_PAUSED, current)


def scorecard(repo: Repo, settings: BotSettings) -> dict:
    rows = _closed_bot_trades(repo)
    shadow = ShadowBook(repo)
    held = paused(repo)
    strategies = {}
    from . import custom  # yerel ice aktarma: custom -> adapter zinciri bu modulu dolayli olarak yukleyebilir

    known = v9.builtin_strategy_ids() | custom.strategy_ids()
    for strategy_id in sorted(known | {t.strategy_id for t, _ in rows if t.strategy_id}):
        strategies[strategy_id] = {
            "mode": strategy_mode(settings, strategy_id), "paused": held.get(strategy_id),
            "live": _stats([r for t, r in rows if t.strategy_id == strategy_id]),
            "shadow": shadow.stats(strategy_id),
            # Nedenler ayri anlam tasir: `shadow`/`paused` canli kosullarda acilacak islemlerdir,
            # `low_score` ise canlida zaten acilmayacak dusuk puanli adaylardir. Canliya alma karari
            # duraklatmadan SONRAKI `paused` sonuclarina bakmalidir.
            "shadow_by_reason": {reason: shadow.stats(strategy_id, reason) for reason in REASONS},
            "shadow_since_pause": (shadow.stats(strategy_id, "paused", since=held[strategy_id].get("at"))
                                   if strategy_id in held else None)}
    modules = {module: {"support": [], "against": [], "abstain": []} for module in FUSION_MODULES}
    for trade, result in rows:
        try:
            votes = json.loads(trade.votes_json) if trade.votes_json else {}
        except ValueError:
            votes = {}
        for module, value in votes.items():
            if module in modules and value in (1, 0, -1):
                modules[module][{1: "support", 0: "abstain", -1: "against"}[value]].append(result)
    return {"strategies": strategies,
            "modules": {m: {bucket: _stats(results) for bucket, results in buckets.items()} for m, buckets in modules.items()},
            "totals": _stats([r for _, r in rows])}


def strategies_to_pause(repo: Repo, settings: BotSettings) -> list[tuple[str, dict]]:
    """Canli kipte olup yeterli islemden sonra ortalama R'si esigin altinda kalan stratejiler."""
    resumed = repo.get_setting(_RESUMED, {})
    rows = _closed_bot_trades(repo)
    found = []
    for strategy_id in sorted({t.strategy_id for t, _ in rows if t.strategy_id}):
        if strategy_mode(settings, strategy_id) != "live":
            continue
        since = resumed.get(strategy_id, 0.0)
        stats = _stats([r for t, r in rows if t.strategy_id == strategy_id and (t.closed_at or 0.0) > since])
        if stats["trades"] >= settings.fusion.pause_min_trades and stats["avg_r"] < settings.fusion.pause_avg_r:
            found.append((strategy_id, stats))
    return found
