"""Actual Backend/Gateway product profiles; no network or persistent user DB."""
import asyncio
import os
from pathlib import Path
import sys
import uuid
import httpx
import pytest
from trade_gateway.app import Settings, create_app
REFERENCE=os.environ.get('TRADE_AI_BACKEND_REFERENCE')
pytestmark=pytest.mark.skipif(not REFERENCE,reason='Pinned backend checkout required')
if REFERENCE:sys.path.insert(0,str(Path(REFERENCE)/'backend'))

def test_profile_scope_ownership_retries_and_analyze(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    token='fixture-profile-integration-token-32'
    backend=backend_app(tmp_path/'backend.sqlite',mode='fixture',token=token,clock=lambda:1800000000000,domain_journal=True)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    auth=gateway.state.auth
    def session(account,**scope):return auth.exchange(auth.pairing(accounts=[account],**scope),str(uuid.uuid4()),'Fixture')['session']
    reader=session('MANUAL',scanner_write=True,paper_write=True)
    writer=session('MANUAL',profiles_write=True)
    other=session('AUTO',profiles_write=True)
    base='/api/v2/portfolios/MANUAL/strategy-profiles'
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net') as c:
            def h(s):return {'Authorization':'Bearer '+s}
            args={'idempotency_key':'profile-integration-1'}
            assert (await c.post(base,json=args,headers=h(reader))).status_code==403
            assert (await c.post(base,json=args,headers=h(other))).status_code==403
            r=await c.post(base,json=args,headers=h(writer)); assert r.status_code==200,r.text
            profile=r.json();key=profile['profile_id']
            assert (await c.post(base,json=args,headers=h(writer))).json()==profile
            assert (await c.get(base+'/'+key,headers=h(reader))).json()==profile
            assert (await c.get('/api/v2/portfolios/AUTO/strategy-profiles/'+key,headers=h(other))).status_code==404
            assert (await c.post(base+'/'+key+'/revisions',json={'idempotency_key':'revision-example-1'},headers=h(reader))).status_code==403
            body={'idempotency_key':'profile-analysis-1','data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1m','profile_id':key,'auto_paper':True}
            r=await c.post('/api/v2/analyze',json=body,headers=h(writer));assert r.status_code==200,r.text
            assert r.json()['auto_order_id'] is None
            assert r.json()['technical_methods']['profile_control']['trade_permission'] is False
            r=await c.post(base+'/'+key+'/evaluate',json={'analysis_id':r.json()['analysis_id']},headers=h(reader))
            assert r.status_code==200,r.text
            assert r.json()['trade_permission'] is False
            assert (await c.post('/api/v2/portfolios/MANUAL/orders',json={},headers=h(writer))).status_code==403
            revised=await c.post(base+'/'+key+'/revisions',json={'idempotency_key':'writer-revision-1'},headers=h(writer))
            assert revised.status_code==200,revised.text
            stale=await c.post(base+'/'+key+'/revisions',json={'idempotency_key':'writer-revision-2'},headers=h(writer))
            assert stale.status_code==409 and stale.json()['error']['code']=='PROFILE_REVISION_CONFLICT'
            auto_session=session('AUTO' ,profiles_write=True,scanner_write=True)
            auto_base='/api/v2/portfolios/AUTO/strategy-profiles'
            auto_profile=await c.post(auto_base,json={'idempotency_key':'auto-watch-profile','selection':{'bias_timeframe':'4H','setup_timeframe':'1H','trigger_timeframe':'15m'}},headers=h(auto_session))
            assert auto_profile.status_code==200,auto_profile.text
            auto_id=auto_profile.json()['profile_id']
            watch=await c.post('/api/v2/watchlist?include_profile=true',json={'symbol':'BTCUSDT','timeframe':'1H','profile_id':auto_id,'auto_paper':True},headers=h(auto_session))
            assert watch.status_code==200,watch.text
            assert watch.json()['profile_id']==auto_id and watch.json()['auto_paper'] is False
            assert (await c.get('/api/v2/watchlist?include_profile=true',headers=h(reader))).json()==[]
            legacy=(await c.get('/api/v2/watchlist',headers=h(auto_session))).json()[0]
            assert 'profile_id' not in legacy
            legacy.pop('watch_id');legacy['enabled']=False
            assert (await c.post('/api/v2/watchlist',json=legacy,headers=h(auto_session))).status_code==200
            assert (await c.get('/api/v2/watchlist?include_profile=true',headers=h(auto_session))).json()[0]['profile_id']==auto_id
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())

def test_gateway_rejects_valid_analysis_with_missing_requested_profile_proof(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    token='fixture-profile-binding-token-32'
    backend=backend_app(tmp_path/'backend.sqlite',mode='fixture',token=token,clock=lambda:1800000000000)
    class MissingProof(httpx.AsyncBaseTransport):
        async def handle_async_request(self,request):
            response=await httpx.ASGITransport(app=backend).handle_async_request(request)
            await response.aread()
            payload=response.json()
            if request.url.path.endswith('/analyze') and response.status_code==200:
                payload['technical_methods'].pop('profile_control',None)
            return httpx.Response(response.status_code,json=payload)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=MissingProof())
    auth=gateway.state.auth
    s=auth.exchange(auth.pairing(accounts=['MANUAL'],profiles_write=True),str(uuid.uuid4()),'Fixture')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+s['session']}) as c:
            r=await c.post('/api/v2/portfolios/MANUAL/strategy-profiles',json={'idempotency_key':'bound-result-profile'})
            assert r.status_code==200,r.text
            r=await c.post('/api/v2/analyze',json={'idempotency_key':'bound-result-analysis','risk_portfolio':'MANUAL','data_mode':'fixture','timeframe':'1m','profile_id':r.json()['profile_id']})
            assert r.status_code==502,r.text
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())
