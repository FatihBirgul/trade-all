"""Closed-candle research adapter. Detection is not a trade signal.

Reuses the existing legacy taxonomy; adds only absent families. Definitions are
our versioned engineering rules, not a claim of TA-Lib numerical equivalence.
No TA-Lib dependency, provider I/O, API mutation or automatic order permission.
"""
from decimal import Decimal as D, Context, localcontext, ROUND_HALF_EVEN
import re
from itertools import islice
from market_ai.engines import candlestick, confluence
from .market_data_contract import validate_series
from .technical_adapter import TIMEFRAME_MS

VERSION = 'v2-pattern-research-2'
LEGACY_NAMES = ('Doji','Long-legged Doji','Dragonfly Doji','Gravestone Doji','Hammer',
    'Hanging Man','Inverted Hammer','Shooting Star','Marubozu','Spinning Top',
    'Bullish Engulfing','Bearish Engulfing','Bullish Harami','Bearish Harami',
    'Piercing Line','Dark Cloud Cover','Tweezer Top','Tweezer Bottom','Inside Bar',
    'Outside Bar','Morning Star','Evening Star','Three White Soldiers','Three Black Crows')
def slug(name):return re.sub('[^a-z0-9]+','_',name.lower()).strip('_')
NEW_FAMILIES = ('harami_cross','three_inside','three_outside','kicking','abandoned_baby',
    'tasuki_gap','matching_low','matching_high','counterattack','rising_three_methods',
    'falling_three_methods','morning_doji_star','evening_doji_star','long_line','short_line',
    'hikkake','ladder_bottom','ladder_top','mat_hold','concealing_baby_swallow')
CATALOG = {**{slug(n):{'status':'IMPLEMENTED','engine':'legacy_candlestick'} for n in LEGACY_NAMES},
           **{n:{'status':'IMPLEMENTED','engine':VERSION} for n in NEW_FAMILIES},
           **{n:{'status':'MISSING','engine':None} for n in ('hikkake_modified','three_stars_in_south','unique_three_river','separating_lines',
               'on_neck','in_neck','thrusting','advance_block','stalled_pattern','tristar','breakaway')}}

def _text(x):return format(D(0) if x==0 else x,'f')

