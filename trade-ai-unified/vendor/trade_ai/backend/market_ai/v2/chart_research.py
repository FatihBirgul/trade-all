"""Bounded causal adapter for V1 structural candidates plus explicit range events.

Legacy structural confidence is heuristic, not a probability. Flags/pennants are
not implemented. This research interface is not added to automatic trade gates.
"""
from decimal import Decimal as D, Context, localcontext, ROUND_HALF_EVEN
from itertools import islice
from market_ai.engines import chart_patterns as legacy
from .market_data_contract import validate_series
from .technical_adapter import TIMEFRAME_MS
from .pattern_research import slug

VERSION='v2-chart-research-1'
STRUCTURAL={'Double Top','Double Bottom','Head and Shoulders','Inverse Head and Shoulders',
    'Ascending Triangle','Descending Triangle','Symmetrical Triangle','Rising Wedge','Falling Wedge','Channel','Rectangle'}
CATALOG={**{slug(n):'STRUCTURAL_CANDIDATE' for n in STRUCTURAL},
         **{n:'IMPLEMENTED' for n in ('range_breakout','range_retest','failed_range_breakout')},
         **{n:'MISSING' for n in ('flag','pennant','rounding_bottom','rounding_top')}}


def detect_charts(candles,*,timeframe,as_of_ms,max_age_ms,tick_size,permitted_gaps=()):
    bars=tuple(islice(candles,257))
    if len(bars)>256 or timeframe not in TIMEFRAME_MS:raise ValueError('Supported chart frame, at most256bars required')
    if isinstance(tick_size,bool):raise ValueError('Invalid chart tick')
    tick=D(str(tick_size))
    if not tick.is_finite() or tick<=0:raise ValueError('Positive finite tick required')
    q=validate_series(bars,timeframe_ms=TIMEFRAME_MS[timeframe],as_of_ms=as_of_ms,max_age_ms=max_age_ms,min_bars=40,permitted_gaps=permitted_gaps)
    result={'version':VERSION,'status':'unavailable','issues':[i.code for i in q.issues],'patterns':[],
            'trade_permission':False,'knowledge_scope':'first_observed_in_supplied_window_after40bar_warmup'}
    if not q.ok:return result
    if any(b.open_time_ms%TIMEFRAME_MS[timeframe] for b in bars):result['issues'].append('timeframe_alignment');return result
    raw=[{k:float(getattr(b,k)) for k in ('open','high','low','close')} for b in bars]
    try:
        # The legacy public wrapper swallows errors as []; use its unchanged
        # core to distinguish calculation failure from absence of a pattern.
        current=legacy._detect(raw)
        wanted={(p['name'],p['location']) for p in current if p['name'] in STRUCTURAL}
        first={};confirmed={}
        for n in range(40,len(bars)+1):
            for p in legacy._detect(raw[:n]):
                key=(p['name'],p['location'])
                if key in wanted:
                    first.setdefault(key,n-1)
                    if p['confirmed']:confirmed.setdefault(key,n-1)
        for p in current:
            key=(p['name'],p['location'])
            if p['name'] not in STRUCTURAL:continue
            i=p['location'];known=first[key];confirmation=confirmed.get(key)
            result['patterns'].append({'pattern_id':slug(p['name']),'pattern_version':VERSION,'kind':'structural_candidate',
                'direction':p['classification'],'formed_at':bars[i].close_time_ms,'known_at':bars[known].close_time_ms,
                'confirmed_at':bars[confirmation].close_time_ms if confirmation is not None else None,
                'timeframe':timeframe,'trade_permission':False,'explanation':p['explanation'],
                'confirmation_scope':'structural_right_pivots_and_observed_price_condition; no neckline execution claim'})
    except Exception:
        result['patterns']=[];result['issues'].append('legacy_chart_engine_unavailable');return result
    with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
        h,l,c=([D(str(getattr(b,k))) for b in bars] for k in ('high','low','close'))
        def event(name,direction,formed,known,level,confirmed=None):
            return {'pattern_id':name,'pattern_version':VERSION,'kind':'closed_range_event','direction':direction,
                'formed_at':bars[formed].close_time_ms,'known_at':bars[known].close_time_ms,
                'confirmed_at':bars[confirmed].close_time_ms if confirmed is not None else None,
                'level':format(level,'f'),'timeframe':timeframe,'trade_permission':False,
                'explanation':'Previous20-bar range, strict tick-buffered break; next closed confirmation and at most3bar retest/failure observation.'}
        for i in range(max(20,len(bars)-6),len(bars)):
            top,bottom=max(h[i-20:i]),min(l[i-20:i])
            direction='bullish' if c[i]>top+tick and c[i-1]<=top else 'bearish' if c[i]<bottom-tick and c[i-1]>=bottom else None
            if direction is None:continue
            up=direction=='bullish';level=top if up else bottom;confirmed=None
            if i+1<len(bars) and (c[i+1]>level if up else c[i+1]<level):confirmed=i+1
            result['patterns'].append(event('range_breakout',direction,i,i,level,confirmed))
            retested=False
            for j in range(i+1,min(i+4,len(bars))):
                failure=c[j]<level if up else c[j]>level
                if failure:
                    result['patterns'].append(event('failed_range_breakout','bearish' if up else 'bullish',i,j,level,j));break
                touch=level-tick<=l[j]<=level+tick if up else level-tick<=h[j]<=level+tick
                if touch and confirmed is not None and not retested:
                    result['patterns'].append(event('range_retest',direction,i,j,level,j));retested=True
    result['patterns'].sort(key=lambda p:(p['known_at'],p['pattern_id'],p['formed_at']))
    result['status']='available'
    return result
