import asyncio
import json

import pytest
from websockets.asyncio.server import serve

from tests.exness.test_client import settings
from tradebot.exness import schema
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


async def _subprotocol_server(seen):
    """Exness gibi davranan yerel sunucu: el sikismasinda alt-protokol secer."""
    from websockets.asyncio.server import serve

    async def handler(socket):
        seen.append((socket.subprotocol, socket.request.headers.get("EXN-API-KEY")))
        await socket.send(json.dumps({"hello": True}))
        await socket.wait_closed()

    # Canli sunucu gibi: istemci onermese de alt-protokolu secip yanit basligina yazar.
    return await serve(handler, "127.0.0.1", 0, subprotocols=[schema.WS_SUBPROTOCOL],
                       select_subprotocol=lambda connection, offered: schema.WS_SUBPROTOCOL)


async def test_default_connect_offers_the_exness_subprotocol():
    """Canli kesif: 'NegotiationError: no subprotocols supported' (sunucu alt-protokol seciyor)."""
    from tradebot.exness.stream import _default_connect

    seen = []
    server = await _subprotocol_server(seen)
    port = server.sockets[0].getsockname()[1]
    try:
        socket = await _default_connect(f"ws://127.0.0.1:{port}/v1/server-events/accounts/1/ws/ticks",
                                        {"EXN-API-KEY": "k"})
        try:
            assert socket.subprotocol == "exness-ws-protocol"
            assert json.loads(await asyncio.wait_for(socket.recv(), 5)) == {"hello": True}
        finally:
            await socket.close()
        assert seen == [("exness-ws-protocol", "k")]  # imza basliklari el sikismasinda gider
    finally:
        server.close()
        await server.wait_closed()


async def test_connecting_without_the_subprotocol_fails_like_production_did():
    from websockets.asyncio.client import connect
    from websockets.exceptions import NegotiationError

    server = await _subprotocol_server([])
    port = server.sockets[0].getsockname()[1]
    try:
        with pytest.raises(NegotiationError, match="no subprotocols supported"):
            await connect(f"ws://127.0.0.1:{port}/x", open_timeout=5)
    finally:
        server.close()
        await server.wait_closed()


async def test_discovery_listener_offers_the_subprotocol_too():
    from tradebot import discover

    seen = []
    server = await _subprotocol_server(seen)
    port = server.sockets[0].getsockname()[1]

    class Client:
        async def ws_endpoint(self, path):
            return f"ws://127.0.0.1:{port}{path}", {"EXN-API-KEY": "k"}
    try:
        messages = await discover.listen_ws(Client(), "/v1/x", [{"id": "1"}], 0.5)
        assert messages == [{"hello": True}] and seen[0][0] == "exness-ws-protocol"
    finally:
        server.close()
        await server.wait_closed()
