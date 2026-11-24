"""Bounded V2 historical research. No network and no persistent DB destination.

Reuses AnalysisService, PaperLedger, domain journal and independent audits in a
new temporary fixture database. Dataset provenance is retained separately; a
simulation is never labelled a live quote or forward-validated strategy.
"""
from bisect import bisect_right
from collections import Counter
from dataclasses import asdict, dataclass
from decimal import Decimal as D, Context, localcontext, ROUND_HALF_EVEN, InvalidOperation
from hashlib import sha256
from itertools import islice
import json
from pathlib import Path
from random import Random
from tempfile import TemporaryDirectory
from types import MappingProxyType

from .market_data_contract import Candle, Instrument, validate_series
from .technical_adapter import TIMEFRAME_MS
from .spot_provider import ProviderUnavailable
from .strategies import BUILTIN_IDS, STRATEGIES
from .product_db import ProductDatabase
from .paper_ledger import PaperLedger
from .analysis_service import AnalysisService, VERSION as ANALYSIS_VERSION
from .api_models import AnalyzeRequest
from .decision_record import _canonical
from .errors import V2Error
from .paper_audit import audit_database
from .pattern_research import detect_patterns, confluence_evidence
from .technical_research import compute_methods
from market_ai.engines.confluence import build_confluence

VERSION='v2-historical-research-1'
CONTEXT=Context(prec=60,rounding=ROUND_HALF_EVEN)

def number(x):
    if isinstance(x,bool):raise ValueError('Boolean is not a number')
    try:r=D(str(x))
    except (InvalidOperation,ValueError,TypeError):raise ValueError('Invalid research number') from None
    if not r.is_finite():raise ValueError('Nonfinite research number')
    return r

def text(x):return format(D(0) if x==0 else x,'f')
def money(x):
    value=x.quantize(D('.00000001'))
    return format(value.copy_abs() if value==0 else value,'f')
def integer(x,minimum,maximum):return type(x) is int and minimum<=x<=maximum

@dataclass(frozen=True,init=False)
class HistoricalDataset:
    """Frozen single-instrument provenance; ALL rows validated before simulation."""
    frames:object
    rules:object
    identity:Instrument
    source:str
    data_kind:str
    data_version:str
    digest:str
    def __init__(self,frames,rules,*,data_kind,data_version):
        if data_kind not in ('synthetic','historical') or not isinstance(data_version,str) or not 1<=len(data_version)<=128:
            raise ValueError('Explicit synthetic/historical provenance and data version required')
        if not isinstance(frames,dict) or '1m' not in frames or any(tf not in TIMEFRAME_MS for tf in frames):
            raise ValueError('Supported frames including consecutive 1m execution bars required')
        frozen={};remaining=30000
        for tf,rows in frames.items():
            frozen[tf]=tuple(islice(rows,remaining+1));remaining-=len(frozen[tf])
            if remaining<0:raise ValueError('Dataset exceeds 30000 bars')
        identity=source=None
        for tf,bars in frozen.items():
            if not bars or any(not isinstance(b,Candle) for b in bars):raise ValueError('Candle frames required')
            end=max(b.close_time_ms for b in bars)
            q=validate_series(bars,timeframe_ms=TIMEFRAME_MS[tf],as_of_ms=end,max_age_ms=0)
            if not q.ok or any(b.open_time_ms%TIMEFRAME_MS[tf] or b.close_time_ms%TIMEFRAME_MS[tf] for b in bars):
                raise ValueError('Invalid historical candle series')
            if identity is None:identity,source=bars[0].instrument,bars[0].source
            if any(b.instrument!=identity or b.source!=source or b.volume_kind!='real' for b in bars):
                raise ValueError('Historical instrument/source/real-volume mismatch')
        if (identity.symbol not in ('BTCUSDT','ETHUSDT','SOLUSDT') or identity.market!='crypto_spot'
                or identity.contract_type!='spot' or identity.price_kind!='last' or identity.quote_currency!='USDT'):
            raise ValueError('Only existing USDT spot identity is supported')
        keys={'quantity_step','minimum_quantity','maximum_quantity','minimum_notional','maximum_notional','price_tick','source'}
        if not isinstance(rules,dict) or set(rules)!=keys or not isinstance(rules['source'],str) or not rules['source']:
            raise ValueError('Explicit immutable historical instrument rules required')
        if any(number(rules[k])<=0 for k in keys-{'source'}) or number(rules['minimum_quantity'])>number(rules['maximum_quantity']) or number(rules['minimum_notional'])>number(rules['maximum_notional']):
            raise ValueError('Invalid historical instrument rules')
        values={'frames':MappingProxyType(frozen),'rules':MappingProxyType(dict(rules)),
                'identity':identity,'source':source,'data_kind':data_kind,'data_version':data_version,
                'digest':sha256(_canonical({'frames':frozen,'rules':rules,'data_kind':data_kind,'data_version':data_version}).encode()).hexdigest()}
        for key,value in values.items():object.__setattr__(self,key,value)

