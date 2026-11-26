"""Exness API alan adlarinin gectigi TEK modul.

Baska hicbir modul ham API alan adi kullanmaz; kesif sonrasi duzeltmeler yalnizca burada yapilir.
(Imza basliklari `signing.py` icindedir; onlar protokolun parcasidir.)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Literal
from urllib.parse import quote, urlsplit


def is_ws_ack(raw: Any) -> bool:
    """Akis abonelik onayi. Canlida `{"id": "ticks-1", "code": 200, "error_message": ""}` biciminde
    gelir: hata yaniti ile ayni alanlar, basari kodu (2xx)."""
    code = raw.get("code") if isinstance(raw, dict) else None
    return isinstance(code, int) and not isinstance(code, bool) and 200 <= code < 300


def parse_error(raw: Any) -> tuple[int | None, str | None]:
    """Hata govdesi -> (kod, mesaj). Bicim taninmazsa (None, None)."""
    if not isinstance(raw, dict):
        return None, None
    code = raw.get("code")
    message = raw.get("error_message")
    return (code if isinstance(code, int) and not isinstance(code, bool) else None,
            message if isinstance(message, str) else None)


def parse_retry_after(raw: Any) -> float | None:
    if isinstance(raw, dict):
        value = raw.get("retry_after")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            return float(value)
    return None


def access_point_path(account_id: str) -> str:
    return f"/v1/trading/access-point?account_id={quote(str(account_id), safe='')}"


def parse_access_point(raw: Any) -> str:
    """Kesif yaniti -> 'https://host'. Guvensiz ya da bicimsiz deger ValueError verir."""
    value = raw.get("access_point") if isinstance(raw, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError("kesif yanitinda access point yok")
    return base_url(value)


def base_url(value: str, *, allow_insecure_loopback: bool = False) -> str:
    """Host ya da URL -> semali, yolsuz taban URL. Yalnizca https (yerel test icin loopback http)."""
    text = value.strip().rstrip("/")
    if "://" not in text:
        text = "https://" + text
    url = urlsplit(text)
    loopback = url.hostname in ("127.0.0.1", "localhost", "::1")
    if url.scheme != "https" and not (allow_insecure_loopback and loopback and url.scheme == "http"):
        raise ValueError("https taban URL bekleniyordu")
    if not url.hostname or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
        raise ValueError("taban URL kimlik bilgisi, yol, sorgu ya da parca iceremez")
    return f"{url.scheme}://{url.netloc}"


# --------------------------------------------------------------------------------------
# Alan modelleri (botun geri kalani yalnizca bunlari gorur)
# --------------------------------------------------------------------------------------

Side = Literal["BUY", "SELL"]
Kind = Literal["forex", "metal", "crypto", "other"]

TIMEFRAMES = ("S1", "S5", "S15", "M1", "M3", "M5", "M10", "M15", "M30", "H1", "H2", "H4", "D1", "W1", "MN")
_INSTRUMENT_NAME = re.compile(r"^[A-Za-z0-9._-]{1,11}$")
_ID = re.compile(r"^[0-9]{1,20}$")
_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_WEEK = 7 * 1440
_METALS = frozenset({"XAU", "XAG", "XPT", "XPD", "XAL", "XCU", "XNI", "XPB", "XZN"})
_CRYPTO = frozenset({"BTC", "ETH", "LTC", "XRP", "BCH", "ADA", "DOT", "SOL", "DOGE", "BNB", "LINK", "XLM",
                     "UNI", "MATIC", "AVAX", "TRX", "ATOM", "FIL", "XTZ", "ETC"})
_FIAT = frozenset({"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "SEK", "NOK", "DKK", "PLN", "HUF",
                   "CZK", "TRY", "ZAR", "MXN", "SGD", "HKD", "CNH", "CNY", "ILS", "THB", "INR", "BRL", "KRW",
                   "RON", "BGN", "AED", "SAR", "KWD", "BHD", "OMR", "QAR", "JOD", "EGP", "NGN", "KES", "GHS",
                   "UGX", "PKR", "BDT", "VND", "IDR", "MYR", "PHP", "TWD", "ARS", "CLP", "COP", "PEN", "UAH",
                   "KZT", "AZN", "GEL", "AMD", "UZS", "MAD", "DZD", "TND", "BND", "LKR", "NPR", "ISK", "RUB"})
_EXCLUDED_CATEGORY = ("stock", "share", "equit", "indic", "index", "energ", "commod", "etf", "bond", "future")


@dataclass(frozen=True)
class AccountState:
    balance: float
    equity: float
    used_margin: float
    leverage: float | None = None


@dataclass(frozen=True)
class Account:
    currency: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    leverage: float | None
    can_open: bool  # hesap yeni pozisyon acmaya izin veriyor mu
    can_trade: bool  # hesapta islem (kapatma dahil) acik mi


@dataclass(frozen=True)
class Instrument:
    symbol: str  # kanonik ad (EURUSD); V9 ve botun geri kalani bunu kullanir
    broker_symbol: str  # API'deki ad (cent hesapta EURUSDc gibi); isteklere bu gider
    kind: Kind
    tick_size: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level: int  # API bu alani vermiyor; 0. Asiri yakin stop broker tarafinda reddedilir.
    digits: int
    currency_base: str
    currency_profit: str
    currency_margin: str
    calc_mode: str
    exec_mode: str
    trading_hours: dict | None  # V9 bicimi: {'timezone': 'UTC', 'weekly': {'0'..'6': [['HH:MM','HH:MM']]}}
    tradable: bool
    commission_type: str | None = None
    commission_value: float | None = None
    commission_currency: str | None = None
    # Gecelik faiz (swap), enstruman kosullarindan: gece basina PUAN (fiyat adimi) cinsinden, alis ve satis icin
    # ayri; eksi = maliyet. `swap_multipliers`: gun adi (MON..SUN) -> o gunun devrinde kac kat uygulanir.
    # Swap'siz hesapta broker bunlari uygulamayabilir: gercek durum pozisyondaki birikmis swap'tan olculur.
    swap_long: float | None = None
    swap_short: float | None = None
    swap_multipliers: dict | None = None


@dataclass(frozen=True)
class Order:
    id: str
    type: str  # market | stop | limit | sltp
    state: str  # pending_new | placed | filled | cancelled | rejected
    position_id: str | None = None
    side: Side | None = None
    symbol: str | None = None  # broker adi
    price: float | None = None
    sl: float | None = None
    tp: float | None = None
    volume: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Position:
    id: str
    symbol: str  # broker adi
    side: Side
    volume: float
    open_price: float | None
    sl: float | None = None
    tp: float | None = None
    sltp_order_id: str | None = None
    initial_volume: float | None = None
    commission: float = 0.0
    swap: float | None = 0.0
    opened_at: float | None = None
    closed: bool = False
    profit: float | None = None  # API vermez; yerelde hesaplanir
    comment: str | None = None


@dataclass(frozen=True)
class Deal:
    id: str
    type: str  # open | close | balance | ...
    time: float | None
    order_id: str | None = None
    position_id: str | None = None
    side: Side | None = None
    symbol: str | None = None
    volume: float | None = None
    price: float | None = None
    profit: float | None = None
    commission: float = 0.0


@dataclass(frozen=True)
class Snapshot:
    positions: tuple[Position, ...]
    orders: tuple[Order, ...]
    account: AccountState | None


@dataclass(frozen=True)
class Tick:
    symbol: str  # broker adi
    bid: float
    ask: float
    time: float


@dataclass(frozen=True)
class TxEvent:
    operation_id: str | None
    client_request_id: str | None
    status: Literal["success", "rejected", "failed"]
    position_id: str | None = None
    price: float | None = None
    volume: float | None = None
    reason: str | None = None
    error_code: int | None = None
    time: float | None = None
    orders: tuple[Order, ...] = ()
    positions: tuple[Position, ...] = ()
    deals: tuple[Deal, ...] = ()
    account: AccountState | None = None


@dataclass(frozen=True)
class Ack:
    operation_id: str | None
    client_request_id: str | None


@dataclass(frozen=True)
class OperationStatus:
    operation_id: str
    status: Literal["pending", "confirmed", "rejected", "failed"]
    client_request_id: str | None = None
    error_code: int | None = None
    reason: str | None = None

    @property
    def final(self) -> bool:
        return self.status != "pending"


@dataclass(frozen=True)
class Limits:
    global_rate: tuple[int, float] | None = None
    methods: tuple[tuple[str, str, int, float], ...] = ()
    max_candles: int | None = None
    history_range_days: int | None = None
    history_age_days: int | None = None
    tick_subscription_rate: tuple[int, float, int] | None = None  # (limit, pencere_sn, burst)
    websocket: dict = field(default_factory=dict)


# --------------------------------------------------------------------------------------
# Yardimcilar
# --------------------------------------------------------------------------------------

def _num(value: Any) -> float | None:
    """API ondalik dizgesi ya da sayisi -> float; bos/gecersiz -> None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _epoch(value: Any) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp()


