"""Real V2 geometry plus one separately versioned missing candle variant."""
from market_ai.v2.pattern_research import detect_patterns,CATALOG as CANDLE_CATALOG
from market_ai.v2.chart_research import detect_charts,CATALOG as CHART_CATALOG
from forex.structure import market_structure
from .technical import ohlc
from .candle_extensions import detect as extended_candles,FAMILIES as EXTRA_CANDLES
from .chart_geometry import detect as geometric_charts,FAMILIES as GEOMETRIC_CHARTS
from .structure_events import analyze as structure_lifecycle,tolerance_at

MINIMUM={'engulfing':2,'harami':2,'tweezer':2,'inside_bar':2,'outside_bar':2,
         'morning':3,'evening':3,'soldiers':3,'crows':3,'hikkake':3,'three_inside':3,
         'three_outside':3,'tasuki':3,'abandoned':3,'concealing':4,'ladder':5,
         'mat_hold':5,'three_methods':5,'kicking':2,'matching':2,'counterattack':2,
         'piercing':2,'dark_cloud':2}


def modified_hikkake(frame):
    """Engineering variant, not a claim of TA-Lib equivalence.

    Mother + strict inside + conditioned nested-inside + false break. A bullish
    conditioned bar closes in its bottom quartile; mirror for bearish. Confirm
    beyond the first inside extreme within three later closed bars; then expire.
    """
    bars=frame.bars;out=[]
    for i in range(max(3,len(bars)-7),len(bars)):
        a,b,c,d=bars[i-3:i+1]
        if not (a.low<b.low<b.high<a.high and b.low<c.low<c.high<b.high):continue
        up=c.close<=c.low+(c.high-c.low)*.25 and d.high<c.high and d.low<c.low
        down=c.close>=c.high-(c.high-c.low)*.25 and d.high>c.high and d.low>c.low
        if up==down:continue
        confirmation=next((x.close_time_ms for x in bars[i+1:i+4]
                           if (x.close>b.high if up else x.close<b.low)),None)
        out.append({'pattern_id':'modified_hikkake','pattern_version':'fx-modified-hikkake-1',
                    'direction':'bullish' if up else 'bearish','formed_at':d.close_time_ms,
                    'first_known_at':d.close_time_ms,'confirmed_at':confirmation,
                    'minimum_candles':4,'confirmation_rule':'within3_close_beyond_first_inside_extreme',
                    'price_range':{'low':d.low,'high':d.high},'invalidation':d.low if up else d.high,
                    'age_bars':len(bars)-1-i,'strength':0,
                    'quality_status':'confirmation_expired' if confirmation is None and len(bars)-1-i>=3 else 'valid_closed_snapshot',
                    'trade_permission':False,'timeframe':frame.timeframe})
    return out


def analyze(frame,metrics,tick):
    candles=detect_patterns(frame.bars,tick_size=tick,**frame.kwargs())
    charts=detect_charts(frame.bars,tick_size=tick,**frame.kwargs())
    by_close={b.close_time_ms:i for i,b in enumerate(frame.bars)}
    for pattern in candles['patterns']:
        minimum=max((count for name,count in MINIMUM.items() if name in pattern['pattern_id']),default=1)
        i=by_close[pattern['formed_at']];rows=frame.bars[max(0,i-minimum+1):i+1]
        low,high=min(b.low for b in rows),max(b.high for b in rows)
        pattern.update(minimum_candles=minimum,first_known_at=pattern['formed_at'],price_range={'low':low,'high':high},
                       invalidation=low if pattern['direction']=='bullish' else high if pattern['direction']=='bearish' else None,
                       invalidation_policy='closed price beyond OHLC formation extreme; geometric heuristic')
    candles['patterns']+=modified_hikkake(frame)
    candles['patterns']+=extended_candles(frame,tick)
    candles['missing_families']=[name for name,item in CANDLE_CATALOG.items() if item['status']=='MISSING' and name!='hikkake_modified' and name not in EXTRA_CANDLES]
    candles['catalog_overrides']={'hikkake_modified':'modified_hikkake / fx-modified-hikkake-1 engineering variant'}
    candles['catalog_overrides'].update({name:'fx-candle-catalog-v7-1 DESCRIPTIVE' for name in EXTRA_CANDLES})
    for pattern in candles['patterns']:
        pattern.setdefault('role','DESCRIPTIVE')
        pattern.setdefault('state','CONFIRMED' if pattern.get('confirmed_at') else 'CANDIDATE')
        pattern.setdefault('trade_permission',False)
    for pattern in charts['patterns']:
        pattern.update(minimum_candles=40,first_known_at=pattern['known_at'],
                       invalidation=pattern.get('level'),
                       invalidation_status='observed_range_level' if 'level' in pattern else 'UNAVAILABLE_STRUCTURAL_GEOMETRY_PARTIAL')
    charts['missing_families']=[name for name,status in CHART_CATALOG.items() if status=='MISSING']
    charts['geometric_patterns']=geometric_charts(frame,tick)
    charts['geometry_catalog']={name:'DESCRIPTIVE_ENGINEERING' for name in GEOMETRIC_CHARTS}
    charts['missing_families']=[]
    charts['validation_status']='PARTIAL_FAMILY_VALIDATION'
    from .pattern_lab import evidence
    candles['validation_metadata']=[evidence(p,'retained_V2_or_versioned_FX_geometry') for p in candles['patterns']]
    charts['validation_metadata']=[evidence(p,'retained_V2_pivots_and_slope') for p in charts['geometric_patterns']]
    return candles,charts


def structure(frame,metrics,price_action,tick,ledger=None):
    old=market_structure(ohlc(frame),timeframe_seconds=frame.duration_ms//1000)
    indices={b.close_time_ms//1000:i for i,b in enumerate(frame.bars)}
    zones=[]
    for label,key in (('support','last_low'),('resistance','last_high')):
        pivot=old.get(key)
        tolerance=tolerance_at(frame,indices[pivot['confirmed_at']],tick) if pivot else tick
        if pivot:zones.append({'kind':label,'low':pivot['price']-tolerance,'high':pivot['price']+tolerance,
                               'first_known_at':pivot['confirmed_at'],'rule_version':'fx-pivot-zone-v1',
                               'invalidation':'closed price beyond far zone edge','institutional_order_claim':False})
    # Reuse V5 confirmed pivot extraction; expose equality from explicitly
    # confirmed historical levels rather than treating current extrema as pivots.
    equal=[]
    for label,key in (('equal_highs','highs'),('equal_lows','lows')):
        pivots=old.get(key,[])
        tolerance=tolerance_at(frame,indices[pivots[-1]['confirmed_at']],tick) if pivots else tick
        if len(pivots)>=2 and abs(pivots[-1]['price']-pivots[-2]['price'])<=tolerance:
            equal.append({'kind':label,'price_range':{'low':min(p['price'] for p in pivots[-2:]),'high':max(p['price'] for p in pivots[-2:])},
                          'first_known_at':max(p['confirmed_at'] for p in pivots[-2:]),'invalidation_distance':tolerance,
                          'rule_version':'fx-confirmed-equality-v1'})
    from .structure_ledger import StructureLedger
    fvg=(ledger if ledger is not None else StructureLedger()).consume(frame,tick)
    return {'v5_pivots':old,'price_action':price_action,'zones':zones,'equal_levels':equal,'fvg_history':fvg,
            'lifecycle':structure_lifecycle(frame,price_action,tick,metrics['atr14']),
            'heuristic_only':True,'rule_version':'fx-structure-context-v6-1'}
