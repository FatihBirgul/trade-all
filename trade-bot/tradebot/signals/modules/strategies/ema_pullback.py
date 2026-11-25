"""Egilim yonunde EMA20'ye geri cekilme (M15), H1 egilimi ile.

AL: H1'de EMA50 > EMA200 ve kapanis EMA50'nin ustunde; son kapanmis M15 mumu EMA20'ye dokunup
(dip <= EMA20) ustunde ve yukselen mum olarak kapanmis. Stop: son 5 mumun dibi - 0.5 ATR. Hedef: 2R.
SAT: ayna goruntusu.
"""

from __future__ import annotations

from ..base import Context, Signal
from ..indicators import atr, ema, trend

LOOKBACK = 5
MAX_STOP_ATR = 3.0


class EmaPullback:
    id, kind = "tb_ema_pullback_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15, h1 = context.bars.get("M15") or [], context.bars.get("H1") or []
        direction = trend(h1)
        if direction is None or len(m15) < 60:
            return None
        average = ema([bar["close"] for bar in m15], 20)[-1]
        volatility = atr(m15)
        bar = m15[-1]
        if not volatility or volatility <= 0:
            return None
        recent = m15[-LOOKBACK:]
        if direction == "bullish":
            if not (bar["low"] <= average < bar["close"] and bar["close"] > bar["open"]):
                return None
            stop = min(b["low"] for b in recent) - 0.5 * volatility
            entry = bar["close"]
            side = "BUY"
        else:
            if not (bar["high"] >= average > bar["close"] and bar["close"] < bar["open"]):
                return None
            stop = max(b["high"] for b in recent) + 0.5 * volatility
            entry = bar["close"]
            side = "SELL"
        distance = abs(entry - stop)
        if distance <= 0 or distance > MAX_STOP_ATR * volatility:
            return None  # stop cok uzak: geri cekilme degil, donus olabilir
        sign = 1.0 if side == "BUY" else -1.0
        return Signal(side, entry, stop, entry + sign * 2.0 * distance,
                      f"H1 egilimi {direction}, M15 EMA20 geri cekilmesi", bar_time=int(bar["time"]))
