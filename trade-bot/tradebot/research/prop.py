"""Prop firma sinavi benzetimi (Funded Trader Markets 2-Step Plus kurallari; kullanicinin ekran goruntulerinden).

Sinav: Faz 1 hedef %8, Faz 2 hedef %5 (her faz baslangic bakiyesine gore; faz 2'de bakiye sifirlanir). Toplam kayip
STATIK %10 (baslangicin %90'i alt sinir). Gunluk kayip %4: her gun 17:00 New York'ta bakiye ve equity'den buyugu
alinir, ondan baslangicin %4'u dusulur; gun icinde equity bu seviyeye degerse ihlal. Acik zarar siniri yok. 30 gun
islemsiz kalmak ihlal. Swap yok; komisyon (acilis + kapanis, her biri) FX/metal %0,0025, endeks %0,005, kripto %0,03.
Fonlu asama: ayrica ACIK ZARAR SINIRI %1 (acik islemlerin toplam anlik zarari hesabin %1'ine ulasirsa hepsi kapanir,
kar payi kalici duser 70 -> 50 -> 40 -> 30 -> 20).

Bakis-one yok: islemler `legs` ile gelir; her bacak yalnizca kendi penceresinde (walk-forward test penceresi k'de
secim penceresi k'nin sectigi eslesme; kasa doneminde onceden tanimli 34 cift) giris yapar. Equity saatlik (H1) izlenir;
bir saatin icinde acik islemlerin en kotu noktalari AYNI ANDA olusmus sayilir (kotumser).
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np

H = 3600
NEW_YORK = ZoneInfo("America/New_York")
COMMISSION = {"forex": 0.0025 / 100, "metal": 0.0025 / 100, "index": 0.005 / 100, "crypto": 0.03 / 100}
SHARES = (0.70, 0.50, 0.40, 0.30, 0.20)
TARGETS = (0.08, 0.05)
TOTAL_LOSS, DAILY_LOSS, INACTIVE_DAYS, FLOATING = 0.10, 0.04, 30, 0.01
MAX_OPEN = 3


@dataclass
class PTrade:
    symbol: str
    entry: int  # ilk H1 mumunun acilis ani (= giris mumunun kapanisi)
    exit: int  # cikis mumunun kapanisi
    r: float  # spread dahil, komisyon haric
    comm_r: float  # komisyon (acilis + kapanis) R cinsinden
    weight: float  # P2 boyutlandirma carpani (P1: 1)
    worst: np.ndarray  # her H1 mumunda en kotu anlik R
    close: np.ndarray  # her H1 mumunun kapanisinda anlik R


@lru_cache(maxsize=None)
def _ny_offset(day: int) -> int:
    return int(datetime.fromtimestamp(day * 86400 + 43200, timezone.utc).astimezone(NEW_YORK).utcoffset().total_seconds())


def trading_day(moment: int) -> int:
    """17:00 New York'ta degisen islem gunu numarasi."""
    local = moment + _ny_offset(moment // 86400)
    return (local - 17 * H) // 86400


def risk_fixed(pct):
    return lambda drawdown: pct


def risk_adaptive(drawdown: float) -> float:
    """%1 basla; baslangica gore -%4'te %0,5; -%7'de %0,25."""
    return 0.0025 if drawdown <= -0.07 else 0.005 if drawdown <= -0.04 else 0.01


def _phase(trades, entries, start, target, risk, stop_at=None, limit_end=None):
    """Tek faz. -> (sonuc, an): sonuc 'pass' | 'total' | 'daily' | 'inactive' | 'open' (veri bitti)."""
    balance, base = 1.0, 1.0
    open_, last_trade = [], start
    k = bisect.bisect_left(entries, start)
    h = start - start % H
    end = limit_end or (trades[-1].exit + H if trades else start)
    day = trading_day(h)
    day_ref = 1.0
    halted_day = None
    while h < end:
        if trading_day(h) != day:  # 17:00 NY: yeni gun referansi (bakiye ve equity'den buyugu)
            day = trading_day(h)
            equity = balance + sum(t.close[min(i - 1, len(t.close) - 1)] * m for t, i, m in open_ if i > 0)
            day_ref = max(balance, equity)
        while k < len(trades) and trades[k].entry <= h:
            t = trades[k]
            k += 1
            if t.entry < h or len(open_) >= MAX_OPEN or halted_day == day or any(o[0].symbol == t.symbol for o in open_):
                continue
            money = risk(balance - base) * t.weight
            balance -= t.comm_r * money / 2  # acilis komisyonu
            open_.append([t, 0, money])
            last_trade = h
        if not open_:
            if h - last_trade >= INACTIVE_DAYS * 86400:
                return "inactive", h
            nxt = trades[k].entry if k < len(trades) else end
            nxt = min(nxt, last_trade + INACTIVE_DAYS * 86400)  # islemsizlik siniri atlanmasin
            h = max(h + H, nxt - nxt % H)
            continue
        worst = balance + sum(t.worst[min(i, len(t.worst) - 1)] * m for t, i, m in open_)
        if worst <= base * (1 - TOTAL_LOSS):
            return "total", h
        if worst <= day_ref - DAILY_LOSS * base:
            return "daily", h
        if stop_at is not None and worst <= day_ref - stop_at * base:  # bot kendini durdurur: hepsini kapat
            balance += sum(t.worst[min(i, len(t.worst) - 1)] * m - t.comm_r * m / 2 for t, i, m in open_)
            open_, halted_day = [], day
            h += H
            continue
        closed = []
        for item in open_:
            t, i, m = item
            if t.exit <= h + H:
                balance += t.r * m - t.comm_r * m / 2
                closed.append(item)
            else:
                item[1] = i + 1
        open_ = [o for o in open_ if o not in closed]
        equity = balance + sum(t.close[min(i - 1, len(t.close) - 1)] * m for t, i, m in open_ if i > 0)
        if equity >= base * (1 + target):
            return "pass", h + H
        if h - last_trade >= INACTIVE_DAYS * 86400 and not open_:
            return "inactive", h
        h += H
    return "open", h


def exam(trades, entries, start, risk, stop_at=None, end=None) -> dict:
    r1, t1 = _phase(trades, entries, start, TARGETS[0], risk, stop_at, end)
    if r1 != "pass":
        return {"result": r1, "phase": 1}
    r2, t2 = _phase(trades, entries, t1, TARGETS[1], risk, stop_at, end)
    return {"result": "pass" if r2 == "pass" else r2, "phase": 2 if r2 != "pass" else 3,
            "days1": (t1 - start) / 86400, "days": (t2 - start) / 86400 if r2 == "pass" else None}


def funded(trades, entries, start, end, risk_pct=0.003) -> dict:
    """Fonlu hesap: %0,3 x en cok 3 (toplam acik risk %0,9). Aylik getiri, %1 acik zarar ihlali, odeme (ay sonunda
    baslangic ustu kar cekilir; zarar devreder). Gunluk %4 / toplam %10 ihlalinde hesap kaybedilir ve yeniden baslar."""
    balance, open_, k = 1.0, [], bisect.bisect_left(entries, start)
    h = start - start % H
    day, day_ref = trading_day(h), 1.0
    month = datetime.fromtimestamp(h, timezone.utc).strftime("%Y-%m")
    month_start, monthly, share_i, payouts, floating_hits, lost = 1.0, {}, 0, 0.0, 0, 0
    while h < end:
        now_month = datetime.fromtimestamp(h, timezone.utc).strftime("%Y-%m")
        if now_month != month:
            monthly[month] = round((balance - month_start) * 100, 3)
            if balance > 1.0 and not open_:
                payouts += (balance - 1.0) * SHARES[share_i]
                balance = 1.0
            month, month_start = now_month, balance
        if trading_day(h) != day:
            day = trading_day(h)
            day_ref = max(balance, balance + sum(t.close[min(i - 1, len(t.close) - 1)] * m for t, i, m in open_ if i > 0))
        while k < len(trades) and trades[k].entry <= h:
            t = trades[k]
            k += 1
            if t.entry < h or len(open_) >= MAX_OPEN or any(o[0].symbol == t.symbol for o in open_):
                continue
            money = risk_pct * t.weight
            balance -= t.comm_r * money / 2
            open_.append([t, 0, money])
        if not open_:
            nxt = trades[k].entry if k < len(trades) else end
            h = max(h + H, nxt - nxt % H)
            continue
        floating = sum(t.worst[min(i, len(t.worst) - 1)] * m for t, i, m in open_)
        if balance + floating <= 1.0 - TOTAL_LOSS or balance + floating <= day_ref - DAILY_LOSS:
            lost += 1
            balance, open_, day_ref = 1.0, [], 1.0
            h += H
            continue
        if floating <= -FLOATING:  # acik zarar siniri: hepsi kapanir, pay kalici duser
            balance += sum(-t.comm_r * m / 2 for t, i, m in open_) + floating
            open_, floating_hits = [], floating_hits + 1
            share_i = min(share_i + 1, len(SHARES) - 1)
            h += H
            continue
        closed = []
        for item in open_:
            t, i, m = item
            if t.exit <= h + H:
                balance += t.r * m - t.comm_r * m / 2
                closed.append(item)
            else:
                item[1] = i + 1
        open_ = [o for o in open_ if o not in closed]
        h += H
    years = max((end - start) / (365.25 * 86400), 1e-9)
    values = list(monthly.values())
    return {"months": len(values), "monthly_pct": monthly,
            "monthly_median": round(float(np.median(values)), 3) if values else None,
            "monthly_p25": round(float(np.percentile(values, 25)), 3) if values else None,
            "monthly_p75": round(float(np.percentile(values, 75)), 3) if values else None,
            "negative_months": sum(1 for v in values if v < 0), "floating_breaches": floating_hits,
            "accounts_lost": lost, "final_share": SHARES[share_i],
            "payout_per_year_pct": round(payouts / years * 100, 3)}


VARIANTS = {"%0,5": (risk_fixed(0.005), None), "%0,75": (risk_fixed(0.0075), None), "%1": (risk_fixed(0.01), None),
            "uyarlanan": (risk_adaptive, None), "%1 + %3'te dur": (risk_fixed(0.01), 0.03)}


def summarize(results: list[dict]) -> dict:
    n = len(results)
    if not n:
        return {"starts": 0}
    p1 = sum(1 for r in results if r["phase"] >= 2 or r["result"] == "pass")
    passed = [r for r in results if r["result"] == "pass"]
    days = sorted(r["days"] for r in passed)
    reasons: dict = {}
    for r in results:
        if r["result"] != "pass":
            reasons[r["result"]] = reasons.get(r["result"], 0) + 1
    return {"starts": n, "phase1_pct": round(p1 / n * 100, 1), "phase2_pct": round(len(passed) / p1 * 100, 1) if p1 else None,
            "pass_pct": round(len(passed) / n * 100, 1),
            "days_median": round(float(np.median(days)), 1) if days else None,
            "days_p75": round(float(np.percentile(days, 75)), 1) if days else None,
            "fail_reasons_pct": {k: round(v / n * 100, 1) for k, v in sorted(reasons.items())}}


def run_all(trades: list[PTrade], windows: list[tuple[int, int]], holdout: tuple[int, int], end: int) -> dict:
    trades = sorted(trades, key=lambda t: (t.entry, t.symbol))
    entries = [t.entry for t in trades]
    first = windows[0][0] if windows else holdout[0]
    starts = list(range(first, end - 7 * 86400, 7 * 86400))
    out = {"starts_from": first, "end": end, "variants": {}}
    for name, (risk, stop_at) in VARIANTS.items():
        res = [dict(exam(trades, entries, s, risk, stop_at, end), start=s) for s in starts]
        out["variants"][name] = {"all": summarize(res), "holdout": summarize([r for r in res if r["start"] >= holdout[0]]),
                                 "before_holdout": summarize([r for r in res if r["start"] < holdout[0]])}
    out["funded"] = {"all": funded(trades, entries, first, end), "holdout": funded(trades, entries, holdout[0], end)}
    return out


def report(out: dict) -> str:
    lines = ["== PROP SINAV (2-Step Plus) =="]
    for name, v in out["variants"].items():
        for part in ("all", "before_holdout", "holdout"):
            s = v[part]
            if not s.get("starts"):
                continue
            lines.append(f"  {name:16s} {part:15s} baslangic={s['starts']:3d} faz1=%{s['phase1_pct']} faz2=%{s['phase2_pct']} "
                         f"toplam=%{s['pass_pct']} gun(medyan/p75)={s['days_median']}/{s['days_p75']} basarisiz={s['fail_reasons_pct']}")
    for part, f in out["funded"].items():
        lines.append(f"  FONLU {part:8s} ay={f['months']} aylik medyan=%{f['monthly_median']} (p25 %{f['monthly_p25']}, "
                     f"p75 %{f['monthly_p75']}) eksi ay={f['negative_months']} acik-zarar ihlali={f['floating_breaches']} "
                     f"hesap kaybi={f['accounts_lost']} son pay={f['final_share']} yillik odeme=%{f['payout_per_year_pct']} "
                     f"(10K: ${round(f['payout_per_year_pct'] * 100)}, 25K: ${round(f['payout_per_year_pct'] * 250)})")
    return "\n".join(lines)