def _iso(epoch: float) -> str:
    """UTC, 'Z' sonekli; URL kacisi gerektirmez (imzalanan yol gonderilenle birebir ayni kalir)."""
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _side(value: Any) -> Side | None:
    return {"buy": "BUY", "sell": "SELL"}.get(value) if isinstance(value, str) else None


def _positive(value: Any, name: str) -> float:
    number = _num(value)
    if number is None or number <= 0:
        raise ValueError(f"{name} pozitif ve sonlu olmali")
    return number


def fmt_price(value: Any, digits: int) -> str:
    number = _positive(value, "fiyat")
    quantum = Decimal(1).scaleb(-int(digits))
    return f"{Decimal(str(number)).quantize(quantum, rounding=ROUND_HALF_EVEN):f}"


def fmt_volume(value: Any, step: float) -> str:
    number = _positive(value, "hacim")
    grid = Decimal(str(_positive(step, "hacim adimi")))
    units = (Decimal(str(number)) / grid).quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    result = units * grid
    if result <= 0:
        raise ValueError("hacim adima yuvarlaninca sifir oluyor")
    return f"{result.quantize(grid):f}" if grid.as_tuple().exponent < 0 else f"{result:f}"


def _check_id(value: Any, name: str) -> str:
    text = str(value)
    if not _ID.match(text):
        raise ValueError(f"{name} gecersiz")
    return text


