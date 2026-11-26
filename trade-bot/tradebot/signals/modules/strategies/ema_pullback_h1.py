"""Gunluk yon dogrultusunda H1 EMA bolgesine geri cekilme + ret mumu (swing ailesi; bkz. swing_rules.py).

Yalnizca bir H1 mumu kapandiginda degerlendirilir. AL (SAT ayna goruntusu): gunluk yon yukari, H1'de
EMA21 > EMA50, son kapanmis H1 mumu bolgeye geri cekilmis ve yukselen mum olarak araliginin ust yarisinda
kapanmis. Bolge iki surumdur (ikisi de onceden sabit; ileri testte ilk donemde secilir, ikincide dogrulanir):
- `20_21` (dar bant): dip, EMA20/EMA21'in ustune degmis; kapanis ikisinin de ustunde.
- `21_50` (genis bant): dip EMA21'in altina inmis ama bant kirilmamis (dip >= EMA50 - 0,25 x ATR);
  kapanis bandin orta noktasinin ustunde.
Stop: son 3 H1 mumunun dibi - 0,1 x H1 ATR; en az 1,5 x gunluk ATR uzakta. Hedef varsayilan 2R.
"""

from __future__ import annotations

from ..base import Context, Signal
from ..indicators import atr, ema
from .swing_rules import daily_bias, plan

H1_SECONDS = 3600
M15_SECONDS = 900


class EmaPullbackH1:
    kind = "strategy"

    def __init__(self, zone: str):
        if zone not in ("20_21", "21_50"):
            raise ValueError("bolge 20_21 ya da 21_50 olmali")
        self.zone = zone
        self.id = f"tb_emapb_h1_{zone}_v1"

    def evaluate(self, context: Context) -> Signal | None:
        m15, h1 = context.bars.get("M15") or [], context.bars.get("H1") or []
        if not m15 or len(h1) < 60:
            return None
        last = m15[-1]
        # Yalnizca H1 kapanisinda: son kapanmis M15 mumu, son kapanmis H1 mumunun son ceyregidir.
        if (last["time"] + M15_SECONDS) % H1_SECONDS != 0 or h1[-1]["time"] + H1_SECONDS != last["time"] + M15_SECONDS:
            return None
        bias = daily_bias(context.bars.get("D1") or [], context.bars.get("H4") or [])
        if bias is None:
            return None
        closes = [bar["close"] for bar in h1]
        e20, fast, slow = ema(closes, 20)[-1], ema(closes, 21)[-1], ema(closes, 50)[-1]
        width = atr(h1)
        bar = h1[-1]
        if not width or width <= 0 or bar["high"] <= bar["low"]:
            return None
        sign = 1.0 if bias == "bullish" else -1.0
        if (fast - slow) * sign <= 0:
            return None  # H1 egilimi gunluk yonle ayni degil
        # Ayna goruntusu icin fiyatlar yon isaretiyle carpilir: "yukari" her iki yonde de islem lehinedir.
        deep = (bar["low"] if sign > 0 else bar["high"]) * sign  # mumun bolgeye en cok girdigi uc
        close, opened, middle = bar["close"] * sign, bar["open"] * sign, (bar["high"] + bar["low"]) / 2.0 * sign
        if not (close > opened and close >= middle):
            return None  # ret mumu degil
        if self.zone == "20_21":
            top = max(e20 * sign, fast * sign)
            if not (deep <= top < close):
                return None
        else:
            if not (slow * sign - 0.25 * width <= deep <= fast * sign and close > (fast + slow) / 2.0 * sign):
                return None
        side = "BUY" if sign > 0 else "SELL"
        extreme = min(b["low"] for b in h1[-3:]) if sign > 0 else max(b["high"] for b in h1[-3:])
        structure = extreme - sign * 0.1 * width
        entry = bar["close"]
        stop = plan(side, entry, structure, context.bars)
        if stop is None:
            return None
        return Signal(side, entry, stop, entry + sign * 2.0 * abs(entry - stop),
                      f"gunluk yon {bias}, H1 EMA{self.zone.replace('_', '/')} geri cekilmesi ve ret mumu",
                      bar_time=int(last["time"]))
