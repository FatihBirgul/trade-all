"""Local TLS integration only. Starts only isolated, temporary test services."""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import uvicorn
import httpx


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--backend',type=Path,required=True)
    p.add_argument('--android',type=Path,required=True)
    p.add_argument('--controlled',action='store_true',help='Synthetic test input through real V2 engine; NEVER a live market test')
    args=p.parse_args()
    sys.path.insert(0,str(args.backend/'backend'))
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from market_ai.v2.api import create_app as backend_app
    from market_ai.v2.spot_provider import ProviderUnavailable
    from trade_gateway.app import create_app,Settings
    class Offline:
        mode='live';name='controlled_offline';venue='controlled_test';source_name='controlled_offline'
        def rules(self,*args):raise ProviderUnavailable('controlled_offline')
        def candles(self,*args):raise ProviderUnavailable('controlled_offline')
    from market_ai.v2.spot_provider import FixtureSpotProvider
    class Controlled(FixtureSpotProvider):
        # Test-only adapter: explicit synthetic source, never in gateway runtime.
        mode='live'; name='controlled_test_input'; source_name='controlled_test_input'; venue='controlled_test'
    with tempfile.TemporaryDirectory(prefix='trade-gateway-test-') as temp:
        root=Path(temp)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'test.key'),'-out',str(root/'test.pem'),'-days','1','-subj','/CN=pc.example.ts.net','-addext','subjectAltName=DNS:pc.example.ts.net'],check=True,capture_output=True)
        token=secrets.token_urlsafe(32)
        backend=backend_app(root/'backend.sqlite',mode='live',token=token,provider=Controlled() if args.controlled else Offline())
        if args.controlled and hasattr(backend.state,'quotes'):
            def quote_source(request):
                now=int(time.time()*1000)
                if request.url.path.endswith('24hr'):
                    return httpx.Response(200,json=[dict(symbol=s,lastPrice='123.45',priceChangePercent='-1.25',closeTime=now) for s in ['BTCUSDT','ETHUSDT','SOLUSDT']])
                end=now//3600000*3600000
                return httpx.Response(200,json=[[end-(24-i)*3600000,'120','130','110','123.45','10',end-(23-i)*3600000-1,'1',1,'1','1','0'] for i in range(24)])
            backend.state.quotes.transport=httpx.MockTransport(quote_source)
        gateway=create_app(Settings('https://pc.example.ts.net',token,root/'auth.sqlite',paper_writes_enabled=args.controlled))
        servers=[];threads=[]
        try:
            for app,port,tls in [(backend,8002,False),(gateway,8787,True)]:
                config=uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,proxy_headers=False,log_level='critical',**({'ssl_certfile':str(root/'test.pem'),'ssl_keyfile':str(root/'test.key')} if tls else {}))
                server=uvicorn.Server(config);thread=threading.Thread(target=server.run,daemon=True)
                servers.append(server);threads.append(thread);thread.start()
                deadline=time.monotonic()+10
                while not server.started:
                    if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Isolated test listener could not start')
                    time.sleep(.02)
            out=root/'android-client'
            subprocess.run(['node','scripts/build-api-test-client.cjs',str(out)],cwd=args.android,check=True)
            data={'origin':'https://pc.example.ts.net','offOrigin':'https://pc.example.ts.net:8788','ca':str(root/'test.pem'),'client':str(out),'follow':args.controlled and hasattr(backend.state,'tracking'),'quotes':args.controlled and hasattr(backend.state,'quotes'),'controlled':args.controlled,'code':gateway.state.auth.pairing(scanner_write=args.controlled,paper_write=args.controlled),'deviceId':str(uuid.uuid4())}
            subprocess.run(['node','scripts/gateway-https-integration.cjs'],cwd=args.android,input=json.dumps(data),text=True,check=True,timeout=60)
        finally:
            for server in servers:server.should_exit=True
            for thread in threads:thread.join(timeout=5)
if __name__=='__main__':main()
