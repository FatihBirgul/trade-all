"""Versioned setup confirmations. No network, execution, scores or probability.

Three non-trend strategies require price structure + momentum + real-volume
confirmation. FVG/BOS/sweep share ONE bucket; VWAP/volume share ONE bucket.
Common paper risk/cost geometry remains a separate veto. All thresholds are
conservative engineering definitions, not calibrated investment claims.
"""
from decimal import Decimal as D
from .price_action import compute_price_action, number, txt
from .strategy_router import StrategySpec, RouteDecision, route_strategy

VERSION = "v2-setups-1"
TREND = "trend_momentum_v2"  # Public identifier retained; continuation semantics v2.
RANGE = "range_mean_reversion_v2"
BREAKOUT = "confirmed_breakout_v2"
SWEEP = "failed_breakout_v2"
STRATEGIES = tuple(StrategySpec(name, frozenset(regimes), frozenset({"crypto_spot"}),
                                frozenset({"ohlc", "real_volume"}), priority=priority, version=version)
                   for name, regimes, priority, version in (
                       (TREND, {"trend"}, 10, "2"),
                       (RANGE, {"range"}, 20, "1"),
                       (BREAKOUT, {"trend", "breakout"}, 30, "1"),
                       (SWEEP, {"range", "trend", "reversal"}, 40, "1")))
BUILTIN_IDS = frozenset(s.strategy_id for s in STRATEGIES)
PARAMETERS = {"minimum_bars": 250, "volume_multiple": "1.5", "breakout_buffer_atr": "0.25",
              "range_edge_fraction": "0.25", "range_min_width_atr": "3",
              "range_max_efficiency": "0.3", "minimum_gross_rr": "1.5", "rsi_period": 14, "range_rsi_bounds": (45,55),
              "breakout_rsi_bounds": (20,45,55,80), "sweep_rsi_midpoint": 50}