def _check_instrument(name: str) -> str:
    if not isinstance(name, str) or not _INSTRUMENT_NAME.match(name):
        raise ValueError("enstruman adi gecersiz")
    return name


# --------------------------------------------------------------------------------------
# Yanit donusturuculer
# --------------------------------------------------------------------------------------

def parse_account_state(raw: Any) -> AccountState:
    raw = raw if isinstance(raw, dict) else {}
    balance, equity = _num(raw.get("balance")), _num(raw.get("equity"))
    if balance is None or equity is None:
        raise ValueError("hesap durumu eksik")
    return AccountState(balance, equity, _num(raw.get("used_margin")) or 0.0, _num(raw.get("leverage")))


def parse_account(details: Any, state: Any) -> Account:
    """Hesap ayarlari (`/account`) + anlik durum (snapshot'taki account_state) -> Account."""
    settings = details.get("settings") if isinstance(details, dict) else None
    settings = settings if isinstance(settings, dict) else {}
    currency = _text(settings.get("currency"))
    if not currency:
        raise ValueError("hesap para birimi yok")
    current = state if isinstance(state, AccountState) else parse_account_state(state)
    enabled = settings.get("trade_mode") == "enabled"
    return Account(currency=currency.upper(), balance=current.balance, equity=current.equity,
                   margin=current.used_margin, margin_free=current.equity - current.used_margin,
                   leverage=current.leverage or _num(settings.get("leverage")),
                   can_open=enabled and settings.get("account_status") == "active", can_trade=enabled)


def _week_minute(value: Any, *, end: bool) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.match(r"^\s*([A-Za-z]{3})[a-z]*,?\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$", value)
    if not match or match.group(1).lower() not in _DAYS:
        return None
    hour, minute, second = int(match.group(2)), int(match.group(3)), int(match.group(4) or 0)
    if hour > 24 or minute > 59 or second > 59:
        return None
    total = _DAYS[match.group(1).lower()] * 1440 + hour * 60 + minute
    # "23:59:59" dakikanin sonu demektir; baslangicta saniye varsa bir sonraki dakikadan baslatilir.
    if second and (second == 59 or not end):
        total += 1
    return total


