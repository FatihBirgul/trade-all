"""Versioned three-touch boundary geometry, not executable orders.

Unchanged V1 strict3left/3right pivots. Three touches on EACH side, endpoint
lines, middle-contact tolerance=max(tick,25% mean candle range); all formation
bars contained. Compressing width<=65%: flat-sided/symmetric triangles or same-
direction wedges. Parallel width80..120%: rectangle/channel. Confirmation needs
TWO closed crosses after right-pivot knowledge, within12bars and before lines
cross. Failure/retest observations are separate events, never backdated.
"""
from dataclasses import asdict
from decimal import Decimal as D,Context,localcontext,ROUND_HALF_EVEN
from market_ai.engines.chart_patterns import _pivots
from .product_db import fingerprint
VERSION='v2-pivot-boundaries-1'
def boundaries(bars,timeframe,tick):
 with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
  h,l,c=([D(str(getattr(b,k))) for b in bars] for k in ('high','low','close'));events={}
  for end in range(max(39,len(bars)-16),len(bars)):
   hi,lo=_pivots([float(x) for x in h[:end+1]],[float(x) for x in l[:end+1]])
   hi=[i for i,_ in hi if i>=end-60][-3:];lo=[i for i,_ in lo if i>=end-60][-3:]
   if len(hi)<3 or len(lo)<3:continue
   start=min(hi[0],lo[0]);formed=max(hi[-1],lo[-1]);known=max(39,formed+3);span=formed-start
   if span<12:continue
   hs=(h[hi[-1]]-h[hi[0]])/(hi[-1]-hi[0]);ls=(l[lo[-1]]-l[lo[0]])/(lo[-1]-lo[0])
   upper=lambda j:h[hi[0]]+hs*(j-hi[0]);lower=lambda j:l[lo[0]]+ls*(j-lo[0])
   tol=max(tick,sum(h[j]-l[j] for j in range(start,formed+1))/D(span+1)/4)
   if abs(h[hi[1]]-upper(hi[1]))>tol or abs(l[lo[1]]-lower(lo[1]))>tol:continue
   if any(h[j]>upper(j)+tol or l[j]<lower(j)-tol for j in range(start,formed+1)):continue
   width0,width1=upper(start)-lower(start),upper(formed)-lower(formed)
   if min(width0,width1)<=2*tick:continue
   flat_h=abs(hs)*span<=tol;flat_l=abs(ls)*span<=tol;name=None
   if width1<=width0*D('.65'):
    if flat_h and ls>0:name='ascending_triangle'
    elif flat_l and hs<0:name='descending_triangle'
    elif hs<0<ls:name='symmetrical_triangle'
    elif 0<hs<ls:name='rising_wedge'
    elif hs<ls<0:name='falling_wedge'
   elif abs(hs-ls)*span<=tol and width0*D('.8')<=width1<=width0*D('1.2'):
    if flat_h and flat_l:name='rectangle'
    elif hs>0 and ls>0:name='rising_channel'
    elif hs<0 and ls<0:name='falling_channel'
   if name is None:continue
   def cross(j):
    if upper(j)<=lower(j):return None
    return 'bullish' if c[j]>upper(j)+tick else 'bearish' if c[j]<lower(j)-tick else None
   horizon=min(known+13,len(bars));confirmed=None;first=None;direction='neutral'
   for j in range(known+1,horizon):
    side=cross(j)
    if side and first is None:first=(j,side)
    if j>known+1 and side and side==cross(j-1):confirmed=j;direction=side;break
   failure=None;retest=None
   if first:
    j,side=first;edge=upper if side=='bullish' else lower
    failure=next((k for k in range(j+1,min(j+4,len(bars),known+13)) if (c[k]<edge(k)-tick if side=='bullish' else c[k]>edge(k)+tick)),None)
   if confirmed is not None and (failure is None or failure>confirmed):
    edge=upper if direction=='bullish' else lower
    retest=next((j for j in range(confirmed+1,min(confirmed+4,len(bars),known+13)) if abs((l[j] if direction=='bullish' else h[j])-edge(j))<=tick and cross(j)==direction),None)
   else:confirmed=None;direction='neutral'
   prior=c[start-1]-c[max(0,start-11)] if start else D(0)
   trend='bullish' if prior>tick else 'bearish' if prior<-tick else 'neutral'
   interpretation='unresolved' if direction=='neutral' or trend=='neutral' else 'continuation' if direction==trend else 'reversal'
   source=fingerprint([[b.open_time_ms,*[str(getattr(b,k)) for k in ('open','high','low','close')]] for b in bars[:known+1]])
   identity={'version':VERSION,'instrument':asdict(bars[0].instrument),'source':bars[0].source,'source_prefix_hash':source,'family':name,'start':bars[start].open_time_ms,'formed':bars[formed].close_time_ms}
   key=fingerprint(identity)
   record={'event_id':key,'pattern_id':name+'_boundary','pattern_version':VERSION,'kind':'three_touch_boundary_research','direction':direction,'formation_start_at':bars[start].open_time_ms,'formed_at':bars[formed].close_time_ms,'known_at':bars[known].close_time_ms,'confirmed_at':bars[confirmed].close_time_ms if confirmed is not None else None,'invalidated_at':bars[failure].close_time_ms if failure is not None else None,'quality_status':'invalidated' if failure is not None else 'confirmed' if confirmed is not None else 'expired' if len(bars)-1-known>=12 else 'awaiting_confirmation','interpretation':interpretation,'prior_trend':trend,'timeframe':timeframe,'trade_permission':False,'source_prefix_hash':source,'minimum_closed_bars':40,'upper_at_known':format(upper(known),'f'),'lower_at_known':format(lower(known),'f'),'explanation':'Three confirmed pivot contacts per boundary; endpoint geometry, fixed tolerance and two closed crosses AFTER pivot knowledge. Wedge continuation/reversal follows actual break vs prior closed trend. No execution/probability claim.'}
   events[key]=record
   for kind,index in (('failure',failure),('retest',retest)):
    if index is not None:
     event={**record,'event_id':fingerprint({'parent':key,'kind':kind,'at':bars[index].close_time_ms}),'pattern_id':name+'_boundary_'+kind,'known_at':bars[index].close_time_ms,'confirmed_at':bars[index].close_time_ms,'quality_status':kind,'direction':('bearish' if first[1]=='bullish' else 'bullish') if kind=='failure' else direction}
     events[event['event_id']]=event
  return list(events.values())
