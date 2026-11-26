"""5 yillik piyasa verisi: Exness (son ~12 ay, sunucunun disa aktardigi) + Dukascopy / Binance (oncesi).

Yalnizca PIYASA verisi: OHLC mumlar ve (Dukascopy'de) ask - bid spread. Hesapla ilgili hicbir alan okunmaz ya da
yazilmaz. Indirme yalnizca GitHub Actions'ta yapilir (sunucu ve gelistirme ortami bu adreslere cikmaz).

Cikti: `bars` tablosu (botun gecmis dosyasiyla ayni bicim; H1, H4, D1), `spreads` (sembol, H1 zamani, spread;
Dukascopy ask-bid kapanisi) ve `meta` (kaynaklar, olcek, kaynak farki).
"""

from __future__ import annotations

import argparse
import concurrent.futures
import io
import json
import lzma
import math
import sqlite3
import statistics
import struct
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

H1, H4, D1 = 3600, 14400, 86400
DUKASCOPY = "https://datafeed.dukascopy.com/datafeed/{code}/{year}/{month:02d}/{side}_candles_hour_1.bi5"
BINANCE = "https://data.binance.vision/data/spot/monthly/klines/{code}/1h/{code}-1h-{year}-{month:02d}.zip"
INDICES = ("US30", "US500", "USTEC")
# Exness adi -> (kaynak, kaynaktaki ad). Listede olmayan FX / metal sembolu Dukascopy'de ayni adla aranir.
SOURCE_NAMES = {"US30": ("dukascopy", "USA30IDXUSD"), "US500": ("dukascopy", "USA500IDXUSD"),
                "USTEC": ("dukascopy", "USATECHIDXUSD"), "BTCUSD": ("binance", "BTCUSDT"),
                "ETHUSD": ("binance", "ETHUSDT")}
# Exness karsiligi olmayan sembolde olcek denetimi icin kaba fiyat araligi (yalnizca 10'un kuvvetini secmek icin).
PRICE_RANGES = {"US30": (10_000.0, 90_000.0), "US500": (1_500.0, 12_000.0), "USTEC": (5_000.0, 40_000.0)}
RECORD = struct.Struct(">5if")  # saniye, acilis, kapanis, dusuk, yuksek (tamsayi puan), hacim
_SCHEMA = ("CREATE TABLE IF NOT EXISTS bars (symbol TEXT, tf TEXT, time INTEGER, open REAL, high REAL, low REAL, "
           "close REAL, volume REAL DEFAULT 0, PRIMARY KEY (symbol, tf, time)) WITHOUT ROWID",
           "CREATE TABLE IF NOT EXISTS spreads (symbol TEXT, time INTEGER, spread REAL, PRIMARY KEY (symbol, time)) "
           "WITHOUT ROWID",
           "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")


def source_of(symbol: str) -> tuple[str, str]:
    return SOURCE_NAMES.get(symbol, ("dukascopy", symbol))


def month_start(year: int, month: int) -> int:
    return int(datetime(year, month, 1, tzinfo=timezone.utc).timestamp())


def months(start: int, end: int) -> list[tuple[int, int]]:
    """[start, end) araligina dokunan (yil, ay) listesi."""
    day = datetime.fromtimestamp(start, timezone.utc)
    year, month, out = day.year, day.month, []
    while month_start(year, month) < end:
        out.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


# ---------------------------------------------------------------- ayristiricilar
def decode_dukascopy(raw: bytes, period_start: int) -> list[tuple]:
    """Dukascopy saatlik mum dosyasi (LZMA) -> (zaman, acilis, yuksek, dusuk, kapanis, hacim); fiyat TAMSAYI puan."""
    if not raw:
        return []
    data = lzma.decompress(raw)
    out = []
    for offset in range(0, len(data) - RECORD.size + 1, RECORD.size):
        seconds, o, c, low, h, volume = RECORD.unpack_from(data, offset)
        out.append((period_start + seconds, o, h, low, c, volume))
    return out


def parse_binance(raw: bytes) -> list[tuple]:
    """Binance aylik kline zip'i -> (zaman, acilis, yuksek, dusuk, kapanis, hacim). Zaman ms ya da (2025'ten
    itibaren) mikrosaniye olabilir."""
    out = []
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in archive.namelist():
            for line in archive.read(name).decode().splitlines():
                cells = line.split(",")
                if len(cells) < 6 or not cells[0].strip().isdigit():
                    continue  # baslik satiri
                stamp = int(cells[0])
                seconds = stamp // 1_000_000 if stamp > 10**14 else stamp // 1000
                out.append((seconds, float(cells[1]), float(cells[2]), float(cells[3]), float(cells[4]),
                            float(cells[5])))
    return out


