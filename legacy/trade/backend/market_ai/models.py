"""Pydantic models with clean Mongo <-> API serialization.

ObjectId is never leaked to the API — every document extends `BaseDocument`
which maps `_id` -> `id: str`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, Field
from pydantic import BeforeValidator
from typing_extensions import Annotated


def _validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return str(v)


PyObjectId = Annotated[str, BeforeValidator(_validate_object_id)]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: Optional[PyObjectId] = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        doc = dict(doc)
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return cls(**doc)

    def to_mongo(self) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        data.pop("_id", None)
        data.pop("id", None)
        return data


# ---------- Request models ----------
class AnalysisRequest(BaseModel):
    symbol: str
    timeframe: str = "4H"
    image_base64: Optional[str] = None  # data URI or raw base64 (jpeg/png)


# ---------- Analysis sub-objects ----------
class ZoneLevels(BaseModel):
    entry_low: Optional[float] = None
    entry_high: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    invalidation: Optional[float] = None
    risk_reward: Optional[float] = None


class AnalysisDoc(BaseDocument):
    symbol: str
    base: str
    quote: str
    timeframe: str
    created_at: str = Field(default_factory=utcnow_iso)

    price_at_analysis: Optional[float] = None
    change_24h_pct: Optional[float] = None

    direction: str = "neutral"          # bullish | bearish | neutral
    confidence: float = 0.0             # 0..100 analytical confidence (NOT probability)

    scores: dict = Field(default_factory=dict)
    indicators: dict = Field(default_factory=dict)
    candlestick_patterns: List[dict] = Field(default_factory=list)
    chart_patterns: List[dict] = Field(default_factory=list)
    levels: dict = Field(default_factory=dict)          # support / resistance arrays
    zones: dict = Field(default_factory=dict)           # ZoneLevels for scenarios

    news_sentiment: dict = Field(default_factory=dict)

    scenarios: dict = Field(default_factory=dict)       # bullish/bearish/neutral text
    supporting_reasons: List[str] = Field(default_factory=list)
    contradicting_reasons: List[str] = Field(default_factory=list)
    summary: str = ""

    vision: dict = Field(default_factory=dict)          # image analysis result
    ai_available: bool = True
    market_data_available: bool = True

    has_image: bool = False
    image_base64: Optional[str] = None                  # stored for result/history thumbnail

    # Outcome tracking — populated by the outcome engine against real price action.
    # status: pending | win | loss | neutral | unresolvable
    outcome: dict = Field(default_factory=lambda: {"status": "pending"})
