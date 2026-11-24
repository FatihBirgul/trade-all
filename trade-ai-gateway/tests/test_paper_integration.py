"""Paper writes enabled ONLY here. Unmodified V2 app, temporary fixture DB."""
import asyncio
import os
from pathlib import Path
import secrets
import sys
import uuid
import httpx
import pytest
from trade_gateway.app import create_app, Settings

REFERENCE = os.environ.get('TRADE_AI_BACKEND_REFERENCE')
pytestmark = pytest.mark.skipif(not REFERENCE, reason='Pinned read-only backend checkout required')
if REFERENCE:
    sys.path.insert(0, str(Path(REFERENCE)/'backend'))


def test_paper_lifecycle_lost_ack_restart_scope_and_recovery(tmp_path):
    from market_ai.v2.api import create_app as backend_app
    now = [1792584000000]
    token = secrets.token_urlsafe(32)
    backend = backend_app(tmp_path/'paper.sqlite', mode='fixture', token=token, clock=lambda:now[0])
    drop = [False]
    class LostAck(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            response = await httpx.ASGITransport(app=backend).handle_async_request(request)
            if drop[0] and request.method=='POST' and request.url.path.endswith('/orders'):
                drop[0]=False
                await response.aread()
                raise httpx.ReadTimeout('controlled committed-but-lost acknowledgement')
            return response
    def gateway(enabled):
        return create_app(Settings('https://pc.example.ts.net', token, tmp_path/'auth.sqlite', 10, 'fixture', enabled), backend_transport=LostAck())
    app=gateway(True)
    auth=app.state.auth
    def pair(accounts=('AUTO','MANUAL'),grant=True):
        return auth.exchange(auth.pairing(accounts=accounts,paper_write=grant),str(uuid.uuid4()),'Paper test')['session']
    session=pair(); manual=pair(('MANUAL',)); read=pair(grant=False)
    headers={'Authorization':'Bearer '+session}
    async def scenario():
        nonlocal app,backend
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net',headers=headers) as c:
            a=(await c.post('/api/v2/analyze',json={'data_mode':'fixture','risk_portfolio':'MANUAL','idempotency_key':'paper-analysis-001'})).json()
            assert a['risk']['status']=='eligible_for_paper'
            path='/api/v2/portfolios/MANUAL/orders'
            body={'analysis_id':a['analysis_id'],'quantity':'0.1','idempotency_key':'paper-create-key'}
            assert (await c.post(path,json=body,headers={'Authorization':'Bearer '+read})).status_code==403
            drop[0]=True
            assert (await c.post(path,json=body)).status_code==504
            rows=(await c.get(path)).json()
            assert len(rows)==1 and rows[0]['status']=='pending'
            assert (await c.get('/api/v2/portfolios/AUTO/orders')).json()==[]
            wrong=await c.post('/api/v2/portfolios/AUTO/orders',json={**body,'idempotency_key':'wrong-account-key'})
            assert wrong.status_code==403
            assert (await c.get('/api/v2/portfolios/AUTO/orders',headers={'Authorization':'Bearer '+manual})).status_code==403
            # Reopen the exact DB/auth state, then explicitly replay original command.
        await app.state.backend_client.aclose()
        backend=backend_app(tmp_path/'paper.sqlite',mode='fixture',token=token,clock=lambda:now[0])
        app=gateway(True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net',headers=headers) as c:
            repeat=await c.post(path,json=body)
            assert repeat.status_code==200,repeat.text
            order=repeat.json();oid=order['order_id']
            assert order['status']=='pending' and len((await c.get(path)).json())==1
            assert (await c.post(path,json={**body,'quantity':'0.2'})).status_code==409
            cancel_path=path+'/'+oid+'/cancel'; cancel={'idempotency_key':'paper-cancel-key'}
            cancelled=await c.post(cancel_path,json=cancel)
            assert cancelled.status_code==200 and cancelled.json()['status']=='cancelled'
            assert (await c.post(cancel_path,json=cancel)).json()==cancelled.json()
            order=(await c.post(path,json={**body,'idempotency_key':'paper-create-second'})).json()
            oid=order['order_id']
            # Test/admin events are never mobile-accessible, even with all grants.
            assert (await c.post('/api/v2/paper/events',json={})).status_code==403
            assert (await c.post('/api/v2/paper/poll',json={})).status_code==403
            async def event(start):
                now[0]=start+60000
                bar={'symbol':'BTCUSDT','open_time_ms':start,'close_time_ms':now[0],'is_final':True,'open':'129.6','high':'130','low':'129.3','close':'129.8','volume':'100'}
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=backend),base_url='http://127.0.0.1:8002',headers={'Authorization':'Bearer '+token}) as admin:
                    r=await admin.post('/api/v2/paper/events',json=bar)
                    assert r.status_code==200,r.text
                    assert (await admin.post('/api/v2/paper/events',json=bar)).json()==r.json()
            await event(1792584000000)
            positions=(await c.get('/api/v2/portfolios/MANUAL/positions')).json()
            assert len(positions)==1 and positions[0]['quantity']=='0.10000000'
            close_path='/api/v2/portfolios/MANUAL/positions/'+oid+'/close'
            close={'quantity':'0.1','idempotency_key':'paper-close-key'}
            r=await c.post(close_path,json=close)
            assert r.status_code==200,r.text
            assert r.json()['status']=='pending'
            assert (await c.post(close_path,json=close)).json()==r.json()
            # Acknowledgement does NOT imply an executed exit.
            assert (await c.get('/api/v2/portfolios/MANUAL/positions')).json()[0]['status']=='open'
            pause=await c.post('/api/v2/portfolios/MANUAL/pause',json={'paused':True})
            assert pause.status_code==200 and pause.json()['paused'] is True
            await event(1792584060000)
            assert (await c.get('/api/v2/portfolios/MANUAL/positions')).json()==[]
            closed=(await c.get('/api/v2/portfolios/MANUAL/positions?open_only=false')).json()
            assert closed[0]['status']=='closed'
            assert len(closed[0]['pending_closes'])==1
            auto=(await c.get('/api/v2/portfolios')).json()[0]
            assert auto['portfolio_id']=='AUTO' and __import__('decimal').Decimal(auto['cash_quote'])==10000
            assert (await c.get('/api/v2/portfolios/AUTO/transactions')).json()==[]
            perf=(await c.get('/api/v2/performance')).json()['portfolios']
            assert perf[1]['closed_positions']==1 and perf[0]['closed_positions']==0
            assert len((await c.get('/api/v2/portfolios/MANUAL/transactions')).json())==2
        await app.state.backend_client.aclose()
        locked=gateway(False)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=locked),base_url='https://pc.example.ts.net',headers=headers) as c:
            assert (await c.post(path,json=body)).status_code==403
        await locked.state.backend_client.aclose()
    asyncio.run(scenario())
