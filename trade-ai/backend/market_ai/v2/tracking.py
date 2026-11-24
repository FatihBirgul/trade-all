"""Opt-in bounded analysis following. Reuses V2 analysis, scanner lease/outbox;
never polls/fills paper orders or changes an immutable decision."""
import threading
import uuid
from typing import Literal
from pydantic import Field
from fastapi import APIRouter,Depends
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from secrets import compare_digest
from .api_models import Model,AnalysisResponse,AnalyzeRequest,ErrorResponse
from .product_db import fingerprint,encode
from . import domain_journal as domain
from .technical_adapter import TIMEFRAME_MS
from .errors import V2Error

class TrackingCreate(Model):
    analysis_id: str=Field(pattern='^[a-f0-9]{64}$')
class TrackingChange(Model):
    enabled: bool=Field(strict=True)
class TrackingSourcePolicyRequest(Model):
    notify_source_changes: bool=Field(strict=True)
class TrackingSourcePolicy(TrackingSourcePolicyRequest):
    tracking_id: str
    portfolio_id: Literal['AUTO','MANUAL']
    data_mode: Literal['fixture','live']
    source_event_ttl_ms: Literal[900000]=900000
    delivery_service: Literal['not_configured']='not_configured'
class TrackingResponse(Model):
    tracking_id: str
    origin_analysis_id: str
    last_analysis_id: str
    portfolio_id: Literal['AUTO','MANUAL']
    symbol: str
    timeframe: str
    data_mode: Literal['fixture','live']
    enabled: bool
    status: Literal['waiting','monitoring','waiting_data','paused','error']
    last_checked_ms: int | None
    last_direction: str
    last_reason: str
    notified_changes: int
    worker_running: bool
    paper_only: Literal[True]=True


def condition(a,now):
    fresh=bool(a.quality.get('ok') and a.price is not None and a.price_time_ms is not None and 0<=now-a.price_time_ms<=TIMEFRAME_MS[a.timeframe] and now<a.expires_at_ms)
    direction=a.direction if fresh else 'WAIT'
    reason=a.reason if fresh or a.direction=='WAIT' else 'stale_analysis'
    signature=fingerprint(dict(direction=direction,reason=reason,quality_ok=fresh,
        regime=a.regime.get('regime'),strategy=a.router.get('strategy_id'),router_status=a.router.get('status'),
        setups={k:{'status':v.get('status'),'reason':v.get('reason'),'direction':v.get('direction')} for k,v in (a.strategy_setups or {}).items()}))
    return signature,fresh,direction,reason

