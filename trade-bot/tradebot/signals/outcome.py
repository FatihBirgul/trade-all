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


# ---------------------------------------------------------------- swing ailesinin cikis plani
# Kullanicinin kurallari (2026-11-26). Rakamlar onceden sabittir, sonuca gore ayarlanmaz:
#   - TP1 = 1R: pozisyonun yarisi kapatilir, stop girise cekilir.
#   - Hedefe ilerleme %60 olunca stop hedef mesafesinin %30'una, %80 olunca %60'ina cekilir (kar kilidi).
#     ("%60/%80'de kar kilitle" kuralinin yorumu: kilit seviyesi, ulasilan ilerlemenin yaklasik yarisi / dortte ucu.)
#   - Kalan yari hedefte (`target_r`, 1,5-2,5R) kapanir.
SWING_TP1_R = 1.0
SWING_TP1_FRACTION = 0.5
SWING_LOCKS = ((0.6, 0.3), (0.8, 0.6))  # (hedefe ilerleme, kilitlenen pay)
SWING_MAX_BARS = 3000  # ~31 gun; bu kadar surede sonuclanmayan islem "acik" raporlanir


def simulate_swing(side: str, entry: float, stop: float, target_r: float, at: float, bars: list[dict], *,
                   spread_at=None) -> dict | None:
    """Swing cikis planiyla sonuc -> {r, closed_at, bars, first, mfe_r, mae_r} (acik kalirsa r None, open_r dolu).

    `bars`: giris anini iceren mumdan baslayan bid mumlari. `spread_at(zaman)`: o andaki spread (SELL ask'tan
    kapanir). Ayni mumda once aleyhte hareket sayilir (kotumser)."""
    if target_r <= 0:
        return None
    return _partial(side, entry, stop, SWING_TP1_R, target_r, SWING_LOCKS, at, bars, spread_at, SWING_MAX_BARS, False)


# DAY plani (eski masanin v10 gun ici yonetimi): Hedef 1'de yari kapanir + stop girise; kalan Hedef 2'de kapanir.
# Hedef 2'ye ilerlemeye gore: %40'ta stop girise, %60'ta yolun %25'i, %80'de %50'si kilitlenir. En cok 5 gun.
PLAN_LOCKS = ((0.4, 0.0), (0.6, 0.25), (0.8, 0.5))
PLAN_MAX_BARS = 480


def simulate_plan(side: str, entry: float, stop: float, tp1: float, tp2: float, at: float, bars: list[dict], *,
                  spread_at=None) -> dict | None:
    """Fiyat olarak verilen iki hedefli plan -> `simulate_swing` ile ayni bicimde sonuc. Sure dolarsa kapanir."""
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    sign = 1.0 if side == "BUY" else -1.0
    tp1_r, target_r = (tp1 - entry) * sign / risk, (tp2 - entry) * sign / risk
    if tp1_r <= 0 or target_r <= 0:
        return None
    return _partial(side, entry, stop, tp1_r, target_r, PLAN_LOCKS, at, bars, spread_at, PLAN_MAX_BARS, True)


