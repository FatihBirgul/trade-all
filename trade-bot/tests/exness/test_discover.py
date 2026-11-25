import json
from pathlib import Path

import httpx

from tests.exness.test_client import KEY, settings
from tradebot import discover
from tradebot.exness.client import ExnessClient

FIXTURES = Path(__file__).parent / "fixtures"
NOW = 1_800_000_000


def load(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def responder(requests):
    def handle(request):
        requests.append(request)
        path = request.url.path
        if path.endswith("/account"):
            return httpx.Response(200, json=load("account"))
        if path.endswith("/limits"):
            return httpx.Response(200, json=load("limits"))
        if path.endswith("/snapshot"):
            return httpx.Response(200, json=load("snapshot"))
        if path.endswith("/instruments"):
            return httpx.Response(200, json={"instruments": ["EURUSDc", "XAUUSD", "BTCUSD", "AAPL", "BROKEN"]})
        if "/instruments/" in path:
            name = path.split("/")[-2]
            if name == "BROKEN":
                return httpx.Response(404, json={"code": 4000, "error_message": "MARKET_INSTRUMENT_NOT_FOUND"})
            fixture = {"EURUSDc": "instrument_cent_eurusd", "XAUUSD": "instrument_xauusd",
                       "BTCUSD": "instrument_btcusd", "AAPL": "instrument_stock"}[name]
            return httpx.Response(200, json=load(fixture))
        if path.endswith("/candles"):
            return httpx.Response(200, json=load("candles_bid"))
        if path.endswith("/deals"):
            return httpx.Response(200, json=load("deals"))
        return httpx.Response(404, json={"code": 3000, "error_message": "REQUEST_INVALID"})
    return handle


async def fake_ws(client, path, subscriptions, seconds):
    return [{"path": path, "subscriptions": subscriptions}, load("tick")]


async def test_discover_only_reads_and_writes_no_secrets(tmp_path):
    requests = []
    config = settings()
    client = ExnessClient(config, transport=httpx.MockTransport(responder(requests)))
    folder = await discover.run(config, tmp_path, client=client, seconds=0.01, ws_listen=fake_ws, now=NOW)

    assert {r.method for r in requests} == {"GET"}
    summary = json.loads((folder / "summary.json").read_text())
    assert summary["instrument_count"] == 5
    assert summary["kinds"] == {"forex": 1, "metal": 1, "crypto": 1, "other": 1}
    assert summary["universe"] == ["EURUSDc", "XAUUSD", "BTCUSD"]
    assert summary["samples"] == ["EURUSDc", "XAUUSD", "BTCUSD"]
    assert "conditions/BROKEN" in summary["errors"]
    assert summary["account"]["currency"] == "USC"
    for name in ("account", "limits", "snapshot", "instruments", "deals", "ws_ticks", "ws_events",
                 "conditions/XAUUSD", "candles/EURUSDc_M15", "candles/BTCUSD_H4"):
        assert (folder / f"{name}.json").exists(), name

    archive = discover.make_zip(folder)
    assert archive.exists()
    blob = "".join(p.read_text() for p in folder.rglob("*.json"))
    assert KEY[:16] not in blob and "exnsk-test" not in blob and "EXN-SIGN" not in blob


async def test_discover_records_failure_instead_of_raising(tmp_path):
    def down(request):
        return httpx.Response(401, json={"code": 1001, "error_message": "AUTH_INVALID_SIGNATURE"})
    config = settings()
    client = ExnessClient(config, transport=httpx.MockTransport(down))
    folder = await discover.run(config, tmp_path, client=client, seconds=0.01, ws_listen=fake_ws, now=NOW)
    summary = json.loads((folder / "summary.json").read_text())
    assert "AUTH_INVALID_SIGNATURE" in summary["errors"]["account"]
