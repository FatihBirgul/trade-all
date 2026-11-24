"""Explicit price-only Forex variants; original crypto volume gates remain intact."""
from dataclasses import dataclass
from forex.strategies import candidates as v5_candidates
from market_ai.v2.strategy_router import StrategySpec,route_strategy,RouteDecision
from market_ai.v2.price_action import compute_price_action
from pydantic import BaseModel,ConfigDict,Field
from hashlib import sha256

TREND='fx_trend_momentum_v6'
RANGE='fx_range_reversion_v6'
BREAKOUT='fx_confirmed_breakout_v6'
SWEEP='fx_failed_breakout_v6'
MARKETS=frozenset({'forex_spot','gold_spot','cfd'})
STRATEGIES=tuple(StrategySpec(name,frozenset(regimes),MARKETS,frozenset({'ohlc','broker_calendar'}),priority=priority,version='2')
                for name,regimes,priority in ((TREND,{'trend','breakout'},10),(RANGE,{'range'},20),
                                              (BREAKOUT,{'trend','breakout'},30),(SWEEP,{'range','trend','reversal'},40)))
BUILTIN_IDS=frozenset(s.strategy_id for s in STRATEGIES)
VERSION='fx-price-setups-v7-1'


class Parameters(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True,allow_inf_nan=False,strict=True)
    version:str=Field(default='fx-price-params-v7-1',pattern='^fx-price-params-v7-1$')
    range_bars:int=Field(default=20,ge=10,le=50)
    minimum_range_atr:float=Field(default=3,ge=2,le=10)
    range_efficiency_max:float=Field(default=.3,gt=0,le=.5)
    breakout_atr_buffer:float=Field(default=.25,ge=.1,le=1)
    max_extension_atr:float=Field(default=3,ge=1,le=5)
    max_setup_age_bars:int=Field(default=1,ge=0,le=2)


def assess(frame,metrics,regime,price_action,prior_action=None,parameters=None):
    parameters=Parameters.model_validate(parameters or {})
    bars=frame.bars
    rows=[dict(time=b.open_time_ms//1000,open=b.open,high=b.high,low=b.low,close=b.close) for b in bars]
    legacy=v5_candidates(rows,metrics)
    atr=metrics['atr14'];close=bars[-1].close;previous=bars[-2]
    rsi,prior=metrics['rsi14_wilder'],metrics['previous_wilder_rsi']
    result={s.strategy_id:{'strategy_id':s.strategy_id,'version':s.version,'family':s.strategy_id,
                           'status':'WAIT','direction':'WAIT','reason':'price confirmation missing',
                           'required_capabilities':['ohlc','broker_calendar'],'known_at':bars[-1].close_time_ms//1000,
                           'invalidation':None,'rule_version':VERSION} for s in STRATEGIES}
    for name,row in result.items():
        row['setup_id']=sha256(f'{bars[0].instrument}|{frame.timeframe}|{name}|{bars[-1].close_time_ms}'.encode()).hexdigest()[:24]
        row['parameters']=parameters.model_dump()
    if frame.as_of_ms-bars[-1].close_time_ms>parameters.max_setup_age_bars*frame.duration_ms:
        for row in result.values():row['reason']='setup exceeded maximum age'
        return list(result.values())
    if atr is None or atr<=0:return list(result.values())
    def confirm(name,direction,condition,reason,invalidation=None):
        row=result[name]
        spec=next(s for s in STRATEGIES if s.strategy_id==name)
        if regime['regime'] not in spec.regimes:
            row['reason']='regime not eligible';return
        if condition:
            row.update(status='CONFIRMED',direction=direction,reason=reason,invalidation=invalidation)
    trend=[v for v in legacy if v['strategy'] in ('trend_following','pullback')]
    directions={v['direction'] for v in trend}
    confirm(TREND,next(iter(directions)) if len(directions)==1 else 'WAIT',len(directions)==1,
            'retained V5 EMA/Wilder-RSI/MACD continuation or confirmed pullback')
    width_bars=parameters.range_bars
    upper=max(b.high for b in bars[-width_bars-2:-2]);lower=min(b.low for b in bars[-width_bars-2:-2])
    width=upper-lower;mid=(upper+lower)/2
    path=sum(abs(bars[i].close-bars[i-1].close) for i in range(len(bars)-width_bars-1,len(bars)-1))
    efficiency=abs(bars[-2].close-bars[-width_bars-2].close)/path if path else 0
    bounded=width>=parameters.minimum_range_atr*atr and efficiency<=parameters.range_efficiency_max
    up=previous.low<=lower+width*.25 and close>previous.high and close<mid and rsi>prior and rsi<45
    down=previous.high>=upper-width*.25 and close<previous.low and close>mid and rsi<prior and rsi>55
    confirm(RANGE,'BUY' if up else 'SELL',bounded and up!=down,
            'price-only range edge rejection, next close and Wilder RSI recovery; not crypto-volume equivalent',
            min(previous.low,bars[-1].low)-atr*.25 if up else max(previous.high,bars[-1].high)+atr*.25)
    buffer=atr*parameters.breakout_atr_buffer
    up=previous.close>upper+buffer and close>previous.close and 55<=rsi<=80 and rsi>prior
    down=previous.close<lower-buffer and close<previous.close and 20<=rsi<=45 and rsi<prior
    displacement=abs(previous.close-previous.open)>=atr*.5
    extension=abs(close-(upper if up else lower))<=atr*parameters.max_extension_atr
    confirm(BREAKOUT,'BUY' if up else 'SELL',up!=down and displacement and extension,
            'two closed range breaks + displacement + non-extended Wilder momentum; no volume substitution',
            upper-buffer if up else lower+buffer)
    prior_gaps=tuple(g for g in frame.permitted_gaps if g[1]<=previous.close_time_ms)
    if prior_action is None:
        prior_action=compute_price_action(bars[:-1],timeframe_ms=frame.duration_ms,as_of_ms=previous.close_time_ms,
                                         max_age_ms=frame.duration_ms*2,permitted_gaps=prior_gaps)
    sweep=prior_action['liquidity_sweep'].get('direction','neutral')
    up=sweep=='bullish' and close>previous.high and close>bars[-1].open and rsi>prior and rsi<50
    down=sweep=='bearish' and close<previous.low and close<bars[-1].open and rsi<prior and rsi>50
    follow=abs(close-bars[-1].open)>=atr*.25
    confirm(SWEEP,'BUY' if up else 'SELL',up!=down and follow,
            'actual V2 prior sweep/reclaim plus next closed price-body and Wilder recovery; OHLC heuristic',
            previous.low-buffer if up else previous.high+buffer)
    return list(result.values())


def route(assessments,*,regime,market,session,capabilities,quality_ok,risk_ok=True,enabled=None):
    rows={a['strategy_id']:a for a in assessments}
    specs=tuple(s for s in STRATEGIES if enabled is None or s.strategy_id in enabled)
    if enabled is not None and (not enabled or not set(enabled)<=BUILTIN_IDS):
        raise ValueError('Unknown or empty strategy selection')
    eligible=[s for s in specs if rows[s.strategy_id]['status']=='CONFIRMED']
    directions={rows[s.strategy_id]['direction'] for s in eligible if regime in s.regimes and market in s.markets
                and s.required_capabilities<=capabilities}
    if len(directions)>1:
        return RouteDecision('wait',None,'opposing_strategy_conflict',tuple(sorted(s.strategy_id for s in eligible)))
    return route_strategy(eligible,regime=regime,market=market,session=session,capabilities=capabilities,
                          data_quality_ok=quality_ok,risk_gate_ok=risk_ok)
