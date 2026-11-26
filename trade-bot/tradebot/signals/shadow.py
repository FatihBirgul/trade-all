"""Golge (sanal) islemler.

Emir gonderilmeyen adaylarin ne sonuc verecegini izler: golge kipindeki stratejiler, puani esigin
altinda kalan adaylar ve duraklatilmis stratejiler. Sonuc kapanmis M15 mumlarindan hesaplanir:
once stop (ayni mumda ikisi de gorulurse temkinli olarak stop sayilir), sonra hedef (TP1 = 2R);
96 mum (24 saat) icinde ikisi de olmazsa son kapanisa gore R.
"""

from __future__ import annotations

import logging

from ..store.repo import Repo
from .adapter import Candidate

log = logging.getLogger(__name__)

MAX_BARS = 96
BAR_SECONDS = 900
REASONS = ("shadow", "low_score", "paused")


class ShadowBook:
    def __init__(self, repo: Repo):
        self._db = repo.conn

    def open(self, candidate: Candidate, reason: str, score: float | None, now: float, spread: float = 0.0) -> bool:
        """Sanal islemi kaydeder; ayni setup ikinci kez kaydedilmez (False).

        `spread`: acilis anindaki alis-satis farki. Mumlar bid fiyatidir; SELL islem ask ile kapanir, bu
        yuzden stop ve hedef denetimi spread kadar kaydirilir (yoksa SELL sonuclari iyimser olur)."""
        if reason not in REASONS:
            raise ValueError("gecersiz golge nedeni")
        # Suren bir egilimde ayni strateji her mumda yeniden CONFIRMED olur. Canli islemde sembol basina
        # tek pozisyon acilir; golgede de ayni sembol/strateji/yon icin acik kayit varken yenisi acilmaz.
        # Yoksa tek bir hareket, karne esigindeki "20 sanal islem"in tamamini uretebilirdi.
        if self._db.execute(
                "SELECT 1 FROM shadow_trades WHERE symbol = ? AND strategy_id = ? AND side = ? AND closed_at IS NULL",
                (candidate.symbol, candidate.strategy_id, candidate.side)).fetchone():
            return False
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO shadow_trades (symbol, side, strategy_id, setup_id, reason, entry, sl, tp, score, "
            "opened_at, spread) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (candidate.symbol, candidate.side, candidate.strategy_id, candidate.setup_id, reason, candidate.entry,
             candidate.stop_loss, candidate.take_profit_1, score, float(now), max(0.0, float(spread or 0.0))))
        return cursor.rowcount == 1

    def open_symbols(self) -> set[str]:
        return {row[0] for row in self._db.execute("SELECT DISTINCT symbol FROM shadow_trades WHERE closed_at IS NULL")}

    def bars_needed(self, symbol: str, now: float, minimum: int = 128, maximum: int = 1500) -> int:
        """En eski acik sanal islemin acilisindan bugune kadar gereken M15 mum sayisi (onbellek en cok 1500 tutar)."""
        row = self._db.execute(
            "SELECT MIN(opened_at) FROM shadow_trades WHERE symbol = ? AND closed_at IS NULL", (symbol,)).fetchone()
        if not row or row[0] is None:
            return minimum
        return max(minimum, min(maximum, int((now - row[0]) // BAR_SECONDS) + 3))

    def resolve(self, symbol: str, bars: list[dict], now: float) -> list[dict]:
        """Acik sanal islemleri `bars` (kapanmis M15 mumlari, eskiden yeniye) ile sonuclandirir."""
        closed: list[dict] = []
        rows = self._db.execute(
            "SELECT id, side, entry, sl, tp, opened_at, strategy_id, spread FROM shadow_trades "
            "WHERE symbol = ? AND closed_at IS NULL", (symbol,)).fetchall()
        for row in rows:
            trade_id, side, entry, stop, target, opened_at, strategy_id, spread = row
            ask_shift = (spread or 0.0) if side == "SELL" else 0.0  # SELL ask ile kapanir: ask = bid + spread
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            sign = 1.0 if side == "BUY" else -1.0
            # Islem, mum kapanisindan birkac saniye sonra (yeni mumun icinde) acilir; o mum da sayilir.
            # Yalnizca acilistan once kapanmis mumlar disarida kalir.
            after = [b for b in bars if b["time"] + BAR_SECONDS > opened_at]
            if bars and bars[0]["time"] > opened_at + BAR_SECONDS:
                # Verilen mumlar acilistan SONRA basliyor: aradaki mumlar gorulmeden karar verilemez (stopa degip
                # degmedigi bilinmez). Yanlis bir sonuc karneyi bozar; islem sonucsuz olarak silinir.
                self._db.execute("DELETE FROM shadow_trades WHERE id = ?", (trade_id,))
                log.warning("sanal islem sonuclandirilamadi (mum gecmisi yetersiz), silindi: %s %s", symbol, strategy_id)
                continue
            result = closed_at = None
            for bar in after[:MAX_BARS]:
                stop_hit = bar["low"] <= stop if side == "BUY" else bar["high"] + ask_shift >= stop
                target_hit = bar["high"] >= target if side == "BUY" else bar["low"] + ask_shift <= target
                if stop_hit:
                    result = -1.0
                elif target_hit:
                    result = abs(target - entry) / risk
                if result is not None:
                    closed_at = bar["time"] + BAR_SECONDS
                    break
            if result is None and len(after) >= MAX_BARS:
                last = after[MAX_BARS - 1]
                result, closed_at = (last["close"] + ask_shift - entry) * sign / risk, last["time"] + BAR_SECONDS
            if result is None:
                continue
            self._db.execute("UPDATE shadow_trades SET closed_at = ?, result_r = ? WHERE id = ?",
                             (min(closed_at, now), result, trade_id))
            closed.append({"id": trade_id, "symbol": symbol, "strategy_id": strategy_id, "result_r": result})
        return closed

    def stats(self, strategy_id: str, reason: str | None = None, since: float | None = None) -> dict:
        sql = "SELECT result_r FROM shadow_trades WHERE strategy_id = ? AND closed_at IS NOT NULL"
        args: list = [strategy_id]
        if reason is not None:
            sql += " AND reason = ?"
            args.append(reason)
        if since is not None:
            sql += " AND opened_at >= ?"
            args.append(float(since))
        results = [row[0] for row in self._db.execute(sql, args)]
        if not results:
            return {"trades": 0, "wins": 0, "win_rate": None, "avg_r": None}
        wins = sum(1 for r in results if r > 0)
        return {"trades": len(results), "wins": wins, "win_rate": wins / len(results),
                "avg_r": sum(results) / len(results)}
