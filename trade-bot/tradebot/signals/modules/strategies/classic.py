"""Uc bilinen strateji, YALNIZCA GOLGE (kullanici istegi 2026-11-26). Parametreler yaygin/ozgun tanimlardan alindi;
sonuca gore ayarlanmadi (asiri uyum olmasin). Tanimlar ve kaynaklar: PROGRESS.md.

1) `tb_silver_bullet_v1` - ICT "Silver Bullet": New York saatiyle 03-04 (Londra acilisi), 10-11 ve 14-15
   pencerelerinde, bir likidite supurmesinden sonra olusan FVG'ye ilk donuste giris. Stop supurmenin otesi,
   hedef karsi taraftaki en yakin likidite (en az 1R uzakta). Ozgun tanim 1-5 dakikalik grafikledir; burada en kucuk
   zaman dilimi M15'tir (FVG pencerede tamamlanmali; donus pencere bitiminden en gec 1 saat sonra).
2) `tb_asia_london_v1` - Asya araligi / Londra kirilimi: Londra saatiyle 00-08 araliginin tepe/dibi; 08-12 arasinda
   aralik disinda ILK M15 kapanisinda giris. Stop araligin karsi ucu, hedef aralik genisligi kadar ileride, 21:00'de
   cikis. Aralik genisligi gunluk ATR'nin %20'si ile %100'u arasinda olmali.
3) `tb_turtle55_v1` - Kaplumbaga (Turtle) Sistem 2, kapanisa gore: gunluk kapanis onceki 55 gunun tepesini asarsa
   AL (dibini kirarsa SAT); stop 2N (N = 20 gunluk Wilder ATR); gunluk kapanis onceki 20 gunun dibinin altina
   (ustune) inerse cikis.
Hepsi yalnizca KAPANMIS mumlarla karar verir.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from ..base import Context, Signal
from . import v13
from .v13 import Frame

NEW_YORK, LONDON = ZoneInfo("America/New_York"), ZoneInfo("Europe/London")
M15 = 900
SILVER_HOURS = (3, 10, 14)  # New York saati: pencere bu saatte baslar, 1 saat surer
SILVER_RETURN = 3600  # FVG'ye donus, pencere bittikten en gec bu kadar sonra
SILVER_SWEEP_BARS = 8
SILVER_BUFFER_ATR = 0.1
ASIA_END, LONDON_END, DAY_EXIT = 8, 12, 21  # Londra saati
ASIA_MIN_BARS = 24
RANGE_MIN_ATR, RANGE_MAX_ATR = 0.2, 1.0
TURTLE_ENTRY, TURTLE_EXIT, TURTLE_N, TURTLE_STOP_N = 55, 20, 20, 2.0


def _local(moment: float, zone: ZoneInfo) -> datetime:
    return datetime.fromtimestamp(moment, timezone.utc).astimezone(zone)


class SilverBullet:
    id, kind = "tb_silver_bullet_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15, d1 = context.bars.get("M15") or [], context.bars.get("D1") or []
        if len(m15) < 100:
            return None
        closed_at = int(m15[-1]["time"]) + M15
        local = _local(closed_at - 1, NEW_YORK)  # kapanan mumun icinde bulundugu an
        window = next((hour for hour in SILVER_HOURS
                       if 0 <= (local.hour - hour) * 3600 + local.minute * 60 + local.second < 3600 + SILVER_RETURN), None)
        if window is None:
            return None
        start = closed_at - 1 - ((local.hour - window) * 3600 + local.minute * 60 + local.second)  # pencerenin basi
        frame = Frame(m15[-128:])
        n = len(frame)
        hs, ls = v13.swings(frame)
        for i in range(n - 2, max(2, n - 9), -1):  # i: FVG'nin ucuncu mumu (son mumdan once tamamlanmis olmali)
            done = frame.T[i] + M15
            if not (start < done <= start + 3600):
                continue  # FVG pencerenin icinde tamamlanmali
            for side in ("L", "S"):
                k = i - 1
                if side == "L" and not (frame.L[i] > frame.H[i - 2] and frame.C[k] > frame.O[k]):
                    continue
                if side == "S" and not (frame.H[i] < frame.L[i - 2] and frame.C[k] < frame.O[k]):
                    continue
                sweep = v13.find_sweep(frame, d1, hs, ls, side, max(0, k - SILVER_SWEEP_BARS), k)
                if sweep is None:
                    continue
                low, high = (frame.H[i - 2], frame.L[i]) if side == "L" else (frame.H[i], frame.L[i - 2])
                between = range(i + 1, n - 1)
                if side == "L":
                    if any(frame.L[j] <= high for j in between) or not (frame.L[-1] <= high and frame.C[-1] > low):
                        continue  # ilk donus degil, ya da son mum bosluga donmedi / boslugu asagi kirdi
                    extreme = min([sweep[3]] + [frame.L[j] for j in range(sweep[0], n)])
                    stop = extreme - SILVER_BUFFER_ATR * frame.atr[-1]
                else:
                    if any(frame.H[j] >= low for j in between) or not (frame.H[-1] >= low and frame.C[-1] < high):
                        continue
                    extreme = max([sweep[3]] + [frame.H[j] for j in range(sweep[0], n)])
                    stop = extreme + SILVER_BUFFER_ATR * frame.atr[-1]
                entry = frame.C[-1]
                sign = 1.0 if side == "L" else -1.0
                risk = (entry - stop) * sign
                if risk <= 0:
                    continue
                highs, lows = v13.levels(frame, d1, hs, ls, n - 1)
                pool = [value for value, _ in (highs if side == "L" else lows) if (value - entry) * sign >= risk]
                if not pool:
                    continue  # karsi tarafta en az 1R uzakta likidite yok
                target = min(pool) if side == "L" else max(pool)
                detail = {"type": "FIXED", "model": f"silver bullet {window:02d} NY", "score": None, "target": target,
                          "max_bars": 96, "volume_ratio": None}
                return Signal("BUY" if side == "L" else "SELL", entry, stop, target,
                              f"Silver Bullet ({window:02d}:00 New York): {sweep[1]} supurmesi, FVG'ye ilk donus",
                              bar_time=int(m15[-1]["time"]), plan=detail)
        return None


class AsiaLondon:
    id, kind = "tb_asia_london_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15, d1 = context.bars.get("M15") or [], context.bars.get("D1") or []
        if len(m15) < 60 or len(d1) < 20:
            return None
        closed_at = int(m15[-1]["time"]) + M15
        local = _local(closed_at - 1, LONDON)
        if not (ASIA_END <= local.hour < LONDON_END):
            return None
        today = [(bar, _local(bar["time"], LONDON)) for bar in m15[-80:]]
        today = [(bar, when) for bar, when in today if when.date() == local.date()]
        asia = [bar for bar, when in today if when.hour < ASIA_END]
        session = [bar for bar, when in today if when.hour >= ASIA_END]
        if len(asia) < ASIA_MIN_BARS or not session:
            return None
        top, bottom = max(bar["high"] for bar in asia), min(bar["low"] for bar in asia)
        width = top - bottom
        daily = Frame(d1).atr[-1]
        if width <= 0 or not daily or math.isnan(daily) or not (RANGE_MIN_ATR * daily <= width <= RANGE_MAX_ATR * daily):
            return None
        if any(bar["close"] > top or bar["close"] < bottom for bar in session[:-1]):
            return None  # bugun aralik disinda daha once kapanis oldu: yalnizca ILK kirilim
        close = float(m15[-1]["close"])
        if close > top:
            side, stop, target = "BUY", bottom, top + width
        elif close < bottom:
            side, stop, target = "SELL", top, bottom - width
        else:
            return None
        sign = 1.0 if side == "BUY" else -1.0
        if (target - close) * sign <= 0:
            return None  # kirilim mumu hedefi coktan gecti
        exit_at = local.replace(hour=DAY_EXIT, minute=0, second=0, microsecond=0)
        bars_left = max(1, int((exit_at.timestamp() - closed_at) // M15))
        detail = {"type": "FIXED", "model": "asya araligi / londra kirilimi", "score": None, "target": target,
                  "max_bars": bars_left, "volume_ratio": None}
        return Signal(side, close, stop, target, "Asya araliginin Londra seansinda kapanisla kirilimi",
                      bar_time=int(m15[-1]["time"]), plan=detail)


class Turtle55:
    id, kind = "tb_turtle55_v1", "strategy"

    def evaluate(self, context: Context) -> Signal | None:
        m15, d1 = context.bars.get("M15") or [], context.bars.get("D1") or []
        if not m15 or len(d1) < TURTLE_ENTRY + TURTLE_N + 1:
            return None
        closed_at = int(m15[-1]["time"]) + M15
        if int(d1[-1]["time"]) + 86400 != closed_at:
            return None  # gunluk mum bu M15 mumuyla kapanmadi (ya da veri guncel degil)
        frame = Frame(d1)
        n_value = v13.rma_series(frame.tr, TURTLE_N)[-1]
        close = frame.C[-1]
        top, bottom = max(frame.H[-TURTLE_ENTRY - 1:-1]), min(frame.L[-TURTLE_ENTRY - 1:-1])
        if not n_value or n_value <= 0:
            return None
        if close > top:
            side, sign = "BUY", 1.0
        elif close < bottom:
            side, sign = "SELL", -1.0
        else:
            return None
        entry = float(m15[-1]["close"])
        stop = entry - sign * TURTLE_STOP_N * n_value
        detail = {"type": "CHANNEL", "model": "turtle 55/20", "score": None, "exit_days": TURTLE_EXIT,
                  "volume_ratio": None}
        return Signal(side, entry, stop, entry + sign * 2.0 * abs(entry - stop),
                      f"{TURTLE_ENTRY} gunluk kirilim (kapanisla), stop {TURTLE_STOP_N:g}N", bar_time=int(m15[-1]["time"]),
                      plan=detail)
