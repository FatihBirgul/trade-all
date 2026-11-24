"""Real unmodified V2 application, temporary product DBs, no public network."""
import os
from pathlib import Path
import secrets
import sys
import uuid
import asyncio
import httpx
import pytest
from trade_gateway.app import create_app, Settings

REFERENCE = os.environ.get('TRADE_AI_BACKEND_REFERENCE')
pytestmark = pytest.mark.skipif(not REFERENCE, reason='Set pinned, read-only backend checkout path for integration tests')
if REFERENCE:
    sys.path.insert(0, str(Path(REFERENCE)/'backend'))


def test_real_v2_fixture_chain_snapshots_idempotency_and_accounts(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    token = secrets.token_urlsafe(32)
    backend = backend_app(tmp_path/'backend-fixture.sqlite',mode='fixture',token=token,clock=lambda:1792584000000)
    gateway = create_app(Settings('https://pc.example.ts.net',token,tmp_path/'gateway.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    auth = gateway.state.auth
    session = auth.exchange(auth.pairing(),str(uuid.uuid4()),'Fixture integration')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+session['session']}) as client:
            assert (await client.get('/api/v2/health')).json()['data_mode']=='fixture'
            assert (await client.get('/api/v2/markets')).status_code==200
            for symbol in ['BTCUSDT','ETHUSDT','SOLUSDT']:
                body={'symbol':symbol,'market':'crypto_spot','timeframe':'1H','timeframes':['15m','4H'],'data_mode':'fixture','risk_portfolio':'MANUAL','auto_paper':True,'idempotency_key':'integration-'+symbol}
                r=await client.post('/api/v2/analyze',json=body)
                assert r.status_code==200,r.text
                analysis=r.json()
                assert analysis['risk_portfolio']=='MANUAL' and analysis['auto_order_id'] is None
                repeat=await client.post('/api/v2/analyze',json=body)
                assert repeat.json()['analysis_id']==analysis['analysis_id']
                detail=await client.get('/api/v2/analyses/'+analysis['analysis_id'])
                assert detail.json()['symbol']==symbol
                candles=await client.get('/api/v2/analyses/'+analysis['analysis_id']+'/candles?limit=40')
                assert candles.status_code==200,candles.text
                assert candles.json()['analysis_id']==analysis['analysis_id'] and candles.json()['snapshot_only'] is True
                assert len(candles.json()['candles'])==40
            history=await client.get('/api/v2/analyses')
            assert len(history.json())==3
            for account in ['AUTO','MANUAL']:
                for suffix in ['orders','positions','transactions']:
                    assert (await client.get('/api/v2/portfolios/'+account+'/'+suffix)).json()==[]
            for endpoint in ['portfolios','performance','scanner','scanner/jobs','watchlist','notifications']:
                r=await client.get('/api/v2/'+endpoint)
                assert r.status_code==200,(endpoint,r.text)
            other=auth.exchange(auth.pairing(),str(uuid.uuid4()),'Conflict test')
            conflict=await client.post('/api/v2/analyze',json={**body,'symbol':'BTCUSDT'},headers={'Authorization':'Bearer '+other['session']})
            assert conflict.status_code==409,conflict.text
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())


def test_real_v2_live_provider_unavailable_is_wait_not_fake_success(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    from market_ai.v2.spot_provider import ProviderUnavailable
    class Offline:
        mode='live'; name='controlled_offline'; venue='controlled_test'; source_name='controlled_offline'
        def rules(self,*args): raise ProviderUnavailable('controlled_offline')
        def candles(self,*args): raise ProviderUnavailable('controlled_offline')
    token=secrets.token_urlsafe(32)
    backend=backend_app(tmp_path/'offline-live.sqlite',mode='live',token=token,provider=Offline())
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite'),backend_transport=httpx.ASGITransport(app=backend))
    current=gateway.state.auth.exchange(gateway.state.auth.pairing(),str(uuid.uuid4()),'Unavailable test')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+current['session']}) as c:
            r=await c.post('/api/v2/analyze',json={'idempotency_key':'offline-live-test','data_mode':'live'})
            assert r.status_code==200,r.text
            a=r.json()
            assert a['direction']=='WAIT' and a['price'] is None and a['levels'] is None
            assert a['reason']=='provider_unavailable'
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())


