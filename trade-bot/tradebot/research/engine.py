"""Faz 5 benzetim motoru: tek pozisyonlu islem benzetimi, filtreler, boyutlandirma, walk-forward ve monkey test.

Kurallar PROGRESS.md "Faz 5 / On kayit" bolumundedir. Ozet:
- Giris sinyali mum KAPANISINDA; giris fiyati o kapanis (AL: + spread). Stop / hedef mum icinde denetlenir; ayni
  mumda ikisi birden olursa stop sayilir; acilis stopun otesindeyse (bosluk) cikis ACILIS fiyatindan.
- Sinyal cikisi mum kapanisinda. AL bid'den, SAT ask'tan (bid + o saatin spread'i) kapanir.
- Maliyet kapisi: giristeki spread / stop mesafesi > %15 ise islem yok (sayilir).
"""

from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable
from zoneinfo import ZoneInfo

import numpy as np

from . import indicators as ind

TF_SECONDS = {"H1": 3600, "H4": 14400, "D1": 86400}
MAX_COST = 0.15
START_BALANCE = 2000.0
RISK_PCT = 0.5
SELECT = {"min_trades": 30, "min_pf": 1.2, "max_dd_pct": 15.0}
PASS = {"min_trades": 40, "min_pf": 1.15, "min_positive_share": 0.6, "min_windows": 2}
SELECT_MONTHS, TEST_MONTHS, WINDOWS, HOLDOUT_MONTHS, REGION_MONTHS = 24, 6, 4, 12, 60
FILTERS = ("F0", "F1", "F2", "F3", "F4")
SIZINGS = ("P1", "P2")
LONDON, NEW_YORK = ZoneInfo("Europe/London"), ZoneInfo("America/New_York")


@dataclass
class Series:
    symbol: str
    tf: str
    time: np.ndarray  # mumun ACILIS zamani (UTC sn)
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray

    @property
    def seconds(self) -> int:
        return TF_SECONDS[self.tf]

    def __len__(self) -> int:
        return len(self.time)


@dataclass
class Spec:
    """Stratejinin cikisi: her mum icin giris / cikis sinyalleri ve stop mesafesi (fiyat)."""
    long: np.ndarray
    short: np.ndarray
    stop: np.ndarray
    exit_long: np.ndarray | None = None
    exit_short: np.ndarray | None = None
    trail: np.ndarray | None = None  # iz suren stop: en iyi fiyat - trail[j] (mum kapanisindan sonra guncellenir)
    target: np.ndarray | None = None  # hedef mesafesi (fiyat)
    max_bars: int | None = None
    exit_fn: Callable | None = None  # ozel cikis: (series, i, sign, entry, stop, spread_at) -> (j, fiyat, neden)
    note: str = ""


@dataclass
class Trade:
    entry_time: int  # giris mumunun KAPANIS zamani
    exit_time: int | None
    side: int
    r: float | None
    weight: float = 1.0
    reason: str = ""


