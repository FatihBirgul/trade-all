"""Testler icin tekrarlanabilir sentetik piyasa: M15 rastgele yuruyus (yon degistiren egilim + seyrek sicramalar)
ve ondan turetilen H1/H4/D1 mumlari. Ayni tohum her zaman ayni seriyi verir."""
import bisect
import random

T0 = 1_700_000_000 // 86400 * 86400
DURATIONS = {"M15": 900, "H1": 3600, "H4": 14400, "D1": 86400}


def market(seed: int, days: int, flip: bool = False) -> dict[str, list[dict]]:
    rnd = random.Random(seed)
    price, drift, m15 = 100.0, 0.0, []
    for i in range(days * 96):
        if i % 600 == 0:
            drift = rnd.choice([-1, 1, 1, -1, 0]) * 0.012
        o = price
        c = o + drift + rnd.gauss(0, 0.08) * (3 if rnd.random() < 0.03 else 1)
        h = max(o, c) + abs(rnd.gauss(0, 0.05))
        low = min(o, c) - abs(rnd.gauss(0, 0.05))
        price = c
        if flip:  # fiyatin aynasi: yukselis <-> dusus
            o, h, low, c = 200 - o, 200 - low, 200 - h, 200 - c
        m15.append({"time": T0 + i * 900, "open": o, "high": h, "low": low, "close": c,
                    "tick_volume": rnd.randint(50, 150)})

    def aggregate(seconds: int) -> list[dict]:
        out: dict[int, dict] = {}
        for bar in m15:
            key = bar["time"] // seconds * seconds
            merged = out.get(key)
            if merged is None:
                out[key] = dict(bar, time=key)
            else:
                merged["high"], merged["low"] = max(merged["high"], bar["high"]), min(merged["low"], bar["low"])
                merged["close"] = bar["close"]
                merged["tick_volume"] += bar["tick_volume"]
        return list(out.values())

    return {"M15": m15, "H1": aggregate(3600), "H4": aggregate(14400), "D1": aggregate(86400)}


def closed(frames: dict, tf: str, now: int, count: int) -> list[dict]:
    """`now` aninda kapanmis son `count` mum."""
    bars = frames[tf]
    end = bisect.bisect_right([bar["time"] for bar in bars], now - DURATIONS[tf])
    return bars[max(0, end - count):end]


def context_bars(frames: dict, now: int) -> dict:
    return {"M15": closed(frames, "M15", now, 4), "H1": closed(frames, "H1", now, 256),
            "H4": closed(frames, "H4", now, 120), "D1": closed(frames, "D1", now, 120)}
