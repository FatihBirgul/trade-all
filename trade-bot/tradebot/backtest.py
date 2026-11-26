"""Ileri test: V9 stratejilerini gecmis gercek mumlar uzerinde, canlidaki kapilarla yeniden oynatir.

Amac "kenar var mi?" sorusunu parametre ayarlamadan olcmektir; hicbir esik sonuca gore degistirilmez.
Ayri, dusuk oncelikli bir surecte calisir (ag ve kimlik bilgisi kullanmaz): bot gecmisi bir SQLite dosyasina
yazar, bu modul oynatir ve sonucu JSON olarak birakir. Sonuc yalnizca sayilar ve R degerleridir.

Bilinen sinirlar (sonucla birlikte raporlanir): spread her sembol icin sabit kabul edilir (isin basladigi
andaki deger); mum ici sira bilinmedigi icin ayni mumda once aleyhte hareket sayilir; haber kapisi, guven
puani ve portfoy kapisi uygulanmaz (ham V9 adaylari); sembol basina ayni anda tek islem.
"""

from __future__ import annotations

import bisect
import dataclasses
import json
import os
import sqlite3
import statistics
import sys
import time
from collections.abc import Callable
from pathlib import Path

from .exness.schema import Account, Instrument
from .signals import outcome

VERSION = "bt-1"
DURATIONS = {"M15": 900, "H1": 3600, "H4": 14400}
WARMUP_DAYS = {"M15": 6, "H1": 16, "H4": 60}  # 256 mum + hafta sonlari
MAX_HOLD_BARS = 400  # bu kadar mumda sonuclanmayan islem "acik" sayilir
REENTRY_BARS = 8  # stoptan sonra ayni sembole bu kadar mum icinde giris "yeniden giris" sayilir
SESSIONS = (("asya", 22, 7), ("londra", 7, 13), ("newyork", 13, 22))  # UTC saatleri
MFE_EDGES = (0.25, 0.5, 1.0, 2.0)


class History:
    """(sembol, zaman dilimi) -> kapanmis mumlar (eskiden yeniye)."""

    def __init__(self) -> None:
        self._bars: dict[tuple[str, str], list[dict]] = {}
        self._times: dict[tuple[str, str], list[int]] = {}

    def add(self, symbol: str, tf: str, bars: list[dict]) -> None:
        rows = sorted({int(b["time"]): b for b in bars}.values(), key=lambda b: b["time"])
        self._bars[(symbol, tf)] = rows
        self._times[(symbol, tf)] = [int(b["time"]) for b in rows]

    def closed(self, symbol: str, tf: str, now: float, count: int) -> list[dict]:
        times = self._times.get((symbol, tf))
        if not times:
            return []
        end = bisect.bisect_right(times, now - DURATIONS[tf])
        return self._bars[(symbol, tf)][max(0, end - count):end]

    def after(self, symbol: str, tf: str, start: float, count: int) -> list[dict]:
        times = self._times.get((symbol, tf))
        if not times:
            return []
        begin = bisect.bisect_left(times, start)
        return self._bars[(symbol, tf)][begin:begin + count]

    def all(self, symbol: str, tf: str) -> list[dict]:
        return self._bars.get((symbol, tf), [])


class _Clock:
    now = 0.0


class _Quotes:
    def __init__(self, history: History, spreads: dict[str, float], clock: _Clock):
        self._history, self._spreads, self._clock = history, spreads, clock

    def quote(self, symbol: str) -> dict | None:
        spread = self._spreads.get(symbol)
        last = self._history.closed(symbol, "M15", self._clock.now, 1)
        # Bayat fiyat uydurulmaz: son mum iki mumdan eskiyse (kapali piyasa) fiyat yok sayilir.
        if spread is None or not last or self._clock.now - (last[-1]["time"] + 900) > 1800:
            return None
        bid = last[-1]["close"]
        return {"bid": bid, "ask": bid + spread, "spread": spread, "time": self._clock.now - 1.0}

    def max_spread(self, symbol: str) -> float | None:
        spread = self._spreads.get(symbol)
        return None if spread is None else spread * 3.0


class _Candles:
    def __init__(self, history: History, clock: _Clock):
        self._history, self._clock = history, clock

    def cached(self, symbol: str, tf: str, count: int = 256) -> list[dict]:
        return self._history.closed(symbol, tf, self._clock.now, count)


