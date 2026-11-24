"""Read-only, source-bound research over saved immutable analysis candles.

No market fetch, writes, arbitrary candles, current price substitution or grants.
Content IDs bind snapshot, anchor, implementation and normalized parameters.
"""
from dataclasses import fields,asdict
from contextlib import contextmanager,closing
from pathlib import Path
import sqlite3
from typing import Literal
from pydantic import ConfigDict,Field,create_model
from .api_models import Model
from .indicator_parameters import IndicatorParameters,compute_parameters,digest,VERSION as PARAMETER_VERSION
from .session_research import anchored_vwap
from .decision_record import ImmutableDecisionRecord
from .market_data_contract import Candle,Instrument,validate_series
from .technical_adapter import TIMEFRAME_MS
from .errors import V2Error
VERSION='v2-snapshot-research-1'
Frame=Literal['1m','5m','15m','1H','4H','1D']
class StrictSettings(Model):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
IndicatorSettings=create_model('IndicatorSettings',__base__=StrictSettings,**{
    f.name:(f.type,f.default) for f in fields(IndicatorParameters) if f.name not in ('strategy_versions','implementation_version')})
class SnapshotResearchRequest(Model):
    schema_version:Literal[1]=1
    source_record_id:str=Field(pattern=r'^[a-f0-9]{64}$')
    symbol:Literal['BTCUSDT','ETHUSDT','SOLUSDT']
    timeframe:Frame
    implementation_version:Literal['v2-snapshot-research-1']=VERSION
    anchor_ms:int|None=Field(None,strict=True,ge=0,le=2**53-1)
    parameters:IndicatorSettings=Field(default_factory=IndicatorSettings)
class ResearchAnchor(Model):
    open_time_ms:int
    close_time_ms:int
class SnapshotResearchResponse(Model):
    schema_version:Literal[1]=1
    version:str=VERSION
    analysis_id:str
    portfolio_id:Literal['AUTO','MANUAL']
    source_record_id:str
    symbol:str
    timeframe:str
    as_of_ms:int
    data_mode:Literal['fixture','live']
    snapshot_only:Literal[True]=True
    trade_permission:Literal[False]=False
    status:Literal['available','unavailable']
    reason:str|None=None
    source:str
    source_digest:str
    configuration_id:str|None=None
    anchors:list[ResearchAnchor]=Field(default_factory=list,max_length=300)
    parameters:dict
    parameter_id:str
    parameter_version:str=PARAMETER_VERSION
    warmup_bars:int
    indicator_research:dict=Field(default_factory=dict)
    anchored_vwap:dict=Field(default_factory=dict)
    limitations:list[str]=Field(default_factory=lambda:[
        'Immutable historical snapshot only; not a current quote or trade confirmation.',
        'OHLC typical-price VWAP approximates trades; historical fees/rules/licensing are not established.',
        'No execution permission; no market profitability or forward validation.'])

@contextmanager
def research_connection(path):
    """Existing file only, consistent deferred snapshot and SQLite-enforced RO."""
    path=Path(path).resolve(strict=True)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,isolation_level=None)) as c:
        c.execute('PRAGMA query_only=ON');c.execute('PRAGMA trusted_schema=OFF')
        c.execute('PRAGMA busy_timeout=1000');c.execute('BEGIN')
        try:yield c
        finally:c.rollback()


def _record(c,key):
    row=c.execute('SELECT body_json FROM decision_records WHERE record_id=?',(key,)).fetchone()
    r=ImmutableDecisionRecord(key,row[0]) if row else None
    if r is None or not r.verify():raise V2Error('STORAGE_CORRUPT','Research source integrity failed',503)
    return r.payload()

