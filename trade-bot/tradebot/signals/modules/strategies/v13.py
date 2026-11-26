"""v13 SMC / EMA geri cekilme (kullanicinin eski masasindaki `smc.py`nin birebir tasinmasi). YALNIZCA GOLGE.

Kaynak koddaki esikler ve siralama aynen korunur: donus noktalari k=3 (EMA yapisi icin k=2), displacement = govde >
1,5 x son 20 govde ortalamasi VEYA > 1 x ATR ve FVG birakir, sonradan tamamen dolan FVG gecersiz, Order Block =
displacement'tan onceki 5 mumdaki ilk ters mum, OB+FVG cakismasi, BOS/CHoCH, likidite seviyeleri (son 6 donus
noktasi, 0,15 ATR icindeki esit tepe/dipler, onceki gunun tepe/dibi, Asya ve Londra seans tepe/dibi), puan tablosu,
model siniflamasi (1-4), esik (Model 1: 65, digerleri 60), son kapanmis mumda ret mumu zorunlulugu, stop = supurme/yapi
ucu -/+ 0,3 ATR, Hedef 1 = 1R otesindeki en yakin donus noktasi (yoksa 1,5R), Hedef 2 = max(2,5R, Hedef 1 + 0,5R),
DAY icin R/R < 1,5 ise islem yok. DAY = H1 mumlari, WEEK = H4 mumlari (hedef yok, iz suren stop).

Kaynaktan bilincli farklar:
- Veri bizim Exness mumlarimizdir (kaynakta yfinance); pencere 256 H1 / 120 H4 / 120 D1 kapanmis mumdur.
- Seans saatleri kaynakta Istanbul saatiyledir (Asya 03-11, Londra 10-19); burada UTC+3 sabit kaydirmayla ayni
  saatler kullanilir. "Onceki gun" = karar mumundan once kapanmis son gunluk mum.
- Kaynaktaki sabit kodlu "US PMI -5 puan" yoktur: canli girislerde botun kendi haber kapisi calisir; gecmis
  oynatmada haber takvimi olmadigindan puan duzeltmesi yapilmaz.
- Her hesap yalnizca verilen (karar anina kadar kapanmis) mumlarla yapilir: donus noktalari, FVG dolumu ve
  seviyeler gelecegi goremez.
"""

from __future__ import annotations

import math

from ..base import Context, Signal

ISTANBUL = 3 * 3600  # kaynak kod seans saatlerini Istanbul saatiyle (UTC+3) tanimlar
NAN = float("nan")
MIN_BARS = {"H1": 200, "H4": 60}
LOOK = {"H1": 36, "H4": 30}
SECONDS = {"H1": 3600, "H4": 14400}
DAY_MIN_RR = 1.5
THRESHOLD_MODEL_1, THRESHOLD_OTHER = 65, 60


def _ewm(values: list[float], alpha: float) -> list[float]:
    """pandas `ewm(adjust=False).mean()`: bastaki `nan` degerler atlanir, ilk gecerli deger baslangictir."""
    out, current = [], None
    for value in values:
        if current is None:
            if not math.isnan(value):
                current = value
        elif not math.isnan(value):
            current = alpha * value + (1 - alpha) * current
        out.append(NAN if current is None else current)
    return out


def ema_series(values: list[float], span: int) -> list[float]:
    return _ewm(values, 2.0 / (span + 1))


def rma_series(values: list[float], period: int) -> list[float]:
    return _ewm(values, 1.0 / period)


class Frame:
    """Kapanmis mumlar + kaynak koddaki `prep()` sutunlari."""

    def __init__(self, bars: list[dict]):
        self.bars = bars
        self.T = [int(b["time"]) for b in bars]
        self.O = [float(b["open"]) for b in bars]
        self.H = [float(b["high"]) for b in bars]
        self.L = [float(b["low"]) for b in bars]
        self.C = [float(b["close"]) for b in bars]
        self.V = [float(b.get("tick_volume") or b.get("volume") or 0.0) for b in bars]
        n = len(bars)
        self.e20, self.e21, self.e50 = (ema_series(self.C, span) for span in (20, 21, 50))
        ranges = [max(self.H[i] - self.L[i], abs(self.H[i] - self.C[i - 1]) if i else 0.0,
                      abs(self.L[i] - self.C[i - 1]) if i else 0.0) for i in range(n)]
        self.tr = ranges
        self.atr = rma_series(ranges, 14)
        self.body = [abs(self.C[i] - self.O[i]) for i in range(n)]
        self.ab = [sum(self.body[i - 19:i + 1]) / 20.0 if i >= 19 else NAN for i in range(n)]
        change = [NAN] + [self.C[i] - self.C[i - 1] for i in range(1, n)]
        gain = rma_series([max(c, 0.0) if not math.isnan(c) else NAN for c in change], 14)
        loss = rma_series([max(-c, 0.0) if not math.isnan(c) else NAN for c in change], 14)
        self.rsi = []
        for g, lo in zip(gain, loss):
            if math.isnan(g) or math.isnan(lo) or (g == 0 and lo == 0):
                self.rsi.append(NAN)
            else:
                self.rsi.append(100.0 if lo == 0 else 100.0 - 100.0 / (1.0 + g / lo))

    def __len__(self) -> int:
        return len(self.bars)


