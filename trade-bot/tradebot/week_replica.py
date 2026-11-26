"""WEEK TRADE'in 2 yillik yeniden uretimi: `bt.py`nin portfoy dongusu, bizim (Exness) mumlarimizla.

Iki kip:
- "bt": kaynak kodun ayni varsayimlari (sabit spread tablosu yalnizca giriste, iz suren stopun ATR'si giris mumunu
  da icerir, stop her zaman stop fiyatindan dolar, veri sonunda acik kalanlar anlik fiyatla sayilir). Amac, kaynak
  islem listesini (giris zamani / sembol / yon) yeniden uretip uretmedigimizi gormek.
- "fixed": duzeltilmis olcum. (a) gercek Exness spread'i: AL ask'tan acilir, SAT ask'tan kapanir; (b) ATR giristen
  once kapanmis mumdan; mum stopun otesinde ACILIRSA acilis fiyatindan cikilir (bosluk); (d) acik kalanlar toplam
  disinda. (c) gecelik faiz (swap) oranlari bu API'de yok: tasinan gece sayisi raporlanir ve yillik orana gore
  duyarlilik verilir.
Sinyaller golge stratejiyle ayni fonksiyondan gelir (`week_trade.signal`).
"""

from __future__ import annotations

import bisect
import json
from pathlib import Path

from .signals.modules.strategies import week_trade
from .signals.modules.strategies.v13 import Frame

SYMBOLS = ("BTCUSD", "ETHUSD", "XAUUSD", "EURUSD", "USDCHF", "GBPAUD")
BT_SPREAD = {"BTCUSD": 20.0, "ETHUSD": 2.0, "XAUUSD": 0.3, "EURUSD": 0.0001, "USDCHF": 0.00015, "GBPAUD": 0.0003}
GROUP = {"BTCUSD": "kripto", "ETHUSD": "kripto", "EURUSD": "usd", "XAUUSD": "usd", "USDCHF": "usd", "GBPAUD": "gbpaud"}
START = 1734220800  # 2024-12-15 00:00 UTC (kaynak testin baslangici)
MAX_PER_DAY = 2
WINDOW_H4, WINDOW_D1 = 300, 300
H4, DAY = 14400, 86400
TIMEOUT = 7 * DAY
REPORT_VERSION = 2  # rapor bicimi degisince ileri testin A asamasi onbellegi yenilenir
SWAP_RATES = (0.03, 0.06)  # duyarlilik: pozisyon buyuklugunun yillik orani olarak gecelik faiz (aleyhte)
# Hesap swap'siz (kullanici Exness'in resmi listesinden teyit etti, 2026-11-26: Turkiye otomatik swap-free
# listesinde; butun enstrumanlarda swap 0). ANA SENARYO swap 0'dir (= ozet toplamlar). Asagidaki duyarlilik
# yalnizca DIPNOTTUR: broker bu statuyu geri alirsa ne olacagini gosterir (`crosses`: yalnizca caprazlarda faiz,
# `everything`: hepsinde). Gercek durum botun olcumuyle izlenir (ozet `swap_observed`, `swap_charged` bildirimi).
SWAP_FREE = frozenset({"BTCUSD", "ETHUSD", "XAUUSD", "EURUSD", "USDCHF"})
REFERENCE = Path(__file__).parent / "data" / "week_reference.json"


def signals(symbol: str, h4: list[dict], d1: list[dict], start: float, soft: bool) -> list[tuple]:
    """(giris zamani, sembol, yon isareti, uzama, stop mesafesi, kapanmis 4H ATR) listesi."""
    out = []
    for index in range(len(h4) - 1):  # son mumdan sonra giris mumu yok
        if h4[index]["time"] < start:
            continue
        found = week_trade.signal(h4[max(0, index - WINDOW_H4 + 1):index + 1],
                                  [bar for bar in d1 if bar["time"] <= h4[index]["time"] + H4][-WINDOW_D1:])
        if found is None or (found["stretch"] and not soft):
            continue
        out.append((h4[index]["time"] + H4, symbol, 1 if found["side"] == "BUY" else -1, found["stretch"],
                    found["stop_distance"], found["atr4"]))
    return out


