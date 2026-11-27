"""Faz 5 kosucusu (GitHub Actions): sembol basina walk-forward + monkey test; birlestirme; kasa (bir kez).

Kullanim:
  python -m tradebot.research.run symbol --data research.db --job job.json --symbol EURUSD --out parts/
  python -m tradebot.research.run assemble --parts parts/ --out wf.json
  python -m tradebot.research.run holdout --data research.db --job job.json --wf wf.json --out holdout.json

`symbol` kipinde veri KASA BASLANGICINDA KESILIR: kasa mumlari hic yuklenmez.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

from . import engine as E
from .strategies import BY_ID, STRATEGIES

WARMUP_DAYS = 300
MAX_MISSING_SHARE = 0.05  # indirilemeyen dosya payi bundan fazlaysa sembol arastirmaya alinmaz
MONKEY_REPS = 200
INDICES = {"US30", "US500", "USTEC"}


def _daily_rows(db, symbol: str) -> list:
    """D1, H1'den yeniden kurulur: kripto disinda Pazar saatleri Pazartesi mumuna katilir (data.sunday_to_monday)."""
    from .data import aggregate, sunday_to_monday
    h1 = [{"time": r[0], "open": r[1], "high": r[2], "low": r[3], "close": r[4]} for r in db.execute(
        "SELECT time, open, high, low, close FROM bars WHERE symbol=? AND tf='H1' ORDER BY time", (symbol,))]
    crypto = kind_of(symbol, {}) == "crypto"
    bars = aggregate(h1, 86400, None if crypto else sunday_to_monday)
    return [(b["time"], b["open"], b["high"], b["low"], b["close"]) for b in bars]


def load(path: Path, symbol: str, until: int | None) -> tuple[dict, dict, dict]:
    db = sqlite3.connect(path)
    try:
        series = {}
        for tf in ("H1", "H4", "D1"):
            rows = _daily_rows(db, symbol) if tf == "D1" else db.execute(
                "SELECT time, open, high, low, close FROM bars WHERE symbol=? AND tf=? ORDER BY time", (symbol, tf)).fetchall()
            if until is not None:
                size = E.TF_SECONDS[tf]
                rows = [r for r in rows if r[0] + size <= until]  # kasa baslangicindan once KAPANMIS mumlar
            arr = np.array(rows, dtype=float) if rows else np.zeros((0, 5))
            series[tf] = E.Series(symbol, tf, arr[:, 0].astype(np.int64), arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4])
        spreads = dict(db.execute("SELECT time, spread FROM spreads WHERE symbol=?", (symbol,)).fetchall())
        if until is not None:
            spreads = {k: v for k, v in spreads.items() if k < until}
        meta = json.loads(db.execute("SELECT value FROM meta").fetchone()[0])
    finally:
        db.close()
    return series, spreads, meta


def load_universe(path: Path, until: int | None) -> dict:
    db = sqlite3.connect(path)
    try:
        names = [r[0] for r in db.execute("SELECT DISTINCT symbol FROM bars WHERE tf='D1'")]
        out = {}
        for name in names:
            rows = _daily_rows(db, name)
            if until is not None:
                rows = [r for r in rows if r[0] + 86400 <= until]
            if rows:
                arr = np.array(rows, dtype=float)
                out[name] = E.Series(name, "D1", arr[:, 0].astype(np.int64), arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4])
        return out
    finally:
        db.close()


def kind_of(symbol: str, job: dict) -> str:
    if symbol in INDICES:
        return "index"
    if symbol.startswith(("XAU", "XAG")):
        return "metal"
    if symbol in ("BTCUSD", "ETHUSD"):
        return "crypto"
    for row in job.get("instruments", []):
        if row["symbol"] == symbol:
            return row.get("kind") or "forex"
    return "forex"


