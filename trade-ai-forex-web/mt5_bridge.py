
from contextlib import asynccontextmanager
from decimal import Decimal
from threading import Lock
from typing import Literal
import math
import time

import MetaTrader5 as mt5
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

mt5_lock = Lock()
last_reconnect_attempt = 0.0
RECONNECT_INTERVAL = 5.0

TIMEFRAMES = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

SYMBOLS = {"XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "CHFJPY", "EURCAD", "USDCAD", "USDCHF", "EURGBP", "EURCHF", "GBPCHF", "NZDUSD", "EURAUD", "CADJPY", "NZDJPY", "AUDUSD", "EURJPY", "GBPJPY", "AUDJPY"}
RISK_SYMBOLS = {"XAUUSD", "EURUSD", "GBPUSD", "USDJPY"}
MT5_SYMBOL_MAP = {"XAUUSD": "XAUUSDc", "EURUSD": "EURUSDc", "GBPUSD": "GBPUSDc", "USDJPY": "USDJPYc", "CHFJPY": "CHFJPYc", "EURCAD": "EURCADc", "USDCAD": "USDCADc", "USDCHF": "USDCHFc", "EURGBP": "EURGBPc", "EURCHF": "EURCHFc", "GBPCHF": "GBPCHFc", "NZDUSD": "NZDUSDc", "EURAUD": "EURAUDc", "CADJPY": "CADJPYc", "NZDJPY": "NZDJPYc", "AUDUSD": "AUDUSDc", "EURJPY": "EURJPYc", "GBPJPY": "GBPJPYc", "AUDJPY": "AUDJPYc"}

def mt5_symbol(symbol):
    return MT5_SYMBOL_MAP.get(symbol, symbol)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    with mt5_lock:
        mt5.shutdown()


app = FastAPI(
    title="Trade AI MT5 Veri Sunucusu",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def ensure_connection():
    global last_reconnect_attempt

    terminal = mt5.terminal_info()

    if terminal is not None and terminal.connected:
        return

    now = time.monotonic()

    if now - last_reconnect_attempt < RECONNECT_INTERVAL:
        raise HTTPException(
            status_code=503,
            detail="MT5 bağlantısı yeniden kuruluyor",
        )

    last_reconnect_attempt = now

    mt5.shutdown()

    if not mt5.initialize(timeout=5000):
        raise HTTPException(
            status_code=503,
            detail=f"MT5 bağlantısı kurulamadı: {mt5.last_error()}",
        )

    terminal = mt5.terminal_info()

    if terminal is None or not terminal.connected:
        raise HTTPException(
            status_code=503,
            detail="MT5 broker bağlantısı aktif değil",
        )


@app.get("/api/health")
def health():
    with mt5_lock:
        terminal = mt5.terminal_info()

        return {
            "service": "Trade AI MT5",
            "connected": bool(
                terminal is not None and terminal.connected
            ),
        }


@app.get("/api/candles")
def candles(
    symbol: str = "XAUUSD",
    timeframe: str = "M5",
    limit: int = Query(200, ge=1, le=500),
):
    if symbol not in SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail="Desteklenmeyen parite",
        )

    if timeframe not in TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail="Desteklenmeyen zaman dilimi",
        )

    with mt5_lock:
        ensure_connection()

        info = mt5.symbol_info(mt5_symbol(symbol))

        if info is None:
            raise HTTPException(
                status_code=404,
                detail="Parite MT5 üzerinde bulunamadı",
            )

        if not info.visible:
            if not mt5.symbol_select(mt5_symbol(symbol), True):
                raise HTTPException(
                    status_code=503,
                    detail="Parite etkinleştirilemedi",
                )

        rates = mt5.copy_rates_from_pos(
            mt5_symbol(symbol),
            TIMEFRAMES[timeframe],
            0,
            limit,
        )

        if rates is None or len(rates) == 0:
            raise HTTPException(
                status_code=503,
                detail=f"Mum verisi alınamadı: {mt5.last_error()}",
            )

        tick = mt5.symbol_info_tick(mt5_symbol(symbol))
        captured_at_utc = int(time.time())

        data = [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
            }
            for r in rates
        ]

        data.sort(key=lambda item: item["time"])

        price = None

        if tick is not None:
            price = {
                "bid": float(tick.bid),
                "ask": float(tick.ask),
                "time": int(tick.time),
            }

        return JSONResponse(
            content={
                "symbol": symbol,
                "timeframe": timeframe,
                "source": "MetaTrader 5",
                "digits": int(info.digits),
                "point": float(info.point),
                "captured_at_utc": captured_at_utc,
                "candles": data,
                "tick": price,
            },
            headers={"Cache-Control": "no-store"},
        )


