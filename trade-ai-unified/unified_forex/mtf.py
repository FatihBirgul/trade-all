"""Source V2 MTF context over the same V5 as-of snapshot; no second price vote."""
from market_ai.engines import mtf as original
from .market import TF


def direction(metrics,close):
    return 'bullish' if close>metrics['ema50']>metrics['ema200'] else 'bearish' if close<metrics['ema50']<metrics['ema200'] else 'neutral'


def analyze(view,primary,metrics):
    snapshots={TF[f.timeframe]:{'direction':direction(metrics[f.timeframe],f.bars[-1].close),
                              'confidence':0,'quality':{'gate_passed':True},'tradeable':False}
               for f in view.frames}
    # Original mtf accepts 30m after the explicit rank extension in this target.
    raw=original.analyze(TF[primary],snapshots)
    confirmations=[]
    p=view.snapshot.payload()
    primary_direction=direction(metrics[primary],view.frame(primary).bars[-1].close)
    higher=[];lower=[]
    for f in view.frames:
        if f.timeframe==primary:continue
        d=direction(metrics[f.timeframe],f.bars[-1].close)
        record={'timeframe':f.timeframe,'direction':d,'closed_at':f.bars[-1].close_time_ms//1000,
                'available':True,'role':'higher_bias' if f.duration_ms>view.frame(primary).duration_ms else 'lower_trigger'}
        confirmations.append(record)
        (higher if record['role']=='higher_bias' else lower).append(d)
    raw['evidence']=[e for e in raw.get('evidence',[]) if e.get('source')!='mtf_current']
    return {'source_context':raw,'primary_direction':primary_direction,'higher_bias':higher,'lower_trigger':lower,
            'confirmations':confirmations,'as_of_utc':p['decision_close_utc'],'independent_price_vote':False,
            'version':'fx-asof-mtf-v6-1'}
