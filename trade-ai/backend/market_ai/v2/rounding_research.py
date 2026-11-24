"""Narrow three-stage rounding candidates, not universal chart classification.

Fixed30closed-bar window:10 directional decline,10 flat base,10 recovery (mirror
for top). >=8/9 side moves, center range<=25% total height, endpoints within20%,
height>=4preceding14ATR and10ticks. Two NEW closed neckline crosses confirm;
12bar horizon; later close beyond formation wick extreme invalidates. No trade.
"""
from decimal import Decimal as D,Context,localcontext,ROUND_HALF_EVEN
from dataclasses import asdict
from .product_db import fingerprint
VERSION='v2-three-stage-rounding-1'
def rounding(bars,timeframe,tick):
 if len(bars)<60:return []
 with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
  h,l,c=([D(str(getattr(b,k))) for b in bars] for k in ('high','low','close'));events=[]
  for end in range(max(59,len(bars)-12),len(bars)):
   start=end-29;values=c[start:end+1];height=max(values)-min(values)
   atr=sum(max(h[j]-l[j],abs(h[j]-c[j-1]),abs(l[j]-c[j-1])) for j in range(start-14,start))/14
   if height<max(atr*4,tick*10) or abs(values[0]-values[-1])>height/5:continue
   first=(values[9]-values[0])/9;middle=(values[19]-values[10])/9;last=(values[29]-values[20])/9
   if max(values[10:20])-min(values[10:20])>height/4 or abs(middle)>min(abs(first),abs(last))/4:continue
   if max(h[j]-l[j] for j in range(start,end+1))>height/2:continue
   for bottom in (True,False):
    if not (first<0<last if bottom else first>0>last):continue
    if sum(values[j]<values[j-1] if bottom else values[j]>values[j-1] for j in range(1,10))<8:continue
    if sum(values[j]>values[j-1] if bottom else values[j]<values[j-1] for j in range(21,30))<8:continue
    level=max(values[0],values[-1]) if bottom else min(values[0],values[-1]);invalid=min(l[start:end+1]) if bottom else max(h[start:end+1])
    cross=lambda j:c[j]>level+tick if bottom else c[j]<level-tick
    horizon=min(end+13,len(bars));confirmed=next((j for j in range(end+2,horizon) if cross(j-1) and cross(j)),None)
    invalidated=next((j for j in range(end+1,horizon) if (c[j]<invalid if bottom else c[j]>invalid)),None)
    if invalidated is not None and confirmed is not None and invalidated<confirmed:confirmed=None
    name='rounding_bottom_geometry' if bottom else 'rounding_top_geometry'
    identity={'version':VERSION,'name':name,'instrument':asdict(bars[0].instrument),'source':bars[0].source,'prefix':[[b.open_time_ms,*[str(getattr(b,k)) for k in ('open','high','low','close')]] for b in bars[:end+1]]}
    events.append({'event_id':fingerprint(identity),'pattern_id':name,'pattern_version':VERSION,'direction':('bullish' if bottom else 'bearish') if confirmed is not None else 'neutral','candidate_bias':'bullish' if bottom else 'bearish','formation_start_at':bars[start].open_time_ms,'formed_at':bars[end].close_time_ms,'known_at':bars[end].close_time_ms,'confirmed_at':bars[confirmed].close_time_ms if confirmed is not None else None,'invalidated_at':bars[invalidated].close_time_ms if invalidated is not None else None,'neckline':format(level,'f'),'invalidation_level':format(invalid,'f'),'quality_status':'invalidated' if invalidated is not None else 'confirmed' if confirmed is not None else 'expired' if len(bars)-1-end>=12 else 'awaiting_confirmation','minimum_closed_bars':60,'timeframe':timeframe,'trade_permission':False,'explanation':'Fixed30-bar three-stage rounding geometry with low-variance10-bar base and directional sides. Needs two later closed neckline crosses. Narrow heuristic definition, not universal pattern recognition or a validated strategy.'})
  return events