@app.get("/api/symbol-spec")
def symbol_spec(symbol: str = "XAUUSD"):
    if symbol not in SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail="Desteklenmeyen parite",
        )

    with mt5_lock:
        ensure_connection()

        info = mt5.symbol_info(mt5_symbol(symbol))

        if info is None:
            raise HTTPException(
                status_code=404,
                detail="Parite MT5 üzerinde bulunamadı",
            )

        if not info.visible:
            if not mt5.symbol_select(mt5_symbol(symbol), True):
                raise HTTPException(
                    status_code=503,
                    detail="Parite etkinleştirilemedi",
                )

            info = mt5.symbol_info(mt5_symbol(symbol))

            if info is None:
                raise HTTPException(
                    status_code=503,
                    detail="Parite bilgileri yenilenemedi",
                )

        account = mt5.account_info()

        if account is None or not account.currency:
            raise HTTPException(
                status_code=503,
                detail="MT5 hesap para birimi alınamadı",
            )

        if (
            info.point <= 0
            or info.trade_tick_size <= 0
            or info.trade_contract_size <= 0
            or info.volume_min <= 0
            or info.volume_max < info.volume_min
            or info.volume_step <= 0
        ):
            raise HTTPException(
                status_code=503,
                detail="Geçerli MT5 lot özellikleri alınamadı",
            )

        return JSONResponse(
            content={
                "symbol": symbol,
                "source": "MetaTrader 5",
                "digits": int(info.digits),
                "point": float(info.point),
                "tick_size": float(info.trade_tick_size),
                "contract_size": float(info.trade_contract_size),
                "volume_min": float(info.volume_min),
                "volume_max": float(info.volume_max),
                "volume_step": float(info.volume_step),
                "currency_profit": str(info.currency_profit),
                "account_currency": str(account.currency),
            },
            headers={"Cache-Control": "no-store"},
        )


