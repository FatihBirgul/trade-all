"""Profile grants are independent of scanner/paper grants, even with no backend."""
import asyncio
import uuid
import httpx
from trade_gateway.app import Settings,create_app
from trade_gateway.contract import route

def test_profiles_are_not_paper_writes_and_routes_are_explicit():
    path='/api/v2/portfolios/MANUAL/strategy-profiles'
    assert route(path,'POST',False)[0] is not None
    assert route(path+'/'+'a'*64+'/revisions','POST',False)[0] is not None
    assert route(path+'/wrong/revisions','POST',True)[0] is None
    assert route('/api/v2/portfolios/MANUAL/orders','POST',False)[0] is None

def test_legacy_grants_do_not_authorize_profiles_or_cross_account_read(tmp_path):
    calls=[]
    app=create_app(Settings('https://pc.example.ts.net','fixture-backend-test-token-32',tmp_path/'auth.sqlite'),backend_transport=httpx.MockTransport(lambda r:calls.append(r)))
    auth=app.state.auth
    s=auth.exchange(auth.pairing(accounts=['MANUAL'],scanner_write=True,paper_write=True),str(uuid.uuid4()),'Fixture')
    assert 'profiles:write' not in s['scopes']
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+s['session']}) as c:
            assert (await c.post('/api/v2/portfolios/MANUAL/strategy-profiles',json={'idempotency_key':'fixture-profile-1'})).status_code==403
            assert (await c.get('/api/v2/portfolios/AUTO/strategy-profiles')).status_code==403
        await app.state.backend_client.aclose()
    asyncio.run(scenario())
    assert not calls

def test_profile_grant_never_adds_paper_or_scanner_permissions(tmp_path):
    from trade_gateway.store import AuthStore
    store=AuthStore(tmp_path/'auth.sqlite')
    session=store.exchange(store.pairing(profiles_write=True),str(uuid.uuid4()),'Fixture')
    assert set(session['scopes'])=={'read','analyze','profiles:write'}

def test_manual_only_scanner_grant_cannot_mutate_auto_watchlist(tmp_path):
    calls=[]
    def upstream(r):
        calls.append(r)
        return httpx.Response(200,json={'watch_id':'BTCUSDT:1H','symbol':'BTCUSDT','timeframe':'1H','enabled':True,'auto_paper':False})
    app=create_app(Settings('https://pc.example.ts.net','fixture-backend-test-token-32',tmp_path/'auth.sqlite'),backend_transport=httpx.MockTransport(upstream))
    auth=app.state.auth
    s=auth.exchange(auth.pairing(accounts=['MANUAL'],scanner_write=True),str(uuid.uuid4()),'Fixture')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+s['session']}) as c:
            assert (await c.post('/api/v2/watchlist',json={'symbol':'BTCUSDT'})).status_code==403
        await app.state.backend_client.aclose()
    asyncio.run(scenario())
    assert not calls

def test_missing_legacy_profile_endpoint_is_update_required_but_unknown_profile_is_not(tmp_path):
    async def scenario():
        for code,expected in [('NOT_FOUND','BACKEND_UPDATE_REQUIRED'),('PROFILE_NOT_FOUND','PROFILE_NOT_FOUND')]:
            app=create_app(Settings('https://pc.example.ts.net','fixture-legacy-profile-token-32',tmp_path/(code+'.sqlite')),backend_transport=httpx.MockTransport(lambda r:httpx.Response(404,json={'error':{'code':code,'message':'Controlled older Backend'}})))
            auth=app.state.auth;s=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Legacy fixture')
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+s['session']}) as c:
                r=await c.get('/api/v2/portfolios/MANUAL/strategy-profiles')
                assert r.status_code==404 and r.json()['error']['code']==expected,r.text
            await app.state.backend_client.aclose()
    asyncio.run(scenario())
