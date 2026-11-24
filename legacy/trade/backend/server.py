import logging
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import asyncio

from bson import ObjectId
from fastapi import APIRouter, FastAPI, HTTPException, Query
from starlette.middleware.cors import CORSMiddleware

from market_ai.config import (
    AI_MODEL,
    AI_PROVIDER,
    DEFAULT_TIMEFRAME,
    MARKET_DATA_PROVIDER,
    NEWS_PROVIDER,
    SUPPORTED_ASSETS,
    SUPPORTED_SYMBOLS,
    TIMEFRAMES,
)
from market_ai.db import db
from market_ai.engines import analysis as analysis_engine
from market_ai.engines import candlestick as candlestick_engine
from market_ai.engines import chart_patterns as chart_engine
from market_ai.engines import outcome as outcome_engine
from market_ai.engines import technical as technical_engine
from market_ai.models import AnalysisDoc, AnalysisRequest, utcnow_iso
from market_ai.providers.ai_provider import get_ai_provider
from market_ai.providers.market_data import MarketDataError, get_provider
from market_ai.providers.news_provider import get_news_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("market_ai")

app = FastAPI(title="Market AI")
api = APIRouter(prefix="/api")

ASSET_BY_SYMBOL = {a["symbol"]: a for a in SUPPORTED_ASSETS}


# ----------------------------------------------------------------------------
# Meta
# ----------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"message": "Market AI API", "status": "ok"}


@api.get("/health")
async def health():
    return {"status": "ok"}


@api.get("/config")
async def config():
    ai = get_ai_provider()
    news = get_news_provider()
    return {
        "providers": {
            "market_data": {"name": MARKET_DATA_PROVIDER, "available": True, "realtime": True},
            "ai": {
                "name": AI_PROVIDER,
                "model": AI_MODEL,
                "available": ai.available,
                "capabilities": ["vision", "reasoning"],
            },
            "news": {"name": NEWS_PROVIDER, "available": news.available},
        },
        "assets": SUPPORTED_ASSETS,
        "timeframes": list(TIMEFRAMES.keys()),
        "default_timeframe": DEFAULT_TIMEFRAME,
        "disclaimer": "Market AI is an analytical decision-support tool. It does not provide financial advice or guarantees.",
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
            t = await provider.get_ticker(a["symbol"])
            return {**a, **t, "available": True}
        except MarketDataError:
            return {**a, "available": False}

    results = await asyncio.gather(*[one(a) for a in SUPPORTED_ASSETS])
    return {"markets": results, "provider": MARKET_DATA_PROVIDER}


@api.get("/markets/{symbol}")
async def market_detail(symbol: str, timeframe: str = Query(DEFAULT_TIMEFRAME)):
    symbol = symbol.upper()
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(404, "Unsupported symbol")
    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME
    provider = get_provider()
    try:
        ticker = await provider.get_ticker(symbol)
        candles = await provider.get_klines(symbol, TIMEFRAMES[timeframe], limit=100)
    except MarketDataError as e:
        raise HTTPException(503, f"Market data unavailable: {e}")
    return {
        **ASSET_BY_SYMBOL[symbol],
        **ticker,
        "timeframe": timeframe,
        "sparkline": [c["close"] for c in candles],
        "available": True,
    }


@api.get("/markets/{symbol}/klines")
async def klines(symbol: str, timeframe: str = Query(DEFAULT_TIMEFRAME), limit: int = 200):
    symbol = symbol.upper()
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(404, "Unsupported symbol")
    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME
    provider = get_provider()
    try:
        candles = await provider.get_klines(symbol, TIMEFRAMES[timeframe], limit=min(limit, 500))
    except MarketDataError as e:
        raise HTTPException(503, f"Market data unavailable: {e}")
    return {"symbol": symbol, "timeframe": timeframe, "candles": candles}


@api.get("/markets/{symbol}/technical")
async def technical(symbol: str, timeframe: str = Query(DEFAULT_TIMEFRAME)):
    symbol = symbol.upper()
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(404, "Unsupported symbol")
    if timeframe not in TIMEFRAMES:
        timeframe = DEFAULT_TIMEFRAME
    provider = get_provider()
    try:
        candles = await provider.get_klines(symbol, TIMEFRAMES[timeframe], limit=300)
    except MarketDataError as e:
        raise HTTPException(503, f"Market data unavailable: {e}")
    tech = technical_engine.compute(candles)
    candles_p = candlestick_engine.detect(candles)
    charts_p = chart_engine.detect(candles)
    agg = analysis_engine.aggregate(tech, candles_p, charts_p, {"sentiment": {"score": 0}})
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "technical": tech,
        "candlestick_patterns": candles_p,
        "chart_patterns": charts_p,
        "scores": agg["scores"],
        "direction": agg["direction"],
        "confidence": agg["confidence"],
    }


# ----------------------------------------------------------------------------
# News
# ----------------------------------------------------------------------------
@api.get("/news")
async def news(symbol: Optional[str] = None):
    provider = get_news_provider()
    data = await provider.get_news((symbol or "").upper())
    return data


