"""Non-authorizing diagnostics bound to the exact immutable product snapshot."""
import logging
from itertools import islice
from market_ai.engines.confluence import build_confluence
from .pattern_research import detect_patterns, confluence_evidence
from .technical_research import compute_methods
from .divergence_research import detect_divergences
from .chart_research import detect_charts
from .session_research import session_research

VERSION='v2-analysis-diagnostics-1'
logger=logging.getLogger(__name__)

def compute_diagnostics(candles,*,timeframe,as_of_ms,max_age_ms,tick_size,source_record_id):
    base={'version':VERSION,'source_record_id':source_record_id,'trade_permission':False,
          'scope':'descriptive_research_confluence_only'}
    try:
        candles=tuple(islice(candles,4097))
        patterns=detect_patterns(candles,timeframe=timeframe,as_of_ms=as_of_ms,max_age_ms=max_age_ms,tick_size=tick_size)
        methods=compute_methods(candles,timeframe=timeframe,as_of_ms=as_of_ms,max_age_ms=max_age_ms)
        try:
            divergence=detect_divergences(candles,timeframe=timeframe,as_of_ms=as_of_ms,max_age_ms=max_age_ms,tick_size=tick_size)
        except Exception:
            logger.warning('Confirmed divergence diagnostics unavailable')
            divergence={'version':'v2-confirmed-divergence-1','status':'unavailable','reason':'diagnostic_engine_unavailable','trade_permission':False,'events':[]}
        try:
            charts=detect_charts(candles[-128:],timeframe=timeframe,as_of_ms=as_of_ms,max_age_ms=max_age_ms,tick_size=tick_size)
            charts['source_window_bars']=min(len(candles),128)
        except Exception:
            logger.warning('Chart diagnostics unavailable')
            charts={'status':'unavailable','trade_permission':False,'patterns':[],'reason':'diagnostic_engine_unavailable'}
        try:
            session=session_research(candles,timeframe=timeframe,as_of_ms=as_of_ms,max_age_ms=max_age_ms)
        except Exception:
            logger.warning('Session diagnostics unavailable')
            session={'status':'unavailable','trade_permission':False,'reason':'diagnostic_engine_unavailable'}
        return {**base,'status':'available' if patterns['status']==methods['status']=='available' else 'unavailable',
                'patterns':patterns,'methods':methods,'divergences':divergence,'charts':charts,'session':session,'confluence':build_confluence(confluence_evidence(patterns))}
    except Exception:
        # Optional explanation must not replace a valid price/decision with a
        # fake source or change trading gates. No raw input/exception text logs.
        logger.warning('Analysis diagnostics unavailable')
        return {**base,'status':'unavailable','reason':'diagnostic_engine_unavailable'}