def swings(frame: Frame, k: int = 3) -> tuple[list[int], list[int]]:
    """Donus noktalari (kaynaktaki gibi esitlik sayilir). Son `k` mum donus noktasi olamaz."""
    highs, lows = [], []
    for i in range(k, len(frame) - k):
        if frame.H[i] == max(frame.H[i - k:i + k + 1]):
            highs.append(i)
        if frame.L[i] == min(frame.L[i - k:i + k + 1]):
            lows.append(i)
    return highs, lows


def trend(frame: Frame) -> str:
    """'L'/'S' guclu, 'l'/'s' zayif, 'N' notr (kaynaktaki `trend()`)."""
    if len(frame) < 6:
        return "N"
    close, e20, e50 = frame.C[-1], frame.e20[-1], frame.e50[-1]
    if close > e20 > e50 and e50 >= frame.e50[-6]:
        return "L"
    if close < e20 < e50 and e50 <= frame.e50[-6]:
        return "S"
    if close > e50 and e20 > e50:
        return "l"
    if close < e50 and e20 < e50:
        return "s"
    return "N"


def rejection(frame: Frame, side: str, i: int = -1) -> str | None:
    """Ret mumu (kaynaktaki `rejection()` birebir): yutan mum, pinbar ya da ret mumu."""
    o, h, low, c = frame.O[i], frame.H[i], frame.L[i], frame.C[i]
    po, pc = frame.O[i - 1], frame.C[i - 1]
    rng = (h - low) or 1e-12
    body, up, lo = abs(c - o), h - max(o, c), min(o, c) - low
    if side == "L":
        if c > o and pc < po and c >= po and o <= pc:
            return "boga engulfing"
        if lo >= 2 * body and lo > 0.5 * rng and c > low + 0.6 * rng:
            return "pinbar (alt fitil)"
        if c > o and lo > 0.35 * rng and c > low + 0.7 * rng:
            return "boga ret mumu"
    else:
        if c < o and pc > po and c <= po and o >= pc:
            return "ayi engulfing"
        if up >= 2 * body and up > 0.5 * rng and c < h - 0.6 * rng:
            return "pinbar (ust fitil)"
        if c < o and up > 0.35 * rng and c < h - 0.7 * rng:
            return "ayi ret mumu"
    return None


def _local_day(moment: int) -> int:
    return (moment + ISTANBUL) // 86400


def _local_hour(moment: int) -> int:
    return ((moment + ISTANBUL) % 86400) // 3600


def levels(frame: Frame, daily: list[dict], hs: list[int], ls: list[int], i_end: int):
    """Supurulebilecek likidite seviyeleri; yalnizca `i_end` mumundan ONCE bilinenler."""
    a = frame.atr[i_end]
    ph = [(frame.H[j], "swing H") for j in hs if j < i_end - 3][-6:]
    pl = [(frame.L[j], "swing L") for j in ls if j < i_end - 3][-6:]
    for arr, name in ((ph, "esit tepeler"), (pl, "esit dipler")):
        for x in range(len(arr)):
            for y in range(x + 1, len(arr)):
                if abs(arr[x][0] - arr[y][0]) < 0.15 * a:
                    arr.append((max(arr[x][0], arr[y][0]) if name == "esit tepeler"
                                else min(arr[x][0], arr[y][0]), name))
    t = frame.T[i_end]
    previous = [bar for bar in daily if bar["time"] + 86400 <= t]
    if previous:
        ph.append((float(previous[-1]["high"]), "PDH"))
        pl.append((float(previous[-1]["low"]), "PDL"))
    today = [j for j in range(i_end) if _local_day(frame.T[j]) == _local_day(t)]
    asia = [j for j in today if 3 <= _local_hour(frame.T[j]) < 11]
    london = [j for j in today if 10 <= _local_hour(frame.T[j]) < 19]
    if len(asia) >= 2:
        ph.append((max(frame.H[j] for j in asia), "Asya H"))
        pl.append((min(frame.L[j] for j in asia), "Asya L"))
    if len(london) >= 2 and _local_hour(t) >= 19:
        ph.append((max(frame.H[j] for j in london), "Londra H"))
        pl.append((min(frame.L[j] for j in london), "Londra L"))
    return ph, pl


