"""Genisletilmis ileri test (surum ft-2): swing ailesi + V9, ic/dis orneklem, saate gore spread.

Iki asama, ikisi de ag ve kimlik bilgisi kullanmayan dusuk oncelikli alt surecte:
A) Swing stratejileri (SMC, H1 EMA geri cekilme): butun semboller, butun donem. Her sinyal uc hedefle
   (1,5R / 2R / 2,5R) ve swing cikis planiyla benzetilir. Hedef ve EMA bolgesi ILK donemde (ic orneklem) secilir,
   SON donemde (dis orneklem) dogrulanir; secim sonuca bakilarak degil, onceden sabit bu kucuk izgaradan yapilir.
   Portfoy kurallari ayrica uygulanir: gunde en cok 5 islem, art arda 3 kayiptan sonra gunun kalaninda giris yok.
B) V9 stratejileri: canlidaki degerlendirme her M15 kapanisinda calisir (pahalidir; sure siniri dolunca kalan
   semboller sonraki calismaya kalir, biten semboller yeniden hesaplanmaz). Her aday iki stopla benzetilir:
   kendi stopu ve "en az 1,5 x gunluk ATR" stopu.
Hicbir esik sonuca gore degistirilmez. Sonuc yalnizca sayilar ve R'dir.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import sqlite3
import statistics
import sys
import time
from pathlib import Path

from . import backtest
from .backtest import History
from .exness.schema import Account, Instrument
from .signals import outcome
from .signals.modules import Context, modules
from .signals.modules.indicators import atr

VERSION = "ft-2"
TARGETS = (1.5, 2.0, 2.5)
SWING_IDS = ("tb_smc_sweep_v1", "tb_emapb_h1_20_21_v1", "tb_emapb_h1_21_50_v1")
EMA_IDS = SWING_IDS[1:]
MAX_PER_DAY = 5
LOSS_STREAK = 3
MIN_TRADES_TO_SELECT = 15  # ic orneklemde bundan az islemi olan secenek secilmez
DAILY_ATR_MULT = 1.5
DAY = 86400.0
WARMUP_DAYS = {"M15": 6, "H1": 16, "H4": 60, "D1": 130}
DURATIONS = {"M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}


class Spreads:
    """Sembol ve saate gore spread: olculmus saatlik medyan; o saat olculmediyse sembolun genel medyani."""

    def __init__(self, profile: dict):
        self._profile = profile

    def has(self, symbol: str) -> bool:
        return symbol in self._profile

    def at(self, symbol: str, moment: float) -> float:
        entry = self._profile[symbol]
        return float(entry["hours"].get(str(int(moment // 3600) % 24), entry["all"]))

    def coverage(self) -> dict:
        hours = [len(entry["hours"]) for entry in self._profile.values()]
        return {"symbols": len(hours), "hours_measured_median": statistics.median(hours) if hours else 0}


def read_history(path: Path, symbol: str) -> History:
    history, grouped = History(), {}
    db = sqlite3.connect(path)
    try:
        for tf, at, o, h, low, c in db.execute(
                "SELECT tf, time, open, high, low, close FROM bars WHERE symbol = ? ORDER BY tf, time", (symbol,)):
            grouped.setdefault(tf, []).append({"time": at, "open": o, "high": h, "low": low, "close": c,
                                               "tick_volume": 0})
    finally:
        db.close()
    for tf, bars in grouped.items():
        history.add(symbol, tf, bars)
    return history


def _closed(history: History, symbol: str, tf: str, now: float, count: int) -> list[dict]:
    times = history._times.get((symbol, tf))
    if not times:
        return []
    import bisect
    end = bisect.bisect_right(times, now - DURATIONS[tf])
    return history._bars[(symbol, tf)][max(0, end - count):end]


# ---------------------------------------------------------------- A) swing ailesi
def swing_trades(symbol: str, kind: str, history: History, spreads: Spreads, start: float, end: float) -> list[dict]:
    """Bir sembolde swing stratejilerinin butun sinyalleri; her biri uc hedefle benzetilmis."""
    active = [m for m in modules("strategy") if m.id in SWING_IDS]
    m15_all = history.all(symbol, "M15")
    trades: list[dict] = []
    open_until = {m.id: 0.0 for m in active}
    upper: dict = {}
    for index, bar in enumerate(m15_all):
        closed_at = bar["time"] + 900
        if closed_at < start or closed_at >= end or index < 3:
            continue
        now = closed_at + 5.0
        if closed_at % 3600 == 0 or not upper:  # ust zaman dilimleri yalnizca saat basinda degisir
            upper = {"H1": _closed(history, symbol, "H1", now, 160), "H4": _closed(history, symbol, "H4", now, 90),
                     "D1": _closed(history, symbol, "D1", now, 90)}
        context = Context(symbol=symbol, now=now, kind=kind, bars={"M15": m15_all[index - 3:index + 1], **upper})
        for module in active:
            if now < open_until[module.id]:
                continue  # ayni stratejinin bu semboldeki islemi hala acik
            signal = module.evaluate(context)
            if signal is None:
                continue
            sign = 1.0 if signal.side == "BUY" else -1.0
            spread = spreads.at(symbol, now)
            entry = bar["close"] + (spread if signal.side == "BUY" else 0.0)  # AL ask'tan acilir
            risk = (entry - signal.stop) * sign
            if risk <= 0:
                continue
            after = m15_all[index + 1:index + 1 + outcome.SWING_MAX_BARS]
            results = {}
            for target in TARGETS:
                result = outcome.simulate_swing(signal.side, entry, signal.stop, target, now, after,
                                                spread_at=lambda moment: spreads.at(symbol, moment))
                results[str(target)] = [result["r"], result["closed_at"], result.get("open_r")]
            daily = atr(upper["D1"])
            trades.append({"strategy_id": module.id, "symbol": symbol, "side": signal.side, "at": now,
                           "results": results, "spread_r": round(spread / risk, 4),
                           "stop_daily_atr": round(risk / daily, 2) if daily else None})
            reference = results["2.0"][1]
            open_until[module.id] = reference if reference is not None else float("inf")
    return trades


def apply_rules(trades: list[dict], target: str) -> list[dict]:
    """Portfoy kurallari (zaman sirasiyla): gunde en cok 5 giris; art arda 3 kayiptan sonra o gun giris yok."""
    accepted: list[dict] = []
    per_day: dict[int, int] = {}
    for trade in sorted(trades, key=lambda t: t["at"]):
        day = int(trade["at"] // DAY)
        if per_day.get(day, 0) >= MAX_PER_DAY:
            continue
        closed = sorted((t["results"][target][1], t["results"][target][0]) for t in accepted
                        if t["results"][target][1] is not None and t["results"][target][1] <= trade["at"])
        streak = 0
        for _, r in reversed(closed):
            if r is None or r >= 0:
                break
            streak += 1
        if streak >= LOSS_STREAK and int(closed[-1][0] // DAY) == day:
            continue
        accepted.append(trade)
        per_day[day] = per_day.get(day, 0) + 1
    return accepted


def stats(values: list[float | None]) -> dict:
    closed = [v for v in values if v is not None]
    return {"trades": len(values), "open": len(values) - len(closed), "wins": sum(1 for v in closed if v > 0),
            "flat": sum(1 for v in closed if v == 0), "losses": sum(1 for v in closed if v < 0),
            "sum_r": round(sum(closed), 2), "avg_r": round(statistics.fmean(closed), 3) if closed else None}


def _periods(trades: list[dict], split: float, value) -> dict:
    return {"is": stats([value(t) for t in trades if t["at"] < split]),
            "oos": stats([value(t) for t in trades if t["at"] >= split])}


def summarize_swing(trades: list[dict], split: float) -> dict:
    out: dict = {"strategies": {}, "selected": {}}
    for strategy_id in SWING_IDS:
        rows = [t for t in trades if t["strategy_id"] == strategy_id]
        table = {}
        for target in (str(t) for t in TARGETS):
            ruled = apply_rules(rows, target)
            table[target] = {"raw": _periods(rows, split, lambda t, k=target: t["results"][k][0]),
                             "rules": _periods(ruled, split, lambda t, k=target: t["results"][k][0])}
        spreads = [t["spread_r"] for t in rows]
        stops = [t["stop_daily_atr"] for t in rows if t["stop_daily_atr"] is not None]
        out["strategies"][strategy_id] = {
            "targets": table, "spread_r_median": round(statistics.median(spreads), 4) if spreads else None,
            "stop_daily_atr_median": round(statistics.median(stops), 2) if stops else None,
            "buy": sum(1 for t in rows if t["side"] == "BUY"), "sell": sum(1 for t in rows if t["side"] == "SELL")}

    def best(ids: tuple[str, ...]) -> dict | None:
        """Ic orneklemde islem basi R'si en yuksek (strateji, hedef); dis orneklem sonucu onunla raporlanir."""
        options = [(out["strategies"][i]["targets"][t]["rules"]["is"]["avg_r"], i, t) for i in ids
                   for t in (str(x) for x in TARGETS)
                   if (out["strategies"][i]["targets"][t]["rules"]["is"]["trades"]
                       - out["strategies"][i]["targets"][t]["rules"]["is"]["open"]) >= MIN_TRADES_TO_SELECT]
        if not options:
            return None
        _, chosen, target = max(options)
        return {"strategy_id": chosen, "target_r": float(target), **out["strategies"][chosen]["targets"][target]["rules"]}

    out["selected"] = {"smc": best(SWING_IDS[:1]), "ema_pullback": best(EMA_IDS)}
    return out