def assess_setups(bars, *, timeframe_ms, as_of_ms, max_age_ms, regime, regime_direction):
    bars = tuple(bars)
    methods = compute_price_action(bars, timeframe_ms=timeframe_ms, as_of_ms=as_of_ms, max_age_ms=max_age_ms)
    assessments = {s.strategy_id: {"status": "wait", "reason": "warmup_or_data_unavailable",
                    "version": s.version, "direction": "neutral", "levels": None, "evidence": [],
                    "required_data": ["closed_ohlc", "real_volume"], "warmup_bars": 250, "parameters": PARAMETERS.copy()} for s in STRATEGIES}
    result = {"version": VERSION, "parameters": PARAMETERS.copy(), "methods": methods, "assessments": assessments}
    if len(bars) < 250 or any(b.volume_kind != "real" for b in bars) or methods["vwap"]["status"] != "available" or methods["structure"]["status"] != "available":
        return result
    o, h, l, c, v = ([number(getattr(b, k)) for b in bars] for k in ("open", "high", "low", "close", "volume"))
    atr = number(methods["atr14_sma"])
    if atr <= 0:
        return result
    vwap = number(methods["vwap"]["value"])
    mean_volume = sum(v[-22:-2])/20
    volume_ok = mean_volume > 0 and v[-1] >= D("1.5")*mean_volume
    def rsi_pair():
        changes = [c[i]-c[i-1] for i in range(1,len(c))]
        gain = sum(max(x,D(0)) for x in changes[:14])/14
        loss = sum(max(-x,D(0)) for x in changes[:14])/14
        values = []
        for change in changes[14:]:
            gain = (gain*13+max(change,D(0)))/14
            loss = (loss*13+max(-change,D(0)))/14
            values.append(D(100)-D(100)/(1+gain/loss) if loss else D(100) if gain else D(50))
        return values[-2:]
    prior_rsi, current_rsi = rsi_pair()
    result["momentum"] = {"rsi14_wilder": txt(current_rsi), "previous_rsi14": txt(prior_rsi)}
    for row in assessments.values():
        row["momentum"] = result["momentum"].copy()
    momentum_up = current_rsi > prior_rsi
    momentum_down = current_rsi < prior_rsi
    def candidate(name, direction, confirmed, stop=None, t1=None, t2=None, reasons=()):
        row = assessments[name]
        if regime not in next(s.regimes for s in STRATEGIES if s.strategy_id == name):
            row["reason"] = "regime_not_eligible"
            return
        row["reason"] = "entry_confirmation_missing"
        row["requirements"] = list(reasons)
        if not confirmed:
            return
        row.update(status="confirmed", reason="closed_bar_confirmation", direction=direction,
                   confirmed_at_ms=bars[-1].close_time_ms)
        if name == TREND:
            # Legacy aggregate/confluence/RR gates still required by the service.
            row["reason"] = "continuation_confirmed_requires_legacy_confluence"
            return
        entry_low, entry_high = c[-1]-atr*D("0.05"), c[-1]+atr*D("0.05")
        edge = entry_high if direction == "bullish" else entry_low
        risk = edge-stop if direction == "bullish" else stop-edge
        reward = t1-edge if direction == "bullish" else edge-t1
        geometry = (0 < stop < entry_low <= entry_high < t1 < t2 if direction == "bullish"
                    else 0 < t2 < t1 < entry_low <= entry_high < stop)
        if not geometry or risk <= 0 or reward/risk < D("1.5"):
            row.update(status="wait", reason="strategy_reward_risk_gate", direction="neutral")
            return
        row["levels"] = dict(zip(("entry_low", "entry_high", "invalidation", "target_1", "target_2"),
                                  map(txt, (entry_low, entry_high, stop, t1, t2))))
        row["evidence"] = [{"source": name+":"+bucket, "bucket": bucket, "direction": direction,
                            "confirmed": True, "as_of_ms": bars[-1].close_time_ms,
                            "label": label} for bucket, label in zip(("price_structure", "momentum", "volume"), reasons)]
    # EMA20/50 are causal from the provided snapshot, not future pivot labels.
    def ema(period):
        value = sum(c[:period])/period
        alpha = D(2)/D(period+1)
        for x in c[period:]: value += alpha*(x-value)
        return value
    fast, slow = ema(20), ema(50)
    trend_up = regime_direction == "bullish" and c[-1] > fast > slow and c[-1] > c[-2] and c[-1] > vwap
    trend_down = regime_direction == "bearish" and c[-1] < fast < slow and c[-1] < c[-2] and c[-1] < vwap
    trend_direction = "bullish" if trend_up else "bearish"
    structure_conflict = any(e["direction"] != trend_direction for e in methods["structure"]["events"])
    fvg_conflict = any(g["direction"] != trend_direction and number(g["low"]) <= c[-1] <= number(g["high"])
                       for g in methods["fvg"]["active_gaps"])
    candidate(TREND, trend_direction, regime == "trend" and (trend_up or trend_down) and not structure_conflict and not fvg_conflict,
              reasons=("EMA20/50 and regime alignment", "closed continuation", "rolling VWAP alignment"))
    upper, lower = max(h[-22:-2]), min(l[-22:-2])
    width, mid = upper-lower, (upper+lower)/2
    traveled = sum(abs(c[i]-c[i-1]) for i in range(len(c)-21, len(c)-1))
    efficiency = abs(c[-2]-c[-22])/traveled if traveled else D(0)
    bounded = regime == "range" and width >= 3*atr and efficiency <= D("0.3")
    up = l[-2] <= lower+width*D("0.25") and c[-1] > h[-2] and c[-1] < vwap and c[-1] < mid
    down = h[-2] >= upper-width*D("0.25") and c[-1] < l[-2] and c[-1] > vwap and c[-1] > mid
    candidate(RANGE, "bullish" if up else "bearish", bounded and volume_ok and (up != down) and ((up and momentum_up and current_rsi < 45) or (down and momentum_down and current_rsi > 55)),
              min(l[-2:])-atr*D("0.25") if up else max(h[-2:])+atr*D("0.25"),
              mid, upper if up else lower,
              ("range edge rejection", "Wilder RSI14 recovery below 45 / above 55", "real volume >=1.5x and VWAP reversion space"))
    buffer = atr*D("0.25")
    up = c[-2] > upper+buffer and c[-1] > upper+buffer and c[-1] > c[-2] and c[-1] > vwap
    down = c[-2] < lower-buffer and c[-1] < lower-buffer and c[-1] < c[-2] and c[-1] < vwap
    direction = "bullish" if up else "bearish"
    stop = upper-buffer if up else lower+buffer
    edge = c[-1]+atr*D("0.05") if up else c[-1]-atr*D("0.05")
    distance = abs(edge-stop)
    candidate(BREAKOUT, direction, volume_ok and (up != down) and ((up and momentum_up and 55 <= current_rsi <= 80) or (down and momentum_down and 20 <= current_rsi <= 45)), stop,
              edge+2*distance if up else edge-2*distance,
              edge+3*distance if up else edge-3*distance,
              ("two closes beyond prior 20-bar range +0.25 ATR", "Wilder RSI14 rising 55-80 / falling 20-45", "real volume >=1.5x and VWAP alignment"))
    previous = compute_price_action(bars[:-1], timeframe_ms=timeframe_ms, as_of_ms=bars[-2].close_time_ms,
                                    max_age_ms=max_age_ms)["liquidity_sweep"]
    sweep = previous.get("direction", "neutral")
    up = sweep == "bullish" and c[-1] > h[-2] and c[-1] > o[-1] and c[-1] < vwap
    down = sweep == "bearish" and c[-1] < l[-2] and c[-1] < o[-1] and c[-1] > vwap
    stop = l[-2]-buffer if up else h[-2]+buffer
    edge = c[-1]+atr*D("0.05") if up else c[-1]-atr*D("0.05")
    distance = abs(edge-stop)
    candidate(SWEEP, "bullish" if up else "bearish", volume_ok and (up != down) and ((up and momentum_up and current_rsi < 50) or (down and momentum_down and current_rsi > 50)), stop,
              edge+2*distance if up else edge-2*distance,
              edge+3*distance if up else edge-3*distance,
              ("prior closed sweep/reclaim of 20-bar extreme", "Wilder RSI14 recovery below / above 50", "real volume >=1.5x and VWAP reversion space"))
    return result


