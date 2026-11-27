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
# Ek kural (2026-11-27, PROGRESS.md): D1 trend ailesi secim penceresinde en az 10 islem; ayrica SEPET olarak da.
D1_FAMILY = ("A01_turtle_s1", "A02_turtle_s2", "A03_ma_cross", "A04_faber_sma200", "A05_tsmom12", "A06_clenow",
             "A09_psar", "A10_ichimoku", "A11_macd_zero")
D1_SELECT_MIN = 10
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
               reps: int = MONKEY_REPS, d1_rule: bool = False) -> dict:
    began = time.time()
    _, _, meta = load(data, symbol, None)
    plan = E.timeline(meta["end"])
    series, spreads, _ = load(data, symbol, plan["holdout"][0])  # KASA KESILDI
    kind = kind_of(symbol, job)
    costs = costs_for(symbol, job, spreads)
    result = {"symbol": symbol, "kind": kind, "plan": plan, "costs": costs.source, "strategies": {},
              "rule": "d1-10" if d1_rule else "base"}
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
        family = d1_rule and strategy.id in D1_FAMILY
        select_min = D1_SELECT_MIN if family else None
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
                wf = E.walk_forward(weighted, plan, data_from, gaps=gaps, select_min=select_min)
                entry = {**wf, "stats": stats}
                if family:  # sepet icin butun islemler (arastirma bolgesi; kasa zaten kesik)
                    entry["trades"] = [[t.entry_time, t.exit_time, t.side, round(t.r, 4), round(t.weight, 4)]
                                       for t in weighted if t.r is not None]
                if wf["passed"]:  # portfoy icin: sayilan test pencerelerindeki islemler (gorulmemis donem)
                    spans = [w["test"] for w, r in zip(plan["windows"], wf["windows"]) if r.get("selected")]
                    entry["oos_trades"] = [[t.entry_time, t.exit_time, t.side, round(t.r, 4), round(t.weight, 4)]
                                           for t in weighted if t.r is not None
                                           and any(a <= t.entry_time < b for a, b in spans)]
                row["variants"][f"{fname}/{sizing}"] = entry
        mk = E.monkey(s, spec, costs, real or [], plan, data_from, reps=reps, gaps=gaps, select_min=select_min,
                      keep=family)
        region = [t for t in E.simulate(s, spec, costs)[0] if plan["region"][0] <= t.entry_time < plan["region"][1]]
        real_pf = E.metrics(region)["pf"] or 0.0
        pfs = mk.pop("pfs", [])
        mk["real_pf"] = float(real_pf)
        mk["percentile"] = round(float(np.mean([p < real_pf for p in pfs])) * 100.0, 1) if pfs else None
        row["monkey_trades"] = mk.pop("trades", None)
        row["monkey"] = mk
        result["strategies"][strategy.id] = row
        print(f"{symbol} {strategy.id:18s} sinyal={len(real or [])} gecen="
              f"{[k for k, v in row['variants'].items() if v['passed']]} monkey={mk.get('pass_rate')}", flush=True)
    result["seconds"] = round(time.time() - began, 1)
    out.write_text(json.dumps(result))
    return result


def basket(parts: list[dict]) -> dict:
    """Ek kural (b): her D1 trend stratejisi 33 sembolde birlikte, esit riskle; sepet duzeyinde ayni walk-forward
    ve gecme olcutu. Monkey: ayni tekrar sirasindaki sembol islemleri birlestirilir -> sepetin tesadufi gecme orani."""
    plan = next(p["plan"] for p in parts if p.get("plan"))
    out: dict = {}
    for sid in D1_FAMILY:
        rows = [p["strategies"][sid] for p in parts if sid in p.get("strategies", {})]
        if not rows:
            continue
        variants = {}
        for variant in rows[0]["variants"]:
            trades = [E.Trade(a, b, c, d, w) for row in rows for a, b, c, d, w in row["variants"].get(variant, {}).get("trades", [])]
            wf = E.walk_forward(trades, plan, plan["region"][0], select_min=D1_SELECT_MIN)
            variants[variant] = {**wf, "symbols": len(rows)}
        reps = min((len(r.get("monkey_trades") or []) for r in rows), default=0)
        passes = 0
        for k in range(reps):
            trades = [E.Trade(a, b, c, d) for r in rows for a, b, c, d in (r.get("monkey_trades") or [])[k]]
            passes += E.walk_forward(trades, plan, plan["region"][0], select_min=D1_SELECT_MIN)["passed"]
        out[sid] = {"variants": variants, "monkey": {"reps": reps, "pass_rate": round(passes / reps, 4) if reps else None}}
    return out