@app.get("/api/risk-preview")
def risk_preview(
    symbol: str = "XAUUSD",
    direction: Literal["BUY", "SELL"] = "BUY",
    balance: float = Query(..., gt=0, le=1000000000),
    risk_percent: float = Query(..., gt=0, le=10),
    entry: float = Query(..., gt=0, le=10000000),
    stop_loss: float = Query(..., gt=0, le=10000000),
):
    """Yalnızca manuel DEMO risk önizlemesi; emir göndermez."""

    if symbol not in RISK_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail="Desteklenmeyen parite",
        )

    if not all(
        math.isfinite(x)
        for x in (balance, risk_percent, entry, stop_loss)
    ):
        raise HTTPException(
            status_code=400,
            detail="Geçersiz sayısal değer",
        )

    if direction == "BUY" and stop_loss >= entry:
        raise HTTPException(
            status_code=400,
            detail="BUY için Stop Loss giriş fiyatının altında olmalı",
        )

    if direction == "SELL" and stop_loss <= entry:
        raise HTTPException(
            status_code=400,
            detail="SELL için Stop Loss giriş fiyatının üstünde olmalı",
        )

    with mt5_lock:
        ensure_connection()

        account = mt5.account_info()

        if account is None or not account.currency:
            raise HTTPException(
                status_code=503,
                detail="MT5 hesap bilgisi alınamadı",
            )

        if account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO and not (account.trade_mode == mt5.ACCOUNT_TRADE_MODE_REAL and account.currency == "USC" and str(account.server).startswith("Exness-")):
            raise HTTPException(
                status_code=403,
                detail="Risk hesaplama sadece MT5 demo hesabında kullanılabilir",
            )

        info = mt5.symbol_info(mt5_symbol(symbol))

        if info is None:
            raise HTTPException(
                status_code=404,
                detail="Parite MT5 üzerinde bulunamadı",
            )

        if not info.visible:
            if not mt5.symbol_select(mt5_symbol(symbol), True):
                raise HTTPException(
                    status_code=503,
                    detail="Parite etkinleştirilemedi",
                )

            info = mt5.symbol_info(mt5_symbol(symbol))

            if info is None:
                raise HTTPException(
                    status_code=503,
                    detail="Parite bilgisi alınamadı",
                )

        if (
            info.volume_min <= 0
            or info.volume_step <= 0
            or info.volume_max < info.volume_min
        ):
            raise HTTPException(
                status_code=503,
                detail="MT5 lot sınırları geçersiz",
            )

        min_lot = Decimal(str(info.volume_min))
        max_lot = Decimal(str(info.volume_max))
        step = Decimal(str(info.volume_step))

        max_steps = int((max_lot - min_lot) // step)
        budget = balance * risk_percent / 100.0

        action = (
            mt5.ORDER_TYPE_BUY
            if direction == "BUY"
            else mt5.ORDER_TYPE_SELL
        )

        def stop_loss_amount(lot: Decimal) -> float:
            profit = mt5.order_calc_profit(
                action,
                mt5_symbol(symbol),
                float(lot),
                entry,
                stop_loss,
            )

            if profit is None or not math.isfinite(profit):
                raise HTTPException(
                    status_code=503,
                    detail="MT5 parasal risk hesaplayamadı",
                )

            loss = -float(profit)

            if loss <= 0:
                raise HTTPException(
                    status_code=503,
                    detail="MT5 Stop Loss için geçerli zarar hesaplayamadı",
                )

            return loss

        minimum_loss = stop_loss_amount(min_lot)

        selected_lot = None
        selected_loss = None
        status = "below_minimum"

        if minimum_loss <= budget:
            left = 0
            right = max_steps
            selected_step = 0
            selected_loss = minimum_loss

            while left <= right:
                middle = (left + right) // 2
                lot = min_lot + middle * step

                loss = stop_loss_amount(lot)

                if loss <= budget:
                    selected_step = middle
                    selected_loss = loss
                    left = middle + 1
                else:
                    right = middle - 1

            selected_lot = float(
                min_lot + selected_step * step
            )

            status = (
                "max_lot_reached"
                if selected_step == max_steps
                else "calculated"
            )

        return JSONResponse(
            content={
                "symbol": symbol,
                "direction": direction,
                "source": "MetaTrader 5 order_calc_profit",
                "demo_only": True,
                "order_sent": False,
                "account_currency": str(account.currency),
                "input_balance": balance,
                "risk_percent": risk_percent,
                "risk_budget": round(budget, 2),
                "entry": entry,
                "stop_loss": stop_loss,
                "volume_min": float(min_lot),
                "volume_max": float(max_lot),
                "volume_step": float(step),
                "min_lot_estimated_loss": round(
                    minimum_loss, 2
                ),
                "suggested_lot": selected_lot,
                "estimated_loss_at_sl": (
                    round(selected_loss, 2)
                    if selected_loss is not None
                    else None
                ),
                "status": status,
                "warning": (
                    "Bu sadece manuel DEMO risk hesaplamasıdır; "
                    "işlem sinyali veya emir değildir. "
                    "Komisyon, swap, kayma ve marjin yeterliliği "
                    "hesaplanmamıştır. "
                    "Fiyat güncelliği bu uç noktada doğrulanmaz."
                ),
            },
            headers={"Cache-Control": "no-store"},
        )