@dataclass
class Costs:
    """Saat bazli spread profili (fiyat birimi): Exness olcumu; yoksa kaynak verinin ask-bid medyani."""
    hours: dict = field(default_factory=dict)
    all: float = 0.0
    source: str = "exness"

    def at(self, moment: float) -> float:
        hour = int(moment // 3600 % 24)
        return float(self.hours.get(hour, self.all))


# ---------------------------------------------------------------- benzetim
def simulate(series: Series, spec: Spec, costs: Costs, entries: list[tuple[int, int]] | None = None,
             allow: tuple[np.ndarray, np.ndarray] | None = None, weights: np.ndarray | None = None,
             max_cost: float = MAX_COST) -> tuple[list[Trade], dict]:
    """Ayni anda en cok bir islem. `entries`: (indeks, yon) listesi verilirse sinyaller yerine bunlar (monkey)."""
    n, sec = len(series), series.seconds
    o, h, low, c, t = series.open, series.high, series.low, series.close, series.time
    if entries is None:
        long_ok = spec.long & (allow[0] if allow is not None else True)
        short_ok = spec.short & (allow[1] if allow is not None else True)
        both = long_ok & short_ok
        idx = np.flatnonzero((long_ok | short_ok) & ~both)
        entries = [(int(i), 1 if long_ok[i] else -1) for i in idx]
    trades: list[Trade] = []
    stats = {"signals": len(entries), "cost_blocked": 0, "open_at_end": 0}
    free_from = 0
    for i, sign in entries:
        if i < free_from or i >= n - 1:
            continue
        dist = spec.stop[i]
        if not (dist > 0 and math.isfinite(dist)):
            continue
        close_time = t[i] + sec
        spread_in = costs.at(close_time)
        if spread_in / dist > max_cost:
            stats["cost_blocked"] += 1
            continue
        entry = c[i] + (spread_in if sign > 0 else 0.0)
        stop = entry - sign * dist
        weight = float(weights[i]) if weights is not None else 1.0
        if spec.exit_fn is not None:
            j, price, reason = spec.exit_fn(series, i, sign, entry, stop, costs.at)
        else:
            j, price, reason = _walk(series, spec, i, sign, entry, stop, costs)
        if j is None:
            stats["open_at_end"] += 1
            trades.append(Trade(int(close_time), None, sign, None, weight, "open"))
            break
        trades.append(Trade(int(close_time), int(t[j] + sec), int(sign), float((price - entry) * sign / dist), weight,
                            reason))
        free_from = j  # ayni kapanista yeni giris olabilir (ters sinyal)
    return trades, stats


def _walk(series: Series, spec: Spec, i: int, sign: int, entry: float, stop: float, costs: Costs):
    o, h, low, c, t, sec = series.open, series.high, series.low, series.close, series.time, series.seconds
    target = entry + sign * spec.target[i] if spec.target is not None and spec.target[i] > 0 else None
    best = entry
    exits = spec.exit_long if sign > 0 else spec.exit_short
    for j in range(i + 1, len(series)):
        shift = 0.0 if sign > 0 else costs.at(t[j])  # SAT pozisyonu ask'tan kapanir
        op, hi, lo, cl = o[j] + shift, h[j] + shift, low[j] + shift, c[j] + shift
        if sign > 0 and lo <= stop:
            return j, min(op, stop), "stop"
        if sign < 0 and hi >= stop:
            return j, max(op, stop), "stop"
        if target is not None:
            if sign > 0 and hi >= target:
                return j, max(op, target), "target"
            if sign < 0 and lo <= target:
                return j, min(op, target), "target"
        if exits is not None and exits[j]:
            return j, cl, "signal"
        if spec.max_bars is not None and j - i >= spec.max_bars:
            return j, cl, "time"
        if spec.trail is not None and spec.trail[j] > 0:
            best = max(best, hi) if sign > 0 else min(best, lo)
            level = best - sign * spec.trail[j]
            stop = max(stop, level) if sign > 0 else min(stop, level)
    return None, None, "open"


# ---------------------------------------------------------------- filtreler ve boyutlandirma
def daily_index(series: Series, daily: Series) -> np.ndarray:
    """Her mumun kapanisinda KAPANMIS son D1 mumunun indeksi (-1: yok)."""
    closes = daily.time + 86400
    return np.searchsorted(closes, series.time + series.seconds, side="right") - 1


def filters(series: Series, daily: Series, kind: str, spread_ratio: np.ndarray | None) -> dict:
    """Filtre -> (AL izni, SAT izni). F3 D1 stratejilerinde anlamsizdir (giris gece yarisi): None doner."""
    n = len(series)
    yes = np.ones(n, bool)
    di = daily_index(series, daily)
    ok = di >= 0
    sma200 = ind.sma(daily.close, 200)
    dclose = np.where(ok, daily.close[np.clip(di, 0, None)], np.nan)
    dsma = np.where(ok, sma200[np.clip(di, 0, None)], np.nan)
    f1 = (dclose > dsma, dclose < dsma)
    a14, a100 = ind.atr(series.high, series.low, series.close, 14), ind.atr(series.high, series.low, series.close, 100)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = a14 / a100
    regime = (ratio >= 0.7) & (ratio <= 1.5)
    out = {"F0": (yes, yes), "F1": f1, "F2": (regime, regime)}
    if series.tf == "D1":
        out["F3"] = None
    else:
        session = np.array([in_session(int(x) + series.seconds, kind) for x in series.time])
        out["F3"] = (session, session)
    if spread_ratio is not None:
        calm = ~(spread_ratio > 1.5)
        out["F4"] = (calm, calm)
    else:
        out["F4"] = (yes, yes)
    return out


def in_session(moment: int, kind: str) -> bool:
    """F3: FX / metal: Londra 08-17 (Londra saati) ya da New York 08-17 (NY saati); endeks: NY nakit 09:30-16:00;
    kripto: filtresiz."""
    if kind == "crypto":
        return True
    when = datetime.fromtimestamp(moment, timezone.utc)
    ny = when.astimezone(NEW_YORK)
    if kind == "index":
        minutes = ny.hour * 60 + ny.minute
        return ny.weekday() < 5 and 570 <= minutes < 960
    london = when.astimezone(LONDON)
    return 8 <= london.hour < 17 or 8 <= ny.hour < 17


def p2_weights(series: Series, daily: Series) -> np.ndarray:
    """P2 agirligi = min(1, sigma_ref / sigma_20); sigma_20: son 20 kapanmis D1'in log getiri std'si; sigma_ref: onceki
    250 D1'de sigma_20 medyani. Veri yetmezse 1."""
    r = np.diff(np.log(daily.close), prepend=np.nan)
    s20 = np.full(len(daily), np.nan)
    for k in range(20, len(daily)):
        s20[k] = np.std(r[k - 19:k + 1])
    ref = np.full(len(daily), np.nan)
    for k in range(270, len(daily)):
        ref[k] = np.nanmedian(s20[k - 250:k])
    with np.errstate(divide="ignore", invalid="ignore"):
        w = np.minimum(1.0, ref / s20)
    w = np.where(np.isfinite(w) & (w > 0), w, 1.0)
    di = daily_index(series, daily)
    return np.where(di >= 0, w[np.clip(di, 0, None)], 1.0)


# ---------------------------------------------------------------- olcum
def metrics(trades: list[Trade], risk_pct: float = RISK_PCT) -> dict:
    closed = sorted((x for x in trades if x.r is not None), key=lambda x: x.exit_time)
    wins = float(sum(x.r * x.weight for x in closed if x.r > 0))
    losses = float(-sum(x.r * x.weight for x in closed if x.r < 0))
    balance = peak = START_BALANCE
    dd = 0.0
    for x in closed:
        balance *= 1.0 + risk_pct / 100.0 * x.r * x.weight
        peak = max(peak, balance)
        dd = max(dd, (peak - balance) / peak * 100.0)
    return {"trades": len(closed), "net_r": round(wins - losses, 3), "wins": sum(1 for x in closed if x.r > 0),
            "pf": round(wins / losses, 3) if losses > 0 else (None if wins == 0 else 99.0),
            "max_dd_pct": round(float(dd), 2), "end_balance": round(float(balance), 1)}


def add_months(moment: int, k: int) -> int:
    day = datetime.fromtimestamp(moment, timezone.utc)
    month = day.month - 1 + k
    year, month = day.year + month // 12, month % 12 + 1
    return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())


