"""In-memory Forex replay feeding the retained V2 train/select/freeze/test protocol."""
from dataclasses import dataclass,asdict
from bisect import bisect_right
from hashlib import sha256
from itertools import islice
from types import MappingProxyType
import copy
from datetime import datetime,timezone
from .engine import AnalysisEngine
from .market import TF
from .strategies import BUILTIN_IDS
from forex.contracts import canonical
from forex.core import DataError,TIMEFRAMES,finite,size_lots,price_round,reward_risk_after_costs
from forex.microstructure import executable_prices,exit_on_bar
from forex.sessions import broker_status
from forex.research import _bootstrap
from market_ai.v2.market_data_contract import Candle,Instrument,validate_series
from market_ai.v2.technical_adapter import TIMEFRAME_MS
from .costs import at_rules

REVERSE={v:k for k,v in TF.items()}


@dataclass(frozen=True,init=False)
class HistoricalDataset:
    frames:object
    identity:Instrument
    source:str
    data_kind:str
    data_version:str
    digest:str
    execution_timeframe:str
    _rules_json:str
    _declaration_json:str
    _epochs_json:str
    ask_frames:object
    def __init__(self,frames,rules,*,data_kind,data_version,declaration=None,rule_epochs=(),ask_frames=None):
        from .provenance import DatasetDeclaration,normalize_epochs
        if data_kind not in ('synthetic','historical') or not isinstance(data_version,str) or not data_version:
            raise ValueError('Explicit dataset provenance required')
        if not isinstance(frames,dict) or not frames or not set(frames)<=set(REVERSE):
            raise ValueError('Supported Forex research frames required')
        from .market import schedule_contract
        if not isinstance(rules,dict) or not schedule_contract(rules)['policy_accepted']:
            raise ValueError('Explicit accepted declared historical broker schedule required')
        epochs=normalize_epochs(rule_epochs)
        owned={};remaining=6000;identity=source=None
        for tf,rows in frames.items():
            bars=tuple(islice(rows,min(2001,remaining+1)))
            if not bars or len(bars)>2000:raise ValueError('Dataset frame exceeds2000 bars')
            remaining-=len(bars)
            if remaining<0:raise ValueError('Dataset exceeds6000 total bars')
            gaps=[]
            for a,b in zip(bars,bars[1:]):
                if a.close_time_ms!=b.open_time_ms:
                    if not 0<b.open_time_ms-a.close_time_ms<=TIMEFRAME_MS[tf]*500:raise ValueError('Invalid historical gap')
                    for stamp in range(a.close_time_ms,b.open_time_ms,60000):
                        from .provenance import rules_at
                        at_rules=rules_at(epochs,stamp) if epochs else rules
                        state=broker_status(datetime.fromtimestamp(stamp/1000,timezone.utc),'',at_rules.get('trade_allowed'),at_rules.get('broker_hours'))
                        if state['status']!='CLOSED':raise ValueError('Historical open-session candle gap')
                    gaps.append((a.close_time_ms,b.open_time_ms))
            q=validate_series(bars,timeframe_ms=TIMEFRAME_MS[tf],as_of_ms=bars[-1].close_time_ms,max_age_ms=0,permitted_gaps=tuple(gaps))
            if not q.ok:raise ValueError('Invalid historical closed candle batch')
            identity=identity or bars[0].instrument;source=source or bars[0].source
            if any(b.instrument!=identity or b.source!=source or b.volume_kind=='real' for b in bars):
                raise ValueError('Historical Forex identity/source/volume mismatch')
            owned[tf]=bars
        if (identity.market,identity.contract_type) not in (('forex_spot','spot'),('gold_spot','spot'),('cfd','cfd')) or identity.price_kind!='bid':
            raise ValueError('Explicit bid Forex/CFD identity required')
        expected_identity={'symbol':identity.symbol,'broker_server':identity.venue,'market_type':identity.market,
                           'contract_type':identity.contract_type,'price_kind':'bid','source':source}
        for metadata in (rules,*(e['rules'] for e in epochs)):
            if any(metadata.get(k)!=v for k,v in expected_identity.items()):raise ValueError('Historical rule broker/instrument/source identity mismatch')
            if metadata.get('account_currency')!=rules.get('account_currency') or metadata.get('tick_value_currency')!=metadata.get('account_currency'):
                raise ValueError('Historical account currency/conversion mismatch; redenomination model unavailable')
        raw_rules=canonical(rules)
        asks={}
        if ask_frames is not None:
            if not isinstance(ask_frames,dict):raise ValueError('Explicit paired ask frames required')
            from .data_sides import paired_frames
            asks={tf:tuple(islice(rows,2001)) for tf,rows in ask_frames.items()}
            if sum(map(len,asks.values()))+sum(map(len,owned.values()))>6000:raise ValueError('Paired dataset exceeds6000 total bars')
            paired_frames(owned,asks)
        decl=DatasetDeclaration.model_validate(declaration or {'retrieved_at':datetime.fromtimestamp(max(b[-1].close_time_ms for b in owned.values())/1000,timezone.utc)}).model_dump(mode='json')
        if datetime.fromisoformat(decl['retrieved_at'].replace('Z','+00:00')).timestamp()*1000<max(b[-1].close_time_ms for b in owned.values()):
            raise ValueError('Dataset retrieval precedes a supplied closed candle')
        for key,value in dict(frames=MappingProxyType(owned),_rules_json=raw_rules,
                              ask_frames=MappingProxyType(asks),
                              _declaration_json=canonical(decl),_epochs_json=canonical(epochs),
                              identity=identity,source=source,data_kind=data_kind,
                              data_version=data_version,execution_timeframe=min(owned,key=TIMEFRAME_MS.get),
                              digest=sha256(canonical({'frames':{tf:[asdict(b) for b in rows] for tf,rows in owned.items()},
                                                       'rules':rules,'data_kind':data_kind,'data_version':data_version,
                                                       'declaration':decl,'rule_epochs':epochs,
                                                       **({'ask_frames':{tf:[asdict(b) for b in rows] for tf,rows in asks.items()}} if asks else {})}).encode()).hexdigest()).items():
            object.__setattr__(self,key,value)

    @property
    def rules(self):
        return MappingProxyType(self.metadata())

    def metadata(self,at_ms=None):
        import json
        if at_ms is not None and self.rule_epochs:
            from .provenance import rules_at
            return rules_at(self.rule_epochs,at_ms)
        return json.loads(self._rules_json)

    @property
    def declaration(self):
        import json
        return json.loads(self._declaration_json)

    @property
    def rule_epochs(self):
        import json
        return json.loads(self._epochs_json)