def costs_for(symbol: str, job: dict, spreads: dict) -> E.Costs:
    profile = (job.get("spreads") or {}).get(symbol)
    if profile:
        return E.Costs({int(h): float(v) for h, v in profile["hours"].items()}, float(profile["all"]), "exness")
    values = sorted(spreads.items())[-24 * 365:]
    if not values:
        return E.Costs({}, 0.0, "yok")
    by_hour: dict = {}
    for moment, value in values:
        by_hour.setdefault(moment // 3600 % 24, []).append(value)
    hours = {h: float(np.median(v)) for h, v in by_hour.items()}
    return E.Costs(hours, float(np.median([v for _, v in values])), "dukascopy")


def spread_ratio(series: E.Series, spreads: dict) -> np.ndarray | None:
    """F4: girisin oldugu saatin spread'i / ayni saat diliminin onceki 60 gundeki medyani (kaynak verinin kendi
    ask-bid olcumu). Olcum yoksa NaN (filtre gecer)."""
    if not spreads:
        return None
    times = sorted(spreads)
    history: dict = {}
    ratio_at = {}
    for moment in times:
        hour = moment // 3600 % 24
        past = history.setdefault(hour, [])
        while past and past[0][0] < moment - 60 * 86400:
            past.pop(0)
        if len(past) >= 20:
            med = float(np.median([v for _, v in past]))
            ratio_at[moment] = spreads[moment] / med if med > 0 else np.nan
        past.append((moment, spreads[moment]))
    last_h1 = series.time + series.seconds - 3600  # kapanistaki son H1 mumu
    return np.array([ratio_at.get(int(x), np.nan) for x in last_h1])


def run_symbol(data: Path, job: dict, symbol: str, out: Path, only: list[str] | None = None,
               reps: int = MONKEY_REPS) -> dict:
    began = time.time()
    _, _, meta = load(data, symbol, None)
    plan = E.timeline(meta["end"])
    series, spreads, _ = load(data, symbol, plan["holdout"][0])  # KASA KESILDI
    kind = kind_of(symbol, job)
    costs = costs_for(symbol, job, spreads)
    result = {"symbol": symbol, "kind": kind, "plan": plan, "costs": costs.source, "strategies": {}}
    if not len(series["H1"]):
        result["error"] = "veri yok"
        out.write_text(json.dumps(result))
        return result
    data_from = int(series["H1"].time[0]) + WARMUP_DAYS * 86400
    result["data_from"] = data_from
    info = meta.get("symbols", {}).get(symbol, {})
    gaps = info.get("gaps") or []
    result["gaps"] = gaps
    if info.get("files") and info.get("failed", 0) > MAX_MISSING_SHARE * info["files"]:
        result["error"] = f"veri eksik ({info['failed']}/{info['files']} dosya indirilemedi)"
        out.write_text(json.dumps(result))
        return result
    daily = series["D1"]
    series["universe"] = load_universe(data, plan["holdout"][0])  # capraz kesit: diger sembollerin D1'i (kasa kesik)
    for strategy in STRATEGIES:
        if (only and strategy.id not in only) or kind not in strategy.kinds:
            continue
        s = series[strategy.tf]
        spec = strategy.build(s, series)
        gates = E.filters(s, daily, kind, spread_ratio(s, spreads))
        weights = E.p2_weights(s, daily)
        row = {"family": strategy.family, "tf": strategy.tf, "variants": {}}
        real = None
        for fname, allow in gates.items():
            if allow is None:
                continue
            trades, stats = E.simulate(s, spec, costs, allow=allow)
            if fname == "F0":
                real = [(int(np.searchsorted(s.time, t.entry_time - s.seconds)), t.side) for t in trades]
            for sizing in E.SIZINGS:
                weighted = trades if sizing == "P1" else [
                    E.Trade(t.entry_time, t.exit_time, t.side, t.r,
                            float(weights[int(np.searchsorted(s.time, t.entry_time - s.seconds))]), t.reason)
                    for t in trades]
                wf = E.walk_forward(weighted, plan, data_from, gaps=gaps)
                entry = {**wf, "stats": stats}
                if wf["passed"]:  # portfoy icin: sayilan test pencerelerindeki islemler (gorulmemis donem)
                    spans = [w["test"] for w, r in zip(plan["windows"], wf["windows"]) if r.get("selected")]
                    entry["oos_trades"] = [[t.entry_time, t.exit_time, t.side, round(t.r, 4), round(t.weight, 4)]
                                           for t in weighted if t.r is not None
                                           and any(a <= t.entry_time < b for a, b in spans)]
                row["variants"][f"{fname}/{sizing}"] = entry
        mk = E.monkey(s, spec, costs, real or [], plan, data_from, reps=reps, gaps=gaps)
        region = [t for t in E.simulate(s, spec, costs)[0] if plan["region"][0] <= t.entry_time < plan["region"][1]]
        real_pf = E.metrics(region)["pf"] or 0.0
        pfs = mk.pop("pfs", [])
        mk["real_pf"] = float(real_pf)
        mk["percentile"] = round(float(np.mean([p < real_pf for p in pfs])) * 100.0, 1) if pfs else None
        row["monkey"] = mk
        result["strategies"][strategy.id] = row
        print(f"{symbol} {strategy.id:18s} sinyal={len(real or [])} gecen="
              f"{[k for k, v in row['variants'].items() if v['passed']]} monkey={mk.get('pass_rate')}", flush=True)
    result["seconds"] = round(time.time() - began, 1)
    out.write_text(json.dumps(result))
    return result


def assemble(parts: Path, out: Path) -> dict:
    rows, chance, tested, passed = [], 0.0, 0, []
    errors = {}
    for path in sorted(parts.glob("*.json")):
        part = json.loads(path.read_text())
        if part.get("error"):
            errors[part["symbol"]] = part["error"]
            continue
        for sid, row in part["strategies"].items():
            p = row["monkey"].get("pass_rate") or 0.0
            for variant, wf in row["variants"].items():
                tested += 1
                chance += p
                key = {"symbol": part["symbol"], "strategy": sid, "variant": variant}
                rows.append({**key, "passed": wf["passed"], "counted": wf["counted"], "oos": wf["oos"],
                             "positive_share": wf["positive_share"]})
                if wf["passed"]:
                    passed.append({**key, "oos_trades": wf.get("oos_trades", [])})
    by_strategy: dict = {}
    for r in rows:
        agg = by_strategy.setdefault(r["strategy"], {"tested": 0, "passed": 0, "selected_windows": 0})
        agg["tested"] += 1
        agg["passed"] += r["passed"]
        agg["selected_windows"] += r["counted"]
    from .portfolio import build as build_portfolio
    portfolio = build_portfolio(one_variant_per_pair(passed)) if passed else None
    summary = {"version": "wf-1", "tested": tested, "portfolio": portfolio, "passed": len(passed), "expected_by_chance": round(chance, 2),
               "approved_candidates": passed, "by_strategy": by_strategy, "errors": errors, "rows": rows,
               "finished_at": time.time()}
    out.write_text(json.dumps(summary))
    return summary


VARIANT_ORDER = [f"{f}/{p}" for f in ("F0", "F1", "F2", "F3", "F4") for p in ("P1", "P2")]


def one_variant_per_pair(passed: list[dict]) -> list[dict]:
    """Portfoyde her (sembol, strateji) bir kez: gecen varyantlardan SABIT siradaki ilki (F0..F4, P1 once). Siralama
    sonuca bakmaz (en iyi varyanti secmek ek bir secim yanlisligi olurdu)."""
    best: dict = {}
    for item in passed:
        key = (item["symbol"], item["strategy"])
        if key not in best or VARIANT_ORDER.index(item["variant"]) < VARIANT_ORDER.index(best[key]["variant"]):
            best[key] = item
    return list(best.values())


def report(summary: dict) -> str:
    """Gunluge yazilan ozet: strateji basina denenen / gecen; gecenlerin gorulmemis sonucu; tesadufi beklenti."""
    pairs = {(k["symbol"], k["strategy"]) for k in summary["approved_candidates"]}
    lines = [f"denenen eslesme: {summary['tested']} | gecen: {summary['passed']} | "
             f"tesadufen beklenen gecen: {summary['expected_by_chance']} | gecen (sembol, strateji) cifti: {len(pairs)}"]
    for sid, agg in sorted(summary["by_strategy"].items()):
        lines.append(f"  {sid:26s} denenen={agg['tested']:4d} gecen={agg['passed']:3d} secilen_pencere={agg['selected_windows']}")
    for key in summary["approved_candidates"]:
        row = next(r for r in summary["rows"] if r["symbol"] == key["symbol"] and r["strategy"] == key["strategy"]
                   and r["variant"] == key["variant"])
        oos = row["oos"]
        lines.append(f"  GECTI {key['symbol']:7s} {key['strategy']:26s} {key['variant']:6s} islem={oos['trades']} "
                     f"R={oos['net_r']} PF={oos['pf']} DD%={oos['max_dd_pct']} pencere={row['counted']} "
                     f"arti_pay={row['positive_share']}")
    if summary.get("portfolio"):
        p = summary["portfolio"]
        lines.append("portfoy (gorulmemis donem): " + json.dumps({k: p[k] for k in ("trades", "rejected", "risk")}))
    if summary["errors"]:
        lines.append("hatalar: " + json.dumps(summary["errors"]))
    return "\n".join(lines)


def holdout(data: Path, job: dict, wf: dict, out: Path) -> dict:
    """KASA: yalnizca walk-forward'u gecen eslesmeler, tum veriyle, BIR KEZ."""
    results = []
    by_symbol: dict = {}
    for key in wf["approved_candidates"]:
        by_symbol.setdefault(key["symbol"], []).append(key)
    universe = load_universe(data, None)
    for symbol, keys in by_symbol.items():
        series, spreads, meta = load(data, symbol, None)
        series["universe"] = universe
        plan = E.timeline(meta["end"])
        kind, costs = kind_of(symbol, job), None
        costs = costs_for(symbol, job, spreads)
        for key in keys:
            strategy = BY_ID[key["strategy"]]
            s = series[strategy.tf]
            spec = strategy.build(s, series)
            fname, sizing = key["variant"].split("/")
            allow = E.filters(s, series["D1"], kind, spread_ratio(s, spreads))[fname]
            trades, _ = E.simulate(s, spec, costs, allow=allow)
            if sizing == "P2":
                weights = E.p2_weights(s, series["D1"])
                trades = [E.Trade(t.entry_time, t.exit_time, t.side, t.r,
                                  float(weights[int(np.searchsorted(s.time, t.entry_time - s.seconds))]), t.reason)
                          for t in trades]
            m = E.metrics([t for t in trades if plan["holdout"][0] <= t.entry_time < plan["holdout"][1]])
            results.append({**key, "holdout": m, "approved": m["trades"] >= 1 and m["net_r"] > 0})
    summary = {"version": "ho-1", "results": results, "approved": [r for r in results if r["approved"]],
               "finished_at": time.time()}
    out.write_text(json.dumps(summary))
    return summary


def _market(path: Path) -> dict:
    db = sqlite3.connect(path)
    try:
        return json.loads(db.execute("SELECT value FROM meta").fetchone()[0]).get("market") or {}
    finally:
        db.close()


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("symbol", "assemble", "holdout"))
    parser.add_argument("--data", type=Path)
    parser.add_argument("--job", type=Path, help="verilmezse veri dosyasindaki piyasa bilgisi (meta.market)")
    parser.add_argument("--symbol")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--reps", type=int, default=MONKEY_REPS)
    parser.add_argument("--parts", type=Path)
    parser.add_argument("--wf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    job = json.loads(args.job.read_text()) if args.job else (_market(args.data) if args.data else {})
    if args.mode == "symbol":
        args.out.mkdir(parents=True, exist_ok=True)
        run_symbol(args.data, job, args.symbol, args.out / f"{args.symbol}.json", args.only, args.reps)
    elif args.mode == "assemble":
        summary = assemble(args.parts, args.out)
        print(report(summary))
    else:
        holdout(args.data, job, json.loads(args.wf.read_text()), args.out)


if __name__ == "__main__":
    main(sys.argv[1:])
