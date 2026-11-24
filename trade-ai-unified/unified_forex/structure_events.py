"""Causal OHLC lifecycle over retained V5 confirmed pivots and V2 price action."""
from hashlib import sha256
from forex.structure import market_structure
from .technical import ohlc

VERSION='fx-structure-lifecycle-v8-1'


def tolerance_at(frame,index,tick):
    """Freeze volatility tolerance when the event first becomes knowable."""
    bars=frame.bars
    start=max(1,index-13)
    tr=[max(bars[i].high-bars[i].low,abs(bars[i].high-bars[i-1].close),abs(bars[i].low-bars[i-1].close)) for i in range(start,index+1)]
    return max(tick,(sum(tr)/len(tr) if tr else 0)*.1)


def analyze(frame,action,tick,atr):
    bars=frame.bars;n=len(bars)
    original=market_structure(ohlc(frame),limit=n,timeframe_seconds=frame.duration_ms//1000)
    index={b.close_time_ms//1000:i for i,b in enumerate(bars)}
    events=[]
    def event(kind,direction,origin,known,level,invalid=None):
        stamp=bars[origin].close_time_ms
        return dict(event_id=sha256(f'{bars[0].instrument}|{frame.timeframe}|{kind}|{stamp}|{level}'.encode()).hexdigest()[:24],
            kind=kind,direction=direction,origin_at=stamp,first_known_at=bars[known].close_time_ms,
            confirmed_at=bars[known].close_time_ms,state='CONFIRMED',invalidated_at=None,expired_at=None,
            retested_at=None,level=level,invalidation=invalid,rule_version=VERSION,
            timeframe=frame.timeframe,ohlc_heuristic=True,order_book_verified=False)
    hp,lp=original['highs'],original['lows']
    for side,pivots in [('high',hp),('low',lp)]:
        previous=None
        for p in pivots:
            i=index[p['formed_at']];known=index[p['confirmed_at']];value=p['price']
            tol=tolerance_at(frame,known,tick)
            label='SWING_HIGH' if side=='high' else 'SWING_LOW'
            if previous:
                delta=value-previous['price']
                label=('HH' if delta>tol else 'LH' if delta<-tol else 'EQUAL_HIGH') if side=='high' else ('HL' if delta>tol else 'LL' if delta<-tol else 'EQUAL_LOW')
            row=event(label,'neutral',i,known,value,value)
            for j in range(known+1,n):
                b=bars[j];broken=b.close>value+tol if side=='high' else b.close<value-tol
                if broken:
                    row.update(state='INVALIDATED',invalidated_at=b.close_time_ms);break
                if j-known>50:row.update(state='EXPIRED',expired_at=b.close_time_ms);break
                if b.low<=value+tol and b.high>=value-tol:row['retested_at']=row['retested_at'] or b.close_time_ms
            events.append(row);previous=p
    # Closed BOS/CHoCH, once per confirmed pivot. Transition bias uses only
    # pivots already knowable BEFORE the event candle, matching V2 methodology.
    seen=set()
    for j in range(5,n):
        highs=[p for p in hp if p['confirmed_at']<bars[j].close_time_ms//1000]
        lows=[p for p in lp if p['confirmed_at']<bars[j].close_time_ms//1000]
        bias='neutral'
        if len(highs)>=2 and len(lows)>=2:
            if highs[-1]['price']>highs[-2]['price'] and lows[-1]['price']>lows[-2]['price']:bias='bullish'
            if highs[-1]['price']<highs[-2]['price'] and lows[-1]['price']<lows[-2]['price']:bias='bearish'
        for direction,pivots in [('bullish',highs),('bearish',lows)]:
            if not pivots:continue
            p=pivots[-1];key=(direction,p['formed_at']);v=p['price']
            crossed=bars[j].close>v+tick if direction=='bullish' else bars[j].close<v-tick
            if crossed and key not in seen:
                seen.add(key);kind='CHoCH' if bias not in ('neutral',direction) else 'BOS'
                row=event(kind,direction,index[p['formed_at']],j,v,v)
                tol=tolerance_at(frame,j,tick)
                for k in range(j+1,n):
                    b=bars[k];failed=b.close<v-tick if direction=='bullish' else b.close>v+tick
                    if failed:row.update(state='INVALIDATED',invalidated_at=b.close_time_ms);break
                    if k-j>30:row.update(state='EXPIRED',expired_at=b.close_time_ms);break
                    if b.low<=v+tol and b.high>=v-tol:row['retested_at']=row['retested_at'] or b.close_time_ms
                events.append(row)
    for gap in action['fvg'].get('active_gaps',[]):
        i=next(i for i,b in enumerate(bars) if b.close_time_ms==gap['formed_at_ms'])
        row=event('FVG',gap['direction'],max(0,i-2),i,float(gap['low']),float(gap['low'] if gap['direction']=='bullish' else gap['high']))
        row.update(price_range={'low':float(gap['low']),'high':float(gap['high'])},scope='source_V2_active_only')
        events.append(row)
    sweep=action['liquidity_sweep']
    if sweep.get('direction') in ('bullish','bearish'):
        row=event('SWEEP_RECLAIM',sweep['direction'],n-1,n-1,float(sweep['extreme']))
        row.update(state='CANDIDATE',confirmed_at=None,confirmation_rule='next_closed_follow_through_required')
        events.append(row)
    return dict(version=VERSION,events=sorted(events,key=lambda e:(e['first_known_at'],e['event_id']))[-128:],
                range_boundaries={'high':max(b.high for b in bars[-21:-1]),'low':min(b.low for b in bars[-21:-1])},
                price_only=True,external_liquidity_verified=False)