class HistoricalProvider:
    name='historical_research';mode='fixture'
    def __init__(self,dataset):
        self.dataset=dataset;self.venue=dataset.identity.venue;self.source_name=dataset.source
        self.ends={tf:tuple(b.close_time_ms for b in bars) for tf,bars in dataset.frames.items()}
    def rules(self,symbol):
        if symbol!=self.dataset.identity.symbol:raise ProviderUnavailable('historical_instrument_unavailable')
        return dict(self.dataset.rules)
    def candles(self,symbol,timeframe,as_of_ms):
        if symbol!=self.dataset.identity.symbol or timeframe not in self.dataset.frames:
            raise ProviderUnavailable('historical_frame_unavailable')
        end=bisect_right(self.ends[timeframe],as_of_ms)
        # Intentional historical prefix selection; quality validation happens on
        # this exact closed snapshot. No incomplete input bar is silently repaired.
        return list(self.dataset.frames[timeframe][max(0,end-300):end])

@dataclass(frozen=True)
class ResearchConfig:
    timeframe:str
    start_ms:int
    end_ms:int
    timeframes:tuple[str,...]=()
    portfolio:str='MANUAL'
    simulate_orders:bool=False
    analysis_every_bars:int=5
    max_events:int=3000
    max_analyses:int=50
    audit_every_bars:int=100
    strategy_ids:tuple[str,...]=tuple(sorted(BUILTIN_IDS))
    seed:int=12
    def __post_init__(self):
        if (self.timeframe not in TIMEFRAME_MS or type(self.timeframes) is not tuple or len(self.timeframes)>5
                or any(tf not in TIMEFRAME_MS for tf in self.timeframes) or len(set(self.timeframes))!=len(self.timeframes)
                or not integer(self.start_ms,0,10**16) or not integer(self.end_ms,self.start_ms+1,10**16)
                or self.start_ms%60000 or self.end_ms%60000 or self.portfolio not in ('AUTO','MANUAL')
                or type(self.simulate_orders) is not bool or not integer(self.analysis_every_bars,1,5000)
                or not integer(self.max_events,1,5000) or not integer(self.max_analyses,1,100)
                or not integer(self.audit_every_bars,1,5000) or not integer(self.seed,0,2**32-1)
                or type(self.strategy_ids) is not tuple or not self.strategy_ids or len(set(self.strategy_ids))!=len(self.strategy_ids)
                or not set(self.strategy_ids)<=BUILTIN_IDS):raise ValueError('Invalid bounded research configuration')


def summarize(equity_curve,trades,*,seed=12):
    """Position-level net PnL, ambiguity excluded. No significance/profitability label."""
    if not integer(seed,0,2**32-1):raise ValueError('Explicit bounded random seed required')
    if len(equity_curve)>5001 or len(trades)>5000:raise ValueError('Metric resource budget exceeded')
    with localcontext(CONTEXT):
        peak=D(0);dd=D(0)
        for point in equity_curve:
            x=number(point['equity_quote'])
            if x<0:raise ValueError('Negative long-spot equity')
            peak=max(peak,x)
            if peak:dd=max(dd,(peak-x)/peak)
        if any(type(t['ambiguous']) is not bool for t in trades):raise ValueError('Explicit ambiguity required')
        values=[number(t['net_pnl_quote']) for t in trades if not t['ambiguous']]
        wins=sum(v>0 for v in values);losses=sum(v<0 for v in values)
        profit=sum((max(D(0),v) for v in values),D(0));loss=-sum((min(D(0),v) for v in values),D(0))
        streaks={1:0,-1:0};current=previous=0
        for v in values:
            sign=1 if v>0 else -1 if v<0 else 0
            current=current+1 if sign and sign==previous else 1 if sign else 0
            if sign:streaks[sign]=max(streaks[sign],current)
            previous=sign
        interval=None
        if len(values)>=30:
            rng=Random(seed)
            means=sorted(sum((values[rng.randrange(len(values))] for _ in values),D(0))/len(values) for _ in range(500))
            interval={'lower':money(means[12]),'upper':money(means[487]),'method':'iid_bootstrap_mean_pnl_95_percentile_500',
                      'limitation':'IID assumption ignores serial dependence and selection bias; not probability of future profit.'}
        return {'scored_trades':len(values),'ambiguous_trades':sum(t['ambiguous'] for t in trades),
            'wins':wins,'losses':losses,'breakeven':len(values)-wins-losses,
            'expectancy_quote':money(sum(values,D(0))/len(values)) if values else None,
            'profit_factor':text(profit/loss) if loss else None,
            'maximum_drawdown_fraction':text(dd),'maximum_win_streak':streaks[1],'maximum_loss_streak':streaks[-1],
            'mean_pnl_interval':interval,'evidence_status':'INSUFFICIENT_EVIDENCE'}


