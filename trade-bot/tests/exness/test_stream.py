import asyncio
import json

import pytest
from websockets.asyncio.server import serve

from tests.exness.test_client import settings
from tradebot.exness.client import ExnessClient
from tradebot.exness.stream import Stream


class StopLoop(Exception):
    pass


async def test_reconnect_backoff_caps_at_60():
    delays = []

    async def failing_connect(url, headers):
        raise OSError("refused")

    async def fake_sleep(seconds):
        delays.append(seconds)
        if len(delays) == 9:
            raise StopLoop

    async def on_message(message):
        pass

    client = ExnessClient(settings())
    stream = Stream(client, "/v1/server-events/accounts/123456/ws/ticks", on_message,
                    connect=failing_connect, sleep=fake_sleep)
    with pytest.raises(StopLoop):
        await stream.run()
    assert delays == [1, 2, 4, 8, 16, 32, 60, 60, 60]
    assert stream.connected is False


async def test_stream_receives_resubscribes_and_resets_backoff():
    received, subscriptions, handshakes = [], [], []
    connections = 0

    async def handler(socket):
        nonlocal connections
        connections += 1
        handshakes.append(dict(socket.request.headers))
        subscriptions.append(json.loads(await socket.recv()))
        await socket.send(json.dumps({"instrument": "EURUSD", "bid": 1.1, "ask": 1.2,
                                      "timestamp": "2026-03-16T12:54:30+00:00", "n": connections}))
        if connections == 1:
            await socket.close()  # ilk baglanti duser; istemci yeniden baglanip abone olmali
        else:
            await socket.wait_closed()

    delays = []

    async def fast_sleep(seconds):
        delays.append(seconds)
        await asyncio.sleep(0)

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = ExnessClient(settings(EXNESS_AP_HOST=f"http://127.0.0.1:{port}"))
        done = asyncio.Event()

        async def on_message(message):
            received.append(message)
            if len(received) == 2:
                done.set()

        stream = Stream(client, "/v1/server-events/accounts/123456/ws/ticks", on_message, sleep=fast_sleep)
        stream.add_subscription({"id": "t1", "subscribe": {"event": "ticks", "instruments": ["EURUSD"]}})
        task = asyncio.create_task(stream.run())
        await asyncio.wait_for(done.wait(), timeout=5)
        assert stream.connected is True and stream.last_message_at is not None
        stream.stop()
        await asyncio.wait_for(task, timeout=5)

    assert [m["n"] for m in received] == [1, 2]
    assert len(subscriptions) == 2 and subscriptions[0] == subscriptions[1]
    assert delays[0] == 1  # mesaj alinmis bir baglantidan sonra bekleme bastan baslar
    assert "exn-sign" in {k.lower() for k in handshakes[0]}
    assert stream.connected is False


async def test_handler_error_does_not_kill_stream():
    seen = []

    async def handler(socket):
        for n in range(3):
            await socket.send(json.dumps({"n": n}))
        await socket.wait_closed()

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        client = ExnessClient(settings(EXNESS_AP_HOST=f"http://127.0.0.1:{port}"))
        done = asyncio.Event()

        async def on_message(message):
            seen.append(message["n"])
            if message["n"] == 1:
                raise RuntimeError("isleyici hatasi")
            if message["n"] == 2:
                done.set()

        stream = Stream(client, "/v1/server-events/accounts/123456/ws/events", on_message)
        task = asyncio.create_task(stream.run())
        await asyncio.wait_for(done.wait(), timeout=5)
        stream.stop()
        await asyncio.wait_for(task, timeout=5)
    assert seen == [0, 1, 2]
