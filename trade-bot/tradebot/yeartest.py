"""Yillik backtest (surum yt-1): butun stratejiler, butun semboller, uc pencere (1 ay / 6 ay / 1 yil).

Kullanici karari (2026-11-26): golgede haftalarca beklemek yerine stratejiler gecmis Exness mumlariyla olculur.
Kurallar:
- Karar yalnizca KAPANMIS mumla verilir (ileri testle ayni oynatma: `forward.swing_trades`, `forward.v9_symbol`).
- Her strateji kendi cikis planiyla benzetilir (canlidaki yonetim / kaynak koddaki plan).
- Maliyet: saatlik spread profili; spread / stop > sinir ise islem acilmaz (maliyet kapisi). Swap 0 (hesap swap'siz).
- Portfoy kurallari (strateji basina ve birlesik satirda): ayni anda en cok 3 acik islem, sembol basina 1, ayni para
  biriminde ayni yonde en cok 2.
- Bakiye egrisi: 2000 USC baslangic, islem basina bakiyenin %0,5'i risk (bilesik); islemler kapanis sirasiyla islenir.
- Pencereler tek bir 1 yillik oynatmadan turetilir: pencere, o tarihten sonra ACILAN islemleri kapsar ve bakiye
  2000'den yeniden baslar.
Sinirlar (sonuc okunurken bilinmeli):
- Haber penceresi gecmise UYGULANAMAZ: takvim kaynagi yalnizca icinde bulunulan haftayi verir.
- Spread profili bugunku saatlik olcumdur; gecmisteki gercek spread degildir.
- Portfoy sinirina takilan islemin yerine ayni sembolde hemen sonraki sinyal alinmaz (islem sayisi biraz az cikar).
- En kucuk lot denetimi yoktur; stoplar tam stop fiyatindan dolmus sayilir.
- V9 pahalidir (degerlendirme basina ~0,3 sn): en yeni aydan geriye dogru 30 gunluk parcalarla hesaplanir; her
  pencerenin tamamlanip tamamlanmadigi ayrica belirtilir.
Gecme olcutu: 1 yilda en az 50 islem, PF >= 1,2, iki yari yilin ikisi de pozitif, en buyuk dusus <= %15, 6 aylik
pencere de pozitif. Verisi 1 yili kapsamayan strateji "bekliyor"dur (gecti sayilmaz).
"""

from __future__ import annotations

import json
import multiprocessing
import os
import statistics
import sys
import time
from pathlib import Path

from . import forward

VERSION = "yt-1"
DAY = 86400.0
WINDOW_SHARES = {"1m": 30.0 / 365.0, "6m": 182.0 / 365.0, "1y": 1.0}
START_BALANCE = 2000.0
RISK_PCT = 0.5
MAX_OPEN = 3
PER_CURRENCY_SIDE = 2
OLD_SWING_TARGET = "2.0"  # eski yorum stratejileri kendi planlariyla (2R hedef) olculur
CURVE_POINTS = 60
PASS_MIN_TRADES = 50
PASS_MIN_PF = 1.2
PASS_MAX_DD_PCT = 15.0
COMPLETE_SHARE = 0.97  # verinin pencerenin en az bu kadarini kapsamasi gerekir
COVERAGE_QUANTILE = 0.2  # kapsam, sembollerin en kotu %20'lik diliminin sinirina gore olculur (medyana gore degil)
UNRESOLVED_HOLD = 31 * DAY  # sonuclanmamis islem portfoyde en cok bu kadar yer tutar (benzetimin en uzun tutma suresi)
PASS_MAX_AGE = 45 * DAY  # gecis, pencerenin bitisinden bu kadar sonra gecerliligini yitirir
TB_IDS = forward.SWING_IDS + forward.PLAN_IDS + forward.FIXED_IDS


def compact(trade: dict) -> dict:
    """Ileri testin islem kaydindan yillik testin kucuk kaydi."""
    key = OLD_SWING_TARGET if trade["strategy_id"] in forward.SWING_IDS else forward.PLAN_KEY
    r, closed_at, open_r = trade["results"][key]
    return {"s": trade["strategy_id"], "y": trade["symbol"], "d": trade["side"], "a": trade["at"], "r": r,
            "c": closed_at, "o": open_r, "p": trade["spread_r"], "b": bool(trade.get("cost_blocked"))}


def compact_v9(trade: dict) -> dict:
    return {"s": trade["strategy_id"], "y": trade["symbol"], "d": trade["side"], "a": trade["at"], "r": trade["r"],
            "c": trade.get("closed_at"), "o": trade.get("open_r"), "p": trade.get("spread_r") or 0.0,
            "b": bool(trade.get("cost_blocked"))}


