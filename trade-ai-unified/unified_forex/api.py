"""Local V6 API; retained data/risk routes plus canonical decision compatibility."""
from datetime import datetime,timezone
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import HTTPException,Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field,ConfigDict
from pydantic import ValidationError
from threading import BoundedSemaphore,RLock
from functools import wraps
from uuid import uuid4
from .strategies import Parameters
from .experiments import ExperimentRegistry
from .engine import AnalysisEngine,AnalysisReport
from .services import scan,Alerts
from .providers import ContractMT5Provider
from .strategies import STRATEGIES
from forex import api as legacy
from forex.core import DataError,SYMBOLS,TIMEFRAMES
from forex.unified import UnifiedAnalysis
from .macro import information_context

app=legacy.app
app.title='Trade AI Unified Forex';app.version='9.0.0-rc1'
app.state.alerts_v6=Alerts()
app.state.experiments_v7=ExperimentRegistry()
from .structure_ledger import LedgerStore
app.state.structure_ledgers=LedgerStore()
app.state.research_cancellation=None
app.state.research_run_id=None
app.state.decision_journal=None
_research_gate=BoundedSemaphore(1)
_provider_lock=RLock()
_research_state_lock=RLock()


def bounded_research(fn):
    @wraps(fn)
    def run(*args,**kwargs):
        if not _research_gate.acquire(blocking=False):raise HTTPException(429,'research workload already active; retry after completion')
        from .research_control import CancellationToken
        with _research_state_lock:
            app.state.research_cancellation=CancellationToken()
            app.state.research_run_id=uuid4().hex
        try:return fn(*args,**kwargs)
        finally:
            with _research_state_lock:
                app.state.research_cancellation=None
                app.state.research_run_id=None
            _research_gate.release()
    return run


@asynccontextmanager
async def lifespan(app):
    try:yield
    finally:
        p=app.state.provider
        try:
            if p is not None and hasattr(p,'close'):p.close()
        finally:app.state.provider=None


app.router.lifespan_context=lifespan
# Route every analysis/scanner/alert compatibility path through one decision host.
replace={'/api/v1/analysis/{symbol}','/api/v1/signals/{symbol}','/api/v1/scanner','/api/v1/alerts/{symbol}','/api/v5/analysis'}
app.router.routes[:]=[r for r in app.router.routes if getattr(r,'path',None) not in replace]
app.openapi_schema=None
engine=AnalysisEngine()
Symbol=Literal['XAUUSD','EURUSD','GBPUSD','USDJPY']
Timeframe=Literal['M5','M15','M30','H1','H4','D1']


def current_provider():
    with _provider_lock:
        if app.state.provider is None:
            try:app.state.provider=ContractMT5Provider()
            except DataError as exc:raise HTTPException(503,{'status':'PROVIDER_UNAVAILABLE','reason':str(exc)}) from exc
        return app.state.provider


legacy.provider=current_provider


class AnalysisRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,strict=True)
    symbol:Symbol
    timeframe:Timeframe='M15'
    confirmations:list[Timeframe]|None=Field(default=None,min_length=1,max_length=3)
    trigger_timeframe:Timeframe|None=None
    balance:float|None=Field(default=None,gt=0)
    risk_pct:float=Field(default=1,gt=0,le=5)
    commission_per_lot:float=Field(default=0,ge=0)
    slippage_price:float=Field(default=0,ge=0)
    records:list[dict]=Field(default_factory=list,max_length=100)
    enabled_strategies:list[str]|None=Field(default=None,min_length=1,max_length=4)
    macro_event_window_minutes:int|None=Field(default=None,ge=1,le=180)
    strategy_parameters:Parameters|None=None


class SectionResponse(BaseModel):
    analysis_id:str
    snapshot_id:str|None
    as_of_utc:str
    symbol:str
    timeframe:str
    provider:str
    final_decision:str
    data_status:str
    source_versions:dict


class IndicatorResponse(SectionResponse):
    indicators:dict|None
    warnings:list[str]


class StructureResponse(SectionResponse):
    market_structure:dict|None


class PatternResponse(SectionResponse):
    candlestick_patterns:dict|None
    chart_patterns:dict|None


class ConfluenceResponse(SectionResponse):
    confluence:dict|None
    strategy_conflicts:list[str]


def section(req,fields):
    common=set(SectionResponse.model_fields)
    return calculate(req).model_dump(include=common|set(fields))


