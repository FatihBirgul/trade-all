"""Offline pattern QA contracts. Diagnostic rates are never market false-positive rates."""
from math import isfinite
from collections import Counter
from random import Random
from dataclasses import replace
from market_ai.v2.market_data_contract import validate_series

VERSION='fx-pattern-validation-v8-1'


def valid_frame(frame,tick,minimum):
    if isinstance(tick,bool) or not isinstance(tick,(int,float)) or not isfinite(tick) or tick<=0:raise ValueError('Positive finite pattern tick required')
    if len(frame.bars)>256:raise ValueError('Pattern input exceeds256 bars')
    return validate_series(frame.bars,timeframe_ms=frame.duration_ms,as_of_ms=frame.as_of_ms,
        max_age_ms=frame.duration_ms*2,min_bars=minimum,permitted_gaps=frame.permitted_gaps).ok


def evidence(pattern,source):
    return {'pattern_id':pattern['pattern_id'],'algorithm_version':pattern['pattern_version'],
        'required_bars':pattern.get('minimum_candles',40),'required_pivots':pattern.get('minimum_pivot_count',0),
        'minimum_tick_tolerance':'explicit instrument tick; rule-specific multiplier',
        'first_known_at':pattern.get('first_known_at',pattern.get('known_at',pattern['formed_at'])),
        'confirmation_at':pattern.get('confirmed_at'),'expiration_at':pattern.get('expired_at'),
        'invalidation_at':pattern.get('invalidated_at'),'state':pattern.get('state','CANDIDATE'),
        'false_positive_classification':'UNLABELLED_ENGINEERING_DETECTION',
        'confidence_semantics':'descriptive heuristic, no calibrated win probability',
        'source_evidence':source,'test_status':'IMPLEMENTED_UNVERIFIED_IN_MARKET',
        'directional_permission':False}


def randomized_report(frame,*,seed=816,paths=12):
    if type(seed) is not int or not 0<=seed<=2**32-1 or type(paths) is not int or not 1<=paths<=50:raise ValueError('Bounded pattern lab required')
    from .candle_extensions import detect as candles
    from .chart_geometry import detect as charts
    from market_ai.v2.pattern_research import detect_patterns
    rng=Random(seed);counts=Counter();occurrences=Counter()
    for _ in range(paths):
        price=100;rows=[]
        for b in frame.bars:
            op=price;price=max(20,op+rng.gauss(0,.5));wick=.05+rng.random()*.5
            rows.append(replace(b,open=op,high=max(op,price)+wick,low=min(op,price)-wick,close=price))
        sample=replace(frame,bars=tuple(rows));events=charts(sample,.01)+candles(sample,.01)+detect_patterns(sample.bars,tick_size=.01,**sample.kwargs())['patterns']
        for p in events:occurrences[p['pattern_id']]+=1
        for name in {p['pattern_id'] for p in events}:counts[name]+=1
    return dict(version=VERSION,seed=seed,paths=paths,data_kind='SYNTHETIC_TEST',
        metric='fraction_of_unlabelled_random_paths_with_detection',
        detection_rates={k:counts[k]/paths for k in sorted(counts)},occurrences=dict(sorted(occurrences.items())),
        market_false_positive_rate=None,warning='Random walks are unlabelled engineering diagnostics; not market precision or predictive probability.')
