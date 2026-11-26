"""Genisletilmis ileri test (surum ft-6): swing ailesi + V9, ic/dis orneklem, saate gore spread.

Iki asama, ikisi de ag ve kimlik bilgisi kullanmayan dusuk oncelikli alt surecte:
A) Swing stratejileri (SMC, H1 EMA geri cekilme): butun semboller, butun donem. Her sinyal uc hedefle
   (1,5R / 2R / 2,5R) ve swing cikis planiyla benzetilir. Hedef ve EMA bolgesi ILK donemde (ic orneklem) secilir,
   SON donemde (dis orneklem) dogrulanir; secim sonuca bakilarak degil, onceden sabit bu kucuk izgaradan yapilir.
   Portfoy kurallari (gunde en cok 5 islem, art arda 3 kayiptan sonra gunun kalaninda giris yok) once her
   stratejiye tek basina, sonra secilen stratejilerin TOPLAMINA (hesap geneli, `portfolio`) uygulanir.
   Ic orneklem yalnizca ayrim anindan ONCE kapanmis islemlerden olusur; ayrimi asan islemler iki doneme de
   sayilmaz (`straddle`). Veri sonunda acik kalan islemler ortalamaya girmez; anlik R toplamlari `open_r` olarak
   ayrica verilir.
   Eski masanin gercek kodundan tasinan stratejiler (v13 SMC / EMA geri cekilme, WEEK TRADE) AYNI oynatmada
   kendi cikis planlariyla benzetilir (DAY: iki hedef + ilerleme kilitleri, en cok 5 gun; WEEK: hedefsiz, iz suren
   stop). Bunlarda secilecek parametre yoktur: ic ve dis orneklem yalnizca yan yana raporlanir. Ek kirilimlar:
   model, enstruman turu, kripto icin hafta sonu/hafta ici, DAY icin tetik mumu hacmi, WEEK TRADE icin asiri uzama.
   Maliyet kapisi (canlidaki ayarla ayni): giristeki spread stop mesafesinin `max_spread_stop_pct`'inden buyukse
   islem ACILMAZ. Bu islemler yine benzetilir ama toplamlara girmez ve sonraki sinyali engellemez; strateji basina
   kac islemin kapiya takildigi ve acilsalardi ne olacagi `cost_gate` altinda raporlanir (V9 icin de).
B) V9 stratejileri: canlidaki degerlendirme her M15 kapanisinda calisir (pahalidir; sure siniri dolunca kalan
   semboller sonraki calismaya kalir, biten semboller yeniden hesaplanmaz). Her aday iki stopla benzetilir:
   kendi stopu ve "en az 1,5 x gunluk ATR" stopu.
Hicbir esik sonuca gore degistirilmez. Sonuc yalnizca sayilar ve R'dir.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import multiprocessing
import os
import sqlite3
import statistics
import sys
import time
from pathlib import Path

from . import backtest, week_replica
from .backtest import History
from .exness.schema import Account, Instrument
from .signals import outcome
from .signals.modules import Context, modules
from .signals.modules.indicators import atr
from .signals.modules.strategies import v13

VERSION = "ft-6"
TARGETS = (1.5, 2.0, 2.5)
SWING_IDS = ("tb_smc_sweep_v1", "tb_emapb_h1_20_21_v1", "tb_emapb_h1_21_50_v1")
EMA_IDS = SWING_IDS[1:]
PLAN_IDS = ("tb_smc_day_v13", "tb_emapb_day_v13", "tb_smc_week_v13", "tb_emapb_week_v13", "tb_week_trade_v1")
PLAN_KEY = "plan"
# Canlida golgede izlenen M15 stratejileri: ayni kuralla (sabit stop, 2R hedef, en cok 96 mum) 90 gunde olculur.
FIXED_IDS = ("tb_ema_pullback_v1", "tb_donchian_breakout_v1")
FIXED_TARGET_R = 2.0
VOLUME_OK = 0.7  # eski masanin hacim kurali: tetik mumu / 20 mum ortalamasi bunun altindaysa zayif
WEEK_TIMEOUT = 7 * 86400.0
MAX_PER_DAY = 5
LOSS_STREAK = 3
MIN_TRADES_TO_SELECT = 15  # ic orneklemde bundan az islemi olan secenek secilmez
DAILY_ATR_MULT = 1.5
DAY = 86400.0
WARMUP_DAYS = {"M15": 6, "H1": 20, "H4": 60, "D1": 185}
DURATIONS = {"M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}


class Spreads:
    """Sembol ve saate gore spread: olculmus saatlik medyan; o saat olculmediyse sembolun genel medyani."""

    def __init__(self, profile: dict):
        self._profile = profile

    def has(self, symbol: str) -> bool:
        return symbol in self._profile

    def at(self, symbol: str, moment: float) -> float:
        entry = self._profile[symbol]
        hour = int(moment // 3600) % 24
        hours = entry["hours"]
        return float(hours.get(str(hour), hours.get(hour, entry["all"])))

    def coverage(self) -> dict:
        hours = [len(entry["hours"]) for entry in self._profile.values()]
        return {"symbols": len(hours), "hours_measured_median": statistics.median(hours) if hours else 0}


def read_history(path: Path, symbol: str) -> History:
    history, grouped = History(), {}
    db = sqlite3.connect(path)
    try:
        for tf, at, o, h, low, c, volume in db.execute(
                "SELECT tf, time, open, high, low, close, volume FROM bars WHERE symbol = ? ORDER BY tf, time",
                (symbol,)):
            grouped.setdefault(tf, []).append({"time": at, "open": o, "high": h, "low": low, "close": c,
                                               "tick_volume": volume or 0})
    finally:
        db.close()
    for tf, bars in grouped.items():
        history.add(symbol, tf, bars)
    return history


def _closed(history: History, symbol: str, tf: str, now: float, count: int) -> list[dict]:
    """`now` aninda KAPANMIS son `count` mum (olusmakta olan mum asla verilmez)."""
    times = history._times.get((symbol, tf))
    if not times:
        return []
    end = bisect.bisect_right(times, now - DURATIONS[tf])
    return history._bars[(symbol, tf)][max(0, end - count):end]


# ---------------------------------------------------------------- A) swing ailesi
def h4_state(history: History, symbol: str):
    """`an` -> o anda kapanmis 4H mumlarindan ATR ve son ONAYLI donus noktalari (iz suren stop icin)."""
    bars = history.all(symbol, "H4")
    if not bars:
        return lambda moment: None
    frame = v13.Frame(bars)
    highs, lows = v13.swings(frame, 3)
    closes = [bar["time"] + DURATIONS["H4"] for bar in bars]

    def state(moment: float) -> dict | None:
        last = bisect.bisect_right(closes, moment) - 1  # son kapanmis mumun indeksi
        if last < 14:
            return None
        # Donus noktasi ancak sagindaki 3 mum kapaninca bilinir.
        high = bisect.bisect_right(highs, last - 3) - 1
        low = bisect.bisect_right(lows, last - 3) - 1
        return {"atr": frame.atr[last],
                "high": (closes[highs[high] + 3], frame.H[highs[high]]) if high >= 0 else None,
                "low": (closes[lows[low] + 3], frame.L[lows[low]]) if low >= 0 else None}

    return state


def _simulate_planned(signal, entry: float, now: float, after: list[dict], state, spread_at) -> dict | None:
    kind = signal.plan["type"]
    if kind == "DAY":
        return outcome.simulate_plan(signal.side, entry, signal.stop, signal.plan["tp1"], signal.plan["tp2"], now,
                                     after, spread_at=spread_at)
    if kind == "WEEKTRADE":  # +1R'de girise, +2R'de +1R kilit, sonra en iyi - 2 x 4H ATR; 7 gunde +1R yoksa cik
        fixed = {"atr": signal.plan["atr4"]}  # kaynak kod: ATR giriste sabitlenir (giristen once kapanmis mum)
        return outcome.simulate_trail(signal.side, entry, signal.stop, now, after, lambda moment: fixed,
                                      spread_at=spread_at, lock=(2.0, 1.0), trail_atr=2.0, timeout=WEEK_TIMEOUT)
    return outcome.simulate_trail(signal.side, entry, signal.stop, now, after, state, spread_at=spread_at,
                                  structure=True)  # v13 WEEK: +1R'de girise, sonra 4H yapisinin arkasindan


def swing_trades(symbol: str, kind: str, history: History, spreads: Spreads, start: float, end: float,
                 max_cost: float | None = None) -> list[dict]:
    """Bir sembolde swing stratejilerinin butun sinyalleri; her biri kendi cikis planiyla benzetilmis.

    `max_cost`: maliyet kapisi (spread / stop orani). Ustundeki islem `cost_blocked` isaretiyle kaydedilir ve
    ayni stratejinin sonraki sinyalini engellemez (gercekte acilmayacagi icin)."""
    active = [m for m in modules("strategy") if m.id in SWING_IDS + PLAN_IDS + FIXED_IDS]
    state = h4_state(history, symbol)
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
            upper = {"H1": _closed(history, symbol, "H1", now, 256), "H4": _closed(history, symbol, "H4", now, 120),
                     "D1": _closed(history, symbol, "D1", now, 120)}
        context = Context(symbol=symbol, now=now, kind=kind,
                          bars={"M15": m15_all[index - 3:index + 1], **upper})
        wide = None  # M15 stratejileri icin genis pencere (yalnizca gerektiginde kurulur)
        for module in active:
            if now < open_until[module.id]:
                continue  # ayni stratejinin bu semboldeki islemi hala acik
            if module.id in FIXED_IDS:
                if wide is None:
                    wide = Context(symbol=symbol, now=now, kind=kind,
                                   bars={**upper, "M15": m15_all[max(0, index - 255):index + 1]})
                signal = module.evaluate(wide)
            else:
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
            spread_at = lambda moment: spreads.at(symbol, moment)  # noqa: E731
            results, extra = {}, {}
            if module.id in FIXED_IDS:
                target = entry + sign * FIXED_TARGET_R * risk
                result = outcome.simulate_fixed(signal.side, entry, signal.stop, target, now, after,
                                                spread_at=spread_at)
                results[PLAN_KEY] = [result["r"], result["closed_at"], None]
                reference = result["closed_at"]
                extra = {"kind": kind, "model": "sabit 2R", "exit": result["first"], "mfe_r": result["mfe_r"],
                         "weekend": (int(now // DAY) + 3) % 7 >= 5}
            elif signal.plan is None:
                for target in TARGETS:
                    result = outcome.simulate_swing(signal.side, entry, signal.stop, target, now, after,
                                                    spread_at=spread_at)
                    results[str(target)] = [result["r"], result["closed_at"], result.get("open_r")]
                reference = results["2.0"][1]
            else:
                result = _simulate_planned(signal, entry, now, after, state, spread_at)
                if result is None:
                    continue
                results[PLAN_KEY] = [result["r"], result["closed_at"], result.get("open_r")]
                reference = result["closed_at"]
                extra = {"kind": kind, "model": signal.plan.get("model"), "score": signal.plan.get("score"),
                         "volume_ratio": signal.plan.get("volume_ratio"), "stretch": signal.plan.get("stretch"),
                         "weekend": (int(now // DAY) + 3) % 7 >= 5, "exit": result["first"]}  # 1970-01-01 persembe
            daily = atr(upper["D1"])
            blocked = max_cost is not None and spread / risk > max_cost
            trades.append({"strategy_id": module.id, "symbol": symbol, "side": signal.side, "at": now,
                           "results": results, "spread_r": round(spread / risk, 4), "cost_blocked": blocked,
                           "stop_daily_atr": round(risk / daily, 2) if daily else None, **extra})
            if blocked:
                continue  # islem acilmadi: strateji bu sembolde mesgul sayilmaz
            open_until[module.id] = reference if reference is not None else float("inf")
    return trades


def _target(trade: dict, target) -> str:
    return target if isinstance(target, str) else target[trade["strategy_id"]]


def apply_rules(trades: list[dict], target) -> list[dict]:
    """Portfoy kurallari (zaman sirasiyla): gunde en cok 5 giris; art arda 3 kayip KAPANDIYSA o gunun kalaninda
    giris yok. Yalnizca giris aninda bilinen (kapanmis) sonuclar kullanilir. `target`: hedef anahtari ya da
    strateji -> hedef anahtari sozlugu (verilen islemlerin tamami tek portfoy sayilir)."""
    accepted: list[dict] = []
    per_day: dict[int, int] = {}
    for trade in sorted(trades, key=lambda t: t["at"]):
        day = int(trade["at"] // DAY)
        if per_day.get(day, 0) >= MAX_PER_DAY:
            continue
        closed = sorted((t["results"][_target(t, target)][1], t["results"][_target(t, target)][0]) for t in accepted
                        if t["results"][_target(t, target)][1] is not None
                        and t["results"][_target(t, target)][1] <= trade["at"])
        streak, blocked = 0, False
        for closed_at, r in closed:
            streak = streak + 1 if r is not None and r < 0 else 0
            if streak >= LOSS_STREAK and int(closed_at // DAY) == day:
                blocked = True  # ucuncu kayip bugun kapandi: sonradan kazanc kapansa da gun kapali kalir
        if blocked:
            continue
        accepted.append(trade)
        per_day[day] = per_day.get(day, 0) + 1
    return accepted


def stats(values: list[float | None], open_values: list[float | None] = ()) -> dict:
    closed = [v for v in values if v is not None]
    marks = [v for v in open_values if v is not None]
    gains, losses = sum(v for v in closed if v > 0), -sum(v for v in closed if v < 0)
    peak = total = drawdown = 0.0
    for value in closed:  # degerler giris sirasiyla gelir
        total += value
        peak = max(peak, total)
        drawdown = min(drawdown, total - peak)
    return {"trades": len(values), "open": len(values) - len(closed), "wins": sum(1 for v in closed if v > 0),
            "flat": sum(1 for v in closed if v == 0), "losses": sum(1 for v in closed if v < 0),
            "sum_r": round(sum(closed), 2), "avg_r": round(statistics.fmean(closed), 3) if closed else None,
            "open_r": round(sum(marks), 2), "pf": round(gains / losses, 2) if losses > 0 else None,
            "max_dd": round(drawdown, 2)}


def _periods(trades: list[dict], split: float, value, closed_at, open_r=lambda t: None) -> dict:
    """Ic orneklem: ayrimdan once ACILIP ayrima kadar KAPANMIS islemler (sonucu ikinci donemin fiyatina
    dayanan islem secime karismaz). Dis orneklem: ayrimdan sonra acilanlar. Ikisine de girmeyenler: straddle."""
    trades = sorted(trades, key=lambda t: t["at"])
    early = [t for t in trades if t["at"] < split]
    inside = [t for t in early if closed_at(t) is not None and closed_at(t) <= split]
    late = [t for t in trades if t["at"] >= split]
    return {"is": stats([value(t) for t in inside]),
            "oos": stats([value(t) for t in late], [open_r(t) for t in late if value(t) is None]),
            "all": stats([value(t) for t in trades], [open_r(t) for t in trades if value(t) is None]),
            "straddle": len(early) - len(inside)}


def _swing_periods(rows: list[dict], split: float, target) -> dict:
    return _periods(rows, split, lambda t: t["results"][_target(t, target)][0],
                    lambda t: t["results"][_target(t, target)][1], lambda t: t["results"][_target(t, target)][2])


def cost_gate(everything: list[dict], key) -> dict:
    """Maliyet kapisina takilan islemler: sayi, oran ve acilsalardi sonuclari (R)."""
    blocked = sorted((t for t in everything if t.get("cost_blocked")), key=lambda t: t["at"])
    return {"signals": len(everything), "blocked": len(blocked),
            "blocked_pct": round(100.0 * len(blocked) / len(everything), 1) if everything else None,
            "would_have": stats([key(t) for t in blocked])}


def summarize_swing(everything: list[dict], split: float) -> dict:
    out: dict = {"strategies": {}, "selected": {}}
    trades = [t for t in everything if not t.get("cost_blocked")]  # toplamlar yalnizca ACILAN islemlerden
    for strategy_id in SWING_IDS:
        rows = [t for t in trades if t["strategy_id"] == strategy_id]
        table = {}
        for target in (str(t) for t in TARGETS):
            table[target] = {"raw": _swing_periods(rows, split, target),
                             "rules": _swing_periods(apply_rules(rows, target), split, target)}
        spreads = [t["spread_r"] for t in rows]
        stops = [t["stop_daily_atr"] for t in rows if t["stop_daily_atr"] is not None]
        out["strategies"][strategy_id] = {
            "cost_gate": cost_gate([t for t in everything if t["strategy_id"] == strategy_id],
                                   lambda t: t["results"]["2.0"][0]),
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
    out["planned"] = {strategy_id: summarize_planned([t for t in trades if t["strategy_id"] == strategy_id], split)
                      for strategy_id in PLAN_IDS + FIXED_IDS}
    for strategy_id in PLAN_IDS + FIXED_IDS:
        out["planned"][strategy_id]["cost_gate"] = cost_gate(
            [t for t in everything if t["strategy_id"] == strategy_id], lambda t: t["results"][PLAN_KEY][0])
    # Hesap geneli: secilen stratejiler tek portfoy; gunluk sinir ve kayip serisi hepsine birlikte uygulanir.
    chosen = {pick["strategy_id"]: str(pick["target_r"]) for pick in out["selected"].values() if pick}
    together = [t for t in trades if t["strategy_id"] in chosen]
    out["portfolio"] = _swing_periods(apply_rules(together, chosen), split, chosen) if chosen else None
    return out


def _split(rows: list[dict], split: float, label) -> dict:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        name = label(row)
        if name is not None:
            groups.setdefault(str(name), []).append(row)
    return {name: _swing_periods(group, split, PLAN_KEY) for name, group in sorted(groups.items())}


def summarize_planned(rows: list[dict], split: float) -> dict:
    """Parametresi secilmeyen (kaynak koddan tasinan) stratejinin ozeti: ham, portfoy kurallariyla ve kirilimlar."""
    spreads = [t["spread_r"] for t in rows]
    stops = [t["stop_daily_atr"] for t in rows if t["stop_daily_atr"] is not None]
    exits: dict[str, int] = {}
    for row in rows:
        exits[str(row.get("exit"))] = exits.get(str(row.get("exit")), 0) + 1
    out = {"raw": _swing_periods(rows, split, PLAN_KEY),
           "rules": _swing_periods(apply_rules(rows, PLAN_KEY), split, PLAN_KEY),
           "spread_r_median": round(statistics.median(spreads), 4) if spreads else None,
           "stop_daily_atr_median": round(statistics.median(stops), 2) if stops else None,
           "buy": sum(1 for t in rows if t["side"] == "BUY"), "sell": sum(1 for t in rows if t["side"] == "SELL"),
           "exits": exits,
           "by_model": _split(rows, split, lambda t: t.get("model")),
           "by_kind": _split(rows, split, lambda t: t.get("kind")),
           "crypto_week": _split([t for t in rows if t.get("kind") == "crypto"], split,
                                 lambda t: "weekend" if t.get("weekend") else "weekday"),
           "volume": _split(rows, split, lambda t: None if t.get("volume_ratio") is None
                            else ("ok" if t["volume_ratio"] >= VOLUME_OK else "low")),
           "stretch": _split(rows, split, lambda t: None if t.get("stretch") is None
                             else ("stretched" if t["stretch"] else "normal"))}
    return out


# ---------------------------------------------------------------- B) V9
class _Rates:
    def __init__(self, bounds):
        self._bounds = bounds


def wide_distance(risk: float, daily_atr: float) -> float:
    """Genis stop: V9'un kendi stop mesafesi ya da 1,5 x gunluk ATR; hangisi uzaksa (stop asla yaklasmaz)."""
    return max(risk, DAILY_ATR_MULT * daily_atr)


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
    max_cost = float(job["max_spread_stop_pct"]) / 100.0 if job.get("max_spread_stop_pct") else None
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
            distance = wide_distance(risk, daily)
            wide = outcome.simulate(c.side, c.entry, c.entry - sign * distance, c.entry + sign * 2 * distance,
                                    c.entry + sign * 3 * distance, clock.now,
                                    before + m15[index + 1:index + 1 + outcome.SWING_MAX_BARS], spread=spread,
                                    **job["rules"])
        if base is None:
            errors += 1
            continue
        blocked = bool(max_cost is not None and risk > 0 and spread / risk > max_cost)
        trades.append({"strategy_id": c.strategy_id, "symbol": symbol, "side": c.side, "at": clock.now,
                       "cost_blocked": blocked,
                       "r": base["r"], "closed_at": base["closed_at"], "open_r": base.get("open_r"),
                       "wide_r": wide["r"] if wide else None, "wide_closed_at": wide["closed_at"] if wide else None,
                       "wide_open_r": wide.get("open_r") if wide else None,
                       "wide_open": wide is not None and wide["r"] is None,
                       "spread_r": round(spread / risk, 4) if risk > 0 else None})
        if not blocked:  # kapiya takilan islem acilmadi: sembol mesgul sayilmaz
            open_until = base["closed_at"] if base["closed_at"] is not None else float("inf")
    return {"symbol": symbol, "done": done, "trades": trades, "evaluations": evaluations, "errors": errors}