def _trading_hours(sessions: Any) -> dict | None:
    """trade_sessions -> V9 haftalik pencere bicimi (UTC). Bilgi yoksa None (V9 'bilinmiyor' sayar)."""
    if not isinstance(sessions, list) or not sessions:
        return None
    spans: list[tuple[int, int]] = []
    for item in sessions:
        if not isinstance(item, dict) or item.get("trade_mode", "enabled") != "enabled":
            continue
        start_raw, end_raw = item.get("week_start_time"), item.get("week_end_time")
        start = 0 if start_raw is None else _week_minute(start_raw, end=False)
        end = _WEEK if end_raw is None else _week_minute(end_raw, end=True)
        if start is None or end is None:
            return None  # okunamayan oturum: tahmin yurutme
        start, end = min(start, _WEEK), min(end, _WEEK)
        if end > start:
            spans.append((start, end))
        elif end < start:  # hafta sonunu asan oturum (or. Paz 21:05 -> Cum 20:59)
            spans += [(start, _WEEK), (0, end)]
    if not spans:
        return None
    spans.sort()
    merged = [list(spans[0])]
    for start, end in spans[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    weekly: dict[str, list[list[str]]] = {}
    for start, end in merged:
        for day in range(start // 1440, (end - 1) // 1440 + 1):
            low, high = max(start, day * 1440) - day * 1440, min(end, (day + 1) * 1440) - day * 1440
            if high > low:
                weekly.setdefault(str(day), []).append([f"{low // 60:02d}:{low % 60:02d}",
                                                        f"{high // 60:02d}:{high % 60:02d}"])
    return {"timezone": "UTC", "weekly": dict(sorted(weekly.items()))}


def _kind(category: str, base: str, quote: str) -> Kind:
    cat = category.lower()
    if any(word in cat for word in _EXCLUDED_CATEGORY):
        return "other"
    if base in _METALS or "metal" in cat:
        return "metal"
    if base in _CRYPTO or "crypto" in cat:
        return "crypto"
    if base in _FIAT and quote in _FIAT and base != quote:
        return "forex"
    if base and quote and base != quote and ("forex" in cat or "currenc" in cat or cat == "fx"):
        return "forex"
    return "other"


def _swap_multipliers(raw: Any) -> dict | None:
    if not isinstance(raw, list):
        return None
    out = {}
    for row in raw:
        if isinstance(row, dict) and isinstance(row.get("day"), str):
            value = _num(row.get("multiplier"))
            if value is not None and 0 <= value <= 10:
                out[row["day"].upper()[:3]] = value
    return out or None


def parse_instrument(raw: Any) -> Instrument:
    if not isinstance(raw, dict) or not isinstance(raw.get("instrument"), str):
        raise ValueError("enstruman kaydi gecersiz")
    name = raw["instrument"]
    base = (_text(raw.get("base_currency")) or "").upper()
    quote_ccy = (_text(raw.get("quote_currency")) or "").upper()
    leading = re.match(r"^[A-Z0-9]+", name)
    canonical = leading.group(0) if leading else name.upper()
    if base and quote_ccy and base != quote_ccy and name.upper().startswith(base + quote_ccy):
        canonical = base + quote_ccy
    elif not base and len(canonical) == 6:
        base, quote_ccy = canonical[:3], quote_ccy or canonical[3:]
    digits = raw.get("point_digits")
    digits_ok = isinstance(digits, int) and not isinstance(digits, bool) and 0 <= digits <= 12
    contract, vmin = _num(raw.get("contract_size")), _num(raw.get("volume_min"))
    vmax, vstep = _num(raw.get("volume_max")), _num(raw.get("volume_step"))
    complete = digits_ok and all(v is not None and v > 0 for v in (contract, vmin, vmax, vstep)) and vmax >= vmin
    commission = raw.get("commission_settings") if isinstance(raw.get("commission_settings"), dict) else {}
    money = commission.get("commission_value") if isinstance(commission.get("commission_value"), dict) else {}
    return Instrument(
        symbol=canonical, broker_symbol=name, kind=_kind(_text(raw.get("category")) or "", base, quote_ccy),
        tick_size=10.0 ** -digits if digits_ok else 0.0, contract_size=contract or 0.0,
        volume_min=vmin or 0.0, volume_max=vmax or 0.0, volume_step=vstep or 0.0, stops_level=0,
        digits=digits if digits_ok else 0, currency_base=base, currency_profit=quote_ccy,
        currency_margin=(_text(raw.get("margin_currency")) or base).upper(),
        calc_mode=_text(raw.get("calc_mode")) or "undefined", exec_mode=_text(raw.get("exec_mode")) or "undefined",
        trading_hours=_trading_hours(raw.get("trade_sessions")),
        swap_long=_num(raw.get("swap_long")), swap_short=_num(raw.get("swap_short")),
        swap_multipliers=_swap_multipliers(raw.get("swap_multipliers")),
        tradable=bool(complete) and raw.get("trade_mode", "enabled") == "enabled",
        commission_type=_text(commission.get("commission_type")), commission_value=_num(money.get("amount")),
        commission_currency=_text(money.get("currency")))


def parse_instrument_names(raw: Any) -> list[str]:
    names = raw.get("instruments") if isinstance(raw, dict) else None
    return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []


def parse_candle(raw: Any) -> dict:
    """Tek fiyat tipli (bid) mum -> V9 satiri. `time` mumun ACILIS zamani (epoch sn, int)."""
    if not isinstance(raw, dict) or "bid" in raw or "ask" in raw:
        raise ValueError("bid mumu bekleniyordu")
    time = _epoch(raw.get("time"))
    prices = [_num(raw.get(key)) for key in ("open", "high", "low", "close")]
    if time is None or any(p is None for p in prices):
        raise ValueError("mum kaydi eksik")
    return {"time": int(time), "open": prices[0], "high": prices[1], "low": prices[2], "close": prices[3],
            "tick_volume": _num(raw.get("volume")) or 0.0}


def parse_candles(raw: Any) -> list[dict]:
    rows = raw.get("candles") if isinstance(raw, dict) else None
    return [parse_candle(row) for row in rows] if isinstance(rows, list) else []


def parse_tick(raw: Any) -> Tick | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("instrument"), str):
        return None
    bid, ask, time = _num(raw.get("bid")), _num(raw.get("ask")), _epoch(raw.get("timestamp"))
    if bid is None or ask is None or time is None:
        return None
    return Tick(raw["instrument"], bid, ask, time)


def parse_order(raw: Any) -> Order | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("order_id"), str):
        return None
    return Order(id=raw["order_id"], type=_text(raw.get("order_type")) or "", state=_text(raw.get("state")) or "",
                 position_id=_text(raw.get("position_id")), side=_side(raw.get("direction")),
                 symbol=_text(raw.get("instrument")), price=_num(raw.get("price")),
                 sl=_num(raw.get("stop_loss_price")), tp=_num(raw.get("take_profit_price")),
                 volume=_num(raw.get("volume")), reason=_text(raw.get("reason")))