def timeline(end: int) -> dict:
    """T = verinin son tam gunu (ayin basina yuvarlanir): kasa [T-12 ay, T], bolge [T-60, T-12]."""
    t = add_months(end, 0)  # ay basi (T'nin icinde bulundugu ayin basi)
    holdout = add_months(t, -HOLDOUT_MONTHS)
    region = add_months(t, -REGION_MONTHS)
    windows = []
    for k in range(WINDOWS):
        s = add_months(region, TEST_MONTHS * k)
        windows.append({"k": k, "select": (s, add_months(s, SELECT_MONTHS)),
                        "test": (add_months(s, SELECT_MONTHS), add_months(s, SELECT_MONTHS + TEST_MONTHS))})
    return {"end": t, "holdout": (holdout, t), "region": (region, holdout), "windows": windows}


def _in(trades, span):
    return [x for x in trades if span[0] <= x.entry_time < span[1]]


def selected(m: dict, min_trades: int | None = None) -> bool:
    return bool(m["trades"] >= (SELECT["min_trades"] if min_trades is None else min_trades) and m["pf"] is not None and m["pf"] >= SELECT["min_pf"]
                and m["max_dd_pct"] <= SELECT["max_dd_pct"])


def walk_forward(trades: list[Trade], plan: dict, data_from: int, risk_pct: float = RISK_PCT,
                 gaps: list[int] | None = None, select_min: int | None = None) -> dict:
    """Pencere sonuclari ve gecme karari. `data_from`: sembolun verisinin (isinma sonrasi) basladigi an. `gaps`:
    verisi indirilemeyen aylarin baslangiclari; boyle bir ay iceren pencere kullanilmaz."""
    rows, counted = [], []
    for w in plan["windows"]:
        holed = any(w["select"][0] <= g < w["test"][1] for g in gaps or [])
        if data_from > w["select"][0] or holed:
            rows.append({"k": w["k"], "usable": False})
            continue
        sel = metrics(_in(trades, w["select"]), risk_pct)
        test_trades = _in(trades, w["test"])
        test = metrics(test_trades, risk_pct)
        pick = selected(sel, select_min)
        rows.append({"k": w["k"], "usable": True, "selected": pick, "select": sel, "test": test})
        if pick:
            counted.append((test_trades, test))
    total = metrics([x for group, _ in counted for x in group], risk_pct)
    positive = sum(1 for _, m in counted if m["net_r"] > 0)
    share = positive / len(counted) if counted else 0.0
    passed = bool(len(counted) >= PASS["min_windows"] and total["trades"] >= PASS["min_trades"]
              and total["pf"] is not None and total["pf"] >= PASS["min_pf"] and share >= PASS["min_positive_share"])
    return {"windows": rows, "counted": len(counted), "oos": total, "positive_share": round(share, 3), "passed": passed}