def find_sweep(frame: Frame, daily: list[dict], hs, ls, side: str, i0: int, i1: int):
    """i0..i1 araliginda (yeniden eskiye) fitille seviyenin otesine gecip iceride kapanan mum."""
    for i in range(i1, i0 - 1, -1):
        ph, pl = levels(frame, daily, hs, ls, i)
        if side == "L":
            for value, name in pl:
                if frame.L[i] < value and frame.C[i] > value:
                    return i, name, value, frame.L[i]
        else:
            for value, name in ph:
                if frame.H[i] > value and frame.C[i] < value:
                    return i, name, value, frame.H[i]
    return None


def smc_events(frame: Frame, daily: list[dict], look: int) -> list[dict]:
    """Son `look` mumdaki displacement + FVG olaylari; OB, cakisma, supurme ve BOS/CHoCH ile (kaynak: `smc_tf`)."""
    n = len(frame)
    hs, ls = swings(frame)
    H, L, O, C = frame.H, frame.L, frame.O, frame.C
    out = []
    for i in range(max(3, n - look), n):  # i = FVG'nin ucuncu mumu, i-1 = displacement
        k = i - 1
        a = frame.atr[k]
        displaced = frame.body[k] > 1.5 * frame.ab[k] or frame.body[k] > 1.0 * a
        for side in ("L", "S"):
            if side == "L" and not (L[i] > H[i - 2] and C[k] > O[k]):
                continue
            if side == "S" and not (H[i] < L[i - 2] and C[k] < O[k]):
                continue
            if not displaced:
                continue
            fvg = (H[i - 2], L[i]) if side == "L" else (H[i], L[i - 2])
            after = range(i + 1, n)
            if side == "L" and after and min(L[j] for j in after) < fvg[0]:
                continue  # bosluk tamamen doldu: gecersiz
            if side == "S" and after and max(H[j] for j in after) > fvg[1]:
                continue
            ob = None
            for j in range(k - 1, max(k - 6, 0), -1):
                if (side == "L" and C[j] < O[j]) or (side == "S" and C[j] > O[j]):
                    ob = (L[j], H[j], j)
                    break
            overlap = None
            if ob:
                lo, hi = max(ob[0], fvg[0]), min(ob[1], fvg[1])
                if lo <= hi:
                    overlap = (lo, hi)
            prev_h = [j for j in hs if j < k - 1]
            prev_l = [j for j in ls if j < k - 1]
            bos = None
            if side == "L" and prev_h:
                level = H[prev_h[-1]]
                if max(C[k:i + 1]) > level or (after and max(C[j] for j in after) > level):
                    down = (len(prev_h) >= 2 and len(prev_l) >= 2 and H[prev_h[-1]] < H[prev_h[-2]]
                            and L[prev_l[-1]] < L[prev_l[-2]])
                    bos = ("CHoCH" if down else "BOS", level)
            if side == "S" and prev_l:
                level = L[prev_l[-1]]
                if min(C[k:i + 1]) < level or (after and min(C[j] for j in after) < level):
                    up = (len(prev_h) >= 2 and len(prev_l) >= 2 and H[prev_h[-1]] > H[prev_h[-2]]
                          and L[prev_l[-1]] > L[prev_l[-2]])
                    bos = ("CHoCH" if up else "BOS", level)
            sweep = find_sweep(frame, daily, hs, ls, side, max(0, k - 8), k)
            ratio = frame.body[k] / frame.ab[k] if frame.ab[k] and not math.isnan(frame.ab[k]) else NAN
            out.append({"side": side, "i": i, "fvg": fvg, "ob": ob, "ov": overlap, "bos": bos, "sw": sweep,
                        "disp_x": ratio})
    return out


def poi_trigger(frame: Frame, event: dict):
    """Ilgi bolgesi (cakisma > OB > FVG), son kapanmis mumun bolgeye donup donmedigi ve ret mumu."""
    side = event["side"]
    zone = event["ov"] or (event["ob"][:2] if event["ob"] else event["fvg"])
    lo, hi = zone
    a = frame.atr[-1]
    if side == "L":
        touched = frame.L[-1] <= hi + 0.05 * a and frame.C[-1] > lo
    else:
        touched = frame.H[-1] >= lo - 0.05 * a and frame.C[-1] < hi
    found = rejection(frame, side) if touched and event["i"] < len(frame) - 1 else None
    return zone, touched, found


