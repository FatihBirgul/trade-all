import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException, Query
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from market_ai.engines import scenario as scenario_engine

from market_ai.config import (
    AI_MODEL,
    AI_PROVIDER,
    DEFAULT_TIMEFRAME,
    MARKET_DATA_PROVIDER,
    NEWS_PROVIDER,
    OUTCOME_EVAL_INTERVAL,
    OUTCOME_HORIZON_BARS,
    SUPPORTED_ASSETS,
    SUPPORTED_SYMBOLS,
    TIMEFRAMES,
)
from market_ai.db import db
from market_ai.engines import analysis as analysis_engine
from market_ai.engines import candlestick as candlestick_engine
from market_ai.engines import chart_patterns as chart_engine
from market_ai.engines import futures_positioning as futures_positioning_engine
from market_ai.engines import liquidation as liquidation_engine
from market_ai.engines import liquidity as liquidity_engine
from market_ai.engines import mtf as mtf_engine
from market_ai.engines import order_flow as order_flow_engine
from market_ai.engines import outcome as outcome_engine
from market_ai.engines import technical as technical_engine
from market_ai.models import AnalysisDoc, AnalysisRequest
from market_ai.providers.ai_provider import get_ai_provider
from market_ai.providers.liquidation_stream import get_liquidation_stream
from market_ai.providers.market_data import MarketDataError, get_provider
from market_ai.providers.news_provider import get_news_provider


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("market_ai")

app = FastAPI(title="Market AI")
api = APIRouter(prefix="/api")

ASSET_BY_SYMBOL = {
    a["symbol"]: a
    for a in SUPPORTED_ASSETS
}


# ----------------------------------------------------------------------------
# Liquidation stream lifecycle
# ----------------------------------------------------------------------------
LIQUIDATION_STREAM_SYMBOLS = list(
    SUPPORTED_SYMBOLS
)

_liquidation_stream = None


async def _start_liquidation_stream():
    global _liquidation_stream

    try:
        _liquidation_stream = get_liquidation_stream(
            LIQUIDATION_STREAM_SYMBOLS
        )

        await _liquidation_stream.start()

        logger.info(
            "Liquidation stream started for %s symbols.",
            len(
                LIQUIDATION_STREAM_SYMBOLS
            ),
        )

    except Exception:
        _liquidation_stream = None

        logger.exception(
            "Failed to start liquidation stream."
        )


async def _stop_liquidation_stream():
    global _liquidation_stream

    stream = _liquidation_stream

    if stream is None:
        return

    try:
        await stream.stop()

        logger.info(
            "Liquidation stream stopped."
        )

    except Exception:
        logger.exception(
            "Failed to stop liquidation stream."
        )

    finally:
        _liquidation_stream = None


@asynccontextmanager
async def lifespan(
    application: FastAPI,
):
    await _start_liquidation_stream()

    try:
        yield

    finally:
        await _stop_liquidation_stream()


app.router.lifespan_context = lifespan


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
async def _get_liquidation(
    symbol: str,
    provider=None,
) -> Optional[Dict]:
    """Analyze recent cached liquidation events for one symbol."""
    stream = _liquidation_stream

    if stream is None:
        return None

    try:
        events = await stream.get_events(
            symbol=symbol
        )

        if not events:
            return {
                **liquidation_engine.analyze(
                    []
                ),
                "stream_connected": (
                    stream.connected
                ),
                "stream_event_count": 0,
            }

        result = liquidation_engine.analyze(
            events
        )

        result[
            "stream_connected"
        ] = stream.connected

        result[
            "stream_event_count"
        ] = len(events)

        result[
            "stream_last_event_timestamp"
        ] = stream.last_event_timestamp

        return result

    except (
        ValueError,
        TypeError,
        KeyError,
    ) as e:
        logger.warning(
            "Liquidation analysis unavailable for %s: %s",
            symbol,
            e,
        )

        return None