def dataset_from_provider(provider,symbol,timeframe,count=500,confirmations=(),data_kind='synthetic'):
    if type(count) is not int or not 251<=count<=2000:raise ValueError('251..2000 research candles required')
    meta=provider.metadata(symbol)
    instrument=Instrument(symbol,meta['market_type'],meta.get('broker_server') or meta['venue'],'bid',meta['contract_type'],symbol[-3:])
    frames={}
    for tf in dict.fromkeys((timeframe,*confirmations)):
        rows=provider.candles(symbol,tf,count)
        if not isinstance(rows,(list,tuple)) or len(rows)>count or (tf==timeframe and len(rows)<251):
            raise ValueError('Insufficient or excessive requested historical candles')
        if any(type(b.get('time')) is not int or b.get('volume_kind','tick' if 'tick_volume' in b else 'unavailable') not in ('tick','unavailable') or b.get('symbol',symbol)!=symbol or b.get('source',meta.get('source',provider.name))!=meta.get('source',provider.name) for b in rows):
            raise ValueError('Invalid raw historical identity/time/volume')
        frames[TF[tf]]=tuple(Candle(instrument,int(b['time']*1000),int((b['time']+TIMEFRAMES[tf])*1000),b.get('is_final',True),
                                       b['open'],b['high'],b['low'],b['close'],b.get('tick_volume'),
                                       'tick' if 'tick_volume' in b else 'unavailable',meta.get('source',provider.name)) for b in rows)
    return HistoricalDataset(frames,meta,data_kind=data_kind,data_version='declared-forex-bars-v6-1')