def summarize_v9(everything: list[dict], split: float) -> dict:
    out = {}
    trades = [t for t in everything if not t.get("cost_blocked")]
    names = sorted({t["strategy_id"] for t in everything}) + ["all"]
    for name in names:
        rows = trades if name == "all" else [t for t in trades if t["strategy_id"] == name]
        full = everything if name == "all" else [t for t in everything if t["strategy_id"] == name]
        wide = [t for t in rows if t["wide_r"] is not None or t["wide_open"]]
        spreads = [t["spread_r"] for t in rows if t["spread_r"] is not None]
        out[name] = {"base": _periods(rows, split, lambda t: t["r"], lambda t: t["closed_at"], lambda t: t["open_r"]),
                     "wide_stop": _periods(wide, split, lambda t: t["wide_r"], lambda t: t["wide_closed_at"],
                                           lambda t: t["wide_open_r"]),
                     "spread_r_median": round(statistics.median(spreads), 4) if spreads else None,
                     "cost_gate": cost_gate(full, lambda t: t["r"])}
    return out


# ---------------------------------------------------------------- is
def run_job(job_path: Path, pool_factory=None) -> dict:
    job = json.loads(job_path.read_text())
    folder = job_path.parent
    spreads = Spreads(job["spreads"])
    symbols = [row["symbol"] for row in job["instruments"] if spreads.has(row["symbol"])]
    kinds = {row["symbol"]: row["kind"] for row in job["instruments"]}
    began = time.time()
    signature = f"{VERSION}:{job['v9_start']}:{job['end']}:{job.get('max_spread_stop_pct')}"
    # A asamasinin imzasi girdileri de kapsar: semboller ya da spread profili degisirse yeniden hesaplanir.
    max_cost = float(job["max_spread_stop_pct"]) / 100.0 if job.get("max_spread_stop_pct") else None
    inputs = hashlib.sha1(json.dumps([symbols, job["spreads"], job["start"], max_cost],
                                     sort_keys=True).encode()).hexdigest()[:12]
    # A asamasi (swing + WEEK TRADE yeniden uretimi) ayni pencere icin bir kez hesaplanir; V9 turlari yeniden kullanir.
    cached = folder / "swing.json"
    first = None
    if cached.exists():
        try:
            first = json.loads(cached.read_text())
        except ValueError:
            first = None
        if not isinstance(first, dict) or first.get("signature") != f"{signature}:{inputs}":
            first = None
    if first is None:
        swing: list[dict] = []
        for symbol in symbols:
            history = read_history(Path(job["history"]), symbol)
            swing += swing_trades(symbol, kinds[symbol], history, spreads, job["start"], job["end"], max_cost)
        long_bars = {}
        for symbol in week_replica.SYMBOLS:
            if spreads.has(symbol):
                history = read_history(Path(job["history"]), symbol)
                long_bars[symbol] = {"H4": [b for b in history.all(symbol, "H4") if b["time"] + 14400 <= job["end"]],
                                     "D1": history.all(symbol, "D1")}
        try:
            replica = week_replica.report(long_bars, spreads.at, job["end"])
        except Exception as exc:  # noqa: BLE001 - yeniden uretim hatasi ana olcumu dusurmez
            replica = {"error": type(exc).__name__}
        first = {"signature": f"{signature}:{inputs}", "swing": summarize_swing(swing, job["split"]),
                 "week_replica": replica, "swing_seconds": round(time.time() - began, 1)}
        if "error" not in replica:  # hatali sonuc saklanmaz: sonraki turda yeniden denenir
            cached.write_text(json.dumps(first))
    summary = {"version": VERSION, "from": job["start"], "to": job["end"], "split": job["split"],
               "max_spread_stop_pct": job.get("max_spread_stop_pct"),
               "v9_from": job["v9_start"], "spread_profile": spreads.coverage(),
               "swing": first["swing"], "week_replica": first["week_replica"],
               "swing_seconds": first["swing_seconds"], "symbols": len(symbols)}
    # V9: biten semboller dosyada durur; yalnizca eksikler calisir. `skip_v9`: yalnizca A asamasi (erken sonuc).
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
    for stale in folder.glob("v9-*.json"):  # baska pencereye/surume ait eski dosyalar
        if stale.name[3:-5] not in done:
            stale.unlink(missing_ok=True)
    todo = [] if job.get("skip_v9") else [symbol for symbol in symbols if symbol not in done]
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
