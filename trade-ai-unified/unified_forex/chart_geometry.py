"""Bounded V2 pivot/trendline extension with causal geometry and lifecycle.

All thresholds refer to pattern width/tick, not nominal instrument price. A pivot
needs three right closes, matching the retained V2 chart engine. Shape recognition
is DESCRIPTIVE; only two later closes beyond a frozen boundary confirm breakout.
"""
from hashlib import sha256
import numpy as np
from market_ai.engines.chart_patterns import _pivots, _slope

VERSION='fx-chart-geometry-v7-1'
FAMILIES=('bull_flag','bear_flag','pennant','ascending_triangle','descending_triangle',
          'symmetrical_triangle','rounding_bottom','rounding_top','rectangle','channel',
          'rising_wedge','falling_wedge','double_top','double_bottom',
          'head_and_shoulders','inverse_head_and_shoulders')


def candidates(bars,highs,lows,tick):
    """Pure geometry at one causal cutoff; pivot indices already confirmed."""
    out=[];n=len(bars)
    def add(family,points,upper,lower,bias='neutral',extra=None):
        if upper(n-1)-lower(n-1)<=2*tick:return
        out.append(dict(family=family,pivot_indices=tuple(sorted({p[0] for p in points})),
                        upper=upper,lower=lower,bias=bias,extra=extra or {}))
    def line(points):
        slope=_slope(points);intercept=sum(v-slope*i for i,v in points)/len(points)
        return lambda i:intercept+slope*i
    if len(highs)>=3 and len(lows)>=3:
        hp,lp=highs[-3:],lows[-3:];u,d=line(hp),line(lp)
        start=min(hp[0][0],lp[0][0]);end=max(hp[-1][0],lp[-1][0]);duration=end-start
        width=u(start)-d(start);latest=u(end)-d(end)
        if duration>=8 and width>10*tick and latest>2*tick:
            tol=max(tick,width*.08);hs=_slope(hp);ls=_slope(lp)
            fit=all(abs(p-u(i))<=tol for i,p in hp) and all(abs(p-d(i))<=tol for i,p in lp)
            contained=all(d(i)-tol<=b.low<=b.high<=u(i)+tol for i,b in enumerate(bars[start:end+1],start))
            flat=tol/duration;converges=.2*width<latest<.8*width
            family=None
            if fit and contained:
                if abs(hs)<=flat and ls>flat and converges:family='ascending_triangle'
                elif hs<-flat and abs(ls)<=flat and converges:family='descending_triangle'
                elif hs<-flat and ls>flat and converges:family='symmetrical_triangle'
                elif hs>flat and ls>hs+flat and converges:family='rising_wedge'
                elif hs<-flat and ls>hs+flat and ls<-flat and converges:family='falling_wedge'
                elif abs(hs)<=flat and abs(ls)<=flat:family='rectangle'
                elif abs(hs-ls)<=flat and abs(hs)>flat:family='channel'
                if family:add(family,hp+lp,u,d,extra={'slopes':[hs,ls],'duration_bars':duration,'tolerance':tol})
                # A genuine pole precedes consolidation; random range alone is
                # never a flag/pennant. Pole uses only earlier closed prices.
                if start>=8 and duration<=36:
                    pole=bars[start-1].close-bars[start-8].close
                    atr=sum(b.high-b.low for b in bars[start-8:start])/8
                    retrace=(max(p for _,p in hp)-min(p for _,p in lp))
                    if abs(pole)>=3*atr and retrace<=abs(pole)*.5 and abs(pole)>10*tick:
                        if family=='channel' and hs*pole<0:
                            add('bull_flag' if pole>0 else 'bear_flag',hp+lp,u,d,'bullish' if pole>0 else 'bearish',{'pole':pole})
                        elif family=='symmetrical_triangle':add('pennant',hp+lp,u,d,'bullish' if pole>0 else 'bearish',{'pole':pole})
    for up,points,opposite in ((False,highs,lows),(True,lows,highs)):
        if len(points)<2:continue
        a,b=points[-2:];between=[p for p in opposite if a[0]<p[0]<b[0]]
        if between and b[0]-a[0]>=6:
            neck=max(p for _,p in between) if up else min(p for _,p in between)
            depth=min(a[1],b[1])-neck if not up else neck-max(a[1],b[1])
            if depth>5*tick and abs(a[1]-b[1])<=max(tick,depth*.1):
                upper=(lambda i,v=neck:v) if up else (lambda i,v=max(a[1],b[1]):v)
                lower=(lambda i,v=min(a[1],b[1]):v) if up else (lambda i,v=neck:v)
                add('double_bottom' if up else 'double_top',[a,b,*between],upper,lower,'bullish' if up else 'bearish',{'neckline':neck})
        if len(points)<3:continue
        a,h,b=points[-3:];left=[p for p in opposite if a[0]<p[0]<h[0]];right=[p for p in opposite if h[0]<p[0]<b[0]]
        if left and right and min(h[0]-a[0],b[0]-h[0])>=3:
            nl=max(left,key=lambda p:p[1]) if up else min(left,key=lambda p:p[1])
            nr=max(right,key=lambda p:p[1]) if up else min(right,key=lambda p:p[1])
            neck=line([nl,nr]);depth=abs(h[1]-neck(h[0]))
            head=(h[1]<min(a[1],b[1])-max(tick,depth*.2)) if up else (h[1]>max(a[1],b[1])+max(tick,depth*.2))
            if head and depth>5*tick and abs(a[1]-b[1])<=depth*.15:
                upper=neck if up else lambda i,v=h[1]:v
                lower=(lambda i,v=h[1]:v) if up else neck
                add('inverse_head_and_shoulders' if up else 'head_and_shoulders',[a,h,b,nl,nr],upper,lower,'bullish' if up else 'bearish',{'neckline_points':[nl,nr]})
    # Rounding is subjective; explicit curvature/residual/slope tests remain
    # experimental descriptive context even after a boundary break.
    if n>=40:
        rows=bars[-32:];ys=np.array([b.close for b in rows]);xs=np.arange(32)
        coef=np.polyfit(xs,ys,2);fit=np.polyval(coef,xs);span=float(max(ys)-min(ys))
        if span>20*tick and abs(coef[0])>tick/32 and np.max(np.abs(ys-fit))<=span*.08:
            vertex=-coef[1]/(2*coef[0]);left=fit[0]-fit[15];right=fit[-1]-fit[15]
            if 10<=vertex<=21 and left*right>0 and min(abs(left),abs(right))>=span*.5:
                up=coef[0]>0;top=float(max(ys));bottom=float(min(ys))
                add('rounding_bottom' if up else 'rounding_top',[(n-32,ys[0]),(n-1,ys[-1])],
                    lambda i,v=top:v,lambda i,v=bottom:v,'bullish' if up else 'bearish',{'quadratic':coef.tolist(),'experimental':True})
    return out