# ---------------------------------------------------------------- B) V9
class _Rates:
    def __init__(self, bounds):
        self._bounds = bounds


def v9_symbol(args: tuple) -> dict:
    """Tek sembolde V9'u oynatir (alt surec havuzunda calisir). Sure dolarsa `done` False doner."""
    job, symbol = args
    try:
        os.nice(19)
    except OSError:
        pass
    from .signals.provider import ExnessV9Provider

    instrument = next(Instrument(**row) for row in job["instruments"] if row["symbol"] == symbol)
    history = read_history(Path(job["history"]), symbol)
    spreads = Spreads(job["spreads"])
    account = Account(**job["account"])
    clock = backtest._Clock()

    class Quotes:
        def quote(self, name: str) -> dict | None:
            last = _closed(history, name, "M15", clock.now, 1)
            if not last or clock.now - (last[-1]["time"] + 900) > 1800:
                return None
            spread = spreads.at(name, clock.now)
            return {"bid": last[-1]["close"], "ask": last[-1]["close"] + spread, "spread": spread, "time": clock.now - 1.0}

        def max_spread(self, name: str) -> float:
            return spreads.at(name, clock.now) * 3.0

    class Provider(ExnessV9Provider):
        def _bounds(self, item, current):  # kur: isin basindaki sabit deger (lot buyuklugu R'yi etkilemez)
            return tuple(job["bounds"][symbol])

    provider = Provider(backtest._Catalog([instrument]), backtest._Candles(history, clock), Quotes(), lambda: account)
    start, end, deadline = job["v9_start"], job["end"], job["deadline"]
    m15 = history.all(symbol, "M15")
    trades, evaluations, errors, open_until, done = [], 0, 0, 0.0, True
    for index, bar in enumerate(m15):
        closed_at = bar["time"] + 900
        if closed_at < start or closed_at >= end:
            continue
        if time.time() > deadline:
            done = False
            break
        clock.now = closed_at + 5.0
        evaluations += 1
        try:
            candidates = backtest.default_evaluate(provider, symbol, clock.now)
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        if not candidates or clock.now < open_until:
            continue
        c = candidates[0]
        sign = 1.0 if c.side == "BUY" else -1.0
        spread = spreads.at(symbol, clock.now)
        before = m15[max(0, index - 40):index + 1]
        base = outcome.simulate(c.side, c.entry, c.stop_loss, c.take_profit_1, c.take_profit_2, clock.now,
                                before + m15[index + 1:index + 1 + backtest.MAX_HOLD_BARS], spread=spread, **job["rules"])
        daily = atr(_closed(history, symbol, "D1", clock.now, 20))
        risk = abs(c.entry - c.stop_loss)
        wide = None
        if daily and risk > 0:
            distance = max(risk, DAILY_ATR_MULT * daily)
            wide = outcome.simulate(c.side, c.entry, c.entry - sign * distance, c.entry + sign * 2 * distance,
                                    c.entry + sign * 3 * distance, clock.now,
                                    before + m15[index + 1:index + 1 + outcome.SWING_MAX_BARS], spread=spread,
                                    **job["rules"])
        if base is None:
            errors += 1
            continue
        trades.append({"strategy_id": c.strategy_id, "symbol": symbol, "side": c.side, "at": clock.now,
                       "r": base["r"], "wide_r": wide["r"] if wide else None,
                       "wide_open": wide is not None and wide["r"] is None,
                       "spread_r": round(spread / risk, 4) if risk > 0 else None})
        open_until = base["closed_at"] if base["closed_at"] is not None else float("inf")
    return {"symbol": symbol, "done": done, "trades": trades, "evaluations": evaluations, "errors": errors}


