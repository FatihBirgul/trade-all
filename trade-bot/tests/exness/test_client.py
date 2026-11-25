import json

import httpx
import pytest

from tradebot.config import load_settings
from tradebot.exness.client import ExnessClient
from tradebot.exness.errors import (ExnessAuthError, ExnessRateLimited, ExnessRejected,
                                    ExnessUnavailable)
from tradebot.exness.limits import RateLimiter
from tradebot.exness.signing import b64url_decode, load_private_key

KEY = ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
       "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")


def settings(**extra):
    env = {"EXNESS_API_KEY": "exnsk-test", "EXNESS_PRIVATE_KEY": KEY, "EXNESS_ACCOUNT_ID": "123456",
           "EXNESS_GATEWAY_HOST": "gateway.test", "EXNESS_AP_HOST": "ap.test"}
    env.update(extra)
    return load_settings({k: v for k, v in env.items() if v is not None})


class Recorder:
    def __init__(self, responder):
        self.requests = []
        self.responder = responder

    def __call__(self, request):
        self.requests.append(request)
        return self.responder(request)


def client_with(responder, **extra):
    recorder = Recorder(responder)
    return ExnessClient(settings(**extra), transport=httpx.MockTransport(recorder), clock=lambda: 1773656070.123), recorder


def ok(payload, status=200):
    return lambda request: httpx.Response(status, json=payload)


async def test_get_signs_exact_path_and_returns_json():
    client, rec = client_with(ok({"account_id": "123456"}))
    result = await client.get("/v1/configuration/accounts/123456/account?x=1")
    assert result == {"account_id": "123456"}
    request = rec.requests[0]
    assert str(request.url) == "https://ap.test/v1/configuration/accounts/123456/account?x=1"
    payload = json.loads(b64url_decode(request.headers["EXN-DATA"]))
    assert payload["path"] == "/v1/configuration/accounts/123456/account?x=1"
    assert payload["method"] == "GET" and payload["timestamp"] == 1773656070123
    assert request.headers["EXN-IDEMPOTENCY-KEY"] == ""
    load_private_key(KEY).public_key().verify(
        b64url_decode(request.headers["EXN-SIGN"]), b64url_decode(request.headers["EXN-DATA"]))


async def test_post_signs_the_bytes_it_sends():
    client, rec = client_with(ok({"status": "accepted", "operation_id": "789"}, status=202))
    result = await client.post("/v1/trading/accounts/123456/positions",
                               {"instrument": "EURUSD", "side": "buy", "volume": "0.01"}, "bot-abc123")
    assert result["operation_id"] == "789"
    request = rec.requests[0]
    import base64, hashlib
    expected = base64.urlsafe_b64encode(hashlib.sha256(request.content).digest()).decode().rstrip("=")
    payload = json.loads(b64url_decode(request.headers["EXN-DATA"]))
    assert payload["body_hash"] == expected
    assert payload["idempotency_key"] == request.headers["EXN-IDEMPOTENCY-KEY"] == "bot-abc123"
    assert request.headers["content-type"] == "application/json"
    assert json.loads(request.content)["volume"] == "0.01"


async def test_delete_has_no_body_and_requires_idempotency():
    client, rec = client_with(ok({"status": "accepted"}, status=202))
    await client.delete("/v1/trading/accounts/123456/positions/1?volume=0.01", "close-1-abc")
    assert rec.requests[0].content == b""
    with pytest.raises(ValueError):
        await client.delete("/v1/trading/accounts/123456/positions/1", "")


async def test_signature_rejected_raises_auth_error_no_retry():
    client, rec = client_with(ok({"code": 1001, "error_message": "AUTH_INVALID_SIGNATURE"}, status=401))
    with pytest.raises(ExnessAuthError) as error:
        await client.get("/v1/configuration/accounts/123456/account")
    assert error.value.code == 1001 and "AUTH_INVALID_SIGNATURE" in str(error.value)
    assert len(rec.requests) == 1


async def test_429_raises_rate_limited_no_loop():
    def responder(request):
        return httpx.Response(429, json={"code": 3015, "error_message": "REQUEST_RATE_LIMIT"},
                              headers={"Retry-After": "7"})
    client, rec = client_with(responder)
    with pytest.raises(ExnessRateLimited) as error:
        await client.get("/v1/trading/accounts/123456/snapshot")
    assert error.value.retry_after == 7.0
    assert len(rec.requests) == 1


async def test_business_rejection_carries_code():
    client, rec = client_with(ok({"code": 3013, "error_message": "REQUEST_POSITION_NOT_FOUND"}, status=400))
    with pytest.raises(ExnessRejected) as error:
        await client.delete("/v1/trading/accounts/123456/positions/9", "close-9-abc")
    assert error.value.code == 3013 and error.value.message == "REQUEST_POSITION_NOT_FOUND"
    assert len(rec.requests) == 1


