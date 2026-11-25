from __future__ import annotations

from ..base import Context, Vote, agree, dig, direction


class Mtf:
    """Ust zaman dilimi uyumu: yon ayni ve uyum orani en az 0.5 ise destek."""
    id, kind = "mtf", "vote"

    def evaluate(self, context: Context) -> Vote:
        alignment = dig(context.report, "mtf", "source_context", "higher_timeframe_alignment") or {}
        ratio = alignment.get("agreement_ratio") if isinstance(alignment, dict) else None
        found = direction(alignment.get("direction")) if isinstance(alignment, dict) else None
        value = agree(found, context.wanted)
        if value == 1 and not (isinstance(ratio, (int, float)) and ratio >= 0.5):
            value = 0
        return Vote(self.id, value, f"ust zaman dilimi: {found or 'belirsiz'}")
