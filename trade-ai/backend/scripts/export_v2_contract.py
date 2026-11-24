"""Generate frontend artifacts from the actual app and explicit fixture data."""
from pathlib import Path
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
import json
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app
from market_ai.v2.spot_provider import ProviderUnavailable, FixtureSpotProvider
from scripts.v2_scenario_fixtures import fixture


TOKEN = "fixture-export-token-not-a-secret-32"


def export(destination):
    destination = Path(destination)
    examples = destination/"v2_examples"
    examples.mkdir(parents=True, exist_ok=True)
    now = [int(datetime(2026, 10, 21, 12, tzinfo=timezone.utc).timestamp()*1000)]
    def save(name, value):
        (examples/(name+".json")).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n", encoding="utf-8")
    with TemporaryDirectory(prefix="v2-contract-export-") as directory:
        app = create_app(Path(directory)/"fixture.sqlite", mode="fixture", token=TOKEN, clock=lambda: now[0])
        (destination/"V2_OPENAPI.json").write_text(json.dumps(app.openapi(), indent=2, sort_keys=True)+"\n", encoding="utf-8")
        with TestClient(app, headers={"Authorization": "Bearer "+TOKEN}) as client:
            def get(path):
                r=client.get("/api/v2/"+path); r.raise_for_status(); return r.json()
            def post(path, body):
                r=client.post("/api/v2/"+path,json=body); r.raise_for_status(); return r.json()
            request = {"symbol":"BTCUSDT", "timeframe":"1H", "timeframes":["15m","4H"],
                       "data_mode":"fixture", "risk_portfolio":"AUTO", "idempotency_key":"example-analysis-request"}
            save("analyze_request",request)
            a=post("analyze",request); save("analysis",a)
            save("candles",get("analyses/"+a["analysis_id"]+"/candles?timeframe=1H&limit=3"))
            save("health",get("health")); save("markets",get("markets"))
            save("wait",post("analyze",{**request,"fixture_case":"range","idempotency_key":"example-wait-request"}))
            order_request={"analysis_id":a["analysis_id"],"quantity":"1","idempotency_key":"example-manual-order"}
            save("order_request",order_request)
            o=post("portfolios/MANUAL/orders",order_request); save("order",o)
            post("portfolios/AUTO/orders",{**order_request,"idempotency_key":"example-auto-order"})
            event={"symbol":"BTCUSDT","open_time_ms":now[0],"close_time_ms":now[0]+60000,
                   "open":"129.9","high":"130.2","low":"129.5","close":"130","volume":"10000"}
            now[0]+=60000; save("event",post("paper/events",event))
            save("positions",get("portfolios/MANUAL/positions"))
            close_request={"quantity":"1","idempotency_key":"example-close-request"}
            save("close_request",close_request)
            save("close_pending",post("portfolios/MANUAL/positions/"+o["order_id"]+"/close",close_request))
            event.update(open_time_ms=now[0],close_time_ms=now[0]+60000,open="130.5",low="130.2",high="130.8",close="130.6")
            now[0]+=60000; post("paper/events",event)
            save("portfolios",get("portfolios")); save("transactions",get("portfolios/MANUAL/transactions"))
            save("performance",get("performance"))
            watch_request={"symbol":"BTCUSDT","timeframe":"1H","enabled":True,"auto_paper":False}
            save("watch_request",watch_request)
            post("watchlist",watch_request)
            save("watchlist",get("watchlist"))
            post("scanner/pause",{"paused":False})
            save("scanner_tick",post("scanner/tick",{}))
            save("scanner",get("scanner"))
            save("scanner_jobs",get("scanner/jobs"))
            save("notifications",get("notifications"))
    # Test-only confirmed scenarios. Public fixture_case=range intentionally
    # remains a WAIT example; these providers are never selected at runtime.
    for kind in ("range", "breakout", "sweep"):
        class ScenarioProvider(FixtureSpotProvider):
            def candles(self,symbol,timeframe,as_of_ms):
                return fixture(kind,timeframe,as_of_ms,symbol)
        with TemporaryDirectory(prefix="v2-contract-scenario-") as directory:
            app=create_app(Path(directory)/"scenario.sqlite",mode="fixture",token=TOKEN,
                           provider=ScenarioProvider(),clock=lambda:now[0])
            with TestClient(app,headers={"Authorization":"Bearer "+TOKEN}) as client:
                r=client.post("/api/v2/analyze",json={"data_mode":"fixture","idempotency_key":"example-confirmed-"+kind})
                r.raise_for_status(); save(kind+"_setup",r.json())
    class Down:
        name,venue,mode="binance_public_spot","binance","live"
        def rules(self,symbol): raise ProviderUnavailable("explicit outage test double")
    with TemporaryDirectory(prefix="v2-contract-outage-") as directory:
        app=create_app(Path(directory)/"outage.sqlite",mode="live",token=TOKEN,provider=Down(),clock=lambda:now[0])
        with TestClient(app,headers={"Authorization":"Bearer "+TOKEN}) as client:
            r=client.post("/api/v2/analyze",json={"idempotency_key":"unavailable-example-request"})
            r.raise_for_status(); save("provider_unavailable",r.json())


if __name__ == "__main__":
    export(BACKEND.parent/"docs")