def walk_forward_splits(total_bars,*,train_bars=300,test_bars=100,purge_bars=0):
    """Expanding train and disjoint OOS windows, optional label-horizon purge.

    These are index plans, NOT a completed optimizer or validation result.
    Caller must keep test data out of parameter selection and declare horizon.
    """
    if not all(integer(x,lo,30000) for x,lo in ((total_bars,1),(train_bars,1),(test_bars,1),(purge_bars,0))):raise ValueError('Invalid fold sizes')
    result=[];end=train_bars
    while end+purge_bars+test_bars<=total_bars:
        result.append({'train_start':0,'train_end':end,'test_start':end+purge_bars,'test_end':end+purge_bars+test_bars})
        end+=test_bars
    return result


def run_backtest(dataset,config,*,fee_bps='5',spread_bps='2',slippage_bps='1',profile=None,indicator_parameters=None):
    with localcontext(CONTEXT):
        return _run(dataset,config,fee_bps,spread_bps,slippage_bps,profile,indicator_parameters)


def _run(dataset,config,fee_bps,spread_bps,slippage_bps,profile,indicator_parameters):
    if not isinstance(dataset,HistoricalDataset) or not isinstance(config,ResearchConfig):raise ValueError('Validated research inputs required')
    if indicator_parameters is not None:
        from .indicator_parameters import IndicatorParameters
        if not isinstance(indicator_parameters,IndicatorParameters):raise ValueError("Immutable indicator parameters required")
        if indicator_parameters.bias_timeframe and indicator_parameters.bias_timeframe not in config.timeframes:raise ValueError("Bias frame must be explicitly requested")
    if profile is not None:
        from .strategy_profiles import StrategyProfile
        if (not isinstance(profile,StrategyProfile) or profile.setup_timeframe!=config.timeframe
                or not set(profile.timeframes)<={config.timeframe,*config.timeframes}
                or profile.strategy_ids!=tuple(sorted(config.strategy_ids)) or profile.analysis_every_bars!=config.analysis_every_bars):
            raise ValueError('Research config must exactly bind selected profile')
    costs={k:text(number(v)) for k,v in dict(fee_bps=fee_bps,spread_bps=spread_bps,slippage_bps=slippage_bps).items()}
    if any(number(v)<0 or number(v)>100 for v in costs.values()):raise ValueError('Research costs must be 0..100 bps')
    events=[b for b in dataset.frames['1m'] if b.open_time_ms>=config.start_ms and b.close_time_ms<=config.end_ms]
    if not events or events[0].open_time_ms!=config.start_ms or events[-1].close_time_ms!=config.end_ms or len(events)>config.max_events:
        raise ValueError('Exact bounded consecutive execution window required')
    if len(events)//config.audit_every_bars+2>64:raise ValueError('Research exceeds64audit checkpoints')
    if not {config.timeframe,*config.timeframes}<=set(dataset.frames):raise ValueError('Requested historical frames are missing')
    scheduled=[config.start_ms]+[b.close_time_ms for i,b in enumerate(events,1) if i%config.analysis_every_bars==0 and b.close_time_ms<config.end_ms]
    if sum(t%TIMEFRAME_MS[config.timeframe]==0 for t in scheduled)>config.max_analyses:
        raise ValueError('Analysis budget exceeded; shorten window or increase cadence')
    now=[config.start_ms];provider=HistoricalProvider(dataset);analyses=[];curve=[];checkpoints=[];reasons=Counter()
    # Always owned temporary file: callers cannot accidentally target live data.
    with TemporaryDirectory(prefix='v2-historical-research-') as root:
        db=ProductDatabase(Path(root)/'isolated.sqlite','fixture',domain_journal=True,clock=lambda:now[0])
        ledger=PaperLedger(db,**costs);service=AnalysisService(db,provider,ledger,lambda:now[0])
        def checkpoint():
            audit=audit_database(db.path,require_domain=True)
            checkpoints.append({'at_ms':now[0],'status':audit['status'],'checks':audit['checks']})
            return audit
        def observe():
            with db.transaction() as c:a=ledger.account(c,config.portfolio,now[0])
            curve.append({'at_ms':now[0],'equity_quote':a['equity_quote'],'cash_quote':a['cash_quote'],'realized_pnl_quote':a['realized_pnl_quote'],'unrealized_pnl_quote':a['unrealized_pnl_quote']})
        def analyze():
            if now[0]%TIMEFRAME_MS[config.timeframe] or len(analyses)>=config.max_analyses:return
            r=service.analyze(AnalyzeRequest(symbol=dataset.identity.symbol,timeframe=config.timeframe,timeframes=list(config.timeframes),data_mode='fixture',risk_portfolio=config.portfolio,auto_paper=False,idempotency_key='research-analysis:'+str(now[0])))
            pattern=detect_patterns(provider.candles(dataset.identity.symbol,config.timeframe,now[0]),timeframe=config.timeframe,as_of_ms=now[0],max_age_ms=TIMEFRAME_MS[config.timeframe],tick_size=dataset.rules['price_tick'])
            row={'analysis_id':r.analysis_id,'at_ms':now[0],'direction':r.direction,'reason':r.reason,'regime':r.regime,
                 'router':r.router,'indicators':r.indicators,'additional_methods':compute_methods(provider.candles(dataset.identity.symbol,config.timeframe,now[0]),timeframe=config.timeframe,as_of_ms=now[0],max_age_ms=TIMEFRAME_MS[config.timeframe]),'patterns':pattern,'pattern_confluence':build_confluence(confluence_evidence(pattern))}
            if profile is not None:
                from .strategy_profiles import evaluate_profile
                row['profile_filter']=evaluate_profile(profile,r.model_dump(mode='json'),row['additional_methods'])
            if indicator_parameters is not None:
                from .indicator_parameters import compute_parameters,parameter_filter
                def parameter_history(tf):
                    end=bisect_right(provider.ends[tf],now[0])
                    return dataset.frames[tf][max(0,end-1024):end]
                row['parameter_research']=compute_parameters(parameter_history(config.timeframe),indicator_parameters,
                    timeframe=config.timeframe,as_of_ms=now[0],max_age_ms=TIMEFRAME_MS[config.timeframe],
                    bias_candles=parameter_history(indicator_parameters.bias_timeframe) if indicator_parameters.bias_timeframe else None)
                row['parameter_filter']=parameter_filter(row['parameter_research'],r.direction)
            if config.simulate_orders and (indicator_parameters is None or row['parameter_filter']['passes']) and (profile is None or row['profile_filter']['passes']) and r.direction!='WAIT' and r.router.get('strategy_id') in config.strategy_ids:
                try:
                    with db.transaction() as c:ledger.place(c,config.portfolio,r,'research-order:'+str(now[0]),None,now[0])
                    row['candidate_status']='placed'
                except V2Error as exc:row['candidate_status']=exc.code
            else:row['candidate_status']='not_requested_or_not_eligible'
            analyses.append(row);reasons[r.reason]+=1
        observe();analyze();checkpoint()
        for i,b in enumerate(events,1):
            now[0]=b.close_time_ms
            event={k:text(number(getattr(b,k))) for k in ('open','high','low','close','volume')}
            event.update(symbol=b.instrument.symbol,open_time_ms=b.open_time_ms,close_time_ms=b.close_time_ms,is_final=True)
            with db.transaction() as c:ledger.event(c,event,now[0])
            observe()
            if i%config.analysis_every_bars==0 and now[0]<config.end_ms:analyze()
            if i%config.audit_every_bars==0:checkpoint()
        audit=checkpoint()
        with db.transaction() as c:
            positions=db.rows(c,'positions',config.portfolio);transactions=db.rows(c,'transactions',config.portfolio)
            orders=db.rows(c,'orders',config.portfolio);saved={a['analysis_id']:a for a in db.rows(c,'analyses')};domain_count=c.execute('SELECT count(*) FROM domain_events').fetchone()[0]
        closed=[];order_by_id={o['order_id']:o for o in orders}
        for p in positions:
            if number(p['quantity'])==0:
                origin=saved[order_by_id[p['order_id']]['analysis_id']]
                closed.append({'strategy_id':origin['router'].get('strategy_id'),'regime':origin['regime'].get('regime','unknown'),'position_id':p['position_id'],'net_pnl_quote':money(sum((number(t['realized_pnl_quote']) for t in transactions if t['position_id']==p['position_id']),D(0))), 'ambiguous':bool(p.get('ambiguity_seen'))})
        integrity=max((c['status'] for c in checkpoints),key=lambda s:('PASS','INCOMPLETE','MISMATCH','CORRUPT','ERROR').index(s))
        return {**({'indicator_configuration':asdict(indicator_parameters),'indicator_parameter_id':indicator_parameters.parameter_id} if indicator_parameters is not None else {}),'version':VERSION,'profile_id':profile.profile_id if profile is not None else None,'integrity_status':integrity,'dataset_digest':dataset.digest,'data_kind':dataset.data_kind,'data_version':dataset.data_version,
            'configuration':asdict(config),'strategy_versions':{s.strategy_id:s.version for s in STRATEGIES},'analysis_version':ANALYSIS_VERSION,
            'execution_model':'next_closed_bar_touch_worst_edge_v1','execution_costs':costs,'policy':json.loads(_canonical(ledger.policy)),
            'validation_status':'BACKTESTED' if dataset.data_kind=='historical' and orders and integrity=='PASS' else 'DETECTION_IMPLEMENTED',
            'evidence_status':'INSUFFICIENT_EVIDENCE','forward_validated':False,'real_execution':False,'events':len(events),
            'analyses':analyses,'reason_counts':dict(sorted(reasons.items())),'orders':len(orders),'journal_records':len(transactions),
            'domain_events':domain_count,'fees_quote':money(sum((number(t['fee_quote']) for t in transactions),D(0))),
            'open_positions':sum(number(p['quantity'])>0 for p in positions),'ambiguous_positions':sum(bool(p.get('ambiguity_seen')) for p in positions),
            'pending_orders':sum(o['status'] in ('pending','partially_filled') for o in orders),
            'equity_curve':curve,'closed_trades':closed,'breakdowns':trade_breakdowns(closed,seed=config.seed),'metrics':summarize(curve,closed,seed=config.seed),
            'audit':{'status':audit['status'],'checks':audit['checks'],'findings':audit['findings'],'domain':audit.get('domain')},'checkpoints':checkpoints,
            'limitations':['Historical source/license/universe must be independently verified; user-supplied label is not certification.',
                'No end-window forced liquidation. Open and ambiguous trades are not scored as wins/losses.',
                'Strategy selection filters existing selected routes; it does not optimize or enable a new product strategy.',
                'Pattern context is research confluence only and never grants order permission.',
                'Walk-forward optimization and forward validation are not performed by this single-window run.']}


