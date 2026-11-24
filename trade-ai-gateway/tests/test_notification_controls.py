"""New grants are opt-in; headers/device identifiers cannot select another owner."""
import uuid
from pathlib import Path
import asyncio,os,sys
import httpx,pytest
from trade_gateway.store import AuthStore
from trade_gateway.app import Settings,create_app
REFERENCE=os.environ.get('TRADE_AI_BACKEND_REFERENCE')
def test_notification_grant_is_never_inferred_from_existing_writes(tmp_path):
    auth=AuthStore(tmp_path/'auth.sqlite')
    normal=auth.exchange(auth.pairing(scanner_write=True,profiles_write=True,paper_write=True),str(uuid.uuid4()),'Fixture')
    assert 'notifications:write' not in normal['scopes']
    explicit=auth.exchange(auth.pairing(notifications_write=True),str(uuid.uuid4()),'Fixture')
    assert set(explicit['scopes'])=={'read','analyze','notifications:write'}
@pytest.mark.skipif(not REFERENCE,reason='Pinned private Backend checkout required')
def test_actual_account_owner_refresh_revoke_and_header_spoof_isolation(tmp_path):
    sys.path.insert(0,str(Path(REFERENCE)/'backend'))
    from market_ai.v2.api import create_app as backend_app
    now=1800000000000;token='fixture-notification-integration-32'
    backend=backend_app(tmp_path/'fixture.sqlite',mode='fixture',token=token,clock=lambda:now,domain_journal=True)
    gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend),clock=lambda:now/1000)
    auth=gateway.state.auth
    writer=auth.exchange(auth.pairing(accounts=['MANUAL'],notifications_write=True),str(uuid.uuid4()),'Fixture writer')
    readonly=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Fixture reader')
    refresh=auth.grant_renewal(writer['session'])
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net') as c:
            url='/api/v2/portfolios/MANUAL/notification-preferences';body={'idempotency_key':'mobile-prefs-fixture','expected_revision':0,'enabled':True,'categories':{'analysis':True}}
            read={'Authorization':'Bearer '+readonly['session']};write={'Authorization':'Bearer '+writer['session']}
            initial=await c.get(url,headers=read);assert initial.status_code==200,initial.text
            assert initial.json()['revision']==0
            assert (await c.post(url,json=body,headers=read)).status_code==403
            r=await c.post(url,json=body,headers=write);assert r.status_code==200,r.text
            assert r.json()['revision']==1 and r.json()['push_status']=='NOT_CONFIGURED'
            assert (await c.post(url,json=body,headers=write)).json()==r.json()
            spoof={**read,'X-V2-Notification-Owner':'a'*64,'X-V2-Recipient-Expires':str(now+86400000)}
            assert (await c.get(url,headers=spoof)).json()['revision']==0
            assert (await c.get(url.replace('MANUAL','AUTO'),headers=write)).status_code==403
            assert (await c.post(url,json={**body,'owner_ref':'a'*64},headers=write)).status_code==422
            import secrets
            next_token='tg_'+secrets.token_urlsafe(32)
            rotated=auth.rotate({'refresh_token':refresh,'next_refresh_token':'tr_'+secrets.token_urlsafe(32),'next_session':next_token,'device_id':writer['device_id'],'request_id':'rq_'+secrets.token_urlsafe(32)})
            # Renewal preserves server-owned family identity, not a client device UUID.
            assert rotated is not None
            assert (await c.get(url,headers=write)).status_code==401
            assert (await c.get(url,headers={'Authorization':'Bearer '+next_token})).json()['revision']==1
            auth.revoke(rotated['session_id'])
            assert (await c.get(url,headers={'Authorization':'Bearer '+next_token})).status_code==401
        await gateway.state.backend_client.aclose()
    asyncio.run(scenario())