# ----------------------------------------------------------------------------
# Analysis
# ----------------------------------------------------------------------------
def _fallback_narrative(direction, scores, ind, structure, candles_p, charts_p, zones, news):
    supporting, contradicting = [], []

    def add(lst, cond, text):
        if cond:
            lst.append(text)

    price = ind.get("price")
    add(supporting, direction == "bullish" and ind.get("ema50") and price > ind["ema50"],
        "Price is trading above the 50 EMA, a sign of near-term strength.")
    add(supporting, direction == "bearish" and ind.get("ema50") and price < ind["ema50"],
        "Price is trading below the 50 EMA, a sign of near-term weakness.")
    add(supporting, structure.get("label") == "uptrend" and direction == "bullish",
        "Market structure shows higher highs and higher lows.")
    add(supporting, structure.get("label") == "downtrend" and direction == "bearish",
        "Market structure shows lower highs and lower lows.")
    if ind.get("macd_hist") is not None:
        add(supporting, (ind["macd_hist"] > 0) == (direction == "bullish"),
            f"MACD histogram ({ind['macd_hist']}) supports the {direction} bias.")
    for p in candles_p[:3]:
        if p["classification"] == direction:
            supporting.append(f"Candlestick pattern detected: {p['name']} ({p['classification']}).")
    for p in charts_p[:3]:
        if p["classification"] == direction:
            supporting.append(f"Chart pattern detected: {p['name']} ({p['classification']}).")

    rsi = ind.get("rsi14")
    add(contradicting, rsi is not None and rsi > 70, f"RSI is elevated at {rsi}; the move may be overextended.")
    add(contradicting, rsi is not None and rsi < 30, f"RSI is depressed at {rsi}; a relief bounce is possible.")
    add(contradicting, (ind.get("volume_ratio") or 1) < 0.9,
        "Volume is below its 20-period average, so conviction behind the move is limited.")
    for p in candles_p[:3]:
        if p["classification"] not in (direction, "neutral"):
            contradicting.append(f"Counter-signal: {p['name']} ({p['classification']}) argues the other way.")
    contradicting.append("News sentiment is unavailable, so the analysis is technical-only.")

    if not supporting:
        supporting.append(f"Component scores lean {direction} on balance.")
    if not contradicting:
        contradicting.append("Signals are mixed; treat any level as provisional until confirmed.")

    summary = (
        f"Technical composite leans {direction}. This is an analytical read of current structure, momentum "
        f"and levels — not a guarantee. Confirm with your own risk management."
    )
    scenarios = {
        "bullish": f"If price holds above {zones.get('entry_low')} and reclaims {zones.get('target_1')}, momentum could extend toward {zones.get('target_2')}.",
        "bearish": f"A loss of {zones.get('invalidation')} would invalidate the {direction} case and open downside risk.",
        "neutral": "If price stays inside the current range, expect chop until a level breaks with volume.",
    }
    return {
        "summary": summary,
        "scenarios": scenarios,
        "supporting_reasons": supporting[:6],
        "contradicting_reasons": contradicting[:5],
    }


@api.post("/analysis")
async def create_analysis(req: AnalysisRequest):
    symbol = req.symbol.upper()
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(400, "Unsupported symbol")
    timeframe = req.timeframe if req.timeframe in TIMEFRAMES else DEFAULT_TIMEFRAME
    asset = ASSET_BY_SYMBOL[symbol]
    provider = get_provider()

    # 1. Market data (required — if unavailable we cannot produce real analysis)
    try:
        ticker = await provider.get_ticker(symbol)
        candles = await provider.get_klines(symbol, TIMEFRAMES[timeframe], limit=300)
        market_ok = True
    except MarketDataError as e:
        raise HTTPException(503, f"Market data unavailable — cannot analyze: {e}")

    # 2. Deterministic engines
    tech = technical_engine.compute(candles)
    candles_p = candlestick_engine.detect(candles)
    charts_p = chart_engine.detect(candles)

    # 3. News (may be unavailable)
    news_data = await get_news_provider().get_news(symbol)

    # 4. Aggregate scores + zones (deterministic)
    agg = analysis_engine.aggregate(tech, candles_p, charts_p, news_data)

    ai = get_ai_provider()

    # 5. Vision pass (optional)
    vision, vision_err = {}, None
    if req.image_base64:
        v, verr = await ai.analyze_image(req.image_base64, symbol, timeframe)
        if v:
            vision = v
        else:
            vision = {"available": False, "error": verr}

    # 6. Reasoning pass (structured -> narrative), with deterministic fallback
    reason_payload = {
        "symbol": symbol,
        "timeframe": timeframe,
        "price": tech["price"],
        "direction": agg["direction"],
        "confidence": agg["confidence"],
        "scores": agg["scores"],
        "indicators": tech["indicators"],
        "structure": tech["structure"],
        "levels": tech["levels"],
        "zones": agg["zones"],
        "candlestick_patterns": candles_p,
        "chart_patterns": charts_p,
        "vision": vision or {},
        "news_available": news_data.get("available", False),
    }
    narrative, nerr = await ai.reason(reason_payload)
    ai_available = narrative is not None
    if not narrative:
        narrative = _fallback_narrative(
            agg["direction"], agg["scores"], tech["indicators"], tech["structure"],
            candles_p, charts_p, agg["zones"], news_data,
        )

    doc = AnalysisDoc(
        symbol=symbol,
        base=asset["base"],
        quote=asset["quote"],
        timeframe=timeframe,
        price_at_analysis=tech["price"],
        change_24h_pct=ticker.get("change_24h_pct"),
        direction=agg["direction"],
        confidence=agg["confidence"],
        scores=agg["scores"],
        indicators=tech["indicators"],
        candlestick_patterns=candles_p,
        chart_patterns=charts_p,
        levels=tech["levels"],
        zones=agg["zones"],
        news_sentiment=news_data.get("sentiment", {}),
        scenarios=narrative.get("scenarios", {}),
        supporting_reasons=narrative.get("supporting_reasons", []),
        contradicting_reasons=narrative.get("contradicting_reasons", []),
        summary=narrative.get("summary", ""),
        vision=vision or {},
        ai_available=ai_available,
        market_data_available=market_ok,
        has_image=bool(req.image_base64),
        image_base64=req.image_base64,
    )

    res = await db.analyses.insert_one(doc.to_mongo())
    saved = await db.analyses.find_one({"_id": res.inserted_id})
    out = AnalysisDoc.from_mongo(saved)
    return out.model_dump()