def calculate(req):
    from forex.contracts import canonical
    try:record_json=canonical(req.records)
    except (ValueError,TypeError) as exc:raise HTTPException(422,'manual records require finite JSON') from exc
    if len(record_json)>100000:raise HTTPException(422,'manual records exceed budget')
    p=current_provider()
    ledger=app.state.structure_ledgers.get(p,req.symbol,req.timeframe)
    result=engine.analyze(p,**req.model_dump(),information_provider=app.state.information_provider,structure_ledger=ledger)
    if app.state.decision_journal is not None:app.state.decision_journal.record(result)
    return result


@app.post('/api/v6/analysis',response_model=AnalysisReport)
def analysis(req:AnalysisRequest):return calculate(req)


@app.get('/api/v6/health')
def health():
    p=current_provider()
    if hasattr(p,'health'):legacy.call(p.health)
    return {'status':'OK','engine_version':'9.0.0-rc1','provider':p.name,'read_only':True,
            'mt5_validation':'UNVERIFIED','data_status':'TEST_ONLY' if 'fixture' in p.name else 'PROVIDER_REACHABLE'}


@app.get('/api/v6/symbols')
def symbols():return {'symbols':SYMBOLS}


@app.get('/api/v6/quotes/{symbol}')
def quotes(symbol:Symbol):return legacy.call(lambda:current_provider().quote(symbol))


@app.get('/api/v6/candles/{symbol}')
def candles(symbol:Symbol,timeframe:Timeframe='M15',count:int=Query(220,ge=1,le=2000)):
    return legacy.call(lambda:current_provider().candles(symbol,timeframe,count))


@app.get('/api/v6/sessions/{symbol}')
def sessions(symbol:Symbol):
    from forex.sessions import session_snapshot
    m=legacy.call(lambda:current_provider().metadata(symbol))
    result=session_snapshot(datetime.now(timezone.utc),symbol,m.get('trade_allowed'),m.get('broker_hours'))
    from .market import schedule_contract
    trust=schedule_contract(m)
    if result['broker']['status']!='DISABLED' and not trust['policy_accepted']:
        result['broker']={'status':'UNKNOWN','reason':'schedule provenance unverified'}
    result['broker']['provenance']=trust
    return result


@app.get('/api/v6/strategies')
def strategies():
    from dataclasses import asdict
    return {'strategies':[asdict(s) for s in STRATEGIES],'original_crypto_volume_gate':'PRESERVED_UNAVAILABLE_FOR_FX'}


@app.post('/api/v6/indicators',response_model=IndicatorResponse)
def indicators(req:AnalysisRequest):return section(req,{'indicators','warnings'})


@app.post('/api/v6/structure',response_model=StructureResponse)
def structure(req:AnalysisRequest):return section(req,{'market_structure'})


@app.post('/api/v6/patterns',response_model=PatternResponse)
def patterns(req:AnalysisRequest):return section(req,{'candlestick_patterns','chart_patterns'})


@app.post('/api/v6/confluence',response_model=ConfluenceResponse)
def confluence(req:AnalysisRequest):return section(req,{'confluence','strategy_conflicts'})


class ScanRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,strict=True)
    symbols:list[Symbol]=Field(default_factory=lambda:['XAUUSD'],min_length=1,max_length=4)
    timeframes:list[Timeframe]=Field(default_factory=lambda:['M15'],min_length=1,max_length=4)
    balance:float|None=Field(default=None,gt=0)
    risk_pct:float=Field(default=1,gt=0,le=5)


class ScanResponse(BaseModel):
    provider:str
    as_of_utc:str
    ranking_policy:str
    results:list[AnalysisReport]
    cached_resource_reads:int
    cache_stats:dict


@app.post('/api/v6/scanner',response_model=ScanResponse)
def scanner(req:ScanRequest):
    try:return scan(current_provider(),**req.model_dump())
    except DataError as exc:raise HTTPException(422,str(exc)) from exc


class RiskRequest(legacy.RiskRequest):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,strict=True)
    commission_per_lot:float=Field(default=0,ge=0)
    slippage_price:float=Field(default=0,ge=0)


@app.post('/api/v6/risk/calculate',response_model=legacy.RiskResponse)
def risk(req:RiskRequest):
    from forex.core import size_lots
    p=current_provider()
    return legacy.call(lambda:size_lots(req.balance,req.risk_pct,req.entry,req.stop_loss,p.metadata(req.symbol),
                                       (lambda side,lots,e,s:p.loss_for(req.symbol,side,lots,e,s)) if hasattr(p,'loss_for') else None,
                                       req.direction,req.account_currency,req.commission_per_lot,req.slippage_price))


