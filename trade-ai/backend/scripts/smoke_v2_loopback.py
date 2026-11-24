"""Explicit real-HTTP fixture acceptance, only 127.0.0.1 and temporary SQLite.

Not collected by offline CI (which forbids TCP). No public provider is used.
Run from backend: python scripts/smoke_v2_loopback.py [--report path.json]
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time

import httpx
import uvicorn

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from market_ai.v2.api import create_app


TOKEN="fixture-loopback-token-not-a-secret-32"


@contextmanager
def serve(app):
    sock=socket.socket()
    sock.bind(("127.0.0.1",0))
    server=uvicorn.Server(uvicorn.Config(app,access_log=False,log_level="warning",lifespan="off"))
    worker=Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True)
    worker.start()
    try:
        deadline=time.monotonic()+5
        while not server.started:
            if not worker.is_alive() or time.monotonic()>deadline:
                raise RuntimeError("Local smoke server failed to start")
            time.sleep(.01)
        with httpx.Client(base_url=f"http://127.0.0.1:{sock.getsockname()[1]}/api/v2/",
                          headers={"Authorization":"Bearer "+TOKEN},timeout=10,trust_env=False) as client:
            yield client
    finally:
        server.should_exit=True
        worker.join(5)
        sock.close()
        if worker.is_alive(): raise RuntimeError("Local smoke server failed to stop")


def smoke():
    now=[1792584000000]
    with TemporaryDirectory(prefix="v2-loopback-acceptance-") as directory:
        path=Path(directory)/"fixture.sqlite"
        def app(): return create_app(path,mode="fixture",token=TOKEN,clock=lambda:now[0])
        with serve(app()) as client:
            def get(route):
                r=client.get(route);r.raise_for_status();return r.json()
            def post(route,body):
                r=client.post(route,json=body);r.raise_for_status();return r.json()
            assert get("health")["real_execution"] is False
            a=post("analyze",{"data_mode":"fixture","timeframe":"1H","timeframes":["15m","4H"],
                              "idempotency_key":"loopback-analysis-request"})
            assert a["quality"]["ok"] and a["direction"]=="bullish"
            assert get("analyses/"+a["analysis_id"])==a
            chart=get("analyses/"+a["analysis_id"]+"/candles?limit=3")
            assert Decimal(chart["candles"][-1]["close"])==Decimal(a["price"])
            assert chart["candles"][-1]["close_time_ms"]==a["price_time_ms"]
            order_request={"analysis_id":a["analysis_id"],"quantity":"1","idempotency_key":"loopback-manual-order"}
            order=post("portfolios/MANUAL/orders",order_request)
            def event(**overrides):
                bar={"symbol":"BTCUSDT","open_time_ms":now[0],"close_time_ms":now[0]+60000,
                     "open":"129.9","high":"130.2","low":"129.5","close":"130","volume":"10000"}
                bar.update(overrides);now[0]+=60000
                first=post("paper/events",bar)
                assert post("paper/events",bar)==first
            event()
            positions=get("portfolios/MANUAL/positions")
            assert len(positions)==1 and Decimal(positions[0]["quantity"])==1
            assert post("portfolios/MANUAL/orders",order_request)==order
            post("portfolios/MANUAL/positions/"+order["order_id"]+"/close",
                 {"quantity":"1","idempotency_key":"loopback-manual-close"})
            event(open="130.5",high="130.8",low="130.2",close="130.6")
            assert get("portfolios/MANUAL/positions")==[]
            account=get("portfolios/MANUAL")
            assert Decimal(account["cash_quote"])==Decimal("10000")+Decimal(account["realized_pnl_quote"])
            assert get("portfolios/AUTO")["cash_quote"]=="10000"
            post("watchlist",{"symbol":"BTCUSDT","timeframe":"1H","auto_paper":False})
            post("scanner/pause",{"paused":False})
            assert len(post("scanner/tick",{})["jobs"])==1
            assert post("scanner/tick",{})["jobs"]==[]
            assert all(n["delivery_status"]=="pending" for n in get("notifications"))
            post("scanner/pause",{"paused":True})
            performance=get("performance")
        with serve(app()) as client:
            r=client.get("portfolios/MANUAL");r.raise_for_status()
            assert r.json()==account
            r=client.get("analyses/"+a["analysis_id"]);r.raise_for_status()
            assert r.json()==a
            r=client.get("performance");r.raise_for_status()
            assert r.json()==performance
        return {"observed_at_utc":datetime.now(timezone.utc).isoformat(),"data_mode":"fixture",
            "bind":"127.0.0.1","public_bind":False,"real_execution":False,"server_stopped":True,
            "analysis_readback":True,"paper_fill_close_reconciliation":True,"idempotency":True,
            "chart_snapshot_readback":True,
            "separate_auto_manual":True,"scanner_closed_bar_dedup":True,"notifications_pending":True,
            "http_server_restart_persistence":True,"temporary_database_only":True,
            "v1_mongo_imported":any(m.startswith(("motor","pymongo")) for m in sys.modules),
            "ai_provider_imported":any(m.startswith(("openai","emergentintegrations")) for m in sys.modules)}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    report=json.dumps(smoke(),indent=2,sort_keys=True)+"\n"
    if args.report: args.report.write_text(report,encoding="utf-8")
    print(report)
