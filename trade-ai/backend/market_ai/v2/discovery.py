"""Versioned, bounded account scanners. Existing analysis; NO financial authority.

Universe is the existing three supported spot instruments, validated through the
configured provider's rules. Not whole-Binance discovery. No invented spread or
liquidity metrics. Lifecycle facts have a per-account checksum chain, not a digital
signature. Financial/domain history is never rewritten or replay-filled here.
"""
from decimal import Decimal
from time import monotonic
from uuid import uuid4
import threading
from typing import Literal
from pydantic import Field,model_validator,field_validator
from .api_models import Model,AnalyzeRequest
from .product_db import fingerprint,encode
from .errors import V2Error
from .market_data_contract import validate_series
from .technical_adapter import TIMEFRAME_MS
from .analysis_service import AnalysisService
from .spot_provider import ProviderUnavailable
from .paper_ledger import decimal_context
from .strategies import BUILTIN_IDS
from .decision_record import ImmutableDecisionRecord

VERSION='v2-opportunity-discovery-1'
UNIVERSE=('BTCUSDT','ETHUSDT','SOLUSDT')
FRAME=Literal['5m','15m','1H','4H','1D']
TERMINAL={'INVALIDATED','EXPIRED'}
TABLES=('discovery_configs','discovery_receipts','discovery_runtime','discovery_jobs','opportunities','opportunity_events','opportunity_streams','discovery_queue')
class DiscoveryWrite(Model):
    # Optional extension: legacy requests retain their original command digest.
    name:str=Field('Tarama profili',min_length=1,max_length=80)
    runtime_mode:Literal['off','selected_profile','supported_markets']|None=None
    @field_validator('name')
    @classmethod
    def clean_name(cls,value):
        value=value.strip()
        if not value or any(ord(ch)<32 or ord(ch)==127 for ch in value):raise ValueError('A printable profile name is required')
        return value
    idempotency_key:str=Field(min_length=8,max_length=128,pattern=r'^[A-Za-z0-9_.:-]+$')
    expected_revision:int=Field(0,strict=True,ge=0,le=256)
    enabled:bool=Field(False,strict=True)
    discovery:bool=Field(False,strict=True)
    favorites:list[Literal['BTCUSDT','ETHUSDT','SOLUSDT']]=Field(default_factory=list,max_length=10)
    interval_seconds:int=Field(300,strict=True,ge=60,le=3600)
    timeframe:FRAME='5m'
    profile_id:str|None=Field(None,pattern=r'^[a-f0-9]{64}$')
    ttl_seconds:int=Field(3600,strict=True,ge=300,le=86400)
    notify_early:bool=Field(False,strict=True)
    notify_confirmed:bool=Field(False,strict=True)
    notify_invalidated:bool=Field(False,strict=True)
    notify_expired:bool=Field(False,strict=True)
    notify_unavailable:bool=Field(False,strict=True)
    @model_validator(mode='after')
    def unique(self):
        if self.runtime_mode=='off' and self.enabled:raise ValueError('Off mode cannot activate scanning')
        if len(set(self.favorites))!=len(self.favorites):raise ValueError('Unique favorites required')
        return self
class DiscoveryReceipt(Model):
    portfolio_id:Literal['AUTO','MANUAL']
    data_mode:Literal['fixture','live']
    config:dict

class DiscoveryView(Model):
    portfolio_id:Literal['AUTO','MANUAL']
    data_mode:Literal['fixture','live']
    version:str=VERSION
    config:dict
    runtime:dict
    jobs:list[dict]
    universe:dict
    trade_permission:Literal[False]=False
class OpportunityRecord(Model):
    opportunity_id:str
    portfolio_id:Literal['AUTO','MANUAL']
    symbol:Literal['BTCUSDT','ETHUSDT','SOLUSDT']
    provider:str
    source:str
    venue:str
    timeframe:FRAME
    profile_id:str|None
    initial_analysis_id:str
    last_analysis_id:str
    source_record_ids:dict
    first_known_ms:int
    first_source_ms:int
    expires_at_ms:int
    last_observed_ms:int
    last_source_ms:int
    state:Literal['EARLY','CONFIRMED','INVALIDATED','EXPIRED','UNAVAILABLE']
    last_valid_state:Literal['EARLY','CONFIRMED']
    setup_fingerprint:str
    modes:list[Literal['favorites','discovery']]
    reason:str
    evidence:dict
    missing:list[str]
    strategy_id:str
    direction:Literal['bullish','bearish']
    stale:bool
    trade_permission:Literal[False]=False
class OpportunityList(Model):
    portfolio_id:Literal['AUTO','MANUAL']
    data_mode:Literal['fixture','live']
    items:list[OpportunityRecord]
    next_offset:int|None=None
    trade_permission:Literal[False]=False
class OpportunityDetail(Model):
    portfolio_id:Literal['AUTO','MANUAL']
    data_mode:Literal['fixture','live']
    opportunity:OpportunityRecord
    events:list[dict]
    trade_permission:Literal[False]=False
class DiscoveryTick(Model):
    portfolio_id:Literal['AUTO','MANUAL']
    data_mode:Literal['fixture','live']
    status:str
    provider_calls:int=Field(0,ge=0,le=12)
    reason:str|None=None
    jobs:list[dict]=Field(default_factory=list)
    trade_permission:Literal[False]=False

