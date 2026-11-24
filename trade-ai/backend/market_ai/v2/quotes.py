"""Bounded public market READS. No engine, ledger, worker or DB mutations."""
import json
import re
import threading
from decimal import Decimal
from secrets import compare_digest
from typing import Literal
import httpx
from pydantic import Field
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .api_models import Model, ErrorResponse
from .errors import V2Error

SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT')
HOUR=3600000

class QuotePoint(Model):
    time_ms: int
    price: str

class MarketQuote(Model):
    symbol: Literal['BTCUSDT','ETHUSDT','SOLUSDT']
    price: str
    change_percent_24h: str
    source_time_ms: int  # rolling-statistics end, NOT a claimed last-trade timestamp
    history: list[QuotePoint] = Field(max_length=24)
    chart_status: Literal['available','unavailable']

class QuotesResponse(Model):
    data_mode: Literal['live'] = 'live'
    provider: Literal['binance_public_spot'] = 'binance_public_spot'
    fetched_at_ms: int
    stale: bool
    provider_status: Literal['available','unavailable']
    refresh_after_seconds: Literal[30] = 30
    chart_timeframe: Literal['1H'] = '1H'
    items: list[MarketQuote] = Field(min_length=3,max_length=3)
    real_execution: Literal[False] = False


def decimal_string(value, positive=False):
    if not isinstance(value,str) or len(value)>80 or not re.fullmatch(r'-?[0-9]+(?:\.[0-9]+)?',value): raise ValueError()
    number=Decimal(value)
    if not number.is_finite() or abs(number)>Decimal('1e24') or (positive and number<=0): raise ValueError()
    return value

class QuoteService:
    def __init__(self, clock, transport=None):
        self.clock,self.transport=clock,transport
        self.lock=threading.Lock()
        self.cached=None;self.last_attempt=None;self.failed=False
        self.charts={};self.chart_attempt=None

    def _get(self, path, params):
        if path not in ('/api/v3/ticker/24hr','/api/v3/klines'): raise ValueError()
        with httpx.Client(timeout=1.5,transport=self.transport,trust_env=False,follow_redirects=False) as client:
            with client.stream('GET','https://data-api.binance.vision'+path,params=params) as response:
                response.raise_for_status(); data=bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data)>100000: raise ValueError()
        return json.loads(data,parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))

    def _chart(self,symbol,now):
        raw=self._get('/api/v3/klines',dict(symbol=symbol,interval='1h',limit=24,endTime=now//HOUR*HOUR-1))
        if not isinstance(raw,list) or not 2<=len(raw)<=24: raise ValueError()
        points=[]
        for row in raw:
            if not isinstance(row,list) or len(row)!=12 or type(row[0]) is not int or type(row[6]) is not int: raise ValueError()
            start,end=row[0],row[6]+1
            if start%HOUR or end-start!=HOUR or end>now or (points and start!=points[-1]['time_ms']): raise ValueError()
            points.append(dict(time_ms=end,price=decimal_string(row[4],True)))
        if not 0<=now-points[-1]['time_ms']<=2*HOUR: raise ValueError()
        return points

    def get(self):
        if not self.lock.acquire(timeout=1): raise V2Error('QUOTE_BUSY','Market read in progress',503)
        try:
            now=self.clock()
            if self.last_attempt is None or now-self.last_attempt>=30000:
                self.last_attempt=now
                try:
                    raw=self._get('/api/v3/ticker/24hr',{'symbols':json.dumps(SYMBOLS,separators=(',',':'))})
                    if not isinstance(raw,list) or len(raw)!=3 or {r['symbol'] for r in raw}!=set(SYMBOLS): raise ValueError()
                    rows=[]
                    for symbol in SYMBOLS:
                        r=next(r for r in raw if r['symbol']==symbol); timestamp=r['closeTime']
                        if type(timestamp) is not int or not -5000<=now-timestamp<=60000: raise ValueError()
                        rows.append(dict(symbol=symbol,price=decimal_string(r['lastPrice'],True),change_percent_24h=decimal_string(r['priceChangePercent']),source_time_ms=timestamp))
                    self.cached=dict(fetched_at_ms=now,items=rows);self.failed=False
                except (httpx.HTTPError,ValueError,KeyError,TypeError,ArithmeticError): self.failed=True
            if self.cached is None: raise V2Error('QUOTE_PROVIDER_UNAVAILABLE','Public market source unavailable',503)
            if not self.failed and (self.chart_attempt is None or now-self.chart_attempt>=300000):
                self.chart_attempt=now
                for symbol in SYMBOLS:
                    try:self.charts[symbol]=self._chart(symbol,now)
                    except (httpx.HTTPError,ValueError,KeyError,TypeError,ArithmeticError):self.charts[symbol]=[]
            items=[]
            for row in self.cached['items']:
                points=self.charts.get(row['symbol'],[])
                if points and now-points[-1]['time_ms']>2*HOUR:points=[]
                items.append(MarketQuote(**row,history=points,chart_status='available' if points else 'unavailable'))
            stale=self.failed or now-self.cached['fetched_at_ms']>60000 or any(now-r.source_time_ms>60000 for r in items)
            return QuotesResponse(fetched_at_ms=self.cached['fetched_at_ms'],items=items,stale=stale,provider_status='unavailable' if self.failed else 'available')
        finally:self.lock.release()


def install_quotes(app,runtime):
    auth=HTTPBearer(auto_error=False,scheme_name='V2Bearer')
    def require(credentials: HTTPAuthorizationCredentials | None=Depends(auth)):
        if credentials is None or not compare_digest(credentials.credentials.encode(),runtime.token.encode()):
            raise V2Error('UNAUTHORIZED','Valid local V2 bearer required',401)
    service=QuoteService(runtime.clock)
    app.state.quotes=service
    router=APIRouter(prefix='/api/v2',tags=['Trade AI V2'],dependencies=[Depends(require)])
    @router.get('/quotes',response_model=QuotesResponse,responses={401:{'model':ErrorResponse,'description':'Unauthorized'},503:{'model':ErrorResponse,'description':'Service Unavailable'}})
    def quotes():
        if runtime.db.mode!='live':raise V2Error('QUOTE_LIVE_ONLY','Fixture prices are never returned as live quotes',503)
        return service.get()
    app.include_router(router)
