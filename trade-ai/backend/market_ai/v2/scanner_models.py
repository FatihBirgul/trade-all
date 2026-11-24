"""Frontend-visible scheduler contracts; queue entries are never delivery claims."""
from typing import Literal
from pydantic import Field, model_serializer
from .api_models import Model, OutputModel


class WatchRequest(Model):
    profile_id: str | None = Field(None, pattern=r"^[a-f0-9]{64}$")
    symbol: Literal["BTCUSDT","ETHUSDT","SOLUSDT"]
    timeframe: Literal["5m","15m","1H","4H","1D"] = "1H"
    enabled: bool = Field(default=True,strict=True)
    auto_paper: bool = Field(default=False,strict=True)


    @model_serializer(mode='wrap')
    def serialize_watch(self, handler):
        result=handler(self)
        if self.profile_id is None:result.pop('profile_id',None)
        return result


class WatchResponse(WatchRequest):
    watch_id: str


class ScannerState(OutputModel):
    paused: bool
    lease_id: str | None
    lease_until_ms: int
    last_tick_ms: int | None
    last_error: str | None
    max_analyses_per_tick: int
    interval_seconds: int


class ScannerJob(OutputModel):
    job_id: str
    symbol: str
    timeframe: str
    closed_bar_ms: int
    status: Literal["running","completed","failed","skipped_stale"]
    started_at_ms: int | None = None
    analysis_id: str | None = None
    reason: str | None = None


class TickResponse(OutputModel):
    status: Literal["paused","busy","completed","blocked"]
    reason: str | None = None
    jobs: list[ScannerJob]


class NotificationResponse(OutputModel):
    notification_id: str
    kind: Literal["analysis","paper_event","scanner_error"]
    details: dict
    created_at_ms: int
    data_mode: Literal["fixture","live"]
    delivery_status: Literal["pending"]
    delivery_service: Literal["not_configured"]
