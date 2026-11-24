"""Narrow, causal chart definitions; price geometry is not institutional flow.

Flags/pennants: 10-bar efficient pole >=3% and >=4 prior-ATR, then eight bars
inside an endpoint envelope with <=50% retrace. Flag parallel slopes oppose pole;
pennant converges. Two subsequent closed bars beyond projected edge confirm.
Necklines use unchanged V1 strict 3-left/3-right pivots, never backdate a cross.
"""
from dataclasses import asdict
from decimal import Decimal as D,Context,localcontext,ROUND_HALF_EVEN
from market_ai.engines.chart_patterns import _pivots
from .product_db import fingerprint
VERSION='v2-chart-confirmations-1'

def confirmations(bars,timeframe,tick):
    with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
        h,l,c=([D(str(getattr(b,k))) for b in bars] for k in ('high','low','close'))
        events=[]
        def add(name,direction,formed,known,confirmed,explanation,**fields):
            identity={'pattern_id':name,'pattern_version':VERSION,'direction':direction,'formed_at':bars[formed].close_time_ms,'known_at':bars[known].close_time_ms,'confirmed_at':bars[confirmed].close_time_ms if confirmed is not None else None,'timeframe':timeframe,'source':bars[0].source,'instrument':asdict(bars[0].instrument),**fields}
            prefix=[[b.open_time_ms,b.close_time_ms,*[str(getattr(b,k)) for k in ('open','high','low','close')]] for b in bars[:known+1]]
            stable={k:v for k,v in identity.items() if k!='confirmed_at'}
            stable['source_prefix_hash']=fingerprint(prefix)
            events.append({**identity,'event_id':fingerprint(stable),'source_prefix_hash':stable['source_prefix_hash'],'trade_permission':False,'kind':'causal_geometry_research','explanation':explanation})
        for end in range(max(40,len(bars)-12),len(bars)):
            start,pole_end=end-18,end-8;cons=pole_end+1;move=c[pole_end]-c[start]
            ranges=[max(h[j]-l[j],abs(h[j]-c[j-1]),abs(l[j]-c[j-1])) for j in range(start-14,start)]
            atr=sum(ranges)/14;size=abs(move)
            path=sum(abs(c[j]-c[j-1]) for j in range(start+1,pole_end+1))
            if size<max(c[start]*D('.03'),atr*4) or path<=0 or size/path<D('.7'):continue
            up=move>0;hs=(h[end]-h[cons])/7;ls=(l[end]-l[cons])/7;width=h[cons]-l[cons];last_width=h[end]-l[end]
            if width<=tick*2 or last_width<=tick*2:continue
            if up and (min(l[cons:end+1])<c[pole_end]-size/2 or max(h[cons:end+1])>c[pole_end]+size*D('.2')):continue
            if not up and (max(h[cons:end+1])>c[pole_end]+size/2 or min(l[cons:end+1])<c[pole_end]-size*D('.2')):continue
            if any(h[j]>h[cons]+hs*(j-cons)+tick or l[j]<l[cons]+ls*(j-cons)-tick for j in range(cons,end+1)):continue
            parallel=abs(hs-ls)*7<=width*D('.2') and width*D('.75')<=last_width<=width*D('1.25')
            flag=parallel and (hs<0 and ls<0 if up else hs>0 and ls>0)
            pennant=hs<0<ls and last_width<=width*D('.6')
            if not flag and not pennant:continue
            name=('bull_' if up else 'bear_')+('flag' if flag else 'pennant')
            def edge(j):return (h[cons]+hs*(j-cons)) if up else (l[cons]+ls*(j-cons))
            crossed=lambda j:c[j]>edge(j)+tick if up else c[j]<edge(j)-tick
            confirm=None
            for j in range(end+2,min(end+5,len(bars))):
                if crossed(j-1) and crossed(j):confirm=j;break
            add(name,'bullish' if up else 'bearish',end,end,confirm,'10-bar efficient pole then eight closed consolidation bars; projected envelope and two closed edge breaks. Heuristic continuation candidate, not validated strategy.',pole_bars=10,consolidation_bars=8,envelope_high=format(h[end],'f'),envelope_low=format(l[end],'f'))
            first_cross=next((j for j in range(end+1,min(end+4,len(bars))) if crossed(j)),None)
            if first_cross is not None:
                failure=next((j for j in range(first_cross+1,min(first_cross+4,len(bars))) if (c[j]<edge(j)-tick if up else c[j]>edge(j)+tick)),None)
                if failure is not None:
                    add('failed_'+('flag' if flag else 'pennant')+'_breakout','bearish' if up else 'bullish',end,failure,failure,'Closed breakout returned through projected consolidation edge within3 bars; failure observation, no executable signal.')
            if confirm is not None:
                for j in range(confirm+1,min(confirm+4,len(bars))):
                    touch=abs((l[j] if up else h[j])-edge(j))<=tick
                    if touch and crossed(j):
                        add(('flag' if flag else 'pennant')+'_retest','bullish' if up else 'bearish',end,j,j,'After two-close confirmation, real wick retested the projected boundary within one tick and close remained outside.');break
        hi,lo=_pivots([float(x) for x in h],[float(x) for x in l])
        for points,up in ((hi,False),(lo,True)):
            for n in (2,3):
                if len(points)<n:continue
                indices=[j for j,_ in points[-n:]];first,last=indices[0],indices[-1]
                if any(b-a<6 for a,b in zip(indices,indices[1:])):continue
                values=[l[j] if up else h[j] for j in indices]
                if n==2:
                    if abs(values[0]-values[1])/values[1]>=D('.02'):continue
                    name='double_bottom_neckline' if up else 'double_top_neckline'
                else:
                    if not (values[1]<min(values[0],values[2]) if up else values[1]>max(values[0],values[2])) or abs(values[0]-values[2])/values[1]>=D('.03'):continue
                    name='inverse_head_and_shoulders_neckline' if up else 'head_and_shoulders_neckline'
                neck=[]
                for a,b in zip(indices,indices[1:]):
                    k=max(range(a+1,b),key=lambda j:h[j]) if up else min(range(a+1,b),key=lambda j:l[j])
                    neck.append((k,h[k] if up else l[k]))
                known=max(last+3,39)
                if known>=len(bars):continue
                slope=(neck[-1][1]-neck[0][1])/(neck[-1][0]-neck[0][0]) if len(neck)>1 else D(0)
                level=lambda j:neck[0][1]+slope*(j-neck[0][0])
                confirm=next((j for j in range(known+1,len(bars)) if (c[j-1]<=level(j-1)+tick and c[j]>level(j)+tick if up else c[j-1]>=level(j-1)-tick and c[j]<level(j)-tick)),None)
                add(name,'bullish' if up else 'bearish',last,known,confirm,'Strict V1 3-left/3-right pivots; intervening opposite extremes define neckline. First tick-buffered closed cross AFTER structure became knowable; no backdated execution.',neckline_at_known=format(level(known),'f'),neckline_slope_per_bar=format(slope,'f'))
        return events