def test_explicit_scanner_grant_forces_auto_paper_off_and_account_scope(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    token=secrets.token_urlsafe(32)
    backend=backend_app(tmp_path/'scanner-fixture.sqlite',mode='fixture',token=token,clock=lambda:1792584000000)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    auth=gateway.state.auth
    current=auth.exchange(auth.pairing(accounts=['AUTO'],scanner_write=True),str(uuid.uuid4()),'Scoped scanner')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+current['session']}) as c:
            other=auth.exchange(auth.pairing(),str(uuid.uuid4()),'Other authorized device')
            analysis=await c.post('/api/v2/analyze',json={'data_mode':'fixture','risk_portfolio':'MANUAL','idempotency_key':'manual-scope-analysis'},headers={'Authorization':'Bearer '+other['session']})
            assert analysis.status_code==200,analysis.text
            aid=analysis.json()['analysis_id']
            assert (await c.get('/api/v2/analyses/'+aid)).status_code==403
            assert (await c.get('/api/v2/analyses/'+aid+'/candles')).status_code==403
            assert (await c.get('/api/v2/analyses')).json()==[]
            assert (await c.get('/api/v2/notifications')).status_code==403
            portfolios=await c.get('/api/v2/portfolios')
            assert [p['portfolio_id'] for p in portfolios.json()]==['AUTO']
            assert (await c.get('/api/v2/portfolios/MANUAL/orders')).status_code==403
            denied=await c.post('/api/v2/analyze',json={'data_mode':'fixture','risk_portfolio':'MANUAL','idempotency_key':'account-denied'})
            assert denied.status_code==422
            watch=await c.post('/api/v2/watchlist',json={'symbol':'BTCUSDT','timeframe':'1H','enabled':True,'auto_paper':True})
            assert watch.status_code==200,watch.text
            assert watch.json()['auto_paper'] is False
            assert (await c.post('/api/v2/scanner/pause',json={'paused':True})).status_code==200
            assert (await c.post('/api/v2/scanner/tick')).json()['status']=='paused'
            assert (await c.post('/api/v2/scanner/pause',json={'paused':False})).status_code==200
            result=await c.post('/api/v2/scanner/tick')
            assert result.status_code==200,result.text
            assert (await c.get('/api/v2/portfolios/AUTO/orders')).json()==[]
            assert (await c.get('/api/v2/scanner/jobs')).status_code==200
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())