def _source(c,analysis,timeframe):
    product=_record(c,analysis.analysis_id)
    source_id=product.get('source_records',{}).get(timeframe)
    if not source_id:raise V2Error('RESEARCH_UNAVAILABLE','No recorded source for this timeframe',404)
    source=_record(c,source_id)
    try:
        rows=source['candles'];config=source['config'];result=product['result']
        if (product['kind']!='product_analysis' or source['kind']!='analysis' or config['timeframe']!=timeframe
                or config['as_of_ms']!=analysis.created_at_ms or result['symbol']!=analysis.symbol
                or result['risk_portfolio']!=analysis.risk_portfolio or not 1<=len(rows)<=1024):raise ValueError()
        bars=tuple(Candle(**{**b,'instrument':Instrument(**b['instrument'])}) for b in rows)
        if any(b.instrument.symbol!=analysis.symbol or b.instrument.venue!=analysis.venue
               or b.instrument.contract_type!=analysis.contract_type or b.instrument.price_kind!=analysis.price_kind
               or b.instrument.quote_currency!=analysis.quote_currency for b in bars):raise ValueError()
    except (KeyError,TypeError,ValueError):raise V2Error('STORAGE_CORRUPT','Research source identity or structure failed',503) from None
    return source_id,source,bars

def snapshot_research(c,analysis,*,timeframe=None,request=None):
    timeframe=request.timeframe if request is not None else timeframe or analysis.timeframe
    source_id,source,bars=_source(c,analysis,timeframe)
    if request is not None and (request.source_record_id!=source_id or request.symbol!=analysis.symbol):
        raise V2Error('RESEARCH_SOURCE_MISMATCH','Requested immutable source does not match analysis',409)
    try:p=IndicatorParameters(**(request.parameters.model_dump() if request else {}))
    except (ValueError,TypeError):raise V2Error('INVALID_RESEARCH_PARAMETERS','Unsupported parameter configuration',422) from None
    out=dict(analysis_id=analysis.analysis_id,portfolio_id=analysis.risk_portfolio,source_record_id=source_id,
        symbol=analysis.symbol,timeframe=timeframe,as_of_ms=analysis.created_at_ms,data_mode=analysis.data_mode,
        source=bars[0].source,source_digest=digest(bars),parameters=asdict(p),parameter_id=p.parameter_id,warmup_bars=p.warmup_bars,status='unavailable')
    q=validate_series(bars,timeframe_ms=TIMEFRAME_MS[timeframe],as_of_ms=analysis.created_at_ms,max_age_ms=TIMEFRAME_MS[timeframe],min_bars=2)
    if not analysis.quality['ok'] or not source['routing']['quality']['ok'] or not q.ok or any(b.open_time_ms%TIMEFRAME_MS[timeframe] for b in bars):
        return SnapshotResearchResponse(**out,reason='closed_source_quality')
    # Catalogue is bounded to actual latest 300 eligible anchors; no interpolation.
    anchors=[];real_suffix=True
    for i in range(len(bars)-1,-1,-1):
        b=bars[i];real_suffix=real_suffix and b.volume_kind=='real' and b.volume is not None
        if i<len(bars)-1 and real_suffix:anchors.append({'open_time_ms':b.open_time_ms,'close_time_ms':b.close_time_ms})
    anchors=list(reversed(anchors[:300]))
    recorded_versions=tuple(sorted((v['strategy_id'],v['version']) for v in source.get('strategies',[])))
    if recorded_versions!=p.strategy_versions:return SnapshotResearchResponse(**out,reason='strategy_implementation_version_mismatch')
    out.update(status='available',anchors=anchors)
    if request is not None:
        bias=None;bias_id=None
        if p.bias_timeframe:
            bias_id,_,bias=_source(c,analysis,p.bias_timeframe)
        methods=compute_parameters(bars,p,timeframe=timeframe,as_of_ms=analysis.created_at_ms,max_age_ms=TIMEFRAME_MS[timeframe],bias_candles=bias)
        anchored=anchored_vwap(bars,timeframe=timeframe,as_of_ms=analysis.created_at_ms,max_age_ms=TIMEFRAME_MS[timeframe],anchor_ms=request.anchor_ms)
        if request.anchor_ms is not None and request.anchor_ms not in {a['open_time_ms'] for a in anchors}:
            raise V2Error('INVALID_RESEARCH_ANCHOR','Anchor must be an eligible recorded closed candle',422)
        out.update(indicator_research=methods,anchored_vwap=anchored,
            configuration_id=digest({'version':VERSION,'analysis_id':analysis.analysis_id,'source_record_id':source_id,
                'bias_record_id':bias_id,'parameters':asdict(p),'anchor_ms':request.anchor_ms}))
    return SnapshotResearchResponse(**out)