async def _build_timeframe_snapshot(
    symbol: str,
    timeframe: str,
    provider,
    news_data: Dict,
) -> Optional[Dict]:
    """Build one deterministic timeframe snapshot for MTF."""
    try:
        candles = await provider.get_klines(
            symbol,
            TIMEFRAMES[timeframe],
            limit=300,
        )

        tech = technical_engine.compute(
            candles,
            timeframe,
        )

        candles_p = candlestick_engine.detect(
            candles
        )

        charts_p = chart_engine.detect(
            candles
        )

        agg = analysis_engine.aggregate(
            tech,
            candles_p,
            charts_p,
            news_data,
        )

        return {
            "timeframe": timeframe,
            "direction": agg.get(
                "direction",
                "neutral",
            ),
            "confidence": agg.get(
                "confidence",
                0.0,
            ),
            "final_score": agg.get(
                "final_score",
                0.0,
            ),
            "quality": agg.get(
                "quality",
                {},
            ),
        }

    except (
        MarketDataError,
        ValueError,
        KeyError,
        TypeError,
    ) as e:
        logger.warning(
            "MTF snapshot unavailable for %s %s: %s",
            symbol,
            timeframe,
            e,
        )
        return None


def _build_mtf_snapshots(
    current_timeframe: str,
    current_aggregate: Dict,
    other_results,
) -> Dict[str, Dict]:
    snapshots: Dict[str, Dict] = {
        current_timeframe: {
            "timeframe": current_timeframe,
            "direction": current_aggregate.get(
                "direction",
                "neutral",
            ),
            "confidence": current_aggregate.get(
                "confidence",
                0.0,
            ),
            "final_score": current_aggregate.get(
                "final_score",
                0.0,
            ),
            "quality": current_aggregate.get(
                "quality",
                {},
            ),
        }
    }

    for result in other_results:
        if not result:
            continue

        timeframe = result.get(
            "timeframe"
        )

        if not timeframe:
            continue

        snapshots[
            timeframe
        ] = result

    return snapshots


async def _get_order_flow(
    symbol: str,
    provider,
) -> Optional[Dict]:
    """Fetch and analyze latest Futures aggregate trades."""
    try:
        trades = await provider.get_aggregate_trades(
            symbol,
            limit=500,
        )

        return order_flow_engine.analyze(
            trades
        )

    except (
        MarketDataError,
        ValueError,
        KeyError,
        TypeError,
    ) as e:
        logger.warning(
            "Order Flow unavailable for %s: %s",
            symbol,
            e,
        )
        return None


async def _get_liquidity(
    symbol: str,
    provider,
) -> Optional[Dict]:
    """Fetch and analyze latest Futures order-book depth."""
    try:
        order_book = await provider.get_order_book(
            symbol,
            limit=100,
        )

        return liquidity_engine.analyze(
            order_book
        )

    except (
        MarketDataError,
        ValueError,
        KeyError,
        TypeError,
    ) as e:
        logger.warning(
            "Liquidity unavailable for %s: %s",
            symbol,
            e,
        )
        return None


async def _get_futures_positioning(
    symbol: str,
    price_change_pct: Optional[float],
    provider,
) -> Optional[Dict]:
    """Fetch current/history OI and funding."""
    try:
        current_oi, oi_history, funding_history = (
            await asyncio.gather(
                provider.get_open_interest(
                    symbol
                ),
                provider.get_open_interest_history(
                    symbol,
                    period="5m",
                    limit=10,
                ),
                provider.get_funding_rate(
                    symbol,
                    limit=10,
                ),
            )
        )

        previous_oi = None

        if len(
            oi_history
        ) >= 2:
            latest_history = (
                oi_history[-1]
            )

            previous_history = (
                oi_history[-2]
            )

            current_timestamp = int(
                current_oi.get(
                    "timestamp",
                    0,
                )
            )

            latest_history_timestamp = int(
                latest_history.get(
                    "timestamp",
                    0,
                )
            )

            if (
                latest_history_timestamp
                <= current_timestamp
            ):
                previous_oi = (
                    previous_history
                )
            else:
                previous_oi = (
                    latest_history
                )

        return futures_positioning_engine.analyze(
            current_open_interest=current_oi,
            previous_open_interest=previous_oi,
            funding_history=funding_history,
            price_change_pct=price_change_pct,
        )

    except (
        MarketDataError,
        ValueError,
        KeyError,
        TypeError,
    ) as e:
        logger.warning(
            "Futures positioning unavailable for %s: %s",
            symbol,
            e,
        )
        return None