def _partial(side, entry, stop, tp1_r, target_r, locks, at, bars, spread_at, max_bars, time_exit) -> dict | None:
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    sign = 1.0 if side == "BUY" else -1.0
    spread_at = spread_at or (lambda moment: 0.0)
    stop_r, realized, remaining, partial = -1.0, 0.0, 1.0, False
    first, best, worst = None, 0.0, 0.0
    after = [b for b in bars if b["time"] + BAR_SECONDS > at][:max_bars]
    for index, bar in enumerate(after):
        shift = spread_at(bar["time"]) if side == "SELL" else 0.0
        adverse = ((bar["low"] if side == "BUY" else bar["high"] + shift) - entry) * sign / risk
        favour = ((bar["high"] if side == "BUY" else bar["low"] + shift) - entry) * sign / risk
        worst, closed_at = min(worst, adverse), bar["time"] + BAR_SECONDS
        if adverse <= stop_r:
            first = first or ("SL" if stop_r <= -1.0 else None)
            return {"first": first, "r": round(realized + remaining * stop_r, 3), "closed_at": closed_at,
                    "bars": index + 1, "mfe_r": round(best, 2), "mae_r": round(worst, 2)}
        best = max(best, favour)
        if not partial and target_r > tp1_r and favour >= tp1_r:
            realized += SWING_TP1_FRACTION * tp1_r
            remaining -= SWING_TP1_FRACTION
            partial = True
            stop_r = max(stop_r, 0.0)
            first = first or "TP1"
        if favour >= target_r:
            first = first or "TP"
            return {"first": first, "r": round(realized + remaining * target_r, 3), "closed_at": closed_at,
                    "bars": index + 1, "mfe_r": round(best, 2), "mae_r": round(worst, 2)}
        for progress, locked in locks:
            if best >= progress * target_r:
                stop_r = max(stop_r, locked * target_r)
    last = ((after[-1]["close"] + (spread_at(after[-1]["time"]) if side == "SELL" else 0.0)) - entry) * sign / risk if after else 0.0
    if time_exit and len(after) >= max_bars:
        return {"first": first or "TIME", "r": round(realized + remaining * last, 3),
                "closed_at": after[-1]["time"] + BAR_SECONDS, "bars": len(after), "mfe_r": round(best, 2),
                "mae_r": round(worst, 2)}
    return {"first": first, "r": None, "open_r": round(realized + remaining * last, 3), "closed_at": None,
            "bars": len(after), "mfe_r": round(best, 2), "mae_r": round(worst, 2)}


H4_SECONDS = 14400
TRAIL_BUFFER_ATR = 0.3  # yapi stopu: donus noktasinin 0,3 x 4H ATR otesi


def simulate_trail(side: str, entry: float, stop: float, at: float, bars: list[dict], state, *, spread_at=None,
                   be_at_r: float = 1.0, lock: tuple[float, float] | None = None, trail_atr: float | None = None,
                   structure: bool = False, timeout: float | None = None) -> dict | None:
    """Hedefsiz, iz suren stoplu plan (WEEK). Stop yalnizca ILERI tasinir.

    - `be_at_r`: bu kadar R goruldugunde stop girise cekilir.
    - `lock` = (esik R, kilit R): esik goruldugunde stop kilit R'ye cekilir; ardindan `trail_atr` verilmisse her 4H
      kapanisinda stop = en iyi fiyat - trail_atr x 4H ATR.
    - `structure`: her 4H kapanisinda, giristen SONRA olusmus son onayli donus noktasinin 0,3 x 4H ATR otesine.
    - `timeout`: bu sure icinde +1R gorulmediyse mum kapanisinda cikilir.
    `state(an)` -> o anda kapanmis 4H mumlarindan {atr, low: (zaman, fiyat) | None, high: ...} ya da None.
    Ayni mumda once aleyhte hareket sayilir; stop guncellemeleri bir sonraki mumdan itibaren gecerlidir."""
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    sign = 1.0 if side == "BUY" else -1.0
    spread_at = spread_at or (lambda moment: 0.0)
    stop_r, first, best, worst = -1.0, None, 0.0, 0.0
    after = [b for b in bars if b["time"] + BAR_SECONDS > at][:SWING_MAX_BARS]

    def done(r, closed_at, count, label):
        return {"first": label, "r": round(r, 3), "closed_at": closed_at, "bars": count, "mfe_r": round(best, 2),
                "mae_r": round(worst, 2)}

    for index, bar in enumerate(after):
        shift = spread_at(bar["time"]) if side == "SELL" else 0.0
        adverse = ((bar["low"] if side == "BUY" else bar["high"] + shift) - entry) * sign / risk
        favour = ((bar["high"] if side == "BUY" else bar["low"] + shift) - entry) * sign / risk
        close_r = (bar["close"] + shift - entry) * sign / risk
        worst, closed_at = min(worst, adverse), bar["time"] + BAR_SECONDS
        if adverse <= stop_r:
            return done(stop_r, closed_at, index + 1, "SL" if stop_r <= -1.0 else "TRAIL")
        best = max(best, favour)
        if timeout is not None and best < 1.0 and closed_at - at >= timeout:
            return done(close_r, closed_at, index + 1, "TIME")
        if best >= be_at_r:
            stop_r = max(stop_r, 0.0)
        if lock is not None and best >= lock[0]:
            stop_r = max(stop_r, lock[1])
        if closed_at % H4_SECONDS == 0:
            now = state(closed_at)
            if now and now.get("atr"):
                if trail_atr is not None and lock is not None and best >= lock[0]:
                    stop_r = max(stop_r, min(best - trail_atr * now["atr"] / risk, close_r))
                pivot = now.get("low" if side == "BUY" else "high") if structure else None
                if pivot is not None and pivot[0] > at:
                    level = pivot[1] - sign * TRAIL_BUFFER_ATR * now["atr"]
                    level_r = (level - entry) * sign / risk
                    if level_r < close_r:  # stop fiyatin yanlis tarafina konmaz
                        stop_r = max(stop_r, level_r)
    last = ((after[-1]["close"] + (spread_at(after[-1]["time"]) if side == "SELL" else 0.0)) - entry) * sign / risk if after else 0.0
    return {"first": first, "r": None, "open_r": round(last, 3), "closed_at": None, "bars": len(after),
            "mfe_r": round(best, 2), "mae_r": round(worst, 2)}


