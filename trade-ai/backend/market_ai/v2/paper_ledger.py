"""Atomic virtual spot ledger. This module has NO network or order gateway.

Execution is a conservative closed-bar simulation, not an exchange fill claim.
Cash/positions/orders/journal/event receipt commit together or all roll back.
"""
from dataclasses import asdict
from decimal import Decimal as D, Context, localcontext, ROUND_FLOOR, ROUND_HALF_EVEN
from functools import wraps
from hashlib import sha256

from .product_db import fingerprint
from . import domain_journal as domain
from .paper_risk import (PaperRiskPolicy, PaperPortfolioSnapshot, PaperSetup, OpenPaperExposure,
                         evaluate_paper_risk, DAY_MS)
from .strategy_router import RouteDecision
from .market_data_contract import Instrument
from .errors import V2Error
from .technical_adapter import TIMEFRAME_MS


ZERO = D("0")
UNIT = D("0.00000001")


def dec(value):
    return D(str(value))


def text(value):
    with localcontext(Context(prec=60, rounding=ROUND_HALF_EVEN)):
        amount = dec(value).quantize(UNIT)
        return format(ZERO.quantize(UNIT) if amount == ZERO else amount, "f")


def decimal_context(function):
    @wraps(function)
    def fixed(*args, **kwargs):
        with localcontext(Context(prec=60, rounding=ROUND_HALF_EVEN)):
            return function(*args, **kwargs)
    return fixed


