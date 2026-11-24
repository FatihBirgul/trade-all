"""Confirmed, aligned price/indicator pivots; descriptive momentum context."""
from forex.core import ema_series,scanner
from market_ai.engines.chart_patterns import _pivots

VERSION='fx-aligned-divergence-v7-1'


def aligned(frame,values,name,tick,alignment=2):
    bars=frame.bars;n=len(bars)
    ph,pl=_pivots([b.high for b in bars],[b.low for b in bars],left=2,right=2)
    # Indicator warm-up is explicit; no zero padding participates in pivots.
    valid=[(i,v) for i,v in enumerate(values) if v is not None]
    if len(valid)<7:return []
    start=valid[0][0];series=[v for _,v in valid]
    ih,il=_pivots(series,series,left=2,right=2)
    ih=[(i+start,v) for i,v in ih];il=[(i+start,v) for i,v in il]
    out=[]
    for kind,prices,indicators in [('low',pl,il),('high',ph,ih)]:
        pairs=[]
        used=set()
        for i,p in prices:
            matches=[(j,v) for j,v in indicators if abs(j-i)<=alignment and j not in used]
            if matches:
                j,v=min(matches,key=lambda x:(abs(x[0]-i),x[0]));used.add(j);pairs.append((i,p,j,v))
        for a,b in zip(pairs,pairs[1:]):
            if not 4<=b[0]-a[0]<=60:continue
            pd=b[1]-a[1];md=b[3]-a[3]
            if abs(pd)<=tick or abs(md)<=1e-10:continue
            regular=(kind=='low' and pd<0 and md>0) or (kind=='high' and pd>0 and md<0)
            hidden=(kind=='low' and pd>0 and md<0) or (kind=='high' and pd<0 and md>0)
            if not regular and not hidden:continue
            known=max(a[0]+2,a[2]+2,b[0]+2,b[2]+2)
            if known>=n:continue
            direction='bullish' if kind=='low' else 'bearish'
            out.append(dict(indicator=name,kind='regular' if regular else 'hidden',direction=direction,
                price_pivots=[a[0],b[0]],indicator_pivots=[a[2],b[2]],price_values=[a[1],b[1]],indicator_values=[a[3],b[3]],
                origin_at=bars[a[0]].close_time_ms,first_known_at=bars[known].close_time_ms,
                confirmed_at=bars[known].close_time_ms,algorithm_version=VERSION,role='DESCRIPTIVE',trade_permission=False))
    return out[-12:]


def analyze(frame,tick):
    closes=[b.close for b in frame.bars];n=len(closes)
    rsi=[None]*n
    for i in range(14,n):rsi[i]=scanner.rsi(closes[:i+1])
    fast,slow=ema_series(closes,12),ema_series(closes,26)
    macd=[None]*25+[a-b for a,b in zip(fast[14:],slow)]
    events=aligned(frame,rsi,'wilder_rsi14',tick)+aligned(frame,macd,'sma_seed_macd12_26',tick)
    return dict(version=VERSION,status='AVAILABLE' if n>=35 else 'WARMUP',events=events,
                momentum_weakening={'macd':abs(macd[-1])<abs(macd[-2]) if n>=27 else None},
                alignment_bars=2,role='DESCRIPTIVE',trade_permission=False)