def monkey(series: Series, spec: Spec, costs: Costs, real: list[tuple[int, int]], plan: dict, data_from: int,
           reps: int = 200, seed: int = 1, gaps: list[int] | None = None, select_min: int | None = None,
           keep: bool = False) -> dict:
    """Ayni sayida ve ayni AL/SAT oraninda rastgele girisler, ayni cikis kurali ve maliyetle. Gercek sinyallerin
    PF'si rastgele dagilimin hangi yuzdeligide; rastgele tekrarlarin kacta kaci gecme kuralini sagliyor."""
    region = plan["region"]
    lo = max(int(np.searchsorted(series.time, max(region[0], data_from))), 1)
    hi = int(np.searchsorted(series.time, region[1]))
    eligible = np.arange(lo, hi)
    eligible = eligible[np.isfinite(spec.stop[eligible]) & (spec.stop[eligible] > 0)]
    count = sum(1 for i, _ in real if lo <= i < hi)
    longs = sum(1 for i, s in real if lo <= i < hi and s > 0)
    if count < 5 or len(eligible) < count:
        return {"reps": 0}
    rng = np.random.default_rng(seed)
    pfs, passes, kept = [], 0, []
    for _ in range(reps):
        picks = np.sort(rng.choice(eligible, size=count, replace=False))
        sides = np.array([1] * longs + [-1] * (count - longs))
        rng.shuffle(sides)
        trades, _ = simulate(series, spec, costs, entries=list(zip(picks.tolist(), sides.tolist())))
        m = metrics(_in(trades, region))
        pfs.append(m["pf"] if m["pf"] is not None else 0.0)
        passes += walk_forward(trades, plan, data_from, gaps=gaps, select_min=select_min)["passed"]
        if keep:  # sepet icin: ayni tekrar sirasiyla sembollerin rastgele islemleri birlestirilir
            kept.append([[t.entry_time, t.exit_time, t.side, round(t.r, 4)] for t in trades if t.r is not None])
    out = {"reps": reps, "pf_median": round(float(np.median(pfs)), 3), "pass_rate": round(passes / reps, 4),
           "pfs": pfs}
    if keep:
        out["trades"] = kept
    return out
