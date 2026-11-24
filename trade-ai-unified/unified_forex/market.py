"""Canonical V5-owned data, strengthened by the actual V2 QC contract."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from . import ROOT
from forex.contracts import capture, Snapshot, canonical, provider_read, _bars
from forex.core import DataError, TIMEFRAMES
from forex.sessions import session_snapshot
from market_ai.v2.market_data_contract import Instrument, Candle, validate_series
from market_ai.v2.capabilities import candle_capabilities

TF={'M5':'5m','M15':'15m','M30':'30m','H1':'1H','H4':'4H','D1':'1D'}


def schedule_contract(metadata):
    """Legacy opt-in is a declaration, never authenticated source evidence."""
    declared=(metadata.get('broker_hours_verified') is True or metadata.get('broker_hours_trust')=='DECLARED') and bool(metadata.get('schedule_source')) and bool(metadata.get('broker_hours'))
    return {'trust':'DECLARED' if declared else 'UNAVAILABLE',
            'source':metadata.get('schedule_source'),'authenticated':False,
            'policy_accepted':declared}


class MarketFailure(DataError):
    def __init__(self,decision,reason):
        super().__init__(reason)
        self.decision=decision


@dataclass(frozen=True)
class Frame:
    timeframe: str
    bars: tuple[Candle,...]
    permitted_gaps: tuple[tuple[int,int],...]
    as_of_ms: int
    @property
    def duration_ms(self):return TIMEFRAMES[self.timeframe]*1000
    def kwargs(self):
        return dict(timeframe=TF[self.timeframe],as_of_ms=self.as_of_ms,
                    max_age_ms=self.duration_ms*2,permitted_gaps=self.permitted_gaps)


@dataclass(frozen=True)
class MarketView:
    snapshot: Snapshot
    frames: tuple[Frame,...]
    capabilities: frozenset[str]
    session_json: str
    def frame(self,tf):return next(frame for frame in self.frames if frame.timeframe==tf)
    def session(self):return json.loads(self.session_json)


class RequestCache:
    """Request/scan scope only; no persisted quote or clock freshness substitution."""
    def __init__(self,provider):
        self.provider=provider;self.name=provider.name;self.cache={};self.errors={};self.hits=0;self.misses=0
        self.simulation_only=getattr(provider,'simulation_only',False) is True
    def _read(self,method,*args):
        key=(method,*args)
        if key in self.errors:
            self.hits+=1;raise DataError(self.errors[key])
        if key in self.cache:self.hits+=1
        if key not in self.cache:
            self.misses+=1
            try:self.cache[key]=canonical(provider_read(self.provider,method,*args))
            except DataError as exc:
                self.errors[key]=str(exc);raise
            except (ValueError,TypeError,OverflowError) as exc:
                self.errors[key]='provider returned an invalid numeric snapshot: '+method
                raise DataError(self.errors[key]) from exc
        return json.loads(self.cache[key])
    def metadata(self,symbol):return self._read('metadata',symbol)
    def quote(self,symbol):return self._read('quote',symbol)
    def candles(self,symbol,timeframe,count=256):return self._read('candles',symbol,timeframe,256)[-count:]
    def loss_for(self,*args):
        # This is an explicit read-only broker calculation, never cached market I/O.
        return provider_read(self.provider,'loss_for',*args)


def acquire(provider,symbol,timeframe,now,confirmations,trigger_timeframe=None):
    snapshot=capture(provider,symbol,timeframe,now,confirmations,
                     allow_zero_spread=getattr(provider,'simulation_only',False) is True)
    p=snapshot.payload();m=p['metadata']
    if p['quote']['time']>now:raise MarketFailure('STALE_DATA','quote is later than as-of')
    identity=(p['market_type'],p['contract_type'])
    if identity not in (('forex_spot','spot'),('gold_spot','spot'),('cfd','cfd')):
        raise MarketFailure('INSUFFICIENT_DATA','explicit compatible Forex/gold/CFD identity required')
    venue=p.get('venue')
    if not isinstance(venue,str) or venue in ('','unverified'):
        raise MarketFailure('INSUFFICIENT_DATA','broker venue identity unavailable')
    session=session_snapshot(datetime.fromtimestamp(now,timezone.utc),symbol,m.get('trade_allowed'),m.get('broker_hours'))
    provenance=schedule_contract(m)
    verified=provenance['policy_accepted']
    if not verified and session['broker']['status'] not in ('DISABLED',):
        session['broker']={'status':'UNKNOWN','reason':'broker schedule provenance not verified'}
    session['broker']['provenance']=provenance
    if trigger_timeframe is not None:
        if trigger_timeframe not in TF or TIMEFRAMES[trigger_timeframe]>=TIMEFRAMES[timeframe]:
            raise MarketFailure('INSUFFICIENT_DATA','trigger must be a lower supported timeframe')
        rows=provider_read(provider,'candles',symbol,trigger_timeframe,256)
        if not isinstance(rows,(list,tuple)) or len(rows)>256 or any(not isinstance(b,dict) or type(b.get('time')) is not int for b in rows):
            raise MarketFailure('INSUFFICIENT_DATA','invalid trigger series')
        cutoff=p['decision_close_utc']
        rows=[b for b in rows if b['time']+TIMEFRAMES[trigger_timeframe]<=cutoff]
        p['frames'][trigger_timeframe]=_bars(rows,trigger_timeframe,cutoff,m,symbol,provider.name)
    p['schema_version']='forex-snapshot-6';p['trigger_timeframe']=trigger_timeframe
    raw=canonical(p);snapshot=Snapshot(sha256(raw.encode()).hexdigest(),raw)
    instrument=Instrument(symbol,p['market_type'],venue,'bid',p['contract_type'],symbol[-3:])
    frames=[];caps=None
    for tf,rows in p['frames'].items():
        rows=rows[-220:]
        bars=tuple(Candle(instrument,b['time']*1000,b['close_time_utc']*1000,True,
                         b['open'],b['high'],b['low'],b['close'],b['volume'],b['volume_kind'],b['source']) for b in rows)
        gaps=tuple((a.close_time_ms,b.open_time_ms) for a,b in zip(bars,bars[1:]) if a.close_time_ms!=b.open_time_ms)
        if gaps and not verified:raise MarketFailure('INSUFFICIENT_DATA','session gaps lack verified broker schedule')
        asof=int((now if tf==timeframe else p['decision_close_utc'])*1000)
        quality=validate_series(bars,timeframe_ms=TIMEFRAMES[tf]*1000,as_of_ms=asof,
                                max_age_ms=TIMEFRAMES[tf]*2000,min_bars=200,permitted_gaps=gaps)
        if not quality.ok:
            codes=sorted({i.code for i in quality.issues})
            raise MarketFailure('STALE_DATA' if 'stale_data' in codes else 'INSUFFICIENT_DATA','V2 QC: '+','.join(codes))
        current=candle_capabilities(bars)
        caps=current if caps is None else caps&current
        frames.append(Frame(tf,bars,gaps,int(p['decision_close_utc']*1000)))
    if verified:caps=caps|{'broker_calendar'}
    return MarketView(snapshot,tuple(frames),frozenset(caps),canonical(session))
