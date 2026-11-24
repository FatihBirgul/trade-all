"""Causal OHLC methods v1. All events become known at a CLOSED bar timestamp.

FVG and sweeps describe price geometry, never actual institutional orders.
VWAP is a rolling 20-bar typical-price proxy (not exchange trade VWAP).
Structure uses strict 2-left/2-right pivots, available two bars after the pivot.
No method carries a probability or contributes independent duplicate votes.
"""
from decimal import Decimal as D
from .market_data_contract import validate_series

VERSION = "v2-price-action-1"
PARAMETERS = {"pivot_left_right": 2, "range_bars": 20, "vwap_bars": 20,
              "fvg_scan_bars": 50, "min_gap_atr": "0.1", "sweep_atr": "0.25"}


def number(x):
    return D(str(x))


def txt(x):
    return format(x, "f") if x is not None else None


def compute_price_action(candles, *, timeframe_ms, as_of_ms, max_age_ms):
    bars = tuple(candles)
    unavailable = lambda reason: {"status": "unavailable", "reason": reason, "version": VERSION}
    quality = validate_series(bars, timeframe_ms=timeframe_ms, as_of_ms=as_of_ms,
                              max_age_ms=max_age_ms, min_bars=25)
    if not quality.ok:
        return {"version": VERSION, "parameters": PARAMETERS.copy(),
                **{k: unavailable("data_quality_gate") for k in ("fvg", "structure", "liquidity_sweep", "vwap")}}
    o, h, l, c = ([number(getattr(b, key)) for b in bars] for key in ("open", "high", "low", "close"))
    n = len(bars)
    atr = sum(max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(n-14, n))/14
    timestamp = bars[-1].close_time_ms
    def available(**fields):
        return {"status": "available", "version": VERSION, "as_of_ms": timestamp, **fields}
    # Confirm pivots using only bars ending BEFORE the event bar. Their time of
    # availability, not their historical pivot time, determines usable evidence.
    highs, lows = [], []
    for i in range(2, n-3):
        if all(h[i] > h[j] for j in (i-2, i-1, i+1, i+2)):
            highs.append(i)
        if all(l[i] < l[j] for j in (i-2, i-1, i+1, i+2)):
            lows.append(i)
    bias = "neutral"
    if len(highs) >= 2 and len(lows) >= 2:
        if h[highs[-1]] > h[highs[-2]] and l[lows[-1]] > l[lows[-2]]:
            bias = "bullish"
        if h[highs[-1]] < h[highs[-2]] and l[lows[-1]] < l[lows[-2]]:
            bias = "bearish"
    breaks = []
    for indices, prices, direction in ((highs, h, "bullish"), (lows, l, "bearish")):
        if not indices:
            continue
        i = indices[-1]
        # The level is unbroken up to this bar: no repeated BOS each bar.
        crossed = c[-1] > prices[i] if direction == "bullish" else c[-1] < prices[i]
        unbroken = all(v <= prices[i] if direction == "bullish" else v >= prices[i] for v in c[i+3:-1])
        if crossed and unbroken:
            breaks.append({"kind": "CHoCH" if bias not in ("neutral", direction) else "BOS",
                           "direction": direction, "level": txt(prices[i]),
                           "pivot_time_ms": bars[i].close_time_ms,
                           "confirmed_at_ms": bars[i+2].close_time_ms, "event_time_ms": timestamp})
    structure = available(bias=bias, events=breaks, bucket="price_structure",
                          last_swing_high=txt(h[highs[-1]]) if highs else None,
                          last_swing_low=txt(l[lows[-1]]) if lows else None)
    gaps = []
    for i in range(max(14, n-50), n):
        direction, low, high = ("bullish", h[i-2], l[i]) if l[i] > h[i-2] else ("bearish", h[i], l[i-2])
        # Gap must be accompanied by a middle-body displacement; full mitigation
        # invalidates it, touch of near edge leaves a partially mitigated zone.
        formed_atr = sum(max(h[j]-l[j], abs(h[j]-c[j-1]), abs(l[j]-c[j-1])) for j in range(i-13,i+1))/14
        if high-low < formed_atr*D("0.1") or high <= low or abs(c[i-1]-o[i-1]) < formed_atr*D("0.5"):
            continue
        if (direction == "bullish" and c[i-1] <= o[i-1]) or (direction == "bearish" and c[i-1] >= o[i-1]):
            continue
        filled = any(l[j] <= low if direction == "bullish" else h[j] >= high for j in range(i+1, n))
        if not filled:
            gaps.append({"direction": direction, "low": txt(low), "high": txt(high),
                         "formed_at_ms": bars[i].close_time_ms})
    upper, lower = max(h[-21:-1]), min(l[-21:-1])
    up = h[-1] > upper and c[-1] < upper and h[-1]-max(c[-1], o[-1]) >= atr*D("0.25")
    down = l[-1] < lower and c[-1] > lower and min(c[-1], o[-1])-l[-1] >= atr*D("0.25")
    sweep_direction = "conflict" if up and down else "bearish" if up else "bullish" if down else "neutral"
    sweep = available(direction=sweep_direction, prior_high=txt(upper), prior_low=txt(lower),
                      extreme=txt(l[-1] if down else h[-1]) if (up or down) else None,
                      bucket="price_structure", confirmation="closed_reclaim_only_requires_follow_through")
    if any(b.volume_kind != "real" for b in bars[-20:]):
        vwap = unavailable("real_volume_required")
    else:
        volumes = [number(b.volume) for b in bars[-20:]]
        total = sum(volumes)
        value = sum((h[i]+l[i]+c[i])/3*v for i, v in zip(range(n-20, n), volumes))/total if total > 0 else None
        vwap = available(value=txt(value), volume_kind="real", window_bars=20,
                         basis="rolling_typical_price", bucket="volume") if value is not None else unavailable("zero_volume")
    return {"version": VERSION, "parameters": PARAMETERS.copy(), "atr14_sma": txt(atr),
            "fvg": available(active_gaps=gaps, bucket="price_structure"),
            "structure": structure, "liquidity_sweep": sweep, "vwap": vwap}
