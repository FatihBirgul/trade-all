"""Canonical private V6 decision: owned data -> real source analysis -> veto -> plan."""
from datetime import datetime,timezone
from decimal import Context,localcontext
from functools import lru_cache
from hashlib import sha256
import json
from typing import Literal
from pydantic import Field
from . import ROOT,__version__
from forex.unified import UnifiedAnalysis
from forex.core import DataError,finite,build_plan,risk_check,reward_risk_after_costs,TIMEFRAMES
from forex.policy import assess as risk_assess
from forex.contracts import canonical,provider_read
from .macro import information_context
from market_ai.v2.price_action import compute_price_action
from .market import acquire,MarketFailure,RequestCache
from . import technical,patterns,mtf,strategies
from .confluence import Observation,combine
from .schemas import EntryZone,RiskPolicy

SOURCE_A='fdcdd418d96d05e71453e70c1f39956dd1cfe9d5'
SOURCE_B='b69111608ea3c2e78609fd84a0d81dee2781c980'


class AnalysisReport(UnifiedAnalysis):
    schema_version:Literal['forex-analysis-6']='forex-analysis-6'
    engine_version:str=__version__
    integration_status:Literal['PRIVATE_INTEGRATED','PRIVATE_PARTIAL','UNAVAILABLE']='PRIVATE_INTEGRATED'
    regime:dict|None=None
    mtf:dict|None=None
    strategies:list[dict]=Field(default_factory=list)
    candidate_direction:Literal['BUY','SELL','WAIT']='WAIT'
    freshness:dict=Field(default_factory=dict)
    routing:dict|None=None
    gross_risk_reward:float|None=None
    net_risk_reward:float|None=None
    broker_schedule:dict=Field(default_factory=dict)
    entry_zone:EntryZone|None=None
    risk_policy:RiskPolicy|None=None


@lru_cache(maxsize=1)
def code_digest():
    paths=list((ROOT/'unified_forex').glob('*.py'))+list((ROOT/'vendor/trade_ai/backend/market_ai').rglob('*.py'))+list((ROOT/'vendor/day_trader/forex').glob('*.py'))
    return sha256(canonical({p.relative_to(ROOT).as_posix():sha256(p.read_bytes()).hexdigest() for p in sorted(paths,key=lambda x:x.relative_to(ROOT).as_posix())}).encode()).hexdigest()


def _observations(frame,metrics,action,candles,state):
    t=frame.bars[-1].close_time_ms//1000
    event=f'{frame.timeframe}:{t}:price'
    result=[]
    close=frame.bars[-1].close
    trend=mtf.direction(metrics,close)
    momentum='bullish' if metrics['rsi14_wilder']>50 and metrics['macd_histogram']>0 else 'bearish' if metrics['rsi14_wilder']<50 and metrics['macd_histogram']<0 else 'neutral'
    if state['regime'] in ('range','reversal'):
        trend='neutral'
        momentum='bullish' if metrics['rsi14_wilder']>metrics['previous_wilder_rsi'] else 'bearish' if metrics['rsi14_wilder']<metrics['previous_wilder_rsi'] else 'neutral'
    # Transparent magnitude normalizations, no floors/bonuses/probabilities.
    trend_strength=min(100,abs(close-metrics['ema50'])/metrics['atr14']*20) if metrics['atr14']>0 else 0
    for source,category,direction,strength in (('v5_ema_alignment','trend',trend,trend_strength),
                                              ('v5_wilder_macd','momentum',momentum,abs(metrics['rsi14_wilder']-50)*2)):
        result.append(Observation(source,event,category,direction,float(strength),True,0,frame.timeframe,t,'fx-evidence-scale-v1'))
    for e in action['structure'].get('events',[]):
        known=e['event_time_ms']//1000
        result.append(Observation('v2_structure',f'{frame.timeframe}:{known}:price','structure',e['direction'],
                                  0.0,True,0,frame.timeframe,known,action['version']))
    for p in candles['patterns']:
        if p.get('confirmed_at') is None or p['direction'] not in ('bullish','bearish') or p.get('state') in ('INVALIDATED','EXPIRED'):continue
        known=p['confirmed_at']//1000
        result.append(Observation('v2_candle:'+p['pattern_id'],f'{frame.timeframe}:{known}:price','pattern',p['direction'],
                                  float(p.get('strength',0)),True,p['age_bars'],frame.timeframe,known,p['pattern_version']))
    return result