def test_all_markets_timeframes_quality_snapshots_scanner_outbox(tmp_path):
    """Real engine, explicit fixture mode, 18 market/timeframe combinations."""
    from market_ai.v2.api import create_app as backend_app
    now=[1792584000000]
    token=secrets.token_urlsafe(32)
    backend=backend_app(tmp_path/'matrix.sqlite',mode='fixture',token=token,clock=lambda:now[0])
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    auth=gateway.state.auth
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net') as c:
            for symbol in ['BTCUSDT','ETHUSDT','SOLUSDT']:
                current=auth.exchange(auth.pairing(scanner_write=True),str(uuid.uuid4()),symbol)
                c.headers['Authorization']='Bearer '+current['session']
                for tf in ['1m','5m','15m','1H','4H','1D']:
                    r=await c.post('/api/v2/analyze',json={'symbol':symbol,'timeframe':tf,'timeframes':['15m','4H'],'data_mode':'fixture','risk_portfolio':'AUTO','idempotency_key':'matrix-'+symbol+'-'+tf})
                    assert r.status_code==200,r.text
                    a=r.json()
                    assert len(a['strategy_setups'])==4
                    assert set(['rsi14','macd','ema20','ema50'])<=set(a['indicators'])
                    assert set(['fvg','structure','liquidity_sweep','vwap'])<=set(a['technical_methods'])
                    assert a['auto_order_id'] is None
                    before=(await c.get('/api/v2/analyses/'+a['analysis_id'])).json()
                    snapshot=(await c.get('/api/v2/analyses/'+a['analysis_id']+'/candles?timeframe='+tf+'&limit=40')).json()
                    assert snapshot['snapshot_only'] is True and snapshot['analysis_id']==a['analysis_id']
                    assert len(snapshot['source_record_id'])==64
                    assert (await c.get('/api/v2/analyses/'+a['analysis_id']+'/candles?timeframe='+tf+'&limit=40')).json()==snapshot
                    assert (await c.get('/api/v2/analyses/'+a['analysis_id'])).json()==before
            # A new session has a fresh analysis allowance, same database records.
            current=auth.exchange(auth.pairing(scanner_write=True),str(uuid.uuid4()),'Quality and scanner')
            c.headers['Authorization']='Bearer '+current['session']
            for case in ['stale','gap','unfinished','mixed']:
                a=(await c.post('/api/v2/analyze',json={'fixture_case':case,'data_mode':'fixture','idempotency_key':'quality-'+case})).json()
                assert a['direction']=='WAIT' and a['levels'] is None and a['quality']['ok'] is False
            first=(await c.get('/api/v2/analyses?limit=20')).json()
            second=(await c.get('/api/v2/analyses?limit=20&offset=20')).json()
            assert len(first)==20 and len(second)==2
            assert not {a['analysis_id'] for a in first}&{a['analysis_id'] for a in second}
            assert (await c.get('/api/v2/scanner')).json()['paused'] is True
            for symbol in ['BTCUSDT','ETHUSDT','SOLUSDT']:
                assert (await c.post('/api/v2/watchlist',json={'symbol':symbol,'timeframe':'15m'})).status_code==200
            await c.post('/api/v2/scanner/pause',json={'paused':False})
            tick=await c.post('/api/v2/scanner/tick')
            assert tick.status_code==200,tick.text
            assert len(tick.json()['jobs'])==2
            for job in tick.json()['jobs']:
                assert job['analysis_id']
                assert (await c.get('/api/v2/analyses/'+job['analysis_id'])).status_code==200
            outbox=(await c.get('/api/v2/notifications')).json()
            assert len(outbox)==2 and all(n['delivery_status']=='pending' for n in outbox)
            assert all(n['details']['analysis_id'] for n in outbox)
            await c.post('/api/v2/scanner/pause',json={'paused':True})
            disabled=await c.post('/api/v2/watchlist',json={'symbol':'BTCUSDT','timeframe':'15m','enabled':False})
            assert disabled.json()['enabled'] is False
            assert len((await c.get('/api/v2/watchlist')).json())==3
            assert (await c.get('/api/v2/portfolios/AUTO/orders')).json()==[]
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())


def test_mobile_tick_refuses_existing_pc_auto_watch(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    token=secrets.token_urlsafe(32)
    backend=backend_app(tmp_path/'unsafe-watch.sqlite',mode='fixture',token=token,clock=lambda:1792584000000)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    session=gateway.state.auth.exchange(gateway.state.auth.pairing(scanner_write=True),str(uuid.uuid4()),'Tick guard')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend),base_url='http://127.0.0.1:8002',headers={'Authorization':'Bearer '+token}) as admin:
            assert (await admin.post('/api/v2/watchlist',json={'symbol':'BTCUSDT','auto_paper':True})).status_code==200
            await admin.post('/api/v2/scanner/pause',json={'paused':False})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+session['session']}) as c:
            r=await c.post('/api/v2/scanner/tick')
            assert r.status_code==409 and r.json()['error']['code']=='SCANNER_AUTO_PAPER_DISABLED'
            assert (await c.get('/api/v2/scanner/jobs')).json()==[]
            assert (await c.get('/api/v2/portfolios/AUTO/orders')).json()==[]
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())


