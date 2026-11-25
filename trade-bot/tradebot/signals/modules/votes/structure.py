from __future__ import annotations

from ..base import Context, Vote, agree, dig, direction


class Structure:
    id, kind = "structure", "vote"

    def evaluate(self, context: Context) -> Vote:
        pivots = dig(context.report, "market_structure", "v5_pivots") or {}
        found = direction(pivots.get("break_of_structure")) or direction(pivots.get("trend")) \
            if isinstance(pivots, dict) else None
        return Vote(self.id, agree(found, context.wanted), "piyasa yapisi")