class TrackingService:
    def __init__(self,runtime):
        self.r=runtime;self.db=runtime.db;self.worker=None;self.stopping=False;self.worker_error=None
        # ProductDatabase/RecordStore ownership and mode have already been checked.
        with self.db.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS analysis_tracking(id TEXT PRIMARY KEY,body TEXT NOT NULL,body_hash TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS analysis_tracking_state(id TEXT PRIMARY KEY,body TEXT NOT NULL,body_hash TEXT NOT NULL)')
            domain.attach(c)
            if self.db.get(c,'analysis_tracking_state','state') is None:
                self.db.put(c,'analysis_tracking_state','state',{'last_tick_ms':None})
    def _save(self,c,table,key,body):
        assert table in ('analysis_tracking','analysis_tracking_state')
        c.execute(f'UPDATE {table} SET body=?,body_hash=? WHERE id=?',(encode(body),fingerprint(body),key))
    def view(self,row):
        if self.worker_error and row["enabled"]:row={**row,"status":"error","last_reason":self.worker_error}
        return TrackingResponse(**{key:value for key,value in row.items() if key in TrackingResponse.model_fields and key!='worker_running'},worker_running=bool(self.worker and self.worker.thread.is_alive()))
    def rows(self):
        with self.db.transaction() as c:return [self.view(row) for row in self.db.rows(c,'analysis_tracking')]
    def get(self,key):
        with self.db.transaction() as c:
            row=self.db.get(c,'analysis_tracking',key)
            if not row:raise V2Error('TRACKING_NOT_FOUND','Analysis follow record not found',404)
            return self.view(row)
    def start(self,analysis_id):
        with self.db.transaction() as c:
            if self.db.domain_enabled:
                domain.begin(c, effective_at=self.r.clock(), source={'control':'follow_start','analysis_id':analysis_id})
                domain.note(c, 'control.requested', {'analysis_id':analysis_id})
            raw=self.db.get(c,'analyses',analysis_id)
            if raw is None:raise V2Error('ANALYSIS_NOT_FOUND','Recorded analysis not found',404)
            a=AnalysisResponse.model_validate(raw)
            if a.data_mode!=self.db.mode:raise V2Error('DATA_MODE_MISMATCH','Analysis mode mismatch')
            key=fingerprint({'follow':analysis_id,'account':a.risk_portfolio,'mode':a.data_mode})
            existing=self.db.get(c,'analysis_tracking',key)
            if existing:return self.view(existing)
            rows=self.db.rows(c,'analysis_tracking')
            if len(rows)>=100 or sum(bool(r['enabled']) for r in rows)>=6:raise V2Error('TRACKING_LIMIT','At most six active and 100 total follow records')
            if any(row['enabled'] and (row['symbol'],row['timeframe'],row['portfolio_id'])==(a.symbol,a.timeframe,a.risk_portfolio) for row in rows):
                raise V2Error('TRACKING_ALREADY_ACTIVE','This market/timeframe/account is already followed')
            signature,fresh,direction,reason=condition(a,self.r.clock())
            row=dict(tracking_id=key,origin_analysis_id=analysis_id,last_analysis_id=analysis_id,
                portfolio_id=a.risk_portfolio,symbol=a.symbol,timeframe=a.timeframe,data_mode=a.data_mode,
                enabled=True,status='waiting',last_checked_ms=None,last_direction=direction,last_reason=reason,
                notified_changes=0,timeframes=a.timeframes,condition_hash=signature,last_boundary=None,last_quality=fresh,next_check_ms=0,failure_count=0)
            profile_id=a.technical_methods.get('profile_control',{}).get('profile_record_id')
            if profile_id is not None:
                self.r.analysis.profiles.get(c,a.risk_portfolio,profile_id)
                row['profile_id']=profile_id
            self.db.put(c,'analysis_tracking',key,row)
            return self.view(row)
    def change(self,key,enabled):
        with self.db.transaction() as c:
            if self.db.domain_enabled:
                domain.begin(c, effective_at=self.r.clock(), source={'control':'follow_change','tracking_id':key})
                domain.note(c, 'control.requested', {'enabled':enabled})
            row=self.db.get(c,'analysis_tracking',key)
            if not row:raise V2Error('TRACKING_NOT_FOUND','Analysis follow record not found',404)
            if row['enabled']==enabled:return self.view(row)
            if enabled:
                others=self.db.rows(c,'analysis_tracking')
                if sum(bool(r['enabled']) for r in others)>=6:raise V2Error('TRACKING_LIMIT','At most six active follow records')
                if any(r['tracking_id']!=key and r['enabled'] and (r['symbol'],r['timeframe'],r['portfolio_id'])==(row['symbol'],row['timeframe'],row['portfolio_id']) for r in others):raise V2Error('TRACKING_ALREADY_ACTIVE','Duplicate active follow')
            row['enabled']=enabled;row['next_check_ms']=0;row['status']='waiting' if enabled else 'paused'
            self._save(c,'analysis_tracking',key,row)
            return self.view(row)
    def source_policy(self,key,enabled=None):
        with self.db.transaction() as c:
            row=self.db.get(c,'analysis_tracking',key)
            if not row:raise V2Error('TRACKING_NOT_FOUND','Analysis follow record not found',404)
            if enabled is not None and enabled!=row.get('notify_source_changes',False):
                if self.db.domain_enabled:
                    domain.begin(c,effective_at=self.r.clock(),source={'control':'follow_source_policy','tracking_id':key})
                    domain.note(c,'control.requested',{'notify_source_changes':enabled})
                row['notify_source_changes']=enabled
                row['notified_data_available']=bool(row['last_quality'])
                self._save(c,'analysis_tracking',key,row)
            return TrackingSourcePolicy(tracking_id=key,portfolio_id=row['portfolio_id'],data_mode=row['data_mode'],notify_source_changes=row.get('notify_source_changes',False))

    def _guard(self,c,owner,key):
        state=self.db.get(c,'scanner_state','state');row=self.db.get(c,'analysis_tracking',key)
        if self.stopping or not row or not row['enabled'] or state['lease_id']!=owner or state['lease_until_ms']<=self.r.clock():
            if self.db.domain_enabled:domain.blocked(c, self.r.clock(), {'control':'follow_guard','tracking_id':key})
            raise V2Error('TRACKING_STOPPED','Follow stopped or lease expired')
    def tick(self):
        now=self.r.clock();owner=uuid.uuid4().hex
        with self.db.transaction() as c:
            state=self.db.get(c,'scanner_state','state');schedule=self.db.get(c,'analysis_tracking_state','state')
            if state['lease_until_ms']>now or (schedule['last_tick_ms'] is not None and now-schedule['last_tick_ms']<60000):return []
            due=[r for r in self.db.rows(c,'analysis_tracking') if r['enabled'] and r.get('next_check_ms',0)<=now and (not r['last_quality'] or r['last_boundary']!=now//TIMEFRAME_MS[r['timeframe']]*TIMEFRAME_MS[r['timeframe']])]
            due=sorted(due,key=lambda row:row['last_checked_ms'] or 0)[:2]
            if not due:return []
            state.update(lease_id=owner,lease_until_ms=now+120000)
            self.db.update(c,'scanner_state','state',state)
            schedule['last_tick_ms']=now;self._save(c,'analysis_tracking_state','state',schedule)
        output=[]
        try:
            for row in due:
                key=row['tracking_id'];boundary=now//TIMEFRAME_MS[row['timeframe']]*TIMEFRAME_MS[row['timeframe']]
                try:
                    request=AnalyzeRequest(profile_id=row.get('profile_id'),symbol=row['symbol'],timeframe=row['timeframe'],timeframes=[t for t in row['timeframes'] if t!=row['timeframe']],risk_portfolio=row['portfolio_id'],data_mode=self.db.mode,auto_paper=False,idempotency_key='follow:'+key+':'+str(now//60000))
                    result=self.r.analysis.analyze(request,commit_guard=lambda c:self._guard(c,owner,key))
                    signature,fresh,direction,reason=condition(result,self.r.clock())
                    with self.db.transaction() as c:
                        self._guard(c,owner,key)
                        current=self.db.get(c,'analysis_tracking',key)
                        market_changed=fresh and signature!=current['condition_hash']
                        available_changed=current.get('notify_source_changes',False) and fresh!=current.get('notified_data_available',current['last_quality'])
                        if market_changed or available_changed:
                            kind='analysis_condition_changed' if market_changed else 'source_recovered' if fresh else 'source_unavailable'
                            revision=current.get('source_event_revision',0)+1
                            identity={'follow':key,'analysis_id':result.analysis_id,'prior':current['condition_hash'],'condition':signature}
                            if not market_changed:identity.update(kind=kind,revision=revision)
                            notification=fingerprint(identity)
                            details=dict(tracking_id=key,origin_analysis_id=row['origin_analysis_id'],analysis_id=result.analysis_id,portfolio_id=row['portfolio_id'],change_kind=kind,direction=direction,reason=reason)
                            if available_changed:details['expires_at_ms']=self.r.clock()+900000
                            self.r.scanner._notify(c,notification,'analysis',details)
                            current['source_event_revision']=revision
                            if market_changed:current['notified_changes']+=1
                        if current.get('notify_source_changes',False):current['notified_data_available']=fresh
                        # Missing/stale input is not a new market condition. Retain the
                        # last valid signature; opt-in source transitions have separate dedup.
                        failures=0 if fresh else min(current.get('failure_count',0)+1,5)
                        current.update(last_analysis_id=result.analysis_id,last_checked_ms=self.r.clock(),last_boundary=boundary,last_quality=fresh,last_direction=direction,last_reason=reason,status='monitoring' if fresh else 'waiting_data',failure_count=failures,next_check_ms=0 if fresh else self.r.clock()+min(60000*2**(failures-1),900000))
                        if fresh:current['condition_hash']=signature
                        self._save(c,'analysis_tracking',key,current)
                        output.append(self.view(current))
                except V2Error as error:
                    with self.db.transaction() as c:
                        current=self.db.get(c,'analysis_tracking',key)
                        if current and current['enabled'] and self.db.get(c,'scanner_state','state')['lease_id']==owner:
                            failures=min(current.get('failure_count',0)+1,5)
                            current.update(status='error',last_quality=False,last_reason=error.code,last_checked_ms=self.r.clock(),failure_count=failures,next_check_ms=self.r.clock()+min(60000*2**(failures-1),900000));self._save(c,'analysis_tracking',key,current)
        finally:
            with self.db.transaction() as c:
                state=self.db.get(c,'scanner_state','state')
                if state['lease_id']==owner:
                    state.update(lease_id=None,lease_until_ms=0);self.db.update(c,'scanner_state','state',state)
        return output

class TrackingWorker:
    def __init__(self,service):
        self.service=service;service.worker=self;self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self.run,name='v2-analysis-follow',daemon=True)
    def run(self):
        while not self.stop_event.is_set():
            try:self.service.tick();self.service.worker_error=None
            except Exception:self.service.worker_error="TRACKING_WORKER_ERROR"
            self.stop_event.wait(60)
    def start(self):self.service.stopping=False;self.thread.start()
    def stop(self):self.service.stopping=True;self.stop_event.set();self.thread.join(timeout=2)

def install_tracking(app,runtime):
    service=TrackingService(runtime);app.state.tracking=service
    auth=HTTPBearer(auto_error=False,scheme_name='V2Bearer')
    def require(credentials:HTTPAuthorizationCredentials|None=Depends(auth)):
        if credentials is None or not compare_digest(credentials.credentials.encode(),runtime.token.encode()):raise V2Error('UNAUTHORIZED','Valid local V2 bearer required',401)
    router=APIRouter(prefix='/api/v2',tags=['Trade AI V2'],dependencies=[Depends(require)],responses={401:{'model':ErrorResponse,'description':'Unauthorized'},404:{'model':ErrorResponse,'description':'Not Found'},409:{'model':ErrorResponse,'description':'Conflict'},422:{'model':ErrorResponse,'description':'Unprocessable Entity'}})
    @router.get('/analysis-tracking',response_model=list[TrackingResponse])
    def rows():return service.rows()
    @router.post('/analysis-tracking',response_model=TrackingResponse)
    def start(request:TrackingCreate):return service.start(request.analysis_id)
    @router.get('/analysis-tracking/{tracking_id}',response_model=TrackingResponse)
    def get(tracking_id:str):return service.get(tracking_id)
    @router.get('/analysis-tracking/{tracking_id}/notification-policy',response_model=TrackingSourcePolicy)
    def source_policy(tracking_id:str):return service.source_policy(tracking_id)
    @router.post('/analysis-tracking/{tracking_id}/notification-policy',response_model=TrackingSourcePolicy)
    def change_source_policy(tracking_id:str,request:TrackingSourcePolicyRequest):return service.source_policy(tracking_id,request.notify_source_changes)
    @router.post('/analysis-tracking/{tracking_id}',response_model=TrackingResponse)
    def change(tracking_id:str,request:TrackingChange):return service.change(tracking_id,request.enabled)
    app.include_router(router)
