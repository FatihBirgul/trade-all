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


def candle_failures(requests, failures, status=401, body=None):
    """Ilk `failures` mum istegini reddeder; digerleri normal yanit verir."""
    normal = responder(requests)
    seen = {"candles": 0}
    body = body or {"code": 1000, "error_message": "AUTH_INVALID_API_KEY"}

    def handle(request):
        if request.url.path.endswith("/candles"):
            seen["candles"] += 1
            if seen["candles"] <= failures:
                requests.append(request)
                return httpx.Response(status, json=body)
        return normal(request)
    return handle


async def run_with(tmp_path, handler):
    config = settings()
    client = ExnessClient(config, transport=httpx.MockTransport(handler))
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)
    folder = await discover.run(config, tmp_path, client=client, seconds=0.01, ws_listen=fake_ws, now=NOW,
                                sleep=sleep)
    return folder, json.loads((folder / "summary.json").read_text()), sleeps


async def test_transient_candle_rejection_is_retried_once_and_reported(tmp_path):
    """Canli kesifte ilk mum istegi AUTH_INVALID_API_KEY ile reddedildi, digerleri basarili oldu."""
    requests = []
    folder, summary, sleeps = await run_with(tmp_path, candle_failures(requests, 1))
    candles = [r for r in requests if r.url.path.endswith("/candles")]
    assert len(candles) == 9 + 1  # 3 sembol x 3 zaman dilimi + tek yineleme
    assert candles[0].url.raw_path == candles[1].url.raw_path  # ayni salt-okuma istegi
    assert sleeps == [discover.RETRY_DELAY]
    # Ikinci denemede gecen istek hata sayilmaz; ilk ret ayri bir alanda saklanir.
    assert "candles/EURUSDc_M15" not in summary["errors"] and "candles/EURUSDc_M15#retry" not in summary["errors"]
    assert "AUTH_INVALID_API_KEY" in summary["retried_errors"]["candles/EURUSDc_M15"]
    assert "[http 401]" in summary["retried_errors"]["candles/EURUSDc_M15"]
    assert summary["retried_ok"] == ["candles/EURUSDc_M15"]
    assert (folder / "candles/EURUSDc_M15.json").exists()


async def test_persistent_candle_rejection_is_not_retried_in_a_loop(tmp_path):
    requests = []
    folder, summary, sleeps = await run_with(tmp_path, candle_failures(requests, 2))
    assert len([r for r in requests if r.url.path.endswith("/candles")]) == 9 + 1
    assert "candles/EURUSDc_M15" in summary["errors"] and "candles/EURUSDc_M15#retry" in summary["errors"]
    assert summary["retried_ok"] == []
    assert not (folder / "candles/EURUSDc_M15.json").exists()
    assert (folder / "candles/EURUSDc_H1.json").exists()  # sonraki istekler etkilenmez


async def test_rate_limited_candle_request_is_never_retried(tmp_path):
    requests = []
    limited = {"code": 3015, "error_message": "REQUEST_RATE_LIMIT", "retry_after": 1}
    _, summary, sleeps = await run_with(tmp_path, candle_failures(requests, 1, status=429, body=limited))
    assert len([r for r in requests if r.url.path.endswith("/candles")]) == 9
    assert sleeps == [] and summary["retried_ok"] == []
    assert "REQUEST_RATE_LIMIT" in summary["errors"]["candles/EURUSDc_M15"]


async def test_other_reads_are_not_retried(tmp_path):
    requests = []
    normal = responder(requests)

    def handle(request):
        if request.url.path.endswith("/deals"):
            requests.append(request)
            return httpx.Response(401, json={"code": 1000, "error_message": "AUTH_INVALID_API_KEY"})
        return normal(request)
    _, summary, sleeps = await run_with(tmp_path, handle)
    assert len([r for r in requests if r.url.path.endswith("/deals")]) == 1
    assert sleeps == [] and "deals" in summary["errors"]