# ----------------------------------------------------------------------------
# Meta
# ----------------------------------------------------------------------------
@api.get("/")
async def root():
    return {
        "message": "Market AI API",
        "status": "ok",
    }


@api.get("/health")
async def health():
    stream = _liquidation_stream

    return {
        "status": "ok",
        "liquidation_stream": {
            "available": stream is not None,
            "connected": (
                stream.connected
                if stream
                else False
            ),
            "cached_events": (
                await stream.event_count()
                if stream
                else 0
            ),
        },
    }


@api.get("/config")
async def config():
    ai = get_ai_provider()
    news = get_news_provider()

    return {
        "providers": {
            "market_data": {
                "name": MARKET_DATA_PROVIDER,
                "available": True,
                "realtime": True,
            },
            "ai": {
                "name": AI_PROVIDER,
                "model": AI_MODEL,
                "available": ai.available,
                "capabilities": [
                    "vision",
                    "reasoning",
                ],
            },
            "news": {
                "name": NEWS_PROVIDER,
                "available": news.available,
            },
            "liquidation_stream": {
                "available": _liquidation_stream
                is not None,
                "connected": (
                    _liquidation_stream.connected
                    if _liquidation_stream
                    else False
                ),
            },
        },
        "assets": SUPPORTED_ASSETS,
        "timeframes": list(
            TIMEFRAMES.keys()
        ),
        "default_timeframe": DEFAULT_TIMEFRAME,
        "disclaimer": (
            "Market AI is an analytical decision-support tool. "
            "It does not provide financial advice or guarantees."
        ),
    }


@api.get("/assets")
async def assets():
    return SUPPORTED_ASSETS


# ----------------------------------------------------------------------------
# Markets
# ----------------------------------------------------------------------------
@api.get("/markets")
async def markets():
    provider = get_provider()

    async def one(a):
        try:
            ticker = await provider.get_ticker(
                a["symbol"]
            )

            return {
                **a,
                **ticker,
                "available": True,
            }

        except MarketDataError:
            return {
                **a,
                "available": False,
            }

    results = await asyncio.gather(
        *[
            one(a)
            for a in SUPPORTED_ASSETS
        ]
    )

    return {
        "markets": results,
        "provider": MARKET_DATA_PROVIDER,
    }


@api.get("/markets/{symbol}")
async def market_detail(
    symbol: str,
    timeframe: str = Query(
        DEFAULT_TIMEFRAME
    ),
):
    symbol = symbol.upper()

    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            404,
            "Unsupported symbol",
        )

    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME

    provider = get_provider()

    try:
        ticker = await provider.get_ticker(
            symbol
        )

        candles = await provider.get_klines(
            symbol,
            TIMEFRAMES[timeframe],
            limit=100,
        )

    except MarketDataError as e:
        raise HTTPException(
            503,
            f"Market data unavailable: {e}",
        )

    return {
        **ASSET_BY_SYMBOL[symbol],
        **ticker,
        "timeframe": timeframe,
        "sparkline": [
            c["close"]
            for c in candles
        ],
        "available": True,
    }


@api.get("/markets/{symbol}/klines")
async def klines(
    symbol: str,
    timeframe: str = Query(
        DEFAULT_TIMEFRAME
    ),
    limit: int = 200,
):
    symbol = symbol.upper()

    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            404,
            "Unsupported symbol",
        )

    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME

    provider = get_provider()

    try:
        candles = await provider.get_klines(
            symbol,
            TIMEFRAMES[timeframe],
            limit=min(limit, 500),
        )

    except MarketDataError as e:
        raise HTTPException(
            503,
            f"Market data unavailable: {e}",
        )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "candles": candles,
    }