@dataclass(frozen=True)
class ResearchConfig:
    timeframe:str
    start_ms:int
    end_ms:int
    timeframes:tuple[str,...]=()
    simulate_orders:bool=True
    analysis_every_bars:int=20
    max_events:int=2000
    max_analyses:int=100
    audit_every_bars:int=100
    strategy_ids:tuple[str,...]=tuple(sorted(BUILTIN_IDS))
    seed:int=12
    execution_ms:int=900000
    def __post_init__(self):
        if (self.timeframe not in REVERSE or type(self.timeframes) is not tuple or not set(self.timeframes)<=set(REVERSE) or len(self.timeframes)>3
                or type(self.start_ms) is not int or type(self.end_ms) is not int or not 0<=self.start_ms<self.end_ms
                or type(self.analysis_every_bars) is not int or not 1<=self.analysis_every_bars<=5000
                or self.simulate_orders is not True or type(self.max_events) is not int or not 1<=self.max_events<=5000 or type(self.max_analyses) is not int or not 1<=self.max_analyses<=100
                or type(self.strategy_ids) is not tuple or not self.strategy_ids or len(set(self.strategy_ids))!=len(self.strategy_ids) or not set(self.strategy_ids)<=BUILTIN_IDS or type(self.seed) is not int or not 0<=self.seed<=2**32-1 or type(self.execution_ms) is not int or self.execution_ms<=0):
            raise ValueError('Invalid bounded Forex research protocol')


class HistoricalProvider:
    name='historical-fixture-only'
    simulation_only=True
    def __init__(self,dataset,now,spread_bps):
        self.dataset=dataset;self.now=now;self.spread_bps=spread_bps
        self.ends={tf:[b.close_time_ms for b in rows] for tf,rows in dataset.frames.items()}
    def metadata(self,symbol):return self.dataset.metadata(self.now)
    def candles(self,symbol,timeframe,count=256):
        rows=self.dataset.frames[TF[timeframe]];end=bisect_right(self.ends[TF[timeframe]],self.now)
        return [dict(time=b.open_time_ms//1000,open=b.open,high=b.high,low=b.low,close=b.close,
                     **({'tick_volume':b.volume} if b.volume_kind=='tick' else {})) for b in rows[max(0,end-count):end]]
    def quote(self,symbol):
        rows=self.dataset.frames[self.dataset.execution_timeframe]
        end=bisect_right(self.ends[self.dataset.execution_timeframe],self.now)
        if not end:raise DataError('historical quote unavailable')
        price=rows[end-1].close;tick=self.dataset.metadata(self.now)['tick_size']
        spread=at_rules(self.dataset.metadata(self.now),price,[0,self.spread_bps,0])['spread']
        if self.dataset.ask_frames:spread=self.dataset.ask_frames[self.dataset.execution_timeframe][end-1].close-price
        return {'bid':price,'ask':price+spread,'time':rows[end-1].close_time_ms/1000}