# ----------------------------------------------------------------------------
# History
# ----------------------------------------------------------------------------
@api.get("/history")
async def history(limit: int = 50):
    cursor = db.analyses.find().sort("created_at", -1).limit(min(limit, 100))
    items = []
    async for doc in cursor:
        m = AnalysisDoc.from_mongo(doc)
        items.append(m.model_dump())
    return {"items": items}


@api.get("/history/{item_id}")
async def history_detail(item_id: str):
    try:
        doc = await db.analyses.find_one({"_id": ObjectId(item_id)})
    except Exception:
        raise HTTPException(400, "Invalid id")
    if not doc:
        raise HTTPException(404, "Not found")
    return AnalysisDoc.from_mongo(doc).model_dump()


@api.delete("/history/{item_id}")
async def history_delete(item_id: str):
    try:
        result = await db.analyses.delete_one({"_id": ObjectId(item_id)})
    except Exception:
        raise HTTPException(400, "Invalid id")
    return {"deleted": result.deleted_count}


# ----------------------------------------------------------------------------
# Outcome tracking / performance
# ----------------------------------------------------------------------------
async def _evaluate_doc(doc: dict) -> dict:
    """Evaluate one analysis against real price action since it was created."""
    analysis = AnalysisDoc.from_mongo(doc).model_dump()
    start_ms = outcome_engine.created_at_ms(analysis.get("created_at", ""))
    if start_ms is None:
        return {"status": "unresolvable", "note": "Bad timestamp."}
    provider = get_provider()
    try:
        # 15m granularity gives good ordering of target vs invalidation touches.
        candles = await provider.get_klines_since(analysis["symbol"], "15m", start_ms, limit=1000)
        # Only count candles strictly after the analysis timestamp.
        candles = [c for c in candles if c["time"] >= start_ms]
    except MarketDataError:
        return analysis.get("outcome") or {"status": "pending", "note": "Price data unavailable."}
    return outcome_engine.evaluate(analysis, candles)


@api.post("/history/evaluate-all")
async def evaluate_all():
    """Re-check every unresolved directional analysis, then return performance."""
    cursor = db.analyses.find().sort("created_at", -1).limit(200)
    updated = 0
    async for doc in cursor:
        current = (doc.get("outcome") or {}).get("status")
        # Skip already-final outcomes; re-check only pending/missing/unresolvable.
        if current in ("win", "loss", "neutral"):
            continue
        result = await _evaluate_doc(doc)
        await db.analyses.update_one({"_id": doc["_id"]}, {"$set": {"outcome": result}})
        updated += 1
    return {"evaluated": updated, "performance": await _performance()}


async def _performance() -> dict:
    outcomes = []
    per_dir = {"bullish": [], "bearish": []}
    cursor = db.analyses.find({}, {"outcome": 1, "direction": 1})
    async for doc in cursor:
        o = doc.get("outcome") or {"status": "pending"}
        outcomes.append(o)
        d = doc.get("direction")
        if d in per_dir:
            per_dir[d].append(o)
    summary = outcome_engine.summarize(outcomes)
    summary["by_direction"] = {
        "bullish": outcome_engine.summarize(per_dir["bullish"]),
        "bearish": outcome_engine.summarize(per_dir["bearish"]),
    }
    return summary


@api.get("/performance")
async def performance():
    return await _performance()


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
