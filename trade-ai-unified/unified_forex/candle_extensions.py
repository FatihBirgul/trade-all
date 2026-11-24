"""Missing candle geometry v7. Engineering taxonomy; descriptive, never an order vote.

Trend is measured strictly BEFORE the formation using ten closed closes; movement
must exceed two formation ticks. Every new family requires a later directional
close. Doji means body<=10% range, long>=60%, short<=35%. No TA-Lib equivalence.
"""
VERSION='fx-candle-catalog-v7-1'
FAMILIES=('three_line_strike','separating_lines','on_neck','in_neck','thrusting',
          'advance_block','stalled_pattern','tristar','breakaway','three_stars_in_south','unique_three_river')
LENGTHS=dict(zip(FAMILIES,(4,2,2,2,2,3,3,3,5,3,3)))


def geometry(rows,tick):
    """Exact formation geometry only. Caller supplies causal trend/confirmation."""
    if not rows:return []
    result=[]
    # Mirror all symmetric definitions; the south/river names are bullish-only.
    for sign in (1,-1):
        values=[(sign*b.open,sign*(b.high if sign==1 else b.low),
                 sign*(b.low if sign==1 else b.high),sign*b.close) for b in rows]
        o,h,l,c=map(list,zip(*values));n=len(o)
        body=lambda i:abs(c[i]-o[i])
        span=lambda i:h[i]-l[i]
        up=lambda i:c[i]-o[i]>tick
        down=lambda i:o[i]-c[i]>tick
        long=lambda i:span(i)>0 and body(i)>=.6*span(i)
        small=lambda i:span(i)>0 and body(i)<=.35*span(i)
        doji=lambda i:span(i)>0 and body(i)<=.1*span(i)
        def add(name,condition,trend):
            if condition:result.append((name,'bullish' if sign==1 else 'bearish',trend*sign))
        if n>=2:
            a,b=n-2,n-1
            add('separating_lines',down(a) and up(b) and long(b) and abs(o[b]-o[a])<=tick and l[b]>=o[b]-tick,1)
            base=down(a) and long(a) and up(b) and o[b]<l[a]-tick
            add('on_neck',base and abs(c[b]-l[a])<=tick,-1)
            add('in_neck',base and c[a]+tick<c[b]<=c[a]+.1*body(a),-1)
            add('thrusting',base and c[a]+.1*body(a)<c[b]<(o[a]+c[a])/2-tick,-1)
        if n>=3:
            a,b,d=n-3,n-2,n-1
            progress=all(up(i) for i in (a,b,d)) and c[a]+tick<c[b]<c[d]-tick and o[a]<o[b]<c[a] and o[b]<o[d]<c[b]
            add('advance_block',progress and body(a)>body(b)>body(d) and h[d]-c[d]>body(d) and h[b]-c[b]>h[a]-c[a],1)
            add('stalled_pattern',progress and long(a) and long(b) and small(d) and o[d]>=c[b]-tick and body(d)<body(b)/2,1)
            add('tristar',all(doji(i) for i in (a,b,d)) and h[b]<l[a]-tick and l[d]>h[b]+tick,-1)
            if sign==1:
                add('three_stars_in_south',all(down(i) for i in (a,b,d)) and long(a) and l[a]<l[b]<l[d] and h[d]<h[b]<h[a] and body(a)>body(b)>body(d) and c[a]-l[a]>body(a)/2 and small(d),-1)
                add('unique_three_river',down(a) and long(a) and down(b) and l[b]<l[a]-tick and c[b]>c[a]+tick and c[b]-l[b]>2*body(b) and up(d) and small(d) and l[d]>l[b] and c[d]<c[b],-1)
        if n>=4:
            a,b,d,e=n-4,n-3,n-2,n-1
            add('three_line_strike',all(up(i) and long(i) for i in (a,b,d)) and o[a]<o[b]<o[d] and c[a]<c[b]<c[d] and down(e) and o[e]>c[d]+tick and c[e]<o[a]-tick,1)
        if n>=5:
            a,b,d,e,f=n-5,n-4,n-3,n-2,n-1
            add('breakaway',down(a) and long(a) and h[b]<l[a]-tick and down(b) and c[e]<c[b] and all(small(i) for i in (d,e)) and up(f) and long(f) and h[b]+tick<c[f]<l[a]-tick,-1)
    return result


def detect(frame,tick):
    from .pattern_lab import valid_frame
    if not valid_frame(frame,tick,15):return []
    bars=frame.bars;out=[]
    for i in range(max(15,len(bars)-6),len(bars)):
        for family,direction,expected in geometry(bars[max(0,i-4):i+1],tick):
            count=LENGTHS[family];start=i-count+1
            context=bars[start-10:start]
            change=context[-1].close-context[0].close
            if change*expected<=2*tick:continue
            formation=bars[start:i+1];low=min(b.low for b in formation);high=max(b.high for b in formation)
            confirmation=None
            # Reversal-named bullish/bearish geometry can describe continuation
            # exhaustion. Direction follows the specified expected reversal rule.
            if family in ('on_neck','in_neck','thrusting','advance_block','stalled_pattern','three_line_strike'):
                direction='bearish' if direction=='bullish' else 'bullish'
            up=direction=='bullish'
            if i+1<len(bars):
                b=bars[i+1]
                if (b.close>high+tick and b.close>b.open) if up else (b.close<low-tick and b.close<b.open):confirmation=b.close_time_ms
            invalid=next((b.close_time_ms for b in bars[i+1:] if b.close<low-tick if up),None) if up else next((b.close_time_ms for b in bars[i+1:] if b.close>high+tick),None)
            out.append(dict(pattern_id=family,pattern_version=VERSION,minimum_candles=count,
                direction=direction,formed_at=bars[i].close_time_ms,first_known_at=bars[i].close_time_ms,
                confirmed_at=confirmation,invalidation=low if up else high,invalidated_at=invalid,
                state='INVALIDATED' if invalid else 'CONFIRMED' if confirmation else 'EXPIRED' if len(bars)-1-i>=3 else 'CANDIDATE',
                age_bars=len(bars)-1-i,trend_context='up' if expected>0 else 'down',
                price_range={'low':low,'high':high},confirmation_rule='next_close_beyond_formation_plus_tick',
                quality_status='engineering_descriptive',role='DESCRIPTIVE',strength=0,
                trade_permission=False,timeframe=frame.timeframe))
    return out
