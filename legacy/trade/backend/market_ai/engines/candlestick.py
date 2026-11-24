"""Candlestick pattern detection engine.

Scans the most recent candles and returns detected patterns. Each pattern is
classified but its direction is treated as context-dependent (a hammer in an
uptrend means something different than in a downtrend).
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np


def _body(o, c):
    return abs(c - o)


def _range(h, l):
    return max(h - l, 1e-9)


def _trend_at(closes: List[float], idx: int, look: int = 10) -> str:
    start = max(0, idx - look)
    seg = closes[start : idx + 1]
    if len(seg) < 3:
        return "flat"
    if seg[-1] > seg[0] * 1.01:
        return "up"
    if seg[-1] < seg[0] * 0.99:
        return "down"
    return "flat"


def _mk(name, cls, idx, strength, context, explanation):
    return {
        "name": name,
        "classification": cls,  # bullish | bearish | neutral
        "location": int(idx),
        "strength": int(max(1, min(100, strength))),
        "context": context,
        "explanation": explanation,
    }


def detect(candles: List[dict]) -> List[Dict]:
    if len(candles) < 5:
        return []

    o = [c["open"] for c in candles]
    h = [c["high"] for c in candles]
    l = [c["low"] for c in candles]
    c = [c["close"] for c in candles]

    out: List[Dict] = []
    n = len(candles)
    # scan last 6 candles for single/double patterns, ending on last
    scan_from = max(2, n - 6)

    for i in range(scan_from, n):
        body = _body(o[i], c[i])
        rng = _range(h[i], l[i])
        upper = h[i] - max(o[i], c[i])
        lower = min(o[i], c[i]) - l[i]
        bull = c[i] > o[i]
        trend = _trend_at(c, i)
        body_ratio = body / rng

        # --- Doji family ---
        if body_ratio < 0.1:
            if upper > rng * 0.4 and lower > rng * 0.4:
                out.append(_mk("Long-legged Doji", "neutral", i, 40,
                               f"Trend: {trend}", "Open and close nearly equal with long wicks both sides — strong indecision."))
            elif lower > rng * 0.6 and upper < rng * 0.15:
                out.append(_mk("Dragonfly Doji", "bullish" if trend == "down" else "neutral", i, 55,
                               f"Trend: {trend}", "Long lower wick with open/close near the high — potential bullish reversal after a decline."))
            elif upper > rng * 0.6 and lower < rng * 0.15:
                out.append(_mk("Gravestone Doji", "bearish" if trend == "up" else "neutral", i, 55,
                               f"Trend: {trend}", "Long upper wick with open/close near the low — potential bearish reversal after a rally."))
            else:
                out.append(_mk("Doji", "neutral", i, 35, f"Trend: {trend}", "Open equals close — market indecision."))
            continue

        # --- Marubozu ---
        if body_ratio > 0.92:
            out.append(_mk("Marubozu", "bullish" if bull else "bearish", i, 70,
                           f"Trend: {trend}", "Full-bodied candle with negligible wicks — strong conviction in the direction of the close."))
            continue

        # --- Spinning Top ---
        if body_ratio < 0.35 and upper > rng * 0.25 and lower > rng * 0.25:
            out.append(_mk("Spinning Top", "neutral", i, 30, f"Trend: {trend}", "Small body between two wicks — indecision / possible pause."))

        # --- Hammer / Hanging Man ---
        if lower > body * 2 and upper < body and body_ratio < 0.4:
            if trend == "down":
                out.append(_mk("Hammer", "bullish", i, 65, "After a decline", "Long lower wick rejecting lower prices after a downtrend — bullish reversal signal."))
            elif trend == "up":
                out.append(_mk("Hanging Man", "bearish", i, 60, "After a rally", "Long lower wick after an uptrend — potential bearish reversal, needs confirmation."))

        # --- Inverted Hammer / Shooting Star ---
        if upper > body * 2 and lower < body and body_ratio < 0.4:
            if trend == "down":
                out.append(_mk("Inverted Hammer", "bullish", i, 55, "After a decline", "Long upper wick after a downtrend — potential bullish reversal, needs confirmation."))
            elif trend == "up":
                out.append(_mk("Shooting Star", "bearish", i, 65, "After a rally", "Long upper wick rejecting higher prices after an uptrend — bearish reversal signal."))

        # --- Two-candle patterns ---
        if i >= 1:
            po, pc, ph, pl = o[i - 1], c[i - 1], h[i - 1], l[i - 1]
            pbull = pc > po
            # Engulfing
            if bull and not pbull and c[i] >= po and o[i] <= pc and body > _body(po, pc):
                out.append(_mk("Bullish Engulfing", "bullish", i, 75, f"Trend: {trend}", "Current bullish body fully engulfs the previous bearish body — strong bullish reversal."))
            if not bull and pbull and o[i] >= pc and c[i] <= po and body > _body(po, pc):
                out.append(_mk("Bearish Engulfing", "bearish", i, 75, f"Trend: {trend}", "Current bearish body fully engulfs the previous bullish body — strong bearish reversal."))
            # Harami
            if pbull and not bull and o[i] < pc and c[i] > po and body < _body(po, pc):
                out.append(_mk("Bearish Harami", "bearish", i, 50, f"Trend: {trend}", "Small bearish candle inside prior bullish body — momentum stalling."))
            if not pbull and bull and o[i] > pc and c[i] < po and body < _body(po, pc):
                out.append(_mk("Bullish Harami", "bullish", i, 50, f"Trend: {trend}", "Small bullish candle inside prior bearish body — momentum stalling."))
            # Piercing / Dark Cloud
            mid_prev = (po + pc) / 2
            if not pbull and bull and o[i] < pl * 1.001 and c[i] > mid_prev and c[i] < po:
                out.append(_mk("Piercing Line", "bullish", i, 60, "After a decline", "Opens below prior low then closes above the midpoint of the prior bearish candle."))
            if pbull and not bull and o[i] > ph * 0.999 and c[i] < mid_prev and c[i] > po:
                out.append(_mk("Dark Cloud Cover", "bearish", i, 60, "After a rally", "Opens above prior high then closes below the midpoint of the prior bullish candle."))
            # Tweezers
            if abs(h[i] - ph) / _range(h[i], l[i]) < 0.001 and trend == "up":
                out.append(_mk("Tweezer Top", "bearish", i, 45, "After a rally", "Two candles with matching highs — resistance rejection."))
            if abs(l[i] - pl) / _range(h[i], l[i]) < 0.001 and trend == "down":
                out.append(_mk("Tweezer Bottom", "bullish", i, 45, "After a decline", "Two candles with matching lows — support hold."))
            # Inside / Outside bar
            if h[i] < ph and l[i] > pl:
                out.append(_mk("Inside Bar", "neutral", i, 30, f"Trend: {trend}", "Range contained within the prior candle — consolidation / breakout pending."))
            if h[i] > ph and l[i] < pl:
                out.append(_mk("Outside Bar", "bullish" if bull else "bearish", i, 40, f"Trend: {trend}", "Range engulfs prior candle — volatility expansion."))

        # --- Three-candle patterns ---
        if i >= 2:
            o1, c1 = o[i - 2], c[i - 2]
            o2, c2 = o[i - 1], c[i - 1]
            b1 = c1 > o1
            b2 = c2 > o2
            small_mid = _body(o2, c2) < _body(o1, c1) * 0.5
            if b1 is False and small_mid and bull and c[i] > (o1 + c1) / 2:
                out.append(_mk("Morning Star", "bullish", i, 80, "After a decline", "Bearish candle, small-bodied indecision, then a strong bullish candle — bullish reversal."))
            if b1 is True and small_mid and (not bull) and c[i] < (o1 + c1) / 2:
                out.append(_mk("Evening Star", "bearish", i, 80, "After a rally", "Bullish candle, small-bodied indecision, then a strong bearish candle — bearish reversal."))
            if b1 and b2 and bull and c[i] > c2 > c1 and o2 > o1 and o[i] > o2:
                out.append(_mk("Three White Soldiers", "bullish", i, 78, f"Trend: {trend}", "Three consecutive strong bullish candles — sustained buying pressure."))
            if (not b1) and (not b2) and (not bull) and c[i] < c2 < c1 and o2 < o1 and o[i] < o2:
                out.append(_mk("Three Black Crows", "bearish", i, 78, f"Trend: {trend}", "Three consecutive strong bearish candles — sustained selling pressure."))

    # dedupe by (name, location), keep highest strength, sort recent-first
    seen = {}
    for p in out:
        key = (p["name"], p["location"])
        if key not in seen or p["strength"] > seen[key]["strength"]:
            seen[key] = p
    result = sorted(seen.values(), key=lambda p: (-p["location"], -p["strength"]))
    return result[:8]
