import json
import logging

import httpx

from tradebot.notify.expo import EXPO_URL, ExpoNotifier
from tradebot.store.repo import Repo

TOKEN_A = "ExponentPushToken[aaaaaaaaaaaaaaaaaaaaaa]"
TOKEN_B = "ExponentPushToken[bbbbbbbbbbbbbbbbbbbbbb]"


def make(tmp_path, responder=None, tokens=(TOKEN_A,)):
    clock = {"now": 1000.0}
    repo = Repo(tmp_path / "bot.db", clock=lambda: clock["now"])
    for token in tokens:
        repo.add_device(token)
    requests = []

    def handle(request):
        requests.append(request)
        if responder:
            return responder(request)
        count = len(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"status": "ok", "id": str(i)} for i in range(count)]})

    notifier = ExpoNotifier(repo, transport=httpx.MockTransport(handle), clock=lambda: clock["now"])
    return notifier, repo, requests, clock


async def test_payload_shape(tmp_path):
    notifier, _, requests, _ = make(tmp_path, tokens=(TOKEN_A, TOKEN_B))
    await notifier.send("trade_opened", "İşlem açıldı", "EURUSD BUY 0.1 lot", {"symbol": "EURUSD", "position_id": "7"})
    await notifier.drain()
    assert len(requests) == 1 and str(requests[0].url) == EXPO_URL
    assert requests[0].headers["content-type"] == "application/json"
    messages = json.loads(requests[0].content)
    assert [m["to"] for m in messages] == [TOKEN_A, TOKEN_B]
    assert messages[0] == {"to": TOKEN_A, "title": "İşlem açıldı", "body": "EURUSD BUY 0.1 lot", "sound": "default",
                           "priority": "high", "channelId": "default",
                           "data": {"kind": "trade_opened", "symbol": "EURUSD", "position_id": "7"}}


async def test_dedup_within_10_minutes(tmp_path):
    notifier, _, requests, clock = make(tmp_path)
    await notifier.send("order_rejected", "Emir reddedildi", "EURUSD", {"symbol": "EURUSD"})
    await notifier.drain()
    await notifier.send("order_rejected", "Emir reddedildi", "EURUSD", {"symbol": "EURUSD"})
    await notifier.drain()
    assert len(requests) == 1
    await notifier.send("order_rejected", "Emir reddedildi", "XAUUSD", {"symbol": "XAUUSD"})
    await notifier.drain()  # baska sembol
    await notifier.send("connection_lost", "Bağlantı koptu", "...")
    await notifier.drain()  # baska tur
    assert len(requests) == 3
    await notifier.send("connection_lost", "Bağlantı koptu", "...")
    await notifier.drain()
    assert len(requests) == 3
    clock["now"] += 599
    await notifier.send("order_rejected", "Emir reddedildi", "EURUSD", {"symbol": "EURUSD"})
    await notifier.drain()
    assert len(requests) == 3
    clock["now"] += 2
    await notifier.send("order_rejected", "Emir reddedildi", "EURUSD", {"symbol": "EURUSD"})
    await notifier.drain()
    assert len(requests) == 4


async def test_distinct_positions_on_same_symbol_are_not_suppressed(tmp_path):
    notifier, _, requests, _ = make(tmp_path)
    await notifier.send("trade_closed", "İşlem kapandı", "EURUSD +5", {"symbol": "EURUSD", "position_id": "1"})
    await notifier.drain()
    await notifier.send("trade_closed", "İşlem kapandı", "EURUSD -3", {"symbol": "EURUSD", "position_id": "2"})
    await notifier.drain()
    await notifier.send("trade_closed", "İşlem kapandı", "EURUSD -3", {"symbol": "EURUSD", "position_id": "2"})
    await notifier.drain()
    assert len(requests) == 2


async def test_send_failure_logged_not_raised(tmp_path, caplog):
    def boom(request):
        raise httpx.ConnectError("no route")
    notifier, _, requests, _ = make(tmp_path, responder=boom)
    with caplog.at_level(logging.WARNING, logger="tradebot.notify.expo"):
        await notifier.send("trade_opened", "t", "b", {"symbol": "EURUSD"})
        await notifier.drain()
    assert len(requests) == 1 and "bildirim" in caplog.text

    notifier, _, requests, _ = make(tmp_path / "b", responder=lambda r: httpx.Response(500, text="oops"))
    await notifier.send("trade_opened", "t", "b", {"symbol": "EURUSD"})
    await notifier.drain()
    assert len(requests) == 1


async def test_failed_send_can_be_retried_by_next_event(tmp_path):
    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("no route")
        return httpx.Response(200, json={"data": [{"status": "ok"}]})
    notifier, _, requests, _ = make(tmp_path, responder=flaky)
    await notifier.send("bot_halted", "Bot durdu", "x")
    await notifier.drain()
    await notifier.send("bot_halted", "Bot durdu", "x")
    await notifier.drain()  # ilk gonderim basarisizdi: bastirilmaz
    assert len(requests) == 2


async def test_no_devices_no_request(tmp_path):
    notifier, _, requests, _ = make(tmp_path, tokens=())
    await notifier.send("trade_opened", "t", "b")
    await notifier.drain()
    assert requests == []


async def test_unregistered_device_is_removed(tmp_path):
    def responder(request):
        return httpx.Response(200, json={"data": [
            {"status": "error", "message": "not registered", "details": {"error": "DeviceNotRegistered"}},
            {"status": "ok", "id": "1"}]})
    notifier, repo, _, _ = make(tmp_path, responder=responder, tokens=(TOKEN_A, TOKEN_B))
    await notifier.send("trade_opened", "t", "b")
    await notifier.drain()
    assert repo.devices() == [TOKEN_B]


async def test_data_is_json_safe_and_small(tmp_path):
    notifier, _, requests, _ = make(tmp_path)
    await notifier.send("signal", "t", "b", {"symbol": "EURUSD", "blob": "x" * 10_000, "obj": object()})
    await notifier.drain()
    message = json.loads(requests[0].content)[0]
    assert message["data"]["symbol"] == "EURUSD" and len(json.dumps(message["data"])) < 3000
