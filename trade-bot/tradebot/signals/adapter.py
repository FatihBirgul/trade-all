"""V9 analiz raporu -> aday islem.

Karar V9'undur: yalnizca `BUY_CANDIDATE`/`SELL_CANDIDATE` ve `ELIGIBLE` sonuc aday olur. Diger her
durumda aday yoktur ve neden loglanir; bu katman bildirim gondermez.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

from . import v9

log = logging.getLogger(__name__)

CANDIDATE_DECISIONS = ("BUY_CANDIDATE", "SELL_CANDIDATE")


@dataclass(frozen=True)
class Candidate:
    symbol: str
    side: Literal["BUY", "SELL"]
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    lots: float
    strategy_id: str
    setup_id: str
    net_rr: float
    analysis_id: str
    risk_amount: float


@dataclass(frozen=True)
class Evaluation:
    symbol: str
    decision: str
    reasons: tuple[str, ...]
    candidate: Candidate | None = None


def evaluate(provider, symbol: str, *, equity: float, risk_pct: float, commission_per_lot: float,
             enabled_strategies: set[str] | None, now: float | None = None, engine=None) -> Evaluation:
    if enabled_strategies is not None:
        # V9 parametreleri ozetledigi icin JSON'a cevrilebilir, sirali bir liste ister.
        enabled_strategies = sorted(set(enabled_strategies) & v9.builtin_strategy_ids())
        if not enabled_strategies:
            return Evaluation(symbol, "WAIT", ("etkin strateji yok",))
    report = (engine or v9.engine()).analyze(
        provider, symbol, "M15", now=now, confirmations=("H1", "H4"), balance=equity, risk_pct=risk_pct,
        commission_per_lot=commission_per_lot, enabled_strategies=enabled_strategies)
    reasons = tuple(str(reason) for reason in report.decision_reasons)
    if report.final_decision not in CANDIDATE_DECISIONS or report.trading_eligibility != "ELIGIBLE":
        return Evaluation(symbol, report.final_decision, reasons)
    strategy_id = (report.routing or {}).get("strategy_id")
    setup_id = next((row.get("setup_id") for row in report.strategies if row.get("strategy_id") == strategy_id), None)
    values = (report.entry_zone, report.stop_loss, report.take_profit_1, report.take_profit_2, report.lot_size,
              report.net_risk_reward, report.risk_amount, strategy_id, setup_id)
    if any(value is None for value in values):
        return Evaluation(symbol, "INSUFFICIENT_DATA", ("V9 raporu eksik alan iceriyor",))
    entry_zone = report.entry_zone if isinstance(report.entry_zone, dict) else report.entry_zone.model_dump()
    candidate = Candidate(
        symbol=symbol, side="BUY" if report.final_decision == "BUY_CANDIDATE" else "SELL",
        entry=float(entry_zone["low"]), stop_loss=float(report.stop_loss),
        take_profit_1=float(report.take_profit_1), take_profit_2=float(report.take_profit_2),
        lots=float(report.lot_size), strategy_id=str(strategy_id), setup_id=str(setup_id),
        net_rr=float(report.net_risk_reward), analysis_id=report.analysis_id, risk_amount=float(report.risk_amount))
    return Evaluation(symbol, report.final_decision, reasons, candidate)


def evaluate_symbol(provider, symbol: str, *, equity: float, risk_pct: float, commission_per_lot: float,
                    enabled_strategies: set[str] | None, now: float | None = None, engine=None) -> Candidate | None:
    result = evaluate(provider, symbol, equity=equity, risk_pct=risk_pct,
                      commission_per_lot=commission_per_lot, enabled_strategies=enabled_strategies,
                      now=now, engine=engine)
    if result.candidate is None:
        log.info("aday yok %s: %s (%s)", symbol, result.decision, "; ".join(result.reasons))
    return result.candidate
