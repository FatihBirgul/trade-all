"""Enriched provenance and strict veto around the actual V2 evidence reducer."""
from dataclasses import dataclass,asdict
from math import isfinite
from market_ai.engines.confluence import Evidence,build_confluence

VERSION='fx-provenance-confluence-v8-1'


@dataclass(frozen=True)
class Observation:
    source:str
    event_id:str
    category:str
    direction:str
    strength:float
    confirmed:bool
    age_bars:int
    timeframe:str
    known_at:int
    algorithm_version:str
    bucket:str='ohlc_price'
    confirmation_at:int|None=None
    related_event_id:str|None=None
    state:str='CONFIRMED'
    expires_at:int|None=None
    def __post_init__(self):
        if self.category not in ('trend','momentum','structure','pattern','mtf','volatility','news','volume'):
            raise ValueError('Unsupported evidence category')
        if (not self.source or not self.event_id or type(self.known_at) is not int or self.known_at<0
                or not self.algorithm_version or not self.bucket):raise ValueError('Invalid observation provenance')
        Evidence(self.source,self.direction,self.strength,self.timeframe,self.age_bars,self.confirmed,self.bucket)
        if self.state not in ('CANDIDATE','CONFIRMED','INVALIDATED','EXPIRED'):raise ValueError('Invalid evidence state')
        for stamp in (self.confirmation_at,self.expires_at):
            if stamp is not None and (type(stamp) is not int or stamp<self.known_at):raise ValueError('Invalid evidence timestamp')
        if self.related_event_id is not None and (not isinstance(self.related_event_id,str) or not 1<=len(self.related_event_id)<=200):raise ValueError('Invalid related event identity')


def combine(observations,*,as_of,max_age_bars=3):
    if type(as_of) is not int or as_of<0 or type(max_age_bars) is not int or not 0<=max_age_bars<=100:raise ValueError('Invalid evidence as-of/age policy')
    if len(observations)>1000:raise ValueError('Evidence budget exceeded')
    valid=[];rejected=[]
    for item in observations:
        reason=None
        if item.known_at>as_of or not item.confirmed or (item.confirmation_at is not None and item.confirmation_at>as_of):
            reason='future_or_unconfirmed'
        elif item.state!='CONFIRMED':reason='invalidated_or_expired'
        elif item.age_bars>max_age_bars or (item.expires_at is not None and item.expires_at<=as_of):reason='stale_or_expired'
        if reason:
            rejected.append({'event_id':item.event_id,'source':item.source,'reason':reason,'observation':asdict(item)});continue
        valid.append(item)
    # Event identity wins over a caller-supplied bucket name. Correlated OHLC
    # categories share a single price bucket even when source labels differ.
    unique={}
    authoritative=('trend','momentum','structure')
    for item in sorted(valid,key=lambda e:(e.related_event_id or e.event_id,e.direction,e.category not in authoritative,-e.strength,e.source)):
        key=(item.related_event_id or item.event_id,item.direction)
        unique.setdefault(key,item)
    directional=[e for e in valid if e.category in authoritative and e.direction!='neutral']
    directions={e.direction for e in directional}
    converted=[]
    for item in unique.values():
        context=item.category in ('mtf','volatility','news','volume','pattern')
        bucket='ohlc_price' if item.category in ('trend','momentum','structure','pattern') else item.bucket
        converted.append(Evidence(item.source,'neutral' if context else item.direction,
                                  0 if context else item.strength,item.timeframe,item.age_bars,item.confirmed,bucket))
    summary=build_confluence(converted)
    return {**summary,'version':VERSION,'source_engine':'trade-ai-v2-confluence',
            'input_observation_count':len(observations),'duplicate_events_removed':len(valid)-len(unique),
            'input_observations':[asdict(e) for e in valid],
            'event_deduplicated_count':len(unique),'observations':[asdict(e) for e in unique.values()],
            'rejected_events':sorted({r['event_id'] for r in rejected}),'rejections':rejected,'conflict_veto':len(directions)>1,
            'directional_context':sorted(directions),
            'conflicting_directions':sorted(directions) if len(directions)>1 else [],
            'success_probability':None,'score_semantics':'versioned heuristic evidence strength, not calibrated probability'}
