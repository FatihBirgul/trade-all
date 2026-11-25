"""Golge (sanal) islemler.

Emir gonderilmeyen adaylarin ne sonuc verecegini izler: golge kipindeki stratejiler, puani esigin
altinda kalan adaylar ve duraklatilmis stratejiler. Sonuc kapanmis M15 mumlarindan hesaplanir:
once stop (ayni mumda ikisi de gorulurse temkinli olarak stop sayilir), sonra hedef (TP1 = 2R);
96 mum (24 saat) icinde ikisi de olmazsa son kapanisa gore R.
"""

from __future__ import annotations

from ..store.repo import Repo
from .adapter import Candidate

MAX_BARS = 96
REASONS = ("shadow", "low_score", "paused")


class ShadowBook:
    def __init__(self, repo: Repo):
        self._db = repo.conn

    def open(self, candidate: Candidate, reason: str, score: float | None, now: float) -> bool:
        """Sanal islemi kaydeder; ayni setup ikinci kez kaydedilmez (False)."""
        if reason not in REASONS:
            raise ValueError("gecersiz golge nedeni")
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO shadow_trades (symbol, side, strategy_id, setup_id, reason, entry, sl, tp, score, "
            "opened_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (candidate.symbol, candidate.side, candidate.strategy_id, candidate.setup_id, reason, candidate.entry,
             candidate.stop_loss, candidate.take_profit_1, score, float(now)))
        return cursor.rowcount == 1

    def open_symbols(self) -> set[str]:
        return {row[0] for row in self._db.execute("SELECT DISTINCT symbol FROM shadow_trades WHERE closed_at IS NULL")}

    def resolve(self, symbol: str, bars: list[dict], now: float) -> list[dict]:
        """Acik sanal islemleri `bars` (kapanmis M15 mumlari, eskiden yeniye) ile sonuclandirir."""
        closed: list[dict] = []
        rows = self._db.execute(
            "SELECT id, side, entry, sl, tp, opened_at, strategy_id FROM shadow_trades "
            "WHERE symbol = ? AND closed_at IS NULL", (symbol,)).fetchall()
        for row in rows:
            trade_id, side, entry, stop, target, opened_at, strategy_id = row
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            sign = 1.0 if side == "BUY" else -1.0
            after = [b for b in bars if b["time"] >= opened_at]  # acilistan sonra baslayan mumlar
            result = closed_at = None
            for bar in after[:MAX_BARS]:
                stop_hit = bar["low"] <= stop if side == "BUY" else bar["high"] >= stop
                target_hit = bar["high"] >= target if side == "BUY" else bar["low"] <= target
                if stop_hit:
                    result = -1.0
                elif target_hit:
                    result = abs(target - entry) / risk
                if result is not None:
                    closed_at = bar["time"] + 900
                    break
            if result is None and len(after) >= MAX_BARS:
                last = after[MAX_BARS - 1]
                result, closed_at = (last["close"] - entry) * sign / risk, last["time"] + 900
            if result is None:
                continue
            self._db.execute("UPDATE shadow_trades SET closed_at = ?, result_r = ? WHERE id = ?",
                             (min(closed_at, now), result, trade_id))
            closed.append({"id": trade_id, "symbol": symbol, "strategy_id": strategy_id, "result_r": result})
        return closed

    def stats(self, strategy_id: str, reason: str | None = None) -> dict:
        sql = "SELECT result_r FROM shadow_trades WHERE strategy_id = ? AND closed_at IS NOT NULL"
        args: list = [strategy_id]
        if reason is not None:
            sql += " AND reason = ?"
            args.append(reason)
        results = [row[0] for row in self._db.execute(sql, args)]
        if not results:
            return {"trades": 0, "wins": 0, "win_rate": None, "avg_r": None}
        wins = sum(1 for r in results if r > 0)
        return {"trades": len(results), "wins": wins, "win_rate": wins / len(results),
                "avg_r": sum(results) / len(results)}