def parse_position(raw: Any, sltp: Order | None = None) -> Position | None:
    """SL/TP pozisyonda degil, ona bagli `sltp` emrinde durur; `sltp` verilirse birlestirilir."""
    if not isinstance(raw, dict) or not isinstance(raw.get("position_id"), str):
        return None
    side, volume = _side(raw.get("direction")), _num(raw.get("volume"))
    if side is None or volume is None or not isinstance(raw.get("instrument"), str):
        return None
    return Position(id=raw["position_id"], symbol=raw["instrument"], side=side, volume=volume,
                    open_price=_num(raw.get("open_price")), sl=sltp.sl if sltp else None,
                    tp=sltp.tp if sltp else None, sltp_order_id=sltp.id if sltp else None,
                    initial_volume=_num(raw.get("initial_volume")), commission=_num(raw.get("commission")) or 0.0,
                    swap=_num(raw.get("swap")), opened_at=_epoch(raw.get("create_time")),  # swap alani yoksa None
                    closed=raw.get("state") == "closed", comment=_text(raw.get("comment")))


def parse_deal(raw: Any, event_time: Any = None) -> Deal | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("deal_id"), str):
        return None
    profit = raw.get("profit") if isinstance(raw.get("profit"), dict) else {}
    return Deal(id=raw["deal_id"], type=_text(raw.get("type")) or "",
                time=_epoch(raw.get("create_time")) or _epoch(event_time), order_id=_text(raw.get("order_id")),
                position_id=_text(raw.get("position_id")), side=_side(raw.get("direction")),
                symbol=_text(raw.get("instrument")), volume=_num(raw.get("volume")), price=_num(raw.get("price")),
                profit=_num(profit.get("amount")), commission=_num(raw.get("commission")) or 0.0)


def _entities(payload: Any) -> tuple[tuple[Order, ...], tuple[Position, ...]]:
    payload = payload if isinstance(payload, dict) else {}
    orders = tuple(o for o in map(parse_order, payload.get("orders") or []) if o)
    active = {o.position_id: o for o in orders
              if o.type == "sltp" and o.position_id and o.state in ("placed", "pending_new")}
    positions = tuple(p for p in (parse_position(r, active.get(r.get("position_id")) if isinstance(r, dict) else None)
                                  for r in payload.get("positions") or []) if p)
    return orders, positions