# ----------------------------------------------------------------------------
# Technical
# ----------------------------------------------------------------------------
@api.get("/markets/{symbol}/technical")
async def technical(
    symbol: str,
    timeframe: str = Query(
        DEFAULT_TIMEFRAME
    ),
):
    symbol = symbol.upper()

    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            404,
            "Unsupported symbol",
        )

    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME

    provider = get_provider()

    try:
        candles = await provider.get_klines(
            symbol,
            TIMEFRAMES[timeframe],
            limit=300,
        )

    except MarketDataError as e:
        raise HTTPException(
            503,
            f"Market data unavailable: {e}",
        )

    tech = technical_engine.compute(
        candles,
        timeframe,
    )

    candles_p = candlestick_engine.detect(
        candles
    )

    charts_p = chart_engine.detect(
        candles
    )

    agg = analysis_engine.aggregate(
        tech,
        candles_p,
        charts_p,
        {"sentiment": {"score": 0}},
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "technical": tech,
        "candlestick_patterns": candles_p,
        "chart_patterns": charts_p,
        "scores": agg["scores"],
        "direction": agg["direction"],
        "confidence": agg["confidence"],
        "quality": agg.get(
            "quality",
            {},
        ),
    }


# ----------------------------------------------------------------------------
# News
# ----------------------------------------------------------------------------
@api.get("/news")
async def news(
    symbol: Optional[str] = None,
):
    provider = get_news_provider()

    return await provider.get_news(
        (symbol or "").upper()
    )


# ----------------------------------------------------------------------------
# Fallback narrative
# ----------------------------------------------------------------------------
def _fallback_narrative(
    direction,
    scores,
    ind,
    structure,
    candles_p,
    charts_p,
    zones,
    news,
):
    supporting = []
    contradicting = []

    def add(
        lst,
        cond,
        text,
    ):
        if cond:
            lst.append(text)

    price = ind.get(
        "price"
    )

    add(
        supporting,
        direction == "bullish"
        and ind.get("ema50") is not None
        and price is not None
        and price > ind["ema50"],
        "Price is trading above the 50 EMA, a sign of near-term strength.",
    )

    add(
        supporting,
        direction == "bearish"
        and ind.get("ema50") is not None
        and price is not None
        and price < ind["ema50"],
        "Price is trading below the 50 EMA, a sign of near-term weakness.",
    )

    add(
        supporting,
        structure.get(
            "label"
        ) == "uptrend"
        and direction == "bullish",
        "Market structure shows higher highs and higher lows.",
    )

    add(
        supporting,
        structure.get(
            "label"
        ) == "downtrend"
        and direction == "bearish",
        "Market structure shows lower highs and lower lows.",
    )

    if ind.get(
        "macd_hist"
    ) is not None:
        add(
            supporting,
            (
                ind["macd_hist"] > 0
            )
            == (
                direction == "bullish"
            ),
            (
                f"MACD histogram "
                f"({ind['macd_hist']}) supports "
                f"the {direction} bias."
            ),
        )

    for p in candles_p[:3]:
        if p[
            "classification"
        ] == direction:
            supporting.append(
                "Candlestick pattern detected: "
                f"{p['name']} "
                f"({p['classification']})."
            )

    for p in charts_p[:3]:
        if p[
            "classification"
        ] == direction:
            supporting.append(
                "Chart pattern detected: "
                f"{p['name']} "
                f"({p['classification']})."
            )

    rsi = ind.get(
        "rsi14"
    )

    add(
        contradicting,
        rsi is not None and rsi > 70,
        f"RSI is elevated at {rsi}; the move may be overextended.",
    )

    add(
        contradicting,
        rsi is not None and rsi < 30,
        f"RSI is depressed at {rsi}; a relief bounce is possible.",
    )

    add(
        contradicting,
        (ind.get("volume_ratio") or 1) < 0.9,
        "Volume is below its 20-period average, so conviction behind the move is limited.",
    )

    for p in candles_p[:3]:
        if p[
            "classification"
        ] not in (
            direction,
            "neutral",
        ):
            contradicting.append(
                "Counter-signal: "
                f"{p['name']} "
                f"({p['classification']}) argues the other way."
            )

    contradicting.append(
        "News sentiment is unavailable, so the analysis is technical-only."
    )

    if not supporting:
        supporting.append(
            f"Component scores lean {direction} on balance."
        )

    if not contradicting:
        contradicting.append(
            "Signals are mixed; treat any level as provisional until confirmed."
        )

    summary = (
        f"Technical composite leans {direction}. "
        "This is an analytical read of current structure, "
        "momentum and levels — not a guarantee. "
        "Confirm with your own risk management."
    )

    scenarios = scenario_engine.build(direction, zones)

    return {
        "summary": summary,
        "scenarios": scenarios,
        "supporting_reasons": supporting[:6],
        "contradicting_reasons": contradicting[:5],
    }


