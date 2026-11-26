"""Deneme modundaki "acilirdi" sinyallerinin sonradan ne olacagini kapanmis M15 mumlariyla hesaplar.

Yaklasik bir benzetimdir (karar raporu icin): mum ici sira bilinmedigi icin ayni mumda once aleyhte hareket
sayilir (kotumser); spread ve komisyon dusulmez; iz suren stop mum basina bir kez guncellenir.
"""

from __future__ import annotations

BAR_SECONDS = 900


def atr(bars: list[dict], period: int = 14) -> float | None:
    if len(bars) < period + 1:
        return None
    ranges = [max(b["high"] - b["low"], abs(b["high"] - a["close"]), abs(b["low"] - a["close"]))
              for a, b in zip(bars[-period - 1:], bars[-period:])]
    return sum(ranges) / len(ranges)


def simulate(side: str, entry: float, stop: float, tp1: float, tp2: float, at: float, bars: list[dict], *,
             be_at_r: float | None, partial_at_r: float | None, partial_fraction: float,
             trail_atr_mult: float | None, spread: float = 0.0) -> dict | None:
    """-> {first, r, closed_at, bars, mfe_r, mae_r}; `first`: ilk degen seviye (SL | TP1 | TP2 | None).

    Mumlar bid fiyatidir. BUY ask'tan acilir (giris zaten spread kadar yukarida) ve bid'den kapanir; SELL
    bid'den acilir ve ask'tan kapanir: `spread` verilirse SELL icin mum fiyatlari o kadar yukari kaydirilir.
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    sign = 1.0 if side == "BUY" else -1.0
    before = [b for b in bars if b["time"] + BAR_SECONDS <= at]
    after = [b for b in bars if b["time"] + BAR_SECONDS > at]
    if before and after and after[0]["time"] - before[-1]["time"] > BAR_SECONDS:
        return None  # acilis mumu eksik: tahmin edilmez
    width = atr(before)
    to_r = lambda price: (price - entry) * sign / risk  # noqa: E731
    tp1_r, tp2_r = to_r(tp1), to_r(tp2)
    stop_r, realized, remaining, partial_done = -1.0, 0.0, 1.0, False
    first, best, worst = None, 0.0, 0.0
    for index, bar in enumerate(after):
        adverse = to_r(bar["low"] if side == "BUY" else bar["high"] + spread)
        favour = to_r(bar["high"] if side == "BUY" else bar["low"] + spread)
        worst, closed_at = min(worst, adverse), bar["time"] + BAR_SECONDS
        if adverse <= stop_r:
            first = first or ("SL" if stop_r <= -1.0 else None)
            return {"first": first, "r": round(realized + remaining * stop_r, 3), "closed_at": closed_at,
                    "bars": index + 1, "mfe_r": round(best, 2), "mae_r": round(worst, 2)}
        best = max(best, favour)
        if favour >= tp1_r:
            first = first or "TP1"
        if favour >= tp2_r:
            first = first or "TP2"
            return {"first": first, "r": round(realized + remaining * tp2_r, 3), "closed_at": closed_at,
                    "bars": index + 1, "mfe_r": round(best, 2), "mae_r": round(worst, 2)}
        if partial_at_r is not None and not partial_done and favour >= partial_at_r:
            realized += partial_fraction * partial_at_r
            remaining -= partial_fraction
            partial_done = True
        if be_at_r is not None and favour >= be_at_r:
            stop_r = max(stop_r, 0.0)
        if trail_atr_mult is not None and partial_done and width:
            stop_r = max(stop_r, best - trail_atr_mult * width / risk)
    last = to_r(after[-1]["close"] + (spread if side == "SELL" else 0.0)) if after else 0.0
    return {"first": first, "r": None, "open_r": round(realized + remaining * last, 3), "closed_at": None,
            "bars": len(after), "mfe_r": round(best, 2), "mae_r": round(worst, 2)}


def shape(side: str, entry: float, stop: float, at: float, bars: list[dict]) -> dict:
    """Islemin kurulusu: stop mesafesi (% ve ATR kati) ve girisin son kapanisa gore yeri.

    `late_r` > 0: fiyat, sinyal mumunun kapanisindan girise kadar islem yonunde ilerlemis (gec giris).
    """
    risk = abs(entry - stop)
    sign = 1.0 if side == "BUY" else -1.0
    before = [b for b in bars if b["time"] + BAR_SECONDS <= at]
    width = atr(before)
    return {"stop_pct": round(risk / entry * 100.0, 4) if entry else None,
            "stop_atr": round(risk / width, 2) if width else None,
            "late_r": round((entry - before[-1]["close"]) * sign / risk, 3) if before and risk > 0 else None}