def parse_snapshot(raw: Any) -> Snapshot:
    orders, positions = _entities(raw)
    state = raw.get("account_state") if isinstance(raw, dict) else None
    return Snapshot(tuple(p for p in positions if not p.closed), orders,
                    parse_account_state(state) if isinstance(state, dict) else None)


def parse_transaction_event(raw: Any) -> TxEvent:
    payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else {}
    orders, positions = _entities(payload)
    deals = tuple(d for d in (parse_deal(r, raw.get("event_time")) for r in payload.get("deals") or []) if d)
    trade = next((d for d in deals if d.type in ("open", "close")), None)
    position_id = (positions[0].id if positions else None) or (trade.position_id if trade else None) \
        or next((o.position_id for o in orders if o.position_id), None)
    status = raw.get("status") if raw.get("status") in ("success", "rejected", "failed") else "failed"
    code, message = raw.get("error_code"), _text(raw.get("error_message"))
    state = payload.get("account_state")
    return TxEvent(operation_id=_text(raw.get("operation_id")), client_request_id=_text(raw.get("client_request_id")),
                   status=status, position_id=position_id, price=trade.price if trade else None,
                   volume=trade.volume if trade else None, reason=message,
                   error_code=code if isinstance(code, int) and not isinstance(code, bool) else None,
                   time=_epoch(raw.get("event_time")), orders=orders, positions=positions, deals=deals,
                   account=parse_account_state(state) if isinstance(state, dict) else None)


def parse_ws_event(raw: Any) -> tuple[str, Any]:
    """Olay akisi mesaji -> (tur, veri). tur: transaction | snapshot | account | instrument | ack | error | other."""
    if not isinstance(raw, dict):
        return "other", raw
    kind = raw.get("event_type")
    payload = raw.get("payload")
    try:
        if kind == "transaction_event":
            return "transaction", parse_transaction_event(raw)
        if kind == "trading_state_snapshot":
            return "snapshot", parse_snapshot(payload)
        if kind == "account_state_event" and isinstance(payload, dict):
            return "account", parse_account_state(payload.get("account_state"))
        if kind == "instrument_event":
            return "instrument", parse_instrument(payload)
    except ValueError:
        return "other", raw
    if kind is None and is_ws_ack(raw):
        return "ack", raw
    if kind is None and parse_error(raw)[0] is not None:
        return "error", parse_error(raw)
    return "other", raw


def parse_ack(raw: Any) -> Ack:
    raw = raw if isinstance(raw, dict) else {}
    return Ack(_text(raw.get("operation_id")), _text(raw.get("client_request_id")))


def parse_operation(raw: Any) -> OperationStatus:
    if not isinstance(raw, dict) or raw.get("status") not in ("pending", "confirmed", "rejected", "failed"):
        raise ValueError("operasyon durumu gecersiz")
    code = raw.get("error_code")
    return OperationStatus(operation_id=str(raw.get("operation_id") or ""), status=raw["status"],
                           client_request_id=_text(raw.get("client_request_id")),
                           error_code=code if isinstance(code, int) and not isinstance(code, bool) else None,
                           reason=_text(raw.get("error_message")))


def parse_limits(raw: Any) -> Limits:
    limits = raw.get("limits") if isinstance(raw, dict) else None
    rest = limits.get("rest") if isinstance(limits, dict) else None
    if not isinstance(rest, dict):
        return Limits()

    def rate(value: Any) -> tuple[int, float] | None:
        if isinstance(value, dict) and _num(value.get("limit")) and _num(value.get("window_seconds")):
            return int(value["limit"]), float(value["window_seconds"])
        return None

    methods, extra = [], {}
    for item in rest.get("methods") or []:
        if not isinstance(item, dict):
            continue
        limit = rate(item.get("rate_limit"))
        if limit and isinstance(item.get("http_method"), str) and isinstance(item.get("path"), str):
            methods.append((item["http_method"].upper(), item["path"], limit[0], limit[1]))
        shape = item.get("limits") if isinstance(item.get("limits"), dict) else {}
        for key in ("max_candles_per_request", "history_range_days", "history_age_days"):
            value = shape.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                extra[key] = min(value, extra.get(key, value))
    websocket = limits.get("websocket") if isinstance(limits.get("websocket"), dict) else {}
    tick_rate = None
    for endpoint in websocket.get("endpoints") or []:
        rates = endpoint.get("subscription_operation_rate") if isinstance(endpoint, dict) else None
        bucket = rates.get("ticks") if isinstance(rates, dict) else None
        if isinstance(bucket, dict) and rate(bucket) and str(endpoint.get("path", "")).endswith("/ws/ticks"):
            burst = bucket.get("burst")
            tick_rate = (*rate(bucket), int(burst) if isinstance(burst, int) and burst > 0 else 1)
    return Limits(tick_subscription_rate=tick_rate, global_rate=rate(rest.get("global_account_rate")), methods=tuple(methods),
                  max_candles=extra.get("max_candles_per_request"),
                  history_range_days=extra.get("history_range_days"),
                  history_age_days=extra.get("history_age_days"), websocket=websocket)