def trade_breakdowns(trades,*,seed=12):
    result={}
    for field in ('strategy_id','regime'):
        groups={}
        for value in sorted({t.get(field,'unknown') or 'unknown' for t in trades}):
            rows=[t for t in trades if (t.get(field,'unknown') or 'unknown')==value]
            metrics=summarize([],rows,seed=seed)
            for key in ('maximum_drawdown_fraction','maximum_win_streak','maximum_loss_streak'):metrics[key]=None
            groups[value]=metrics
        result[field]=groups
    return result


def load_dataset(path):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError('Explicit existing historical JSON required')
    if path.stat().st_size>32*1024*1024:raise ValueError('Dataset file exceeds 32MiB')
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError('Duplicate JSON key')
            d[k]=v
        return d
    body=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    if not isinstance(body,dict) or set(body)!={'schema_version','data_kind','data_version','instrument','source','rules','frames'} or type(body['schema_version']) is not int or body['schema_version']!=1:raise ValueError('Unsupported historical dataset schema')
    if not isinstance(body['frames'],dict) or not isinstance(body['instrument'],dict):raise ValueError('Historical frames/instrument objects required')
    identity=Instrument(**body['instrument']);frames={}
    fields={'open_time_ms','close_time_ms','is_final','open','high','low','close','volume','volume_kind'}
    for tf,rows in body['frames'].items():
        if not isinstance(rows,list) or any(not isinstance(row,dict) or set(row)!=fields for row in rows):raise ValueError('Unknown candle fields')
        frames[tf]=[Candle(identity,source=body['source'],**r) for r in rows]
    return HistoricalDataset(frames,body['rules'],data_kind=body['data_kind'],data_version=body['data_version'])
