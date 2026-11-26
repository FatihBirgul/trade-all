"""WEEK TRADE: kullanicinin eski masasindaki 2 yillik testin kodu (`bt.py`) birebir. YALNIZCA GOLGE.

Kurallar (`bt.py`den):
- Gunluk yon: dusus = kapanis < EMA20 < EMA50 ve EMA20, 3 mum oncesinden dusuk; yukselis aynasi. Gunluk veri
  her zaman "bir onceki takvim gunu"dur: sinyal mumunun ACILDIGI gunden once kapanmis son gunluk mum.
- 4H ayni dizilim: kapanis < EMA20 < EMA50 (4H'te EMA20 egimi aranmaz).
- Tetik (kapanan 4H mumu): govde araligin %50'sinden buyuk, yonle uyumlu ve 4H RSI yonle uyumlu (dusus: < 50).
- Igne: sinyal mumunun ya da bir onceki mumun araligi 2 x 4H ATR'den buyukse gec.
- Asiri uzama (gunluk RSI < 20 / > 80, ya da |kapanis - EMA20| > 2,5 x gunluk ATR): "siki" surumde gec,
  "yumusak" surumde serbest. Golge strateji yumusak surumdur; uzama yalnizca isaretlenir.
- Stop mesafesi 2 x gunluk ATR (GIRIS mumunun gununden onceki gunluk mum). Hedef yok.
- ATR, gercek araligin 14 mumluk BASIT ortalamasidir (kaynaktaki gibi; Wilder degil).
Cikis (ileri testte): +1R'de stop girise, +2R'de +1R kilit, 2R asilinca en iyi fiyat - 2 x 4H ATR (ATR giriste
sabitlenir); 7 gunde +1R gorulmediyse cikilir.

Kaynaktan bilincli farklar:
- Iz suren stopun ATR'si giristen ONCE kapanmis son 4H mumundandir (kaynak, giris mumunun kendisini de
  kullaniyordu: kucuk bir bakis-one).
- Kaynakta, gunluk verisi olmayan gunlerde (FX'te pazar) bir gun daha eski deger kullaniliyordu; burada her zaman
  en son kapanmis onceki gun kullanilir.
"""

from __future__ import annotations

import math

from ..base import Context, Signal
from .v13 import NAN, Frame

H4_SECONDS = 14400
DAY = 86400
STOP_DAILY_ATR = 2.0
SPIKE_ATR = 2.0
STRETCH_ATR = 2.5
MIN_DAILY, MIN_H4 = 55, 60


def simple_atr(frame: Frame, period: int = 14) -> list[float]:
    """Gercek araligin `period` mumluk basit ortalamasi (pandas `rolling(period).mean()`)."""
    out, total = [], 0.0
    for index, value in enumerate(frame.tr):
        total += value
        if index >= period:
            total -= frame.tr[index - period]
        out.append(total / period if index >= period - 1 else NAN)
    return out


def days_before(d1: list[dict], moment: float) -> list[dict]:
    """`moment`in icinde oldugu takvim gununden ONCEKI gunluk mumlar (o gunun mumu, kapanmis olsa da, haric)."""
    day = int(moment // DAY) * DAY
    return [bar for bar in d1 if bar["time"] < day]


def daily_state(rows: list[dict]) -> dict | None:
    """Son gunluk mumdaki yon (+1 / -1 / 0), asiri uzama ve gunluk ATR."""
    if len(rows) < MIN_DAILY:
        return None
    frame = Frame(rows)
    close, e20, e50, before = frame.C[-1], frame.e20[-1], frame.e50[-1], frame.e20[-4]
    atr, value = simple_atr(frame)[-1], frame.rsi[-1]
    if close < e20 < e50 and e20 < before:
        bias = -1
    elif close > e20 > e50 and e20 > before:
        bias = 1
    else:
        bias = 0
    stretch = (not math.isnan(value) and (value < 20 or value > 80)) or abs(close - e20) > STRETCH_ATR * atr
    return {"bias": bias, "stretch": bool(stretch), "atr": atr}


def signal(h4: list[dict], d1: list[dict]) -> dict | None:
    """`h4[-1]` az once kapanmis sinyal mumudur -> {side, stretch, stop_distance, atr4} ya da None (`bt.py`)."""
    if len(h4) < MIN_H4:
        return None
    daily = daily_state(days_before(d1, h4[-1]["time"]))
    if daily is None or daily["bias"] == 0:
        return None
    frame = Frame(h4)
    sign = daily["bias"]
    close, e20, e50 = frame.C[-1], frame.e20[-1], frame.e50[-1]
    aligned = -1 if close < e20 < e50 else (1 if close > e20 > e50 else 0)
    if aligned != sign:
        return None
    body, span, value = frame.C[-1] - frame.O[-1], frame.H[-1] - frame.L[-1], frame.rsi[-1]
    if math.isnan(value) or not (body * sign > 0 and abs(body) > 0.5 * span):
        return None
    if (sign > 0) != (value > 50) or value == 50:
        return None
    atr4 = simple_atr(frame)[-1]
    if math.isnan(atr4) or span > SPIKE_ATR * atr4 or (frame.H[-2] - frame.L[-2]) > SPIKE_ATR * atr4:
        return None
    entry_day = daily_state(days_before(d1, h4[-1]["time"] + H4_SECONDS))  # giris mumunun gunune gore
    if entry_day is None or math.isnan(entry_day["atr"]) or entry_day["atr"] <= 0:
        return None
    return {"side": "BUY" if sign > 0 else "SELL", "stretch": daily["stretch"],
            "stop_distance": STOP_DAILY_ATR * entry_day["atr"], "atr4": atr4}


class WeekTrade:
    id, kind = "tb_week_trade_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15 = context.bars.get("M15") or []
        h4, d1 = context.bars.get("H4") or [], context.bars.get("D1") or []
        if not m15 or not h4:
            return None
        closed_at = int(m15[-1]["time"]) + 900
        if closed_at % H4_SECONDS or int(h4[-1]["time"]) + H4_SECONDS != closed_at:
            return None  # 4H mumu bu M15 mumuyla kapanmadi (ya da veri guncel degil)
        found = signal(h4, d1)
        if found is None:
            return None
        sign = 1.0 if found["side"] == "BUY" else -1.0
        entry, distance = float(m15[-1]["close"]), found["stop_distance"]
        detail = {"type": "WEEKTRADE", "model": "week trade", "score": None, "stretch": found["stretch"],
                  "tp1": None, "tp2": None, "volume_ratio": None, "atr4": found["atr4"]}
        return Signal(found["side"], entry, entry - sign * distance, entry + sign * 2.0 * distance,
                      "gunluk + 4H EMA20/50 yonu, 4H govde tetigi, stop 2 x gunluk ATR"
                      + (" (asiri uzama)" if found["stretch"] else ""), bar_time=int(m15[-1]["time"]), plan=detail)