async def test_503_and_transport_errors_are_unavailable_without_retry():
    client, rec = client_with(ok({"code": 2, "error_message": "SYSTEM_TEMPORARY_UNAVAILABLE"}, status=503))
    with pytest.raises(ExnessUnavailable):
        await client.get("/v1/trading/accounts/123456/snapshot")
    assert len(rec.requests) == 1

    def boom(request):
        raise httpx.ConnectError("no route")
    client, rec = client_with(boom)
    with pytest.raises(ExnessUnavailable):
        await client.get("/v1/trading/accounts/123456/snapshot")
    assert len(rec.requests) == 1


async def test_non_json_error_body_is_handled():
    client, _ = client_with(lambda request: httpx.Response(403, text="<html>blocked</html>"))
    with pytest.raises(ExnessRejected) as error:
        await client.get("/v1/trading/accounts/123456/snapshot")
    assert error.value.code is None and error.value.status == 403


async def test_errors_never_contain_secrets():
    client, _ = client_with(ok({"code": 1000, "error_message": "AUTH_INVALID_API_KEY"}, status=401))
    with pytest.raises(ExnessAuthError) as error:
        await client.get("/v1/configuration/accounts/123456/account")
    text = repr(error.value) + str(error.value)
    assert "exnsk-test" not in text and KEY[:16] not in text


async def test_resolve_host_prefers_configured_access_point():
    client, rec = client_with(ok({}))
    assert await client.resolve_host() == "https://ap.test"
    assert rec.requests == []


async def test_resolve_host_discovers_through_gateway_once():
    def responder(request):
        if request.url.host == "gateway.test":
            assert request.url.raw_path == b"/v1/trading/access-point?account_id=123456"
            return httpx.Response(200, json={"access_point": "https://ap-7.test", "account_id": "123456"})
        return httpx.Response(200, json={"ok": True})
    client, rec = client_with(responder, EXNESS_AP_HOST=None)
    assert await client.resolve_host() == "https://ap-7.test"
    await client.get("/v1/configuration/accounts/123456/account")
    await client.get("/v1/configuration/accounts/123456/account")
    hosts = [r.url.host for r in rec.requests]
    assert hosts == ["gateway.test", "ap-7.test", "ap-7.test"]


async def test_discovery_rejects_unsafe_access_point():
    client, _ = client_with(ok({"access_point": "http://evil.test/path"}), EXNESS_AP_HOST=None)
    with pytest.raises(ExnessUnavailable):
        await client.resolve_host()


async def test_ws_endpoint_is_signed_as_get():
    client, _ = client_with(ok({}))
    url, headers = await client.ws_endpoint("/v1/server-events/accounts/123456/ws/ticks")
    assert url == "wss://ap.test/v1/server-events/accounts/123456/ws/ticks"
    payload = json.loads(b64url_decode(headers["EXN-DATA"]))
    assert payload["method"] == "GET" and payload["path"] == "/v1/server-events/accounts/123456/ws/ticks"


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


async def test_rate_limiter_waits_for_window_instead_of_bursting():
    fake = FakeTime()
    limiter = RateLimiter(clock=fake.clock, sleep=fake.sleep)
    limiter.configure(global_rate=(100, 1.0), methods=[("GET", "/v1/trading/accounts/{account_id}/snapshot", 2, 10.0)])
    for _ in range(2):
        await limiter.acquire("GET", "/v1/trading/accounts/123456/snapshot")
    assert fake.sleeps == []
    await limiter.acquire("GET", "/v1/trading/accounts/123456/snapshot")
    assert sum(fake.sleeps) >= 10.0


async def test_rate_limiter_matches_templates_ignoring_query_and_respects_global():
    fake = FakeTime()
    limiter = RateLimiter(clock=fake.clock, sleep=fake.sleep)
    limiter.configure(global_rate=(3, 5.0), methods=[
        ("GET", "/v1/market-data/accounts/{account_id}/candles", 50, 1.0),
        ("DELETE", "/v1/trading/accounts/{account_id}/positions/{position_id}", 50, 1.0)])
    await limiter.acquire("GET", "/v1/market-data/accounts/1/candles?instrument=EURUSD")
    await limiter.acquire("DELETE", "/v1/trading/accounts/1/positions/22?volume=0.01")
    await limiter.acquire("GET", "/v1/unknown")
    assert fake.sleeps == []
    await limiter.acquire("GET", "/v1/unknown")
    assert sum(fake.sleeps) >= 5.0


async def test_unconfigured_rate_limiter_does_not_block():
    fake = FakeTime()
    limiter = RateLimiter(clock=fake.clock, sleep=fake.sleep)
    for _ in range(50):
        await limiter.acquire("GET", "/v1/x")
    assert fake.sleeps == []


async def test_client_uses_rate_limiter():
    fake = FakeTime()
    limiter = RateLimiter(clock=fake.clock, sleep=fake.sleep)
    limiter.configure(global_rate=(1, 2.0), methods=[])
    recorder = Recorder(ok({}))
    client = ExnessClient(settings(), transport=httpx.MockTransport(recorder), limiter=limiter)
    await client.get("/v1/a")
    await client.get("/v1/b")
    assert sum(fake.sleeps) >= 2.0 and len(recorder.requests) == 2