def assemble(parts: Path, out: Path) -> dict:
    rows, chance, tested, passed = [], 0.0, 0, []
    errors = {}
    loaded = [json.loads(path.read_text()) for path in sorted(parts.glob("*.json"))]
    for part in loaded:
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
    baskets = basket(loaded) if any(p.get("rule") == "d1-10" for p in loaded) else None
    basket_chance = sum((b["monkey"]["pass_rate"] or 0.0) * len(b["variants"]) for b in (baskets or {}).values())
    summary = {"version": "wf-1", "tested": tested, "portfolio": portfolio, "baskets": baskets,
               "basket_expected_by_chance": round(basket_chance, 2), "passed": len(passed), "expected_by_chance": round(chance, 2),
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
    for sid, b in (summary.get("baskets") or {}).items():
        won = [v for v, wf in b["variants"].items() if wf["passed"]]
        first = b["variants"].get("F0/P1", {}).get("oos", {})
        lines.append(f"  SEPET {sid:22s} gecen={won} F0/P1 gorulmemis: islem={first.get('trades')} R={first.get('net_r')} "
                     f"PF={first.get('pf')} DD%={first.get('max_dd_pct')} monkey={b['monkey']['pass_rate']}")
    if summary.get("baskets") is not None:
        lines.append(f"sepet tesadufen beklenen gecen: {summary['basket_expected_by_chance']}")
    if summary["errors"]:
        lines.append("hatalar: " + json.dumps(summary["errors"]))
    return "\n".join(lines)


def _variant_trades(strategy, series, spreads, kind, costs, variant):
    s = series[strategy.tf]
    spec = strategy.build(s, series)
    fname, sizing = variant.split("/")
    allow = E.filters(s, series["D1"], kind, spread_ratio(s, spreads))[fname]
    trades, _ = E.simulate(s, spec, costs, allow=allow)
    if sizing == "P2":
        weights = E.p2_weights(s, series["D1"])
        trades = [E.Trade(t.entry_time, t.exit_time, t.side, t.r,
                          float(weights[int(np.searchsorted(s.time, t.entry_time - s.seconds))]), t.reason)
                  for t in trades]
    return trades


def _per_trade(m: dict) -> float | None:
    return round(m["net_r"] / m["trades"], 4) if m and m.get("trades") else None


def holdout(data: Path, job: dict, wfs: list[dict], out: Path, index_costs: dict | None = None) -> dict:
    """KASA: walk-forward'u gecen BUTUN adaylar (sembol bazinda + sepet), tum veriyle, BIR KEZ. Kasa sonucuna gore
    hicbir kural ya da secim degistirilmez. `index_costs`: endeksler icin Exness olcumu (verilirse ikinci maliyet
    senaryosu olarak da hesaplanir)."""
    from .portfolio import accept, curve
    candidates, oos_by_key, baskets = {}, {}, []
    for wf in wfs:
        for row in wf.get("rows", []):
            if row["passed"]:
                key = (row["symbol"], row["strategy"], row["variant"])
                candidates[key] = row
                oos_by_key[key] = row["oos"]
        for sid, b in (wf.get("baskets") or {}).items():
            baskets += [(sid, v, b["variants"][v]["oos"]) for v, w in b["variants"].items() if w["passed"]]
    universe = load_universe(data, None)
    scenarios = {"kaynak": None} | ({"exness_endeks": index_costs} if index_costs else {})
    result = {"version": "ho-1", "scenarios": {}, "finished_at": None}
    for name, override in scenarios.items():
        rows, pair_trades = [], {}
        cache: dict = {}

        def load_symbol(symbol):
            if symbol not in cache:
                series, spreads, meta = load(data, symbol, None)
                series["universe"] = universe
                costs = costs_for(symbol, job, spreads)
                if override and symbol in override:
                    costs = E.Costs({int(h): float(v) for h, v in override[symbol]["hours"].items()},
                                    float(override[symbol]["all"]), "exness")
                cache[symbol] = (series, spreads, E.timeline(meta["end"]), costs)
            return cache[symbol]

        for (symbol, sid, variant), row in sorted(candidates.items()):
            series, spreads, plan, costs = load_symbol(symbol)
            trades = _variant_trades(BY_ID[sid], series, spreads, kind_of(symbol, job), costs, variant)
            inside = [t for t in trades if plan["holdout"][0] <= t.entry_time < plan["holdout"][1]]
            m = E.metrics(inside)
            oos = oos_by_key[(symbol, sid, variant)]
            rows.append({"symbol": symbol, "strategy": sid, "variant": variant, "holdout": m,
                         "approved": bool(m["trades"] >= 1 and m["net_r"] > 0), "oos": oos,
                         "r_per_trade": {"oos": _per_trade(oos), "holdout": _per_trade(m)},
                         "pf": {"oos": oos.get("pf"), "holdout": m["pf"]}})
            pair_trades[(symbol, sid, variant)] = inside
        chosen = one_variant_per_pair([{"symbol": r["symbol"], "strategy": r["strategy"], "variant": r["variant"]}
                                       for r in rows])
        flat = [{"symbol": c["symbol"], "key": f"{c['symbol']}|{c['strategy']}", "entry": t.entry_time,
                 "exit": t.exit_time, "side": t.side, "r": t.r, "w": t.weight}
                for c in chosen for t in pair_trades[(c["symbol"], c["strategy"], c["variant"])] if t.r is not None]
        accepted, rejected = accept(flat)
        portfolio = {"pairs": len(chosen), "trades": len(accepted), "rejected": rejected,
                     "net_r": round(sum(t["r"] * t["w"] for t in accepted), 3),
                     "risk": {f"{p}%": curve(accepted, p) for p in (0.5, 1.0)}}
        basket_rows = []
        for sid, variant, oos in baskets:
            union = []
            for symbol in sorted(universe):
                try:
                    series, spreads, plan, costs = load_symbol(symbol)
                except (KeyError, IndexError, ValueError):
                    continue
                if kind_of(symbol, job) not in BY_ID[sid].kinds or not len(series[BY_ID[sid].tf]):
                    continue
                union += [t for t in _variant_trades(BY_ID[sid], series, spreads, kind_of(symbol, job), costs, variant)
                          if plan["holdout"][0] <= t.entry_time < plan["holdout"][1]]
            m = E.metrics(union)
            basket_rows.append({"strategy": sid, "variant": variant, "holdout": m, "oos": oos,
                                "approved": bool(m["trades"] >= 1 and m["net_r"] > 0),
                                "r_per_trade": {"oos": _per_trade(oos), "holdout": _per_trade(m)}})
        result["scenarios"][name] = {"rows": rows, "portfolio": portfolio, "baskets": basket_rows}
    result["finished_at"] = time.time()
    out.write_text(json.dumps(result))
    return result


def holdout_report(result: dict) -> str:
    lines = []
    for name, sc in result["scenarios"].items():
        lines.append(f"== KASA ({name}) ==")
        for r in sc["rows"]:
            h = r["holdout"]
            lines.append(f"  {'ONAY' if r['approved'] else 'RED '} {r['symbol']:7s} {r['strategy']:24s} {r['variant']:6s} "
                         f"kasa: islem={h['trades']} R={h['net_r']} PF={h['pf']} DD%={h['max_dd_pct']} | R/islem "
                         f"gorulmemis={r['r_per_trade']['oos']} kasa={r['r_per_trade']['holdout']}")
        for b in sc["baskets"]:
            h = b["holdout"]
            lines.append(f"  {'ONAY' if b['approved'] else 'RED '} SEPET {b['strategy']:20s} {b['variant']:6s} kasa: "
                         f"islem={h['trades']} R={h['net_r']} PF={h['pf']} DD%={h['max_dd_pct']}")
        p = sc["portfolio"]
        lines.append("  portfoy (kasa): " + json.dumps({"pairs": p["pairs"], "trades": p["trades"], "net_r": p["net_r"],
                     **{k: {x: v[x] for x in ("end_balance", "max_dd_pct", "longest_dd_days")} for k, v in p["risk"].items()}}))
    return "\n".join(lines)


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
    parser.add_argument("--d1-rule", action="store_true", help="ek kural: D1 trend ailesi (>= 10 islem) + sepet")
    parser.add_argument("--parts", type=Path)
    parser.add_argument("--wf", type=Path, nargs="*")
    parser.add_argument("--index-costs", type=Path, help="endeksler icin Exness spread profili (json)")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    job = json.loads(args.job.read_text()) if args.job else (_market(args.data) if args.data else {})
    if args.mode == "symbol":
        args.out.mkdir(parents=True, exist_ok=True)
        run_symbol(args.data, job, args.symbol, args.out / f"{args.symbol}.json", args.only, args.reps, args.d1_rule)
    elif args.mode == "assemble":
        summary = assemble(args.parts, args.out)
        print(report(summary))
    else:
        result = holdout(args.data, job, [json.loads(p.read_text()) for p in args.wf], args.out,
                         json.loads(args.index_costs.read_text()) if args.index_costs else None)
        print(holdout_report(result))


if __name__ == "__main__":
    main(sys.argv[1:])
