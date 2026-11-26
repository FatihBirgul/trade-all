""""Swing" stratejilerinin (SMC, H1 EMA geri cekilme) ortak kurallari. Kaynak: kullanicinin eski masasindaki
kurallar (2026-11-26); resmi bir gecmis testi yoktur, bu yuzden bu stratejiler yalnizca GOLGE kipinde izlenir.

Kurallar (hepsi kapanmis mumlarla, onceden sabitlenmis; sonuca gore ayarlanmaz):
- Gunluk yon (bias): D1 kapanis > EMA20 > EMA50 ise yukari, tersi asagi; H4 kapanisi EMA50'nin ayni tarafinda
  olmali. Yon yoksa ya da islem yonu tersse GEC.
- Asiri RSI: H1 RSI(14) > 70 iken AL, < 30 iken SAT yok.
- Stop: yapinin (supurulen uc / geri cekilme dibi) otesinde VE en az 1,5 x GUNLUK ATR(14) uzakta.
- Yer: giristen en yakin karsi gunluk donus noktasina (son 60 gun) uzaklik 1R'den azsa GEC.
"""

from __future__ import annotations

from ..indicators import atr, ema, pivots, rsi

DAILY_ATR_MULT = 1.5
RSI_HIGH, RSI_LOW = 70.0, 30.0
ROOM_DAYS = 60
MIN_ROOM_R = 1.0
MIN_D1, MIN_H4, MIN_H1 = 55, 55, 60


def daily_bias(d1: list[dict], h4: list[dict]) -> str | None:
    """'bullish' | 'bearish' | None (yon yok ya da D1 ile H4 uyusmuyor)."""
    if len(d1) < MIN_D1 or len(h4) < MIN_H4:
        return None
    closes = [bar["close"] for bar in d1]
    fast, slow, close = ema(closes, 20)[-1], ema(closes, 50)[-1], closes[-1]
    h4_close, h4_mean = h4[-1]["close"], ema([bar["close"] for bar in h4], 50)[-1]
    if close > fast > slow and h4_close > h4_mean:
        return "bullish"
    if close < fast < slow and h4_close < h4_mean:
        return "bearish"
    return None


def stop_price(side: str, entry: float, structure: float, d1: list[dict]) -> float | None:
    """Yapi stopu ile 1,5 x gunluk ATR'den UZAK olani. Gunluk ATR yoksa None."""
    daily = atr(d1)
    if not daily or daily <= 0:
        return None
    floor = DAILY_ATR_MULT * daily
    if side == "BUY":
        return min(structure, entry - floor)
    return max(structure, entry + floor)


def room_ok(side: str, entry: float, stop: float, d1: list[dict]) -> bool:
    """Giris ile en yakin karsi gunluk donus noktasi arasinda en az 1R yer var mi? Karsi nokta yoksa yer vardir."""
    risk = abs(entry - stop)
    recent = d1[-ROOM_DAYS:]
    highs, lows = pivots(recent)
    if side == "BUY":
        levels = [recent[i]["high"] for i in highs if recent[i]["high"] > entry]
        return not levels or min(levels) - entry >= MIN_ROOM_R * risk
    levels = [recent[i]["low"] for i in lows if recent[i]["low"] < entry]
    return not levels or entry - max(levels) >= MIN_ROOM_R * risk


def rsi_blocks(side: str, h1: list[dict]) -> bool:
    value = rsi([bar["close"] for bar in h1])
    if value is None:
        return True  # olculemiyorsa islem yok
    return value > RSI_HIGH if side == "BUY" else value < RSI_LOW


def plan(side: str, entry: float, structure: float, context_bars: dict) -> float | None:
    """Ortak kapilardan gecen islemin stop fiyati; gecemezse None."""
    d1, h1 = context_bars.get("D1") or [], context_bars.get("H1") or []
    if len(h1) < MIN_H1 or rsi_blocks(side, h1):
        return None
    stop = stop_price(side, entry, structure, d1)
    if stop is None or not room_ok(side, entry, stop, d1):
        return None
    return stop
