"""Public V2 schema. Prices/money are decimal strings; times are UTC epoch ms."""
from typing import Literal
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class OutputModel(Model):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)


class ChartCandle(OutputModel):
    open_time_ms: int
    close_time_ms: int
    is_final: Literal[True]
    open: str
    high: str
    low: str
    close: str
    volume: str


class ChartResponse(OutputModel):
    analysis_id: str
    source_record_id: str
    symbol: str
    timeframe: str
    as_of_ms: int
    data_mode: Literal["live","fixture"]
    provider: str
    venue: str
    source: str
    price_kind: Literal["last"]
    contract_type: Literal["spot"]
    quote_currency: Literal["USDT"]
    volume_kind: Literal["real"] = "real"
    snapshot_only: Literal[True] = True
    candles: list[ChartCandle]


class ErrorDetail(Model):
    code: str
    message: str


class ErrorResponse(Model):
    error: ErrorDetail


class AnalyzeRequest(Model):
    profile_id: str | None = Field(None, pattern=r"^[a-f0-9]{64}$")
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT", "EURUSD", "XAUUSD"] = "BTCUSDT"
    market: Literal["crypto_spot", "forex_spot", "gold_spot"] = "crypto_spot"
    timeframe: Literal["1m", "5m", "15m", "1H", "4H", "1D"] = "1H"
    timeframes: list[Literal["1m", "5m", "15m", "1H", "4H", "1D"]] = Field(default_factory=list, max_length=5)
    data_mode: Literal["live", "fixture"] = "live"
    risk_portfolio: Literal["AUTO", "MANUAL"] = "AUTO"
    fixture_case: Literal["trend", "range", "stale", "unfinished", "mixed", "gap"] = "trend"
    auto_paper: bool = Field(False, strict=True)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")


# Absence and explicit null mean no profile. Keep historical command preimages
# byte-for-byte compatible even for internal callers using model_dump().
    @model_serializer(mode="wrap")
    def serialize_request(self, handler):
        result = handler(self)
        if self.profile_id is None:
            result.pop("profile_id", None)
        return result


class Levels(Model):
    entry_low: str
    entry_high: str
    invalidation: str
    target_1: str
    target_2: str
    target_3: str | None = None
    reward_risk: str


class AnalysisResponse(OutputModel):
    analysis_id: str
    version: str
    created_at_ms: int
    expires_at_ms: int
    symbol: str
    market: str
    provider: str
    venue: str
    contract_type: str
    price_kind: str
    quote_currency: str
    data_mode: Literal["live", "fixture"]
    timeframe: str
    timeframes: list[str]
    price: str | None = None
    price_time_ms: int | None = None
    age_ms: int | None = None
    quality: dict
    regime: dict
    router: dict
    indicators: dict
    technical_methods: dict = Field(default_factory=dict)
    strategy_setups: dict = Field(default_factory=dict)
    market_rules: dict
    mtf: dict
    supporting_evidence: list[dict]
    conflicting_evidence: list[dict]
    direction: Literal["bullish", "bearish", "WAIT"]
    reason: str
    levels: Levels | None = None
    risk: dict
    risk_portfolio: Literal["AUTO", "MANUAL"]
    warnings: list[str]
    scenarios: dict[str, str]
    auto_order_id: str | None = None


class OrderRequest(Model):
    analysis_id: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]+$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=24, decimal_places=8)


class CloseRequest(Model):
    quantity: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")


class CancelRequest(Model):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")


class FixtureEventRequest(Model):
    """Only accepted in an explicitly fixture-mode runtime/database."""
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    open_time_ms: int = Field(ge=0)
    close_time_ms: int = Field(gt=0)
    open: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    high: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    low: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    close: Decimal = Field(gt=0, max_digits=24, decimal_places=8)
    volume: Decimal = Field(ge=0, max_digits=24, decimal_places=8)
    is_final: bool = Field(True, strict=True)


class PortfolioResponse(OutputModel):
    paper_only: Literal[True] = True
    portfolio_id: Literal["AUTO", "MANUAL"]
    quote_currency: str
    data_mode: str
    seed_equity_quote: str
    cash_quote: str
    reserved_cash_quote: str
    available_cash_quote: str
    equity_quote: str
    realized_pnl_quote: str
    unrealized_pnl_quote: str
    realized_loss_today_quote: str
    open_positions: int
    pending_orders: int
    paused: bool


class OrderResponse(OutputModel):
    paper_only: Literal[True] = True
    order_id: str
    portfolio_id: str
    analysis_id: str
    symbol: str
    data_mode: str
    status: str
    quantity: str
    remaining_quantity: str
    created_at_ms: int
    expires_at_ms: int
    risk: dict
    execution_model: str
    fee_rate: str
    adverse_rate: str
    participation_fraction: str


class PositionResponse(OutputModel):
    paper_only: Literal[True] = True
    position_id: str
    portfolio_id: str
    order_id: str
    symbol: str
    data_mode: str
    status: str
    quantity: str
    average_entry: str
    cost_basis_quote: str
    mark_price: str
    mark_time_ms: int
    realized_pnl_quote: str
    unrealized_pnl_quote: str
    invalidation: str
    target_1: str
    target_2: str
    opened_at_ms: int
    pending_closes: list[dict] = Field(default_factory=list)
    stop_triggered: bool = False
    ambiguity_seen: bool = False


class TransactionResponse(OutputModel):
    paper_only: Literal[True] = True
    transaction_id: str
    portfolio_id: str
    order_id: str
    position_id: str
    event_id: str
    kind: str
    quantity: str
    price: str
    fee_quote: str
    cash_delta_quote: str
    realized_pnl_quote: str
    time_ms: int
    data_mode: str


class Page(Model):
    items: list[dict]
    limit: int
    offset: int


class PerformanceResponse(Model):
    paper_only: Literal[True] = True
    data_mode: str
    portfolios: list[dict]
    note: str


class HealthResponse(Model):
    status: str
    version: str
    data_mode: str
    storage: str
    provider: str
    provider_status: str
    real_execution: Literal[False] = False
    auth_required: bool = True


class MarketsResponse(Model):
    items: list[dict]
    data_mode: str
