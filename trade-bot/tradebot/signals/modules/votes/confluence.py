from __future__ import annotations

from ..base import Context, Vote, agree, dig


class Confluence:
    id, kind = "confluence", "vote"

    def evaluate(self, context: Context) -> Vote:
        bull = dig(context.report, "confluence", "bullish_strength")
        bear = dig(context.report, "confluence", "bearish_strength")
        found = None
        if isinstance(bull, (int, float)) and isinstance(bear, (int, float)) and bull != bear:
            found = "bullish" if bull > bear else "bearish"
        return Vote(self.id, agree(found, context.wanted), "kanit birlesimi")