# ----------------------------------------------------------------------------
# Analysis
# ----------------------------------------------------------------------------
@api.post("/analysis")
async def create_analysis(
    req: AnalysisRequest,
):
    symbol = req.symbol.upper()

    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            400,
            "Unsupported symbol",
        )

    timeframe = (
        req.timeframe
        if req.timeframe in TIMEFRAMES
        else DEFAULT_TIMEFRAME
    )

    asset = ASSET_BY_SYMBOL[
        symbol
    ]

    provider = get_provider()

    # ------------------------------------------------------------------------
    # 1. Current timeframe market data
    # ------------------------------------------------------------------------
    try:
        ticker = await provider.get_ticker(
            symbol
        )

        current_candles = (
            await provider.get_klines(
                symbol,
                TIMEFRAMES[timeframe],
                limit=300,
            )
        )

        market_ok = True

    except MarketDataError as e:
        raise HTTPException(
            503,
            (
                "Market data unavailable — "
                f"cannot analyze: {e}"
            ),
        )

    # ------------------------------------------------------------------------
    # 2. Current timeframe deterministic engines
    # ------------------------------------------------------------------------
    current_tech = (
        technical_engine.compute(
            current_candles,
            timeframe,
        )
    )

    current_candles_p = (
        candlestick_engine.detect(
            current_candles
        )
    )

    current_charts_p = (
        chart_engine.detect(
            current_candles
        )
    )

    # ------------------------------------------------------------------------
    # 3. News
    # ------------------------------------------------------------------------
    news_data = (
        await get_news_provider().get_news(
            symbol
        )
    )

    # ------------------------------------------------------------------------
    # 4. Baseline current timeframe aggregate
    # ------------------------------------------------------------------------
    current_aggregate = (
        analysis_engine.aggregate(
            current_tech,
            current_candles_p,
            current_charts_p,
            news_data,
        )
    )

    # ------------------------------------------------------------------------
    # 5. Futures price context
    # ------------------------------------------------------------------------
    price_change_pct = ticker.get(
        "change_24h_pct"
    )

    # ------------------------------------------------------------------------
    # 6. Fetch auxiliary signals in parallel
    # ------------------------------------------------------------------------
    auxiliary_timeframes = [
        tf
        for tf in TIMEFRAMES.keys()
        if tf != timeframe
    ]

    auxiliary_results_task = asyncio.gather(
        *[
            _build_timeframe_snapshot(
                symbol,
                tf,
                provider,
                news_data,
            )
            for tf in auxiliary_timeframes
        ]
    )

    order_flow_task = _get_order_flow(
        symbol,
        provider,
    )

    liquidity_task = _get_liquidity(
        symbol,
        provider,
    )

    futures_positioning_task = (
        _get_futures_positioning(
            symbol,
            price_change_pct,
            provider,
        )
    )

    liquidation_task = _get_liquidation(
        symbol,
        provider,
    )

    (
        auxiliary_results,
        order_flow_data,
        liquidity_data,
        futures_positioning_data,
        liquidation_data,
    ) = await asyncio.gather(
        auxiliary_results_task,
        order_flow_task,
        liquidity_task,
        futures_positioning_task,
        liquidation_task,
    )

    mtf_snapshots = _build_mtf_snapshots(
        timeframe,
        current_aggregate,
        auxiliary_results,
    )

    # ------------------------------------------------------------------------
    # 7. MTF
    # ------------------------------------------------------------------------
    try:
        mtf_result = mtf_engine.analyze(
            timeframe,
            mtf_snapshots,
        )

    except (
        ValueError,
        TypeError,
        KeyError,
    ) as e:
        logger.exception(
            "MTF analysis failed for %s %s",
            symbol,
            timeframe,
        )

        mtf_result = {
            "direction": "neutral",
            "current_timeframe": timeframe,
            "current": {
                "timeframe": timeframe,
                "direction": current_aggregate.get(
                    "direction",
                    "neutral",
                ),
                "confidence": current_aggregate.get(
                    "confidence",
                    0.0,
                ),
                "gate_passed": current_aggregate.get(
                    "quality",
                    {},
                ).get(
                    "gate_passed",
                    False,
                ),
                "tradeable": False,
                "final_score": current_aggregate.get(
                    "final_score",
                    0.0,
                ),
                "available": True,
            },
            "higher_timeframe_bias": {
                "timeframe": None,
                "direction": "neutral",
                "confidence": 0.0,
                "gate_passed": False,
                "tradeable": False,
                "final_score": 0.0,
            },
            "higher_timeframe_alignment": {
                "direction": "neutral",
                "agreement_ratio": 0.0,
                "conflict_ratio": 0.0,
                "supporting_count": 0,
                "opposing_count": 0,
                "available_count": 0,
                "evidence": [],
            },
            "lower_timeframe_confirmation": {
                "direction": "neutral",
                "agreement_ratio": 0.0,
                "conflict_ratio": 0.0,
                "supporting_count": 0,
                "opposing_count": 0,
                "available_count": 0,
                "evidence": [],
            },
            "alignment_ratio": 0.0,
            "conflict_ratio": 0.0,
            "supporting_count": 0,
            "opposing_count": 0,
            "evidence": [],
            "error": str(e),
        }

    # ------------------------------------------------------------------------
    # 8. Final aggregate
    # ------------------------------------------------------------------------
    agg = analysis_engine.aggregate(
        current_tech,
        current_candles_p,
        current_charts_p,
        news_data,
        mtf=mtf_result,
        order_flow=order_flow_data,
        liquidity=liquidity_data,
        futures_positioning=(
            futures_positioning_data
        ),
        liquidation=liquidation_data,
    )

    ai = get_ai_provider()

    # ------------------------------------------------------------------------
    # 9. Vision
    # ------------------------------------------------------------------------
    vision = {}

    if req.image_base64:
        v, verr = await ai.analyze_image(
            req.image_base64,
            symbol,
            timeframe,
        )

        if v:
            vision = v
        else:
            vision = {
                "available": False,
                "error": verr,
            }

    # ------------------------------------------------------------------------
    # 10. AI reasoning
    # ------------------------------------------------------------------------
    reason_payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "price": current_tech[
            "price"
        ],
        "direction": agg[
            "direction"
        ],
        "confidence": agg[
            "confidence"
        ],
        "final_score": agg.get(
            "final_score",
            0.0,
        ),
        "scores": agg[
            "scores"
        ],
        "indicators": current_tech[
            "indicators"
        ],
        "structure": current_tech[
            "structure"
        ],
        "levels": current_tech[
            "levels"
        ],
        "zones": agg[
            "zones"
        ],
        "quality": agg.get(
            "quality",
            {},
        ),
        "mtf": mtf_result,
        "order_flow": (
            order_flow_data
            or {}
        ),
        "liquidity": (
            liquidity_data
            or {}
        ),
        "futures_positioning": (
            futures_positioning_data
            or {}
        ),
        "liquidation": (
            liquidation_data
            or {}
        ),
        "candlestick_patterns": (
            current_candles_p
        ),
        "chart_patterns": (
            current_charts_p
        ),
        "vision": vision or {},
        "news_available": news_data.get(
            "available",
            False,
        ),
    }

    narrative, _ = await ai.reason(
        reason_payload
    )

    ai_available = (
        narrative is not None
    )

    if not narrative:
        narrative = _fallback_narrative(
            agg["direction"],
            agg["scores"],
            current_tech[
                "indicators"
            ],
            current_tech[
                "structure"
            ],
            current_candles_p,
            current_charts_p,
            agg["zones"],
            news_data,
        )
    else:
        narrative["scenarios"] = scenario_engine.sanitize(
            narrative.get("scenarios"), scenario_engine.build(agg["direction"], agg["zones"])
        )

    # ------------------------------------------------------------------------
    # 11. Persist
    # ------------------------------------------------------------------------
    doc = AnalysisDoc(
        symbol=symbol,
        base=asset["base"],
        quote=asset["quote"],
        timeframe=timeframe,
        price_at_analysis=current_tech[
            "price"
        ],
        change_24h_pct=ticker.get(
            "change_24h_pct"
        ),
        direction=agg[
            "direction"
        ],
        confidence=agg[
            "confidence"
        ],
        final_score=agg.get(
            "final_score",
            0.0,
        ),
        scores=agg[
            "scores"
        ],
        indicators=current_tech[
            "indicators"
        ],
        candlestick_patterns=(
            current_candles_p
        ),
        chart_patterns=(
            current_charts_p
        ),
        levels=current_tech[
            "levels"
        ],
        zones=agg[
            "zones"
        ],
        quality=agg.get(
            "quality",
            {},
        ),
        news_sentiment=news_data.get(
            "sentiment",
            {},
        ),
        scenarios=narrative.get(
            "scenarios",
            {},
        ),
        supporting_reasons=narrative.get(
            "supporting_reasons",
            [],
        ),
        contradicting_reasons=narrative.get(
            "contradicting_reasons",
            [],
        ),
        summary=narrative.get(
            "summary",
            "",
        ),
        vision=vision or {},
        ai_available=ai_available,
        market_data_available=market_ok,
        has_image=bool(
            req.image_base64
        ),
        image_base64=(
            req.image_base64
        ),
    )

    res = await db.analyses.insert_one(
        doc.to_mongo()
    )

    saved = await db.analyses.find_one(
        {
            "_id": res.inserted_id
        }
    )

    out = AnalysisDoc.from_mongo(
        saved
    )

    return out.model_dump()


