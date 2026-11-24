import unittest
from dataclasses import replace
from fixtures import fixture,NOW
from unified_forex.market import acquire
from unified_forex.technical import compute
from unified_forex.strategies import assess,TREND,RANGE,BREAKOUT,SWEEP
from market_ai.v2.price_action import compute_price_action


def assess_frame(frame,regime):
    metrics=compute(frame)
    action=compute_price_action(frame.bars,timeframe_ms=frame.duration_ms,as_of_ms=frame.as_of_ms,max_age_ms=frame.duration_ms)
    return {a['strategy_id']:a for a in assess(frame,metrics,{'regime':regime},action)},metrics


class ForexFamilies(unittest.TestCase):
    def frame(self):return acquire(fixture(),'XAUUSD','M15',NOW,('H4',)).frame('M15')

    def test_retained_trend_and_sell_mirror(self):
        for direction in ('BUY','SELL'):
            f=acquire(fixture(direction),'XAUUSD','M15',NOW,('H4',)).frame('M15')
            rows,_=assess_frame(f,'trend')
            self.assertEqual(rows[TREND]['direction'],direction)
            self.assertEqual(rows[TREND]['status'],'CONFIRMED')

    def test_price_range_positive_negative_without_volume_dependency(self):
        f=self.frame();bars=list(f.bars)
        for i,b in enumerate(bars):
            c=2000+(.7 if i%2 else -.7);bars[i]=replace(b,open=c,high=c+.2,low=c-.2,close=c)
        closes=[1998,2000,2002,2004,2005,2006,2005,2004,2003,2002,2001,2000,1999,1998,1997,1996,1995,1994,1993,1994]
        for i,c in enumerate(closes,len(bars)-22):bars[i]=replace(bars[i],open=c,high=c+.2,low=c-.2,close=c)
        bars[-2]=replace(bars[-2],open=1993,high=1993.2,low=1992.8,close=1993)
        bars[-1]=replace(bars[-1],open=1993.1,high=1994.2,low=1993,close=1994)
        f=replace(f,bars=tuple(bars));rows,metrics=assess_frame(f,'range')
        self.assertEqual(rows[RANGE]['status'],'CONFIRMED',(rows[RANGE],metrics['rsi14_wilder']))
        self.assertEqual(rows[RANGE]['direction'],'BUY')
        changed=replace(f,bars=tuple(replace(b,volume=99999) for b in f.bars))
        self.assertEqual(assess_frame(changed,'range')[0][RANGE],rows[RANGE])
        rows,_=assess_frame(replace(f,bars=f.bars[:-1]+(replace(f.bars[-1],close=1993.1),)),'range')
        self.assertEqual(rows[RANGE]['status'],'WAIT')

    def test_two_close_breakout_displacement_and_negative(self):
        f=self.frame();bars=list(f.bars)
        for i,b in enumerate(bars):
            c=2000+(.15 if i%2 else -.15);bars[i]=replace(b,open=c,high=c+.2,low=c-.2,close=c)
        bars[-2]=replace(bars[-2],open=2000,high=2001.2,low=1999.9,close=2001)
        bars[-1]=replace(bars[-1],open=2001,high=2001.6,low=2000.9,close=2001.4)
        f=replace(f,bars=tuple(bars));rows,m=assess_frame(f,'breakout')
        self.assertEqual(rows[BREAKOUT]['status'],'CONFIRMED',(rows[BREAKOUT],m['rsi14_wilder']))
        bars[-2]=replace(bars[-2],open=2001)
        self.assertEqual(assess_frame(replace(f,bars=tuple(bars)),'breakout')[0][BREAKOUT]['status'],'WAIT')

    def test_actual_sweep_followthrough_creates_reversal_candidate(self):
        from unified_forex.engine import AnalysisEngine
        p=fixture();rows=p.data['XAUUSD']['candles']['M15']
        for i,b in enumerate(rows):
            c=2000+(.7 if i%2 else -.7)
            if i>=190:c=2010-.3*(i-190)
            b.update(open=c,high=c+.2,low=c-.2,close=c)
        rows[-2].update(open=2001.5,high=2002.1,low=1999.5,close=2001.9)
        rows[-1].update(open=2001.9,high=2002.6,low=2001.8,close=2002.4)
        p.data['XAUUSD']['quote'].update(bid=2002.4,ask=2002.6)
        result=AnalysisEngine().analyze(p,'XAUUSD',now=NOW,balance=10000)
        self.assertEqual(result.regime['label'],'REVERSAL_CANDIDATE')
        sweep=next(r for r in result.strategies if r['strategy_id']==SWEEP)
        self.assertEqual(sweep['status'],'CONFIRMED',(sweep,result.decision_reasons))
        self.assertEqual(result.final_decision,'BUY_CANDIDATE',result.decision_reasons)
        self.assertEqual(result.routing['strategy_id'],SWEEP)
