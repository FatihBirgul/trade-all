"""Chronological parameter selection and held-out execution in temporary ledgers.

Existing route filters/cadence and optional frozen research indicator restrictions
are selectable. No live execution or independent evidence of profitability.
"""
import json
from dataclasses import dataclass, asdict
from decimal import localcontext
from hashlib import sha256
import re
from .research import (HistoricalDataset, ResearchConfig, run_backtest, number,
                       money, integer, CONTEXT, summarize, VERSION as RESEARCH_VERSION, ANALYSIS_VERSION)
from .decision_record import _canonical
from .strategies import BUILTIN_IDS, STRATEGIES
from .technical_adapter import TIMEFRAME_MS
from .pipeline import PIPELINE_VERSION
from .paper_risk import RISK_VERSION

VERSION = 'v2-walk-forward-1'
STATUS_ORDER = ('PASS', 'INCOMPLETE', 'MISMATCH', 'CORRUPT', 'ERROR')

def digest(value):
    return sha256(_canonical(value).encode()).hexdigest()

@dataclass(frozen=True)
class Candidate:
    candidate_id: str = 'default'
    strategy_ids: tuple[str, ...] = tuple(sorted(BUILTIN_IDS))
    analysis_every_bars: int = 10

    def __post_init__(self):
        if (not isinstance(self.candidate_id, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,64}', self.candidate_id)
                or type(self.strategy_ids) is not tuple or not self.strategy_ids
                or len(set(self.strategy_ids)) != len(self.strategy_ids)
                or not set(self.strategy_ids) <= BUILTIN_IDS
                or not integer(self.analysis_every_bars, 1, 5000)):
            raise ValueError('Unsupported research candidate')
        object.__setattr__(self,'strategy_ids',tuple(sorted(self.strategy_ids)))

@dataclass(frozen=True)
class IndicatorCandidate(Candidate):
    """Opt-in subtype preserves legacy candidate/protocol serialization."""
    parameters: object = None

    def __post_init__(self):
        super().__post_init__()
        from .indicator_parameters import IndicatorParameters
        if not isinstance(self.parameters,IndicatorParameters):
            raise ValueError('Frozen indicator research configuration required')


def parameter_kwargs(candidate):
    return {'indicator_parameters':candidate.parameters} if isinstance(candidate,IndicatorCandidate) else {}


@dataclass(frozen=True)
class WalkForwardConfig:
    train_bars: int = 500
    test_bars: int = 100
    warmup_bars: int = 250
    purge_bars: int = 1
    label_horizon_bars: int = 1
    embargo_bars: int = 0
    mode: str = 'expanding'
    max_folds: int = 3
    minimum_training_trades: int = 1
    simulate_orders: bool = False
    timeframe: str = '1m'
    timeframes: tuple[str, ...] = ()
    candidates: tuple[Candidate, ...] = (Candidate(),)
    fee_bps: str = '5'
    spread_bps: str = '2'
    slippage_bps: str = '1'
    max_total_events: int = 12000
    max_total_analyses: int = 300
    seed: int = 12

    def __post_init__(self):
        if (not integer(self.train_bars, 251, 30000) or not integer(self.test_bars, 1, 5000)
                or not integer(self.warmup_bars, 250, self.train_bars-1)
                or not integer(self.label_horizon_bars, 1, 5000)
                or not integer(self.purge_bars, self.label_horizon_bars, 5000)
                or not integer(self.embargo_bars, 0, 5000) or self.mode not in ('expanding', 'rolling')
                or not integer(self.max_folds, 1, 4) or not integer(self.minimum_training_trades, 1, 5000)
                or self.simulate_orders is not True or self.timeframe not in TIMEFRAME_MS
                or type(self.timeframes) is not tuple or len(self.timeframes)>5
                or len(set(self.timeframes)) != len(self.timeframes) or any(t not in TIMEFRAME_MS for t in self.timeframes)
                or type(self.candidates) is not tuple or not 1 <= len(self.candidates) <= 4
                or any(not isinstance(c, Candidate) for c in self.candidates)
                or len({c.candidate_id for c in self.candidates}) != len(self.candidates)
                or not integer(self.max_total_events, 1, 12000) or not integer(self.max_total_analyses, 1, 300)
                or not integer(self.seed, 0, 2**32-1)):
            raise ValueError('Invalid bounded walk-forward protocol; explicit temporary simulation required')
        for x in (self.fee_bps, self.spread_bps, self.slippage_bps):
            if not 0 <= number(x) <= 100:
                raise ValueError('Fixed experiment costs must be 0..100 bps')
        for key in ('fee_bps','spread_bps','slippage_bps'):
            parsed=number(getattr(self,key));value='0' if parsed==0 else format(parsed,'f')
            object.__setattr__(self,key,value.rstrip('0').rstrip('.') if '.' in value else value)
        object.__setattr__(self,'candidates',tuple(sorted(self.candidates,key=lambda c:c.candidate_id)))
        object.__setattr__(self,'timeframes',tuple(sorted(self.timeframes,key=TIMEFRAME_MS.get)))