def score_smc(event: dict, daily_trend: str, upper_trend: str, found: str | None, frame: Frame):
    score, side = 45, event["side"]
    if daily_trend.upper() == side:
        score += 8 if daily_trend == side else 4
    elif daily_trend.upper() in "LS" and daily_trend.upper() != side:
        score -= 6
    if upper_trend.upper() == side:
        score += 5
    if event["sw"]:
        score += 10
    score += 8  # displacement
    if event["bos"]:
        score += 8 if event["bos"][0] == "CHoCH" else 6
    if event["ov"]:
        score += 10
    elif event["ob"]:
        score += 4
    if found:
        score += 8
    value = frame.rsi[-1]
    if (side == "L" and value > 75) or (side == "S" and value < 25):
        score -= 4
    if event["sw"] and event["ov"] and event["bos"]:
        model = "1 SMC OB+FVG"
    elif event["sw"]:
        model = "3 Sweep reversal+OB/FVG"
    elif event["bos"]:
        model = "4 BOS continuation+OB/FVG"
    else:
        model = "FVG/OB (zayif)"
    return score, model


def plan(frame: Frame, side: str, entry: float, extreme: float, kind: str, pivots) -> dict:
    """Stop ve hedefler (kaynaktaki `plan()`): stop = uc -/+ 0,3 ATR; WEEK'te hedef yoktur."""
    a = frame.atr[-1]
    extreme = min(extreme, entry) if side == "L" else max(extreme, entry)
    stop = extreme - 0.3 * a if side == "L" else extreme + 0.3 * a
    risk = abs(entry - stop)
    if kind == "WEEK":
        return {"entry": entry, "sl": stop, "tp1": None, "tp2": None, "rr": None}
    hs, ls = pivots
    if side == "L":
        targets = [frame.H[j] for j in hs if frame.H[j] > entry + risk]
        tp1 = min(targets) if targets else entry + 1.5 * risk
        tp2 = max(entry + 2.5 * risk, tp1 + 0.5 * risk)
    else:
        targets = [frame.L[j] for j in ls if frame.L[j] < entry - risk]
        tp1 = max(targets) if targets else entry - 1.5 * risk
        tp2 = min(entry - 2.5 * risk, tp1 - 0.5 * risk)
    return {"entry": entry, "sl": stop, "tp1": tp1, "tp2": tp2, "rr": abs(tp1 - entry) / risk if risk else 0.0}


def ema_pullbacks(frame: Frame, daily_trend: str, upper_trend: str) -> list[dict]:
    """Model 2: ust yon net + son kapanmis mum EMA20/21'e (ya da 21-50 bolgesine) cekilmis."""
    out = []
    a, low, high, close = frame.atr[-1], frame.L[-1], frame.H[-1], frame.C[-1]
    e20, e21, e50 = frame.e20[-1], frame.e21[-1], frame.e50[-1]
    for side in ("L", "S"):
        if daily_trend.upper() != side or upper_trend.upper() != side:
            continue
        if side == "L":
            tagged = low <= max(e20, e21) + 0.15 * a and close > min(e21, e50) - 0.1 * a
        else:
            tagged = high >= min(e20, e21) - 0.15 * a and close < max(e21, e50) + 0.1 * a
        if not tagged:
            continue
        found = rejection(frame, side)
        hs, ls = swings(frame, 2)
        structure = None
        if len(ls) >= 2 and len(hs) >= 2:
            if side == "L" and frame.L[ls[-1]] > frame.L[ls[-2]]:
                structure = "HL"
            if side == "S" and frame.H[hs[-1]] < frame.H[hs[-2]]:
                structure = "LH"
        score = 50
        if daily_trend == side:
            score += 4
        if found:
            score += 10
        if structure:
            score += 6
        value = frame.rsi[-1]
        if (side == "L" and value > 75) or (side == "S" and value < 25):
            score -= 4
        out.append({"side": side, "model": "2 EMA pullback", "score": score, "rej": found, "struct": structure})
    return out


