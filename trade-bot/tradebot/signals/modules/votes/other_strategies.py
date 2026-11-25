from __future__ import annotations

from ..base import Context, Vote, dig


class OtherStrategies:
    """Ayni yonde CONFIRMED olan (yonlendirilen disindaki) baska strateji varsa destek."""
    id, kind = "other_strategies", "vote"

    def evaluate(self, context: Context) -> Vote:
        routed = dig(context.report, "routing", "strategy_id")
        others = [s for s in context.report.get("strategies") or []
                  if isinstance(s, dict) and s.get("status") == "CONFIRMED" and s.get("strategy_id") != routed
                  and s.get("direction") == context.side]
        return Vote(self.id, 1 if others else 0, f"ayni yonde {len(others)} baska strateji")
