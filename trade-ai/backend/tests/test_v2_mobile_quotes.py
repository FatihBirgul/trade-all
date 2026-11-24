"""No external network, real FastAPI app, temporary DBs and controlled HTTP source."""
import json
import secrets
from decimal import Decimal
import httpx
import pytest
from fastapi.testclient import TestClient
from market_ai.v2.quotes import QuoteService,SYMBOLS,HOUR
from market_ai.v2.api import create_app


def source(now,seen,broken):
    def handler(request):
        seen.append(request)
        assert request.method=='GET' and request.url.host=='data-api.binance.vision'
        assert 'authorization' not in request.headers
        if broken[0]:return httpx.Response(503)
        if request.url.path.endswith('24hr'):
            assert json.loads(request.url.params['symbols'])==list(SYMBOLS)
            return httpx.Response(200,json=[dict(symbol=s,lastPrice='123.4500',priceChangePercent='-1.25',closeTime=now[0]) for s in SYMBOLS])
        assert request.url.path.endswith('/klines') and request.url.params['interval']=='1h'
        end=now[0]//HOUR*HOUR
        return httpx.Response(200,json=[[end-(24-i)*HOUR,'120','130','110','123.45','10',end-(23-i)*HOUR-1,'1',1,'1','1','0'] for i in range(24)])
    return httpx.MockTransport(handler)


def test_cache_bounds_stale_failure_and_no_paper_mutations(tmp_path):
    now=[1792584000000];seen=[];broken=[False]
    token=secrets.token_urlsafe(32);app=create_app(tmp_path/'product.sqlite',mode='live',token=token,clock=lambda:now[0])
    app.state.quotes.transport=source(now,seen,broken)
    with TestClient(app) as c:
        assert c.get('/api/v2/quotes').status_code==401 and not seen
        c.headers['Authorization']='Bearer '+token
        r=c.get('/api/v2/quotes');assert r.status_code==200
        data=r.json();assert not data['stale'] and data['real_execution'] is False
        assert len(data['items'])==3 and all(len(row['history'])==24 for row in data['items'])
        assert len(seen)==4
        assert c.get('/api/v2/quotes').json()==data and len(seen)==4
        now[0]+=31000;broken[0]=True
        failed=c.get('/api/v2/quotes').json()
        assert failed['stale'] and failed['provider_status']=='unavailable'
        assert failed['fetched_at_ms']==data['fetched_at_ms']
        assert len(seen)==5
        assert c.get('/api/v2/quotes').json()==failed and len(seen)==5
        assert c.get('/api/v2/portfolios/MANUAL/orders').json()==[]
        assert c.post('/api/v2/quotes').status_code==405


def test_no_cache_unavailable_fixture_and_malformed_source(tmp_path):
    now=[1792584000000]
    service=QuoteService(lambda:now[0],httpx.MockTransport(lambda r:httpx.Response(200,json=[dict(symbol=s,lastPrice='NaN',priceChangePercent='1',closeTime=now[0]) for s in SYMBOLS])))
    with pytest.raises(Exception,match='Public market source unavailable'):service.get()
    token=secrets.token_urlsafe(32); app=create_app(tmp_path/'fixture.sqlite',mode='fixture',token=token)
    with TestClient(app) as c:
        assert c.get('/api/v2/quotes',headers={'Authorization':'Bearer '+token}).status_code==503
