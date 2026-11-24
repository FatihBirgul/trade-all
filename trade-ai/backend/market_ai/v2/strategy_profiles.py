"""Whitelisted research profiles, never an alternative trading/risk authority."""
from dataclasses import dataclass, fields, field
from hashlib import sha256
from itertools import islice
import json
import re
from .strategies import STRATEGIES, BUILTIN_IDS
from .technical_adapter import TIMEFRAME_MS
from .decision_record import _canonical
from market_ai.engines.confluence import CORRELATION_BUCKETS

LEGACY_METHODS=frozenset(('ema20','ema50','rsi14','macd','macd_hist','atr14'))
ADDITIONAL_METHODS=frozenset(('roc12','stochastic14','donchian20_previous','bollinger_bandwidth20','adx14_wilder','supertrend10_3'))
REGIMES=frozenset(('trend','range','breakout','reversal'))

def valid_hash(x):return isinstance(x,str) and re.fullmatch('[a-f0-9]{64}',x) is not None

@dataclass(frozen=True)
class StrategyProfile:
    _versions:tuple=field(init=False,repr=False)
    schema_version:int=1
    revision:int=1
    parent_id:str|None=None
    strategy_ids:tuple[str,...]=tuple(sorted(BUILTIN_IDS))
    required_methods:tuple[str,...]=('roc12',)
    allowed_regimes:tuple[str,...]=tuple(sorted(REGIMES))
    bias_timeframe:str='1m'
    setup_timeframe:str='1m'
    trigger_timeframe:str='1m'
    minimum_confirmations:int=2
    analysis_every_bars:int=10

    def __post_init__(self):
        if (type(self.schema_version) is not int or self.schema_version!=1 or type(self.revision) is not int or not 1<=self.revision<=10000
                or (self.revision==1 and self.parent_id is not None) or (self.revision>1 and not valid_hash(self.parent_id))
                or type(self.strategy_ids) is not tuple or not self.strategy_ids or len(set(self.strategy_ids))!=len(self.strategy_ids)
                or not set(self.strategy_ids)<=BUILTIN_IDS or type(self.required_methods) is not tuple
                or len(set(self.required_methods))!=len(self.required_methods) or not set(self.required_methods)<=LEGACY_METHODS|ADDITIONAL_METHODS
                or type(self.allowed_regimes) is not tuple or not self.allowed_regimes or len(set(self.allowed_regimes))!=len(self.allowed_regimes)
                or not set(self.allowed_regimes)<=REGIMES or type(self.minimum_confirmations) is not int or not 2<=self.minimum_confirmations<=5
                or type(self.analysis_every_bars) is not int or not 1<=self.analysis_every_bars<=1000
                or any(t not in TIMEFRAME_MS for t in (self.bias_timeframe,self.setup_timeframe,self.trigger_timeframe))):
            raise ValueError('Invalid whitelisted strategy profile')
        ranks=[TIMEFRAME_MS[t] for t in (self.bias_timeframe,self.setup_timeframe,self.trigger_timeframe)]
        if not (ranks[0]==ranks[1]==ranks[2] or ranks[0]>ranks[1]>ranks[2]):
            raise ValueError('Use one frame or strict bias > setup > trigger roles')
        for s in STRATEGIES:
            if s.strategy_id in self.strategy_ids and not s.regimes.intersection(self.allowed_regimes):
                raise ValueError('Selected strategy contradicts allowed regimes')
        for key in ('strategy_ids','required_methods','allowed_regimes'):
            object.__setattr__(self,key,tuple(sorted(getattr(self,key))))
        object.__setattr__(self,'_versions',tuple(sorted((s.strategy_id,s.version) for s in STRATEGIES if s.strategy_id in self.strategy_ids)))

    def body(self):
        return {**{f.name:getattr(self,f.name) for f in fields(self) if f.init},'strategy_versions':dict(self._versions)}

    @property
    def profile_id(self):return sha256(_canonical(self.body()).encode()).hexdigest()

    @property
    def timeframes(self):return tuple(sorted({self.bias_timeframe,self.setup_timeframe,self.trigger_timeframe},key=TIMEFRAME_MS.get))

    @classmethod
    def from_dict(cls,body):
        names={f.name for f in fields(cls) if f.init}
        if not isinstance(body,dict) or set(body)!=names|{'strategy_versions'}:raise ValueError('Unsupported profile fields')
        values={k:v for k,v in body.items() if k!='strategy_versions'}
        for key in ('strategy_ids','required_methods','allowed_regimes'):
            if not isinstance(values[key],(list,tuple)):raise ValueError('Profile list required')
            values[key]=tuple(values[key])
        p=cls(**values)
        if body['strategy_versions']!=p.body()['strategy_versions']:raise ValueError('Unsupported strategy version')
        return p


def evaluate_profile(profile,analysis,additional):
    if not isinstance(profile,StrategyProfile):raise ValueError('Validated profile required')
    def result(passes,reason):return {'profile_id':profile.profile_id,'passes':passes,'reason':reason,'trade_permission':False,'scope':'additional_research_filter_only'}
    if analysis.get('direction') not in ('bullish','bearish') or analysis.get('quality',{}).get('ok') is not True:
        return result(False,'analysis_wait_or_bad_quality')
    if analysis.get('risk',{}).get('status')!='eligible_for_paper':return result(False,'existing_risk_gate')
    if analysis.get('router',{}).get('strategy_id') not in profile.strategy_ids:return result(False,'strategy_not_selected')
    selected=analysis['router']['strategy_id']
    if analysis.get('strategy_setups',{}).get(selected,{}).get('version')!=dict(profile._versions)[selected]:return result(False,'strategy_version_missing_or_mismatch')
    if analysis.get('regime',{}).get('regime') not in profile.allowed_regimes:return result(False,'regime_not_selected')
    for name in profile.required_methods:
        if name in LEGACY_METHODS:
            from .research import number
            try:number(analysis.get('indicators',{}).get(name))
            except ValueError:return result(False,'required_indicator_unavailable')
        elif additional.get('methods',{}).get(name,{}).get('status')!='available':return result(False,'required_indicator_unavailable')
    buckets=set()
    for e in analysis.get('supporting_evidence',[]):
        if e.get('confirmed') is True and e.get('direction',analysis['direction'])==analysis['direction']:
            bucket=e.get('bucket') or CORRELATION_BUCKETS.get(e.get('source'))
            if bucket:buckets.add(CORRELATION_BUCKETS.get(bucket,bucket))
    if len(buckets)<profile.minimum_confirmations:return result(False,'distinct_confirmations_missing')
    return result(True,'existing_analysis_and_profile_filter_pass')


def validate_history(profiles):
    rows=tuple(islice(profiles,65))
    if not rows or len(rows)>64 or any(not isinstance(p,StrategyProfile) for p in rows):raise ValueError('Bounded profile history required')
    if rows[0].revision!=1:raise ValueError('History must start at first revision')
    for previous,current in zip(rows,rows[1:]):
        if current.revision!=previous.revision+1 or current.parent_id!=previous.profile_id:raise ValueError('Broken profile revision chain')
    return 'PASS'


def load_profile(path):
    from pathlib import Path
    path=Path(path)
    if not path.is_file():raise ValueError('Existing bounded profile JSON required')
    with path.open('r',encoding='utf-8') as f:raw=f.read(65537)
    if len(raw)>65536:raise ValueError('Profile budget exceeded')
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate profile JSON key')
            result[k]=v
        return result
    return StrategyProfile.from_dict(json.loads(raw,object_pairs_hook=unique))