def parse_deals(raw: Any) -> tuple[list[Deal], str | None]:
    items = raw.get("items") if isinstance(raw, dict) else None
    deals = []
    for item in items if isinstance(items, list) else []:
        deal = parse_deal(item.get("deal"), item.get("event_time")) if isinstance(item, dict) else None
        if deal:
            deals.append(deal)
    cursor = _text(raw.get("next_cursor")) if isinstance(raw, dict) else None
    if cursor is None and isinstance(raw, dict) and raw.get("has_more") is True:
        # Devami var ama imlec okunamadi: sessizce eksik gecmisle devam etmek (kapanis ya da para
        # yatirma/cekme kacirmak) yerine acik hata.
        raise ValueError("deal gecmisinin devami var ama next_cursor okunamadi")
    return deals, cursor


# --------------------------------------------------------------------------------------
# Istek kuruculari
# --------------------------------------------------------------------------------------

def account_path(account_id: str) -> str:
    return f"/v1/configuration/accounts/{_check_id(account_id, 'hesap')}/account"


def limits_path(account_id: str) -> str:
    return f"/v1/configuration/accounts/{_check_id(account_id, 'hesap')}/limits"


def instruments_path(account_id: str) -> str:
    return f"/v1/configuration/accounts/{_check_id(account_id, 'hesap')}/instruments"


def instrument_path(account_id: str, broker_symbol: str) -> str:
    return (f"/v1/configuration/accounts/{_check_id(account_id, 'hesap')}"
            f"/instruments/{_check_instrument(broker_symbol)}/conditions")


def snapshot_path(account_id: str) -> str:
    return f"/v1/trading/accounts/{_check_id(account_id, 'hesap')}/snapshot"


def operation_path(account_id: str, operation_id: str) -> str:
    return f"/v1/trading/accounts/{_check_id(account_id, 'hesap')}/operations/{_check_id(operation_id, 'operasyon')}"


DEAL_BALANCE = "balance"  # para yatirma/cekme deal turu

# Kimlik hatasi kodlari (Trading Error Codes).
AUTH_INVALID_API_KEY = 1000

# Sunucu el sikismasinda bu alt-protokolu secer; istemci onermezse baglanti kurulamaz
# (resmi kod ornegi: new WebSocket(url, 'exness-ws-protocol', ...)).
WS_SUBPROTOCOL = "exness-ws-protocol"


def ticks_ws_path(account_id: str) -> str:
    return f"/v1/server-events/accounts/{_check_id(account_id, 'hesap')}/ws/ticks"


def events_ws_path(account_id: str) -> str:
    return f"/v1/server-events/accounts/{_check_id(account_id, 'hesap')}/ws/events"


def candles_path(account_id: str, broker_symbol: str, timeframe: str, start: float,
                 end: float | None = None, *, count: int | None = None) -> str:
    """`start` dahil, `end` haric (mumun acilis zamanina gore). `end` ya da `count`'tan tam biri verilir."""
    if timeframe not in TIMEFRAMES:
        raise ValueError("zaman dilimi gecersiz")
    if (end is None) == (count is None) or count == 0:
        raise ValueError("end ya da sifir olmayan count'tan tam biri verilmeli")
    path = (f"/v1/market-data/accounts/{_check_id(account_id, 'hesap')}/candles"
            f"?instrument={_check_instrument(broker_symbol)}&timeframe={timeframe}&from={_iso(start)}")
    return path + (f"&to={_iso(end)}" if end is not None else f"&count={int(count)}")