def detect_patterns(candles, *, timeframe, as_of_ms, max_age_ms, tick_size, permitted_gaps=()):
    """Reject invalid batches; no future-bar filtering to manufacture good QC.

    At most 4096 supplied bars and six recent formations are examined. Context
    uses the prefix preceding formation, never later confirmation bars. A latest
    formation normally awaits the NEXT closed directional bar. Three-inside/
    outside, doji-star, abandoned-baby and methods already contain confirmation.
    """
    bars=tuple(islice(candles,4097))
    if len(bars)>4096:raise ValueError('Pattern input exceeds 4096 bars')
    if timeframe not in TIMEFRAME_MS:raise ValueError('Unsupported timeframe')
    if isinstance(tick_size,bool):raise ValueError('Invalid price tick')
    tick=D(str(tick_size))
    if not tick.is_finite() or tick<=0:raise ValueError('Invalid price tick')
    quality=validate_series(bars,timeframe_ms=TIMEFRAME_MS[timeframe],as_of_ms=as_of_ms,max_age_ms=max_age_ms,min_bars=25,permitted_gaps=permitted_gaps)
    result={'version':VERSION,'status':'unavailable','quality_status':'invalid_data',
            'issues':[i.code for i in quality.issues], 'validation_status':'DETECTION_IMPLEMENTED',
            'trade_permission':False,'patterns':[],'timeframe':timeframe,'as_of_ms':as_of_ms}
    if not quality.ok:return result
    with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
        raw=[{k:float(getattr(b,k)) if getattr(b,k) is not None else None for k in ('open','high','low','close','volume')} for b in bars]
        legacy=candlestick.detect(raw)
        rows=[(slug(p['name']),p['name'],p['classification'],p['location'],p['base_strength'],p['explanation'],False) for p in legacy]
        o,h,l,c=([D(str(getattr(b,k))) for b in bars] for k in ('open','high','low','close'))
        body=[abs(x-y) for x,y in zip(o,c)];span=[x-y for x,y in zip(h,l)]
        bull=lambda i:c[i]>o[i]
        doji=lambda i:span[i]>0 and body[i]<=span[i]*D('.1')
        full=lambda i:span[i]>0 and body[i]>=span[i]*D('.92')
        inside=lambda a,b:min(o[a],c[a])<min(o[b],c[b])<=max(o[b],c[b])<max(o[a],c[a])
        engulf=lambda a,b:min(o[b],c[b])<min(o[a],c[a])<max(o[a],c[a])<max(o[b],c[b])
        def add(family,direction,i,rule,intrinsic=False):rows.append((family,family.replace('_',' ').title(),direction,i,55,rule,intrinsic))
        for i in range(max(20,len(bars)-6),len(bars)):
            a,b=i-1,i
            average=sum(body[i-20:i])/20
            # Hikkake: strict inside bar then lower-high/lower-low false break
            # (bullish), mirrored for bearish. Confirmation may take three bars.
            a,b,d=i-2,i-1,i
            if h[b]<h[a] and l[b]>l[a]:
                if h[d]<h[b] and l[d]<l[b]:add('hikkake','bullish',i,'Inside bar, false downside break; close above inside high within next3 bars.')
                elif h[d]>h[b] and l[d]>l[b]:add('hikkake','bearish',i,'Inside bar, false upside break; close below inside low within next3 bars.')
            a,b,d,e=i-3,i-2,i-1,i
            if (not bull(a) and not bull(b) and full(a) and full(b) and not bull(d) and not bull(e)
                    and o[d]<c[b] and h[d]>c[b] and o[e]>h[d] and c[e]<l[d]):
                add('concealing_baby_swallow','bullish',i,'Two bearish >=92% bodies, downside body gap with upper reclaim, then bearish engulfing; next close must exceed formation high.')
            a,b,d,e,f=i-4,i-3,i-2,i-1,i
            for up in (True,False):
                direction='bullish' if up else 'bearish'
                descending=(o[a]>o[b]>o[d] and c[a]>c[b]>c[d]) if up else (o[a]<o[b]<o[d] and c[a]<c[b]<c[d])
                wick=h[e]-max(o[e],c[e]) if up else min(o[e],c[e])-l[e]
                turn=(o[f]>o[e] and c[f]>h[e]) if up else (o[f]<o[e] and c[f]<l[e])
                if (all(bull(j)!=up and body[j]>average for j in (a,b,d)) and descending
                        and bull(e)!=up and body[e]>0 and wick>=2*body[e] and bull(f)==up and turn):
                    add('ladder_bottom' if up else 'ladder_top',direction,i,'Three progressing opposite bodies, exhaustion wick, final reversal beyond fourth extreme.',True)
                midpoint=(o[a]+c[a])/2
                gap=o[b]>c[a] if up else o[b]<c[a]
                held=all(l[j]>midpoint for j in (b,d,e)) if up else all(h[j]<midpoint for j in (b,d,e))
                resumed=(c[f]>max(h[a:f]) and o[f]>c[e]) if up else (c[f]<min(l[a:f]) and o[f]<c[e])
                if (bull(a)==up and body[a]>average and bull(b)!=up and gap and held
                        and all(body[j]<body[a]/2 for j in (b,d,e)) and bull(f)==up and resumed):
                    add('mat_hold',direction,i,'Long body, body-gapped pullback, three small bodies holding initial midpoint, continuation beyond prior extremes.',True)
            a,b=i-1,i
            if span[i]>0 and body[i]>=average*D('1.5') and body[i]>=span[i]*D('.6'):
                add('long_line','neutral',i,'Body >=1.5x prior20 mean and >=60% range; context only.')
            if average>0 and body[i]<=average*D('.5') and not doji(i):
                add('short_line','neutral',i,'Body <=0.5x prior20 mean; context only.')
            if body[a]>average and doji(b) and inside(a,b):add('harami_cross','bearish' if bull(a) else 'bullish',i,'Doji body strictly inside prior long real body.')
            if not bull(a) and not bull(b) and abs(c[a]-c[b])<=tick and o[b]>c[a]:add('matching_low','bullish',i,'Two bearish closes within one instrument tick.')
            if bull(a) and bull(b) and abs(c[a]-c[b])<=tick and o[b]<c[a]:add('matching_high','bearish',i,'Mirrored matching closes within one tick.')
            if bull(a)!=bull(b) and body[a]>average and abs(c[a]-c[b])<=tick and ((not bull(a) and o[b]<c[a]) or (bull(a) and o[b]>c[a])):
                add('counterattack','bullish' if bull(b) else 'bearish',i,'Opposite body opens beyond prior close and returns within one tick.')
            if full(a) and full(b) and bull(a)!=bull(b) and ((bull(b) and l[b]>h[a]) or (not bull(b) and h[b]<l[a])):
                add('kicking','bullish' if bull(b) else 'bearish',i,'Opposite >=92% bodies with full shadow gap.')
            a,b,d=i-2,i-1,i
            if body[a]>average and inside(a,b) and bull(a)!=bull(b) and bull(b)==bull(d) and ((bull(d) and c[d]>o[a]) or (not bull(d) and c[d]<o[a])):
                add('three_inside','bullish' if bull(d) else 'bearish',i,'Harami plus third close beyond first open.',True)
            if engulf(a,b) and bull(a)!=bull(b) and bull(b)==bull(d) and ((bull(d) and c[d]>c[b]) or (not bull(d) and c[d]<c[b])):
                add('three_outside','bullish' if bull(d) else 'bearish',i,'Engulfing plus third close beyond engulfing close.',True)
            if body[a]>average and doji(b) and bull(a)!=bull(d):
                up=not bull(a) and bull(d)
                body_gap=max(o[b],c[b])<min(o[a],c[a]) if up else min(o[b],c[b])>max(o[a],c[a])
                midpoint=(o[a]+c[a])/2
                if body_gap and ((up and c[d]>midpoint) or (not up and c[d]<midpoint)):
                    add('morning_doji_star' if up else 'evening_doji_star','bullish' if up else 'bearish',i,'Long body, body-gapped doji, third close beyond first midpoint.',True)
                full_gap=(h[b]<l[a] and h[b]<l[d]) if up else (l[b]>h[a] and l[b]>h[d])
                if full_gap and ((up and c[d]>midpoint) or (not up and c[d]<midpoint)):
                    add('abandoned_baby','bullish' if up else 'bearish',i,'Doji separated by full shadow gaps on both sides; midpoint recovery.',True)
            if bull(a)==bull(b) and bull(b)!=bull(d):
                up=bull(a)
                gap=l[b]>h[a] if up else h[b]<l[a]
                retrace=(min(o[b],c[b])<o[d]<max(o[b],c[b]) and h[a]<c[d]<l[b]) if up else (min(o[b],c[b])<o[d]<max(o[b],c[b]) and h[b]<c[d]<l[a])
                if gap and retrace:add('tasuki_gap','bullish' if up else 'bearish',i,'Same-direction pair with full gap; opposite body leaves gap partially open.')
            a=i-4
            if body[a]>average and bull(a)==bull(i) and all(l[a]<l[j] and h[j]<h[a] and body[j]<body[a] for j in range(a+1,i)):
                up=bull(a)
                if all(bull(j)!=up for j in range(a+1,i)) and ((up and c[i]>h[a]) or (not up and c[i]<l[a])):
                    add('rising_three_methods' if up else 'falling_three_methods','bullish' if up else 'bearish',i,'Long body, three opposite contained candles, continuation beyond initial extreme.',True)
        seen=set()
        for family,name,direction,i,strength,explanation,intrinsic in sorted(rows,key=lambda x:(x[3],x[0])):
            key=(family,i)
            if key in seen:continue
            seen.add(key)
            confirmed=i if intrinsic else None
            if family=='hikkake':
                for j in range(i+1,min(i+4,len(bars))):
                    if (direction=='bullish' and c[j]>h[i-1]) or (direction=='bearish' and c[j]<l[i-1]):confirmed=j;break
            elif family=='concealing_baby_swallow':
                if i+1<len(bars) and bull(i+1) and c[i+1]>h[i]:confirmed=i+1
            elif not intrinsic and i+1<len(bars):
                if direction=='neutral' or (direction=='bullish' and c[i+1]>c[i] and bull(i+1)) or (direction=='bearish' and c[i+1]<c[i] and not bull(i+1)):confirmed=i+1
            prior=bars[max(0,i-20):i]
            pc=[D(str(b.close)) for b in prior]
            trend='up' if pc[-1]>pc[0]*D('1.01') else 'down' if pc[-1]<pc[0]*D('.99') else 'flat'
            tr=[max(D(str(x.high))-D(str(x.low)),abs(D(str(x.high))-D(str(y.close))),abs(D(str(x.low))-D(str(y.close)))) for y,x in zip(prior,prior[1:])]
            atr=sum(tr[-14:])/len(tr[-14:])
            vol={'status':'unavailable'}
            if len(prior)>=20 and all(x.volume_kind=='real' for x in (*prior,bars[i])):
                mean=sum(D(str(x.volume)) for x in prior)/len(prior)
                if mean>0:vol={'status':'available','ratio':_text(D(str(bars[i].volume))/mean),'confirmed':D(str(bars[i].volume))>=mean*D('1.5')}
            result['patterns'].append({'pattern_id':family,'pattern_version':VERSION if family in NEW_FAMILIES else 'legacy-candle-adapter-1',
                'family':family,'name':name,'direction':direction,'formed_at':bars[i].close_time_ms,
                'confirmed_at':bars[confirmed].close_time_ms if confirmed is not None else None,
                'timeframe':timeframe,'age_bars':len(bars)-1-i,'market_regime':'not_evaluated',
                'trend_context':trend,'support_resistance_context':{'status':'available','prior_low':_text(min(D(str(x.low)) for x in prior)),'prior_high':_text(max(D(str(x.high)) for x in prior))},
                'volatility_context':{'status':'available','prior_atr14_sma':_text(atr)},'volume_confirmation':vol,
                'quality_status':'confirmation_expired' if family=='hikkake' and confirmed is None and len(bars)-1-i>=3 else 'valid_closed_snapshot','strength':strength,'explanation':explanation,
                'confirmation_rule':'next3_close_beyond_inside_extreme' if family=='hikkake' else 'next_close_above_formation_high' if family=='concealing_baby_swallow' else 'intrinsic_closed_formation' if intrinsic else 'next_directional_closed_bar'})
        result.update(status='available',quality_status='valid_closed_snapshot')
    return result


def confluence_evidence(snapshot):
    """Research-only evidence adapter, ONE shared candlestick bucket.

    No direction/BUY/SELL is selected here. Existing confluence performs bucket
    dedup and conflict abstention; no additional composite contribution.
    """
    if snapshot.get('status')!='available':return []
    return [confluence.Evidence(source='candlestick',direction=p['direction'],strength=p['strength'],
        timeframe=p['timeframe'],age_bars=p['age_bars'],confirmed=True,
        bucket=confluence.CORRELATION_BUCKETS['candlestick']) for p in snapshot['patterns']
        if p['confirmed_at'] is not None and p['age_bars']<=3 and p['direction'] in ('bullish','bearish')]
