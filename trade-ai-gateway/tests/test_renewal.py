import asyncio
import json
import secrets
import uuid
import httpx
from trade_gateway.app import create_app,Settings
from trade_gateway.store import AuthStore


def propose(refresh, device):
    return dict(refresh_token=refresh,device_id=device,request_id='rq_'+secrets.token_urlsafe(32),next_refresh_token='tr_'+secrets.token_urlsafe(32),next_session='tg_'+secrets.token_urlsafe(32))


def paired(tmp_path, now, accounts=('AUTO','MANUAL')):
    store=AuthStore(tmp_path/'auth.sqlite',clock=lambda:now[0])
    device=str(uuid.uuid4())
    result=store.exchange(store.pairing(accounts=accounts,scanner_write=True),device,'Phone')
    refresh=store.grant_renewal(result['session'])
    return store,device,result,refresh


def test_rotation_hashes_lost_ack_exact_replay_restart_and_scope(tmp_path):
    now=[1000.]
    store,device,session,refresh=paired(tmp_path,now,('MANUAL',))
    request=propose(refresh,device)
    result=store.rotate(request)
    assert result['accounts']==['MANUAL'] and result['scopes']==session['scopes']
    assert store.session(session['session']) is None
    assert store.session(request['next_session'])['session_id']==result['session_id']
    reopened=AuthStore(store.path,clock=lambda:now[0])
    assert reopened.rotate(request)==result
    db=store.path.read_bytes()
    assert all(value.encode() not in db for key,value in request.items() if key in ('refresh_token','next_refresh_token','next_session'))
    # Lost acknowledgement can be reconciled even after access expiry; receipt
    # does not extend it. Only the successor refresh can issue fresh access.
    now[0]+=86401
    receipt=reopened.rotate(request)
    assert receipt['expires_at_ms']==result['expires_at_ms']
    next_result=reopened.rotate(propose(request['next_refresh_token'],device))
    assert next_result['renewal_expires_at_ms']==result['renewal_expires_at_ms']


def test_reuse_revokes_family_and_old_sid_revoke_reaches_descendants(tmp_path):
    now=[1000.]
    store,device,session,refresh=paired(tmp_path,now)
    request=propose(refresh,device);store.rotate(request)
    assert store.rotate(propose(refresh,device)) is None
    assert store.session(request['next_session']) is None
    assert store.rotate(propose(request['next_refresh_token'],device)) is None
    store,device,session,refresh=paired(tmp_path,now)
    request=propose(refresh,device);store.rotate(request)
    store.revoke(session['session_id'])
    assert store.session(request['next_session']) is None
    assert store.rotate(propose(request['next_refresh_token'],device)) is None


def test_absolute_expiry_repair_other_device_and_unknown_tokens(tmp_path):
    now=[1000.]
    store,device,session,refresh=paired(tmp_path,now)
    other=str(uuid.uuid4()); independent=store.exchange(store.pairing(),other,'Other')
    assert store.rotate(propose(refresh,other)) is None
    now[0]+=30*86400
    assert store.rotate(propose(refresh,device)) is None
    now[0]=2000
    store,device,session,refresh=paired(tmp_path,now)
    store.exchange(store.pairing(),device,'Re-paired')
    assert store.rotate(propose(refresh,device)) is None
    assert store.session(independent['session']) is not None
    assert store.rotate(propose('tr_'+secrets.token_urlsafe(32),device)) is None


def test_http_pair_opt_in_and_refresh_boundary(tmp_path):
    app=create_app(Settings('https://pc.example.ts.net',secrets.token_urlsafe(32),tmp_path/'db.sqlite'))
    device=str(uuid.uuid4())
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net') as c:
            body=dict(code=app.state.auth.pairing(accounts=['AUTO']),device_id=device,device_name='Android',renewal=True)
            r=await c.post('/gateway/pair',json=body)
            assert r.status_code==200
            paired=r.json();assert paired['refresh_token'].startswith('tr_')
            request=propose(paired['refresh_token'],device)
            r=await c.post('/gateway/refresh',json=request)
            assert r.status_code==200 and r.json()['accounts']==['AUTO']
            assert 'session' not in r.json() and 'refresh_token' not in r.json()
            assert (await c.post('/gateway/refresh',json={**request,'accounts':['MANUAL']})).status_code==422
            assert (await c.post('/gateway/refresh',json=request,headers={'Host':'evil.example'})).status_code==400
            assert (await c.post('/gateway/refresh',json=propose(paired['refresh_token'],device))).status_code==401
        await app.state.backend_client.aclose()
    asyncio.run(scenario())
