"""Application orchestration. Providers fetch; existing deterministic engines decide."""
from dataclasses import asdict
import json
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING

from market_ai.engines import analysis as aggregation, mtf as mtf_engine
from .decision_record import record_analysis, AnalysisConfig, _record
from .technical_adapter import TIMEFRAME_MS, compute_technical
from .narrative import build_safe_scenarios
from .spot_provider import ProviderUnavailable, FixtureSpotProvider
from .api_models import AnalysisResponse, Levels
from .errors import V2Error
from .analysis_diagnostics import compute_diagnostics
from . import domain_journal as domain
from .paper_risk import _amount


VERSION = "v2-product-analysis-3"
from .strategies import STRATEGIES, TREND



def decimal_text(value):
    return format(Decimal(str(value)), "f")


class AnalysisService:
    def __init__(self, database, provider, ledger, clock):
        self.db, self.provider, self.ledger, self.clock = database, provider, ledger, clock
        self.provider_status = "not_probed"

    def analyze(self, request, *, commit_guard=None):
        if request.auto_paper and request.risk_portfolio != "AUTO":
            raise V2Error("INVALID_AUTO_ACCOUNT", "AUTO placement requires risk_portfolio=AUTO", 422)
        if request.data_mode != self.db.mode:
            raise V2Error("DATA_MODE_MISMATCH", "Request mode must match this runtime and database", 422)
        if request.market != "crypto_spot" or request.symbol in ("EURUSD", "XAUUSD"):
            raise V2Error("MARKET_UNAVAILABLE", "A verified provider/calendar is not configured for this market", 503)
        args = request.model_dump(mode="json")
        if request.profile_id is None:
            args.pop('profile_id', None)  # Preserve legacy idempotency digests exactly.
        profile = None
        with self.db.transaction() as c:
            previous = self.db.command(c, "analyze", request.idempotency_key, args)
            if previous is not None:
                return AnalysisResponse.model_validate(previous)
        if request.profile_id is not None:
            with self.db.transaction() as c:
                _,profile = self.profiles.get(c,request.risk_portfolio,request.profile_id)
            if request.timeframe != profile.setup_timeframe or not set(profile.timeframes).issubset({request.timeframe,*request.timeframes}):
                raise V2Error('PROFILE_TIMEFRAME_MISMATCH','Request must include the selected profile timeframe roles',422)
        now = self.clock()
        tfs = sorted(set([request.timeframe, *request.timeframes]), key=TIMEFRAME_MS.get)
        records, snapshots, technical, errors = {}, {}, {}, []
        batches = {}
        price, price_time, identity = None, None, None
        market_rules = {}
        provider = self.provider
        if type(provider) is FixtureSpotProvider and provider.case != request.fixture_case:
            provider = FixtureSpotProvider(request.fixture_case)
        warnings = ["Conditional heuristic scenario; not a validated probability or trade recommendation.",
                    "News/calendar, order book, funding and liquidation feeds are unavailable."]
        try:
            market_rules = provider.rules(request.symbol)
            for key in ("quantity_step", "minimum_quantity", "maximum_quantity", "minimum_notional", "price_tick"):
                if not _amount(Decimal(market_rules[key]), positive=True):
                    raise ProviderUnavailable("invalid_instrument_rules")
            for tf in tfs:
                frame_errors_start = len(errors)
                bars = tuple(provider.candles(request.symbol, tf, now))
                batches[tf] = bars
                if not bars:
                    raise ProviderUnavailable("empty_closed_candles")
                if len(bars) < 250:
                    errors.append(tf + ":strategy_warmup_incomplete")
                expected = (request.symbol, "crypto_spot", provider.venue, "last", "spot", "USDT")
                actual = tuple(asdict(bars[0].instrument).values())
                # Instrument field order is symbol,market,venue,price_kind,contract_type,quote_currency.
                if actual != expected or any(b.instrument != bars[0].instrument for b in bars):
                    errors.append(tf + ":instrument_mismatch")
                if any(b.open_time_ms % TIMEFRAME_MS[tf] or b.close_time_ms % TIMEFRAME_MS[tf] for b in bars):
                    errors.append(tf + ":timeframe_alignment")
                if any(b.source != provider.source_name for b in bars):
                    errors.append(tf + ":provider_source_mismatch")
                if identity is not None and identity != (bars[0].instrument, bars[0].source):
                    errors.append(tf + ":cross_timeframe_identity")
                identity = (bars[0].instrument, bars[0].source)
                record = record_analysis(bars, STRATEGIES, config=AnalysisConfig(
                    "provider-closed-bars-1", VERSION, tf, now, TIMEFRAME_MS[tf], "off_hours", True))
                records[tf] = record
                payload = record.payload()
                if not payload["routing"]["quality"]["ok"]:
                    errors.extend(tf + ":" + i["code"] for i in payload["routing"]["quality"]["issues"])
                frame_ok = len(errors) == frame_errors_start
                snapshot = payload["technical"] if frame_ok else None
                if snapshot is None and payload["routing"]["quality"]["ok"] and frame_ok:
                    snapshot = asdict(compute_technical(bars, timeframe=tf, as_of_ms=now, max_age_ms=TIMEFRAME_MS[tf]))
                if snapshot is not None and snapshot["status"] == "available":
                    tech = json.loads(snapshot["payload_json"])
                    technical[tf] = tech
                    snapshots[tf] = aggregation.aggregate(tech, [], [], {})
                    if payload["routing"]["route"]["status"] != "selected":
                        snapshots[tf]["direction"] = "neutral"
                        snapshots[tf]["quality"]["gate_passed"] = False
                elif snapshot is not None:
                    errors.append(tf + ":technical_unavailable:" + snapshot["reason"])
                if tf == request.timeframe:
                    price_time = bars[-1].close_time_ms if isinstance(bars[-1].close_time_ms, int) else None
                    price = decimal_text(bars[-1].close) if payload["routing"]["quality"]["ok"] and frame_ok else None
            self.provider_status = "reachable"
        except (ProviderUnavailable, ArithmeticError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
            self.provider_status = "unavailable"
            market_rules = {}
            errors.append("provider_unavailable")
            warnings.append("No live replacement data was generated; source unavailable.")
        current = records.get(request.timeframe)
        base = current.payload() if current else {}
        route = base.get("routing", {}).get("route", {"status": "wait", "strategy_id": None,
                    "reason": "provider_unavailable", "eligible_strategy_ids": []})
        regime = base.get("routing", {}).get("regime", {"regime": "unknown", "direction": "neutral"})
        quality = {"ok": not errors and len(records) == len(tfs), "issues": sorted(set(errors)),
                   "timeframes": {tf: r.payload()["routing"]["quality"] for tf, r in records.items()}}
        mtf = mtf_engine.analyze(request.timeframe, snapshots)
        # Current-TF evidence is already counted by aggregation. MTF may add
        # only genuinely other-timeframe evidence, never duplicate current TA.
        mtf["evidence"] = [e for e in mtf["evidence"] if e["source"] != "mtf_current"]
        mtf["supporting_count"] = sum(e["direction"] == mtf["direction"] for e in mtf["evidence"])
        mtf["opposing_count"] = sum(e["direction"] != mtf["direction"] for e in mtf["evidence"])
        agg = aggregation.aggregate(technical[request.timeframe], [], [], {}, mtf=mtf) if request.timeframe in technical and quality["ok"] else {}
        strategy_analysis = base.get("routing", {}).get("strategy_analysis") or {}
        setup = strategy_analysis.get("assessments", {}).get(route.get("strategy_id"), {})
        strategy_evidence = []
        setup_wait_reason = None
        if quality["ok"] and route["status"] == "selected" and route["strategy_id"] != TREND:
            proposed = setup.get("direction")
            opposite = "bearish" if proposed == "bullish" else "bullish"
            # Other-TF opposing evidence vetoes the new setup; it cannot be
            # drowned out by counting correlated structure detectors repeatedly.
            conflict = any(e.get("direction") == opposite for e in mtf["evidence"])
            if setup.get("status") == "confirmed" and setup.get("levels") and not conflict:
                strategy_evidence = setup["evidence"]
                agg = {"direction": proposed, "zones": setup["levels"]}
            else:
                agg = {}
                setup_wait_reason = "mtf_strategy_conflict" if conflict else "strategy_confirmation_missing"
        if route.get("strategy_id") == TREND and agg.get("direction") in ("bullish", "bearish") and agg["direction"] != setup.get("direction"):
            agg = {}
            setup_wait_reason = "strategy_direction_conflict"
        direction, reason, levels = "WAIT", route["reason"], None
        if quality["ok"] and route["status"] == "selected" and agg.get("direction") in ("bullish", "bearish"):
            direction, reason = agg["direction"], "conditional_setup"
            z = agg["zones"]
            tick = Decimal(market_rules["price_tick"])
            rounded = {}
            for k in ("entry_low", "entry_high", "invalidation", "target_1", "target_2"):
                up = k == "entry_high" or (direction == "bearish" and k in ("invalidation", "target_1", "target_2"))
                rounded[k] = (Decimal(str(z[k]))/tick).to_integral_value(rounding=ROUND_CEILING if up else ROUND_FLOOR)*tick
            entry = rounded["entry_high"] if direction == "bullish" else rounded["entry_low"]
            risk_distance = abs(entry-rounded["invalidation"])
            rr = abs(rounded["target_1"]-entry)/risk_distance if risk_distance > 0 else Decimal(0)
            levels = Levels(**{k: decimal_text(v) for k, v in rounded.items()}, reward_risk=decimal_text(rr))
            if route["strategy_id"] != TREND and rr < Decimal("1.5"):
                direction, reason, levels = "WAIT", "strategy_reward_risk_gate", None
        elif errors:
            reason = ("provider_unavailable" if "provider_unavailable" in errors else
                      "technical_engine_unavailable" if any(":technical_unavailable:" in e for e in errors) else "data_quality_gate")
        elif route["status"] == "selected":
            reason = setup_wait_reason or "evidence_or_reward_risk_gate"
        evidence = strategy_evidence or agg.get("quality", {}).get("confluence", {}).get("evidence", [])
        diagnostics = ({"version":"v2-analysis-diagnostics-1", "status":"unavailable",
                        "reason":"data_quality_or_provider_gate", "trade_permission":False})
        if quality["ok"] and current is not None:
            diagnostics = compute_diagnostics(batches[request.timeframe], timeframe=request.timeframe,
                as_of_ms=now, max_age_ms=TIMEFRAME_MS[request.timeframe],
                tick_size=market_rules["price_tick"], source_record_id=current.record_id)
        response = AnalysisResponse(analysis_id="", version=VERSION, created_at_ms=now,
            expires_at_ms=now + min(max(3*TIMEFRAME_MS[request.timeframe], 180_000), 3_600_000),
            symbol=request.symbol, market=request.market, provider=provider.name, venue=provider.venue,
            contract_type="spot", price_kind="last", quote_currency="USDT", data_mode=self.db.mode,
            timeframe=request.timeframe, timeframes=tfs, price=price, price_time_ms=price_time,
            age_ms=now-price_time if price_time is not None else None, quality=quality, regime=regime,
            router=route, technical_methods={**strategy_analysis.get("methods", {}), "research_context":diagnostics},
            strategy_setups=strategy_analysis.get("assessments", {}), indicators=technical.get(request.timeframe, {}).get("indicators", {}), mtf=mtf,
            market_rules=market_rules,
            supporting_evidence=[e for e in evidence if e["direction"] == direction],
            conflicting_evidence=[e for e in evidence if e["direction"] in ("bullish", "bearish") and e["direction"] != direction],
            direction=direction, reason=reason, levels=levels, risk={}, risk_portfolio=request.risk_portfolio, warnings=warnings,
            scenarios=build_safe_scenarios(direction, levels.model_dump() if levels else {}))
        if any(value is None for value in response.indicators.values()):
            response.warnings.append("Some indicators are unavailable; no substitute numbers were generated.")
        with self.db.transaction() as c:
            # Recheck idempotency after provider I/O; no DB lock during network.
            domain.request(c, 'analyze', request.idempotency_key, args)
            if commit_guard is not None:
                commit_guard(c)
            previous = self.db.command(c, "analyze", request.idempotency_key, args)
            if previous is not None:
                return AnalysisResponse.model_validate(previous)
            execution_now = self.clock()
            risk = self.ledger.preview(c, response, request.risk_portfolio, execution_now)
            response.risk = risk
            if risk.get("status") != "eligible_for_paper":
                response.direction, response.reason, response.levels = "WAIT", risk.get("reason", response.reason), None
                response.scenarios = build_safe_scenarios("neutral", {})
            if profile is not None:
                control = self.profiles.evaluate(profile,response.model_dump(mode="json"))
                control['profile_record_id'] = request.profile_id
                response.technical_methods['profile_control'] = control
                if not control['passes']:
                    response.direction,response.reason,response.levels = 'WAIT','profile_filter:'+control['reason'],None
                    response.scenarios = build_safe_scenarios('neutral',{})
            record = _record({"kind": "product_analysis", "version": VERSION,
                "request_semantics": {"auto_paper": request.auto_paper},
                "source_records": {tf: r.record_id for tf, r in records.items()}, "result": response.model_dump(mode="json"),
                "policy": self.ledger.policy, "fee_rate": str(self.ledger.fee), "adverse_rate": str(self.ledger.adverse)})
            response.analysis_id = record.record_id
            existing = self.db.get(c, "analyses", response.analysis_id)
            if existing is not None:
                self.db.remember(c, "analyze", request.idempotency_key, args, existing)
                return AnalysisResponse.model_validate(existing)
            if request.auto_paper and response.direction != "WAIT":
                old_signal = c.execute("SELECT id FROM orders WHERE portfolio='AUTO' AND signal_key=?", (self.ledger.signal_key(response),)).fetchone()
                if old_signal:
                    response.auto_order_id = self.db.get(c, "orders", old_signal[0])["order_id"]
                    response.warnings.append("AUTO already has a candidate for this closed bar; no duplicate order created.")
                else:
                    order = self.ledger.place(c, "AUTO", response, request.idempotency_key + ":auto", None, execution_now)
                    response.auto_order_id = order["order_id"]
            for source_record in records.values():
                self.db.record(c, source_record)
            self.db.record(c, record)
            result = response.model_dump(mode="json")
            self.db.put(c, "analyses", response.analysis_id, result, created_ms=now)
            self.db.remember(c, "analyze", request.idempotency_key, args, result)
        return response