def candidates(frame: Frame, daily_frame: Frame, upper: Frame, daily: list[dict], tf: str, family: str) -> list[dict]:
    """Bir zaman diliminde bir ailenin (smc | ema) GECEN adaylari, en iyisi basta (kaynak: `analyse`)."""
    kind = "DAY" if tf == "H1" else "WEEK"
    daily_trend, upper_trend = trend(daily_frame), trend(upper)
    found: list[dict] = []
    if family == "smc":
        pivots = swings(frame)
        for event in smc_events(frame, daily, LOOK[tf]):
            zone, touched, rej = poi_trigger(frame, event)
            score, model = score_smc(event, daily_trend, upper_trend, rej, frame)
            i, side = event["i"], event["side"]
            if event["sw"]:
                extreme = event["sw"][3]
            else:
                extreme = min(frame.L[i - 3:i + 1]) if side == "L" else max(frame.H[i - 3:i + 1])
            if side == "L":
                extreme = min(extreme, zone[0], frame.L[-1] if rej else zone[0])
            else:
                extreme = max(extreme, zone[1], frame.H[-1] if rej else zone[1])
            entry = frame.C[-1] if rej else (zone[0] + zone[1]) / 2
            found.append({"side": side, "model": model, "score": score, "rej": rej,
                          "plan": plan(frame, side, entry, extreme, kind, pivots)})
    else:
        for item in ema_pullbacks(frame, daily_trend, upper_trend):
            hs, ls = swings(frame, 2)
            side = item["side"]
            if side == "L" and ls:
                extreme = frame.L[ls[-1]]
            else:
                extreme = frame.H[hs[-1]] if hs else frame.C[-1]
            extreme = min(extreme, frame.L[-1]) if side == "L" else max(extreme, frame.H[-1])
            item["plan"] = plan(frame, side, frame.C[-1], extreme, kind, swings(frame))
            found.append(item)
    passed = []
    for item in found:
        threshold = THRESHOLD_MODEL_1 if item["model"].startswith("1") else THRESHOLD_OTHER
        ok = item["score"] >= threshold and bool(item["rej"])
        # 1e-9: Hedef 1 tam 1,5R oldugunda kayan nokta yuvarlamasi islemi rastgele elemesin.
        if kind == "DAY" and item["plan"]["rr"] is not None and item["plan"]["rr"] < DAY_MIN_RR - 1e-9:
            ok = False
        if ok:
            passed.append(item)
    passed.sort(key=lambda item: item["score"], reverse=True)
    return passed


def volume_ratio(frame: Frame) -> float | None:
    """Tetik mumunun hacmi / onceki 20 mumun ortalamasi (hacim yoksa None). Yalnizca raporlama icindir."""
    if len(frame) < 21:
        return None
    base = sum(frame.V[-21:-1]) / 20.0
    return round(frame.V[-1] / base, 2) if base > 0 else None


class V13:
    """`smc.py` adaylari: yalnizca ilgili ust mum (H1 ya da H4) KAPANDIGINDA degerlendirilir."""

    kind = "strategy"

    def __init__(self, family: str, tf: str):
        if family not in ("smc", "ema") or tf not in SECONDS:
            raise ValueError("bilinmeyen v13 ailesi ya da zaman dilimi")
        self.family, self.tf = family, tf
        self.id = f"tb_{'smc' if family == 'smc' else 'emapb'}_{'day' if tf == 'H1' else 'week'}_v13"

    def evaluate(self, context: Context) -> Signal | None:
        m15 = context.bars.get("M15") or []
        bars = context.bars.get(self.tf) or []
        h4, d1 = context.bars.get("H4") or [], context.bars.get("D1") or []
        if not m15 or len(bars) < MIN_BARS[self.tf] or len(h4) < MIN_BARS["H4"] or len(d1) < 60:
            return None
        closed_at = int(m15[-1]["time"]) + 900
        if closed_at % SECONDS[self.tf] or int(bars[-1]["time"]) + SECONDS[self.tf] != closed_at:
            return None  # ust mum bu M15 mumuyla kapanmadi (ya da veri guncel degil)
        frame = Frame(bars)
        upper = frame if self.tf == "H4" else Frame(h4)
        passed = candidates(frame, Frame(d1), upper, d1, self.tf, self.family)
        if not passed:
            return None
        best = passed[0]
        side = "BUY" if best["side"] == "L" else "SELL"
        sign = 1.0 if side == "BUY" else -1.0
        entry, stop = best["plan"]["entry"], best["plan"]["sl"]
        if (entry - stop) * sign <= 0:
            return None
        day = self.tf == "H1"
        detail = {"type": "DAY" if day else "WEEK", "model": best["model"], "score": best["score"],
                  "tp1": best["plan"]["tp1"], "tp2": best["plan"]["tp2"], "volume_ratio": volume_ratio(frame)}
        target = best["plan"]["tp2"] if day else entry + sign * 2.0 * abs(entry - stop)
        return Signal(side, entry, stop, target, f"v13 {best['model']} ({detail['type']}), puan {best['score']}, "
                      f"tetik: {best['rej']}", bar_time=int(m15[-1]["time"]), plan=detail)
