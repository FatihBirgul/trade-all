"""Faz 5 portfoyu: gecen (sonra onaylanan) eslesmelerin islemleri birlesik portfoyde.

Kurallar (on kayit): en cok 3 acik islem, sembol basina 1, para birimi yonu basina 2. %0,5 ve %1 risk ile 2000 USC
egrisi; aylik / uc aylik sonuc; en uzun dusus suresi; eslesmeler arasi aylik R korelasyonu.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

START_BALANCE = 2000.0
MAX_OPEN, PER_CURRENCY_SIDE = 3, 2
INDEX_CURRENCY = {"US30": "USD", "US500": "USD", "USTEC": "USD"}


def legs(symbol: str, side: int) -> tuple:
    if symbol in INDEX_CURRENCY:
        base, quote = symbol, INDEX_CURRENCY[symbol]
    else:
        base, quote = symbol[:3], symbol[3:6]
    long, short = ("long", "short") if side > 0 else ("short", "long")
    return (base, long), (quote, short)


def accept(trades: list[dict]) -> tuple[list[dict], int]:
    """Giris sirasiyla portfoy kurallari. trade: {symbol, key, entry, exit, side, r, w}."""
    book, accepted, rejected = [], [], 0
    for t in sorted(trades, key=lambda x: (x["entry"], x["symbol"], x["key"])):
        book = [b for b in book if b["exit"] > t["entry"]]
        exposure: dict = {}
        for b in book:
            for leg in legs(b["symbol"], b["side"]):
                exposure[leg] = exposure.get(leg, 0) + 1
        if (len(book) >= MAX_OPEN or any(b["symbol"] == t["symbol"] for b in book)
                or any(exposure.get(leg, 0) >= PER_CURRENCY_SIDE for leg in legs(t["symbol"], t["side"]))):
            rejected += 1
            continue
        book.append(t)
        accepted.append(t)
    return accepted, rejected


def curve(trades: list[dict], risk_pct: float) -> dict:
    balance = peak = START_BALANCE
    dd, worst_days, peak_at = 0.0, 0.0, None
    points = []
    for t in sorted(trades, key=lambda x: x["exit"]):
        balance *= 1.0 + risk_pct / 100.0 * t["r"] * t["w"]
        if balance >= peak:
            if peak_at is not None:
                worst_days = max(worst_days, (t["exit"] - peak_at) / 86400.0)
            peak, peak_at = balance, t["exit"]
        else:
            peak_at = peak_at if peak_at is not None else t["exit"]
            dd = max(dd, (peak - balance) / peak * 100.0)
        points.append([t["exit"], round(balance, 1)])
    if peak_at is not None and points and balance < peak:
        worst_days = max(worst_days, (points[-1][0] - peak_at) / 86400.0)
    step = max(1, len(points) // 60)
    return {"end_balance": round(balance, 1), "max_dd_pct": round(dd, 2), "longest_dd_days": round(worst_days, 1),
            "curve": points[::step] + (points[-1:] if points and (len(points) - 1) % step else [])}


def periods(trades: list[dict], fmt) -> dict:
    out: dict = {}
    for t in trades:
        key = fmt(datetime.fromtimestamp(t["exit"], timezone.utc))
        out[key] = round(out.get(key, 0.0) + t["r"] * t["w"], 3)
    return dict(sorted(out.items()))


def correlation(trades: list[dict]) -> dict:
    """Eslesmeler arasi aylik R korelasyonu (en az 6 ortak ay)."""
    monthly: dict = {}
    for t in trades:
        month = datetime.fromtimestamp(t["exit"], timezone.utc).strftime("%Y-%m")
        monthly.setdefault(t["key"], {}).setdefault(month, 0.0)
        monthly[t["key"]][month] += t["r"] * t["w"]
    keys = sorted(monthly)
    months = sorted({m for v in monthly.values() for m in v})
    out = {}
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            x = np.array([monthly[a].get(m, 0.0) for m in months])
            y = np.array([monthly[b].get(m, 0.0) for m in months])
            if len(months) >= 6 and x.std() > 0 and y.std() > 0:
                out[f"{a} ~ {b}"] = round(float(np.corrcoef(x, y)[0, 1]), 3)
    return out


def build(passed: list[dict]) -> dict:
    trades = []
    for item in passed:
        key = f"{item['symbol']}|{item['strategy']}|{item['variant']}"
        for entry, exit_, side, r, w in item.get("oos_trades", []):
            trades.append({"symbol": item["symbol"], "key": key, "entry": entry, "exit": exit_, "side": side, "r": r,
                           "w": w})
    accepted, rejected = accept(trades)
    return {"trades": len(accepted), "rejected": rejected, "net_r": round(sum(t["r"] * t["w"] for t in accepted), 3),
            "risk": {f"{p}%": {k: v for k, v in curve(accepted, p).items() if k != "curve"} for p in (0.5, 1.0)},
            "curves": {f"{p}%": curve(accepted, p)["curve"] for p in (0.5, 1.0)},
            "monthly_r": periods(accepted, lambda d: d.strftime("%Y-%m")),
            "quarterly_r": periods(accepted, lambda d: f"{d.year}-Q{(d.month - 1) // 3 + 1}"),
            "correlation": correlation(accepted)}