def resolve_setups(specs, setup, **kwargs):
    """Direction conflicts veto even unequal priorities. Same-direction precedence
    is sweep > confirmed breakout > range > trend, never a confidence bonus.
    Generic external specs retain the base router contract.
    """
    specs = tuple(specs)
    # Validate identities/duplicate IDs even if confirmation would filter one out.
    base = route_strategy(specs, **kwargs)
    if base.reason in ("data_quality_gate", "risk_gate", "unknown_regime", "unsupported_market_or_session"):
        return base
    candidates = [s for s in specs if (s.strategy_id not in BUILTIN_IDS or
                  setup["assessments"][s.strategy_id]["status"] == "confirmed")]
    directions = {setup["assessments"][s.strategy_id]["direction"] for s in candidates
                  if s.strategy_id in BUILTIN_IDS and s.enabled and kwargs["regime"] in s.regimes
                  and kwargs["market"] in s.markets and s.required_capabilities.issubset(kwargs["capabilities"])
                  and (not s.sessions or kwargs["session"] in s.sessions)}
    if len(directions) > 1:
        return RouteDecision("wait", None, "opposing_strategy_conflict", tuple(sorted(s.strategy_id for s in candidates)))
    result = route_strategy(candidates, **kwargs)
    if result.reason == "no_eligible_strategy" and base.eligible_strategy_ids:
        return RouteDecision("wait", None, "strategy_confirmation_missing", ())
    return result