# ----------------------------------------------------------------------------
# History
# ----------------------------------------------------------------------------
@api.get("/history")
async def history(
    limit: int = 50,
):
    cursor = (
        db.analyses
        .find()
        .sort(
            "created_at",
            -1,
        )
        .limit(
            min(
                limit,
                100,
            )
        )
    )

    items = []

    async for doc in cursor:
        m = AnalysisDoc.from_mongo(
            doc
        )

        items.append(
            m.model_dump()
        )

    return {
        "items": items
    }


@api.get("/history/{item_id}")
async def history_detail(
    item_id: str,
):
    try:
        doc = await db.analyses.find_one(
            {
                "_id": ObjectId(
                    item_id
                )
            }
        )

    except Exception:
        raise HTTPException(
            400,
            "Invalid id",
        )

    if not doc:
        raise HTTPException(
            404,
            "Not found",
        )

    return AnalysisDoc.from_mongo(
        doc
    ).model_dump()


@api.delete("/history/{item_id}")
async def history_delete(
    item_id: str,
):
    try:
        result = await db.analyses.delete_one(
            {
                "_id": ObjectId(
                    item_id
                )
            }
        )

    except Exception:
        raise HTTPException(
            400,
            "Invalid id",
        )

    return {
        "deleted": result.deleted_count
    }