class _Catalog:
    def __init__(self, instruments: list[Instrument]):
        self._by_symbol = {i.symbol: i for i in instruments}

    def get(self, symbol: str) -> Instrument:
        return self._by_symbol[symbol]


def default_evaluate(provider, symbol: str, now: float) -> list:
    from .signals import v9
    from .signals.adapter import evaluate_all

    modes = {s: "live" for s in v9.builtin_strategy_ids()}
    return [r.candidate for r in evaluate_all(provider, symbol, equity=10_000.0, risk_pct=0.5,
                                              commission_per_lot=0.0, modes=modes, now=now)
            if r.candidate is not None]


def replay(instruments: list[Instrument], history: History, spreads: dict[str, float], account: Account, *,
           rules: dict, start: float, end: float, budget: float = 7200.0,
           evaluate: Callable | None = None, timer: Callable[[], float] = time.monotonic) -> dict:
    """Her sembolu [start, end) araligindaki her M15 kapanisinda degerlendirir -> {trades, coverage}."""
    from .signals.provider import ExnessV9Provider

    clock = _Clock()
    provider = ExnessV9Provider(_Catalog(instruments), _Candles(history, clock), _Quotes(history, spreads, clock),
                                lambda: account)
    evaluate = evaluate or default_evaluate
    began = timer()
    trades: list[dict] = []
    coverage = {"symbols": [], "evaluations": 0, "errors": 0, "skipped_open": 0, "out_of_budget": False}
    for instrument in instruments:
        symbol, spread = instrument.symbol, spreads.get(instrument.symbol)
        if spread is None or not history.all(symbol, "M15"):
            continue
        open_until, last_stop = 0.0, None
        for bar in history.after(symbol, "M15", start - 900, 10**9):
            closed_at = bar["time"] + 900
            if closed_at < start or closed_at >= end:
                continue
            if timer() - began > budget:
                coverage["out_of_budget"] = True
                break
            clock.now = closed_at + 5.0
            coverage["evaluations"] += 1
            try:
                candidates = evaluate(provider, symbol, clock.now)
            except Exception:  # noqa: BLE001 - tek bir mumdaki hata butun olcumu durdurmasin
                coverage["errors"] += 1
                continue
            if not candidates:
                continue
            if clock.now < open_until:
                coverage["skipped_open"] += 1
                continue
            c = candidates[0]
            bars = history.closed(symbol, "M15", clock.now, 40) + history.after(symbol, "M15", closed_at,
                                                                                 MAX_HOLD_BARS)
            levels = (c.entry, c.stop_loss, c.take_profit_1, c.take_profit_2)
            net = outcome.simulate(c.side, *levels, clock.now, bars, spread=spread, **rules)
            shift = spread if c.side == "BUY" else 0.0  # brut: girisi bid'e tasi, spread'siz
            gross = outcome.simulate(c.side, *(v - shift for v in levels), clock.now, bars, **rules)
            if net is None or gross is None:
                coverage["errors"] += 1
                continue
            risk = abs(c.entry - c.stop_loss)
            trade = {"symbol": symbol, "side": c.side, "strategy_id": c.strategy_id, "at": clock.now,
                     "r": net["r"], "open_r": net.get("open_r"), "first": net["first"], "bars": net["bars"],
                     "mfe_r": net["mfe_r"], "mae_r": net["mae_r"],
                     "gross_r": gross["r"] if gross["r"] is not None else gross.get("open_r"),
                     "spread_r": round(spread / risk, 4) if risk > 0 else None,
                     **outcome.shape(c.side, c.entry, c.stop_loss, clock.now, bars),
                     "reentry": last_stop is not None and clock.now - last_stop <= REENTRY_BARS * 900}
            trades.append(trade)
            open_until = net["closed_at"] if net["closed_at"] is not None else float("inf")
            if net["r"] is not None and net["r"] < 0:
                last_stop = net["closed_at"]
        else:
            coverage["symbols"].append(symbol)
            continue
        break  # butce bitti
    coverage["seconds"] = round(timer() - began, 1)
    return {"trades": trades, "coverage": coverage}


