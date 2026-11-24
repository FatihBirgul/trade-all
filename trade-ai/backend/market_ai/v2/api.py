"""Standalone/local V2 FastAPI and reusable router. No V1 DB/AI imports."""
from dataclasses import dataclass
from decimal import Decimal
from secrets import compare_digest
import logging
import os
import time
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, FastAPI, Query, Request, Header
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from pydantic import Field

from .api_models import (Model, HealthResponse, MarketsResponse, AnalyzeRequest, AnalysisResponse,
    PortfolioResponse, PositionResponse, TransactionResponse, PerformanceResponse, OrderRequest,
    OrderResponse, CloseRequest, CancelRequest, FixtureEventRequest, ErrorResponse, ChartResponse)
from .product_db import ProductDatabase
from . import domain_journal as domain
from .paper_ledger import PaperLedger, dec, text, decimal_context
from .equity_history import EquityHistoryResponse
from .notification_controls import NotificationControls,NoticePreferences,NoticePreferencesWrite
from .equity_archive import EquityWindowResponse,read_window
from .profile_product import ProfileStore, ProfileWrite, ProfileRecord, ProfileEvaluationRequest, ProfileEvaluation, capabilities
from .analysis_service import AnalysisService
from .spot_provider import BinanceSpotProvider, FixtureSpotProvider
from .errors import V2Error
from .scanner import Scanner
from .scanner_models import WatchRequest, WatchResponse, ScannerState, ScannerJob, TickResponse, NotificationResponse
from .discovery import DiscoveryService,DiscoveryWrite,DiscoveryReceipt,DiscoveryView,DiscoveryTick,OpportunityList,OpportunityDetail
from .snapshot_research import SnapshotResearchRequest,SnapshotResearchResponse,snapshot_research,research_connection
from .decision_record import ImmutableDecisionRecord


class PauseRequest(Model):
    paused: bool = Field(strict=True)