def detect(frame,tick):
    from .pattern_lab import valid_frame
    if not valid_frame(frame,tick,40):return []
    bars=frame.bars;raw_highs,raw_lows=_pivots([b.high for b in bars],[b.low for b in bars])
    events={}
    for n in range(40,len(bars)+1):
        hp=[p for p in raw_highs if p[0]+3<n];lp=[p for p in raw_lows if p[0]+3<n]
        for shape in candidates(bars[:n],hp,lp,tick):
            family=shape['family'];indices=shape['pivot_indices'];key=(family,indices)
            if key in events:continue
            start=min(indices);end=max(indices);known=n-1;u,d=shape['upper'],shape['lower']
            event_id=sha256(f'{bars[0].instrument}|{frame.timeframe}|{family}|{bars[start].close_time_ms}|{bars[end].close_time_ms}'.encode()).hexdigest()[:24]
            row=dict(pattern_id=family,pattern_version=VERSION,event_id=event_id,
                origin_at=bars[start].close_time_ms,formed_at=bars[end].close_time_ms,
                first_known_at=bars[known].close_time_ms,known_at=bars[known].close_time_ms,
                confirmed_at=None,invalidated_at=None,expired_at=None,retested_at=None,
                state='CANDIDATE',direction=shape['bias'],minimum_pivot_count=len(indices),
                pivot_indices=list(indices),neckline=shape['extra'].get('neckline'),
                geometry={**shape['extra'],'upper_at_known':u(known),'lower_at_known':d(known),
                          'upper_slope':u(known+1)-u(known),'lower_slope':d(known+1)-d(known)},
                invalidation=None,role='DESCRIPTIVE',trade_permission=False,timeframe=frame.timeframe)
            broken=None
            for j in range(known+1,len(bars)):
                b=bars[j]
                if j-known>30:
                    row.update(state='EXPIRED',expired_at=b.close_time_ms);break
                up=b.close>u(j)+tick;down=b.close<d(j)-tick
                direction='bullish' if up else 'bearish' if down else None
                if row['confirmed_at'] is None:
                    if direction and broken and broken==(direction,j-1):
                        row.update(state='CONFIRMED',confirmed_at=b.close_time_ms,direction=direction,
                                   invalidation=d(j) if up else u(j))
                    broken=(direction,j) if direction else None
                else:
                    bullish=row['direction']=='bullish';boundary=u(j) if bullish else d(j)
                    if (b.close<boundary-tick if bullish else b.close>boundary+tick):
                        row.update(state='INVALIDATED',invalidated_at=b.close_time_ms,failed_breakout=True);break
                    if b.low<=boundary+tick and b.high>=boundary-tick:
                        row['retested_at']=row['retested_at'] or b.close_time_ms
            events[key]=row
    return sorted(events.values(),key=lambda p:(p['first_known_at'],p['pattern_id']))[-64:]