def test_quote_contract_through_gateway_read_only(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    if not hasattr(__import__('market_ai.v2.api',fromlist=['create_app']),'create_app'):pytest.skip('Backend missing')
    token=secrets.token_urlsafe(32);now=1792584000000
    backend=backend_app(tmp_path/'quote-backend.sqlite',mode='live',token=token,clock=lambda:now)
    if not hasattr(backend.state,'quotes'):pytest.skip('Pinned baseline has no additive quote endpoint')
    def source(request):
        assert 'authorization' not in request.headers and request.url.host=='data-api.binance.vision'
        if request.url.path.endswith('24hr'):return httpx.Response(200,json=[dict(symbol=s,lastPrice='100.00',priceChangePercent='1.5',closeTime=now) for s in ['BTCUSDT','ETHUSDT','SOLUSDT']])
        return httpx.Response(503)
    backend.state.quotes.transport=httpx.MockTransport(source)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite'),backend_transport=httpx.ASGITransport(app=backend))
    auth=gateway.state.auth;session=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Read only')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+session['session']}) as c:
            r=await c.get('/api/v2/quotes');assert r.status_code==200,r.text
            assert len(r.json()['items'])==3 and r.json()['data_mode']=='live'
            assert (await c.get('/api/v2/quotes?url=https://evil.example')).status_code==422
            assert (await c.post('/api/v2/quotes')).status_code==403
            assert (await c.get('/api/v2/portfolios/MANUAL/orders')).json()==[]
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())


def test_follow_gateway_scope_and_idempotent_stop_before_mutation(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    token=secrets.token_urlsafe(32)
    from market_ai.v2.spot_provider import FixtureSpotProvider,ProviderUnavailable
    class Switchable(FixtureSpotProvider):
        offline=True
        def rules(self,symbol):
            if self.offline:raise ProviderUnavailable('controlled offline')
            return super().rules(symbol)
    provider=Switchable()
    backend=backend_app(tmp_path/'follow.sqlite',mode='fixture',token=token,provider=provider,clock=lambda:1792584000000)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    auth=gateway.state.auth
    all_=auth.exchange(auth.pairing(scanner_write=True),str(uuid.uuid4()),'Owner')
    manual=auth.exchange(auth.pairing(accounts=['MANUAL'],scanner_write=True),str(uuid.uuid4()),'Manual device')
    read=auth.exchange(auth.pairing(),str(uuid.uuid4()),'Reader')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+all_['session']}) as c:
            auto=(await c.post('/api/v2/analyze',json={'data_mode':'fixture','risk_portfolio':'AUTO','idempotency_key':'follow-auto-test'})).json()
            track=await c.post('/api/v2/analysis-tracking',json={'analysis_id':auto['analysis_id']})
            assert track.status_code==200,track.text
            record=track.json();key=record['tracking_id']
            provider.offline=False
            backend.state.tracking.tick()
            events=(await c.get('/api/v2/notifications')).json()
            assert len(events)==1 and events[0]['delivery_status']=='pending'
            assert events[0]['details']['tracking_id']==key
            aid=events[0]['details']['analysis_id']
            assert (await c.get('/api/v2/analyses/'+aid)).json()['risk_portfolio']=='AUTO'
            assert (await c.get('/api/v2/analyses/'+aid+'/candles')).json()['snapshot_only'] is True
            backend.state.tracking.tick()
            assert len((await c.get('/api/v2/notifications')).json())==1
            for account in ['AUTO','MANUAL']:
                assert (await c.get('/api/v2/portfolios/'+account+'/orders')).json()==[]

            assert (await c.post('/api/v2/analysis-tracking',json={'analysis_id':auto['analysis_id']})).json()['tracking_id']==key
            assert (await c.post('/api/v2/analysis-tracking',json={'analysis_id':auto['analysis_id']},headers={'Authorization':'Bearer '+read['session']})).status_code==403
            denied=await c.post('/api/v2/analysis-tracking/'+key,json={'enabled':False},headers={'Authorization':'Bearer '+manual['session']})
            assert denied.status_code==403
            assert (await c.get('/api/v2/analysis-tracking/'+key,headers={'Authorization':'Bearer '+manual['session']})).status_code==403
            assert (await c.get('/api/v2/analysis-tracking/'+key)).json()['enabled'] is True
            assert (await c.get('/api/v2/analysis-tracking',headers={'Authorization':'Bearer '+manual['session']})).json()==[]
            assert (await c.post('/api/v2/analysis-tracking/'+key,json={'enabled':False})).json()['enabled'] is False
            assert (await c.post('/api/v2/analysis-tracking/'+key,json={'enabled':False})).json()['enabled'] is False
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())
