"""Named scanner config/explicit activation through real Backend and Gateway."""
import asyncio,os,sys,uuid
from pathlib import Path
import httpx,pytest
from trade_gateway.app import Settings,create_app
REF=os.environ.get('TRADE_AI_BACKEND_REFERENCE')
pytestmark=pytest.mark.skipif(not REF,reason='Pinned private Backend checkout required')
if REF:sys.path.insert(0,str(Path(REF)/'backend'))
def test_named_modes_activation_and_scopes_never_start_host_runtime(tmp_path):
 from market_ai.v2.api import create_app as backend_app
 token='fixture-activation-integration-not-secret'
 backend=backend_app(tmp_path/'backend.sqlite',mode='fixture',token=token,clock=lambda:1800000000000,domain_journal=True)
 gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
 auth=gateway.state.auth
 def session(account,**kw):return auth.exchange(auth.pairing(accounts=[account],**kw),str(uuid.uuid4()),'Fixture')
 writer=session('MANUAL',discovery_write=True);reader=session('MANUAL');other=session('AUTO',discovery_write=True)
 assert 'scanner-activation-v1' in writer['capabilities']
 async def run():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net') as c:
   def h(s):return {'Authorization':'Bearer '+s['session']}
   path='/api/v2/portfolios/MANUAL/market-scanner'
   body={'idempotency_key':'named-scan-config','name':'Akşam kontrolü','runtime_mode':'supported_markets','discovery':True,'timeframe':'15m','favorites':['BTCUSDT']}
   assert (await c.post(path,json=body,headers=h(reader))).status_code==403
   assert (await c.post(path,json=body,headers=h(other))).status_code==403
   r=await c.post(path,json=body,headers=h(writer));assert r.status_code==200,r.text
   assert not r.json()['config']['enabled'] and backend.state.v2.discovery.worker is None
   active={**body,'idempotency_key':'account-activation','expected_revision':1,'enabled':True}
   r=await c.post(path,json=active,headers=h(writer));assert r.status_code==409 and r.json()['error']['code']=='DISCOVERY_ACTIVATION_BLOCKED',r.text
   assert (await c.get(path,headers=h(reader))).json()['config']['revision']==1
   backend.state.v2.discovery.start()
   try:
    r=await c.post(path,json=active,headers=h(writer));assert r.status_code==200,r.text
    assert (await c.post(path,json=active,headers=h(writer))).json()==r.json()
    assert (await c.get(path,headers=h(reader))).json()['runtime']['activation']['state']=='active'
    pause={**body,'idempotency_key':'account-pause','expected_revision':2,'enabled':False}
    r=await c.post(path,json=pause,headers=h(writer));assert r.status_code==200,r.text
   finally:backend.state.v2.discovery.stop()
   assert not (await c.get(path,headers=h(reader))).json()['runtime']['worker_active']
   assert (await c.post('/api/v2/portfolios/MANUAL/orders',json={},headers=h(writer))).status_code==403
  await gateway.state.backend_client.aclose()
 asyncio.run(run())
 with backend.state.v2.db.transaction() as c:assert c.execute('SELECT count(*) FROM orders').fetchone()[0]==0
