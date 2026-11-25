"""Forex extensions. Legacy stock modules remain importable and unchanged."""
from __future__ import annotations
import importlib.util
import math
import re
from pathlib import Path
from datetime import datetime, timezone
from decimal import Decimal, ROUND_FLOOR
from .sessions import session_snapshot

ROOT = Path(__file__).resolve().parent.parent

def legacy(folder, filename):
    path = ROOT / folder / filename
    spec = importlib.util.spec_from_file_location(folder.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

scanner = legacy('trader-scanner', 'scan.py')
entry = legacy('trader-entry', 'entry.py')
exit_planner = legacy('trader-exit', 'exit.py')
timemachine = legacy('trader-timemachine', 'timemachine.py')

TIMEFRAMES = {'M5': 300, 'M15': 900, 'M30': 1800, 'H1': 3600, 'H4': 14400, 'D1': 86400}
SYMBOLS = ('XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY')
_SYMBOL_PATTERN = re.compile(r'[A-Z0-9]{3,12}')

def is_supported_symbol(symbol):
    """Any canonical broker symbol; SYMBOLS stays as the legacy four-symbol catalogue."""
    return isinstance(symbol, str) and _SYMBOL_PATTERN.fullmatch(symbol) is not None

class DataError(ValueError):
    pass

def finite(value, name):
    if isinstance(value,bool):
        raise DataError(f'{name} must be numeric, not boolean')
    try:
        n = float(value)
    except (TypeError, ValueError, OverflowError):
        raise DataError(f'{name} missing or invalid')
    if not math.isfinite(n):
        raise DataError(f'{name} must be finite')
    return n

def ema(values, n):
    if len(values) < n:
        return None
    result = sum(values[:n]) / n
    for v in values[n:]:
        result += (v - result) * (2 / (n + 1))
    return result

def atr(bars, n=14):
    if len(bars) < n + 1:
        return None
    # Reuse the exit skill's true-range calculation on broker OHLC.
    converted = [{'h': b['high'], 'l': b['low'], 'c': b['close']} for b in bars]
    value, count = exit_planner.atr_of(converted, n)
    return value if count == n else None

def ema_series(values, n):
    if len(values)<n: return []
    current=sum(values[:n])/n
    out=[current]
    alpha=2/(n+1)
    for value in values[n:]:
        current+=(value-current)*alpha
        out.append(current)
    return out

def indicators(bars):
    closes = [b['close'] for b in bars]
    if len(closes) < 200:
        raise DataError('at least 200 closed candles required')
    e12, e26 = ema_series(closes,12), ema_series(closes,26)
    macd_series = [a-b for a,b in zip(e12[14:],e26)]
    macd_line = macd_series[-1]
    signal = ema(macd_series,9)
    mid = sum(closes[-20:])/20
    std = (sum((x-mid)**2 for x in closes[-20:])/20)**.5
    previous_signal=ema(macd_series[:-1],9)
    previous_hist=macd_series[-2]-previous_signal
    histogram=macd_line-signal
    sma20=mid;sma50=sum(closes[-50:])/50
    high=max(b['high'] for b in bars[-21:-1]);low=min(b['low'] for b in bars[-21:-1])
    previous_high=max(b['high'] for b in bars[-41:-21]);previous_low=min(b['low'] for b in bars[-41:-21])
    cached_ema={n:ema(closes,n) for n in (9,20,21,50,100,200)}
    previous_ema20=ema(closes[:-1],20)
    current_atr=atr(bars)
    return {'ema9':cached_ema[9],'ema20':cached_ema[20],'ema21':cached_ema[21],'ema50':cached_ema[50],
            'ema100':cached_ema[100],'ema200':cached_ema[200],'sma20':sma20,'sma50':sma50,
            'rsi14':scanner.rsi(closes),'atr14':current_atr,'normalized_atr':current_atr/closes[-1],
            'macd':macd_line,'macd_signal':signal,'macd_histogram':histogram,
            'momentum_change':histogram-previous_hist,
            'bollinger_upper':mid+2*std,'bollinger_lower':mid-2*std,
            'bollinger_width':4*std/mid if mid>0 else None,
            'swing_high':high,'swing_low':low,
            'higher_high':high>previous_high,'higher_low':low>previous_low,
            'lower_high':high<previous_high,'lower_low':low<previous_low,
            'ema20_slope':cached_ema[20]-previous_ema20,'ema20_previous':previous_ema20,
            'price_ema20_distance':(closes[-1]-cached_ema[20])/closes[-1]}

def validate_bars(bars, tf, now):
    if tf not in TIMEFRAMES:
        raise DataError('invalid timeframe')
    if not bars:
        raise DataError('no candles')
    end = 0
    for b in bars:
        t = finite(b.get('time'),'candle time')
        if t <= end or t+TIMEFRAMES[tf] > now:
            raise DataError('candles must be ordered and closed')
        end = t
        o,h,l,c = (finite(b.get(k),k) for k in ('open','high','low','close'))
        if l <= 0 or l > min(o,c) or h < max(o,c):
            raise DataError('invalid OHLC')
    return end

def price_round(value, tick, mode='nearest'):
    q = Decimal(str(value))/Decimal(str(tick))
    if mode == 'down': q = q.to_integral_value(rounding=ROUND_FLOOR)
    elif mode == 'up': q = (-q).to_integral_value(rounding=ROUND_FLOOR)*-1
    else: q = q.to_integral_value()
    return float(q*Decimal(str(tick)))

def size_lots(balance, risk_pct, entry_price, stop, meta, calc_profit=None, side='BUY', account_currency=None,
              commission_per_lot=0, slippage_price=0):
    """Size on the broker volume grid, always verifying a loss in account currency."""
    balance, risk_pct = finite(balance, 'balance'), finite(risk_pct, 'risk percent')
    if balance <= 0 or not 0 < risk_pct <= 5:
        raise DataError('invalid balance or risk percent')
    tick = finite(meta.get('tick_size'), 'tick_size')
    step = finite(meta.get('volume_step'), 'volume_step')
    minimum = finite(meta.get('volume_min'), 'volume_min')
    maximum = finite(meta.get('volume_max'), 'volume_max')
    contract = finite(meta.get('contract_size'), 'contract_size')
    if min(tick, step, minimum, maximum, contract) <= 0 or maximum < minimum:
        raise DataError('invalid contract metadata')
    currency = account_currency or meta.get('account_currency')
    if not currency or (meta.get('account_currency') and currency != meta['account_currency']):
        raise DataError('account currency unavailable or mismatched')
    ep, sl = finite(entry_price, 'entry'), finite(stop, 'stop')
    if ep <= 0 or sl <= 0 or side not in ('BUY', 'SELL') or (ep-sl)*(1 if side == 'BUY' else -1) <= 0:
        raise DataError('stop is on wrong side of entry')
    if abs(ep-sl) < tick:
        raise DataError('stop distance below tick size')
    commission = finite(commission_per_lot, 'commission per lot')
    slip = finite(slippage_price, 'slippage price')
    if commission < 0 or slip < 0:
        raise DataError('negative risk cost')
    # Round-trip commission in account currency per lot; adverse stop slippage
    # is an execution allowance, never another spread charge.
    loss_stop = sl - slip if side == 'BUY' else sl + slip
    if loss_stop <= 0:
        raise DataError('invalid slippage-adjusted stop')
    if calc_profit:
        sample = finite(calc_profit(side, minimum, ep, loss_stop), 'broker profit')
        if sample >= 0:
            raise DataError('broker did not report a stop-loss loss')
        per_lot = -sample / minimum + commission
    else:
        value = finite(meta.get('tick_value_loss') if meta.get('tick_value_loss') is not None else meta.get('tick_value'), 'tick_value_loss')
        if value <= 0 or meta.get('tick_value_currency') != currency:
            raise DataError('tick value not verified in account currency')
        per_lot = abs(ep-loss_stop)/tick*value + commission
    if per_lot <= 0:
        raise DataError('estimated loss unavailable')
    cap = Decimal(str(balance))*Decimal(str(risk_pct))/Decimal('100')
    dmin, dstep, dmax = map(lambda x: Decimal(str(x)), (minimum, step, maximum))
    if Decimal(str(per_lot))*dmin > cap:
        raise DataError('minimum lot exceeds risk budget')
    upper = min(dmax, cap/Decimal(str(per_lot)))
    units = ((upper-dmin)/dstep).to_integral_value(rounding=ROUND_FLOOR)
    lots = dmin + units*dstep
    if lots < dmin or lots > dmax:
        raise DataError('volume grid unavailable')
    if calc_profit:
        verified_profit = finite(calc_profit(side, float(lots), ep, loss_stop), 'broker profit')
        if verified_profit >= 0:
            raise DataError('broker did not report a stop-loss loss')
        loss = -verified_profit + float(lots)*commission
    else:
        loss = float(lots)*per_lot
    if loss <= 0 or Decimal(str(loss)) > cap:
        raise DataError('broker loss exceeds risk budget')
    return {'lots':float(lots),'estimated_risk':round(loss,2),'unrounded_risk':loss,
            'risk_cap':round(float(cap),2),'currency':currency}

def risk_check(plan, meta, max_spread, min_rr=1.5, max_open_positions=1, open_positions=0):
    reasons=[]
    try:
        max_spread=finite(max_spread,'max_spread')
        min_rr=finite(min_rr,'minimum reward/risk')
        if max_spread<=0 or min_rr<=0: reasons.append('invalid risk limits')
        if plan['direction'] not in ('BUY','SELL'): reasons.append('invalid direction')
        if 'allowed_directions' in meta and plan['direction'] not in meta['allowed_directions']:
            reasons.append('broker direction not permitted')
        spread=finite(meta.get('spread'),'spread')
        if spread < 0 or spread > max_spread: reasons.append('spread exceeds limit')
        if open_positions >= max_open_positions: reasons.append('position limit reached')
        e,s,t = [finite(plan[k],k) for k in ('entry','stop_loss','take_profit_1')]
        if min(e,s,t)<=0: reasons.append('nonpositive plan price')
        sign = 1 if plan['direction']=='BUY' else -1
        if (e-s)*sign <= 0 or (t-e)*sign <= 0: reasons.append('invalid stop or target side')
        elif (t-e)*sign/((e-s)*sign) < min_rr: reasons.append('reward/risk below minimum')
        point=finite(meta.get('point'),'point')
        stops=finite(meta.get('stops_level'),'stops_level')
        tick=finite(meta.get('tick_size'),'tick_size')
        if point<=0 or tick<=0 or stops<0: reasons.append('invalid broker stop metadata')
        if tick>0 and any(abs(value-price_round(value,tick))>max(1e-10,tick*1e-7) for value in (s,t)):
            reasons.append('stop or target off broker tick grid')
        if 'take_profit_2' in plan:
            t2=finite(plan['take_profit_2'],'take_profit_2')
            if t2<=0 or (t2-t)*sign<=0: reasons.append('invalid second target')
            if tick>0 and abs(t2-price_round(t2,tick))>max(1e-10,tick*1e-7): reasons.append('second target off broker tick grid')
        effective_stop_distance=abs(e-s)-spread
        if effective_stop_distance < stops*point:
            reasons.append('broker minimum stop distance after spread')
    except (KeyError,DataError) as exc:
        reasons.append(str(exc))
    return {'decision':'BLOCK' if reasons else 'PASS','reasons':reasons}

def build_plan(symbol,timeframe,direction,metrics,quote,meta,timestamp,reasons,invalidation=None):
    """Extracted V5 ATR/tick plan; optional strategy invalidation only widens stop."""
    tick=finite(meta.get('tick_size'),'tick_size')
    point=finite(meta.get('point'),'point')
    spread=finite(quote['ask'],'ask')-finite(quote['bid'],'bid')
    side=1 if direction=='BUY' else -1
    ep=quote['ask'] if direction=='BUY' else quote['bid']
    stop_dist=max(metrics['atr14']*1.5,finite(meta.get('stops_level'),'stops_level')*point+spread+tick)
    stop=ep-side*stop_dist
    if invalidation is not None:
        level=finite(invalidation,'strategy invalidation')
        if (ep-level)*side<=0:raise DataError('invalid strategy stop side')
        stop=min(stop,level) if side==1 else max(stop,level)
    stop=price_round(stop,tick,'down' if side==1 else 'up')
    distance=abs(ep-stop)
    return {'symbol':symbol,'direction':direction,'timeframe':timeframe,'entry':ep,'stop_loss':stop,
            'take_profit_1':price_round(ep+side*2*distance,tick,'up' if side==1 else 'down'),
            'take_profit_2':price_round(ep+side*3*distance,tick,'up' if side==1 else 'down'),
            'risk_reward':2.0,'invalidation':f'closed candle beyond {stop}',
            'timestamp':timestamp,'reasons':reasons}

def analyze(provider, symbol, timeframe='M15', balance=None, risk_pct=1.0, now=None, confirmation_timeframes=None):
    if not is_supported_symbol(symbol): raise DataError('unsupported symbol')
    if timeframe not in TIMEFRAMES: raise DataError('invalid timeframe')
    now = now or datetime.now(timezone.utc).timestamp()
    base={'symbol':symbol,'timeframe':timeframe,'provider':provider.name,'timestamp':datetime.fromtimestamp(now,timezone.utc).isoformat(), 'signal':'WAIT','plan':None,'reasons':[]}
    try:
        meta=provider.metadata(symbol)
        quote=provider.quote(symbol)
        if not meta or not quote: raise DataError('quote or metadata unavailable')
        for key in ('contract_size','tick_size','tick_value','point','volume_min','volume_max','volume_step'):
            if finite(meta.get(key),key)<=0: raise DataError('invalid '+key)
        if not meta.get('account_currency'): raise DataError('account currency unavailable')
        session=session_snapshot(datetime.fromtimestamp(now,timezone.utc), symbol, meta.get('trade_allowed'), meta.get('broker_hours'))
        base['session']=session
        if session['broker']['status'] not in ('OPEN','CLOSING_SOON'):
            raise DataError('broker market '+session['broker']['status'].lower())
        bid,ask=finite(quote.get('bid'),'bid'),finite(quote.get('ask'),'ask')
        qt=finite(quote.get('time'),'tick time')
        if bid <= 0 or ask <= bid: raise DataError('invalid bid/ask')
        if now-qt > 120 or qt>now+5: raise DataError('stale tick')
        spread=ask-bid
        meta={**meta,'spread':spread}
        max_spread=finite(meta.get('max_spread'),'max_spread')
        if max_spread<=0: raise DataError('invalid max_spread')
        if spread > max_spread: raise DataError('spread exceeds limit')
        bars=provider.candles(symbol,timeframe,220)
        last=validate_bars(bars,timeframe,now)
        if now-last-TIMEFRAMES[timeframe] > TIMEFRAMES[timeframe]*2: raise DataError('stale candles')
        primary_close=last+TIMEFRAMES[timeframe]
        a=indicators(bars)
        close=bars[-1]['close']
        trend='BUY' if close>a['ema20']>a['ema50']>a['ema200'] else 'SELL' if close<a['ema20']<a['ema50']<a['ema200'] else 'WAIT'
        confirmations=[]
        confirm=confirmation_timeframes if confirmation_timeframes is not None else ('H4',)
        if not confirm or len(confirm)>3 or len(set(confirm))!=len(confirm):
            raise DataError('invalid confirmation timeframes')
        for tf in confirm:
            if tf not in TIMEFRAMES or TIMEFRAMES[tf]<TIMEFRAMES[timeframe]:
                raise DataError('confirmation timeframe must be equal or higher')
            upper=bars if tf==timeframe else provider.candles(symbol,tf,220)
            upper=[b for b in upper if b['time']+TIMEFRAMES[tf]<=primary_close]
            upper_last=validate_bars(upper,tf,primary_close)
            if primary_close-upper_last-TIMEFRAMES[tf]>TIMEFRAMES[tf]*2:
                raise DataError('stale '+tf+' candles')
            b=a if tf==timeframe else indicators(upper)
            c=upper[-1]['close']
            direction='BUY' if c>b['ema50']>b['ema200'] else 'SELL' if c<b['ema50']<b['ema200'] else 'WAIT'
            confirmations.append({'timeframe':tf,'direction':direction,
                                  'closed_at':upper_last+TIMEFRAMES[tf]})
        directions={item['direction'] for item in confirmations}
        higher=next(iter(directions)) if len(directions)==1 else 'WAIT'
        base['confirmations']=confirmations
        from .strategies import candidates, resolve
        votes=candidates(bars,a)
        decision,why=resolve(votes,higher)
        from .structure import market_structure
        base['market_structure']=market_structure(bars,timeframe_seconds=TIMEFRAMES[timeframe])
        base['indicators']=a
        base['strategies']=votes
        base['reasons']=[f'trend={trend}',f'confirmations={higher}']+why
        if decision!='WAIT':
            plan=build_plan(symbol,timeframe,decision,a,quote,meta,base['timestamp'],base['reasons'])
            ep,stop=plan['entry'],plan['stop_loss']
            verdict=risk_check(plan,meta,max_spread)
            base['risk_verdict']=verdict
            if verdict['decision']=='PASS':
                if balance is not None:
                    plan['position_size']=size_lots(balance,risk_pct,ep,stop,meta,(lambda side,lots,e,s: provider.loss_for(symbol,side,lots,e,s)) if hasattr(provider,'loss_for') else getattr(provider,'calc_profit',None),decision,meta.get('account_currency'))
                base.update(signal=decision,plan=plan)
            else: base['reasons']+=verdict['reasons']
        base['data_status']='OK'
    except DataError as exc:
        base['data_status']='STALE' if 'stale' in str(exc) else 'DATA_UNAVAILABLE'
        base['reasons']=[str(exc)]
    return base

def backtest(bars, direction, entry_price, stop, target, spread=0, price_basis='bid'):
    """Single assumed fill after bars[0]; OHLC and levels share a stated basis."""
    from .microstructure import executable_prices, exit_on_bar
    if len(bars)<2 or len(bars)>10000: raise DataError('2..10000 candles required')
    model=executable_prices(direction,entry_price,stop,target,spread,price_basis)
    previous_time=None
    for i,bar in enumerate(bars):
        o,h,l,c=[finite(bar[k],k) for k in ('open','high','low','close')]
        if l<=0 or l>min(o,c) or h<max(o,c): raise DataError('invalid backtest candle')
        if 'time' in bar:
            stamp=finite(bar['time'],'time')
            if previous_time is not None and stamp<=previous_time: raise DataError('non-monotonic candle time')
            previous_time=stamp
        if i==0:
            if abs(c-entry_price)>max(1e-9,abs(entry_price)*1e-9):
                raise DataError('entry reference must equal first closed candle')
            continue
        result=exit_on_bar(model,bar)
        if result:
            net=result['net_r']
            return {'trades':1,'outcomes_r':[net],'result_r':net,'status':result['outcome'].upper(),
                    'exit_time':bar.get('time'),'bars_evaluated':i,'max_drawdown_r':max(0,-net),
                    'policy':'stop_first','entry_assumption':'filled_after_first_bar_close',
                    'price_basis':price_basis,'spread_assumption':spread}
    last=finite(bars[-1]['close'],'close')
    bid_last=last-(spread/2 if price_basis=='mid' else 0)
    exit_mark=bid_last if direction=='BUY' else bid_last+spread
    net=(exit_mark-model['entry'])*(1 if direction=='BUY' else -1)/model['risk']
    return {'trades':0,'outcomes_r':[],'result_r':net,'status':'OPEN','exit_time':None,
            'bars_evaluated':len(bars)-1,'max_drawdown_r':None,'policy':'stop_first',
            'entry_assumption':'filled_after_first_bar_close','price_basis':price_basis,
            'spread_assumption':spread}


def reward_risk_after_costs(plan,meta,commission_per_lot=0,slippage_price=0,calc_profit=None):
    """Account-currency net TP1 reward / adverse-stop loss, without a probability."""
    side=plan['direction'];sign=1 if side=='BUY' else -1
    entry,stop,target=(finite(plan[k],k) for k in ('entry','stop_loss','take_profit_1'))
    fee=finite(commission_per_lot,'commission per lot');slip=finite(slippage_price,'stop slippage')
    minimum=finite(meta.get('volume_min'),'minimum lot')
    if side not in ('BUY','SELL') or min(entry,stop,target,minimum)<=0 or min(fee,slip)<0 or (entry-stop)*sign<=0 or (target-entry)*sign<=0:
        raise DataError('invalid cost-adjusted plan')
    stop_execution=stop-sign*slip
    if stop_execution<=0:raise DataError('invalid adverse stop execution price')
    if calc_profit is not None:
        stop_pnl=finite(calc_profit(side,minimum,entry,stop_execution),'broker stop profit')
        target_pnl=finite(calc_profit(side,minimum,entry,target),'broker target profit')
        if stop_pnl>=0 or target_pnl<=0:raise DataError('broker stop/target profit signs invalid')
        original_stop_pnl=finite(calc_profit(side,minimum,entry,stop),'broker gross stop profit') if slip else stop_pnl
        if original_stop_pnl>=0:raise DataError('broker gross stop profit sign invalid')
        gross_loss=-original_stop_pnl;gross_reward=target_pnl
        loss=-stop_pnl+minimum*fee;reward=target_pnl-minimum*fee
    else:
        tick=finite(meta.get('tick_size'),'tick_size')
        loss_value=finite(meta.get('tick_value_loss') if meta.get('tick_value_loss') is not None else meta.get('tick_value'),'tick_value_loss')
        profit_value=finite(meta.get('tick_value_profit') if meta.get('tick_value_profit') is not None else meta.get('tick_value'),'tick_value_profit')
        if min(tick,loss_value,profit_value)<=0 or not meta.get('account_currency') or meta.get('tick_value_currency')!=meta.get('account_currency'):
            raise DataError('cost-adjusted currency conversion unverified')
        loss=(entry-stop_execution)*sign*minimum*loss_value/tick+minimum*fee
        reward=(target-entry)*sign*minimum*profit_value/tick-minimum*fee
        gross_loss=(entry-stop)*sign*minimum*loss_value/tick
        gross_reward=(target-entry)*sign*minimum*profit_value/tick
    if loss<=0:raise DataError('cost-adjusted loss unavailable')
    return {'gross_reward_risk':gross_reward/gross_loss,
            'gross_price_reward_risk':(target-entry)*sign/((entry-stop)*sign),
            'gross_loss_at_minimum_lot':gross_loss,'gross_reward_at_minimum_lot':gross_reward,
            'net_reward_risk':reward/loss,'net_reward_at_minimum_lot':reward,
            'loss_at_minimum_lot':loss,'currency':meta['account_currency'],
            'version':'forex-cost-netrr-v7-1','slippage_basis':'adverse stop only','commission_basis':'round_trip_per_lot'}
