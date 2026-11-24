"""Actual forward equity observations and mobile account isolation, no network."""
import asyncio,os,sys,uuid
from pathlib import Path
import httpx
import pytest
from trade_gateway.app import Settings,create_app
REFERENCE=os.environ.get('TRADE_AI_BACKEND_REFERENCE')
pytestmark=pytest.mark.skipif(not REFERENCE,reason='Pinned private Backend checkout required')
if REFERENCE:sys.path.insert(0,str(Path(REFERENCE)/'backend'))
def test_equity_history_mobile_read_scopes_and_source_values(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    token='fixture-equity-integration-token-32'
    backend=backend_app(tmp_path/'fixture.sqlite',mode='fixture',token=token,clock=lambda:1800000000000,domain_journal=True)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
    auth=gateway.state.auth;s=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Fixture')
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend),base_url='http://fixture',headers={'Authorization':'Bearer '+token}) as admin:
            a=(await admin.post('/api/v2/analyze',json={'idempotency_key':'history-analysis','data_mode':'fixture','risk_portfolio':'MANUAL'})).json()
            r=await admin.post('/api/v2/portfolios/MANUAL/orders',json={'idempotency_key':'history-order','analysis_id':a['analysis_id'],'quantity':'1'});assert r.status_code==200,r.text
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+s['session']}) as c:
            r=await c.get('/api/v2/portfolios/MANUAL/equity-history');assert r.status_code==200,r.text
            point=r.json()['points'][0];assert point['cash_quote']=='10000.00000000' and point['reserved_cash_quote']!='0.00000000'
            assert point['source']['kind']=='command' and point['chart_eligible'] is True
            assert (await c.get('/api/v2/portfolios/AUTO/equity-history')).status_code==403
            assert (await c.get('/api/v2/portfolios/MANUAL/equity-history?limit=999')).status_code==422
            assert (await c.post('/api/v2/portfolios/MANUAL/equity-history',json={})).status_code==403
            page=await c.get('/api/v2/portfolios/MANUAL/equity-history-window?limit=1')
            assert page.status_code==200,page.text
            assert page.json()['points'][0]==point
            cursor=page.json()['request_cursor']
            assert (await c.get('/api/v2/portfolios/MANUAL/equity-history-window',params={'cursor':cursor})).json()==page.json()
            assert (await c.get('/api/v2/portfolios/AUTO/equity-history-window',params={'cursor':cursor})).status_code==403
            assert (await c.post('/api/v2/portfolios/MANUAL/equity-history-window',json={})).status_code==403
            assert (await c.get('/api/v2/portfolios/MANUAL/equity-history-window?limit=201')).status_code==422
            writer=auth.exchange(auth.pairing(accounts=['MANUAL'],scanner_write=True),str(uuid.uuid4()),'Fixture writer')
            wrong=auth.exchange(auth.pairing(accounts=['AUTO'],scanner_write=True),str(uuid.uuid4()),'Fixture other account')
            headers={'Authorization':'Bearer '+writer['session']}
            t=await c.post('/api/v2/analysis-tracking',json={'analysis_id':a['analysis_id']},headers=headers);assert t.status_code==200,t.text
            path='/api/v2/analysis-tracking/'+t.json()['tracking_id']+'/notification-policy'
            assert (await c.get(path)).json()['notify_source_changes'] is False
            assert (await c.post(path,json={'notify_source_changes':True})).status_code==403
            assert (await c.post(path,json={'notify_source_changes':True},headers={'Authorization':'Bearer '+wrong['session']})).status_code==403
            enabled=await c.post(path,json={'notify_source_changes':True},headers=headers)
            assert enabled.status_code==200,enabled.text
            assert enabled.json()['notify_source_changes'] is True and enabled.json()['delivery_service']=='not_configured'
            assert (await c.post(path,json={'notify_source_changes':True},headers=headers)).json()==enabled.json()
            assert (await c.post(path,json={'notify_source_changes':'true'},headers=headers)).status_code==422
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())
