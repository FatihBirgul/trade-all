import asyncio
import json
import secrets
from pathlib import Path
import uuid
import httpx
import pytest
from trade_gateway.app import create_app, Settings
from trade_gateway.store import AuthStore

ORIGIN = 'https://pc.example.ts.net'


def run(coro):
    return asyncio.run(coro)


def setup(tmp_path, transport=None, clock=None, mode='live', timeout=.1):
    token = secrets.token_urlsafe(32)
    settings = Settings(ORIGIN, token, tmp_path/'auth.sqlite', timeout, mode)
    app = create_app(settings, backend_transport=transport, clock=clock)
    code = app.state.auth.pairing()
    current = app.state.auth.exchange(code, str(uuid.uuid4()), 'Test Android')
    return app, current, token


async def request(app, method='GET', path='/api/v2/health', current=None, **kwargs):
    headers = {'Authorization': 'Bearer '+current['session']} if current else {}
    headers.update(kwargs.pop('headers', {}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client:
        return await client.request(method, path, headers=headers, **kwargs)


def health(mode='live'):
    return {'status':'ok','version':'2','data_mode':mode,'provider':'offline_test','provider_status':'not_probed','storage':'sqlite','real_execution':False,'auth_required':True}


def test_pairing_single_use_hashes_expiry_revoke_devices(tmp_path):
    now = [1000.]
    store = AuthStore(tmp_path/'auth.sqlite', lambda: now[0])
    code = store.pairing()
    device = str(uuid.uuid4())
    a = store.exchange(code, device, 'A')
    assert a and store.exchange(code, device, 'A') is None
    assert code.encode() not in store.path.read_bytes()
    assert a['session'].encode() not in store.path.read_bytes()
    b = store.exchange(store.pairing(), str(uuid.uuid4()), 'B')
    store.revoke(a['session_id'])
    assert store.session(a['session']) is None and store.session(b['session'])
    now[0] += 86401
    assert store.session(b['session']) is None
    code = store.pairing()
    now[0] += 121
    assert store.exchange(code, device, 'A') is None


@pytest.mark.parametrize('authorization',[None,'Bearer wrong','Basic abc'])
def test_unauthorized_never_reaches_backend(tmp_path, authorization):
    upstream = []
    app, current, _ = setup(tmp_path, httpx.MockTransport(lambda req: upstream.append(req)))
    r = run(request(app, headers={'Authorization':authorization} if authorization else {}))
    assert r.status_code == 401 and not upstream


@pytest.mark.parametrize('method,path', [('POST','/api/v2/paper/events'),('POST','/api/v2/paper/poll'),('POST','/api/v2/portfolios/AUTO/orders'),('GET','/api/v2/http://evil.example'),('GET','/api/v2/health?url=http://evil.example'),('POST','/api/v2/scanner/tick')])
def test_allowlist_and_scopes(tmp_path, method, path):
    app, current, _ = setup(tmp_path)
    r = run(request(app, method, path, current))
    assert r.status_code in (403,422)


def test_auth_replacement_no_secrets_or_upstream_headers(tmp_path):
    seen = []
    def upstream(req):
        seen.append(req)
        return httpx.Response(200, json=health(), headers={'Set-Cookie':'private','X-Debug':'secret'})
    app, current, token = setup(tmp_path, httpx.MockTransport(upstream))
    r = run(request(app, current=current))
    assert r.status_code == 200 and seen[0].headers['authorization'] == 'Bearer '+token
    assert seen[0].url.host == '127.0.0.1' and seen[0].url.port == 8002
    assert token not in r.text and current['session'] not in r.text
    assert 'set-cookie' not in r.headers and 'x-debug' not in r.headers
    assert r.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('kind,status',[('closed',503),('timeout',504),('invalid',502),('redirect',502),('conflict',409),('unavailable',503),('owner_denied',503)])
def test_upstream_failure_semantics(tmp_path, kind, status):
    def upstream(req):
        if kind=='closed': raise httpx.ConnectError('secret never returned')
        if kind=='timeout': raise httpx.ReadTimeout('secret never returned')
        if kind=='invalid': return httpx.Response(200, text='<html>secret</html>')
        if kind=='redirect': return httpx.Response(302, headers={'Location':'https://evil.example'}, json={})
        return httpx.Response({'conflict':409,'unavailable':503,'owner_denied':401}[kind],json={'error':{'code':'IDEMPOTENCY_CONFLICT','message':'secret'}})
    app, current, token = setup(tmp_path, httpx.MockTransport(upstream))
    r = run(request(app, current=current))
    assert r.status_code == status and 'secret' not in r.text and token not in r.text


def test_session_revocation_and_expiry_during_request(tmp_path):
    now = [1000.]
    app, current, _ = setup(tmp_path, clock=lambda:now[0], transport=httpx.MockTransport(lambda req:httpx.Response(200,json=health())))
    now[0] += 86401
    assert run(request(app, current=current)).status_code == 401
    app.state.auth.revoke(current['session_id'])
    assert run(request(app,current=current)).status_code == 401


def test_pair_http_limits_body_host_and_query(tmp_path):
    app, current, _ = setup(tmp_path)
    assert run(request(app,'POST','/gateway/pair',json={'code':'x'})).status_code == 422
    assert run(request(app, current=current, headers={'Host':'evil.example'})).status_code == 400
    assert run(request(app,'POST','/gateway/pair',content='x'*17000)).status_code == 413
    assert run(request(app,current=current,path='/api/v2/analyses?limit=1000')).status_code == 422
    assert run(request(app,current=current,path='/api/v2/analyses?limit=1&limit=2')).status_code == 422
    for _ in range(5): run(request(app,'POST','/gateway/pair',json={}))
    assert run(request(app,'POST','/gateway/pair',json={})).status_code == 429


def test_production_rejects_fixture_and_unsafe_health(tmp_path):
    for body in [health('fixture'),{**health(), 'real_execution':True}]:
        app, current, _ = setup(tmp_path, httpx.MockTransport(lambda req:httpx.Response(200,json=body)))
        assert run(request(app,current=current)).status_code == 502


def test_total_deadline_and_revocation_before_delivery(tmp_path):
    async def slow(req):
        await asyncio.sleep(.2)
        return httpx.Response(200,json=health())
    app, current, _ = setup(tmp_path,httpx.MockTransport(slow),timeout=.01)
    assert run(request(app,current=current)).status_code==504
    async def revoke(req):
        app.state.auth.revoke(current['session_id'])
        return httpx.Response(200,json=health())
    app, current, _ = setup(tmp_path,httpx.MockTransport(revoke))
    assert run(request(app,current=current)).status_code==401


def test_backend_token_echo_and_oversize_are_blocked(tmp_path):
    app, current, token=setup(tmp_path)
    # Create a fresh app so its closed-over client has this controlled transport.
    settings=Settings(ORIGIN,token,tmp_path/'second.sqlite')
    for payload in [{**health(),'provider':token},'x'*2_000_001]:
        transport=httpx.MockTransport(lambda req:httpx.Response(200,json=payload))
        app=create_app(settings,backend_transport=transport)
        current=app.state.auth.exchange(app.state.auth.pairing(),str(uuid.uuid4()),'Boundary')
        r=run(request(app,current=current))
        assert r.status_code==502 and token not in r.text


def test_private_peer_https_and_origin_boundary(tmp_path):
    app,current,_=setup(tmp_path)
    assert run(request(app,current=current,headers={'X-Forwarded-Proto':'http'})).status_code==403
    assert run(request(app,current=current,headers={'Origin':'https://evil.example'})).status_code==403
    async def remote():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app,client=('192.0.2.1',1234)),base_url=ORIGIN) as client:
            return await client.get('/api/v2/health',headers={'Authorization':'Bearer '+current['session']})
    assert run(remote()).status_code==403