def summarize_v9(trades: list[dict], split: float) -> dict:
    out = {}
    names = sorted({t["strategy_id"] for t in trades}) + ["all"]
    for name in names:
        rows = trades if name == "all" else [t for t in trades if t["strategy_id"] == name]
        wide = [t for t in rows if t["wide_r"] is not None or t["wide_open"]]
        spreads = [t["spread_r"] for t in rows if t["spread_r"] is not None]
        out[name] = {"base": _periods(rows, split, lambda t: t["r"]), "wide_stop": _periods(wide, split, lambda t: t["wide_r"]),
                     "spread_r_median": round(statistics.median(spreads), 4) if spreads else None}
    return out


# ---------------------------------------------------------------- is
def run_job(job_path: Path, pool_factory=None) -> dict:
    job = json.loads(job_path.read_text())
    folder = job_path.parent
    spreads = Spreads(job["spreads"])
    symbols = [row["symbol"] for row in job["instruments"] if spreads.has(row["symbol"])]
    kinds = {row["symbol"]: row["kind"] for row in job["instruments"]}
    began = time.time()
    swing: list[dict] = []
    for symbol in symbols:
        history = read_history(Path(job["history"]), symbol)
        swing += swing_trades(symbol, kinds[symbol], history, spreads, job["start"], job["end"])
    summary = {"version": VERSION, "from": job["start"], "to": job["end"], "split": job["split"],
               "v9_from": job["v9_start"], "spread_profile": spreads.coverage(),
               "swing": summarize_swing(swing, job["split"]),
               "swing_seconds": round(time.time() - began, 1), "symbols": len(symbols)}
    # V9: biten semboller dosyada durur; yalnizca eksikler calisir.
    signature = f"{VERSION}:{job['v9_start']}:{job['end']}"
    done: dict[str, dict] = {}
    for symbol in symbols:
        cached = folder / f"v9-{symbol}.json"
        if cached.exists():
            try:
                data = json.loads(cached.read_text())
            except ValueError:
                continue
            if data.get("signature") == signature and data.get("done"):
                done[symbol] = data
    todo = [symbol for symbol in symbols if symbol not in done]
    workers = max(1, min(int(job.get("workers") or 1), len(todo) or 1))
    if todo:
        make_pool = pool_factory or (lambda count: multiprocessing.get_context("spawn").Pool(count))
        with make_pool(workers) as pool:
            for result in pool.imap_unordered(v9_symbol, [(job, symbol) for symbol in todo]):
                result["signature"] = signature
                if result["done"]:
                    (folder / f"v9-{result['symbol']}.json").write_text(json.dumps(result))
                    done[result["symbol"]] = result
    v9_trades = [t for data in done.values() for t in data["trades"]]
    summary["v9"] = summarize_v9(v9_trades, job["split"])
    summary["v9_coverage"] = {"symbols_done": len(done), "symbols_total": len(symbols), "workers": workers,
                              "evaluations": sum(d["evaluations"] for d in done.values()),
                              "errors": sum(d["errors"] for d in done.values()), "complete": len(done) == len(symbols)}
    summary["seconds"] = round(time.time() - began, 1)
    summary["finished_at"] = time.time()
    target = Path(job["result"])
    partial = target.with_suffix(".partial")
    partial.write_text(json.dumps(summary))
    os.replace(partial, target)
    return summary


if __name__ == "__main__":
    try:
        os.nice(19)
    except OSError:
        pass
    run_job(Path(sys.argv[1]))
