"""Kanal kirilimi (M15), oynaklik genislemesi ve H1 egilimi ile.

AL: son kapanmis M15 mumu onceki 20 mumun en yuksegini kapanisla asmis, ATR(14) 20 mum oncekinden
buyuk ve H1 egilimi yukari. Stop: giris - 1.5 ATR. Hedef: 2R. SAT: ayna goruntusu.
"""

from __future__ import annotations

from ..base import Context, Signal
from ..indicators import atr, trend

CHANNEL = 20
STOP_ATR = 1.5


class DonchianBreakout:
    id, kind = "tb_donchian_breakout_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15, h1 = context.bars.get("M15") or [], context.bars.get("H1") or []
        direction = trend(h1)
        if direction is None or len(m15) < CHANNEL + 36:
            return None
        bar, channel = m15[-1], m15[-CHANNEL - 1:-1]
        now_atr, past_atr = atr(m15), atr(m15[:-CHANNEL])
        if not now_atr or not past_atr or now_atr <= past_atr:
            return None  # oynaklik genislemiyor: kirilim zayif
        upper, lower = max(b["high"] for b in channel), min(b["low"] for b in channel)
        if direction == "bullish" and bar["close"] > upper:
            side, sign = "BUY", 1.0
        elif direction == "bearish" and bar["close"] < lower:
            side, sign = "SELL", -1.0
        else:
            return None
        entry = bar["close"]
        distance = STOP_ATR * now_atr
        return Signal(side, entry, entry - sign * distance, entry + sign * 2.0 * distance,
                      f"M15 {CHANNEL} mumluk kanal kirilimi, H1 egilimi {direction}", bar_time=int(bar["time"]))
