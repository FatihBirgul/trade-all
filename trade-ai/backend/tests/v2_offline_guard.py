"""Test-only guard: no sockets; SQLite restricted to a fresh temporary root."""
from contextlib import contextmanager
from pathlib import Path
import socket
import sqlite3
import tempfile
import sys
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import url2pathname


_connect = sqlite3.connect
_socket_connect = socket.socket.connect
_socketpair_code = getattr(socket.socketpair, "__code__", None)


@contextmanager
def offline_test_environment(root):
    root = Path(root).resolve()

    def no_network(*_, **__):
        raise AssertionError("Network access is forbidden in V2 offline tests")

    def guarded_connect(*args, **kwargs):
        # Windows implements asyncio's local wakeup socketpair via loopback.
        # Permit ONLY the direct stdlib socketpair call, never application TCP.
        caller = sys._getframe(1).f_code
        if (caller is _socketpair_code and len(args) >= 2 and isinstance(args[1], tuple)
                and args[1][0] in ("127.0.0.1", "::1")):
            return _socket_connect(*args, **kwargs)
        return no_network()

    def isolated_connect(database, *args, **kwargs):
        if str(database) != ":memory:":
            raw = str(database)
            if raw.startswith("file:"):
                uri = urlsplit(raw)
                if uri.netloc:
                    raise AssertionError("Remote SQLite paths are forbidden")
                raw = url2pathname(uri.path)
            target = Path(raw).resolve()
            if not target.is_relative_to(root):
                raise AssertionError("SQLite access outside the V2 temporary test root is forbidden")
        return _connect(database, *args, **kwargs)

    with (patch.object(tempfile, "tempdir", str(root)),
          patch.object(sqlite3, "connect", isolated_connect),
          patch.object(socket, "create_connection", no_network),
          patch.object(socket, "getaddrinfo", no_network),
          patch.object(socket.socket, "connect", guarded_connect),
          patch.object(socket.socket, "connect_ex", no_network),
          patch.object(socket.socket, "sendto", no_network)):
        yield
