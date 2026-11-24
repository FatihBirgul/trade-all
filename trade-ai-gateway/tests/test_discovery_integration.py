"""Actual Backend modules, explicit discovery grant, isolated SQLite only."""
import asyncio,os,sys,uuid
from pathlib import Path
import httpx,pytest
from trade_gateway.app import Settings,create_app
REF=os.environ.get('TRADE_AI_BACKEND_REFERENCE')
pytestmark=pytest.mark.skipif(not REF,reason='Pinned private Backend checkout required')
if REF:sys.path.insert(0,str(Path(REF)/'backend'))

def test_dual_scanner_scope_accounts_lost_ack_and_lifecycle_reads(tmp_path):
 from market_ai.v2.api import create_app as backend_app
 token='fixture-dual-scanner-integration-32'
 backend=backend_app(tmp_path/'backend.sqlite',mode='fixture',token=token,clock=lambda:1800000000000,domain_journal=True)
 gateway=create_app(Settings('https://pc.example.ts.net',token,tmp_path/'auth.sqlite',10,'fixture'),backend_transport=httpx.ASGITransport(app=backend))
 auth=gateway.state.auth
 def session(account,**scopes):return auth.exchange(auth.pairing(accounts=[account],**scopes),str(uuid.uuid4()),'Fixture')
 reader=session('MANUAL',scanner_write=True,profiles_write=True,paper_write=True)
 writer=session('MANUAL',discovery_write=True)
 other=session('AUTO',discovery_write=True)
 assert 'discovery:write' not in reader['scopes'] and 'paper:write' not in writer['scopes']
 assert 'dual-scanner-v1' in writer['capabilities']
 async def run():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway),base_url='https://pc.example.ts.net') as c:
   def h(s):return {'Authorization':'Bearer '+s['session']}
   base='/api/v2/portfolios/MANUAL/market-scanner';args={'idempotency_key':'dual-scanner-config','enabled':True,'favorites':['BTCUSDT'],'discovery':True}
   assert (await c.post(base,json=args,headers=h(reader))).status_code==403
   assert (await c.post(base,json=args,headers=h(other))).status_code==403
   r=await c.post(base,json=args,headers=h(writer));assert r.status_code==200,r.text
   assert (await c.post(base,json=args,headers=h(writer))).json()==r.json()
   r=await c.post(base+'/tick',headers=h(writer));assert r.status_code==200,r.text
   assert len(r.json()['jobs'])<=2
   r=await c.get('/api/v2/portfolios/MANUAL/opportunities',headers=h(reader));assert r.status_code==200,r.text
   opp=r.json()['items'][0];key=opp['opportunity_id'];assert opp['trade_permission'] is False
   detail=await c.get('/api/v2/portfolios/MANUAL/opportunities/'+key,headers=h(reader));assert detail.status_code==200,detail.text
   assert (await c.get('/api/v2/portfolios/AUTO/opportunities/'+key,headers=h(other))).status_code==404
   assert (await c.get('/api/v2/portfolios/MANUAL/opportunities/'+key,headers=h(other))).status_code==403
   assert (await c.post('/api/v2/portfolios/MANUAL/orders',json={},headers=h(writer))).status_code==403
  await gateway.state.backend_client.aclose()
 asyncio.run(run())
 with backend.state.v2.db.transaction() as c:assert c.execute('select count(*) from orders').fetchone()[0]==0
 assert backend.state.v2.discovery.verify_events('MANUAL')['status']=='PASS'