FIXED_MAX_BARS = 96


def simulate_fixed(side: str, entry: float, stop: float, target: float, at: float, bars: list[dict], *,
                   spread_at=None, max_bars: int = FIXED_MAX_BARS) -> dict | None:
    """Sabit stop + sabit hedef (golge izleyicinin kurali), ondan BAGIMSIZ yazilmis ikinci hesap.

    Fiyatlar acikca alis/satis olarak izlenir: AL pozisyonu satis fiyatindan (bid) kapanir, SAT pozisyonu alis
    fiyatindan (ask = bid + spread). `entry`, pozisyonun acildigi gercek fiyattir (AL icin ask, SAT icin bid).
    Ayni mumda stop ve hedef birlikte gorulurse stop sayilir. `max_bars` mum icinde ikisi de olmazsa o mumun
    kapanisindan cikilir; daha az mum varsa islem aciktir (r None)."""
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    spread_at = spread_at or (lambda moment: 0.0)
    after = [b for b in bars if b["time"] + BAR_SECONDS > at][:max_bars]
    best = worst = 0.0
    for index, bar in enumerate(after):
        spread = spread_at(bar["time"])
        if side == "BUY":  # cikis fiyati: bid
            worst_exit, best_exit = bar["low"], bar["high"]
            lost, won = worst_exit <= stop, best_exit >= target
            adverse, favour = (worst_exit - entry) / risk, (best_exit - entry) / risk
        else:  # cikis fiyati: ask
            worst_exit, best_exit = bar["high"] + spread, bar["low"] + spread
            lost, won = worst_exit >= stop, best_exit <= target
            adverse, favour = (entry - worst_exit) / risk, (entry - best_exit) / risk
        worst, best = min(worst, adverse), max(best, favour)
        if lost or won:
            return {"first": "SL" if lost else "TP", "r": -1.0 if lost else round(abs(target - entry) / risk, 3),
                    "closed_at": bar["time"] + BAR_SECONDS, "bars": index + 1, "mfe_r": round(best, 2),
                    "mae_r": round(worst, 2)}
    if len(after) >= max_bars:
        last = after[-1]
        exit_price = last["close"] + (spread_at(last["time"]) if side == "SELL" else 0.0)
        r = (exit_price - entry) / risk if side == "BUY" else (entry - exit_price) / risk
        return {"first": "TIME", "r": round(r, 3), "closed_at": last["time"] + BAR_SECONDS, "bars": len(after),
                "mfe_r": round(best, 2), "mae_r": round(worst, 2)}
    return {"first": None, "r": None, "closed_at": None, "bars": len(after), "mfe_r": round(best, 2),
            "mae_r": round(worst, 2)}