def run_backtest(dataset,config,*,fee_bps='5',spread_bps='2',slippage_bps='1',profile=None,cancellation=None):
    from market_ai.v2.research import summarize,money,number
    from decimal import Decimal
    if not isinstance(dataset,HistoricalDataset) or not isinstance(config,ResearchConfig) or profile is not None:
        raise ValueError('Validated Forex dataset/config required; profile integration unavailable')
    costs=[finite(v,k) for k,v in (('commission',fee_bps),('spread',spread_bps),('slippage',slippage_bps))]
    if any(not 0<=v<=100 for v in costs):raise ValueError('Fixed cost assumptions0..100bps required')
    base=dataset.frames[dataset.execution_timeframe]
    events=[(i,b) for i,b in enumerate(base) if b.open_time_ms>=config.start_ms and b.close_time_ms<=config.end_ms]
    if not events or len(events)>config.max_events or events[0][1].open_time_ms!=config.start_ms or events[-1][1].close_time_ms!=config.end_ms:
        raise ValueError('Exact bounded execution window required')
    expected=sum((j%config.analysis_every_bars==0) for j in range(len(events)))
    if expected>config.max_analyses:raise ValueError('Analysis resource budget exceeded')
    equity=10000.0;curve=[{'at_ms':config.start_ms,'equity_quote':money(Decimal(str(equity)))}]
    closed=[];position=None;engine=AnalysisEngine();evaluations=0;exposure=0
    meta=dataset.metadata();tick=finite(meta.get('tick_size'),'tick size')
    if tick<=0:raise ValueError('Invalid historical tick size')
    value=finite(meta.get('tick_value'),'tick value')/tick
    if min(tick,value)<=0 or not meta.get('account_currency') or meta.get('tick_value_currency')!=meta.get('account_currency'):
        raise ValueError('Historical account-currency tick conversion unavailable')
    for key in ('tick_value_profit','tick_value_loss'):
        if meta.get(key) is not None and finite(meta[key],key)<=0:raise ValueError('Invalid historical PnL tick value')
    for j,(index,bar) in enumerate(events):
        if cancellation is not None:cancellation.check()
        if any(bar.open_time_ms<e[k]<bar.close_time_ms for e in dataset.rule_epochs for k in ('effective_from_ms','effective_to_ms')):
            raise ValueError('Historical contract boundary inside execution candle is unsupported')
        current=dataset.metadata(bar.open_time_ms)
        if position is not None and any(current.get(k)!=meta.get(k) for k in ('tick_size','tick_value','tick_value_profit','tick_value_loss','contract_size','account_currency','leverage','margin_rate','swap_mode')):
            raise ValueError('Contract change across open position requires an explicit settlement model')
        meta=current;tick=finite(meta.get('tick_size'),'tick size')
        if tick<=0:raise ValueError('Invalid historical tick size')
        value=finite(meta.get('tick_value'),'tick value')/tick
        if min(tick,value)<=0 or meta.get('tick_value_currency')!=meta.get('account_currency'):raise ValueError('Historical currency/tick rules unavailable')
        if position is None and j%config.analysis_every_bars==0:
            if equity<=0:break
            provider=HistoricalProvider(dataset,bar.open_time_ms,costs[1])
            reference=base[index-1].close if index else bar.open
            setup_cost=at_rules(meta,reference,costs)
            result=engine.analyze(provider,dataset.identity.symbol,REVERSE[config.timeframe],now=bar.open_time_ms/1000,
                                  confirmations=tuple(REVERSE[tf] for tf in config.timeframes) or (REVERSE[config.timeframe],),
                                  enabled_strategies=config.strategy_ids,commission_per_lot=setup_cost['commission_account_per_lot'],
                                  slippage_price=setup_cost['slippage'])
            evaluations+=1
            if result.final_decision in ('BUY_CANDIDATE','SELL_CANDIDATE'):
                direction=result.legacy_signal;sign=1 if direction=='BUY' else -1
                fill_cost=at_rules(meta,bar.open,costs)
                spread=fill_cost['spread'];slip=fill_cost['slippage'];fee=fill_cost['commission_account_per_lot'];commission=fee/value
                if dataset.ask_frames:spread=dataset.ask_frames[dataset.execution_timeframe][index].open-bar.open
                # Keep levels known before this opening. SELL plan levels are
                # executable ask levels; the bid chart triggers one spread lower.
                stop=result.stop_loss-(spread if sign==-1 else 0)
                target=result.take_profit_1-(spread if sign==-1 else 0)
                try:
                    model=executable_prices(direction,bar.open,stop,target,spread,'bid',slip)
                    model['entry']=price_round(model['entry'],tick,'up' if sign==1 else 'down')
                    model['risk']=(model['entry']-model['stop_exit'])*sign
                    model['reward']=(model['target_exit']-model['entry'])*sign
                    net=reward_risk_after_costs({'direction':direction,'entry':model['entry'],'stop_loss':model['stop_exit'],
                                                'take_profit_1':model['target_exit']},meta,commission*value,slip)
                    if net['net_reward_risk']<1.5:continue
                    size=size_lots(equity,1,model['entry'],model['stop_exit'],meta,side=direction,
                                   commission_per_lot=commission*value,slippage_price=slip)
                except DataError:continue
                position={'model':model,'lots':size['lots'],'risk_amount':size['unrounded_risk'],'commission':commission,'slip':slip,
                          'entry_fee_per_lot':fee/2,'entry_reference':bar.open,'cost_version':fill_cost['version'],
                          'direction':direction,'net_reward_risk':net['net_reward_risk'],
                          'entry_index':index,'entry_time':bar.open_time_ms,'known_at':bar.open_time_ms,
                          'strategy':result.routing['strategy_id'],'regime':result.regime['regime']}
        if position is not None:
            exposure+=1
            exit_cost=at_rules(meta,position['entry_reference'],costs)
            total_fee=position['entry_fee_per_lot']+exit_cost['commission_account_per_lot']/2
            execution_model=dict(position['model']);execution_model['spread']=exit_cost['spread']
            if position['direction']=='SELL':
                execution_model['stop_bid']=execution_model['stop_exit']-exit_cost['spread']
                execution_model['target_bid']=execution_model['target_exit']-exit_cost['spread']
            exit_bar=bar
            if dataset.ask_frames:
                execution_model['spread']=0
                execution_model['stop_bid']=execution_model['stop_exit'];execution_model['target_bid']=execution_model['target_exit']
                if position['direction']=='SELL':exit_bar=dataset.ask_frames[dataset.execution_timeframe][index]
            outcome=exit_on_bar(execution_model,asdict(exit_bar),0,total_fee/value)
            if outcome and outcome['outcome']=='stop':
                outcome=exit_on_bar(execution_model,asdict(exit_bar),exit_cost['slippage'],total_fee/value)
            if outcome:
                # Realized conversion uses the PnL-side tick value. Bps fee is
                # charged once per completed trade, in account currency/lot.
                gross=(outcome['exit_price']-position['model']['entry'])*(1 if position['direction']=='BUY' else -1)
                if outcome['outcome']=='stop':gross-=exit_cost['slippage']
                pnl_value=meta.get('tick_value_profit' if gross>0 else 'tick_value_loss')
                factor=(pnl_value if pnl_value is not None else meta['tick_value'])/tick
                pnl=(gross*factor-total_fee)*position['lots']
                equity+=pnl
                closed.append({k:position[k] for k in ('entry_index','entry_time','known_at','strategy','regime','direction','lots','risk_amount','net_reward_risk')}|
                              {'exit_index':index,'exit_time':bar.close_time_ms,'net_pnl_quote':money(Decimal(str(pnl))),
                               'round_trip_commission_account':total_fee*position['lots'],
                               'entry_fee_account':position['entry_fee_per_lot']*position['lots'],
                               'exit_fee_account':exit_cost['commission_account_per_lot']/2*position['lots'],
                               'swap_status':'UNAVAILABLE','intrabar_ambiguous':exit_bar.high>=execution_model['target_bid'] and exit_bar.low<=execution_model['stop_bid'] if position['direction']=='BUY' else exit_bar.high>=execution_model['stop_bid'] and exit_bar.low<=execution_model['target_bid'],
                               'ambiguous':False,'r':pnl/position['risk_amount'],'holding_bars':index-position['entry_index']+1,
                               'outcome':outcome['outcome']})
                position=None
        mark=equity
        if position is not None:
            model=position['model'];sign=1 if model['direction']=='BUY' else -1
            exit_mark=bar.close if sign==1 else bar.close+exit_cost['spread']
            if dataset.ask_frames and sign==-1:exit_mark=dataset.ask_frames[dataset.execution_timeframe][index].close
            gross=(exit_mark-model['entry'])*sign
            mark_value=meta.get('tick_value_profit' if gross>0 else 'tick_value_loss')
            mark+=(gross*(mark_value/tick if mark_value is not None else value)-total_fee)*position['lots']
        curve.append({'at_ms':bar.close_time_ms,'equity_quote':money(Decimal(str(mark)))})
    metrics=summarize(curve,closed,seed=config.seed)
    metrics.update(exposure_fraction=exposure/len(events),average_r=sum(t['r'] for t in closed)/len(closed) if closed else None)
    metrics['sample_warning']='fewer_than30_closed_trades' if len(closed)<30 else 'selection_dependence_and_unverified_market_data'
    breakdown={field:{name:summarize([], [t for t in closed if t[field]==name],seed=config.seed)
                      for name in sorted({t[field] for t in closed})} for field in ('strategy','regime','direction')}
    from .provenance import describe
    from .data_sides import describe as side_evidence
    return {'version':'fx-backtest-v9-1','integrity_status':'PASS','validation_status':'MECHANICS_ONLY','events':len(events),
            'dataset_manifest':describe(dataset),'cost_model':{'fee_bps':costs[0],'spread_bps':costs[1],'slippage_bps':costs[2],
                'spread_application':'PAIRED_OHLC_SIDES_OVERRIDE_MODEL' if dataset.ask_frames else 'DECLARED_MODELLED_SPREAD',
                'version':'fx-dated-costs-v8-1','dated_overrides':'DECLARED; entry_half_fee_plus_exit_half_fee; current spread/stop slippage',
                'commission_basis':'one_round_trip_per_closed_trade','slippage_basis':'entry_and_stop_exit_only','swap':'UNAVAILABLE','margin':'UNAVAILABLE'},
            'orders':0,'journal_records':0,'domain_events':0,'fees_quote':sum(t['round_trip_commission_account'] for t in closed),'open_positions':int(position is not None),
            'price_evidence':side_evidence(dataset),
            'execution_mode':'SYNTHETIC_MECHANICAL_TEST' if dataset.data_kind=='synthetic' else 'DECLARED_COST_REPLAY' if dataset.ask_frames else 'BID_ONLY_MODELLED_SPREAD',
            'monetary_unit':'ACCOUNT_CURRENCY','account_currency':meta['account_currency'],'quote_fields_are_legacy_aliases':True,
            'ambiguous_closed_trades':sum(t['intrabar_ambiguous'] for t in closed),
            'ambiguous_positions':0,'pending_orders':0,'equity_curve':curve,'closed_trades':closed,
            'metrics':metrics,'audit':{'status':'PASS','kind':'in_memory_chronology_and_single_exit'},'checkpoints':[],
            'breakdowns':breakdown,'analyses':evaluations,'dataset_digest':dataset.digest,'data_kind':dataset.data_kind,
            'monte_carlo':_bootstrap(closed,config.seed),'evidence_status':'INSUFFICIENT_EVIDENCE','forward_validated':False,
            'real_execution':False,'simulation_basis':'next-open bid OHLC, fixed bps costs, stop-first, broker grid, 1% equity risk',
            'warning':'Source/license/point-in-time rules/costs unverified; stop-first OHLC ambiguity is an assumption, not observed execution.'}