class AnalysisEngine:
    """No persistent state, source imports or order permissions are optional fallbacks."""
    def analyze(self,provider,symbol,timeframe='M15',*,now=None,confirmations=None,trigger_timeframe=None,
                balance=None,risk_pct=1,records=(),commission_per_lot=0,slippage_price=0,
                enabled_strategies=None,information_provider=None,macro_event_window_minutes=None,strategy_parameters=None,structure_ledger=None):
        confirmations=tuple(confirmations) if confirmations is not None else ('D1',) if timeframe=='D1' else ('H4',)
        acquisition_error=None
        if now is None:
            provider=provider if isinstance(provider,RequestCache) else RequestCache(provider)
            try:
                provider.metadata(symbol);provider.quote(symbol)
                for tf in dict.fromkeys((timeframe,*confirmations,*((trigger_timeframe,) if trigger_timeframe else ()))):
                    provider.candles(symbol,tf,256)
            except Exception as exc:acquisition_error=exc
            # The live as-of is known after explicit reads. Replay supplied by
            # the caller never advances its historical cutoff.
            now=datetime.now(timezone.utc).timestamp()
        now=finite(now,'as of')
        params=dict(confirmations=confirmations,trigger_timeframe=trigger_timeframe,balance=balance,risk_pct=risk_pct,
                    records=records,commission_per_lot=commission_per_lot,slippage_price=slippage_price,
                    enabled_strategies=enabled_strategies,macro_event_window_minutes=macro_event_window_minutes)
        params['strategy_parameters']=strategy_parameters
        source_versions={'day_trader':SOURCE_A,'trade_ai':SOURCE_B,'target_code_sha256':code_digest(),
                         'parameters_sha256':sha256(canonical(params).encode()).hexdigest(),
                         'algorithms':technical.VERSIONS,'forex_strategies':strategies.VERSION,'risk':'forex-cost-netrr-v7-1'}
        body=AnalysisReport(analysis_id='',source_versions=source_versions,symbol=symbol,timeframe=timeframe,
                            provider=provider.name,as_of_utc=datetime.fromtimestamp(now,timezone.utc).isoformat(),
                            missing_capabilities=['real_volume','vwap','order_flow','funding','liquidations','verified_margin','verified_swap','verified_calendar'],
                            warnings=['Analytical candidate; no execution permission.','Synthetic tests do not establish market profitability.']).model_dump()
        body['information']=information_context(information_provider,as_of=datetime.fromtimestamp(now,timezone.utc))
        stage='market acquisition'
        try:
            with localcontext(Context(prec=60)):
                if acquisition_error is not None:raise acquisition_error
                view=acquire(provider,symbol,timeframe,now,confirmations,trigger_timeframe)
                p=view.snapshot.payload();m=p['metadata'];q=p['quote'];session=view.session()
                body.update(snapshot_id=view.snapshot.snapshot_id,market_type=p['market_type'],contract_type=p['contract_type'],
                            broker_symbol=p['broker_symbol'],market_status=session['broker']['status'],data_status='OK',
                            broker_schedule=session['broker']['provenance'],
                            freshness={'quote_age_seconds':now-q['time'],'primary_close_utc':p['decision_close_utc'],
                                       'candle_age_seconds':now-p['decision_close_utc'],'bid':q['bid'],'ask':q['ask'],
                                       'spread':q['ask']-q['bid'],'max_spread':m.get('max_spread')},
                            private_extension={'status':'AVAILABLE','source_sha':SOURCE_B,'bridge_version':'in-process-v6-owned-source'})
                if body['market_status'] in ('CLOSED','DISABLED'):
                    raise MarketFailure('MARKET_CLOSED','broker market closed or disabled')
                if body['market_status'] not in ('OPEN','CLOSING_SOON'):
                    raise MarketFailure('NO_TRADE','broker market hours unknown or not open')
                spread=q['ask']-q['bid'];meta={**m,'spread':spread}
                maximum=finite(m.get('max_spread'),'max_spread')
                if maximum<=0 or spread>maximum:raise MarketFailure('NO_TRADE','spread exceeds verified policy')
                if macro_event_window_minutes is not None:
                    if type(macro_event_window_minutes) is not int or not 1<=macro_event_window_minutes<=180:
                        raise MarketFailure('NO_TRADE','invalid macro risk window')
                    related={symbol[:3],symbol[-3:]}
                    events=body['information']['events']
                    if any(e['importance']=='HIGH' and e['currency'] in related and abs(datetime.fromisoformat(e['release_at']).timestamp()-now)<=macro_event_window_minutes*60 for e in events):
                        raise MarketFailure('NO_TRADE','declared high-impact macro event risk veto; coverage unverified')
                    from zoneinfo import ZoneInfo
                    if any(e['currency'] in related and e['date_start']<=datetime.fromtimestamp(now,ZoneInfo(e['source_timezone'])).date().isoformat()<=e['date_end']
                           for e in body['information'].get('date_only_events',[])):
                        raise MarketFailure('NO_TRADE','date-only official macro risk veto; release clock unknown; coverage unverified')
                stage='technical and price action'
                all_metrics={f.timeframe:technical.compute(f,finite(m.get('tick_size'),'tick_size')) for f in view.frames}
                frame=view.frame(timeframe);metrics=all_metrics[timeframe]
                action=compute_price_action(frame.bars,timeframe_ms=frame.duration_ms,as_of_ms=frame.as_of_ms,
                                            max_age_ms=frame.duration_ms*2,permitted_gaps=frame.permitted_gaps,atr14=metrics['atr14'])
                if any(action[k]['status']!='available' for k in ('structure','fvg','liquidity_sweep')):
                    raise MarketFailure('INSUFFICIENT_DATA','price action source quality unavailable')
                prior_action=compute_price_action(frame.bars[:-1],timeframe_ms=frame.duration_ms,
                                                  as_of_ms=frame.bars[-2].close_time_ms,max_age_ms=frame.duration_ms*2,
                                                  permitted_gaps=tuple(g for g in frame.permitted_gaps if g[1]<=frame.bars[-2].close_time_ms))
                state=technical.regime(frame,metrics,action,prior_action)
                stage='structure and patterns'
                tick=finite(m.get('tick_size'),'tick_size')
                if tick<=0:raise MarketFailure('NO_TRADE','invalid broker tick size')
                candles,charts=patterns.analyze(frame,metrics,tick)
                if candles['status']!='available' or charts['status']!='available':
                    raise MarketFailure('INSUFFICIENT_DATA','pattern source unavailable')
                body.update(indicators=metrics,regime=state,
                            trend={'direction':mtf.direction(metrics,frame.bars[-1].close),'ema20':metrics['ema20'],'ema50':metrics['ema50'],'ema200':metrics['ema200']},
                            momentum={k:metrics[k] for k in ('rsi14_wilder','rsi14_rolling','macd','macd_histogram','momentum_change')},
                            volatility={'atr14':metrics['atr14'],'normalized_atr':metrics['normalized_atr'],'regime':state['volatility']},
                            market_structure=patterns.structure(frame,metrics,action,tick,structure_ledger),candlestick_patterns=candles,chart_patterns=charts)
                stage='MTF and confluence'
                context=mtf.analyze(view,timeframe,all_metrics)
                body['mtf']=context;body['confirmations']=context['confirmations']
                evidence=_observations(frame,metrics,action,candles,state)
                body['confluence']=combine(evidence,as_of=int(p['decision_close_utc']))
                stage='strategy eligibility'
                assessments=strategies.assess(frame,metrics,state,action,prior_action,strategy_parameters) if strategy_parameters is not None else strategies.assess(frame,metrics,state,action,prior_action)
                body['strategies']=assessments
                body['strategy_candidates']=[{'strategy':a['strategy_id'],'direction':a['direction'],'reason':a['reason']}
                                             for a in assessments if a['status']=='CONFIRMED']
                active=session['sessions']
                label='overlap' if 'London_New_York_overlap' in active else 'london' if 'London' in active else 'new_york' if 'New_York' in active else 'asia' if 'Asian' in active else 'off_hours'
                route=strategies.route(assessments,regime=state['regime'],market=p['market_type'],session=label,
                                       capabilities=view.capabilities,quality_ok=True,enabled=enabled_strategies)
                from dataclasses import asdict
                body['routing']=asdict(route)
                if route.reason=='opposing_strategy_conflict' or body['confluence']['conflict_veto']:
                    body['strategy_conflicts']=sorted({a['direction'] for a in assessments if a['status']=='CONFIRMED'}|
                                                      {'BUY' if d=='bullish' else 'SELL' for d in body['confluence']['conflicting_directions']})
                    raise MarketFailure('WAIT','opposing strategy or confirmed directional price evidence')
                if route.status!='selected':raise MarketFailure('WAIT',route.reason)
                chosen=next(a for a in assessments if a['strategy_id']==route.strategy_id)
                direction=chosen['direction'];body['candidate_direction']=direction
                desired='bullish' if direction=='BUY' else 'bearish'
                if any(d!=desired for d in body['confluence']['directional_context']):
                    raise MarketFailure('WAIT','selected setup conflicts with confirmed directional price evidence')
                if any(d!=desired for d in context['higher_bias']) or any(d!=desired for d in context['lower_trigger']):
                    raise MarketFailure('WAIT','higher bias or lower trigger unavailable/conflicting')
                if state['volatility']=='HIGH_VOLATILITY':raise MarketFailure('NO_TRADE','high volatility risk veto')
                stage='broker plan and risk'
                from forex.core import price_round
                if any(abs(q[k]-price_round(q[k],tick))>max(1e-10,tick*1e-7) for k in ('bid','ask')):
                    raise MarketFailure('NO_TRADE','broker quote off executable tick grid')
                for key in ('contract_size','tick_value','point','volume_min','volume_max','volume_step'):
                    if finite(m.get(key),key)<=0:raise MarketFailure('NO_TRADE','invalid broker contract metadata: '+key)
                currency=m.get('account_currency')
                if not isinstance(currency,str) or len(currency)!=3 or not currency.isalpha() or currency!=currency.upper():
                    raise MarketFailure('NO_TRADE','account currency unavailable or malformed')
                plan=build_plan(symbol,timeframe,direction,metrics,q,meta,body['as_of_utc'],[chosen['reason']],chosen['invalidation'])
                check=risk_check(plan,meta,maximum)
                if check['decision']!='PASS':raise MarketFailure('NO_TRADE','; '.join(check['reasons']))
                raw_provider=provider.provider if isinstance(provider,RequestCache) else provider
                from forex.providers import FixtureProvider
                calc=(lambda side,lots,e,s:provider_read(raw_provider,'loss_for',symbol,side,lots,e,s)) if hasattr(raw_provider,'loss_for') and not isinstance(raw_provider,FixtureProvider) else None
                costs=reward_risk_after_costs(plan,meta,commission_per_lot,slippage_price,calc)
                if costs['net_reward_risk']<1.5:
                    raise MarketFailure('NO_TRADE','cost-adjusted reward/risk below minimum')
                body['gross_risk_reward']=costs['gross_reward_risk'];body['net_risk_reward']=costs['net_reward_risk']
                if balance is not None:
                    policy=risk_assess(plan,meta,balance,risk_pct,records,calc_profit=calc,account_currency=m['account_currency'],
                                       now=datetime.fromtimestamp(now,timezone.utc),commission_per_lot=commission_per_lot,slippage_price=slippage_price)
                    body['risk_policy']=policy
                    policy['cost_adjusted_plan']=costs
                    if policy['decision']!='PASS':raise MarketFailure('NO_TRADE','; '.join(policy['reasons']))
                    body['lot_size']=policy['sizing']['lots'];body['risk_amount']=policy['sizing']['estimated_risk']
                    body['trading_eligibility']='ELIGIBLE'
                else:
                    body['trading_eligibility']='NOT_EVALUATED';body['missing_capabilities'].append('account_risk_policy')
                body.update(final_decision=direction+'_CANDIDATE',legacy_signal=direction,
                            entry_zone={'low':plan['entry'],'high':plan['entry'],'price_side':'ask' if direction=='BUY' else 'bid'},
                            stop_loss=plan['stop_loss'],take_profit_1=plan['take_profit_1'],take_profit_2=plan['take_profit_2'],risk_reward=plan['risk_reward'],
                            decision_reasons=[chosen['reason'],'actual V2 QC/regime/pattern/confluence/router and V5 risk passed'])
        except MarketFailure as exc:
            body['final_decision']=exc.decision;body['decision_reasons']=[str(exc)]
            if exc.decision in ('INSUFFICIENT_DATA','STALE_DATA'):body['data_status']='STALE' if exc.decision=='STALE_DATA' else 'DATA_UNAVAILABLE'
        except (DataError,KeyError,ValueError,TypeError,OverflowError) as exc:
            reason=str(exc) if isinstance(exc,DataError) else 'invalid input or calculation contract'
            body['final_decision']='NO_TRADE' if stage=='broker plan and risk' else 'STALE_DATA' if 'stale' in reason else 'PROVIDER_UNAVAILABLE' if any(s in reason for s in ('unavailable:','failed','disconnected','no candles')) else 'INSUFFICIENT_DATA'
            body['data_status']='OK' if body['final_decision']=='NO_TRADE' else 'STALE' if body['final_decision']=='STALE_DATA' else 'DATA_UNAVAILABLE'
            body['decision_reasons']=[reason]
        except Exception:
            body.update(final_decision='INSUFFICIENT_DATA',data_status='DATA_UNAVAILABLE',integration_status='PRIVATE_PARTIAL',decision_reasons=['calculation unavailable at '+stage])
        if body['final_decision'] not in ('BUY_CANDIDATE','SELL_CANDIDATE'):
            body.update(legacy_signal='WAIT',entry_zone=None,stop_loss=None,take_profit_1=None,take_profit_2=None,
                        candidate_direction='WAIT',
                        risk_reward=None,gross_risk_reward=None,net_risk_reward=None,lot_size=None,risk_amount=None,trading_eligibility='BLOCKED')
        body['missing_capabilities']=sorted(set(body['missing_capabilities']))
        body['analysis_id']=sha256(canonical(body).encode()).hexdigest()
        return AnalysisReport.model_validate(body)
