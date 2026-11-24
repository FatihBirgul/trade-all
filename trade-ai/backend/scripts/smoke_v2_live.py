"""Explicit public spot read smoke, fresh temporary DB, AUTO placement disabled.

Separate from offline CI: python scripts/smoke_v2_live.py [--report path.json]
Exit 0 requires provider reachability and valid closed data; an outage exits 2.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from market_ai.v2.api import create_app


def smoke():
    token=secrets.token_urlsafe(32)
    with TemporaryDirectory(prefix="v2-public-spot-smoke-") as directory:
        app=create_app(Path(directory)/"live.sqlite",mode="live",token=token)
        with TestClient(app,headers={"Authorization":"Bearer "+token}) as client:
            r=client.post("/api/v2/analyze",json={"symbol":"BTCUSDT","timeframe":"1H","timeframes":["15m","4H"],
                "data_mode":"live","auto_paper":False,"idempotency_key":"public-spot-smoke-request"})
            r.raise_for_status()
            a=r.json()
            read=client.get("/api/v2/analyses/"+a["analysis_id"])
            read.raise_for_status()
            orders=client.get("/api/v2/portfolios/AUTO/orders")
            orders.raise_for_status()
            if read.json()!=a or orders.json(): raise RuntimeError("Smoke invariant failed")
            ready=app.state.v2.analysis.provider_status=="reachable" and a["quality"]["ok"]
            return {"observed_at_utc":datetime.now(timezone.utc).isoformat(),"data_mode":"live",
                "status":"verified" if ready else "unavailable_or_invalid","http_status":r.status_code,
                "network_scope":"public spot GET only","storage":"fresh temporary V2 database",
                "provider":a["provider"],"venue":a["venue"],"analysis_id":a["analysis_id"],
                "timeframes":a["timeframes"],"quality":a["quality"],"direction":a["direction"],
                "reason":a["reason"],"price_time_ms":a["price_time_ms"],"age_ms":a["age_ms"],
                "roundtrip_equal":True,"auto_paper":False,"auto_orders":0,"real_execution":False}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",type=Path)
    args=parser.parse_args()
    result=smoke()
    report=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.report: args.report.write_text(report,encoding="utf-8")
    print(report)
    raise SystemExit(0 if result["status"]=="verified" else 2)
