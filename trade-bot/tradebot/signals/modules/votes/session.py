from __future__ import annotations

from datetime import datetime, timezone

from ..base import Context, Vote


def session_value(now: float, kind: str) -> int:
    if kind == "crypto":
        return 0  # 7/24 piyasa: seans oy vermez
    from forex.sessions import active_sessions

    active = active_sessions(datetime.fromtimestamp(now, timezone.utc))
    if "London" in active or "New_York" in active:
        return 1
    return 0 if "Asian" in active else -1


class Session:
    id, kind = "session", "vote"

    def evaluate(self, context: Context) -> Vote:
        return Vote(self.id, session_value(context.now, context.kind), "seans kalitesi")