def _session(at: float) -> str:
    hour = int(at // 3600) % 24
    for name, begin, finish in SESSIONS:
        if (begin <= hour < finish) if begin < finish else (hour >= begin or hour < finish):
            return name
    return "?"


def _stats(rows: list[dict]) -> dict:
    closed = [t for t in rows if t["r"] is not None]
    results = [t["r"] for t in closed]
    gross = [t["gross_r"] for t in closed if t["gross_r"] is not None]
    spreads = [t["spread_r"] for t in rows if t["spread_r"] is not None]
    stops = [t["stop_atr"] for t in rows if t.get("stop_atr") is not None]
    mfe = [0] * (len(MFE_EDGES) + 1)
    for t in closed:
        mfe[bisect.bisect_right(MFE_EDGES, t["mfe_r"])] += 1
    first = {}
    for t in closed:
        first[t["first"] or "yok"] = first.get(t["first"] or "yok", 0) + 1
    return {"trades": len(rows), "closed": len(closed), "open": len(rows) - len(closed),
            "wins": sum(1 for r in results if r > 0), "flat": sum(1 for r in results if r == 0),
            "losses": sum(1 for r in results if r < 0),
            "sum_r": round(sum(results), 2), "avg_r": round(statistics.fmean(results), 3) if results else None,
            "gross_sum_r": round(sum(gross), 2), "gross_avg_r": round(statistics.fmean(gross), 3) if gross else None,
            "spread_r_median": round(statistics.median(spreads), 3) if spreads else None,
            "stop_atr_median": round(statistics.median(stops), 2) if stops else None,
            "first_touch": first, "mfe_buckets": mfe}


def summarize(result: dict, *, start: float, end: float) -> dict:
    trades = result["trades"]

    def group(key: Callable[[dict], str]) -> dict:
        names = sorted({key(t) for t in trades})
        return {name: _stats([t for t in trades if key(t) == name]) for name in names}

    return {"version": VERSION, "from": start, "to": end, "coverage": result["coverage"],
            "mfe_edges": list(MFE_EDGES), "total": _stats(trades),
            "by_strategy": group(lambda t: t["strategy_id"]), "by_session": group(lambda t: _session(t["at"])),
            "by_side": group(lambda t: t["side"]),
            "reentry": {"after_stop": _stats([t for t in trades if t["reentry"]]),
                        "other": _stats([t for t in trades if not t["reentry"]])},
            "by_symbol": {name: {k: v for k, v in stats.items() if k in ("trades", "closed", "wins", "sum_r")}
                          for name, stats in group(lambda t: t["symbol"]).items()}}


# ---------------------------------------------------------------- dosya bicimi (bot <-> alt surec)
_SCHEMA = ("CREATE TABLE IF NOT EXISTS bars (symbol TEXT, tf TEXT, time INTEGER, open REAL, high REAL, low REAL, "
           "close REAL, volume REAL DEFAULT 0, PRIMARY KEY (symbol, tf, time)) WITHOUT ROWID")


def write_history(path: Path, rows: list[tuple]) -> None:
    db = sqlite3.connect(path)
    try:
        db.execute(_SCHEMA)
        with db:
            db.executemany("INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?,?)",
                           [tuple(row) + (0.0,) * (8 - len(row)) for row in rows])
    finally:
        db.close()


def read_history(path: Path) -> History:
    history, grouped = History(), {}
    db = sqlite3.connect(path)
    try:
        for symbol, tf, at, o, h, low, c, volume in db.execute("SELECT * FROM bars ORDER BY symbol, tf, time"):
            grouped.setdefault((symbol, tf), []).append({"time": at, "open": o, "high": h, "low": low, "close": c,
                                                         "tick_volume": volume or 0})
    finally:
        db.close()
    for (symbol, tf), bars in grouped.items():
        history.add(symbol, tf, bars)
    return history


def run_job(job_path: Path) -> dict:
    job = json.loads(job_path.read_text())
    instruments = [Instrument(**row) for row in job["instruments"]]
    account = Account(**job["account"])
    history = read_history(Path(job["history"]))
    result = replay(instruments, history, job["spreads"], account, rules=job["rules"], start=job["start"],
                    end=job["end"], budget=job["budget"])
    summary = summarize(result, start=job["start"], end=job["end"])
    summary["finished_at"] = time.time()
    target = Path(job["result"])
    temporary = target.with_suffix(".partial")
    temporary.write_text(json.dumps(summary))
    os.replace(temporary, target)
    return summary


def job_instruments(instruments: list[Instrument]) -> list[dict]:
    return [dataclasses.asdict(i) for i in instruments]


if __name__ == "__main__":
    try:
        os.nice(19)
    except OSError:
        pass
    run_job(Path(sys.argv[1]))