# ----------------------------------------------------------------------------
# Outcome tracking / performance
# ----------------------------------------------------------------------------
async def _evaluate_doc(
    doc: dict,
) -> dict:
    analysis = (
        AnalysisDoc
        .from_mongo(doc)
        .model_dump()
    )

    timeframe = analysis.get(
        "timeframe",
        DEFAULT_TIMEFRAME,
    )

    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME

    start_ms = outcome_engine.created_at_ms(
        analysis.get(
            "created_at",
            "",
        )
    )

    if start_ms is None:
        return {
            "status": "unresolvable",
            "note": "Bad timestamp.",
        }

    eval_interval = (
        OUTCOME_EVAL_INTERVAL.get(
            timeframe,
            TIMEFRAMES[
                DEFAULT_TIMEFRAME
            ],
        )
    )

    horizon_bars = int(
        OUTCOME_HORIZON_BARS.get(
            timeframe,
            120,
        )
    )

    signal_ms = {
        "1m": 60_000,
        "5m": 5 * 60_000,
        "15m": 15 * 60_000,
        "1H": 60 * 60_000,
        "4H": 4 * 60 * 60_000,
        "1D": 24 * 60 * 60_000,
    }

    horizon_ms = (
        signal_ms.get(
            timeframe,
            signal_ms[
                DEFAULT_TIMEFRAME
            ],
        )
        * horizon_bars
    )

    end_ms = (
        start_ms
        + horizon_ms
    )

    provider = get_provider()

    try:
        candles = (
            await provider.get_klines_since(
                analysis["symbol"],
                eval_interval,
                start_ms,
                limit=1000,
                end_ms=end_ms,
            )
        )

        candles = [
            c
            for c in candles
            if (
                c["time"] >= start_ms
                and c["time"] <= end_ms
            )
        ]

    except MarketDataError:
        return analysis.get(
            "outcome"
        ) or {
            "status": "pending",
            "note": "Price data unavailable.",
        }

    result = outcome_engine.evaluate(
        analysis,
        candles,
    )

    result[
        "evaluation_timeframe"
    ] = eval_interval

    result[
        "analysis_timeframe"
    ] = timeframe

    result[
        "horizon_bars"
    ] = horizon_bars

    return result


