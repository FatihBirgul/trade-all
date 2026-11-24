"""Causal confirmed price pivots + existing legacy oscillator series.

RSI is the project's simple rolling RSI14, not Wilder RSI. MACD uses the existing
12/26 EMA line, not histogram. Neither event authorizes trades or adds confluence.
"""
from dataclasses import asdict
from decimal import Decimal as D,Context,localcontext,ROUND_HALF_EVEN,InvalidOperation
from itertools import islice
import math
import pandas as pd
from market_ai.engines.technical import rsi,macd
from .market_data_contract import validate_series
from .technical_adapter import TIMEFRAME_MS
from .product_db import fingerprint
VERSION='v2-confirmed-divergence-1'

def detect_divergences(candles,*,timeframe,as_of_ms,max_age_ms,tick_size):
    result={'version':VERSION,'status':'unavailable','validation_status':'DETECTION_IMPLEMENTED',
        'trade_permission':False,'scope':'descriptive_only_not_strategy_validation','timeframe':timeframe,'as_of_ms':as_of_ms,'events':[]}
    bars=tuple(islice(candles,513))
    if len(bars)>512:return {**result,'reason':'resource_budget'}
    if timeframe not in TIMEFRAME_MS:return {**result,'reason':'unsupported_timeframe'}
    quality=validate_series(bars,timeframe_ms=TIMEFRAME_MS[timeframe],as_of_ms=as_of_ms,max_age_ms=max_age_ms,min_bars=40)
    if not quality.ok:return {**result,'reason':'closed_data_or_warmup_gate','issues':[i.code for i in quality.issues]}
    try:tick=D(str(tick_size))
    except (InvalidOperation,ValueError):return {**result,'reason':'invalid_tick'}
    if not tick.is_finite() or tick<=0:return {**result,'reason':'invalid_tick'}
    with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
        closes=[float(b.close) for b in bars]
        if any(not math.isfinite(x) or abs(x)>1e100 for x in closes):return {**result,'reason':'numeric_range'}
        series=pd.Series(closes,dtype='float64')
        oscillators={'legacy_rsi14_sma':rsi(series,14),'legacy_macd_line_12_26':macd(series)[0]}
        parameters={'pivot_left':2,'pivot_right':2,'minimum_rsi_delta':'1','minimum_macd_delta':format(tick.normalize(),'f')}
        events=[]
        for side,attribute,direction in (('low','low','bullish'),('high','high','bearish')):
            values=[D(str(getattr(b,attribute))) for b in bars]
            previous=None
            for index in range(2,len(bars)-2):
                pivot=all(values[index]<values[j] if side=='low' else values[index]>values[j] for j in (index-2,index-1,index+1,index+2))
                if not pivot:continue
                if previous is not None:
                    price_move=values[index]<values[previous] if side=='low' else values[index]>values[previous]
                    for method,oscillator in oscillators.items():
                        old,new=float(oscillator.iloc[previous]),float(oscillator.iloc[index])
                        if not price_move or not all(math.isfinite(x) for x in (old,new)):continue
                        old,new=D(str(old)),D(str(new));minimum=D(1) if method=='legacy_rsi14_sma' else tick
                        confirmed=new-old>=minimum if side=='low' else old-new>=minimum
                        if not confirmed:continue
                        identity={'version':VERSION,'instrument':asdict(bars[0].instrument),'source':bars[0].source,'timeframe':timeframe,'first_price':format(values[previous],'f'),'second_price':format(values[index],'f'),'first_indicator':format(old,'f'),'second_indicator':format(new,'f'),'method_id':method,'direction':direction,'first_pivot_at':bars[previous].close_time_ms,'formed_at':bars[index].close_time_ms,'confirmed_at':bars[index+2].close_time_ms,'parameters':parameters}
                        events.append({**identity,'event_id':fingerprint(identity),'known_at':bars[index+2].close_time_ms,'bucket':'momentum',
                            'price_at_first_pivot':format(values[previous],'f'),'price_at_second_pivot':format(values[index],'f'),
                            'indicator_at_first_pivot':format(old,'f'),'indicator_at_second_pivot':format(new,'f'),
                            'confirmation_rule':'strict_2left_2right_price_pivots','trade_permission':False,
                            'explanation':'İki teyitli fiyat pivotunda fiyat ve momentum zıt ilerledi. Bu yapısal araştırma bulgusudur; giriş teyidi, emir veya doğrulanmış başarı olasılığı değildir.'})
                previous=index
        return {**result,'status':'available','parameters':parameters,'events':sorted(events,key=lambda e:(e['confirmed_at'],e['method_id'],e['direction']))}