def simulate(sign: int, entry: float, risk: float, atr4: float, at: float, future: list[dict], mode: str,
             spread_at) -> dict:
    """`bt.py`nin cikis dongusu (4H mumlariyla). `future[0]` giris mumudur."""
    stop, best = entry - sign * risk, 0.0
    for bar in future:
        shift = spread_at(bar["time"]) if (mode == "fixed" and sign < 0) else 0.0  # SAT ask'tan kapanir
        low, high, opened = bar["low"] + shift, bar["high"] + shift, bar["open"] + shift
        if (low <= stop) if sign > 0 else (high >= stop):
            price = stop
            if mode == "fixed" and bar["time"] > at and (opened - stop) * sign < 0:
                price = opened  # mum stopun otesinde acildi: stop fiyatindan degil acilistan dolar
            return {"r": (price - entry) * sign / risk, "exit": bar["time"], "why": "stop"}
        favour = ((high - entry) if sign > 0 else (entry - low)) / risk
        best = max(best, favour)
        if best >= 1:
            stop = max(stop * sign, entry * sign) * sign
        if best >= 2:
            stop = max(stop * sign, (entry + sign * risk) * sign) * sign
        if best > 2:
            stop = max(stop * sign, (entry + sign * best * risk - sign * 2 * atr4) * sign) * sign
        if bar["time"] - at >= TIMEOUT and best < 1:
            return {"r": (bar["close"] + shift - entry) * sign / risk, "exit": bar["time"], "why": "time"}
    last = future[-1]
    shift = spread_at(last["time"]) if (mode == "fixed" and sign < 0) else 0.0
    return {"r": (last["close"] + shift - entry) * sign / risk, "exit": last["time"] + H4, "why": "open"}


def all_signals(bars: dict, start: float = START) -> list[tuple]:
    """Butun sembollerin (yumusak surum) sinyalleri; siki surum bunlardan uzamis olanlar cikarilarak elde edilir."""
    found: list[tuple] = []
    for symbol in SYMBOLS:
        if bars.get(symbol, {}).get("H4"):
            found += signals(symbol, bars[symbol]["H4"], bars[symbol].get("D1") or [], start, True)
    return found


