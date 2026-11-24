import asyncio,os,sys,uuid
from pathlib import Path
import httpx,pytest
from trade_gateway.contract import route
from trade_gateway.app import Settings,create_app

def test_research_is_read_only_contract_not_paper_write():
    operation,params=route('/api/v2/analyses/'+'a'*64+'/research','POST',False)
    assert operation is not None and params['analysis_id']=='a'*64
    assert route('/api/v2/portfolios/AUTO/orders','POST',False)[0] is None

@pytest.mark.skipif(not os.getenv('TRADE_AI_BACKEND_REFERENCE'),reason='Pinned private Backend checkout required')
def test_actual_read_scope_source_identity_and_cross_account_denial(tmp_path):
    sys.path.insert(0,str(Path(os.environ['TRADE_AI_BACKEND_REFERENCE'])/'backend'))
    from market_ai.v2.api import create_app as backend_app
    token='fixture-research-integration-not-secret'
    backend=backend_app(tmp_path/'backend.sqlite',mode='fixture',token=token,clock=lambda:1800000000000)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    auth=gateway.state.auth
    manual=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Research fixture')
    auto=auth.exchange(auth.pairing(accounts=['AUTO']),str(uuid.uuid4()),'Other fixture')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+manual['session']}) as c:
            a=(await c.post('/api/v2/analyze',json={'data_mode':'fixture','risk_portfolio':'MANUAL','timeframe':'1H','idempotency_key':'research-mobile-fixture'})).json()
            path='/api/v2/analyses/'+a['analysis_id']+'/research'
            cat=await c.get(path);assert cat.status_code==200,cat.text
            cat=cat.json();body={'source_record_id':cat['source_record_id'],'symbol':cat['symbol'],'timeframe':cat['timeframe'],'anchor_ms':cat['anchors'][-2]['open_time_ms'],'parameters':{'ema_period':8}}
            r=await c.post(path,json=body);assert r.status_code==200,r.text
            assert r.json()['anchored_vwap']['status']=='available' and not r.json()['trade_permission']
            assert (await c.post(path,json=body)).json()==r.json()
            for method in ('GET','POST'):
                denied=await c.request(method,path,json=body if method=='POST' else None,headers={'Authorization':'Bearer '+auto['session']})
                assert denied.status_code==403,denied.text
            assert (await c.post(path,json={**body,'source_record_id':'0'*64})).status_code==409
            assert (await c.post(path,json={**body,'parameters':{'risk_override':True}})).status_code==422
            assert (await c.post('/api/v2/portfolios/MANUAL/orders',json={})).status_code==403
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())

@pytest.mark.skipif(not os.getenv('TRADE_AI_BACKEND_REFERENCE'),reason='Pinned private Backend checkout required')
def test_older_backend_research_route_reports_update_required_after_real_parent_auth(tmp_path):
    sys.path.insert(0,str(Path(os.environ['TRADE_AI_BACKEND_REFERENCE'])/'backend'))
    from market_ai.v2.api import create_app as backend_app
    token='fixture-older-backend-research-32'
    backend=backend_app(tmp_path/'backend.sqlite',mode='fixture',token=token,clock=lambda:1800000000000)
    class OlderBackend(httpx.AsyncBaseTransport):
        legacy=True
        async def handle_async_request(self,request):
            if self.legacy and request.url.path.endswith('/research'):return httpx.Response(404,json={'error':{'code':'NOT_FOUND','message':'No legacy route'}})
            return await httpx.ASGITransport(app=backend).handle_async_request(request)
    transport=OlderBackend()
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=transport)
    auth=gateway.state.auth;s=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Legacy fixture')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+s['session']}) as c:
            a=await c.post('/api/v2/analyze',json={'data_mode':'fixture','risk_portfolio':'MANUAL','idempotency_key':'legacy-research-analysis'})
            assert a.status_code==200,a.text
            r=await c.get('/api/v2/analyses/'+a.json()['analysis_id']+'/research')
            assert r.status_code==404 and r.json()['error']['code']=='BACKEND_UPDATE_REQUIRED',r.text
            transport.legacy=False
            path='/api/v2/analyses/'+a.json()['analysis_id']+'/research'
            missing=await c.get(path,params={'timeframe':'5m'})
            assert missing.status_code==404 and missing.json()['error']['code']=='RESEARCH_UNAVAILABLE',missing.text
            catalog=(await c.get(path)).json()
            body={'source_record_id':catalog['source_record_id'],'symbol':catalog['symbol'],'timeframe':catalog['timeframe']}
            for changed,code,status in [({'source_record_id':'0'*64},'RESEARCH_SOURCE_MISMATCH',409),({'parameters':{'ema_period':999}},'INVALID_RESEARCH_PARAMETERS',422),({'anchor_ms':1},'INVALID_RESEARCH_ANCHOR',422)]:
                bad=await c.post(path,json={**body,**changed})
                assert bad.status_code==status and bad.json()['error']['code']==code,bad.text

        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())