def run_oos(dataset,config,manifest=None,registry=None,cancellation=None,preregistration=None,trial_registry=None,campaign_id=None):
    from market_ai.v2.walk_forward import run_walk_forward
    token=None;protocol_id=None
    if preregistration is not None:
        from .research_protocol import verify
        protocol_id=verify(preregistration,dataset,config)
    if trial_registry is not None:
        if protocol_id is None:raise ValueError('Trial accounting requires frozen preregistration')
        token=trial_registry.begin(campaign_id,protocol_id)
    try:
        result=run_walk_forward(dataset,config,manifest=manifest,cancellation=cancellation)
        from .provenance import describe
        result['dataset_manifest']=describe(dataset)
        result['preregistration']={'status':'LOCAL_INPUT_BOUND' if protocol_id else 'NOT_PREREGISTERED',
            'protocol_id':protocol_id,'external_attestation':False}
        if cancellation is not None:cancellation.check()
        if registry is not None:result['registry']=registry.record(result)
    except Exception as exc:
        from .research_control import ResearchCancelled
        if token:trial_registry.finish(token,'CANCELLED' if isinstance(exc,ResearchCancelled) else 'FAILED')
        raise
    if token:result['cross_run_disclosure']=trial_registry.finish(token,'COMPLETED')
    return result