def deals_path(account_id: str, *, start: float | None = None, end: float | None = None,
               cursor: str | None = None, limit: int = 100) -> str:
    base = f"/v1/history/accounts/{_check_id(account_id, 'hesap')}/deals?"
    if cursor is not None:
        return base + f"cursor={quote(cursor, safe='')}&limit={int(limit)}"
    if start is None:
        raise ValueError("start ya da cursor gerekli")
    return base + f"from={_iso(start)}" + (f"&to={_iso(end)}" if end is not None else "") + f"&limit={int(limit)}"


def open_position_request(account_id: str, instrument: Instrument, side: str, volume: float, *,
                          sl: float | None, tp: float | None, price: float | None = None,
                          deviation_points: int | None = None, comment: str | None = None) -> tuple[str, dict]:
    """Piyasa emriyle pozisyon acma. SL zorunludur: SL'siz emir kuran kod yolu yoktur (spec §2)."""
    if side not in ("BUY", "SELL"):
        raise ValueError("yon BUY ya da SELL olmali")
    if sl is None:
        raise ValueError("stop loss olmadan pozisyon acilamaz")
    lots = _positive(volume, "hacim")
    text_volume = fmt_volume(lots, instrument.volume_step)
    if not instrument.volume_min <= float(text_volume) <= instrument.volume_max:
        raise ValueError("hacim enstruman sinirlarinin disinda")
    body = {"instrument": _check_instrument(instrument.broker_symbol), "side": side.lower(), "volume": text_volume}
    if instrument.exec_mode == "instant":
        if price is None:
            raise ValueError("instant yurutmede istenen fiyat gerekli")
        body["price"] = fmt_price(price, instrument.digits)
        if deviation_points is not None:
            body["deviation"] = str(int(deviation_points))
    body["stop_loss_price"] = fmt_price(sl, instrument.digits)
    if tp is not None:
        body["take_profit_price"] = fmt_price(tp, instrument.digits)
    if comment:
        body["comment"] = comment[:31]
    return f"/v1/trading/accounts/{_check_id(account_id, 'hesap')}/positions", body


def sltp_create_request(account_id: str, position_id: str, *, sl: float | None, tp: float | None,
                        digits: int) -> tuple[str, dict]:
    """Pozisyona bagli yeni SL/TP emri (pozisyonun henuz SL/TP emri yoksa)."""
    if sl is None and tp is None:
        raise ValueError("SL ya da TP'den en az biri gerekli")
    body: dict = {"position_id": _check_id(position_id, "pozisyon"), "type": "sltp"}
    if sl is not None:
        body["stop_loss_price"] = fmt_price(sl, digits)
    if tp is not None:
        body["take_profit_price"] = fmt_price(tp, digits)
    return f"/v1/trading/accounts/{_check_id(account_id, 'hesap')}/orders", body


def sltp_modify_request(account_id: str, order_id: str, *, sl: float | None, tp: float | None,
                        digits: int) -> tuple[str, dict]:
    """Mevcut SL/TP emrini degistirir. None = dokunma. SL'i kaldiran bir kurucu bilerek yoktur."""
    if sl is None and tp is None:
        raise ValueError("SL ya da TP'den en az biri gerekli")
    body: dict = {}
    if sl is not None:
        body["stop_loss_price"] = fmt_price(sl, digits)
    if tp is not None:
        body["take_profit_price"] = fmt_price(tp, digits)
    path = f"/v1/trading/accounts/{_check_id(account_id, 'hesap')}/orders/{_check_id(order_id, 'emir')}"
    return path, body


def close_position_path(account_id: str, position_id: str, *, volume: float | None = None,
                        volume_step: float | None = None) -> str:
    """Tam kapama (volume yok) ya da kismi kapama. DELETE ile kullanilir."""
    path = (f"/v1/trading/accounts/{_check_id(account_id, 'hesap')}"
            f"/positions/{_check_id(position_id, 'pozisyon')}")
    if volume is None:
        return path
    return path + "?volume=" + fmt_volume(volume, _positive(volume_step, "hacim adimi"))


def subscribe_ticks(request_id: str, broker_symbols: list[str]) -> dict:
    return {"id": request_id, "subscribe": {"event": "ticks",
                                            "instruments": [_check_instrument(s) for s in broker_symbols]}}


def subscribe_events(request_id: str, event: str, instruments: list[str] | None = None) -> dict:
    body: dict = {"event": event}
    if instruments is not None:
        body["instruments"] = list(instruments)
    return {"id": request_id, "subscribe": body}