class PollRequest(Model):
    symbols: list[Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"]] = Field(default_factory=lambda: ["BTCUSDT"], min_length=1, max_length=3)


class EventResult(Model):
    event_id: str
    data_mode: str
    close_time_ms: int
    processed: list[dict]
    market_event: dict


class CloseResult(Model):
    close_request_id: str
    position_id: str
    quantity: str
    status: str
    created_at_ms: int


@dataclass
class Runtime:
    db: ProductDatabase
    ledger: PaperLedger
    analysis: AnalysisService
    token: str
    clock: object
    scanner: object = None


def create_runtime(db_path, *, mode="live", token, provider=None, clock=None, domain_journal=False):
    if not isinstance(token, str) or len(token) < 24:
        raise ValueError("V2_API_TOKEN must contain at least 24 characters")
    clock = clock or (lambda: int(time.time()*1000))
    provider = provider or (FixtureSpotProvider() if mode == "fixture" else BinanceSpotProvider())
    if provider.mode != mode:
        raise ValueError("Provider and database mode must match")
    db = ProductDatabase(db_path, mode, domain_journal=domain_journal, clock=clock)
    ledger = PaperLedger(db)
    runtime = Runtime(db, ledger, AnalysisService(db, provider, ledger, clock), token, clock)
    runtime.analysis.profiles = ProfileStore(db, clock)
    runtime.notification_controls = NotificationControls(db)
    runtime.scanner = Scanner(runtime)
    runtime.discovery = DiscoveryService(runtime)
    return runtime


def build_router(runtime):
    auth = HTTPBearer(auto_error=False, scheme_name="V2Bearer")

    def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(auth)):
        if credentials is None or not compare_digest(credentials.credentials.encode(), runtime.token.encode()):
            raise V2Error("UNAUTHORIZED", "A valid local V2 bearer token is required", 401)

    descriptions = {401:"Authentication required",403:"Operation disabled in this runtime",404:"Resource not found",
                    409:"Conflict or risk veto",422:"Request validation failed",500:"Internal V2 error",503:"Source or storage unavailable"}
    # HTTPStatus(422).phrase differs between Python 3.11 and 3.13. API prose is
    # part of the exported contract, so declare it instead of using stdlib prose.
    router = APIRouter(prefix="/api/v2", tags=["Trade AI V2"], dependencies=[Depends(require_auth)],
                       responses={status: {"model": ErrorResponse, "description": description}
                                  for status,description in descriptions.items()})
    db, ledger, service, clock = runtime.db, runtime.ledger, runtime.analysis, runtime.clock

    def get_analysis(c, key):
        row = db.get(c, "analyses", key)
        if row is None:
            raise V2Error("ANALYSIS_NOT_FOUND", "Analysis not found", 404)
        return AnalysisResponse.model_validate(row)

    @router.get("/health", response_model=HealthResponse)
    def health():
        with db.transaction() as c:
            if any(db.get(c, "accounts", name) is None for name in ("AUTO", "MANUAL")):
                raise V2Error("STORAGE_CORRUPT", "Virtual account state is missing", 503)
        return HealthResponse(status="ok", version="v2-backend-1", data_mode=db.mode,
                              storage="sqlite_product_1", provider=service.provider.name,
                              provider_status=service.provider_status)

    @router.get("/markets", response_model=MarketsResponse)
    def markets():
        items = [{"symbol": symbol, "market": "crypto_spot", "contract_type": "spot", "quote_currency": "USDT",
            "provider": service.provider.name, "venue": service.provider.venue, "availability": "configured",
            "provider_status": service.provider_status, "timeframes": ["1m", "5m", "15m", "1H", "4H", "1D"]}
            for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT")]
        items.extend({"symbol": s, "market": m, "availability": "unavailable", "reason": "verified_provider_and_calendar_required"}
                     for s, m in (("EURUSD", "forex_spot"), ("XAUUSD", "gold_spot")))
        return MarketsResponse(items=items, data_mode=db.mode)

    @router.get("/strategy-capabilities", response_model=dict)
    def strategy_capabilities():
        return capabilities()

    @router.get("/portfolios/{portfolio_id}/strategy-profiles", response_model=list[ProfileRecord])
    def profiles(portfolio_id: Literal["AUTO","MANUAL"], limit: int = Query(20,ge=1,le=100), offset: int = Query(0,ge=0)):
        with db.transaction() as c:
            return [db.decode(row) for row in c.execute("SELECT body,body_hash FROM strategy_profiles WHERE portfolio=? ORDER BY rowid DESC LIMIT ? OFFSET ?",(portfolio_id,limit,offset))]

    @router.post("/portfolios/{portfolio_id}/strategy-profiles", response_model=ProfileRecord)
    def create_profile(portfolio_id: Literal["AUTO","MANUAL"], request: ProfileWrite):
        return service.profiles.write(portfolio_id,request)

    @router.get("/portfolios/{portfolio_id}/strategy-profiles/{profile_id}", response_model=ProfileRecord)
    def read_profile(portfolio_id: Literal["AUTO","MANUAL"], profile_id: str):
        with db.transaction() as c:
            return service.profiles.get(c,portfolio_id,profile_id)[0]

    @router.post("/portfolios/{portfolio_id}/strategy-profiles/{profile_id}/revisions", response_model=ProfileRecord)
    def revise_profile(portfolio_id: Literal["AUTO","MANUAL"], profile_id: str, request: ProfileWrite):
        return service.profiles.write(portfolio_id,request,profile_id)

    @router.post("/portfolios/{portfolio_id}/strategy-profiles/{profile_id}/evaluate", response_model=ProfileEvaluation)
    def evaluate_saved_profile(portfolio_id: Literal["AUTO","MANUAL"], profile_id: str, request: ProfileEvaluationRequest):
        with db.transaction() as c:
            _,profile=service.profiles.get(c,portfolio_id,profile_id)
            analysis=get_analysis(c,request.analysis_id).model_dump(mode="json")
            if analysis['risk_portfolio']!=portfolio_id:
                raise V2Error('ANALYSIS_NOT_FOUND','Analysis not found for this account',404)
            return {**service.profiles.evaluate(profile,analysis),'profile_id':profile_id,'analysis_id':request.analysis_id,'portfolio_id':portfolio_id}

    @router.post("/analyze", response_model=AnalysisResponse)
    def analyze(request: AnalyzeRequest):
        return service.analyze(request)

    @router.get("/analyses", response_model=list[AnalysisResponse])
    def analyses(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        with db.transaction() as c:
            return [db.get(c, "analyses", r[0]) for r in c.execute("SELECT id FROM analyses ORDER BY created_ms DESC,id LIMIT ? OFFSET ?", (limit, offset))]

    @router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
    def analysis_detail(analysis_id: str):
        with db.transaction() as c:
            return get_analysis(c, analysis_id)

    @router.get("/analyses/{analysis_id}/candles", response_model=ChartResponse)
    def analysis_candles(analysis_id: str,
                         timeframe: Literal["1m","5m","15m","1H","4H","1D"] | None = None,
                         limit: int = Query(300,ge=1,le=300)):
        with db.transaction() as c:
            analysis=get_analysis(c,analysis_id)
            tf=timeframe or analysis.timeframe
            def saved_record(key):
                row=c.execute("SELECT body_json FROM decision_records WHERE record_id=?",(key,)).fetchone()
                record=ImmutableDecisionRecord(key,row[0]) if row else None
                if record is None or not record.verify():
                    raise V2Error("STORAGE_CORRUPT","Analysis candle provenance failed integrity verification",503)
                return record.payload()
            product=saved_record(analysis_id)
            source_id=product["source_records"].get(tf)
            if source_id is None:
                raise V2Error("CANDLE_SNAPSHOT_UNAVAILABLE","No recorded candle snapshot for this timeframe",404)
            snapshot=saved_record(source_id)
            if not analysis.quality["ok"] or not snapshot["routing"]["quality"]["ok"]:
                raise V2Error("CANDLE_SNAPSHOT_UNAVAILABLE","Recorded source failed quality checks; no chart prices substituted")
            bars=snapshot["candles"]
            return ChartResponse(analysis_id=analysis_id,source_record_id=source_id,symbol=analysis.symbol,timeframe=tf,
                as_of_ms=analysis.created_at_ms,data_mode=analysis.data_mode,provider=analysis.provider,venue=analysis.venue,
                source=bars[0]["source"],price_kind=analysis.price_kind,contract_type=analysis.contract_type,
                quote_currency=analysis.quote_currency,candles=[{**{k:b[k] for k in ("open_time_ms","close_time_ms","is_final")},
                    **{k:format(Decimal(str(b[k])),"f") for k in ("open","high","low","close","volume")}} for b in bars[-limit:]])

    @router.get("/analyses/{analysis_id}/research",response_model=SnapshotResearchResponse)
    def research_catalogue(analysis_id:str,timeframe:Literal["1m","5m","15m","1H","4H","1D"]|None=None):
        with research_connection(db.path) as c:
            return snapshot_research(c,get_analysis(c,analysis_id),timeframe=timeframe)

    @router.post("/analyses/{analysis_id}/research",response_model=SnapshotResearchResponse)
    def research_compute(analysis_id:str,request:SnapshotResearchRequest):
        with research_connection(db.path) as c:
            return snapshot_research(c,get_analysis(c,analysis_id),request=request)

    @router.get('/portfolios/{portfolio_id}/market-scanner',response_model=DiscoveryView)
    def market_scanner(portfolio_id:Literal['AUTO','MANUAL']):return runtime.discovery.view(portfolio_id)

    @router.post('/portfolios/{portfolio_id}/market-scanner',response_model=DiscoveryReceipt)
    def market_scanner_config(portfolio_id:Literal['AUTO','MANUAL'],request:DiscoveryWrite):return runtime.discovery.configure(portfolio_id,request)

    @router.post('/portfolios/{portfolio_id}/market-scanner/tick',response_model=DiscoveryTick)
    def market_scanner_tick(portfolio_id:Literal['AUTO','MANUAL']):
        return {**runtime.discovery.tick(portfolio_id),'portfolio_id':portfolio_id,'data_mode':db.mode}

    @router.get('/portfolios/{portfolio_id}/opportunities',response_model=OpportunityList)
    def opportunity_list(portfolio_id:Literal['AUTO','MANUAL'],limit:int=Query(20,ge=1,le=50),offset:int=Query(0,ge=0,le=10000)):
        return runtime.discovery.opportunities(portfolio_id,limit,offset)

    @router.get('/portfolios/{portfolio_id}/opportunities/{opportunity_id}',response_model=OpportunityDetail)
    def opportunity_detail(portfolio_id:Literal['AUTO','MANUAL'],opportunity_id:str):return runtime.discovery.detail(portfolio_id,opportunity_id)

    @router.get("/portfolios", response_model=list[PortfolioResponse])
    def portfolios():
        with db.transaction() as c:
            return [ledger.account(c, name, clock()) for name in ("AUTO", "MANUAL")]

    @router.get("/portfolios/{portfolio_id}", response_model=PortfolioResponse)
    def portfolio(portfolio_id: Literal["AUTO", "MANUAL"]):
        with db.transaction() as c:
            return ledger.account(c, portfolio_id, clock())

    @router.get("/portfolios/{portfolio_id}/positions", response_model=list[PositionResponse])
    @decimal_context
    def positions(portfolio_id: Literal["AUTO", "MANUAL"], open_only: bool = True,
                  limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        with db.transaction() as c:
            rows = db.rows(c, "positions", portfolio_id)
            if open_only:
                rows = [p for p in rows if dec(p["quantity"]) > 0]
            for p in rows:
                p["unrealized_pnl_quote"] = text(dec(p["quantity"])*dec(p["mark_price"])-dec(p["cost_basis_quote"]))
            return rows[offset:offset+limit]

    @router.get("/portfolios/{portfolio_id}/transactions", response_model=list[TransactionResponse])
    def transactions(portfolio_id: Literal["AUTO", "MANUAL"], limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        with db.transaction() as c:
            return db.rows(c, "transactions", portfolio_id)[::-1][offset:offset+limit]

    @router.get("/portfolios/{portfolio_id}/orders", response_model=list[OrderResponse])
    def orders(portfolio_id: Literal["AUTO", "MANUAL"], limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        with db.transaction() as c:
            return db.rows(c, "orders", portfolio_id)[::-1][offset:offset+limit]

    @router.post("/portfolios/{portfolio_id}/orders", response_model=OrderResponse)
    def order_create(portfolio_id: Literal["AUTO", "MANUAL"], request: OrderRequest):
        with db.transaction() as c:
            domain.request(c, 'order:'+portfolio_id, request.idempotency_key,
                           {'analysis_id':request.analysis_id,'quantity':str(request.quantity) if request.quantity is not None else None})
            return ledger.place(c, portfolio_id, get_analysis(c, request.analysis_id), request.idempotency_key, request.quantity, clock())

    @router.post("/portfolios/{portfolio_id}/orders/{order_id}/cancel", response_model=OrderResponse)
    def order_cancel(portfolio_id: Literal["AUTO", "MANUAL"], order_id: str, request: CancelRequest):
        with db.transaction() as c:
            args = {"order_id": order_id}
            scope = "cancel:" + portfolio_id
            previous = db.command(c, scope, request.idempotency_key, args)
            if previous is not None:
                return previous
            order = db.get(c, "orders", order_id)
            if order is None or order["portfolio_id"] != portfolio_id:
                raise V2Error("ORDER_NOT_FOUND", "Virtual order not found", 404)
            if order["status"] not in ("pending", "partially_filled"):
                raise V2Error("ORDER_NOT_CANCELLABLE", "No pending remainder exists")
            order["remaining_quantity"], order["status"] = "0", "cancelled"
            db.update(c, "orders", order_id, order)
            db.remember(c, scope, request.idempotency_key, args, order)
            ledger.history.capture(c,portfolio_id,{"kind":"command","scope":scope,"key":request.idempotency_key},clock())
            return order

    @router.post("/portfolios/{portfolio_id}/positions/{position_id}/close", response_model=CloseResult)
    def close(portfolio_id: Literal["AUTO", "MANUAL"], position_id: str, request: CloseRequest):
        with db.transaction() as c:
            return ledger.close_position(c, portfolio_id, position_id, request, clock())

    @router.post("/portfolios/{portfolio_id}/pause", response_model=PortfolioResponse)
    def pause(portfolio_id: Literal["AUTO", "MANUAL"], request: PauseRequest):
        with db.transaction() as c:
            if db.domain_enabled:
                domain.begin(c, effective_at=clock(), source={'control':'account_pause', 'portfolio_id':portfolio_id})
                domain.note(c, 'control.requested', {'paused':request.paused}, portfolio_id)
            if not request.paused and any((p["status"] == "ambiguous" or p.get("stop_triggered")) and dec(p["quantity"]) > 0 for p in db.rows(c,"positions",portfolio_id)):
                raise V2Error("UNRESOLVED_PAPER_EXIT", "Resolve ambiguous or protective-exit risk before resuming")
            a = db.get(c, "accounts", portfolio_id)
            a["paused"] = request.paused
            db.update(c, "accounts", portfolio_id, a)
            return ledger.account(c, portfolio_id, clock())

    @router.post("/paper/events", response_model=EventResult)
    def fixture_event(request: FixtureEventRequest):
        if db.mode != "fixture":
            raise V2Error("FIXTURE_DISABLED", "Client-supplied market events are forbidden in live mode", 403)
        event = request.model_dump(mode="json")
        for k in ("open", "high", "low", "close", "volume"):
            event[k] = text(event[k])
        with db.transaction() as c:
            return ledger.event(c, event, clock())

    @router.post("/paper/poll", response_model=dict)
    def poll(request: PollRequest):
        return runtime.scanner.poller.poll(request.symbols)

    @router.get("/watchlist", response_model=list[WatchResponse])
    def watchlist(include_profile: bool = False):
        rows=runtime.scanner.rows("watchlist",limit=10)
        return rows if include_profile else [{k:v for k,v in row.items() if k!='profile_id'} for row in rows]

    @router.post("/watchlist", response_model=WatchResponse)
    def watch(request: WatchRequest, include_profile: bool = False):
        row=runtime.scanner.watch(request)
        return row if include_profile else {k:v for k,v in row.items() if k!='profile_id'}

    @router.get("/scanner", response_model=ScannerState)
    def scanner_state():
        return runtime.scanner.state()

    @router.post("/scanner/pause", response_model=ScannerState)
    def scanner_pause(request: PauseRequest):
        return runtime.scanner.pause(request.paused)

    @router.post("/scanner/tick", response_model=TickResponse)
    def scanner_tick():
        return runtime.scanner.tick()

    @router.get("/scanner/jobs", response_model=list[ScannerJob])
    def scanner_jobs(limit: int = Query(20,ge=1,le=100),offset: int = Query(0,ge=0)):
        return runtime.scanner.rows("scanner_jobs",limit,offset)

    @router.get('/portfolios/{portfolio_id}/notification-preferences',response_model=NoticePreferences)
    def notification_preferences(portfolio_id: Literal['AUTO','MANUAL'], x_v2_notification_owner: str | None = Header(None), x_v2_recipient_expires: int | None = Header(None)):
        return runtime.notification_controls.read(portfolio_id,x_v2_notification_owner,x_v2_recipient_expires)

    @router.post('/portfolios/{portfolio_id}/notification-preferences',response_model=NoticePreferences)
    def notification_preferences_write(portfolio_id: Literal['AUTO','MANUAL'], request: NoticePreferencesWrite, x_v2_notification_owner: str | None = Header(None), x_v2_recipient_expires: int | None = Header(None)):
        return runtime.notification_controls.write(portfolio_id,x_v2_notification_owner,x_v2_recipient_expires,request)

    @router.get("/notifications", response_model=list[NotificationResponse])
    def notifications(limit: int = Query(20,ge=1,le=100),offset: int = Query(0,ge=0)):
        return runtime.scanner.rows("notifications",limit,offset)

    @router.get('/portfolios/{portfolio_id}/equity-history', response_model=EquityHistoryResponse)
    def equity_history(portfolio_id: Literal['AUTO','MANUAL'], period: Literal['day','week','month'] = 'day', limit: int = Query(100,ge=1,le=200), offset: int = Query(0,ge=0,le=100000), from_ms: int = Query(0,ge=0,le=9223372036854775807), to_ms: int = Query(9223372036854775807,ge=0,le=9223372036854775807)):
        return ledger.history.read(portfolio_id,limit=limit,offset=offset,from_ms=from_ms,to_ms=to_ms,period=period)

    @router.get('/portfolios/{portfolio_id}/equity-history-window', response_model=EquityWindowResponse)
    def equity_history_window(portfolio_id: Literal['AUTO','MANUAL'], limit: int = Query(100,ge=1,le=200), from_ms: int = Query(0,ge=0,le=9223372036854775807), to_ms: int = Query(9223372036854775807,ge=0,le=9223372036854775807), cursor: str | None = Query(None,max_length=1600), sampling: Literal['raw','minmax'] = 'raw'):
        return read_window(db,portfolio_id,limit=limit,from_ms=from_ms,to_ms=to_ms,cursor=cursor,sampling=sampling)

    @router.get("/performance", response_model=PerformanceResponse)
    @decimal_context
    def performance():
        with db.transaction() as c:
            output = []
            for name in ("AUTO", "MANUAL"):
                a = ledger.account(c, name, clock())
                all_positions = db.rows(c, "positions", name)
                closed = [p for p in all_positions if p["status"] == "closed"]
                wins = sum(dec(p["realized_pnl_quote"]) > 0 and not p.get("ambiguity_seen") for p in closed)
                losses = sum(dec(p["realized_pnl_quote"]) < 0 and not p.get("ambiguity_seen") for p in closed)
                output.append({"portfolio_id": name, "closed_positions": len(closed), "wins": wins, "losses": losses,
                    "ambiguous_positions": sum(bool(p.get("ambiguity_seen")) for p in all_positions),
                    "win_rate": text(Decimal(wins)/Decimal(wins+losses)*100) if wins+losses else None,
                    "realized_pnl_quote": a["realized_pnl_quote"], "unrealized_pnl_quote": a["unrealized_pnl_quote"],
                    "equity_quote": a["equity_quote"], "fees_quote": text(sum((dec(t["fee_quote"]) for t in db.rows(c, "transactions", name)), Decimal(0)))})
        return PerformanceResponse(data_mode=db.mode, portfolios=output,
            note="Paper simulation only. Costs included in realized PnL; ambiguous positions are unresolved, not wins. No backtest validation or success probability implied.")

    return router


def install_v2(app, runtime):
    app.include_router(build_router(runtime))

    @app.exception_handler(V2Error)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": {"code": exc.code, "message": exc.message}},
                            headers={"WWW-Authenticate":"Bearer"} if exc.status == 401 else None)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        if request.url.path.startswith("/api/v2/"):
            return JSONResponse(status_code=exc.status_code, content={"error": {
                "code": "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR", "message": str(exc.detail)}})
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        if request.url.path.startswith("/api/v2/"):
            if runtime.db.domain_enabled:
                # Never persist malformed request bodies or HTTP headers.
                account=request.path_params.get('portfolio_id')
                account=account if account in ('AUTO','MANUAL') else None
                try:
                    with runtime.db.transaction() as c:
                        domain.begin(c,effective_at=runtime.clock(),source={'control':'request_validation'})
                        domain.note(c,'request.validation_rejected',{'reason':'VALIDATION_ERROR'},account)
                except sqlite3.Error:
                    return JSONResponse(status_code=503,content={'error':{'code':'STORAGE_UNAVAILABLE','message':'Audit write failed; request was not applied'}})
            return JSONResponse(status_code=422, content={"error": {"code": "VALIDATION_ERROR", "message": "Request fields failed V2 schema validation"}})
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(sqlite3.Error)
    async def storage_error(request, exc):
        if not request.url.path.startswith("/api/v2/"):
            raise exc
        logging.getLogger(__name__).exception("V2 storage transaction failed")
        return JSONResponse(status_code=503, content={"error": {"code": "STORAGE_UNAVAILABLE",
                            "message": "Transaction rolled back; retry with the same idempotency key"}})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        if not request.url.path.startswith("/api/v2/"):
            raise exc
        logging.getLogger(__name__).exception("Unexpected V2 request failure")
        return JSONResponse(status_code=500,content={"error":{"code":"V2_INTERNAL_ERROR",
            "message":"Internal V2 failure; inspect current state before retrying with the same idempotency key"}})


def create_app(db_path, *, mode="live", token, provider=None, clock=None, domain_journal=False):
    app = FastAPI(title="Trade AI 2.0 Local Backend", version="2.0.0", docs_url="/docs")
    runtime = create_runtime(db_path, mode=mode, token=token, provider=provider, clock=clock, domain_journal=domain_journal)
    app.state.v2 = runtime
    install_v2(app, runtime)
    from .quotes import install_quotes
    install_quotes(app, runtime)
    from .tracking import install_tracking
    install_tracking(app, runtime)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
    return app


def app_from_env():
    """Explicit local launch: uvicorn market_ai.v2.api:app_from_env --factory."""
    path, token = os.environ.get("V2_DB_PATH"), os.environ.get("V2_API_TOKEN")
    if not path or not token:
        raise RuntimeError("Set V2_DB_PATH to a new V2-only file and V2_API_TOKEN (24+ chars)")
    app=create_app(path, token=token, mode=os.environ.get("V2_DATA_MODE", "live"), domain_journal=os.environ.get("V2_DOMAIN_JOURNAL")=="1")
    if os.environ.get("V2_TRACKING_WORKER")=="1":
        from .tracking import TrackingWorker
        worker=TrackingWorker(app.state.tracking)
        app.add_event_handler("startup",worker.start)
        app.add_event_handler("shutdown",worker.stop)
    return app
