"""One named canonical technical view; alternate mathematics stays explicit."""
from dataclasses import asdict
import math
import pandas as pd
from forex.core import indicators, scanner
from market_ai.engines import technical as v2technical
from market_ai.v2.technical_research import compute_methods
from market_ai.v2.regime import classify_regime

VERSIONS={'canonical':'forex-v5-sma-seed-wilder-rsi-sma-atr-population-bb',
          'rsi_rolling':'v2-rolling-rsi14-1','stoch_rsi':'v2-rolling-rsi-stochastic14-3-1',
          'extra_methods':'v2-technical-research-1','volatility':'fx-atr-ratio20-v1',
          'divergence':'fx-aligned-divergence-v7-1'}


def ohlc(frame):
    return [dict(time=b.open_time_ms//1000,open=b.open,high=b.high,low=b.low,close=b.close) for b in frame.bars]


def compute(frame,tick=1e-10):
    rows=ohlc(frame);metrics=indicators(rows)
    closes=pd.Series([b.close for b in frame.bars],dtype=float)
    rolling=v2technical.rsi(closes)
    k,d=v2technical.stoch_rsi(closes,rsi_series=rolling)
    def value(series):
        result=float(series.iloc[-1])
        return result if math.isfinite(result) else None
    metrics.update(rsi14_wilder=metrics['rsi14'],rsi14_rolling=value(rolling),
                   stochastic_rsi_k=value(k),stochastic_rsi_d=value(d),
                   previous_wilder_rsi=scanner.rsi(closes.tolist()[:-1]))
    extra=compute_methods(frame.bars,**frame.kwargs())
    metrics['research_methods']=extra
    from .divergence import analyze as divergences
    metrics['divergence']=divergences(frame,tick)
    return metrics


def regime(frame,metrics,price_action,prior_action=None):
    bars=frame.bars
    raw=classify_regime([b.close for b in bars],[b.high for b in bars],[b.low for b in bars])
    # Non-directional volatility: current TR mean versus preceding20 TR mean.
    tr=[max(b.high-b.low,abs(b.high-a.close),abs(b.low-a.close)) for a,b in zip(bars,bars[1:])]
    baseline=sum(tr[-34:-14])/20
    ratio=metrics['atr14']/baseline if baseline>0 else None
    volatility='UNKNOWN' if ratio is None else 'HIGH_VOLATILITY' if ratio>1.8 else 'LOW_VOLATILITY' if ratio<.55 else 'NORMAL'
    state=raw.regime
    direction=raw.direction
    if any(e['kind']=='CHoCH' for e in price_action.get('structure',{}).get('events',[])):
        state='reversal'
    sweep=(prior_action or {}).get('liquidity_sweep',{}).get('direction')
    if (sweep=='bullish' and bars[-1].close>bars[-2].high) or (sweep=='bearish' and bars[-1].close<bars[-2].low):
        state='reversal';direction=sweep
    return {**asdict(raw),'direction':direction,'regime':state,'label':{'reversal':'REVERSAL_CANDIDATE'}.get(state,state.upper()),
            'volatility':volatility,'atr_ratio':ratio,'version':'fx-regime-v6-1',
            'source_version':'v2-regime-1','volatility_is_directional':False}