def scale_for(raw_closes: list[float], reference: float | None, price_range: tuple | None) -> float:
    """Tamsayi puanlari fiyata ceviren 10'un kuvveti. Exness'in ortusen donemdeki medyanina (yoksa kaba araliga)
    en yakin olcek secilir."""
    middle = statistics.median(raw_closes)
    candidates = [10.0 ** k for k in range(0, 8)]
    if reference:
        return min(candidates, key=lambda s: abs(math.log(middle / s / reference)))
    if price_range:
        low, high = price_range
        inside = [s for s in candidates if low <= middle / s <= high]
        if inside:
            return inside[0]
    raise ValueError("olcek bulunamadi")


# ---------------------------------------------------------------- birlestirme
def aggregate(h1: list[dict], size: int) -> list[dict]:
    """H1 mumlarindan UTC sinirlarinda daha buyuk mumlar (H4: 00/04/..., D1: gece yarisi)."""
    out: list[dict] = []
    for bar in h1:
        start = bar["time"] - bar["time"] % size
        if out and out[-1]["time"] == start:
            last = out[-1]
            last["high"], last["low"] = max(last["high"], bar["high"]), min(last["low"], bar["low"])
            last["close"], last["volume"] = bar["close"], last["volume"] + bar.get("volume", 0.0)
        else:
            out.append({"time": start, "open": bar["open"], "high": bar["high"], "low": bar["low"],
                        "close": bar["close"], "volume": bar.get("volume", 0.0)})
    return out


def merge(exness: list[dict], other: list[dict]) -> list[dict]:
    """Exness'in ilk mumundan itibaren Exness, oncesi diger kaynak (ikisi ust uste binmez)."""
    if not exness:
        return list(other)
    first = exness[0]["time"]
    return [bar for bar in other if bar["time"] < first] + list(exness)


def compare(exness: list[dict], other: list[dict]) -> dict | None:
    """Ortusen H1 mumlarinda kaynak farki: kapanis farkinin medyani (fiyatin binde biri olarak) ve H1 getiri
    korelasyonu."""
    theirs = {bar["time"]: bar["close"] for bar in other}
    pairs = [(bar["close"], theirs[bar["time"]]) for bar in exness if bar["time"] in theirs]
    if len(pairs) < 50:
        return None
    diff = statistics.median(abs(a - b) / a * 1000.0 for a, b in pairs)
    ra = [math.log(pairs[i][0] / pairs[i - 1][0]) for i in range(1, len(pairs))]
    rb = [math.log(pairs[i][1] / pairs[i - 1][1]) for i in range(1, len(pairs))]
    try:
        corr = statistics.correlation(ra, rb)
    except statistics.StatisticsError:
        corr = None
    return {"bars": len(pairs), "close_diff_permille": round(diff, 4), "return_corr": None if corr is None else round(corr, 4)}


# ---------------------------------------------------------------- indirme (yalnizca Actions)
def _get(url: str, tries: int = 4) -> bytes | None:
    """404 -> None (o ay yok). 401/403 kalici: hemen hata. Diger hatalar kisa beklemeyle yeniden denenir."""
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-bot"}),
                                        timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            if exc.code in (401, 403):
                raise RuntimeError(f"erisim reddedildi ({exc.code}): {url}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            pass
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"indirilemedi: {url}")


def _tasks(symbol: str, start: int, end: int) -> list[tuple]:
    source, code = source_of(symbol)
    out = []
    for year, month in months(start, end):
        if source == "binance":
            out.append((symbol, "binance", BINANCE.format(code=code, year=year, month=month), month_start(year, month), "BID"))
        else:
            for side in ("BID", "ASK"):
                out.append((symbol, "dukascopy", DUKASCOPY.format(code=code, year=year, month=month - 1, side=side),
                            month_start(year, month), side))
    return out