def legs(symbol: str, side: str, currencies: dict) -> tuple:
    base, quote = currencies.get(symbol) or (symbol[:3], symbol[3:])
    long, short = ("long", "short") if side == "BUY" else ("short", "long")
    return (base, long), (quote, short)


def portfolio(trades: list[dict], currencies: dict) -> tuple[list[dict], int]:
    """Portfoy kurallarindan gecen islemler (giris sirasiyla) ve reddedilen sayisi."""
    accepted, rejected, book = [], 0, []
    for trade in sorted(trades, key=lambda t: (t["a"], t["y"], t["s"])):
        # Sonuclanmamis islem sonsuza kadar yer tutmaz: en uzun tutma suresi kadar acik sayilir.
        book = [item for item in book if (item["c"] if item["c"] is not None else item["a"] + UNRESOLVED_HOLD) > trade["a"]]
        exposure: dict = {}
        for item in book:
            for leg in legs(item["y"], item["d"], currencies):
                exposure[leg] = exposure.get(leg, 0) + 1
        if (len(book) >= MAX_OPEN or any(item["y"] == trade["y"] for item in book)
                or any(exposure.get(leg, 0) >= PER_CURRENCY_SIDE for leg in legs(trade["y"], trade["d"], currencies))):
            rejected += 1
            continue
        book.append(trade)
        accepted.append(trade)
    return accepted, rejected


