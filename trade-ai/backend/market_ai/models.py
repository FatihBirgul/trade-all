"""Pydantic models with clean Mongo <-> API serialization.

ObjectId is never leaked to the API — every document extends `BaseDocument`
which maps `_id` -> `id: str`.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional

from bson import ObjectId
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
)
from typing_extensions import Annotated


def _validate_object_id(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)

    return str(v)


PyObjectId = Annotated[
    str,
    BeforeValidator(_validate_object_id),
]


def utcnow_iso() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class BaseDocument(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    id: Optional[PyObjectId] = Field(
        default=None,
        alias="_id",
    )

    @classmethod
    def from_mongo(
        cls,
        doc: Optional[dict],
    ):
        if not doc:
            return None

        doc = dict(doc)

        if "_id" in doc:
            doc["_id"] = str(
                doc["_id"]
            )

        return cls(**doc)

    def to_mongo(self) -> dict:
        data = self.model_dump(
            by_alias=True,
            exclude_none=True,
        )

        data.pop(
            "_id",
            None,
        )

        data.pop(
            "id",
            None,
        )

        return data


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class AnalysisRequest(BaseModel):
    symbol: str
    timeframe: str = "4H"
    image_base64: Optional[str] = None


# ---------------------------------------------------------------------------
# Analysis sub-objects
# ---------------------------------------------------------------------------
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

    created_at: str = Field(
        default_factory=utcnow_iso
    )

    price_at_analysis: Optional[float] = None
    change_24h_pct: Optional[float] = None

    direction: str = "neutral"

    confidence: float = 0.0

    # The deterministic weighted composite score used before
    # Confluence/MTF tradeability gating.
    final_score: Optional[float] = None

    scores: dict = Field(
        default_factory=dict
    )

    indicators: dict = Field(
        default_factory=dict
    )

    candlestick_patterns: List[dict] = Field(
        default_factory=list
    )

    chart_patterns: List[dict] = Field(
        default_factory=list
    )

    levels: dict = Field(
        default_factory=dict
    )

    zones: dict = Field(
        default_factory=dict
    )

    # Full deterministic quality snapshot:
    # volatility, gate, confluence, MTF, etc.
    quality: dict = Field(
        default_factory=dict
    )

    news_sentiment: dict = Field(
        default_factory=dict
    )

    scenarios: dict = Field(
        default_factory=dict
    )

    supporting_reasons: List[str] = Field(
        default_factory=list
    )

    contradicting_reasons: List[str] = Field(
        default_factory=list
    )

    summary: str = ""

    vision: dict = Field(
        default_factory=dict
    )

    ai_available: bool = True
    market_data_available: bool = True

    has_image: bool = False

    image_base64: Optional[str] = None

    # Outcome tracking.
    # status:
    # pending | win | loss | neutral | ambiguous | unresolvable
    outcome: dict = Field(
        default_factory=lambda: {
            "status": "pending"
        }
    )