class AlertResponse(BaseModel):
    analysis_id:str
    events:list[dict]
    data_status:str


@app.post('/api/v6/alerts',response_model=AlertResponse)
def alerts(req:AnalysisRequest):
    report=calculate(req)
    return {'analysis_id':report.analysis_id,'events':app.state.alerts_v6.evaluate(report),'data_status':report.data_status}


@app.get('/api/v6/news')
def news():return legacy.news()


@app.get('/api/v6/calendar')
def calendar():return information_context(app.state.information_provider)


class BacktestRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False,strict=True)
    symbol:Symbol
    timeframe:Timeframe='M15'
    count:int=Field(default=500,ge=251,le=2000)
    fee_bps:float=Field(default=5,ge=0,le=100)
    spread_bps:float=Field(default=2,ge=0,le=100)
    slippage_bps:float=Field(default=1,ge=0,le=100)
    cadence:int=Field(default=20,ge=1,le=5000)
    strategy_ids:list[str]|None=Field(default=None,min_length=1,max_length=4)
    seed:int=Field(default=12,ge=0,le=2**32-1)


@app.post('/api/v6/backtests')
@bounded_research
def backtest(req:BacktestRequest):
    from .research import dataset_from_provider,ResearchConfig,run_backtest
    from .strategies import BUILTIN_IDS
    try:
        p=current_provider();d=dataset_from_provider(p,req.symbol,req.timeframe,req.count,data_kind='synthetic' if 'fixture' in p.name else 'historical')
        tf=d.execution_timeframe;b=d.frames[tf]
        config=ResearchConfig(tf,b[250].open_time_ms,b[-1].close_time_ms,analysis_every_bars=req.cadence,
                              strategy_ids=tuple(req.strategy_ids or sorted(BUILTIN_IDS)),seed=req.seed)
        return run_backtest(d,config,fee_bps=str(req.fee_bps),spread_bps=str(req.spread_bps),slippage_bps=str(req.slippage_bps),cancellation=app.state.research_cancellation)
    except (ValueError,DataError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


class CandidateRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    candidate_id:str=Field(min_length=1,max_length=64,pattern=r'^[a-zA-Z0-9_.-]+$')
    strategy_ids:list[str]=Field(min_length=1,max_length=4)
    cadence:int=Field(ge=1,le=5000)


class OOSRequest(BacktestRequest):
    train_bars:int=Field(default=330,ge=251,le=1500)
    test_bars:int=Field(default=40,ge=1,le=500)
    purge_bars:int=Field(default=1,ge=1,le=500)
    embargo_bars:int=Field(default=0,ge=0,le=500)
    folds:int=Field(default=2,ge=1,le=4)
    label_horizon_bars:int=Field(default=1,ge=1,le=500)
    candidates:list[CandidateRequest]|None=Field(default=None,min_length=1,max_length=4)
    validation_bars:int=Field(default=0,ge=0,le=500)


@app.post('/api/v6/research/oos')
@bounded_research
def oos(req:OOSRequest):
    from .research import dataset_from_provider,run_oos
    from .strategies import BUILTIN_IDS
    from market_ai.v2.walk_forward import WalkForwardConfig,Candidate
    try:
        p=current_provider();d=dataset_from_provider(p,req.symbol,req.timeframe,req.count,data_kind='synthetic' if 'fixture' in p.name else 'historical')
        ids=tuple(req.strategy_ids or sorted(BUILTIN_IDS))
        candidates=tuple(Candidate(c.candidate_id,tuple(c.strategy_ids),c.cadence) for c in req.candidates) if req.candidates else (
            (Candidate('declared-fast',ids,req.cadence),Candidate('declared-slow',ids,min(5000,req.cadence*2)))
            if req.cadence<5000 else (Candidate('declared-single',ids,req.cadence),))
        config=WalkForwardConfig(train_bars=req.train_bars,test_bars=req.test_bars,warmup_bars=250,
                                  purge_bars=req.purge_bars,label_horizon_bars=req.label_horizon_bars,embargo_bars=req.embargo_bars,
                                  max_folds=req.folds,simulate_orders=True,timeframe=d.execution_timeframe,candidates=candidates,
                                  validation_bars=req.validation_bars,
                                  fee_bps=str(req.fee_bps),spread_bps=str(req.spread_bps),slippage_bps=str(req.slippage_bps),seed=req.seed)
        return run_oos(d,config,registry=app.state.experiments_v7,cancellation=app.state.research_cancellation)
    except (ValueError,DataError,KeyError) as exc:raise HTTPException(422,str(exc)) from exc


@app.get('/api/v6/research/status')
def research_status():
    with _research_state_lock:
        return {'engine':'retained V2 train/select/freeze/test with in-memory Forex replay',
                'real_market_evidence':'UNVERIFIED','forward_validated':False,'source_license_status':'UNVERIFIED',
                'active_run_id':app.state.research_run_id,'cancellation_supported':True}


class CancelRequest(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    run_id:str=Field(pattern='^[a-f0-9]{32}$')


@app.post('/api/v6/research/cancel')
def cancel_research(req:CancelRequest):
    with _research_state_lock:
        token=app.state.research_cancellation
        if token is None or req.run_id!=app.state.research_run_id:raise HTTPException(409,'active research run ID mismatch')
        token.cancel()
    return {'cancellation_requested':True,'run_id':req.run_id,'semantics':'cooperative between bars/folds; incomplete results never registered'}


@app.get('/api/v6/research/experiments/{experiment_id}')
def experiment(experiment_id:str):
    if len(experiment_id)!=64 or any(c not in '0123456789abcdef' for c in experiment_id):raise HTTPException(422,'invalid experiment ID')
    result=app.state.experiments_v7.get(experiment_id)
    if result is None:raise HTTPException(404,'experiment unavailable or evicted; registry resets on restart')
    return result


@app.post('/api/v5/analysis',response_model=UnifiedAnalysis)
def v5(req:legacy.UnifiedRequest):
    r=calculate(AnalysisRequest(**req.model_dump(exclude={'require_private'}))).model_dump()
    # Private source is present; V5 clients retain their enum and nullable fields.
    body={k:v for k,v in r.items() if k in UnifiedAnalysis.model_fields}
    body.update(schema_version='forex-analysis-5',integration_status='PRIVATE_AVAILABLE' if r['integration_status']=='PRIVATE_INTEGRATED' else 'PRIVATE_PARTIAL')
    return UnifiedAnalysis.model_validate(body)


@app.get('/api/v1/analysis/{symbol}',response_model=legacy.AnalysisResponse)
@app.get('/api/v1/signals/{symbol}',response_model=legacy.AnalysisResponse)
def v1(symbol:Symbol,timeframe:Timeframe='M15',confirmations:str|None=None):
    confirm=confirmations.split(',') if confirmations else None
    try:r=calculate(AnalysisRequest(symbol=symbol,timeframe=timeframe,confirmations=confirm))
    except ValidationError as exc:raise HTTPException(422,'unsupported analysis parameters') from exc
    plan=None if r.entry_zone is None else dict(entry=r.entry_zone['low'],stop_loss=r.stop_loss,take_profit_1=r.take_profit_1,
                                               take_profit_2=r.take_profit_2,direction=r.legacy_signal,risk_reward=r.risk_reward)
    payload=dict(symbol=symbol,timeframe=timeframe,provider=r.provider,timestamp=r.as_of_utc,signal=r.legacy_signal,plan=plan,
                 reasons=r.decision_reasons,data_status=r.data_status,indicators=r.indicators,strategies=r.strategy_candidates,
                 confirmations=r.confirmations,market_structure=r.market_structure,session={'broker':{'status':r.market_status}})
    return JSONResponse(status_code=503,content=payload) if r.data_status!='OK' else payload


@app.get('/api/v1/scanner')
def v1_scan(symbols:str='XAUUSD',timeframes:str='M15'):
    try:
        r=scan(current_provider(),symbols.split(','),timeframes.split(','))
        return {'provider':r['provider'],'timestamp':r['as_of_utc'],'errors':[],
                'results':[{'symbol':a['symbol'],'timeframe':a['timeframe'],'signal':a['legacy_signal'],
                            'data_status':a['data_status'],'reasons':a['decision_reasons'],'indicators':a['indicators'],
                            'session':{'broker':{'status':a['market_status']}},'strategies':a['strategy_candidates'],
                            'market_structure':a['market_structure']} for a in r['results']]}
    except DataError as exc:raise HTTPException(422,str(exc)) from exc


@app.get('/api/v1/alerts/{symbol}')
def v1_alert(symbol:Symbol,timeframe:Timeframe='M15'):
    return alerts(AnalysisRequest(symbol=symbol,timeframe=timeframe))
