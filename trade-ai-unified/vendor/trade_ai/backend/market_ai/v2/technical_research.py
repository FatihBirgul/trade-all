"""Versioned OHLC research methods; no directional composite/order permissions.

Legacy EMA/RSI/MACD/ATR/Bollinger implementations remain untouched. Bandwidth
uses the existing sample-std Bollinger function with its unrounded values.
ADX/ATR-Wilder and Supertrend explicitly use different named definitions.
"""
from dataclasses import replace
from decimal import Decimal as D, Context, localcontext, ROUND_HALF_EVEN
from itertools import groupby, islice
import pandas as pd
from market_ai.engines.technical import bollinger
from .market_data_contract import validate_series
from .technical_adapter import TIMEFRAME_MS

VERSION='v2-technical-research-1'
CONTEXT=Context(prec=60,rounding=ROUND_HALF_EVEN)
def txt(x):return format(D(0) if x==0 else x,'f')

def wilder(values,period):
    result={}
    if len(values)<period:return result
    value=sum(values[:period])/period;result[period]=value
    for i,x in enumerate(values[period:],period+1):
        value=(value*(period-1)+x)/period;result[i]=value
    return result

def compute_methods(candles,*,timeframe,as_of_ms,max_age_ms,permitted_gaps=()):
    bars=tuple(islice(candles,4097))
    if timeframe not in TIMEFRAME_MS or len(bars)>4096:raise ValueError('Supported bounded research frame required')
    quality=validate_series(bars,timeframe_ms=TIMEFRAME_MS[timeframe],as_of_ms=as_of_ms,max_age_ms=max_age_ms,min_bars=2,permitted_gaps=permitted_gaps)
    result={'version':VERSION,'status':'unavailable','issues':[i.code for i in quality.issues],
            'as_of_ms':as_of_ms,'timeframe':timeframe,'trade_permission':False,'methods':{}}
    if not quality.ok:return result
    with localcontext(CONTEXT):
        n=len(bars);o,h,l,c=([D(str(getattr(b,k))) for b in bars] for k in ('open','high','low','close'))
        names=('roc12','stochastic14','donchian20_previous','bollinger_bandwidth20','adx14_wilder','supertrend10_3')
        methods={k:{'status':'warmup'} for k in names}
        if n>=13:methods['roc12']={'status':'available','percent':txt((c[-1]/c[-13]-1)*100)}
        if n>=14:
            top,bottom=max(h[-14:]),min(l[-14:])
            methods['stochastic14']=({'status':'available','k':txt((c[-1]-bottom)/(top-bottom)*100)} if top>bottom else {'status':'undefined_flat_range'})
        if n>=21:
            methods['donchian20_previous']={'status':'available','upper':txt(max(h[-21:-1])),'lower':txt(min(l[-21:-1])),
                'definition':'Previous20 closed bars; latest bar excluded from channel.'}
        if n>=20:
            u,m,low=bollinger(pd.Series([float(x) for x in c]))
            upper,middle,lower=(D(str(float(x.iloc[-1]))) for x in (u,m,low))
            methods['bollinger_bandwidth20']=({'status':'available','percent':txt((upper-lower)/middle*100),'definition':'Legacy SMA20 sample-standard-deviation bands, unrounded.'}
                if all(x.is_finite() for x in (upper,middle,lower)) and middle>0 else {'status':'unavailable_numeric_range'})
        tr=[max(h[i]-l[i],abs(h[i]-c[i-1]),abs(l[i]-c[i-1])) for i in range(1,n)]
        plus=[];minus=[]
        for i in range(1,n):
            up,down=h[i]-h[i-1],l[i-1]-l[i]
            plus.append(up if up>down and up>0 else D(0));minus.append(down if down>up and down>0 else D(0))
        atr14,plus14,minus14=(wilder(x,14) for x in (tr,plus,minus));dx=[]
        for i in range(14,n):
            pdm=100*plus14[i]/atr14[i] if atr14[i] else D(0)
            mdm=100*minus14[i]/atr14[i] if atr14[i] else D(0)
            dx.append(100*abs(pdm-mdm)/(pdm+mdm) if pdm+mdm else D(0))
        if n>=28:
            adx=wilder(dx,14)[len(dx)]
            methods['adx14_wilder']={'status':'available','adx':txt(adx),'plus_di':txt(pdm),'minus_di':txt(mdm),
                'atr_wilder':txt(atr14[n-1]),'definition':'14 changes seed DM/TR,14 DX seed ADX; first ADX at28 candles.'}
        atr10=wilder(tr,10)
        if atr10:
            upper=lower=None;direction=None;value=None
            for i in range(10,n):
                mid=(h[i]+l[i])/2;bu=mid+3*atr10[i];bl=mid-3*atr10[i]
                if upper is None:
                    upper,lower=bu,bl;direction='bullish' if c[i]>mid else 'bearish'
                else:
                    upper=bu if bu<upper or c[i-1]>upper else upper
                    lower=bl if bl>lower or c[i-1]<lower else lower
                    if direction=='bullish' and c[i]<lower:direction='bearish'
                    elif direction=='bearish' and c[i]>upper:direction='bullish'
                value=lower if direction=='bullish' else upper
            methods['supertrend10_3']={'status':'available','value':txt(value),'direction':direction,
                'definition':'Wilder ATR10, multiplier3, close crossing retained bands; first side by close>mid.'}
        result.update(status='available',methods=methods)
    return result


def resample_closed(candles,*,source_timeframe,target_timeframe,as_of_ms):
    """UTC aligned OHLC aggregation; partial leading/trailing buckets reported.

    Entire source must already be closed/QC-valid. This does not infer exchange
    sessions, interpolate missing bars, fetch prices or relabel tick volume real.
    """
    if source_timeframe not in TIMEFRAME_MS or target_timeframe not in TIMEFRAME_MS:raise ValueError('Unsupported frame')
    source,target=TIMEFRAME_MS[source_timeframe],TIMEFRAME_MS[target_timeframe]
    if target<=source or target%source:raise ValueError('Target must be a larger exact multiple')
    bars=tuple(islice(candles,30001))
    if len(bars)>30000:raise ValueError('Resampling exceeds30000bars')
    q=validate_series(bars,timeframe_ms=source,as_of_ms=as_of_ms,max_age_ms=source)
    if not q.ok or any(b.open_time_ms%source for b in bars):raise ValueError('Closed valid aligned source required')
    output=[];dropped=0
    with localcontext(CONTEXT):
        for boundary,group in groupby(bars,key=lambda b:b.open_time_ms//target*target):
            rows=tuple(group)
            if len(rows)!=target//source or rows[0].open_time_ms!=boundary or rows[-1].close_time_ms!=boundary+target:
                dropped+=len(rows);continue
            volume=None if rows[0].volume_kind=='unavailable' else txt(sum((D(str(b.volume)) for b in rows),D(0)))
            output.append(replace(rows[0],open_time_ms=boundary,close_time_ms=boundary+target,
                open=rows[0].open,high=txt(max(D(str(b.high)) for b in rows)),low=txt(min(D(str(b.low)) for b in rows)),
                close=rows[-1].close,volume=volume))
    return {'version':VERSION,'source_timeframe':source_timeframe,'target_timeframe':target_timeframe,
            'candles':tuple(output),'dropped_partial_bars':dropped,'as_of_ms':as_of_ms}