@pytest.mark.parametrize('enabled,grant,account', [(False,True,'MANUAL'),(True,False,'MANUAL'),(True,True,'AUTO')])
def test_paper_default_flag_and_explicit_scope_are_independent(tmp_path, enabled, grant, account):
    seen=[]
    app=create_app(Settings(ORIGIN,secrets.token_urlsafe(32),tmp_path/'auth.sqlite',paper_writes_enabled=enabled),backend_transport=httpx.MockTransport(lambda r:seen.append(r)))
    auth=app.state.auth
    current=auth.exchange(auth.pairing(accounts=['MANUAL'],paper_write=grant),str(uuid.uuid4()),'Feature gate')
    for suffix in ['orders','orders/'+'a'*64+'/cancel','positions/'+'b'*64+'/close','pause']:
        r=run(request(app,'POST','/api/v2/portfolios/'+account+'/'+suffix,current,json={}))
        assert r.status_code==403
    assert seen==[]


def test_tick_can_complete_after_short_general_deadline_and_lost_ack_is_observable(tmp_path):
    import time
    from threading import Event
    finished=Event()
    jobs=[]
    def completed():
        time.sleep(.05)
        jobs[:]=[dict(job_id=x*64,symbol=s,timeframe='1H',closed_bar_ms=100,status='completed',analysis_id=x*64,started_at_ms=101) for x,s in [('a','BTCUSDT'),('b','ETHUSDT')]]
        finished.set()
        return httpx.Response(200,json={'status':'completed','jobs':jobs})
    async def upstream(request):
        if request.url.path.endswith('/watchlist'):return httpx.Response(200,json=[])
        if request.url.path.endswith('/jobs'):return httpx.Response(200,json=jobs)
        return await asyncio.to_thread(completed)
    async def scenario():
        for index,limit,expected in [(0,.01,504),(1,.2,200)]:
            app=create_app(Settings(ORIGIN,secrets.token_urlsafe(32),tmp_path/str(index)/'db.sqlite',timeout=.01,scanner_timeout=limit),backend_transport=httpx.MockTransport(upstream))
            current=app.state.auth.exchange(app.state.auth.pairing(scanner_write=True),str(uuid.uuid4()),'Slow tick')
            finished.clear()
            result=await request(app,'POST','/api/v2/scanner/tick',current)
            assert result.status_code==expected,result.text
            # Wait for the simulated durable commit, not an assumed thread dispatch
            # latency. Keep both original HTTP deadlines/status assertions intact.
            assert await asyncio.to_thread(finished.wait,2), "Fixture worker did not commit"
            observed=await request(app,'GET','/api/v2/scanner/jobs',current)
            assert len(observed.json())==2 and all(j['status']=='completed' for j in observed.json())
            if expected==200:assert result.json()['status']=='completed'
            await app.state.backend_client.aclose()
    run(scenario())