class PaperLedger:
    def __init__(self, database, *, fee_bps="5", spread_bps="2", slippage_bps="1", participation="0.01"):
        self.db = database
        self.fee = dec(fee_bps) / 10000
        self.adverse = (dec(spread_bps) / 2 + dec(slippage_bps)) / 10000
        self.participation = dec(participation)
        from .equity_history import EquityHistory
        self.history = EquityHistory(self)
        self.policy = PaperRiskPolicy("demo-spot-conservative-1", D(".005"), D(".03"), D(".015"),
                                      D(".03"), D(".9"), D("1.2"), 5, 1000)

    @staticmethod
    def signal_key(analysis):
        return fingerprint({"symbol": analysis.symbol, "venue": analysis.venue, "mode": analysis.data_mode,
                            "timeframe": analysis.timeframe, "price_time_ms": analysis.price_time_ms,
                            "strategy": analysis.router.get("strategy_id")})

    @decimal_context
    def account(self, c, portfolio, now):
        account = self.db.get(c, "accounts", portfolio)
        if account is None:
            raise V2Error("PORTFOLIO_NOT_FOUND", "Unknown virtual account", 404)
        positions = self.db.rows(c, "positions", portfolio)
        orders = self.db.rows(c, "orders", portfolio)
        transactions = self.db.rows(c, "transactions", portfolio)
        opened = [p for p in positions if dec(p["quantity"]) > 0]
        reserved = sum((dec(o["remaining_quantity"]) * dec(o["reservation_per_unit"])
                        for o in orders if o["status"] in ("pending", "partially_filled")), ZERO)
        marked = sum((dec(p["quantity"]) * dec(p["mark_price"]) for p in opened), ZERO)
        unrealized = sum((dec(p["quantity"]) * dec(p["mark_price"]) - dec(p["cost_basis_quote"]) for p in opened), ZERO)
        realized = sum((dec(t["realized_pnl_quote"]) for t in transactions), ZERO)
        start = now // DAY_MS * DAY_MS
        losses = sum((-min(ZERO, dec(t["realized_pnl_quote"])) for t in transactions if t["time_ms"] >= start), ZERO)
        cash = dec(account["cash_quote"])
        return {**account, "quote_currency": "USDT", "reserved_cash_quote": text(reserved),
            "available_cash_quote": text(cash-reserved), "equity_quote": text(cash+marked),
            "realized_pnl_quote": text(realized), "unrealized_pnl_quote": text(unrealized),
            "realized_loss_today_quote": text(losses), "open_positions": len(opened),
            "pending_orders": sum(o["status"] in ("pending", "partially_filled") for o in orders)}

    def _snapshot(self, c, portfolio, now):
        a = self.account(c, portfolio, now)
        exposures = []
        for order in self.db.rows(c, "orders", portfolio):
            pending = dec(order["remaining_quantity"]) if order["status"] in ("pending", "partially_filled") else ZERO
            position = self.db.get(c, "positions", order["order_id"])
            filled = dec(position["quantity"]) if position else ZERO
            qty = pending + filled
            if qty > 0:
                exposures.append(OpenPaperExposure(portfolio, "crypto", dec(text(qty * dec(order["risk_per_unit"]))),
                                                  dec(text(qty * dec(order["reservation_per_unit"])))))
        # UTC day-start equity reconstructed from this paper ledger, not from a
        # mutable wall-clock reset. Unrealized PnL never offsets realized losses.
        day_start = now // DAY_MS * DAY_MS
        transactions = self.db.rows(c, "transactions", portfolio)
        before_day = sum((dec(t["realized_pnl_quote"]) for t in transactions if t["time_ms"] < day_start), ZERO)
        return PaperPortfolioSnapshot(portfolio, "USDT", now, day_start,
            dec(a["equity_quote"]), max(UNIT, dec(text(dec(a["seed_equity_quote"]) + before_day))),
            max(ZERO, dec(a["available_cash_quote"])), dec(a["realized_loss_today_quote"]), tuple(exposures)), a

    @decimal_context
    def preview(self, c, analysis, portfolio, now):
        if analysis.direction == "WAIT" or analysis.levels is None or not analysis.quality["ok"]:
            return {"status": "wait", "reason": analysis.reason, "policy_version": self.policy.version, "quantity": "0"}
        if analysis.price_time_ms is None or not 0 <= now-analysis.price_time_ms <= TIMEFRAME_MS[analysis.timeframe]:
            return {"status": "wait", "reason": "stale_analysis", "quantity": "0"}
        for p in self.db.rows(c, "positions", portfolio):
            if dec(p["quantity"]) > 0 and p.get("stop_triggered"):
                return {"status": "wait", "reason": "protective_exit_pending", "quantity": "0"}
            if dec(p["quantity"]) > 0 and p["status"] == "ambiguous":
                return {"status": "wait", "reason": "unresolved_ambiguity", "quantity": "0"}
            if dec(p["quantity"]) > 0 and not 0 <= now-p["mark_time_ms"] <= 120000:
                return {"status": "wait", "reason": "stale_open_position_mark", "quantity": "0"}
        for o in self.db.rows(c, "orders", portfolio):
            if o["status"] in ("pending", "partially_filled") and now-o["created_at_ms"] > 120000:
                return {"status": "wait", "reason": "paper_recovery_required", "quantity": "0"}
        snapshot, account = self._snapshot(c, portfolio, now)
        rules = analysis.market_rules
        if not rules:
            return {"status": "wait", "reason": "instrument_rules_unavailable", "quantity": "0"}
        z = analysis.levels
        # Bound both entry/exit costs at the highest relevant long-scenario price.
        cost = max(dec(z.entry_high), dec(z.target_2)) * (2*self.fee + 2*self.adverse)
        setup = PaperSetup(portfolio, analysis.router["strategy_id"],
            Instrument(analysis.symbol, analysis.market, analysis.venue, "last", "spot", "USDT"), "crypto", analysis.direction,
            *(dec(getattr(z, k)) for k in ("entry_low", "entry_high", "invalidation", "target_1", "target_2")),
            analysis.created_at_ms, analysis.expires_at_ms, dec(rules["quantity_step"]), dec(rules["minimum_quantity"]),
            dec(rules["minimum_notional"]), D("1"), dec(text(cost)), "linear", "USDT", analysis.analysis_id)
        route = RouteDecision(**{**analysis.router, "eligible_strategy_ids": tuple(analysis.router["eligible_strategy_ids"])})
        decision = evaluate_paper_risk(setup, snapshot, self.policy, route=route, as_of_ms=now,
                                       session_allowed=True, news_clear=True, emergency_paused=account["paused"])
        # Crypto-only demo policy has no economic-calendar blackout. Missing news
        # is surfaced in the analysis; this is not a verified FX/news-clear claim.
        result = asdict(decision)
        result["news_filter"] = "not_configured_optional_in_crypto_demo_policy"
        result["session_filter"] = "24x7_crypto"
        if decision.status == "eligible_for_paper":
            maximum = min(dec(rules["maximum_quantity"]), dec(rules.get("maximum_notional", "1e24"))/(dec(z.entry_high)+cost))
            step = dec(rules["quantity_step"])
            quantity = (min(dec(decision.quantity), maximum)/step).to_integral_value(rounding=ROUND_FLOOR)*step
            if quantity <= 0 or quantity < dec(rules["minimum_quantity"]) or quantity*dec(z.entry_high) < dec(rules["minimum_notional"]):
                return {"status": "wait", "reason": "instrument_size_limit", "quantity": "0"}
            result["quantity"] = text(quantity)
            result["risk_per_unit"] = text(abs(dec(z.entry_high)-dec(z.invalidation)) + cost)
            result["reservation_per_unit"] = text(dec(z.entry_high) + cost)
            result["reserved_risk_quote"] = text(quantity*dec(result["risk_per_unit"]))
            result["reserved_notional_quote"] = text(quantity*dec(result["reservation_per_unit"]))
            result["quantity_step"] = rules["quantity_step"]
        return result

    @decimal_context
    def place(self, c, portfolio, analysis, key, quantity, now):
        request = {"analysis_id": analysis.analysis_id, "quantity": str(quantity) if quantity is not None else None}
        previous = self.db.command(c, "order:"+portfolio, key, request)
        if previous is not None:
            return previous
        if portfolio == "AUTO":
            existing = c.execute("SELECT body FROM orders WHERE portfolio='AUTO' AND signal_key=?", (self.signal_key(analysis),)).fetchone()
            if existing:
                raise V2Error("AUTO_SIGNAL_ALREADY_USED", "AUTO already created a candidate for this strategy/closed bar")
        risk = self.preview(c, analysis, portfolio, now)
        if getattr(c, 'domain_session', None):
            domain.note(c, 'risk.evaluated', {'analysis_id':analysis.analysis_id, 'risk':risk,
                'policy':{k:str(v) if isinstance(v,D) else v for k,v in asdict(self.policy).items()},
                'account':self.account(c,portfolio,now)}, portfolio)
        if risk["status"] != "eligible_for_paper":
            raise V2Error("RISK_REJECTED", "Paper risk gate: " + risk["reason"])
        qty = dec(quantity) if quantity is not None else dec(risk["quantity"])
        step = dec(risk["quantity_step"])
        if (qty <= 0 or qty > dec(risk["quantity"]) or qty % step != 0
                or qty < dec(analysis.market_rules["minimum_quantity"])
                or qty*dec(analysis.levels.entry_high) < dec(analysis.market_rules["minimum_notional"])):
            raise V2Error("INVALID_PAPER_SIZE", "Quantity violates step, minimum, maximum or risk limits", 422)
        order_id = fingerprint({"portfolio": portfolio, "key": key})
        body = {"order_id": order_id, "portfolio_id": portfolio, "analysis_id": analysis.analysis_id,
                "symbol": analysis.symbol, "venue": analysis.venue, "data_mode": self.db.mode,
                "status": "pending", "quantity": text(qty), "remaining_quantity": text(qty),
                "created_at_ms": now, "expires_at_ms": analysis.expires_at_ms,
                "risk": risk, "risk_per_unit": risk["risk_per_unit"], "reservation_per_unit": risk["reservation_per_unit"],
                "quantity_step": analysis.market_rules["quantity_step"], "levels": analysis.levels.model_dump(),
                "fee_rate": text(self.fee), "adverse_rate": text(self.adverse), "participation_fraction": text(self.participation),
                "execution_model": "next_closed_bar_touch_worst_edge_v1"}
        self.db.put(c, "orders", order_id, body, portfolio=portfolio, analysis_id=analysis.analysis_id, signal_key=self.signal_key(analysis))
        self.db.remember(c, "order:"+portfolio, key, request, body)
        self.history.capture(c,portfolio,{"kind":"command","scope":"order:"+portfolio,"key":key},now)
        return body

    def _cash(self, c, portfolio, delta):
        account = self.db.get(c, "accounts", portfolio)
        cash = dec(account["cash_quote"]) + delta
        if cash < 0:
            raise V2Error("INSUFFICIENT_CASH", "Paper cash cannot become negative")
        account["cash_quote"] = text(cash)
        self.db.update(c, "accounts", portfolio, account)

    def _journal(self, c, order, position_id, event_id, kind, quantity, price, fee, delta, pnl, time_ms):
        key = fingerprint({"event": event_id, "order": order["order_id"], "kind": kind})
        body = {"transaction_id": key, "portfolio_id": order["portfolio_id"], "order_id": order["order_id"],
                "position_id": position_id, "event_id": event_id, "kind": kind, "quantity": text(quantity),
                "price": text(price), "fee_quote": text(fee), "cash_delta_quote": text(delta),
                "realized_pnl_quote": text(pnl), "time_ms": time_ms, "data_mode": self.db.mode}
        self.db.put(c, "transactions", key, body, portfolio=order["portfolio_id"], event_id=event_id)

    def _fill(self, c, order, event, event_id, available):
        z = order["levels"]
        if dec(event["low"]) > dec(z["entry_high"]) or dec(event["high"]) < dec(z["entry_low"]):
            return ZERO
        # Do not open a position into a bar that opened through invalidation.
        if dec(event["open"]) <= dec(z["invalidation"]):
            order["status"], order["remaining_quantity"] = "cancelled_gap", "0"
            self.db.update(c, "orders", order["order_id"], order)
            return ZERO
        step = dec(order["quantity_step"])
        qty = (min(dec(order["remaining_quantity"]), available) / step).to_integral_value(rounding=ROUND_FLOOR) * step
        domain.note(c, 'entry.decision', {'order_id':order['order_id'], 'quantity':text(qty),
                    'available':text(available), 'remaining':order['remaining_quantity']}, order['portfolio_id'])
        if qty <= 0:
            return ZERO
        price = dec(text(dec(z["entry_high"]) * (1+dec(order["adverse_rate"]))))
        notional = dec(text(qty*price))
        fee = dec(text(notional*dec(order["fee_rate"])))
        self._cash(c, order["portfolio_id"], -notional-fee)
        p = self.db.get(c, "positions", order["order_id"])
        if p is None:
            p = {"position_id": order["order_id"], "portfolio_id": order["portfolio_id"], "order_id": order["order_id"],
                 "symbol": order["symbol"], "data_mode": self.db.mode, "status": "open", "quantity": "0",
                 "average_entry": text(price), "cost_basis_quote": "0", "mark_price": event["close"],
                 "mark_time_ms": event["close_time_ms"], "realized_pnl_quote": "0", "opened_at_ms": event["open_time_ms"],
                 "invalidation": z["invalidation"], "target_1": z["target_1"], "target_2": z["target_2"], "tp1_done": False}
            self.db.put(c, "positions", p["position_id"], p, portfolio=order["portfolio_id"], order_id=order["order_id"])
        old_qty = dec(p["quantity"])
        p["average_entry"] = text((old_qty*dec(p["average_entry"]) + qty*price)/(old_qty+qty))
        p["quantity"] = text(old_qty+qty)
        p["cost_basis_quote"] = text(dec(p["cost_basis_quote"])+notional+fee)
        p["mark_price"], p["mark_time_ms"] = event["close"], event["close_time_ms"]
        if dec(event["low"]) <= dec(z["invalidation"]) or dec(event["high"]) >= dec(z["target_1"]):
            p["status"] = "ambiguous"
            p["ambiguity_seen"] = True
            account = self.db.get(c, "accounts", order["portfolio_id"])
            account["paused"] = True
            self.db.update(c, "accounts", order["portfolio_id"], account)
        self.db.update(c, "positions", p["position_id"], p)
        order["remaining_quantity"] = text(dec(order["remaining_quantity"])-qty)
        order["status"] = "filled" if dec(order["remaining_quantity"]) == 0 else "partially_filled"
        self.db.update(c, "orders", order["order_id"], order)
        self._journal(c, order, p["position_id"], event_id, "entry", qty, price, fee, -notional-fee, ZERO, event["close_time_ms"])
        return qty

    def _exit(self, c, position, order, qty, base_price, event_id, kind, now, *, available=None):
        if qty <= 0 or qty > dec(position["quantity"]):
            raise V2Error("INVALID_CLOSE_SIZE", "Close quantity exceeds open virtual position", 422)
        domain.note(c, 'exit.decision', {'order_id':order['order_id'], 'kind':kind, 'quantity':text(qty),
            'base_price':str(base_price), 'available':str(available) if available is not None else None,
            'before':{k:position[k] for k in ('quantity','status','invalidation','target_1','target_2','tp1_done')},
            'tp1_remaining':position.get('tp1_remaining'), 'prior_stop':bool(position.get('stop_triggered'))}, order['portfolio_id'])
        price = dec(text(base_price*(1-dec(order["adverse_rate"]))))
        gross = dec(text(qty*price))
        fee = dec(text(gross*dec(order["fee_rate"])))
        basis = dec(position["cost_basis_quote"]) if qty == dec(position["quantity"]) else dec(text(dec(position["cost_basis_quote"])*qty/dec(position["quantity"])))
        pnl = gross-fee-basis
        self._cash(c, order["portfolio_id"], gross-fee)
        position["quantity"] = text(dec(position["quantity"])-qty)
        position["cost_basis_quote"] = text(dec(position["cost_basis_quote"])-basis)
        position["realized_pnl_quote"] = text(dec(position["realized_pnl_quote"])+pnl)
        if dec(position["quantity"]) == 0:
            position["status"] = "closed"
            position["closed_at_ms"] = now
            for pending in position.get("pending_closes", []):
                if pending["status"] == "pending":
                    pending["status"] = "cancelled_position_closed"
            # Closing a partially filled order also cancels its unfilled remainder.
            if dec(order["remaining_quantity"]) > 0:
                order["remaining_quantity"], order["status"] = "0", "cancelled_remainder"
                self.db.update(c, "orders", order["order_id"], order)
        self.db.update(c, "positions", position["position_id"], position)
        self._journal(c, order, position["position_id"], event_id, kind, qty, price, fee, gross-fee, pnl, now)

    @decimal_context
    def event(self, c, event, now):
        # Public live poll and explicit fixture ingress both pass normalized
        # closed candles. Never accept a bar overlapping order creation time.
        start, end = event["open_time_ms"], event["close_time_ms"]
        domain.begin(c, effective_at=end, source={'event_id':fingerprint({'mode':self.db.mode,'symbol':event['symbol'],'open':start})})
        domain.note(c, 'market.received', {'symbol':event['symbol']})
        if (not event["is_final"] or start < 0 or end-start != 60000 or start % 60000
                or end > now or any(not dec(event[k]).is_finite() or dec(event[k]) <= 0 for k in ("open", "high", "low", "close"))
                or dec(event["high"]) < max(dec(event["open"]), dec(event["close"]))
                or dec(event["low"]) > min(dec(event["open"]), dec(event["close"]))
                or not dec(event["volume"]).is_finite() or dec(event["volume"]) < 0):
            raise V2Error("INVALID_MARKET_EVENT", "A finite, aligned and already closed 1m candle is required", 422)
        event_id = fingerprint({"mode": self.db.mode, "symbol": event["symbol"], "open": start})
        old = c.execute("SELECT hash,body,body_hash FROM events WHERE id=?", (event_id,)).fetchone()
        if old:
            if old[0] != fingerprint(event):
                raise V2Error("EVENT_CONFLICT", "A processed candle cannot be rewritten")
            domain.note(c, 'market.replayed', {'event_id':event_id})
            if getattr(c,'domain_session',None):c.domain_session.pending=None
            return self.db.decode((old[1], old[2]))
        last = c.execute("SELECT MAX(close_ms) FROM events WHERE symbol=?", (event["symbol"],)).fetchone()[0]
        if last is not None and start < last:
            raise V2Error("OUT_OF_ORDER_EVENT", "Market events must be processed in time order")
        active = [o for o in self.db.rows(c, "orders") if o["symbol"] == event["symbol"]]
        relevant = [o for o in active if o["status"] in ("pending", "partially_filled") or
                    (self.db.get(c, "positions", o["order_id"]) or {}).get("status") in ("open", "ambiguous", "exit_pending")]
        relevant.sort(key=lambda o: (0 if dec((self.db.get(c,"positions",o["order_id"]) or {}).get("quantity","0")) > 0 else 1,
                                     o["created_at_ms"], o["order_id"]))
        if relevant:
            earliest = min((o["created_at_ms"]+59999)//60000*60000 for o in relevant)
            expected = max(last if last is not None else earliest, earliest)
            if start > expected:
                raise V2Error("MARKET_EVENT_GAP", "Replay missing bars before advancing open paper risk")
        capacity = {name: dec(event["volume"])*min((dec(o["participation_fraction"]) for o in relevant
                    if o["portfolio_id"] == name), default=self.participation) for name in ("AUTO", "MANUAL")}
        touched = []
        for order in relevant:
            if start < order["created_at_ms"]:
                continue
            account = order["portfolio_id"]
            domain.note(c, "order.bar_started", {"order_id":order["order_id"]}, account)
            position = self.db.get(c, "positions", order["order_id"])
            step = dec(order["quantity_step"])
            if order["status"] in ("pending", "partially_filled") and end > order["expires_at_ms"]:
                order["status"], order["remaining_quantity"] = ("expired_remainder" if position else "expired"), "0"
                self.db.update(c, "orders", order["order_id"], order)
            if position and dec(position["quantity"]) > 0:
                position["mark_price"], position["mark_time_ms"] = event["close"], end
                # A queued manual exit is executed at a subsequent bar OPEN,
                # never at the historical mark displayed when it was requested.
                manual_changed = False
                for close in position.get("pending_closes", []):
                    if close["status"] != "pending" or start < close["created_at_ms"]:
                        continue
                    qty = (min(dec(close["remaining_quantity"]), dec(position["quantity"]), capacity[account])/step).to_integral_value(rounding=ROUND_FLOOR)*step
                    if qty <= 0:
                        continue
                    self._exit(c, position, order, qty, dec(event["open"]), event_id,
                               "manual_close:"+close["close_request_id"], end, available=capacity[account])
                    capacity[account] -= qty
                    manual_changed = True
                    close["remaining_quantity"] = text(dec(close["remaining_quantity"])-qty)
                    close["status"] = "filled" if dec(close["remaining_quantity"]) == 0 else "pending"
                if dec(position["quantity"]) <= 0:
                    for close in position.get("pending_closes", []):
                        if close["status"] == "pending":
                            close["status"] = "cancelled_position_closed"
                    self.db.update(c, "positions", position["position_id"], position)
                    touched.append({"order_id": order["order_id"], "status": "closed"})
                    continue
                if position["status"] == "ambiguous":
                    domain.note(c, "protective.blocked", {"order_id":order["order_id"], "reason":"ambiguous"}, account)
                    self.db.update(c, "positions", position["position_id"], position)
                    if manual_changed:
                        touched.append({"order_id":order["order_id"], "status":"ambiguous"})
                    continue
                prior_stop = bool(position.get("stop_triggered"))
                stop = prior_stop or dec(event["low"]) <= dec(position["invalidation"])
                target = dec(event["high"]) >= dec(position["target_1"] if not position["tp1_done"] else position["target_2"])
                # At/through the stop at bar OPEN (or an already triggered
                # market exit), sequence is known; later highs cannot undo it.
                if stop and (prior_stop or dec(event["open"]) <= dec(position["invalidation"])):
                    target = False
                domain.note(c, 'protective.evaluated', {'order_id':order['order_id'],
                    'before':{k:position[k] for k in ('quantity','status','invalidation','target_1','target_2','tp1_done')},
                    'tp1_remaining':position.get('tp1_remaining'), 'prior_stop':prior_stop,
                    'stop':stop, 'target':target, 'available':text(capacity[account])}, account)
                if stop and target:
                    position["status"], position["ambiguity_seen"] = "ambiguous", True
                    account_data = self.db.get(c, "accounts", account)
                    account_data["paused"] = True
                    self.db.update(c, "accounts", account, account_data)
                elif stop or target:
                    # Any exit cancels an unfilled entry remainder first.
                    if dec(order["remaining_quantity"]) > 0:
                        order["status"], order["remaining_quantity"] = "cancelled_remainder", "0"
                        self.db.update(c, "orders", order["order_id"], order)
                    if stop:
                        position["stop_triggered"] = True
                        qty = (min(dec(position["quantity"]), capacity[account])/step).to_integral_value(rounding=ROUND_FLOOR)*step
                        if qty > 0:
                            base = dec(event["open"]) if prior_stop else min(dec(event["open"]), dec(position["invalidation"]))
                            self._exit(c, position, order, qty, base, event_id, "stop_loss", end, available=capacity[account])
                            capacity[account] -= qty
                        if dec(position["quantity"]) > 0:
                            position["status"] = "exit_pending"
                            account_data = self.db.get(c, "accounts", account)
                            account_data["paused"] = True
                            self.db.update(c, "accounts", account, account_data)
                    else:
                        if not position["tp1_done"]:
                            desired = dec(position.get("tp1_remaining", text((dec(position["quantity"])/2/step).to_integral_value(rounding=ROUND_FLOOR)*step)))
                            if desired <= 0:
                                desired = dec(position["quantity"])
                            # A queued manual reduction can shrink the position after a
                            # volume-limited TP1. Never sell more than remains open.
                            desired = min(desired, dec(position["quantity"]))
                            qty = (min(desired, capacity[account])/step).to_integral_value(rounding=ROUND_FLOOR)*step
                            if qty > 0:
                                self._exit(c, position, order, qty, dec(position["target_1"]), event_id, "take_profit_1", end, available=capacity[account])
                                capacity[account] -= qty
                            position["tp1_remaining"] = text(desired-qty)
                            position["tp1_done"] = desired == qty
                        if position["tp1_done"] and dec(position["quantity"]) > 0 and dec(event["high"]) >= dec(position["target_2"]):
                            qty = (min(dec(position["quantity"]), capacity[account])/step).to_integral_value(rounding=ROUND_FLOOR)*step
                            if qty > 0:
                                self._exit(c, position, order, qty, dec(position["target_2"]), event_id, "take_profit_2", end, available=capacity[account])
                                capacity[account] -= qty
                self.db.update(c, "positions", position["position_id"], position)
                if (not stop and not target and order["status"] == "partially_filled"
                        and end <= order["expires_at_ms"] and not self.db.get(c, "accounts", account)["paused"]):
                    capacity[account] -= self._fill(c, order, event, event_id, capacity[account])
            elif order["status"] in ("pending", "partially_filled"):
                if end > order["expires_at_ms"]:
                    order["status"], order["remaining_quantity"] = "expired", "0"
                    self.db.update(c, "orders", order["order_id"], order)
                elif not self.db.get(c, "accounts", account)["paused"]:
                    capacity[account] -= self._fill(c, order, event, event_id, capacity[account])
            touched.append({"order_id": order["order_id"], "status": (self.db.get(c, "positions", order["order_id"]) or order)["status"]})
        result = {"event_id": event_id, "data_mode": self.db.mode, "close_time_ms": end, "processed": touched, "market_event": event}
        self.db.put(c, "events", event_id, result, hash=fingerprint(event), symbol=event["symbol"], close_ms=end)
        for account in sorted({o["portfolio_id"] for o in relevant}):
            self.history.capture(c,account,{"kind":"event","event_id":event_id},now,effective_at=end)
        if getattr(c,"domain_session",None):c.domain_session.pending=None
        return result

    @decimal_context
    def close_position(self, c, portfolio, position_id, request, now):
        args = request.model_dump(mode="json")
        scope = "close:"+portfolio+":"+position_id
        previous = self.db.command(c, scope, request.idempotency_key, args)
        if previous is not None:
            return previous
        p = self.db.get(c, "positions", position_id)
        if not p or p["portfolio_id"] != portfolio:
            raise V2Error("POSITION_NOT_FOUND", "Virtual position not found", 404)
        order = self.db.get(c, "orders", p["order_id"])
        qty = request.quantity
        pending = p.setdefault("pending_closes", [])
        reserved = sum((dec(item["remaining_quantity"]) for item in pending if item["status"] == "pending"), ZERO)
        if qty <= 0 or qty > dec(p["quantity"])-reserved or qty % dec(order["quantity_step"]) != 0:
            raise V2Error("INVALID_CLOSE_SIZE", "Quantity exceeds unreserved position size or violates step", 422)
        close_id = fingerprint({"scope": scope, "key": request.idempotency_key})
        result = {"close_request_id": close_id, "position_id": position_id, "quantity": text(qty),
                  "status": "pending", "created_at_ms": now}
        pending.append({**result, "remaining_quantity": text(qty)})
        if dec(order["remaining_quantity"]) > 0:
            order["remaining_quantity"], order["status"] = "0", "cancelled_remainder"
            self.db.update(c, "orders", order["order_id"], order)
        self.db.update(c, "positions", position_id, p)
        self.db.remember(c, scope, request.idempotency_key, args, result)
        self.history.capture(c,portfolio,{"kind":"command","scope":scope,"key":request.idempotency_key},now)
        return result
