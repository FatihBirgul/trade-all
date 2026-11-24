"""Analysis aggregation engine.

Combines the deterministic outputs (technical indicators, market structure,
candlestick + chart patterns, volume, volatility, news sentiment) into a single
structured analysis object with component scores and a final analytical score.

The final number is explicitly an *analytical confidence*, NOT a statistically
proven probability. The data structures leave room for future calibration from
backtesting (see `calibration` field).
"""
from __future__ import annotations

from typing import Dict, List


def _clip(v, lo=-100, hi=100):
    return max(lo, min(hi, v))


def _trend_score(ind: Dict, structure: Dict) -> float:
    price = ind.get("price")
    score = 0.0
    for ema_key, w in [("ema20", 12), ("ema50", 12), ("ema100", 10), ("ema200", 16)]:
        e = ind.get(ema_key)
        if e and price:
            score += w if price > e else -w
    # EMA stacking (fast above slow = bullish)
    e20, e50, e200 = ind.get("ema20"), ind.get("ema50"), ind.get("ema200")
    if e20 and e50 and e200:
        if e20 > e50 > e200:
            score += 20
        elif e20 < e50 < e200:
            score -= 20
    if structure.get("label") == "uptrend":
        score += 18
    elif structure.get("label") == "downtrend":
        score -= 18
    return _clip(score)


def _momentum_score(ind: Dict) -> float:
    score = 0.0
    rsi = ind.get("rsi14")
    if rsi is not None:
        if rsi > 70:
            score -= 10   # overbought, momentum stretched
        elif rsi > 55:
            score += 22
        elif rsi < 30:
            score += 8    # oversold, potential bounce
        elif rsi < 45:
            score -= 22
    hist = ind.get("macd_hist")
    if hist is not None:
        score += 25 if hist > 0 else -25
    k = ind.get("stoch_rsi_k")
    d = ind.get("stoch_rsi_d")
    if k is not None and d is not None:
        if k > d and k < 80:
            score += 15
        elif k < d and k > 20:
            score -= 15
    return _clip(score)


def _volume_score(ind: Dict, trend_score: float) -> float:
    ratio = ind.get("volume_ratio") or 1.0
    # volume confirms the direction of the trend score
    conf = 0.0
    if ratio > 1.3:
        conf = 30
    elif ratio > 1.0:
        conf = 12
    elif ratio < 0.7:
        conf = -10
    sign = 1 if trend_score >= 0 else -1
    return _clip(conf * sign)


def _volatility_score(ind: Dict) -> float:
    # Volatility is context, not direction. We return a magnitude (0..100) telling
    # how much room / risk exists. Higher ATR% = wider stops needed.
    atrp = ind.get("atr_pct")
    if atrp is None:
        return 0
    if atrp > 6:
        return 80
    if atrp > 3:
        return 55
    if atrp > 1.5:
        return 35
    return 20


def _pattern_score(candles: List[Dict], charts: List[Dict]) -> float:
    score = 0.0
    for p in candles:
        w = p["strength"] / 100 * 22
        if p["classification"] == "bullish":
            score += w
        elif p["classification"] == "bearish":
            score -= w
    for p in charts:
        w = p["confidence"] / 100 * 30
        if p["classification"] == "bullish":
            score += w
        elif p["classification"] == "bearish":
            score -= w
    return _clip(score)


def _structure_score(structure: Dict) -> float:
    if structure.get("label") == "uptrend":
        return 60
    if structure.get("label") == "downtrend":
        return -60
    return 0


def build_zones(direction: str, price: float, support, resistance, atr: float) -> Dict:
    atr = atr or price * 0.01
    sup = [s["level"] for s in support] if support else []
    res = [r["level"] for r in resistance] if resistance else []

    zones = {}
    if direction == "bullish":
        entry_low = sup[0] if sup else price - atr
        entry_high = price
        t1 = res[0] if len(res) >= 1 else price + atr * 2
        t2 = res[1] if len(res) >= 2 else price + atr * 4
        inval = (sup[0] - atr) if sup else price - atr * 2
        risk = max(entry_high - inval, atr * 0.5)
        reward = t1 - entry_high
    elif direction == "bearish":
        entry_high = res[0] if res else price + atr
        entry_low = price
        t1 = sup[0] if len(sup) >= 1 else price - atr * 2
        t2 = sup[1] if len(sup) >= 2 else price - atr * 4
        inval = (res[0] + atr) if res else price + atr * 2
        risk = max(inval - entry_low, atr * 0.5)
        reward = entry_low - t1
    else:  # neutral -> show the range
        entry_low = sup[0] if sup else price - atr
        entry_high = res[0] if res else price + atr
        t1 = res[0] if res else price + atr * 2
        t2 = res[1] if len(res) >= 2 else None
        inval = sup[0] - atr if sup else price - atr * 2
        risk = atr
        reward = atr

    rr = round(reward / risk, 2) if risk and reward and risk > 0 else None

    def r(v):
        return round(v, 4) if v is not None else None

    zones = {
        "entry_low": r(min(entry_low, entry_high)),
        "entry_high": r(max(entry_low, entry_high)),
        "target_1": r(t1),
        "target_2": r(t2),
        "invalidation": r(inval),
        "risk_reward": rr if (rr is None or rr > 0) else None,
    }
    return zones


def aggregate(technical: Dict, candle_patterns: List[Dict], chart_patterns: List[Dict],
              news: Dict) -> Dict:
    ind = technical["indicators"]
    structure = technical["structure"]
    levels = technical["levels"]
    price = technical["price"]

    trend = _trend_score(ind, structure)
    momentum = _momentum_score(ind)
    volume = _volume_score(ind, trend)
    volatility = _volatility_score(ind)
    pattern = _pattern_score(candle_patterns, chart_patterns)
    struct = _structure_score(structure)
    news_score = float(news.get("sentiment", {}).get("score", 0.0)) if news else 0.0

    scores = {
        "trend": round(trend, 1),
        "momentum": round(momentum, 1),
        "volume": round(volume, 1),
        "volatility": round(volatility, 1),   # magnitude (risk context)
        "pattern": round(pattern, 1),
        "structure": round(struct, 1),
        "news": round(news_score, 1),
    }

    # Weighted directional composite (volatility excluded — it's context/risk).
    weights = {"trend": 0.28, "momentum": 0.22, "volume": 0.12,
               "pattern": 0.20, "structure": 0.14, "news": 0.04}
    final = sum(scores[k] * w for k, w in weights.items())
    final = _clip(final)

    if final > 15:
        direction = "bullish"
    elif final < -15:
        direction = "bearish"
    else:
        direction = "neutral"

    confidence = round(min(100, abs(final) + 20), 1)  # 0..100 analytical confidence

    atr = ind.get("atr14") or price * 0.01
    zones = build_zones(direction, price, levels.get("support"), levels.get("resistance"), atr)

    return {
        "direction": direction,
        "confidence": confidence,
        "final_score": round(final, 1),
        "scores": scores,
        "zones": zones,
        "calibration": {
            "method": "heuristic_v1",
            "note": "Analytical confidence derived from weighted technical components. NOT a statistically proven probability. Reserved for future backtesting calibration.",
            "sample_size": 0,
        },
    }
