"""Chart pattern detection engine.

Uses swing pivots + trendline geometry to detect classic chart patterns. All
detections are heuristic and returned as *signals* with a confidence score, not
guarantees. Defensive by design: any failure returns an empty list.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np


def _pivots(highs, lows, left=3, right=3):
    hi, lo = [], []
    n = len(highs)
    for i in range(left, n - right):
        wh = highs[i - left : i + right + 1]
        wl = lows[i - left : i + right + 1]
        if highs[i] == max(wh):
            hi.append((i, highs[i]))
        if lows[i] == min(wl):
            lo.append((i, lows[i]))
    return hi, lo


def _slope(points):
    if len(points) < 2:
        return 0.0
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    if xs.max() == xs.min():
        return 0.0
    return float(np.polyfit(xs, ys, 1)[0])


def _mk(name, cls, confidence, explanation, target=None):
    return {
        "name": name,
        "classification": cls,
        "confidence": int(max(1, min(100, confidence))),
        "explanation": explanation,
        "implied_target": target,
    }


def detect(candles: List[dict]) -> List[Dict]:
    try:
        return _detect(candles)
    except Exception:
        return []


def _detect(candles: List[dict]) -> List[Dict]:
    if len(candles) < 40:
        return []

    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    closes = [c["close"] for c in candles]
    price = closes[-1]

    hi_piv, lo_piv = _pivots(highs, lows)
    out: List[Dict] = []

    recent_hi = hi_piv[-5:]
    recent_lo = lo_piv[-5:]

    # --- Double Top / Bottom ---
    if len(recent_hi) >= 2:
        a, b = recent_hi[-2], recent_hi[-1]
        if abs(a[1] - b[1]) / b[1] < 0.02 and price < min(a[1], b[1]):
            out.append(_mk("Double Top", "bearish", 62,
                           "Two swing highs at a similar level with price rolling over — bearish reversal signal.",
                           target=round(price - (max(a[1], b[1]) - price), 4)))
    if len(recent_lo) >= 2:
        a, b = recent_lo[-2], recent_lo[-1]
        if abs(a[1] - b[1]) / b[1] < 0.02 and price > max(a[1], b[1]):
            out.append(_mk("Double Bottom", "bullish", 62,
                           "Two swing lows at a similar level with price recovering — bullish reversal signal.",
                           target=round(price + (price - min(a[1], b[1])), 4)))

    # --- Head & Shoulders / Inverse ---
    if len(recent_hi) >= 3:
        l, h, r = recent_hi[-3][1], recent_hi[-2][1], recent_hi[-1][1]
        if h > l and h > r and abs(l - r) / h < 0.03:
            out.append(_mk("Head and Shoulders", "bearish", 58,
                           "Central peak (head) higher than two similar peaks (shoulders) — classic bearish reversal."))
    if len(recent_lo) >= 3:
        l, h, r = recent_lo[-3][1], recent_lo[-2][1], recent_lo[-1][1]
        if h < l and h < r and abs(l - r) / (h or 1) < 0.03:
            out.append(_mk("Inverse Head and Shoulders", "bullish", 58,
                           "Central trough (head) lower than two similar troughs — classic bullish reversal."))

    # --- Trendline based: triangles / wedges / channels ---
    if len(recent_hi) >= 3 and len(recent_lo) >= 3:
        hs = _slope(recent_hi)
        ls = _slope(recent_lo)
        # normalize slopes to % per bar
        hs_n = hs / price
        ls_n = ls / price
        flat = 0.0008

        if abs(hs_n) < flat and ls_n > flat:
            out.append(_mk("Ascending Triangle", "bullish", 55, "Flat resistance with rising support — buyers stepping up, bullish bias."))
        elif hs_n < -flat and abs(ls_n) < flat:
            out.append(_mk("Descending Triangle", "bearish", 55, "Falling resistance with flat support — sellers pressing, bearish bias."))
        elif hs_n < -flat and ls_n > flat:
            out.append(_mk("Symmetrical Triangle", "neutral", 45, "Converging trendlines — a breakout is pending; direction unconfirmed."))
        elif hs_n > flat and ls_n > flat and ls_n > hs_n:
            out.append(_mk("Rising Wedge", "bearish", 50, "Both trendlines rising but converging — often resolves bearish."))
        elif hs_n < -flat and ls_n < -flat and hs_n > ls_n:
            out.append(_mk("Falling Wedge", "bullish", 50, "Both trendlines falling but converging — often resolves bullish."))
        elif abs(hs_n - ls_n) < flat and abs(hs_n) > flat:
            direction = "bullish" if hs_n > 0 else "bearish"
            out.append(_mk("Channel", direction, 45, "Parallel trendlines — price trending inside a channel."))
        elif abs(hs_n) < flat and abs(ls_n) < flat:
            out.append(_mk("Rectangle", "neutral", 40, "Horizontal support and resistance — ranging / accumulation."))

    # --- Breakout / Breakdown / Retest vs recent range ---
    window = closes[-30:]
    hi_range = max(highs[-30:])
    lo_range = min(lows[-30:])
    rng = hi_range - lo_range
    if rng > 0:
        if price >= hi_range - rng * 0.02 and closes[-2] < hi_range - rng * 0.05:
            out.append(_mk("Breakout", "bullish", 55, "Price pushing above the recent range high — bullish breakout, watch for a retest."))
        if price <= lo_range + rng * 0.02 and closes[-2] > lo_range + rng * 0.05:
            out.append(_mk("Breakdown", "bearish", 55, "Price slipping below the recent range low — bearish breakdown, watch for a retest."))

    # dedupe by name keep highest confidence
    seen = {}
    for p in out:
        if p["name"] not in seen or p["confidence"] > seen[p["name"]]["confidence"]:
            seen[p["name"]] = p
    return sorted(seen.values(), key=lambda p: -p["confidence"])[:6]
