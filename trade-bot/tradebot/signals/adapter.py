"""V9 analiz raporu -> aday islem.

Karar V9'undur: yalnizca `BUY_CANDIDATE`/`SELL_CANDIDATE` ve `ELIGIBLE` sonuc aday olur. Diger her
durumda aday yoktur ve neden loglanir; bu katman bildirim gondermez.
"""

from __future__ import annotations

import dataclasses
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
    report: object | None = None  # V9 AnalysisReport (guven puani modulleri okur)
    mode: str = "live"  # adayin stratejisinin kipi: live | shadow


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
        return Evaluation(symbol, report.final_decision, reasons, report=report)
    strategy_id = (report.routing or {}).get("strategy_id")
    setup_id = next((row.get("setup_id") for row in report.strategies if row.get("strategy_id") == strategy_id), None)
    values = (report.entry_zone, report.stop_loss, report.take_profit_1, report.take_profit_2, report.lot_size,
              report.net_risk_reward, report.risk_amount, strategy_id, setup_id)
    if any(value is None for value in values):
        return Evaluation(symbol, "INSUFFICIENT_DATA", ("V9 raporu eksik alan iceriyor",), report=report)
    entry_zone = report.entry_zone if isinstance(report.entry_zone, dict) else report.entry_zone.model_dump()
    candidate = Candidate(
        symbol=symbol, side="BUY" if report.final_decision == "BUY_CANDIDATE" else "SELL",
        entry=float(entry_zone["low"]), stop_loss=float(report.stop_loss),
        take_profit_1=float(report.take_profit_1), take_profit_2=float(report.take_profit_2),
        lots=float(report.lot_size), strategy_id=str(strategy_id), setup_id=str(setup_id),
        net_rr=float(report.net_risk_reward), analysis_id=report.analysis_id, risk_amount=float(report.risk_amount))
    return Evaluation(symbol, report.final_decision, reasons, candidate, report)


def evaluate_symbol(provider, symbol: str, *, equity: float, risk_pct: float, commission_per_lot: float,
                    enabled_strategies: set[str] | None, now: float | None = None, engine=None) -> Candidate | None:
    result = evaluate(provider, symbol, equity=equity, risk_pct=risk_pct,
                      commission_per_lot=commission_per_lot, enabled_strategies=enabled_strategies,
                      now=now, engine=engine)
    if result.candidate is None:
        log.info("aday yok %s: %s (%s)", symbol, result.decision, "; ".join(result.reasons))
    return result.candidate


MAX_EXTRA_STRATEGIES = 3


def evaluate_all(provider, symbol: str, *, equity: float, risk_pct: float, commission_per_lot: float,
                 modes: dict[str, str], now: float | None = None, engine=None) -> list[Evaluation]:
    """Kipi `off` olmayan stratejilerle degerlendirir; her CONFIRMED stratejiye ayri sans verir.

    V9 yonlendiricisi tek strateji secer. Sectigi strateji sonraki bir kapidan (or. maliyet sonrasi
    R/R) gecemezse ve ayni anda baska bir strateji de CONFIRMED ise, o strateji tek basina yeniden
    degerlendirilir. Ters yonlu onay V9'da sert vetodur ve burada asilmaz. Aday varsa aday(lar),
    yoksa nedeniyle birlikte ilk degerlendirme doner.
    """
    active = sorted(s for s in v9.builtin_strategy_ids() if modes.get(s, "live") != "off")
    if not active:
        return [Evaluation(symbol, "WAIT", ("etkin strateji yok",))]

    def run(enabled: list[str]) -> Evaluation:
        result = evaluate(provider, symbol, equity=equity, risk_pct=risk_pct, commission_per_lot=commission_per_lot,
                          enabled_strategies=set(enabled), now=now, engine=engine)
        if result.candidate is not None:
            return dataclasses.replace(result, mode=modes.get(result.candidate.strategy_id, "live"))
        return result

    first = run(active)
    if first.report is None:
        return [first]
    live = [s for s in active if modes.get(s, "live") == "live"]
    if first.candidate is not None:
        if first.mode == "live" or not live:
            return [first]
        # Yonlendirici golge (ya da duraklatilmis) bir strateji secti. O kaydedilir, ama canli
        # stratejilerin sansi kesilmez: yalnizca canli olanlarla yeniden degerlendirilir. Ters yonlu
        # bir aday kabul edilmez (golge strateji de olsa ters yon onayi V9'da sert vetodur).
        second = run(live)
        if second.candidate is not None and second.candidate.side == first.candidate.side:
            return [first, second]
        return [first]
    routing = getattr(first.report, "routing", None) or {}
    if routing.get("status") != "selected":
        return [first]  # secim yok ya da ters yonlu catisma: tek tek denemek vetoyu delmek olurdu
    routed = routing.get("strategy_id")
    others = [s.get("strategy_id") for s in getattr(first.report, "strategies", [])
              if s.get("status") == "CONFIRMED" and s.get("strategy_id") != routed and s.get("strategy_id") in active]
    others.sort(key=lambda s: modes.get(s, "live") != "live")  # once canli stratejiler
    found = [result for result in (run([strategy]) for strategy in others[:MAX_EXTRA_STRATEGIES])
             if result.candidate is not None]
    return found[:1] or [first]
