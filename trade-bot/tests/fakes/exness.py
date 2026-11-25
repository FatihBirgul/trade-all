"""Testler icin bellek ici Exness.

`ExnessClient` ile ayni arayuzu sunar (get/post/patch/delete) ve ham API JSON'u dondurur; boylece
`schema.py` de testlerde calisir. Emirler gercekteki gibi asenkrondur: ACK hemen doner, sonuc
`transaction_event` olarak dinleyicilere gider (`flush`). Hata enjeksiyonu icin bayraklar vardir.
"""

from __future__ import annotations

import copy
import itertools
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlsplit

from tradebot.exness.errors import ExnessRateLimited, ExnessRejected, ExnessUnavailable
from tradebot.exness.limits import RateLimiter


def iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def conditions(name, *, category="Forex", base=None, quote="USD", digits=5, contract="100000",
               vmin="0.01", vmax="200", vstep="0.01", sessions="all", exec_mode="market"):
    week = [{"trade_mode": "enabled", "week_start_time": "Mon, 00:00:00", "week_end_time": "Sun, 23:59:59"}]
    weekdays = [{"trade_mode": "enabled", "week_start_time": "Mon, 00:00:00", "week_end_time": "Fri, 23:59:59"}]
    return {"instrument": name, "category": category, "base_currency": base or name[:3], "quote_currency": quote,
            "margin_currency": base or name[:3], "point_digits": digits, "exec_mode": exec_mode,
            "calc_mode": "forex", "contract_size": contract, "volume_min": vmin, "volume_max": vmax,
            "volume_step": vstep, "trade_mode": "enabled",
            "trade_sessions": week if sessions == "all" else weekdays}


DEFAULT_INSTRUMENTS = {
    "EURUSD": conditions("EURUSD", sessions="weekdays"),
    "GBPUSD": conditions("GBPUSD", sessions="weekdays"),
    "XAUUSD": conditions("XAUUSD", category="Metals", digits=2, contract="100", sessions="weekdays"),
    "BTCUSD": conditions("BTCUSD", category="Crypto", digits=2, contract="1"),
    "AAPL": conditions("AAPL", category="Stocks", base="USD", digits=2, contract="1"),
}


