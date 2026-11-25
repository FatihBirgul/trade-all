from __future__ import annotations

from typing import Any

from ..base import Context, Vote, dig, direction

RECENT_BARS = 5


def pattern_vote(rows: Any, wanted: str, *, need_confirmation: bool) -> int:
    same = other = False
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("state") in ("INVALIDATED", "EXPIRED"):
            continue
        if need_confirmation and row.get("confirmed_at") is None:
            continue
        age = row.get("age_bars")
        if isinstance(age, (int, float)) and age > RECENT_BARS:
            continue
        found = direction(row.get("direction"))
        same = same or found == wanted
        other = other or (found is not None and found != wanted)
    return 1 if same and not other else -1 if other and not same else 0


class CandlePattern:
    id, kind = "candle_pattern", "vote"

    def evaluate(self, context: Context) -> Vote:
        rows = dig(context.report, "candlestick_patterns", "patterns")
        return Vote(self.id, pattern_vote(rows, context.wanted, need_confirmation=True), "son mumlardaki onayli formasyon")


class ChartPattern:
    id, kind = "chart_pattern", "vote"

    def evaluate(self, context: Context) -> Vote:
        rows = dig(context.report, "chart_patterns", "patterns")
        return Vote(self.id, pattern_vote(rows, context.wanted, need_confirmation=False), "grafik formasyonu")
