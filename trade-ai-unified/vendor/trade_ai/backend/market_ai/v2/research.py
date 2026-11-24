"""Pure research math extracted from pinned V2; no ledger/service imports.

Forex dataset/runner are injected into the retained V2 walk-forward protocol.
"""
from decimal import Decimal as D, Context, localcontext, ROUND_HALF_EVEN, InvalidOperation
from random import Random
CONTEXT=Context(prec=60,rounding=ROUND_HALF_EVEN)
VERSION='fx-historical-research-v9-1'
ANALYSIS_VERSION='9.0.0-rc1'

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

def summarize(equity_curve,trades,*,seed=12):
    """Position-level net PnL, ambiguity excluded. No significance/profitability label."""
    if not integer(seed,0,2**32-1):raise ValueError('Explicit bounded random seed required')
    if len(equity_curve)>5001 or len(trades)>5000:raise ValueError('Metric resource budget exceeded')
    with localcontext(CONTEXT):
        peak=D(0);dd=D(0)
        for point in equity_curve:
            x=number(point['equity_quote'])
            # Forex gaps may produce negative equity; preserve observed loss.
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
            'win_rate':wins/len(values) if values else None,'loss_rate':losses/len(values) if values else None,
            'average_holding_bars':sum(t.get('holding_bars',0) for t in trades)/len(trades) if trades else None,
            'expectancy_quote':money(sum(values,D(0))/len(values)) if values else None,
            'profit_factor':text(profit/loss) if loss else None,
            'maximum_drawdown_fraction':text(dd),'maximum_win_streak':streaks[1],'maximum_loss_streak':streaks[-1],
            'mean_pnl_interval':interval,'evidence_status':'INSUFFICIENT_EVIDENCE'}

from unified_forex.research import HistoricalDataset,ResearchConfig,run_backtest
