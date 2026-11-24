from copy import deepcopy
import math
import unified_forex
from forex.providers import FixtureProvider

NOW=1800000000
TF={'M5':300,'M15':900,'M30':1800,'H1':3600,'H4':14400,'D1':86400}
META={'symbol':'XAUUSD','broker_symbol':'XAUUSD.test','market_type':'cfd','contract_type':'cfd',
      'broker_server':'synthetic-broker','price_kind':'bid','source':'fixture-test-only',
      'contract_size':100,'tick_size':.01,'tick_value':1,'tick_value_currency':'USD','point':.01,
      'volume_step':.01,'volume_min':.01,'volume_max':10,'stops_level':10,
      'account_currency':'USD','profit_currency':'USD','margin_currency':'USD','trade_allowed':True,
      'allowed_directions':['BUY','SELL'],'max_spread':1,
      'broker_hours_verified':True,'schedule_source':'synthetic-fixture-only',
      'broker_hours':{'timezone':'UTC','weekly':{str(i):[['00:00','24:00']] for i in range(7)}}}


def fixture(direction='BUY',n=220,frames=('M15','H4')):
    sign=1 if direction=='BUY' else -1
    candles={}
    for tf in frames:
        rows=[]
        for i in range(n):
            close=2000+sign*(i*.1+(2 if i==n-1 else 0))
            rows.append(dict(time=NOW-(n-i)*TF[tf],open=close-sign*.05,high=close+.2,low=close-.2,
                             close=close,tick_volume=30))
        candles[tf]=rows
    close=candles[frames[0]][-1]['close']
    return FixtureProvider({'XAUUSD':{'metadata':deepcopy(META),'quote':{'bid':close,'ask':close+.2,'time':NOW-1},'candles':candles}})


def multi_fixture(frames=('M15','H4','H1'),n=220):
    from forex.core import SYMBOLS
    base=fixture(n=n,frames=frames);data={}
    configs={'XAUUSD':(1,.01,1,100),'EURUSD':(.00055,.00001,.001,100000),
             'GBPUSD':(.00065,.00001,.001,100000),'USDJPY':(.075,.001,.1,100000)}
    for symbol in SYMBOLS:
        item=deepcopy(base.data['XAUUSD']);factor,tick,max_spread,contract=configs[symbol]
        item['metadata'].update(symbol=symbol,broker_symbol=symbol+'.test',tick_size=tick,point=tick,
                                max_spread=max_spread,contract_size=contract)
        if symbol!='XAUUSD':item['metadata'].update(market_type='forex_spot',contract_type='spot',profit_currency=symbol[-3:])
        for rows in item['candles'].values():
            for bar in rows:
                for key in ('open','high','low','close'):bar[key]*=factor
        item['quote'].update(bid=item['quote']['bid']*factor,ask=item['quote']['ask']*factor)
        data[symbol]=item
    return FixtureProvider(data)