class FakeExness:
    def __init__(self, *, account_id="123456", currency="USD", balance=10_000.0, instruments=None, clock=None):
        self.account_id = account_id
        self.currency = currency
        self.balance = balance
        self.instruments = copy.deepcopy(instruments or DEFAULT_INSTRUMENTS)
        self.clock = clock or (lambda: 1_800_000_000.0)
        self.limiter = RateLimiter()
        self.prices: dict[str, tuple[float, float]] = {}
        self.candles: dict[tuple[str, str], list[dict]] = {}
        self.positions: dict[str, dict] = {}
        self.orders: dict[str, dict] = {}
        self.deals: list[dict] = []
        self.operations: dict[str, dict] = {}
        self.idempotency: dict[str, tuple[str, str]] = {}
        self.requests: list[tuple[str, str, dict | None, str]] = []
        self.event_listeners: list = []
        self.tick_listeners: list = []
        self._ids = itertools.count(1000)
        self._queue: list[dict] = []  # islenmeyi bekleyen operasyonlar
        self._events: list[dict] = []  # teslim edilmeyi bekleyen olaylar
        # hata enjeksiyonu
        self.auto_process = True  # False: operasyonlar flush() cagrilana kadar 'pending' kalir
        self.drop_events = False  # True: olaylar uretilir ama teslim edilmez (WS kopuk)
        self.fail_next: Exception | None = None  # bir sonraki istek ACK'ten once bu hatayla biter
        self.lose_next_ack = False  # istek islenir ama yanit kaybolur
        self.reject_next: tuple[int, str] | None = None  # bir sonraki operasyon asenkron reddedilir
        self.account_status = "active"
        self.last_ok_at = 0.0
        self.mid_request = None  # async cagri: istek kaydedildikten sonra, yanit donmeden once calisir
        self.omit_sltp_in_event = False  # dolum olayinda SL/TP emri gelmesin (broker'da yine vardir)
        self.drop_sltp_on_open = False  # broker SL/TP emrini hic olusturmasin
        self.patch_replaces = False  # PATCH verilmeyen alani SILER (belgelenenin tersi; TP kaybi denetimi icin)

    # ------------------------------------------------------------------ yardimcilar
    def _id(self) -> str:
        return str(next(self._ids))

    def _rate(self) -> float:
        return 100.0 if self.currency == "USC" else 1.0

    def calls(self, method: str, contains: str = "") -> list:
        return [r for r in self.requests if r[0] == method and contains in r[1]]

    def _state(self) -> dict:
        floating = 0.0
        for p in self.positions.values():
            if p["state"] != "open" or p["instrument"] not in self.prices:
                continue
            bid, ask = self.prices[p["instrument"]]
            floating += self._pnl(p, bid if p["direction"] == "buy" else ask, float(p["volume"]))
        return {"balance": f"{self.balance:.2f}", "equity": f"{self.balance + floating:.2f}", "used_margin": "0.00"}

    def _pnl(self, position: dict, price: float, volume: float) -> float:
        sign = 1.0 if position["direction"] == "buy" else -1.0
        contract = float(self.instruments[position["instrument"]]["contract_size"])
        return (price - float(position["open_price"])) * sign * volume * contract * self._rate()

    def _sltp(self, position_id: str) -> dict | None:
        return next((o for o in self.orders.values() if o.get("position_id") == position_id
                     and o["order_type"] == "sltp" and o["state"] == "placed"), None)

    def set_candles(self, symbol: str, timeframe: str, rows: list[dict]) -> None:
        self.candles[(symbol, timeframe)] = [dict(r) for r in rows]

    # ------------------------------------------------------------------ fiyat ve olay akisi
    async def set_price(self, symbol: str, bid: float, ask: float | None = None, *, at: float | None = None):
        """Fiyati gunceller, tick yayinlar ve SL/TP tetiklerini isler."""
        ask = bid if ask is None else ask
        self.prices[symbol] = (bid, ask)
        tick = {"instrument": symbol, "bid": bid, "ask": ask, "timestamp": iso(at if at is not None else self.clock())}
        for listener in list(self.tick_listeners):
            await listener(tick)
        for position in list(self.positions.values()):
            if position["instrument"] != symbol or position["state"] != "open":
                continue
            order = self._sltp(position["position_id"])
            if not order:
                continue
            buy = position["direction"] == "buy"
            price = bid if buy else ask
            sl, tp = order.get("stop_loss_price"), order.get("take_profit_price")
            hit = None
            if sl is not None and (price <= float(sl) if buy else price >= float(sl)):
                hit = ("sl", float(sl))
            elif tp is not None and (price >= float(tp) if buy else price <= float(tp)):
                hit = ("tp", float(tp))
            if hit:
                self._close(position, float(position["volume"]), hit[1], reason=hit[0], operation=None)
        await self.flush()

    async def flush(self) -> None:
        """Bekleyen operasyonlari isler ve olaylari dinleyicilere teslim eder."""
        queue, self._queue = self._queue, []
        for operation in queue:
            self._execute(operation)
        events, self._events = self._events, []
        if self.drop_events:
            return
        for event in events:
            for listener in list(self.event_listeners):
                await listener(copy.deepcopy(event))

    def _emit(self, operation: dict | None, payload: dict, status="success", error=None) -> None:
        event = {"event_type": "transaction_event", "status": status, "event_time": iso(self.clock()),
                 "payload": payload}
        if operation is not None:
            event["operation_id"] = operation["operation_id"]
            event["client_request_id"] = operation["client_request_id"]
        if error:
            event["error_code"], event["error_message"] = error
        elif payload:
            payload["account_state"] = {**self._state(), "leverage": "2000"}
        self._events.append(event)

    # ------------------------------------------------------------------ istemci arayuzu
    async def resolve_host(self) -> str:
        return "https://fake.test"

    async def ws_endpoint(self, path: str):
        return "wss://fake.test" + path, {}

    async def aclose(self) -> None:
        pass

    async def _before(self, method, path, payload, key):
        self.requests.append((method, path, copy.deepcopy(payload), key))
        if self.fail_next is not None:
            error, self.fail_next = self.fail_next, None
            raise error

    async def _after(self, result):
        """Gercek agda oldugu gibi: yanit yoldayken baska olaylar islenebilir."""
        if self.mid_request is not None:
            hook, self.mid_request = self.mid_request, None
            await hook()
        self.last_ok_at = self.clock()
        return result

    async def get(self, path: str) -> dict:
        await self._before("GET", path, None, "")
        return await self._after(self._get(path))

    def _get(self, path: str) -> dict:
        url = urlsplit(path)
        query = dict(parse_qsl(url.query))
        parts = url.path.strip("/").split("/")
        if url.path.endswith("/account"):
            return {"account_id": self.account_id, "create_date": iso(0),
                    "settings": {"currency": self.currency, "leverage": "2000", "trade_mode": "enabled",
                                 "account_status": self.account_status, "execution_mode": "market"}}
        if url.path.endswith("/limits"):
            return {"limits": {"rest": {"global_account_rate": {"limit": 100000, "window_seconds": 1},
                                        "methods": [{"api_operation_id": "getCandleHistory", "http_method": "GET",
                                                     "path": "/v1/market-data/accounts/{account_id}/candles",
                                                     "rate_limit": {"limit": 100000, "window_seconds": 1},
                                                     "limits": {"max_candles_per_request": 1000}}]},
                               "websocket": {}}}
        if url.path.endswith("/instruments"):
            return {"instruments": list(self.instruments)}
        if url.path.endswith("/conditions"):
            name = parts[-2]
            if name not in self.instruments:
                raise ExnessRejected("MARKET_INSTRUMENT_NOT_FOUND", code=4000, status=404)
            return copy.deepcopy(self.instruments[name])
        if url.path.endswith("/snapshot"):
            return self.snapshot()
        if "/operations/" in url.path:
            operation = self.operations.get(parts[-1])
            if operation is None:
                raise ExnessRejected("REQUEST_OPERATION_NOT_FOUND", code=3014, status=404)
            return {k: v for k, v in operation.items() if k in
                    ("operation_id", "status", "client_request_id", "error_code", "error_message")}
        if url.path.endswith("/candles"):
            rows = self.candles.get((query["instrument"], query["timeframe"]), [])
            start = datetime.fromisoformat(query["from"]).timestamp()
            end = datetime.fromisoformat(query["to"]).timestamp()
            return {"candles": [{"time": iso(r["time"]), "open": r["open"], "high": r["high"], "low": r["low"],
                                 "close": r["close"], "volume": r.get("tick_volume", 1)}
                                for r in rows if start <= r["time"] < end]}
        if url.path.endswith("/deals"):
            start = datetime.fromisoformat(query["from"]).timestamp() if "from" in query else 0.0
            items = [{"event_time": d["create_time"], "deal": copy.deepcopy(d)} for d in self.deals
                     if datetime.fromisoformat(d["create_time"]).timestamp() >= start]
            return {"items": items, "has_more": False}
        raise ExnessRejected("REQUEST_INVALID", code=3000, status=400)

    def snapshot(self) -> dict:
        return {"orders": [copy.deepcopy(o) for o in self.orders.values() if o["state"] == "placed"],
                "positions": [copy.deepcopy(p) for p in self.positions.values() if p["state"] == "open"],
                "account_state": self._state()}

    async def post(self, path: str, payload: dict, idempotency_key: str) -> dict:
        await self._before("POST", path, payload, idempotency_key)
        kind = "open" if path.endswith("/positions") else "sltp_create"
        return await self._after(self._accept(kind, {"body": copy.deepcopy(payload)}, idempotency_key))

    async def patch(self, path: str, payload: dict, idempotency_key: str) -> dict:
        await self._before("PATCH", path, payload, idempotency_key)
        order_id = urlsplit(path).path.split("/")[-1]
        if order_id not in self.orders or self.orders[order_id]["state"] != "placed":
            raise ExnessRejected("REQUEST_ORDER_NOT_FOUND", code=3012, status=400)
        return await self._after(
            self._accept("sltp_modify", {"order_id": order_id, "body": copy.deepcopy(payload)}, idempotency_key))

    async def delete(self, path: str, idempotency_key: str) -> dict:
        await self._before("DELETE", path, None, idempotency_key)
        url = urlsplit(path)
        position_id = url.path.split("/")[-1]
        if position_id not in self.positions or self.positions[position_id]["state"] != "open":
            raise ExnessRejected("REQUEST_POSITION_NOT_FOUND", code=3013, status=400)
        volume = dict(parse_qsl(url.query)).get("volume")
        return await self._after(self._accept("close", {"position_id": position_id, "volume": volume}, idempotency_key))

    def _accept(self, kind: str, data: dict, key: str) -> dict:
        fingerprint = repr((kind, data))
        if key in self.idempotency:
            operation_id, known = self.idempotency[key]
            if known != fingerprint:
                raise ExnessRejected("REQUEST_INVALID", code=3000, status=409)
            return {"operation_id": operation_id, "client_request_id": key, "status": "accepted"}
        operation = {"operation_id": self._id(), "client_request_id": key, "status": "pending", "kind": kind, **data}
        if self.reject_next is not None:
            operation["reject"], self.reject_next = self.reject_next, None
        self.operations[operation["operation_id"]] = operation
        self.idempotency[key] = (operation["operation_id"], fingerprint)
        self._queue.append(operation)
        if self.auto_process:
            queue, self._queue = self._queue, []
            for item in queue:
                self._execute(item)
        if self.lose_next_ack:
            self.lose_next_ack = False
            raise ExnessUnavailable("ag hatasi: ReadTimeout")
        return {"operation_id": operation["operation_id"], "client_request_id": key, "status": "accepted"}

    # ------------------------------------------------------------------ operasyon isleme
    def _fail(self, operation: dict, code: int, message: str) -> None:
        operation.update(status="rejected", error_code=code, error_message=message)
        self._emit(operation, {}, status="rejected", error=(code, message))

    def _execute(self, operation: dict) -> None:
        if "reject" in operation:
            return self._fail(operation, *operation["reject"])
        handler = getattr(self, "_do_" + operation["kind"])
        handler(operation)

    def _do_open(self, operation: dict) -> None:
        body = operation["body"]
        name = body["instrument"]
        if self.account_status != "active":
            return self._fail(operation, 2002, "ACCOUNT_CLOSE_ONLY")
        if name not in self.instruments:
            return self._fail(operation, 4000, "MARKET_INSTRUMENT_NOT_FOUND")
        if name not in self.prices:
            return self._fail(operation, 4004, "MARKET_NO_QUOTES")
        bid, ask = self.prices[name]
        buy = body["side"] == "buy"
        price = ask if buy else bid
        sl, tp = body.get("stop_loss_price"), body.get("take_profit_price")
        if sl is not None and (float(sl) >= bid if buy else float(sl) <= ask):
            return self._fail(operation, 5005, "TRADING_RULE_INVALID_PRICE_LEVELS")
        now = iso(self.clock())
        position_id, order_id = self._id(), self._id()
        digits = self.instruments[name]["point_digits"]
        position = {"position_id": position_id, "direction": body["side"], "instrument": name,
                    "initial_volume": body["volume"], "volume": body["volume"],
                    "open_price": f"{price:.{digits}f}", "state": "open", "create_time": now,
                    "commission": "0", "swap": "0"}
        self.positions[position_id] = position
        market = {"order_id": order_id, "position_id": position_id, "order_type": "market", "state": "filled",
                  "direction": body["side"], "instrument": name, "price": position["open_price"],
                  "volume": body["volume"], "create_time": now}
        deal = {"deal_id": self._id(), "order_id": order_id, "position_id": position_id, "type": "open",
                "direction": body["side"], "instrument": name, "volume": body["volume"],
                "price": position["open_price"], "create_time": now}
        self.deals.append(deal)
        orders = [market]
        if (sl is not None or tp is not None) and not self.drop_sltp_on_open:
            sltp = {"order_id": self._id(), "position_id": position_id, "order_type": "sltp", "state": "placed",
                    "create_time": now}
            if sl is not None:
                sltp["stop_loss_price"] = sl
            if tp is not None:
                sltp["take_profit_price"] = tp
            self.orders[sltp["order_id"]] = sltp
            if not self.omit_sltp_in_event:
                orders.append(sltp)
        operation["status"] = "confirmed"
        self._emit(operation, {"orders": copy.deepcopy(orders), "positions": [copy.deepcopy(position)],
                               "deals": [copy.deepcopy(deal)]})

    def _do_sltp_create(self, operation: dict) -> None:
        body = operation["body"]
        position = self.positions.get(body["position_id"])
        if position is None or position["state"] != "open":
            return self._fail(operation, 3013, "REQUEST_POSITION_NOT_FOUND")
        order = self._sltp(body["position_id"]) or {
            "order_id": self._id(), "position_id": body["position_id"], "order_type": "sltp", "state": "placed",
            "create_time": iso(self.clock())}
        self.orders[order["order_id"]] = order
        self._apply_levels(operation, order, position, body)

    def _do_sltp_modify(self, operation: dict) -> None:
        order = self.orders.get(operation["order_id"])
        position = self.positions.get(order["position_id"]) if order else None
        if order is None or order["state"] != "placed" or position is None:
            return self._fail(operation, 3012, "REQUEST_ORDER_NOT_FOUND")
        self._apply_levels(operation, order, position, operation["body"])

    def _apply_levels(self, operation, order, position, body) -> None:
        bid, ask = self.prices.get(position["instrument"], (None, None))
        buy = position["direction"] == "buy"
        sl = body.get("stop_loss_price")
        if sl is not None and bid is not None and (float(sl) >= bid if buy else float(sl) <= ask):
            return self._fail(operation, 5005, "TRADING_RULE_INVALID_PRICE_LEVELS")
        for key in ("stop_loss_price", "take_profit_price"):
            if key in body:
                if body[key] is None:
                    order.pop(key, None)
                else:
                    order[key] = body[key]
            elif self.patch_replaces and operation["kind"] == "sltp_modify":
                order.pop(key, None)
        order["update_time"] = iso(self.clock())
        operation["status"] = "confirmed"
        self._emit(operation, {"orders": [copy.deepcopy(order)]})

    def _do_close(self, operation: dict) -> None:
        position = self.positions.get(operation["position_id"])
        if position is None or position["state"] != "open":
            return self._fail(operation, 3013, "REQUEST_POSITION_NOT_FOUND")
        if position["instrument"] not in self.prices:
            return self._fail(operation, 4004, "MARKET_NO_QUOTES")
        bid, ask = self.prices[position["instrument"]]
        volume = float(operation["volume"]) if operation["volume"] else float(position["volume"])
        if volume > float(position["volume"]) + 1e-9:
            return self._fail(operation, 5000, "TRADING_RULE_INVALID_VOLUME")
        vmin = float(self.instruments[position["instrument"]]["volume_min"])
        remaining = float(position["volume"]) - volume
        if 1e-9 < remaining < vmin - 1e-9:
            return self._fail(operation, 5004, "TRADING_RULE_INVALID_REMAINING_VOLUME")
        operation["status"] = "confirmed"
        self._close(position, volume, bid if position["direction"] == "buy" else ask, reason=None, operation=operation)

    def _close(self, position: dict, volume: float, price: float, *, reason, operation) -> None:
        now = iso(self.clock())
        digits = self.instruments[position["instrument"]]["point_digits"]
        profit = self._pnl(position, price, volume)
        self.balance += profit
        remaining = round(float(position["volume"]) - volume, 8)
        position["volume"] = f"{remaining:.2f}"
        opposite = "sell" if position["direction"] == "buy" else "buy"
        order = {"order_id": self._id(), "position_id": position["position_id"], "order_type": "market",
                 "state": "filled", "direction": opposite, "instrument": position["instrument"],
                 "price": f"{price:.{digits}f}", "volume": f"{volume:.2f}", "create_time": now}
        if reason:
            order["reason"] = reason
        deal = {"deal_id": self._id(), "order_id": order["order_id"], "position_id": position["position_id"],
                "type": "close", "direction": opposite, "instrument": position["instrument"],
                "volume": f"{volume:.2f}", "price": f"{price:.{digits}f}", "commission": "0",
                "profit": {"amount": f"{profit:.2f}", "currency": self.currency}, "create_time": now}
        self.deals.append(deal)
        orders = [order]
        if remaining <= 1e-9:
            position["state"] = "closed"
            sltp = self._sltp(position["position_id"])
            if sltp:
                sltp["state"] = "filled" if reason else "cancelled"
                orders.append(sltp)
        self._emit(operation, {"orders": copy.deepcopy(orders), "positions": [copy.deepcopy(position)],
                               "deals": [copy.deepcopy(deal)]})

    # ------------------------------------------------------------------ bot disi islemler (MT5/web'den)
    async def external_open(self, symbol, side, volume, sl=None, tp=None) -> str:
        """Kullanicinin botun disindan (MT5/web) actigi pozisyon."""
        operation = {"operation_id": self._id(), "client_request_id": None, "status": "pending", "kind": "open",
                     "body": {"instrument": symbol, "side": side.lower(), "volume": f"{volume:.2f}"}}
        if sl is not None:
            operation["body"]["stop_loss_price"] = str(sl)
        if tp is not None:
            operation["body"]["take_profit_price"] = str(tp)
        self._do_open(operation)
        event = self._events[-1]
        event.pop("operation_id", None)
        event.pop("client_request_id", None)
        position_id = event["payload"]["positions"][0]["position_id"]
        await self.flush()
        return position_id

    async def external_set_sl(self, position_id: str, sl: float) -> None:
        order = self._sltp(position_id)
        if order is None:
            order = {"order_id": self._id(), "position_id": position_id, "order_type": "sltp", "state": "placed",
                     "create_time": iso(self.clock())}
            self.orders[order["order_id"]] = order
        order["stop_loss_price"] = str(sl)
        self._emit(None, {"orders": [copy.deepcopy(order)]})
        await self.flush()

    async def external_cancel_sltp(self, position_id: str) -> None:
        """Pozisyonun SL/TP emri broker tarafinda iptal oldu (stop artik yok)."""
        order = self._sltp(position_id)
        order["state"] = "cancelled"
        self._emit(None, {"orders": [copy.deepcopy(order)]})
        await self.flush()
