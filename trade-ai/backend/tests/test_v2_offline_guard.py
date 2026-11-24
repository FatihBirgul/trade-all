"""Verify the runner's safety boundary without making any real network calls."""
from contextlib import closing
from pathlib import Path
import socket
import sqlite3
from tempfile import TemporaryDirectory
from unittest import TestCase

from tests.v2_offline_guard import offline_test_environment


class OfflineGuardTests(TestCase):
    def test_dns_and_socket_connections_are_blocked_before_io(self):
        with TemporaryDirectory(prefix="v2-guard-") as root:
            with offline_test_environment(root):
                with self.assertRaises(AssertionError):
                    socket.create_connection(("fixture.invalid", 443))
                with self.assertRaises(AssertionError):
                    socket.getaddrinfo("fixture.invalid", 443)
                with socket.socket() as connection:
                    with self.assertRaises(AssertionError):
                        connection.connect(("127.0.0.1", 1))

    def test_sqlite_outside_temporary_root_is_blocked_without_creating_file(self):
        with TemporaryDirectory(prefix="v2-guard-") as root:
            outside = Path(root).parent / (Path(root).name + "-forbidden.sqlite")
            with offline_test_environment(root):
                with self.assertRaises(AssertionError):
                    sqlite3.connect(outside)
                with self.assertRaises(AssertionError):
                    sqlite3.connect(outside.as_uri() + "?mode=rw", uri=True)
            self.assertFalse(outside.exists())

    def test_sqlite_in_temporary_root_and_memory_are_allowed(self):
        with TemporaryDirectory(prefix="v2-guard-") as root:
            path = Path(root) / "fixture.sqlite"
            with offline_test_environment(root):
                for target in (path, ":memory:"):
                    with closing(sqlite3.connect(target)) as connection:
                        self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)

    def test_guard_restores_functions_and_uses_no_persistent_configuration(self):
        before = socket.create_connection, sqlite3.connect
        with TemporaryDirectory(prefix="v2-guard-") as root:
            with offline_test_environment(root):
                self.assertNotEqual(before, (socket.create_connection, sqlite3.connect))
        self.assertEqual(before, (socket.create_connection, sqlite3.connect))