def metrics(trades: list[dict], start: float, with_detail: bool = True) -> dict:
    """`start` aninda ya da sonrasinda acilan islemlerin olculeri; bakiye 2000 USC'den baslar."""
    rows = [t for t in trades if t["a"] >= start]
    closed = sorted((t for t in rows if t["r"] is not None), key=lambda t: (t["c"] or t["a"], t["a"]))
    gains = sum(t["r"] for t in closed if t["r"] > 0)
    losses = -sum(t["r"] for t in closed if t["r"] < 0)
    balance = peak = START_BALANCE
    total = high = down_r = down_pct = 0.0
    curve = [[round(start), round(balance, 2)]]
    for trade in closed:
        total += trade["r"]
        high = max(high, total)
        down_r = min(down_r, total - high)
        balance += balance * RISK_PCT / 100.0 * trade["r"]
        peak = max(peak, balance)
        down_pct = min(down_pct, (balance - peak) / peak * 100.0)
        curve.append([round(trade["c"] or trade["a"]), round(balance, 2)])
    costs = [t["p"] for t in rows if t["p"] is not None]
    out = {"trades": len(rows), "closed": len(closed), "open": len(rows) - len(closed),
           "wins": sum(1 for t in closed if t["r"] > 0),
           "win_pct": round(100.0 * sum(1 for t in closed if t["r"] > 0) / len(closed), 1) if closed else None,
           "net_r": round(total, 2), "net_usc": round(balance - START_BALANCE, 2),
           "pf": round(gains / losses, 2) if losses > 0 else None, "max_dd_r": round(down_r, 2),
           "max_dd_pct": round(down_pct, 2), "open_r": round(sum(t["o"] or 0.0 for t in rows if t["r"] is None), 2),
           "cost_stop_pct": round(100.0 * statistics.median(costs), 2) if costs else None}
    if with_detail:
        step = max(1, -(-len(curve) // CURVE_POINTS))
        out["curve"] = curve[::step] + ([curve[-1]] if (len(curve) - 1) % step else [])
        symbols: dict = {}
        for trade in closed:
            row = symbols.setdefault(trade["y"], {"trades": 0, "wins": 0, "net_r": 0.0})
            row["trades"] += 1
            row["wins"] += int(trade["r"] > 0)
            row["net_r"] = round(row["net_r"] + trade["r"], 2)
        out["by_symbol"] = dict(sorted(symbols.items()))
    return out


def verdict(windows: dict, halves: dict, complete: bool) -> dict:
    """Gecme olcutu. `passed`: True / False; veri 1 yili kapsamiyorsa None ("bekliyor")."""
    year, half = windows["1y"], windows["6m"]
    reasons = []
    if year["closed"] < PASS_MIN_TRADES:
        reasons.append(f"1 yılda {year['closed']} işlem (en az {PASS_MIN_TRADES})")
    if year["pf"] is None or year["pf"] < PASS_MIN_PF:
        reasons.append(f"PF {year['pf']} (en az {PASS_MIN_PF})")
    if halves["first"]["net_r"] <= 0 or halves["second"]["net_r"] <= 0:
        reasons.append(f"yarı yıllar {halves['first']['net_r']:+g}R / {halves['second']['net_r']:+g}R (ikisi de artı olmalı)")
    if year["max_dd_pct"] < -PASS_MAX_DD_PCT:
        reasons.append(f"en büyük düşüş %{abs(year['max_dd_pct'])} (en çok %{PASS_MAX_DD_PCT:g})")
    if half["net_r"] <= 0:
        reasons.append(f"6 ay {half['net_r']:+g}R (artı olmalı)")
    if not complete:
        return {"passed": None, "reasons": ["veri 1 yılı kapsamıyor"] + reasons}
    return {"passed": not reasons, "reasons": reasons}


def summarize(trades: list[dict], currencies: dict, start: float, end: float, covered: dict) -> dict:
    """Bir stratejinin (ya da birlesik portfoyun) sonucu. `covered`: pencere -> veri tam mi."""
    opened = [t for t in trades if not t["b"]]
    accepted, rejected = portfolio(opened, currencies)
    span = end - start
    windows = {name: {**metrics(accepted, end - share * span), "complete": bool(covered.get(name))}
               for name, share in WINDOW_SHARES.items()}
    middle = start + span / 2.0
    halves = {"first": metrics([t for t in accepted if t["a"] < middle], start, False),
              "second": metrics(accepted, middle, False)}
    return {"windows": windows, "halves": halves, "portfolio_rejected": rejected,
            "cost_gate": {"signals": len(trades), "blocked": len(trades) - len(opened)},
            "verdict": verdict(windows, halves, bool(covered.get("1y")))}


def chunks(start: float, end: float, size: float) -> list[tuple[float, float]]:
    """En yeniden eskiye, `size` saniyelik parcalar (sonuncusu `start`ta kesilir)."""
    out, upper = [], end
    while upper > start + 1e-6:
        lower = max(start, upper - size)
        out.append((lower, upper))
        upper = lower
    return out


def v9_chunk(args: tuple) -> dict:
    """Bir sembolun bir parcasi (alt surec havuzunda). Sure dolduysa hic baslamaz."""
    job, symbol, index, lower, upper = args
    if time.time() > job["deadline"]:
        return {"symbol": symbol, "index": index, "done": False, "trades": [], "evaluations": 0, "errors": 0}
    result = forward.v9_symbol(({**job, "v9_start": lower, "end": upper}, symbol))
    return {"symbol": symbol, "index": index, "done": result["done"], "evaluations": result["evaluations"],
            "errors": result["errors"], "trades": [compact_v9(t) for t in result["trades"]]}


def _load(path: Path, signature: str):
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("signature") == signature else None


def run_job(job_path: Path, pool_factory=None) -> dict:
    return run(json.loads(job_path.read_text()), job_path.parent, pool_factory)


def run(job: dict, folder: Path, pool_factory=None) -> dict:
    """`job["only"]` (sembol listesi) verilirse yalnizca o semboller HESAPLANIR; ozet yine klasordeki butun bitmis
    parcalardan kurulur. Boylece is sembol sembol ayri makinelerde kosup sonra tek yerde toplanabilir."""
    began = time.time()
    only = set(job["only"]) if job.get("only") else None
    spreads = forward.Spreads(job["spreads"])
    rows = [row for row in job["instruments"] if spreads.has(row["symbol"])]
    symbols = [row["symbol"] for row in rows]
    kinds = {row["symbol"]: row["kind"] for row in rows}
    currencies = {row["symbol"]: (row.get("currency_base") or row["symbol"][:3],
                                  row.get("currency_profit") or row["symbol"][3:]) for row in rows}
    end, start = float(job["end"]), float(job["year_start"])
    span = end - start
    max_cost = forward.max_cost_of(job)
    # Imza olcumu etkileyen her seyi kapsar: oynatma surumu, pencere, maliyet siniri, cikis kurallari.
    signature = (f"{VERSION}:{forward.VERSION}:{start}:{end}:{job.get('max_spread_stop_pct')}:"
                 f"{json.dumps(job.get('rules'), sort_keys=True)}")
    history_path = Path(job["history"])

    # A) V9 disi stratejiler: sembol sembol, sonuc dosyada saklanir (yeniden baslatmada yeniden hesaplanmaz).
    tb_trades: list[dict] = []
    coverage: dict[str, float] = {}
    tb_done = 0
    for symbol in symbols:
        cached = _load(folder / f"yt-tb-{symbol}.json", signature)
        if cached is None:
            if time.time() > job["deadline"] or (only is not None and symbol not in only):
                continue
            history = forward.read_history(history_path, symbol)
            m15 = history.all(symbol, "M15")
            found = forward.swing_trades(symbol, kinds[symbol], history, spreads, start, end, max_cost)
            cached = {"signature": signature, "first_bar": m15[0]["time"] if m15 else None,
                      "trades": [compact(t) for t in found if t["strategy_id"] in TB_IDS]}
            (folder / f"yt-tb-{symbol}.json").write_text(json.dumps(cached))
        tb_done += 1
        tb_trades += cached["trades"]
        coverage[symbol] = (round((end - max(start, cached["first_bar"])) / DAY, 1)
                            if cached["first_bar"] is not None else 0.0)  # mumu olmayan sembol 0 gun sayilir

    # B) V9: en yeni parcadan eskiye. Biten (sembol, parca) dosyada saklanir.
    size = float(job.get("chunk_days", 30.0)) * DAY
    parts = chunks(start, end, size)
    done: dict[tuple[str, int], dict] = {}
    todo = []
    for index, (lower, upper) in enumerate(parts):
        for symbol in symbols:
            cached = _load(folder / f"yt-v9-{symbol}-{index}.json", signature)
            if cached is not None and cached.get("done"):
                done[(symbol, index)] = cached
            elif only is None or symbol in only:
                todo.append((job, symbol, index, lower, upper))
    tb_ready = tb_done == len(symbols) if only is None else all((folder / f"yt-tb-{s}.json").exists() for s in only)
    if todo and tb_ready and time.time() < job["deadline"]:
        workers = max(1, min(int(job.get("workers") or 1), len(todo)))
        make_pool = pool_factory or (lambda count: multiprocessing.get_context("spawn").Pool(count))
        with make_pool(workers) as pool:
            for result in pool.imap(v9_chunk, todo):
                if result["done"]:
                    result["signature"] = signature
                    (folder / f"yt-v9-{result['symbol']}-{result['index']}.json").write_text(json.dumps(result))
                    done[(result["symbol"], result["index"])] = result
    # Bir parca ancak BUTUN sembollerde bittiyse sayilir; kapsam en yeniden baslayan kesintisiz parcalardir.
    full = 0
    for index in range(len(parts)):
        if all((symbol, index) in done for symbol in symbols):
            full += 1
        else:
            break
    v9_from = parts[full - 1][0] if full else end
    v9_trades = [t for (symbol, index), data in done.items() if index < full for t in data["trades"]]

    def covered(from_time: float, enough: bool = True) -> dict:
        return {name: enough and from_time <= end - share * span * COMPLETE_SHARE + 1e-6
                for name, share in WINDOW_SHARES.items()}

    # Kapsam medyana gore DEGIL, en kotu dilime gore: sembollerin cogu eksikse "tam" denmez.
    ranked = sorted(coverage.values())
    floor_days = ranked[int(COVERAGE_QUANTILE * (len(ranked) - 1))] if ranked else 0.0
    data_from = end - floor_days * DAY
    strategies: dict = {}
    for strategy_id in TB_IDS:
        mine = [t for t in tb_trades if t["s"] == strategy_id]
        strategies[strategy_id] = {"source": "custom", **summarize(mine, currencies, start, end,
                                                                  covered(data_from, tb_done == len(symbols)))}
    for strategy_id in sorted({t["s"] for t in v9_trades} | set(job.get("v9_ids") or [])):
        mine = [t for t in v9_trades if t["s"] == strategy_id]
        strategies[strategy_id] = {"source": "v9", **summarize(mine, currencies, start, end, covered(max(v9_from, data_from)))}
    passed = [name for name, row in strategies.items() if row["verdict"]["passed"]]
    combined = None
    if passed:
        both = [t for t in tb_trades + v9_trades if t["s"] in passed]
        combined = {"strategies": passed, **summarize(both, currencies, start, end, covered(data_from))}
    complete = bool(symbols) and tb_done == len(symbols) and full == len(parts)
    summary = {
        "version": VERSION, "from": start, "to": end, "symbols": len(symbols), "complete": complete,
        "rules": {"start_balance": START_BALANCE, "risk_pct": RISK_PCT, "max_open": MAX_OPEN,
                  "per_currency_side": PER_CURRENCY_SIDE, "max_spread_stop_pct": job.get("max_spread_stop_pct"),
                  "swap": 0, "news_applied": False, "currency": "USC"},
        "pass_rule": {"min_trades": PASS_MIN_TRADES, "min_pf": PASS_MIN_PF, "max_dd_pct": PASS_MAX_DD_PCT,
                      "both_halves_positive": True, "six_months_positive": True},
        "history": {"days_median": statistics.median(coverage.values()) if coverage else 0.0,
                    "days_min": min(coverage.values()) if coverage else 0.0, "days_floor": floor_days,
                    "symbols_full": sum(1 for days in coverage.values() if days >= span / DAY * COMPLETE_SHARE),
                    "by_symbol": coverage},
        "progress": {"tb_symbols_done": tb_done, "symbols": len(symbols), "v9_chunks_done": len(done),
                     "v9_chunks_total": len(parts) * len(symbols), "v9_days_complete": round((end - v9_from) / DAY, 1),
                     "v9_evaluations": sum(d["evaluations"] for d in done.values()),
                     "v9_errors": sum(d["errors"] for d in done.values())},
        "strategies": strategies, "combined": combined, "seconds": round(time.time() - began, 1),
        "finished_at": time.time()}
    target = Path(job["year_result"])
    partial = target.with_suffix(".partial")
    partial.write_text(json.dumps(summary))
    os.replace(partial, target)
    return summary


def public(result: dict | None) -> dict | None:
    """Herkese acik ozet: sembol tablosu ve egri olmadan (yalnizca sayilar; benzetim sonucu, hesap verisi degil)."""
    if not isinstance(result, dict):
        return None
    def slim(row: dict) -> dict:
        return {**{k: v for k, v in row.items() if k != "windows"},
                "windows": {name: {k: v for k, v in window.items() if k not in ("curve", "by_symbol")}
                            for name, window in row["windows"].items()}}
    return {**{k: v for k, v in result.items() if k not in ("strategies", "combined", "history")},
            "history": {k: v for k, v in (result.get("history") or {}).items() if k != "by_symbol"},
            "strategies": {name: slim(row) for name, row in (result.get("strategies") or {}).items()},
            "combined": slim(result["combined"]) if result.get("combined") else None}


def passed(result: dict | None, strategy_id: str, now: float, max_spread_stop_pct: float) -> bool:
    """Bu strateji gecme olcutunu sagliyor mu? Gecis yalnizca su kosullarda sayilir: guncel surum; olcum penceresi
    en cok `PASS_MAX_AGE` once bitmis (eski sonuc suresiz gecerli olmaz); olcumdeki maliyet siniri SIMDIKI ayardan
    gevsek degil (sinir sonradan gevsetildiyse canli, backtestin eledigi islemleri acardi)."""
    if not isinstance(result, dict) or result.get("version") != VERSION:
        return False
    try:
        if now - float(result.get("to")) > PASS_MAX_AGE:
            return False
        measured = (result.get("rules") or {}).get("max_spread_stop_pct")
        if measured is None or float(measured) < float(max_spread_stop_pct) - 1e-9:
            return False
    except (TypeError, ValueError):
        return False
    row = (result.get("strategies") or {}).get(strategy_id)
    return bool(isinstance(row, dict) and (row.get("verdict") or {}).get("passed") is True)


def main(argv: list[str]) -> dict:
    """python -m tradebot.yeartest IS.json [--history DOSYA] [--out KLASOR] [--only SEMBOL,...] [--workers N]
    [--assemble]. `--assemble`: hicbir sey hesaplamaz, klasordeki parcalardan ozeti kurar."""
    import argparse
    parser = argparse.ArgumentParser(prog="tradebot.yeartest")
    parser.add_argument("job")
    parser.add_argument("--history")
    parser.add_argument("--out")
    parser.add_argument("--only")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--assemble", action="store_true")
    args = parser.parse_args(argv)
    job = json.loads(Path(args.job).read_text())
    folder = Path(args.out) if args.out else Path(args.job).parent
    folder.mkdir(parents=True, exist_ok=True)
    if args.history:
        job["history"] = args.history
    if args.out or "year_result" not in job:
        job["year_result"] = str(folder / "year.json")
    if args.only:
        job["only"] = [name for name in args.only.split(",") if name]
    if args.workers:
        job["workers"] = args.workers
    job["deadline"] = 0.0 if args.assemble else float(job.get("deadline") or time.time() + 5.5 * 3600)
    return run(job, folder)


if __name__ == "__main__":
    try:
        os.nice(19)
    except OSError:
        pass
    main(sys.argv[1:])