def plan_folds(total_bars, config):
    if not integer(total_bars, 1, 30000) or not isinstance(config, WalkForwardConfig):
        raise ValueError('Invalid chronological fold input')
    folds = []
    end = config.train_bars
    while end + config.purge_bars + config.test_bars <= total_bars and len(folds) < config.max_folds:
        start = 0 if config.mode == 'expanding' else end-config.train_bars
        test_start = end+config.purge_bars
        folds.append(dict(train_start=start, train_end=end, test_start=test_start, test_end=test_start+config.test_bars))
        # Embargo is an explicit unused gap BETWEEN held-out windows. Earlier
        # test data can enter a later chronological training fold once known.
        end += config.test_bars+config.embargo_bars
    return folds


def prefix(dataset, end_ms, start_ms=0):
    frames = {tf: tuple(b for b in rows if b.open_time_ms >= start_ms and b.close_time_ms <= end_ms) for tf, rows in dataset.frames.items()}
    if any(not b for b in frames.values()):
        raise ValueError('No closed history for requested frame at training cutoff')
    return HistoricalDataset(frames, dict(dataset.rules), data_kind=dataset.data_kind, data_version=dataset.data_version)


def _run_config(dataset, config, fold, candidate, training):
    bars = dataset.frames['1m']
    start = fold['train_start']+config.warmup_bars if training else fold['test_start']
    end = fold['train_end'] if training else fold['test_end']
    return ResearchConfig(timeframe=config.timeframe, timeframes=config.timeframes,
        start_ms=bars[start].open_time_ms, end_ms=bars[end-1].close_time_ms,
        simulate_orders=True, strategy_ids=candidate.strategy_ids, analysis_every_bars=candidate.analysis_every_bars,
        max_events=5000, max_analyses=100, audit_every_bars=max(1, (end-start+7)//8), seed=config.seed)


def _scheduled(c):
    times=[c.start_ms]+list(range(c.start_ms+c.analysis_every_bars*60000, c.end_ms, c.analysis_every_bars*60000))
    return sum(t % TIMEFRAME_MS[c.timeframe] == 0 for t in times)


def compact(report):
    keys=('version','integrity_status','validation_status','events','orders','journal_records','domain_events',
          'fees_quote','open_positions','ambiguous_positions','pending_orders','equity_curve','closed_trades',
          'metrics','audit','checkpoints','breakdowns')
    return {k: report[k] for k in keys if k in report}


def run_walk_forward(dataset, config, *, manifest=None, registry=None):
    """Test each frozen winner once; NEVER pass held-out rows to training.

    Repeating a protocol has the same experiment ID, not new independent OOS
    evidence. Cross-run discretionary re-optimization requires external review.
    Each fold starts a new seed account; no continuous compounded equity claim.
    """
    if not isinstance(dataset, HistoricalDataset) or not isinstance(config, WalkForwardConfig):
        raise ValueError('Validated dataset and immutable protocol required')
    with localcontext(CONTEXT):
        folds=plan_folds(len(dataset.frames['1m']), config)
        if not folds:
            raise ValueError('Not enough history for a complete purged held-out fold')
        if not {config.timeframe,*config.timeframes} <= set(dataset.frames):
            raise ValueError('Requested historical frames are absent')
        candidates=tuple(sorted(config.candidates, key=lambda c:c.candidate_id))
        for candidate in candidates:
            if isinstance(candidate,IndicatorCandidate):
                p=candidate.parameters
                if config.warmup_bars*60000<p.warmup_bars*TIMEFRAME_MS[config.timeframe]:
                    raise ValueError('Parameter warmup exceeds protocol warmup')
                if p.bias_timeframe:
                    if p.bias_timeframe not in config.timeframes or TIMEFRAME_MS[p.bias_timeframe]<=TIMEFRAME_MS[config.timeframe] or TIMEFRAME_MS[p.bias_timeframe]%TIMEFRAME_MS[config.timeframe]:
                        raise ValueError('Explicit supported higher bias frame required')
                    # Warmup is measured in execution (1m) bars, not bias bars.
                    if config.warmup_bars*60000<2*p.ema_period*TIMEFRAME_MS[p.bias_timeframe]:
                        raise ValueError('Insufficient bias-frame warmup')
        events=analyses=0
        for fold in folds:
            configs=[_run_config(dataset,config,fold,c,True) for c in candidates]
            # Budget all test choices conservatively, although only one runs.
            tests=[_run_config(dataset,config,fold,c,False) for c in candidates]
            events += sum((c.end_ms-c.start_ms)//60000 for c in configs)+max((c.end_ms-c.start_ms)//60000 for c in tests)
            analyses += sum(_scheduled(c) for c in configs)+max(_scheduled(c) for c in tests)
            if any((c.end_ms-c.start_ms)//60000>5000 for c in configs+tests):
                raise ValueError('Per-run execution budget exceeded')
            if any(_scheduled(c)>100 for c in configs+tests):
                raise ValueError('Per-run analysis budget exceeded')
        if events>config.max_total_events or analyses>config.max_total_analyses:
            raise ValueError('Total experiment resource budget exceeded')
        costs=dict(fee_bps=config.fee_bps,spread_bps=config.spread_bps,slippage_bps=config.slippage_bps)
        versions={s.strategy_id:s.version for s in STRATEGIES}
        from .historical_provenance import verify_manifest
        provenance=verify_manifest(dataset,manifest,costs=costs)
        if provenance['status'] in ('MISMATCH','CORRUPT','ERROR'):raise ValueError('Dataset evidence does not match experiment')
        engines={'analysis':ANALYSIS_VERSION,'research':RESEARCH_VERSION,'routing':PIPELINE_VERSION,'risk':RISK_VERSION,'execution':'next_closed_bar_touch_worst_edge_v1'}
        if any(isinstance(c,IndicatorCandidate) for c in candidates):
            from .indicator_parameters import VERSION as parameter_version
            engines['indicator_parameters']=parameter_version
        protocol={'engine_versions':engines,'manifest_id':manifest.manifest_id if manifest is not None else None,'version':VERSION,'dataset_digest':dataset.digest,'configuration':asdict(config),'strategy_versions':versions}
        if registry is not None:
            from dataclasses import asdict as identity_dict
            first=dataset.frames['1m'][0]
            stream=digest({'instrument':identity_dict(first.instrument),'source':first.source,'base_timeframe':'1m'})
            windows=[(dataset.frames['1m'][f['test_start']].open_time_ms,dataset.frames['1m'][f['test_end']-1].close_time_ms) for f in folds]
            key=registry.register(protocol,stream,windows)
            cached=registry.result(key)
            if cached is not None:return cached
        output=[];statuses=[];pooled=[]
        for i,fold in enumerate(folds):
            train_end=dataset.frames['1m'][fold['train_end']-1].close_time_ms
            training_data=prefix(dataset,train_end,dataset.frames['1m'][fold['train_start']].open_time_ms)
            training=[];eligible=[]
            for candidate in candidates:
                c=_run_config(dataset,config,fold,candidate,True)
                r=run_backtest(training_data,c,**costs,**parameter_kwargs(candidate))
                net=number(r['equity_curve'][-1]['equity_quote'])-number(r['equity_curve'][0]['equity_quote'])
                row={'candidate':asdict(candidate),'training_input_digest':training_data.digest,
                     'metrics':r['metrics'],'breakdowns':r['breakdowns'],'integrity_status':r['integrity_status'],'scored_trades':r['metrics']['scored_trades'],
                     'marked_net_change_quote':money(net),'drawdown_fraction':r['metrics']['maximum_drawdown_fraction']}
                training.append(row);statuses.append(r['integrity_status'])
                if r['integrity_status']=='PASS' and row['scored_trades']>=config.minimum_training_trades:
                    eligible.append((candidate,row))
            row={'fold':i,'indices':fold,'training_cutoff_ms':train_end,'training':training,
                 'selected_candidate':None,'frozen_parameters_hash':None,'test':None,'status':'INSUFFICIENT_EVIDENCE'}
            if eligible:
                winner,score=min(eligible,key=lambda pair:(-number(pair[1]['marked_net_change_quote']),number(pair[1]['drawdown_fraction']),pair[0].candidate_id))
                frozen={'candidate':asdict(winner),'training_input_digest':training_data.digest,'fold':fold,
                        'strategy_versions':versions,'engine_versions':engines,'costs':costs,'selection_objective':'marked_net_change_then_lower_drawdown_then_id'}
                test_config=_run_config(dataset,config,fold,winner,False)
                test_data=prefix(dataset,test_config.end_ms)
                result=run_backtest(test_data,test_config,**costs,**parameter_kwargs(winner))
                statuses.append(result['integrity_status']);pooled.extend(result['closed_trades'])
                row.update(selected_candidate=winner.candidate_id,frozen_parameters_hash=digest(frozen),
                           frozen_parameters=frozen,test=compact(result),status='OOS_EVALUATED' if result['integrity_status']=='PASS' else result['integrity_status'])
            output.append(row)
        integrity=max(statuses,key=STATUS_ORDER.index)
        pooled_metrics=summarize([],pooled,seed=config.seed)
        # Reset accounts and interfold gaps cannot form a continuous equity curve.
        for k in ('maximum_drawdown_fraction','maximum_win_streak','maximum_loss_streak'):
            pooled_metrics[k]=None
        complete=all(f['status']=='OOS_EVALUATED' for f in output) and integrity=='PASS'
        report={**protocol,'experiment_id':digest(protocol),'data_kind':dataset.data_kind,'folds':output,
            'validation_status':'OOS_EVALUATED' if complete else 'DETECTION_IMPLEMENTED',
            'provenance':provenance,'integrity_status':integrity,'evidence_status':'INSUFFICIENT_EVIDENCE','forward_validated':False,
            'real_execution':False,'pooled_closed_trade_metrics':pooled_metrics,'continuous_equity_available':False,
            'limitations':['Synthetic OOS validates execution/leakage machinery, not market profitability.',
                'Purged horizon bounds training labels; persistent positions are marked at train end, never labelled using later outcomes.',
                'Independent seed accounts per fold; no compounded return or pooled drawdown.',
                'Same experiment ID on rerun is not independent evidence; external preregistration needed to control cross-run selection.',
                'Cadence, selected-route and optional research parameter restrictions only; no new trading strategy or risk override.']}

        if registry is not None:
            report['registration']={'schema_version':1,'scope':'local_registry_only','status':'preregistered_frozen_result','experiment_id':key}
            report=json.loads(json.dumps(report,sort_keys=True,allow_nan=False))
            registry.save_result(key,report)
        return report