def run(bars: dict, *, soft: bool, mode: str, spread=None, start: float = START,
        found: list[tuple] | None = None) -> list[dict]:
    """`bars`: sembol -> {"H4": [...], "D1": [...]}. `spread(sembol, an)`: "fixed" kipinde gercek spread."""
    found = [item for item in (all_signals(bars, start) if found is None else found) if soft or not item[3]]
    frames: dict[str, tuple] = {}
    for symbol in SYMBOLS:
        if bars.get(symbol, {}).get("H4"):
            h4 = bars[symbol]["H4"]
            frames[symbol] = (h4, [bar["time"] for bar in h4], week_trade.simple_atr(Frame(h4)))
    found.sort(key=lambda item: item[:4])
    open_until: dict[str, float] = {}
    per_day: dict[int, int] = {}
    trades: list[dict] = []
    for at, symbol, sign, stretch, risk, atr_closed in found:
        group, day = GROUP[symbol], int(at // DAY)
        if open_until.get(group, 0) > at or per_day.get(day, 0) >= MAX_PER_DAY:
            continue
        h4, times, atr_all = frames[symbol]
        first = bisect.bisect_left(times, at)
        future = h4[first:]
        if len(future) < 2:
            continue
        if mode == "bt":
            entry = future[0]["open"] + sign * BT_SPREAD[symbol]
            atr4 = atr_all[bisect.bisect_right(times, at) - 1]  # kaynak: giris mumu dahil
            cost = BT_SPREAD[symbol]
        else:
            cost = float(spread(symbol, at))
            entry = future[0]["open"] + (cost if sign > 0 else 0.0)
            atr4 = atr_closed
        result = simulate(sign, entry, risk, atr4, at, future, mode, lambda moment: float(spread(symbol, moment))
                          if spread else 0.0)
        open_until[group] = result["exit"]
        per_day[day] = per_day.get(day, 0) + 1
        nights = max(0, int(result["exit"] // DAY) - int(at // DAY))
        trades.append({"at": at, "symbol": symbol, "side": "BUY" if sign > 0 else "SELL", "stretch": stretch,
                       "r": result["r"], "exit": result["exit"], "why": result["why"], "nights": nights,
                       "cost_r": cost / risk, "night_r": entry / 365.0 / risk})
    return trades


def stats(rows: list[dict]) -> dict:
    values = [row["r"] for row in rows]
    gains, losses = sum(v for v in values if v > 0), -sum(v for v in values if v < 0)
    peak = total = drawdown = 0.0
    for value in values:
        total += value
        peak = max(peak, total)
        drawdown = min(drawdown, total - peak)
    costs = sorted(row["cost_r"] for row in rows)
    return {"trades": len(values), "win_pct": round(100.0 * sum(1 for v in values if v > 0) / len(values), 1) if values else None,
            "net_r": round(sum(values), 2), "pf": round(gains / losses, 2) if losses > 0 else None,
            "max_dd": round(drawdown, 2), "cost_r_median": round(costs[len(costs) // 2], 4) if costs else None,
            "nights": sum(row["nights"] for row in rows)}


def summarize(trades: list[dict], *, exclude_open: bool) -> dict:
    rows = [t for t in trades if not (exclude_open and t["why"] == "open")]
    middle = START + 365 * DAY
    out = {"all": stats(rows), "ex_xau": stats([t for t in rows if t["symbol"] != "XAUUSD"]),
           "year1": stats([t for t in rows if t["at"] < middle]), "year2": stats([t for t in rows if t["at"] >= middle]),
           "stretched": stats([t for t in rows if t["stretch"]]),
           "open": {"trades": sum(1 for t in trades if t["why"] == "open"),
                    "r": round(sum(t["r"] for t in trades if t["why"] == "open"), 2)},
           "exits": {why: sum(1 for t in rows if t["why"] == why) for why in ("stop", "time", "open")},
           "by_symbol": {symbol: stats([t for t in rows if t["symbol"] == symbol]) for symbol in SYMBOLS}}
    # Gecelik faiz duyarliligi: her gece, pozisyon buyuklugunun yillik `oran`i kadar aleyhte maliyet varsayilirsa.
    def net(rate: float, only_crosses: bool, without_gold: bool) -> float:
        return round(sum(t["r"] - (0.0 if only_crosses and t["symbol"] in SWAP_FREE else t["nights"] * t["night_r"] * rate)
                         for t in rows if not (without_gold and t["symbol"] == "XAUUSD")), 2)

    # Ana senaryo: swap 0 (= yukaridaki toplamlar). Ikinci senaryo: yalnizca caprazlarda faiz. Ucuncu (en kotu):
    # butun sembollerde faiz.
    out["swap"] = {"crosses": {str(rate): {"all": net(rate, True, False), "ex_xau": net(rate, True, True)}
                               for rate in SWAP_RATES},
                   "everything": {str(rate): {"all": net(rate, False, False), "ex_xau": net(rate, False, True)}
                                  for rate in SWAP_RATES},
                   "cross_nights": sum(t["nights"] for t in rows if t["symbol"] not in SWAP_FREE)}
    return out


def compare(ours: list[dict], reference: list[list], until: float) -> dict:
    """Kaynak islem listesiyle karsilastirma: ayni sembol + ayni yon, giris zamani ayni / 1 gun icinde."""
    theirs = [row for row in reference if row[0] < until]
    mine = [t for t in ours if t["at"] < until]
    left = [(t["at"], t["symbol"], t["side"]) for t in mine]
    exact = near = 0
    r_pairs = []
    for at, symbol, side, r, *_ in theirs:
        hit = next((item for item in left if item[1] == symbol and item[2] == side and item[0] == at), None)
        kind = "exact"
        if hit is None:
            hit = min((item for item in left if item[1] == symbol and item[2] == side and abs(item[0] - at) <= DAY),
                      key=lambda item: abs(item[0] - at), default=None)
            kind = "near"
        if hit is None:
            continue
        left.remove(hit)
        exact, near = exact + (kind == "exact"), near + (kind == "near")
        r_pairs.append((r, next(t["r"] for t in mine if (t["at"], t["symbol"], t["side"]) == hit)))
    same_sign = sum(1 for a, b in r_pairs if (a > 0) == (b > 0))
    return {"reference": len(theirs), "ours": len(mine), "exact": exact, "within_1d": near,
            "only_reference": len(theirs) - exact - near, "only_ours": len(left),
            "matched_same_result_sign": same_sign,
            "reference_net_r": round(sum(row[3] for row in theirs), 2),
            "by_symbol": {symbol: {"reference": sum(1 for row in theirs if row[1] == symbol),
                                   "ours": sum(1 for t in mine if t["symbol"] == symbol)} for symbol in SYMBOLS}}


def report(bars: dict, spread, data_end: float) -> dict:
    """Ileri test isinin cagirdigi ozet: kaynak kipinde karsilastirma + duzeltilmis olcum."""
    reference = json.loads(REFERENCE.read_text())
    covered = {symbol: [bars[symbol]["H4"][0]["time"], bars[symbol]["H4"][-1]["time"], len(bars[symbol]["H4"]),
                        len(bars[symbol].get("D1") or [])] for symbol in SYMBOLS if bars.get(symbol, {}).get("H4")}
    out: dict = {"from": START, "to": data_end, "coverage": covered, "missing": [s for s in SYMBOLS if s not in covered]}
    found = all_signals(bars)
    for name, soft in (("soft", True), ("strict", False)):
        replica = run(bars, soft=soft, mode="bt", found=found)
        fixed = run(bars, soft=soft, mode="fixed", spread=spread, found=found)
        out[name] = {"replica": summarize(replica, exclude_open=False),
                     "match": compare(replica, reference[name], data_end),
                     "fixed": summarize(fixed, exclude_open=True)}
    return out
