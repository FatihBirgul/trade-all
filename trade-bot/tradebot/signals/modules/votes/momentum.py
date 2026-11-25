from __future__ import annotations

from ..base import Context, Vote, agree, dig


class Momentum:
    id, kind = "momentum", "vote"

    def evaluate(self, context: Context) -> Vote:
        rsi = dig(context.report, "momentum", "rsi14_wilder")
        histogram = dig(context.report, "momentum", "macd_histogram")
        found = None
        if isinstance(rsi, (int, float)) and isinstance(histogram, (int, float)):
            found = "bullish" if rsi > 50 and histogram > 0 else "bearish" if rsi < 50 and histogram < 0 else None
        return Vote(self.id, agree(found, context.wanted), "RSI ve MACD")
