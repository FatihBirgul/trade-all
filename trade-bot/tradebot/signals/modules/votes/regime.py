from __future__ import annotations

from ..base import Context, Vote, agree, dig, direction


class Regime:
    id, kind = "regime", "vote"

    def evaluate(self, context: Context) -> Vote:
        found = direction(dig(context.report, "regime", "direction"))
        return Vote(self.id, agree(found, context.wanted), f"rejim: {dig(context.report, 'regime', 'regime') or '-'}")
