"""Explicit documentation/test OHLC fixtures. Never a live provider fallback."""
from dataclasses import replace
from math import cos, sin, pi
from market_ai.v2.spot_provider import FixtureSpotProvider

NOW=1800000000000


def fixture(kind, timeframe="1H", now=NOW, symbol="BTCUSDT", mirror=False):
    base=FixtureSpotProvider().candles(symbol,timeframe,now)
    if kind == "trend": return base
    period=12 if kind=="range" else 20
    b=[replace(x,open=100+10*cos(2*pi*i/period),high=100+10*cos(2*pi*i/period)+.3,
               low=100+10*cos(2*pi*i/period)-.3,close=100+10*cos(2*pi*i/period),volume=100) for i,x in enumerate(base)]
    b[-2]=replace(b[-2],open=91,high=91.5,low=89.5,close=90.5)
    b[-1]=replace(b[-1],open=91.8,high=92.3,low=91.7,close=92,volume=300)
    if kind=="breakout":
        b=[replace(x,open=100+sin(i)*1.5,high=100+sin(i)*1.5+.3,low=100+sin(i)*1.5-.3,close=100+sin(i)*1.5,volume=100) for i,x in enumerate(base)]
        b[-2]=replace(b[-2],open=102,high=103.3,low=101.8,close=103)
        b[-1]=replace(b[-1],open=103.3,high=104.3,low=103.1,close=104,volume=300)
    if mirror:
        b=[replace(x,open=200-x.open,close=200-x.close,high=200-x.low,low=200-x.high) for x in b]
    return b