def observation(a,now,allowed):
    """Only engine-confirmed, risk-eligible decisions can be CONFIRMED.

    EARLY is the existing closed reclaim (liquidity_sweep), still missing the
    failed-breakout follow-through. No new trade indicator or confidence score.
    """
    known=a.price_time_ms
    if (not a.quality.get('ok') or a.price is None or type(known) is not int or not 0<=now-known<=TIMEFRAME_MS[a.timeframe] or now>=a.expires_at_ms):
        return dict(state='UNAVAILABLE',reason=a.reason or 'source_quality',source_ms=None,strategy=None,direction='neutral',evidence={},missing=['fresh_closed_source'])
    sid=a.router.get('strategy_id');setup=a.strategy_setups.get(sid,{})
    control=a.technical_methods.get('profile_control')
    if (sid in allowed and a.router.get('status')=='selected' and a.direction in ('bullish','bearish')
            and setup.get('status')=='confirmed' and setup.get('direction')==a.direction
            and a.risk.get('status')=='eligible_for_paper' and (not control or control.get('passes') is True)
            and a.mtf.get('conflict_ratio',0)==0):
        return dict(state='CONFIRMED',reason='existing_strategy_and_all_execution_gates_passed',source_ms=known,strategy=sid,direction=a.direction,evidence={'setup':setup,'mtf':a.mtf,'risk_status':a.risk.get('status')},missing=[])
    sweep=a.technical_methods.get('liquidity_sweep',{});failed=a.strategy_setups.get('failed_breakout_v2',{})
    if ('failed_breakout_v2' in allowed and a.direction=='WAIT' and sweep.get('status')=='available'
            and sweep.get('direction') in ('bullish','bearish') and sweep.get('as_of_ms')==known
            and failed.get('reason')=='entry_confirmation_missing'):
        return dict(state='EARLY',reason='closed_reclaim_waits_for_existing_failed_breakout_confirmation',source_ms=known,strategy='failed_breakout_v2',direction=sweep['direction'],evidence={'closed_reclaim':sweep,'strategy_requirements':failed.get('requirements',[])},missing=['existing_strategy_follow_through','aggregate_MTF_profile_risk_gates'])
    return dict(state='OBSERVING',reason=a.reason,source_ms=known,strategy=None,direction='neutral',evidence={},missing=['qualifying_setup'])

class BudgetProvider:
    def __init__(self,provider,deadline,reserve):
        self.p=provider;self.deadline=deadline;self.calls=0;self.cache={};self.reserve=reserve
        self.name,self.venue,self.mode,self.source_name=provider.name,provider.venue,provider.mode,provider.source_name
    def _get(self,kind,args):
        key=(kind,*args)
        if monotonic()>self.deadline:raise ProviderUnavailable('discovery_cycle_deadline')
        if key not in self.cache:
            if self.calls>=12:raise ProviderUnavailable('discovery_provider_budget')
            self.reserve();self.calls+=1
            value=getattr(self.p,kind)(*args)
            self.cache[key]=tuple(value) if kind=='candles' else dict(value)
        if monotonic()>self.deadline:raise ProviderUnavailable('discovery_cycle_deadline')
        return self.cache[key]
    def rules(self,symbol):return self._get('rules',(symbol,))
    def candles(self,symbol,tf,now):return self._get('candles',(symbol,tf,now))

