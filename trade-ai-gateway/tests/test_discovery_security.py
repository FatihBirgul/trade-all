"""Standalone Gateway tests; no private Backend required."""
import asyncio,uuid
import httpx
from trade_gateway.app import Settings,create_app

def test_discovery_scope_is_separate_from_all_existing_grants(tmp_path):
 app=create_app(Settings('https://pc.example.ts.net','fixture-private-backend-token-32',tmp_path/'auth.sqlite'))
 auth=app.state.auth
 normal=auth.exchange(auth.pairing(scanner_write=True,paper_write=True,profiles_write=True,notifications_write=True),str(uuid.uuid4()),'Fixture')
 discovery=auth.exchange(auth.pairing(accounts=['MANUAL'],discovery_write=True),str(uuid.uuid4()),'Fixture')
 assert 'discovery:write' not in normal['scopes']
 assert set(discovery['scopes'])=={'read','analyze','discovery:write'}
 asyncio.run(app.state.backend_client.aclose())

def test_old_backend_capability_absence_and_real_missing_record_are_distinct(tmp_path):
 response=[{'error':{'code':'NOT_FOUND'}}]
 upstream=httpx.MockTransport(lambda request:httpx.Response(404,json=response[0]))
 app=create_app(Settings('https://pc.example.ts.net','fixture-private-backend-token-32',tmp_path/'auth.sqlite'),backend_transport=upstream)
 auth=app.state.auth;session=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Fixture')
 async def run():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+session['session']}) as c:
   r=await c.get('/api/v2/portfolios/MANUAL/market-scanner');assert r.status_code==404 and r.json()['error']['code']=='BACKEND_UPDATE_REQUIRED'
   response[0]={'error':{'code':'OPPORTUNITY_NOT_FOUND'}}
   r=await c.get('/api/v2/portfolios/MANUAL/opportunities/'+'a'*64);assert r.status_code==404 and r.json()['error']['code']=='OPPORTUNITY_NOT_FOUND'
   assert (await c.post('/api/v2/portfolios/MANUAL/market-scanner',json={'idempotency_key':'no-scope-request'})).status_code==403
   assert (await c.get('/api/v2/portfolios/AUTO/market-scanner')).status_code==403
  await app.state.backend_client.aclose()
 asyncio.run(run())

def test_schema_valid_opportunity_for_other_account_is_rejected(tmp_path):
 opp={'opportunity_id':'a'*64,'portfolio_id':'AUTO','symbol':'BTCUSDT','provider':'fixture','source':'fixture','venue':'fixture','timeframe':'5m','profile_id':None,'initial_analysis_id':'b'*64,'last_analysis_id':'b'*64,'source_record_ids':{},'first_known_ms':1800000000000,'first_source_ms':1800000000000,'last_observed_ms':1800000000000,'last_source_ms':1800000000000,'expires_at_ms':1800003600000,'state':'CONFIRMED','last_valid_state':'CONFIRMED','setup_fingerprint':'c'*64,'modes':['favorites'],'reason':'controlled','evidence':{},'missing':[],'strategy_id':'trend_momentum_v2','direction':'bullish','stale':False,'trade_permission':False}
 payload={'portfolio_id':'MANUAL','data_mode':'live','items':[opp],'next_offset':None,'trade_permission':False}
 upstream=httpx.MockTransport(lambda request:httpx.Response(200,json=payload))
 app=create_app(Settings('https://pc.example.ts.net','fixture-private-backend-token-32',tmp_path/'auth.sqlite'),backend_transport=upstream)
 auth=app.state.auth;session=auth.exchange(auth.pairing(accounts=['MANUAL']),str(uuid.uuid4()),'Fixture')
 async def run():
  async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://pc.example.ts.net',headers={'Authorization':'Bearer '+session['session']}) as c:
   r=await c.get('/api/v2/portfolios/MANUAL/opportunities');assert r.status_code==502 and r.json()['error']['code']=='INVALID_RESPONSE'
  await app.state.backend_client.aclose()
 asyncio.run(run())