@api.post("/history/evaluate-all")
async def evaluate_all():
    """Re-check every unresolved directional analysis."""

    cursor = (
        db.analyses
        .find()
        .sort(
            "created_at",
            -1,
        )
        .limit(200)
    )

    updated = 0

    async for doc in cursor:
        current = (
            (
                doc.get("outcome")
                or {}
            ).get(
                "status"
            )
        )

        if current in (
            "win",
            "loss",
            "neutral",
            "ambiguous",
        ):
            continue

        result = await _evaluate_doc(
            doc
        )

        await db.analyses.update_one(
            {
                "_id": doc["_id"]
            },
            {
                "$set": {
                    "outcome": result
                }
            },
        )

        updated += 1

    return {
        "evaluated": updated,
        "performance": await _performance(),
    }


async def _performance() -> dict:
    outcomes = []

    per_dir = {
        "bullish": [],
        "bearish": [],
    }

    cursor = db.analyses.find(
        {},
        {
            "outcome": 1,
            "direction": 1,
        },
    )

    async for doc in cursor:
        outcome = (
            doc.get("outcome")
            or {
                "status": "pending"
            }
        )

        outcomes.append(
            outcome
        )

        direction = doc.get(
            "direction"
        )

        if direction in per_dir:
            per_dir[
                direction
            ].append(
                outcome
            )

    summary = outcome_engine.summarize(
        outcomes
    )

    summary["by_direction"] = {
        "bullish": outcome_engine.summarize(
            per_dir["bullish"]
        ),
        "bearish": outcome_engine.summarize(
            per_dir["bearish"]
        ),
    }

    return summary


@api.get("/performance")
async def performance():
    return await _performance()


app.include_router(api)

# Opt-in local V2 integration; unset V2_DB_PATH leaves V1 startup/routes intact.
# The standalone `market_ai.v2.api:app_from_env` needs no MongoDB or AI imports.
if os.environ.get("V2_DB_PATH"):
    from market_ai.v2.api import create_runtime, install_v2

    install_v2(app, create_runtime(
        os.environ["V2_DB_PATH"], token=os.environ.get("V2_API_TOKEN", ""),
        mode=os.environ.get("V2_DATA_MODE", "live"),
    ))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