def fetch_all(names: list[str], start: int, end: int, workers: int = 32) -> dict:
    """Butun sembollerin aylik dosyalari tek havuzda paralel indirilir -> sembol -> {h1, ask, source, code, ...}."""
    tasks = [task for name in names for task in _tasks(name, start, end)]
    got: dict = {name: {"source": source_of(name)[0], "code": source_of(name)[1], "h1": [], "ask": {},
                        "integer": source_of(name)[0] == "dukascopy", "missing_months": 0, "failed": 0}
                 for name in names}

    def one(task):
        symbol, source, url, begin, side = task
        try:
            raw = _get(url)
        except RuntimeError:
            return task, None, True
        if raw is None:
            return task, None, False
        return task, (parse_binance(raw) if source == "binance" else decode_dukascopy(raw, begin)), False

    done = 0
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        for (symbol, source, url, begin, side), rows, failed in pool.map(one, tasks):
            done += 1
            entry = got[symbol]
            if failed:
                entry["failed"] += 1
            elif rows is None:
                entry["missing_months"] += side == "BID"
            elif side == "BID":
                entry["h1"] += rows
            else:
                entry["ask"].update({row[0]: row[4] for row in rows})
            if done % 500 == 0:
                print(f"indirildi {done}/{len(tasks)}", flush=True)
    for entry in got.values():
        entry["h1"] = sorted(r for r in entry["h1"] if start <= r[0] < end and r[2] >= r[3] > 0)
    return got


def build(job: dict, exness_path: Path | None, out: Path, years: float, symbols: list[str] | None = None,
          workers: int = 32) -> dict:
    """Uc kaynagi birlestirip `out` dosyasini yazar -> meta."""
    from ..backtest import read_history  # sunucunun disa aktardigi dosya (Exness mumlari)
    exness = read_history(exness_path) if exness_path and exness_path.exists() else None
    names = symbols or json.loads((Path(__file__).parent / "symbols.json").read_text())
    end = int(time.time() // D1 * D1)
    start = end - int(years * 365.25 * D1)
    meta: dict = {"start": start, "end": end, "symbols": {}}
    db = sqlite3.connect(out)
    for statement in _SCHEMA:
        db.execute(statement)

    fetched_all = fetch_all(names, start, end, workers)
    if True:
        for symbol, fetched in fetched_all.items():
            ex_h1 = [dict(bar) for bar in exness.all(symbol, "H1")] if exness else []
            info = {"source": fetched["source"], "code": fetched["code"], "exness_h1": len(ex_h1),
                    "missing_months": fetched["missing_months"], "failed": fetched["failed"]}
            rows = fetched["h1"]
            scale = 1.0
            if rows and fetched["integer"]:
                reference = statistics.median(b["close"] for b in ex_h1) if ex_h1 else None
                try:
                    scale = scale_for([r[4] for r in rows], reference, PRICE_RANGES.get(symbol))
                except ValueError:
                    info["error"] = "olcek bulunamadi"
                    rows = []
            other = [{"time": r[0], "open": r[1] / scale, "high": r[2] / scale, "low": r[3] / scale,
                      "close": r[4] / scale, "volume": r[5]} for r in rows]
            info.update({"scale": scale, "other_h1": len(other), "compare": compare(ex_h1, other)})
            h1 = merge(ex_h1, other)
            if h1:
                info.update({"first": h1[0]["time"], "last": h1[-1]["time"], "exness_from": ex_h1[0]["time"] if ex_h1 else None,
                             "days": round((h1[-1]["time"] - h1[0]["time"]) / D1, 1)})
            for tf, size in (("H1", H1), ("H4", H4), ("D1", D1)):
                series = h1 if tf == "H1" else aggregate(h1, size)
                db.executemany("INSERT OR REPLACE INTO bars VALUES (?,?,?,?,?,?,?,?)",
                               [(symbol, tf, b["time"], b["open"], b["high"], b["low"], b["close"], b.get("volume", 0.0))
                                for b in series])
            spreads = [(symbol, r[0], (fetched["ask"][r[0]] - r[4]) / scale) for r in rows if r[0] in fetched["ask"]]
            db.executemany("INSERT OR REPLACE INTO spreads VALUES (?,?,?)", [s for s in spreads if s[2] >= 0])
            info["spread_bars"] = len(spreads)
            meta["symbols"][symbol] = info
            db.commit()
            print(f"{symbol:8s} {info['source']:9s} gun={info.get('days')} exness={len(ex_h1)} diger={len(other)} "
                  f"olcek={scale:g} fark={info['compare']}", flush=True)
    meta["market"] = {"instruments": [{"symbol": row["symbol"], "kind": row.get("kind")}
                                      for row in job.get("instruments", []) if row.get("symbol") in names],
                      "spreads": {k: v for k, v in (job.get("spreads") or {}).items() if k in names}}
    db.execute("INSERT OR REPLACE INTO meta VALUES ('meta', ?)", (json.dumps(meta),))
    db.commit()
    db.close()
    return meta


def main(argv: list[str]) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path, required=True)
    parser.add_argument("--exness", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--years", type=float, default=6.0)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)
    job = json.loads(args.job.read_text())
    return build(job, args.exness, args.out, args.years, args.only)


if __name__ == "__main__":
    main(sys.argv[1:])
