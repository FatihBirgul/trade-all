"""Explicit crypto 24/7 UTC-day research, not an exchange-session assertion.

No Forex/equity calendar or DST conversion is guessed. VWAP uses actual base
volume and OHLC typical price: a candle approximation, not tick/trade VWAP.
"""
from decimal import Decimal as D,Context,localcontext,ROUND_HALF_EVEN
from itertools import islice
from .market_data_contract import validate_series
from .technical_adapter import TIMEFRAME_MS
VERSION='v2-crypto-session-research-1'
DAY=86400000

def _vwap(rows):
    """Shared unchanged typical-price/real-volume formula, fixed Decimal context."""
    with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
        def unavailable(reason):return {'status':'unavailable','reason':reason}
        def fmt(x):return format(D(0) if x==0 else x,'f')
        if not rows or any(b.volume_kind!='real' or b.volume is None for b in rows):return unavailable('real_base_volume_required')
        total=sum((D(str(b.volume)) for b in rows),D(0))
        if total<=0:return unavailable('positive_volume_required')
        value=sum(((D(str(b.high))+D(str(b.low))+D(str(b.close)))/3*D(str(b.volume)) for b in rows),D(0))/total
        return {'status':'available','value':fmt(value),'volume':fmt(total),'from_ms':rows[0].open_time_ms,'known_at':rows[-1].close_time_ms}


def session_research(candles,*,timeframe,as_of_ms,max_age_ms,anchor_ms=None,calendar_id='crypto_utc_day_v1'):
    out={'version':VERSION,'status':'unavailable','trade_permission':False,'validation_status':'DETECTION_IMPLEMENTED','calendar_id':calendar_id,'calendar_timezone':'UTC','session_definition':'crypto_24x7_UTC_00:00_to_next_00:00_exclusive','vwap_definition':'OHLC_typical_price_times_real_base_volume_approximation'}
    bars=tuple(islice(candles,4097))
    if len(bars)>4096:return {**out,'reason':'resource_budget'}
    if not bars or timeframe not in TIMEFRAME_MS:return {**out,'reason':'missing_supported_data'}
    if calendar_id!='crypto_utc_day_v1' or bars[0].instrument.market!='crypto_spot' or bars[0].instrument.contract_type!='spot':return {**out,'reason':'unsupported_calendar_or_market'}
    frame=TIMEFRAME_MS[timeframe]
    q=validate_series(bars,timeframe_ms=frame,as_of_ms=as_of_ms,max_age_ms=max_age_ms,min_bars=1)
    if not q.ok or any(b.open_time_ms%frame for b in bars):return {**out,'reason':'closed_data_quality','issues':[i.code for i in q.issues]}
    start=(bars[-1].close_time_ms-1)//DAY*DAY
    current=[b for b in bars if b.open_time_ms>=start]
    if not current or current[0].open_time_ms!=start:return {**out,'reason':'missing_session_prefix','session_started_at_ms':start}
    def unavailable(reason):return {'status':'unavailable','reason':reason}
    with localcontext(Context(prec=60,rounding=ROUND_HALF_EVEN)):
        def fmt(x):return format(D(0) if x==0 else x,'f')
        def extrema(rows):return max(D(str(b.high)) for b in rows),min(D(str(b.low)) for b in rows)
        high,low=extrema(current)
        anchor_index=next((i for i,b in enumerate(bars) if type(anchor_ms) is int and b.open_time_ms==anchor_ms),None)
        anchored=_vwap(bars[anchor_index:]) if anchor_index is not None else unavailable('explicit_closed_source_anchor_required')
        orb=unavailable('opening_15min_closed_prefix_required')
        if frame<=900000 and 900000%frame==0 and bars[-1].close_time_ms>=start+900000:
            opening=[b for b in current if b.close_time_ms<=start+900000]
            oh,ol=extrema(opening);latest=D(str(current[-1].close))
            orb={'status':'available','high':fmt(oh),'low':fmt(ol),'known_at':start+900000,'state':'above' if latest>oh else 'below' if latest<ol else 'inside','confirmation_at':current[-1].close_time_ms,'scope':'closed_price_vs_fixed_opening_range_not_trade_permission'}
        previous=[b for b in bars if start-DAY<=b.open_time_ms<start]
        prev=unavailable('full_previous_UTC_day_not_recorded')
        if previous and previous[0].open_time_ms==start-DAY and previous[-1].close_time_ms==start:
            ph,pl=extrema(previous);prev={'status':'available','high':fmt(ph),'low':fmt(pl),'known_at':start}
        volatility=unavailable('26_closed_bars_required')
        if len(bars)>=26:
            tr=[max(D(str(b.high))-D(str(b.low)),abs(D(str(b.high))-D(str(a.close))),abs(D(str(b.low))-D(str(a.close)))) for a,b in zip(bars,bars[1:])]
            prior=sum(tr[-25:-5])/20;recent=sum(tr[-5:])/5
            if prior>0:
                ratio=recent/prior;volatility={'status':'available','ratio':fmt(ratio),'regime':'expanding' if ratio>=D('1.5') else 'compressing' if ratio<=D(2)/3 else 'normal','known_at':bars[-1].close_time_ms}
        return {**out,'status':'available','source':bars[0].source,'symbol':bars[0].instrument.symbol,'session_started_at_ms':start,'known_at':bars[-1].close_time_ms,'session_high':fmt(high),'session_low':fmt(low),'session_range':fmt(high-low),'session_vwap':_vwap(current),'anchored_vwap':anchored,'orb':orb,'previous_session':prev,'volatility':volatility}


def anchored_vwap(candles,*,timeframe,as_of_ms,max_age_ms,anchor_ms):
    """Explicit closed anchor, independent of UTC-day prefix. No source guessing."""
    out={'version':'v2-explicit-anchor-1','status':'unavailable','trade_permission':False,
         'definition':'OHLC_typical_price_times_real_base_volume_approximation'}
    bars=tuple(islice(candles,1025))
    if not 2<=len(bars)<=1024 or timeframe not in TIMEFRAME_MS:return {**out,'reason':'bounded_source_required'}
    frame=TIMEFRAME_MS[timeframe]
    q=validate_series(bars,timeframe_ms=frame,as_of_ms=as_of_ms,max_age_ms=max_age_ms,min_bars=2)
    if not q.ok or any(b.open_time_ms%frame for b in bars):return {**out,'reason':'closed_data_quality'}
    if bars[0].instrument.market!='crypto_spot' or bars[0].instrument.contract_type!='spot':return {**out,'reason':'unsupported_market'}
    index=next((i for i,b in enumerate(bars) if type(anchor_ms) is int and b.open_time_ms==anchor_ms),None)
    if index is None or len(bars)-index<2:return {**out,'reason':'two_closed_source_candles_from_anchor_required'}
    return {**out,**_vwap(bars[index:])}
