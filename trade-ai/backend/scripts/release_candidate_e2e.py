"""Real Android TypeScript client -> verified HTTPS loopback Gateway -> Backend ASGI.

Explicit sibling checkouts, temporary DBs/CA only. No public bind, TLS bypass,
production provider, push sender or automated paper orders. The live wire format
is deliberately exercised with a named controlled fixture provider; these prices
are test inputs, NEVER live-market evidence or APK demo data.
"""
import argparse,asyncio,hashlib,json,secrets,socket,subprocess,sys,threading,time
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
from contextlib import closing
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def command(args,**kw):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=kw.pop('timeout',60),**kw)
    if p.returncode:raise RuntimeError('Build/tool command failed: '+p.stdout.decode(errors='replace')[-1200:])
    return p.stdout

def source(path):
    return {'sha':command(['git','-C',str(path),'rev-parse','HEAD']).decode().strip(),
            'dirty':bool(command(['git','-C',str(path),'status','--porcelain']))}

def run(android,gateway):
    sys.path.insert(0,str(gateway))
    import httpx,uvicorn
    from fastapi.responses import JSONResponse
    from market_ai.v2.api import create_app as backend_app
    from market_ai.v2.spot_provider import FixtureSpotProvider,ProviderUnavailable
    from market_ai.v2.paper_audit import audit_database
    from trade_gateway.app import create_app as gateway_app,Settings
    roots={'backend':Path(__file__).resolve().parents[2],'android':android,'gateway':gateway}
    identities={k:source(p) for k,p in roots.items()}
    contracts=[p.read_bytes() for p in (roots['backend']/'docs/V2_OPENAPI.json',android/'docs/backend/V2_OPENAPI.json',gateway/'trade_gateway/openapi.json')]
    assert len({hashlib.sha256(b).hexdigest() for b in contracts})==1,'Contract mismatch'
    class ControlledProvider(FixtureSpotProvider):
        name=source_name='RC_CONTROLLED_FIXTURE';mode='live';outage=False
        def candles(self,*args):
            if self.outage:raise ProviderUnavailable('rc_controlled_outage')
            return super().candles(*args)
    with TemporaryDirectory(prefix='trade-ai-rc-e2e-') as temporary:
        root=Path(temporary);initial_clock=int(time.time()*1000)//60000*60000;now=[initial_clock];provider=ControlledProvider()
        backend_token=secrets.token_urlsafe(32);db=root/'backend.sqlite';authdb=root/'gateway.sqlite'
        state={'backend_down':False,'malformed':False,'slow':False,'privileged_requests':0,'seeded_orders':0,'legacy_research':False};audit_results=[]
        backend=[backend_app(db,mode='live',token=backend_token,provider=provider,clock=lambda:now[0],domain_journal=True)]
        class BackendTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self,request):
                assert request.headers['authorization']=='Bearer '+backend_token,'Backend bearer isolation'
                state['privileged_requests']+=1
                if state['legacy_research'] and request.url.path.endswith('/research'):return httpx.Response(404,json={'error':{'code':'NOT_FOUND','message':'Controlled older Backend route absent'}})
                if state['backend_down']:raise httpx.ConnectError('Controlled missing Backend')
                return await httpx.ASGITransport(app=backend[0]).handle_async_request(request)
        def new_gateway():return gateway_app(Settings('https://rc.example.test',backend_token,authdb,expected_mode='live'),backend_transport=BackendTransport())
        active=[new_gateway()];loop=[None]
        class Switch:
            async def __call__(self,scope,receive,send):
                loop[0]=asyncio.get_running_loop()
                if scope['path']=='/api/v2/health' and (state['malformed'] or state['slow']):
                    messages=[]
                    async def capture(m):messages.append(m)
                    await active[0](scope,receive,capture) # Actual auth/boundary first.
                    if state['slow']:
                        state['slow']=False;await asyncio.sleep(20)
                    if state['malformed']:
                        state['malformed']=False
                        await JSONResponse({'invalid_controlled_response':True})(scope,receive,send);return
                    for m in messages:await send(m)
                else:await active[0](scope,receive,send)
        command(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-keyout',str(root/'key.pem'),'-out',str(root/'cert.pem'),'-subj','/CN=rc.example.test','-addext','subjectAltName=DNS:rc.example.test'])
        # Bind once to eliminate free-port races; never wildcard or public.
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(Switch(),host='127.0.0.1',port=port,ssl_keyfile=str(root/'key.pem'),ssl_certfile=str(root/'cert.pem'),lifespan='off',access_log=False,log_level='critical',timeout_graceful_shutdown=2))
        thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True);thread.start()
        deadline=time.monotonic()+10
        while not server.started:
            if time.monotonic()>deadline:raise RuntimeError('Loopback startup failed')
            time.sleep(.02)
        child=None;timer=None
        try:
            compiled=root/'compiled'
            command(['node',str(android/'node_modules/typescript/bin/tsc'),'--ignoreConfig','--rootDir',str(android),'--outDir',str(compiled),'--module','commonjs','--target','ES2022','--moduleResolution','node','--resolveJsonModule','--esModuleInterop','--skipLibCheck','--ignoreDeprecations','6.0',str(android/'src/api/client.ts'),str(android/'src/api/gateway.ts'),str(android/'src/api/renewal.ts')],cwd=android)
            writer=active[0].state.auth.pairing(accounts=['AUTO','MANUAL'],profiles_write=True,scanner_write=True,discovery_write=True)
            reader=active[0].state.auth.pairing(accounts=['MANUAL'])
            initial={'port':port,'ca':str(root/'cert.pem'),'writer_code':writer,'reader_code':reader,'now':now[0]}
            child=subprocess.Popen(['node',str(android/'scripts/release-candidate-client.cjs'),str(compiled)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            timer=threading.Timer(100,child.kill);timer.start()
            def respond(obj):child.stdin.write(json.dumps(obj)+'\n');child.stdin.flush()
            respond(initial);result=None
            for line in child.stdout:
                m=json.loads(line)
                if 'control' not in m:result=m;continue
                name=m['control'];reply={'ok':True}
                if name in ('outage','recover'):
                    provider.outage=name=='outage';now[0]+=60000
                    backend[0].state.tracking.tick() # Explicit fixture step, no worker thread.
                elif name=='discovery_worker':
                    discovery=backend[0].state.v2.discovery
                    started=time.monotonic();discovery.start()
                    try:
                        deadline=time.monotonic()+8
                        while time.monotonic()<deadline:
                            view=discovery.view('MANUAL')
                            if view['runtime']['last_success_ms'] and not view['runtime']['lease_until_ms']:break
                            time.sleep(.02)
                        else:raise RuntimeError('Fixture worker did not complete bounded cycle')
                        reply['worker_seen_active']=view['runtime']['worker_active']
                        reply['cycle_seconds']=round(time.monotonic()-started,4)
                    finally:discovery.stop()
                elif name=='activation_runtime_start':
                    backend[0].state.v2.discovery.start() # Explicit fixture operator, not a mobile endpoint.
                elif name=='activation_runtime_stop':
                    backend[0].state.v2.discovery.stop()
                elif name in ('discovery_outage','discovery_recover'):
                    provider.outage=name=='discovery_outage';now[0]+=300000
                    reply['tick']=backend[0].state.v2.discovery.tick('MANUAL')
                    reply['chain']=backend[0].state.v2.discovery.verify_events('MANUAL')
                elif name=='seed_observations':
                    runtime=backend[0].state.v2
                    from market_ai.v2.api_models import AnalyzeRequest
                    # Explicit fixture administrator seeds two orders; Android
                    # receives NO paper grant and automatic analysis stays off.
                    for account in ('AUTO','MANUAL'):
                        a=runtime.analysis.analyze(AnalyzeRequest(data_mode='live',timeframe='1H',risk_portfolio=account,auto_paper=False,idempotency_key='rc-fixture-seed-analysis-'+account))
                        assert a.auto_order_id is None
                        with runtime.db.transaction() as c:runtime.ledger.place(c,account,a,'rc-fixture-seed-'+account,'1',now[0])
                        state['seeded_orders']+=1
                    for _ in range(201):
                        start=now[0];now[0]+=60000
                        event={'symbol':'BTCUSDT','open_time_ms':start,'close_time_ms':now[0],'open':'129.9','high':'130.2','low':'129.5','close':'130','volume':'10000','is_final':True}
                        with runtime.db.transaction() as c:runtime.ledger.event(c,event,now[0])
                elif name=='audit':
                    audit=audit_database(db,require_domain=True)
                    assert audit['status']=='PASS',audit['checks'];reply['status']=audit['status']
                    audit_results.append({'status':audit['status'],'checks':audit['checks']})
                    with backend[0].state.v2.db.transaction() as c:
                        assert c.execute('SELECT COUNT(*) FROM orders').fetchone()[0]==state['seeded_orders']==2
                elif name=='restart':
                    asyncio.run_coroutine_threadsafe(active[0].state.backend_client.aclose(),loop[0]).result(5)
                    backend[0]=backend_app(db,mode='live',token=backend_token,provider=provider,clock=lambda:now[0],domain_journal=True);active[0]=new_gateway()
                elif name=='revoke':
                    for saved in active[0].state.auth.sessions():
                        if saved['name']=='RC disposable client':active[0].state.auth.revoke(saved['id'])
                elif name=='legacy_research':state['legacy_research']=True
                elif name=='modern_research':state['legacy_research']=False
                elif name=='malformed':state['malformed']=True
                elif name=='backend_down':state['backend_down']=True
                elif name=='backend_up':state['backend_down']=False
                elif name=='slow':state['slow']=True
                elif name=='gateway_down':
                    server.should_exit=True;thread.join(5)
                else:raise RuntimeError('Unknown fixture control')
                respond(reply)
            child.wait(timeout=10);timer.cancel()
            if child.returncode or not result or result.get('failure'):raise RuntimeError('Android real-client scenario failed: '+json.dumps(result))
            result.update(source_heads=identities,contract_sha256=hashlib.sha256(contracts[0]).hexdigest(),tls_verified=True,fixture_clock_ms=initial_clock,audit_checkpoints=audit_results,public_listener=False,backend_admin_bearer_on_android=False,privileged_backend_requests=state['privileged_requests'],automatic_orders=0,fixture_administrator_seeded_orders=state['seeded_orders'],release_gate='PASS' if all(not s['dirty'] for s in identities.values()) else 'PARTIAL_DIRTY_INPUTS',physical_device='UNVERIFIED',market_validation='INSUFFICIENT_EVIDENCE')
            return result
        finally:
            backend[0].state.v2.discovery.stop()
            if timer is not None:timer.cancel()
            if child is not None:
                if child.poll() is None:
                    child.terminate()
                    try:child.wait(timeout=5)
                    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)
                for stream in (child.stdin,child.stdout,child.stderr):stream.close()
            server.should_exit=True;thread.join(5)
            if loop[0] and loop[0].is_running():asyncio.run_coroutine_threadsafe(active[0].state.backend_client.aclose(),loop[0]).result(5)
            else:asyncio.run(active[0].state.backend_client.aclose())
            sock.close()

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--android',type=Path,required=True);p.add_argument('--gateway',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args(argv)
    result=run(a.android.resolve(strict=True),a.gateway.resolve(strict=True));a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({'scenarios':len(result['results']),'status':result['release_gate'],'source_heads':result['source_heads']}));return 0 if result['release_gate']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
