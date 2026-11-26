"""WEEK TRADE (kullanicinin eski masasindaki 2 yillik testin "yumusak" surumu, belge bolum 2.10). YALNIZCA GOLGE.

Kurallar (kaynak `bt.py` ozetinden):
- Gunluk yon: dusus = kapanis < EMA20 < EMA50 ve EMA20, 3 mum oncesine gore dusuyor; yukselis aynasi.
  4H'te ayni dizilim sart.
- Tetik (kapanan 4H mumu): govde araligin %50'sinden buyuk ve yonle uyumlu (dusus: kirmizi govde ve 4H RSI < 50).
- Igne: son ya da onceki 4H mumunun araligi 2 x 4H ATR'den buyukse gec.
- Asiri uzama (gunluk RSI < 20 ya da > 80, ya da |kapanis - EMA20| > 2,5 x gunluk ATR) islemi ENGELLEMEZ
  ("yumusak" surum); yalnizca isaretlenir ve ayri raporlanir.
- Stop mesafesi 2 x gunluk ATR. Hedef yok. Cikis plani ileri testte uygulanir: +1R'de stop girise, +2R'de +1R
  kilit, sonra en iyi fiyat - 2 x 4H ATR ile iz surer; 7 gunde +1R gorulmediyse cikilir.
Kaynak testte kalite kapisi ve haber filtresi yoktu; burada da yoktur.
"""

from __future__ import annotations

import math

from ..base import Context, Signal
from .v13 import Frame

H4_SECONDS = 14400
STOP_DAILY_ATR = 2.0
SPIKE_ATR = 2.0
STRETCH_ATR = 2.5


def bias(frame: Frame) -> str | None:
    if len(frame) < 55:
        return None
    close, e20, e50, before = frame.C[-1], frame.e20[-1], frame.e50[-1], frame.e20[-4]
    if close < e20 < e50 and e20 < before:
        return "SELL"
    if close > e20 > e50 and e20 > before:
        return "BUY"
    return None


def stretched(daily: Frame) -> bool:
    value, a = daily.rsi[-1], daily.atr[-1]
    return (not math.isnan(value) and (value < 20 or value > 80)) or abs(daily.C[-1] - daily.e20[-1]) > STRETCH_ATR * a


class WeekTrade:
    id, kind = "tb_week_trade_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15 = context.bars.get("M15") or []
        h4, d1 = context.bars.get("H4") or [], context.bars.get("D1") or []
        if not m15 or len(h4) < 60 or len(d1) < 60:
            return None
        closed_at = int(m15[-1]["time"]) + 900
        if closed_at % H4_SECONDS or int(h4[-1]["time"]) + H4_SECONDS != closed_at:
            return None  # 4H mumu bu M15 mumuyla kapanmadi (ya da veri guncel degil)
        daily, upper = Frame(d1), Frame(h4)
        side = bias(daily)
        if side is None or bias(upper) != side:
            return None
        o, h, low, c = upper.O[-1], upper.H[-1], upper.L[-1], upper.C[-1]
        value, a4, daily_atr = upper.rsi[-1], upper.atr[-1], daily.atr[-1]
        if math.isnan(value) or not a4 or not daily_atr or daily_atr <= 0:
            return None
        if abs(c - o) <= 0.5 * (h - low):
            return None
        if side == "SELL" and not (c < o and value < 50):
            return None
        if side == "BUY" and not (c > o and value > 50):
            return None
        if (h - low) > SPIKE_ATR * a4 or (upper.H[-2] - upper.L[-2]) > SPIKE_ATR * a4:
            return None
        sign = 1.0 if side == "BUY" else -1.0
        entry = float(m15[-1]["close"])
        distance = STOP_DAILY_ATR * daily_atr
        detail = {"type": "WEEKTRADE", "model": "week trade", "score": None, "stretch": stretched(daily),
                  "tp1": None, "tp2": None, "volume_ratio": None}
        return Signal(side, entry, entry - sign * distance, entry + sign * 2.0 * distance,
                      "gunluk + 4H EMA20/50 yonu, 4H govde tetigi, stop 2 x gunluk ATR"
                      + (" (asiri uzama)" if detail["stretch"] else ""), bar_time=int(m15[-1]["time"]), plan=detail)