class DiscoveryService:
    def __init__(self,runtime):
        self.r,self.db=runtime,runtime.db;self.worker=None;self.stopping=False
        with self.db.transaction() as c:
            for table in TABLES:c.execute(f'CREATE TABLE IF NOT EXISTS {table}(id TEXT PRIMARY KEY,body TEXT NOT NULL,body_hash TEXT NOT NULL)')
            for table in ('discovery_configs','discovery_receipts','opportunity_events'):
                for op in ('UPDATE','DELETE'):c.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable discovery fact'); END")
            c.execute("CREATE INDEX IF NOT EXISTS discovery_job_account ON discovery_jobs(json_extract(body,'$.portfolio_id'),json_extract(body,'$.boundary_ms'))")
            c.execute("CREATE INDEX IF NOT EXISTS opportunity_account ON opportunities(json_extract(body,'$.portfolio_id'),json_extract(body,'$.last_observed_ms'))")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS opportunity_event_sequence ON opportunity_events(json_extract(body,'$.portfolio_id'),json_extract(body,'$.sequence'))")
            if not self.db.get(c,'discovery_runtime','global'):
                self.db.put(c,'discovery_runtime','global',{'owner':None,'lease_until_ms':0,'last_tick_ms':None,'heartbeat_ms':None,'cursor':0,'shutdown':'inactive'})
    def _save(self,c,table,key,body):
        if table not in ('discovery_runtime','discovery_jobs','opportunities','opportunity_streams','discovery_queue'):raise ValueError('Immutable discovery table')
        if self.db.get(c,table,key):c.execute(f'UPDATE {table} SET body=?,body_hash=? WHERE id=?',(encode(body),fingerprint(body),key))
        else:self.db.put(c,table,key,body)
    def _rows(self,c,table,account,limit=10000):
        return [self.db.decode(r) for r in c.execute(f"SELECT body,body_hash FROM {table} WHERE json_extract(body,'$.portfolio_id')=? ORDER BY rowid DESC LIMIT ?",(account,limit))]
    def _config(self,c,account):
        rows=self._rows(c,'discovery_configs',account,1)
        return rows[0] if rows else {'portfolio_id':account,'revision':0,**DiscoveryWrite(idempotency_key='default-disabled').model_dump(exclude={'idempotency_key','expected_revision'})}
    def _schedule(self,c,account):
        return self.db.get(c,'discovery_runtime',account) or {'portfolio_id':account,'next_due_ms':0,'last_attempt_ms':None,'last_success_ms':None,'last_discovery_ms':None,'missed_scans':0,'failures':0,'provider_status':'not_probed','screened':0,'eligible':0,'last_error':None}
    def configure(self,account,request):
        args=request.model_dump(exclude={'name','runtime_mode'})
        if 'name' in request.model_fields_set:args['name']=request.name
        if request.runtime_mode is not None:args['runtime_mode']=request.runtime_mode
        key=fingerprint({'account':account,'key':request.idempotency_key})
        with self.db.transaction() as c:
            old=self.db.get(c,'discovery_receipts',key)
            if old:
                if old['digest']!=fingerprint(args):raise V2Error('IDEMPOTENCY_CONFLICT','Discovery command conflicts',409)
                return old['result']
            cfg=self._config(c,account)
            if cfg['revision']!=request.expected_revision:raise V2Error('DISCOVERY_REVISION_CONFLICT','Read current scanner revision before editing',409)
            if cfg['revision']>=256:raise V2Error('DISCOVERY_LIMIT','Configuration history capacity reached; no deletion',409)
            if request.profile_id and (request.enabled or request.profile_id!=cfg.get('profile_id') or request.timeframe!=cfg.get('timeframe')):
                _,profile=self.r.analysis.profiles.get(c,account,request.profile_id)
                if profile.setup_timeframe!=request.timeframe:raise V2Error('PROFILE_TIMEFRAME_MISMATCH','Scanner and profile frames must match',422)
            previous=cfg
            cfg={'portfolio_id':account,'revision':cfg['revision']+1,**request.model_dump(exclude={'idempotency_key','expected_revision'})}
            # Old clients cannot silently erase metadata or downgrade an explicit
            # activation policy by omitting fields unknown to their contract.
            if 'name' not in request.model_fields_set:cfg['name']=previous.get('name',request.name)
            if request.runtime_mode is None:cfg['runtime_mode']=previous.get('runtime_mode')
            if request.enabled and cfg['runtime_mode'] is not None:
                readiness=self._activation(c,cfg)
                if readiness['reasons']:raise V2Error('DISCOVERY_ACTIVATION_BLOCKED','Scanner activation blocked: '+','.join(readiness['reasons']),409)
            self.db.put(c,'discovery_configs',fingerprint(cfg),cfg)
            for queued in self._rows(c,'discovery_queue',account,3):
                queued.update(status='superseded',reason='configuration_revision_changed');self._save(c,'discovery_queue',fingerprint({'account':account,'symbol':queued['symbol']}),queued)
            schedule=self._schedule(c,account);schedule['next_due_ms']=self.r.clock();self._save(c,'discovery_runtime',account,schedule)
            result={'portfolio_id':account,'data_mode':self.db.mode,'config':cfg}
            self.db.put(c,'discovery_receipts',key,{'portfolio_id':account,'digest':fingerprint(args),'result':result})
            return result
    def _activation(self,c,cfg):
        g=self.db.get(c,'discovery_runtime','global');now=self.r.clock();reasons=[]
        mode=cfg.get('runtime_mode')
        if mode in (None,'off'):reasons.append('runtime_mode_required' if mode is None else 'runtime_off')
        if mode=='selected_profile' and not cfg.get('profile_id'):reasons.append('profile_required')
        if mode=='selected_profile' and cfg.get('discovery'):reasons.append('selected_profile_requires_favorites_mode')
        if mode=='supported_markets' and not cfg.get('discovery'):reasons.append('discovery_scope_required')
        if not cfg.get('favorites') and not cfg.get('discovery'):reasons.append('empty_scope')
        heartbeat=g.get('worker_heartbeat_ms')
        available=bool(g.get('worker_owner') and g.get('worker_until_ms',0)>now and type(heartbeat) is int and 0<=now-heartbeat<120000)
        if not available:reasons.append('runtime_not_running')
        if g.get('worker_stopping'):reasons.append('worker_stopping')
        return {'state':'blocked' if reasons else 'active' if cfg['enabled'] else 'ready_to_activate','reasons':reasons,'runtime_available':available,'account_enabled':cfg['enabled'],'starts_process':False,'requires_discovery_write':True,'semantics':'recent_lease_and_heartbeat_not_continuous_availability'}
    def view(self,account):
        with self.db.transaction() as c:
            cfg=self._config(c,account);state=self._schedule(c,account);global_state=self.db.get(c,'discovery_runtime','global')
            jobs=self._rows(c,'discovery_jobs',account,30)
            queue=self._rows(c,'discovery_queue',account,3)
            state.update(activation=self._activation(c,cfg),queue=queue,backlog_age_ms=max((max(0,self.r.clock()-q['queued_at_ms']) for q in queue if q['status']=='pending'),default=0),lease_until_ms=global_state['lease_until_ms'],heartbeat_ms=global_state.get('worker_heartbeat_ms'),recovered_leases=global_state.get('recovered_leases',0),worker_active=bool(self.worker and self.worker.is_alive()) or bool(global_state.get('worker_owner') and global_state.get('worker_until_ms',0)>self.r.clock()),worker_stopping=global_state.get('worker_stopping',False),shutdown=global_state['shutdown'],backlog=sum(j['status']=='pending' for j in queue),capacity=10000,opportunity_capacity=256)
            return {'portfolio_id':account,'data_mode':self.db.mode,'version':VERSION,'config':cfg,'runtime':state,'jobs':jobs,'universe':{'scope':'configured_supported_USDT_spot_only','symbols':list(UNIVERSE),'provider':self.r.analysis.provider.name,'liquidity_spread_filters':'unavailable_not_applied','live_discovery_performance':'UNVERIFIED'},'trade_permission':False}
    def opportunities(self,account,limit=20,offset=0):
        now=self.r.clock()
        with self.db.transaction() as c:
            rows=[self.db.decode(r) for r in c.execute("SELECT body,body_hash FROM opportunities WHERE json_extract(body,'$.portfolio_id')=? ORDER BY rowid DESC LIMIT ? OFFSET ?",(account,limit+1,offset))]
        return {'portfolio_id':account,'data_mode':self.db.mode,'items':[{**r,'stale':r['state'] in ('UNAVAILABLE','EXPIRED','INVALIDATED') or now>=r['expires_at_ms'] or not 0<=now-r.get('last_source_ms',r['first_known_ms'])<=TIMEFRAME_MS[r['timeframe']]} for r in rows[:limit]],'next_offset':offset+limit if len(rows)>limit else None,'trade_permission':False}
    def detail(self,account,key):
        with self.db.transaction() as c:
            row=self.db.get(c,'opportunities',key)
            if row is not None and row['opportunity_id']!=key:raise V2Error('STORAGE_CORRUPT','Opportunity identity mismatch',503)
            if row is None or row['portfolio_id']!=account:raise V2Error('OPPORTUNITY_NOT_FOUND','Opportunity not found for this account',404)
            events=[self.db.decode(r) for r in c.execute("SELECT body,body_hash FROM opportunity_events WHERE json_extract(body,'$.opportunity_id')=? ORDER BY rowid DESC LIMIT 50",(key,))]
            return {'portfolio_id':account,'data_mode':self.db.mode,'opportunity':{**row,'stale':row['state'] in ('UNAVAILABLE','EXPIRED','INVALIDATED') or self.r.clock()>=row['expires_at_ms'] or not 0<=self.r.clock()-row.get('last_source_ms',row['first_known_ms'])<=TIMEFRAME_MS[row['timeframe']]},'events':events,'trade_permission':False}
    def _event(self,c,opp,state,reason,analysis_id,source_ms,cfg):
        count=c.execute("SELECT count(*) FROM opportunity_events WHERE json_extract(body,'$.portfolio_id')=?",(opp['portfolio_id'],)).fetchone()[0]
        if count>=10000:raise V2Error('DISCOVERY_LIMIT','Lifecycle history capacity reached; no pruning',409)
        previous=c.execute("SELECT body,body_hash FROM opportunity_events WHERE json_extract(body,'$.portfolio_id')=? ORDER BY rowid DESC LIMIT 1",(opp['portfolio_id'],)).fetchone()
        prior=self.db.decode(previous) if previous else None
        saved=self.db.get(c,'analyses',analysis_id)
        raw=c.execute('SELECT body_json FROM decision_records WHERE record_id=?',(analysis_id,)).fetchone()
        record=ImmutableDecisionRecord(analysis_id,raw[0]) if raw else None
        if saved is None or saved['risk_portfolio']!=opp['portfolio_id'] or record is None or not record.verify():raise V2Error('STORAGE_CORRUPT','Lifecycle event source failed identity verification',503)
        source_refs=record.payload().get('source_records',{})
        event={'schema_version':1,'portfolio_id':opp['portfolio_id'],'opportunity_id':opp['opportunity_id'],'sequence':count+1,'previous_hash':prior['event_hash'] if prior else '0'*64,'state':state,'reason':reason,'analysis_id':analysis_id,'source_ms':source_ms,'recorded_at_ms':self.r.clock(),'modes':opp['modes'],'source_record_ids':source_refs,'source_reference_semantics':'last_valid_when_source_ms_absent','trade_permission':False}
        event['event_hash']=fingerprint(event);self.db.put(c,'opportunity_events',event['event_hash'],event)
        if reason!='scanner_provenance_extended_same_closed_source' and cfg.get('enabled') and cfg.get('notify_'+('unavailable' if reason=='source_recovered_no_new_market_confirmation' else state.lower()),False):
            self.r.scanner._notify(c,event['event_hash'],'analysis',{'portfolio_id':opp['portfolio_id'],'opportunity_id':opp['opportunity_id'],'change_kind':'opportunity_'+('recovered' if reason=='source_recovered_no_new_market_confirmation' else state.lower()),'analysis_id':analysis_id,'reason':reason,'category':'analysis','expires_at_ms':self.r.clock()+900000,'trade_permission':False})
    def _apply(self,c,job,a,cfg,allowed):
        now=self.r.clock()
        saved=self.db.get(c,'analyses',a.analysis_id)
        raw=c.execute('SELECT body_json FROM decision_records WHERE record_id=?',(a.analysis_id,)).fetchone()
        record=ImmutableDecisionRecord(a.analysis_id,raw[0]) if raw else None
        if saved is None or saved['risk_portfolio']!=job['portfolio_id'] or fingerprint(saved)!=fingerprint(a.model_dump(mode='json')) or record is None or not record.verify():
            raise V2Error('STORAGE_CORRUPT','Opportunity requires exact immutable saved analysis',503)
        refs=record.payload().get('source_records',{})
        o=observation(a,now,allowed)
        stream_key=fingerprint({k:job[k] for k in ('portfolio_id','symbol','timeframe','profile_id','provider','source','venue')})
        stream=self.db.get(c,'opportunity_streams',stream_key) or {'portfolio_id':job['portfolio_id'],'opportunity_id':None,'last_source_ms':-1,'rearmed':True}
        old=self.db.get(c,'opportunities',stream['opportunity_id']) if stream['opportunity_id'] else None
        if o['source_ms'] is not None and o['source_ms']<=stream['last_source_ms']:
            if old and o['source_ms']==stream['last_source_ms'] and old['state'] not in TERMINAL:
                modes=sorted(set(old['modes'])|set(job['modes']))
                if modes!=old['modes']:
                    old['modes']=modes
                    self._event(c,old,old['state'],'scanner_provenance_extended_same_closed_source',a.analysis_id,o['source_ms'],cfg)
                    self._save(c,'opportunities',old['opportunity_id'],old)
            return
        if old and old['state'] not in TERMINAL and now>=old['expires_at_ms']:
            old.update(state='EXPIRED',reason='explicit_opportunity_TTL_elapsed',last_observed_ms=now)
            self._event(c,old,'EXPIRED',old['reason'],a.analysis_id,o['source_ms'],cfg);self._save(c,'opportunities',old['opportunity_id'],old)
        if o['state']=='UNAVAILABLE':
            if old and old['state'] not in TERMINAL and old['state']!='UNAVAILABLE':
                old.update(state='UNAVAILABLE',reason=o['reason'],last_observed_ms=now,last_analysis_id=a.analysis_id)
                self._event(c,old,'UNAVAILABLE',o['reason'],a.analysis_id,None,cfg);self._save(c,'opportunities',old['opportunity_id'],old)
            return
        stream['last_source_ms']=o['source_ms']
        fp=fingerprint({'strategy':o['strategy'],'direction':o['direction']})
        if old and old['state'] not in TERMINAL and old.get('last_valid_state')=='CONFIRMED' and o['state']=='EARLY':
            o={**o,'state':'OBSERVING','reason':'existing_confirmation_rules_lost'}

        if o['state']=='OBSERVING':
            stream['rearmed']=True
            if old and old['state'] not in TERMINAL:
                old.update(state='INVALIDATED',reason='fresh_closed_analysis_no_longer_has_qualifying_condition',last_observed_ms=now,last_analysis_id=a.analysis_id)
                self._event(c,old,'INVALIDATED',old['reason'],a.analysis_id,o['source_ms'],cfg);self._save(c,'opportunities',old['opportunity_id'],old)
        else:
            if old and old['state'] not in TERMINAL and old['setup_fingerprint']!=fp:
                old.update(state='INVALIDATED',reason='fresh_strategy_or_direction_changed',last_observed_ms=now)
                self._event(c,old,'INVALIDATED',old['reason'],a.analysis_id,o['source_ms'],cfg);self._save(c,'opportunities',old['opportunity_id'],old);stream['rearmed']=True
            if not old or old['state'] in TERMINAL and stream['rearmed']:
                if len(self._rows(c,'opportunities',job['portfolio_id'],257))>=256:raise V2Error('DISCOVERY_LIMIT','Opportunity capacity reached; no history deleted',409)
                key=fingerprint({'stream':stream_key,'first_known':o['source_ms'],'source_analysis':a.analysis_id,'version':VERSION})
                old={'opportunity_id':key,'portfolio_id':job['portfolio_id'],'symbol':job['symbol'],'provider':job['provider'],'source':job['source'],'venue':job['venue'],'timeframe':job['timeframe'],'profile_id':job['profile_id'],'initial_analysis_id':a.analysis_id,'source_record_ids':refs,'first_known_ms':a.created_at_ms,'first_source_ms':o['source_ms'],'expires_at_ms':now+cfg['ttl_seconds']*1000,'state':None,'setup_fingerprint':fp,'modes':job['modes'],'trade_permission':False}
                stream.update(opportunity_id=key,rearmed=False)
            if old['state'] not in TERMINAL:
                previous=old['state'];recovered=previous=='UNAVAILABLE' and old.get('last_valid_state')==o['state'];old.update(state=o['state'],reason=o['reason'],last_analysis_id=a.analysis_id,last_observed_ms=now,last_source_ms=o['source_ms'],evidence=o['evidence'],missing=o['missing'],strategy_id=o['strategy'],direction=o['direction'],last_valid_state=o['state'],source_record_ids=refs,modes=sorted(set(old['modes'])|set(job['modes'])))
                if previous!=old['state']:self._event(c,old,old['state'],'source_recovered_no_new_market_confirmation' if recovered else o['reason'],a.analysis_id,o['source_ms'],cfg)
                self._save(c,'opportunities',old['opportunity_id'],old)
        self._save(c,'opportunity_streams',stream_key,stream)
    def _guard(self,c,owner,cfg,job=None):
        global_state=self.db.get(c,'discovery_runtime','global')
        current=self._config(c,cfg['portfolio_id'])
        if self.stopping or global_state['owner']!=owner or global_state['lease_until_ms']<=self.r.clock() or current!=cfg or not current['enabled']:
            raise V2Error('DISCOVERY_STALE_JOB','Scanner lease or configuration changed',409)
        if job and job['boundary_ms']!=self.r.clock()//TIMEFRAME_MS[job['timeframe']]*TIMEFRAME_MS[job['timeframe']]:raise V2Error('DISCOVERY_STALE_JOB','Old closed-bar job cannot be replayed',409)
    def _reserve(self):
        now=self.r.clock();key='provider-budget:'+fingerprint(self.r.analysis.provider.name)
        with self.db.transaction() as c:
            b=self.db.get(c,'discovery_runtime',key) or {'bucket':now//60000,'used':0}
            if b['bucket']!=now//60000:b={'bucket':now//60000,'used':0}
            if b['used']>=24:raise ProviderUnavailable('discovery_provider_minute_budget')
            b['used']+=1;self._save(c,'discovery_runtime',key,b)

    def _unavailable(self,c,job,cfg):
        for opp in self._rows(c,'opportunities',job['portfolio_id'],256):
            if opp['symbol']==job['symbol'] and opp['profile_id']==cfg['profile_id'] and opp['timeframe']==cfg['timeframe'] and opp['state'] not in TERMINAL and opp['state']!='UNAVAILABLE':
                opp.update(state='UNAVAILABLE',reason=job['reason'],last_observed_ms=self.r.clock())
                self._event(c,opp,'UNAVAILABLE',job['reason'],opp['last_analysis_id'],None,cfg);self._save(c,'opportunities',opp['opportunity_id'],opp)

    @decimal_context
    def tick(self,account=None):
        now=self.r.clock();owner=uuid4().hex;accounts=[account] if account else ['AUTO','MANUAL'];done=[];deadline=monotonic()+30
        with self.db.transaction() as c:
            g=self.db.get(c,'discovery_runtime','global')
            if g['last_tick_ms'] is not None and now<g['last_tick_ms']:return {'status':'clock_rollback','jobs':[]}
            if g['lease_until_ms']>now:return {'status':'busy','jobs':[]}
            configs=[self._config(c,a) for a in accounts];configs=[cfg for cfg in configs if cfg['enabled']]
            if not configs:return {'status':'disabled','jobs':[]}
            configs.sort(key=lambda cfg:(cfg['portfolio_id']!=('AUTO' if g['cursor']%2==0 else 'MANUAL')))
            g['recovered_leases']=g.get('recovered_leases',0)+int(bool(g['owner']))
            g.update(owner=owner,lease_until_ms=now+120000,last_tick_ms=now,heartbeat_ms=now,cursor=g['cursor']+1,shutdown='running');self._save(c,'discovery_runtime','global',g)
        provider=BudgetProvider(self.r.analysis.provider,deadline,self._reserve)
        service=AnalysisService(self.db,provider,self.r.ledger,self.r.clock);service.profiles=self.r.analysis.profiles
        try:
            for cfg in configs:
                if len(done)>=2 or monotonic()>deadline:break
                a=cfg['portfolio_id'];interval=cfg['interval_seconds']*1000
                with self.db.transaction() as c:
                    self._guard(c,owner,cfg);schedule=self._schedule(c,a)
                    if now<schedule['next_due_ms']:continue
                    schedule['missed_scans']+=max(0,(now-schedule['next_due_ms'])//interval) if schedule['next_due_ms'] else 0
                    schedule.update(last_attempt_ms=now,next_due_ms=now+interval,screened=0,eligible=0,last_error=None)
                    self._save(c,'discovery_runtime',a,schedule)
                    # Expiry independent of provider success; explicit TTL, not price failure.
                    for opp in self._rows(c,'opportunities',a,256):
                        if opp['state'] not in TERMINAL and now>=opp['expires_at_ms']:
                            opp.update(state='EXPIRED',reason='explicit_opportunity_TTL_elapsed',last_observed_ms=now)
                            self._event(c,opp,'EXPIRED',opp['reason'],opp['last_analysis_id'],None,cfg);self._save(c,'opportunities',opp['opportunity_id'],opp)
                    for row in c.execute("SELECT body,body_hash FROM discovery_jobs WHERE json_extract(body,'$.portfolio_id')=? AND json_extract(body,'$.status') IN ('pending','running') LIMIT 10",(a,)).fetchall():
                        stale=self.db.decode(row)
                        if stale['boundary_ms']!=now//TIMEFRAME_MS[stale['timeframe']]*TIMEFRAME_MS[stale['timeframe']] or stale.get('config_revision')!=cfg['revision']:
                            stale.update(status='skipped_stale',reason='boundary_or_revision_changed_no_historical_replay');self._save(c,'discovery_jobs',stale['job_id'],stale)
                    if c.execute("SELECT count(*) FROM discovery_jobs WHERE json_extract(body,'$.portfolio_id')=?",(a,)).fetchone()[0]>=10000:raise V2Error('DISCOVERY_LIMIT','Job capacity reached; archive review required',409)
                allowed=set(BUILTIN_IDS);frames=[]
                if cfg['profile_id']:
                    with self.db.transaction() as c:_,profile=self.r.analysis.profiles.get(c,a,cfg['profile_id'])
                    allowed=set(profile.strategy_ids);frames=[tf for tf in profile.timeframes if tf!=cfg['timeframe']]
                # Rotate discovery-only items; favorites always get first budget slot.
                other=[s for s in UNIVERSE if s not in cfg['favorites']]
                shift=(now//interval)%len(other) if other else 0;other=other[shift:]+other[:shift]
                symbols=list(cfg['favorites'])+(other if cfg['discovery'] else [])
                # Rotate favorite round-robin to prevent alphabetical starvation.
                if cfg['favorites']:
                    n=(now//interval)%len(cfg['favorites']);symbols=cfg['favorites'][n:]+cfg['favorites'][:n]+(other if cfg['discovery'] else [])
                if cfg['discovery'] and len(symbols)>1 and len(cfg['favorites'])>1:
                    symbols=[symbols[0]]+other[:1]+symbols[1:len(cfg['favorites'])]+other[1:]
                successes=0;failures=0;prepared=[]
                for symbol in symbols:
                    if monotonic()>deadline:break
                    boundary=now//TIMEFRAME_MS[cfg['timeframe']]*TIMEFRAME_MS[cfg['timeframe']]
                    key=fingerprint({'account':a,'symbol':symbol,'timeframe':cfg['timeframe'],'profile':cfg['profile_id'],'revision':cfg['revision'],'boundary':boundary,'version':VERSION,'provider':provider.name,'source':provider.source_name,'venue':provider.venue})
                    job={'job_id':key,'portfolio_id':a,'symbol':symbol,'timeframe':cfg['timeframe'],'profile_id':cfg['profile_id'],'config_revision':cfg['revision'],'provider':provider.name,'source':provider.source_name,'venue':provider.venue,'boundary_ms':boundary,'modes':['favorites'] if symbol in cfg['favorites'] else [],'status':'pending','last_attempt_ms':now,'last_success_ms':None,'analysis_id':None,'reason':'awaiting_validated_source','queued_at_ms':now}
                    queue_id=fingerprint({'account':a,'symbol':symbol})
                    try:
                        rules=provider.rules(symbol);bars=provider.candles(symbol,cfg['timeframe'],now)
                        q=validate_series(bars,timeframe_ms=TIMEFRAME_MS[cfg['timeframe']],as_of_ms=now,max_age_ms=TIMEFRAME_MS[cfg['timeframe']],min_bars=250)
                        if not q.ok or bars[-1].close_time_ms!=boundary or len(bars)>1024 or any(b.open_time_ms%TIMEFRAME_MS[cfg['timeframe']] or b.instrument.symbol!=symbol or b.instrument.venue!=provider.venue or b.instrument.contract_type!='spot' or b.instrument.price_kind!='last' or b.instrument.quote_currency!='USDT' or b.source!=provider.source_name or b.volume_kind!='real' for b in bars):raise ProviderUnavailable('discovery_closed_source_quality')
                        tick=Decimal(rules['price_tick'])
                        if not tick.is_finite() or tick<=0:raise ProviderUnavailable('invalid_instrument_tick')
                        schedule['eligible']+=1;schedule['screened']+=1;successes+=1
                        moving=abs(Decimal(str(bars[-1].close))-Decimal(str(bars[-2].close)))>=tick and bars[-1].volume is not None and bars[-1].volume>0
                        if cfg['discovery'] and moving:job['modes']=sorted(set(job['modes'])|{'discovery'})
                        job.update(reason='favorite_priority' if symbol in cfg['favorites'] else 'closed_change_at_least_verified_tick',source_ms=bars[-1].close_time_ms)
                        if not job['modes']:job.update(status='screened_out',reason='closed_change_below_verified_tick')
                    except Exception:
                        failures+=1;job.update(status='unavailable',reason='provider_or_source_unavailable',source_ms=None)
                    with self.db.transaction() as c:
                        self._guard(c,owner,cfg)
                        prior=self.db.get(c,'discovery_jobs',key)
                        if job['status']=='unavailable':self._unavailable(c,job,cfg)
                        if prior and prior['status'] not in ('running','pending'):
                            queue={**prior,'queued_at_ms':prior['last_attempt_ms']} if job['status']!='unavailable' else job
                        else:
                            if prior is None and c.execute("SELECT count(*) FROM discovery_jobs WHERE json_extract(body,'$.portfolio_id')=?",(a,)).fetchone()[0]>=10000:raise V2Error('DISCOVERY_LIMIT','Job capacity reached',409)
                            job['queued_at_ms']=prior.get('queued_at_ms',prior['last_attempt_ms']) if prior else now
                            queue=dict(job)
                            self._save(c,'discovery_jobs',key,job)
                            if job['status']=='pending':prepared.append(job)
                        self._save(c,'discovery_queue',queue_id,queue)
                for job in prepared:
                    if len(done)>=2 or monotonic()>deadline:break
                    key=job['job_id'];queue_id=fingerprint({'account':a,'symbol':job['symbol']})
                    with self.db.transaction() as c:
                        self._guard(c,owner,cfg,job);job['status']='running';self._save(c,'discovery_jobs',key,job)
                    try:
                        result=service.analyze(AnalyzeRequest(symbol=job['symbol'],timeframe=cfg['timeframe'],timeframes=frames,data_mode=self.db.mode,risk_portfolio=a,profile_id=cfg['profile_id'],auto_paper=False,idempotency_key='discovery:'+key),commit_guard=lambda c:self._guard(c,owner,cfg,job))
                        with self.db.transaction() as c:
                            self._guard(c,owner,cfg,job);self._apply(c,job,result,cfg,allowed)
                        job.update(status='completed' if result.quality.get('ok') else 'unavailable',analysis_id=result.analysis_id,last_success_ms=now if result.quality.get('ok') else None)
                    except V2Error as exc:
                        if exc.code=='DISCOVERY_STALE_JOB':raise
                        job.update(status='unavailable',reason=exc.code)
                        with self.db.transaction() as c:self._guard(c,owner,cfg);self._unavailable(c,job,cfg)
                    with self.db.transaction() as c:
                        self._guard(c,owner,cfg);self._save(c,'discovery_jobs',key,job);self._save(c,'discovery_queue',queue_id,dict(job))
                    done.append(job)
                if successes:
                    schedule.update(last_success_ms=now,failures=0,provider_status='partial' if failures else 'reachable')
                    if cfg['discovery']:schedule['last_discovery_ms']=now
                elif symbols:
                    schedule.update(failures=min(5,schedule['failures']+1),provider_status='circuit_open' if schedule['failures']>=2 else 'unavailable',last_error='provider_or_source_unavailable')
                    schedule['next_due_ms']=now+min(3600000,interval*2**schedule['failures'])
                with self.db.transaction() as c:
                    self._guard(c,owner,cfg);self._save(c,'discovery_runtime',a,schedule)
            return {'status':'completed','jobs':done,'provider_calls':provider.calls}
        except V2Error as exc:
            with self.db.transaction() as c:
                g=self.db.get(c,'discovery_runtime','global');g['last_error']=exc.code;self._save(c,'discovery_runtime','global',g)
            return {'status':'superseded' if exc.code=='DISCOVERY_STALE_JOB' else 'blocked','reason':exc.code,'jobs':done}
        finally:
            with self.db.transaction() as c:
                g=self.db.get(c,'discovery_runtime','global')
                if g['owner']==owner:g.update(owner=None,lease_until_ms=0,heartbeat_ms=self.r.clock(),shutdown='stopping' if self.stopping else 'idle');self._save(c,'discovery_runtime','global',g)
    def verify_events(self,account):
        previous='0'*64;count=0
        with self.db.transaction() as c:
            for row in c.execute("SELECT body,body_hash FROM opportunity_events WHERE json_extract(body,'$.portfolio_id')=? ORDER BY json_extract(body,'$.sequence') LIMIT 10001",(account,)):
                count+=1
                if count>10000:return {'status':'INCOMPLETE','events':count-1}
                event=self.db.decode(row)
                if event['portfolio_id']!=account or event['sequence']!=count or event['previous_hash']!=previous or fingerprint({k:v for k,v in event.items() if k!='event_hash'})!=event['event_hash']:
                    return {'status':'CORRUPT','events':count}
                previous=event['event_hash']
        return {'status':'PASS','events':count,'head_hash':previous,'signature_available':False}

    def start(self):
        if self.worker and self.worker.is_alive():raise ValueError('Worker already running')
        owner=uuid4().hex;now=self.r.clock()
        with self.db.transaction() as c:
            g=self.db.get(c,'discovery_runtime','global')
            if g.get('worker_owner') and g.get('worker_until_ms',0)>now:raise V2Error('DISCOVERY_STALE_JOB','An unattended worker lease is active',409)
            g.update(worker_owner=owner,worker_until_ms=now+120000,worker_heartbeat_ms=now,worker_stopping=False);self._save(c,'discovery_runtime','global',g)
        self.stopping=False;self.stop_event=threading.Event()
        def loop():
            try:
                while not self.stop_event.is_set():
                    with self.db.transaction() as c:
                        g=self.db.get(c,'discovery_runtime','global')
                        if g.get('worker_owner')!=owner:break
                        g.update(worker_until_ms=self.r.clock()+120000,worker_heartbeat_ms=self.r.clock());self._save(c,'discovery_runtime','global',g)
                    try:self.tick()
                    except Exception:
                        with self.db.transaction() as c:
                            g=self.db.get(c,'discovery_runtime','global');g['shutdown']='worker_error';self._save(c,'discovery_runtime','global',g)
                    self.stop_event.wait(5)
            finally:
                with self.db.transaction() as c:
                    g=self.db.get(c,'discovery_runtime','global')
                    if g.get('worker_owner')==owner:g.update(worker_owner=None,worker_until_ms=0,worker_stopping=False,shutdown='stopped');self._save(c,'discovery_runtime','global',g)
                # This also runs when stop()'s bounded join returned before a
                # slow provider call. No in-flight worker tick remains here.
                self.stopping=False
        self.worker=threading.Thread(target=loop,name='v2-discovery',daemon=True);self.worker.start()
    def stop(self):
        self.stopping=True
        if self.worker and self.worker.is_alive():
            with self.db.transaction() as c:
                g=self.db.get(c,'discovery_runtime','global');g['worker_stopping']=True;self._save(c,'discovery_runtime','global',g)
            self.stop_event.set();self.worker.join(timeout=2)
            if not self.worker.is_alive():self.stopping=False
        else:self.stopping=False
