"""Immutable, account-scoped product profiles; only narrow existing decisions.

The local backend bearer is administrative. Mobile ownership and an explicit
profiles:write grant are enforced by the Gateway, never inferred from paper scope.
"""
from typing import Literal
from pydantic import Field, model_validator
from .api_models import Model
from .strategy_profiles import StrategyProfile, LEGACY_METHODS, ADDITIONAL_METHODS, REGIMES, evaluate_profile
from .strategies import STRATEGIES
from .technical_adapter import TIMEFRAME_MS
from .product_db import fingerprint
from .errors import V2Error
from . import domain_journal as domain

class ProfileSelection(Model):
    strategy_ids: list[str] = Field(default_factory=lambda:list(StrategyProfile().strategy_ids), max_length=4)
    required_methods: list[str] = Field(default_factory=lambda:['roc12'], max_length=12)
    allowed_regimes: list[str] = Field(default_factory=lambda:sorted(REGIMES), max_length=4)
    bias_timeframe: str = '1m'
    setup_timeframe: str = '1m'
    trigger_timeframe: str = '1m'
    minimum_confirmations: int = Field(2, strict=True, ge=2, le=5)
    analysis_every_bars: int = Field(10, strict=True, ge=1, le=1000)

    def profile(self, **revision):
        values=self.model_dump()
        for k in ('strategy_ids','required_methods','allowed_regimes'):values[k]=tuple(values[k])
        return StrategyProfile(**values,**revision)

    @model_validator(mode='after')
    def check_profile(self):
        self.profile()
        return self

class ProfileWrite(Model):
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r'^[a-zA-Z0-9_.:-]+$')
    selection: ProfileSelection = Field(default_factory=ProfileSelection)

class ProfileRecord(Model):
    profile_id: str
    portfolio_id: Literal['AUTO','MANUAL']
    group_id: str
    revision: int
    parent_id: str | None
    content_id: str
    created_at_ms: int
    selection: ProfileSelection
    strategy_versions: dict[str,str]
    scope: Literal['restrict_existing_analysis_only'] = 'restrict_existing_analysis_only'
    trade_permission: Literal[False] = False

class ProfileEvaluationRequest(Model):
    analysis_id: str = Field(pattern=r'^[a-f0-9]{64}$')

class ProfileEvaluation(Model):
    profile_id: str
    analysis_id: str
    portfolio_id: Literal['AUTO','MANUAL']
    passes: bool
    reason: str
    trade_permission: Literal[False] = False
    scope: str

class ProfileStore:
    def __init__(self,db,clock):
        self.db,self.clock=db,clock
        with db.transaction() as c:
            c.execute('CREATE TABLE IF NOT EXISTS strategy_profiles(id TEXT PRIMARY KEY, portfolio TEXT NOT NULL, group_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, body_hash TEXT NOT NULL, UNIQUE(portfolio,group_id,revision))')
            c.execute('CREATE INDEX IF NOT EXISTS strategy_profile_account ON strategy_profiles(portfolio,group_id,revision)')
            for op in ('UPDATE','DELETE'):
                c.execute(f"CREATE TRIGGER IF NOT EXISTS strategy_profiles_{op.lower()} BEFORE {op} ON strategy_profiles BEGIN SELECT RAISE(ABORT,'immutable strategy profile'); END")
            domain.attach(c)

    def get(self,c,account,key):
        row=self.db.get(c,'strategy_profiles',key)
        if row is None or row['portfolio_id']!=account:
            raise V2Error('PROFILE_NOT_FOUND','Profile not found for this account',404)
        record=ProfileRecord.model_validate(row)
        parent=self.db.get(c,'strategy_profiles',record.parent_id) if record.parent_id is not None else None
        if record.parent_id is not None and (parent is None or parent['portfolio_id']!=account or parent['group_id']!=record.group_id or parent['revision']+1!=record.revision):
            raise V2Error('STORAGE_CORRUPT','Broken profile revision chain',503)
        profile=record.selection.profile(revision=record.revision,parent_id=parent['content_id'] if parent else None)
        if record.content_id!=profile.profile_id or record.strategy_versions!=dict(profile._versions):
            raise V2Error('PROFILE_VERSION_UNAVAILABLE','Profile version is no longer supported',409)
        return row,profile

    def write(self,account,request,parent_id=None):
        with self.db.transaction() as c:
            profile=request.selection.profile()
            args={'portfolio_id':account,'profile_digest':profile.profile_id,'parent_id':parent_id}
            scope='profile:'+account
            prior=self.db.command(c,scope,request.idempotency_key,args)
            if prior is not None:return prior
            parent=None
            if parent_id:
                parent,old=self.get(c,account,parent_id)
                if c.execute('SELECT MAX(revision) FROM strategy_profiles WHERE portfolio=? AND group_id=?',(account,parent['group_id'])).fetchone()[0]!=parent['revision']:
                    raise V2Error('PROFILE_REVISION_CONFLICT','Revise the latest profile revision')
                if parent['revision']>=64:raise V2Error('PROFILE_HISTORY_LIMIT','At most 64 revisions per profile')
                profile=request.selection.profile(revision=parent['revision']+1,parent_id=old.profile_id)
            key=fingerprint({'portfolio':account,'key':request.idempotency_key,'profile':profile.profile_id,'parent':parent_id})
            record=ProfileRecord(profile_id=key,portfolio_id=account,group_id=parent['group_id'] if parent else key,
                revision=profile.revision,parent_id=parent_id,content_id=profile.profile_id,created_at_ms=self.clock(),
                selection=request.selection,strategy_versions=dict(profile._versions)).model_dump(mode='json')
            self.db.put(c,'strategy_profiles',key,record,portfolio=account,group_id=record['group_id'],revision=profile.revision)
            self.db.remember(c,scope,request.idempotency_key,args,record)
            return record

    @staticmethod
    def evaluate(profile,analysis):
        # Exactly the same research filter, no alternative routing or risk override.
        context=analysis.get('technical_methods',{}).get('research_context',{})
        if analysis.get('timeframe') != profile.setup_timeframe or not set(profile.timeframes).issubset(analysis.get('timeframes',[])):
            return {'profile_id':profile.profile_id,'passes':False,'reason':'profile_timeframes_missing','trade_permission':False,'scope':'additional_research_filter_only'}
        return evaluate_profile(profile,analysis,context.get('methods',{}))


def capabilities():
    return {'version':'v2-product-profiles-1','scope':'restrict_existing_analysis_only','trade_permission':False,
        'strategies':[{'strategy_id':s.strategy_id,'version':s.version,'regimes':sorted(s.regimes)} for s in STRATEGIES],
        'methods':[{'method_id':name,'parameters':'fixed_in_method_id','tunable':False} for name in sorted(LEGACY_METHODS|ADDITIONAL_METHODS)],
        'regimes':sorted(REGIMES),'timeframes':list(TIMEFRAME_MS),'maximum_revisions':64,
        'minimum_confirmations':{'minimum':2,'maximum':5},'analysis_every_bars':{'minimum':1,'maximum':1000,'automatic_scheduling':False}}
