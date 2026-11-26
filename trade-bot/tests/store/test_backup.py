"""Gunluk yedek, temizlik ve bakim gorevi: veri kaybina karsi koruma; islem yolunu dusurmez."""
import os
import sqlite3
import stat

import httpx
import pytest

from tests.app_helpers import NOW, started
from tradebot.api.server import create_app
from tradebot.store import backup
from tradebot.store.repo import Repo

DAY = 86400.0


def test_backup_is_a_consistent_private_copy_and_old_ones_are_pruned(tmp_path):
    repo = Repo(tmp_path / "bot.db", clock=lambda: NOW)
    repo.add_event("warning", "bot_stopped", "durduruldu")
    repo.set_setting("isaret", {"deger": 42})
    for n in range(20):  # 20 gun: yalnizca en yeni 14 kalir
        result = backup.backup_database(repo.db_path, NOW + n * DAY)
    files = sorted((tmp_path / "backups").glob("tradebot-*.db"))
    assert len(files) == backup.KEEP_BACKUPS and result["removed"] == 1
    assert files[-1].name == f"tradebot-{backup.backup_day(NOW + 19 * DAY)}.db" and result["bytes"] > 0
    assert stat.S_IMODE(os.stat(files[-1]).st_mode) == 0o600
    assert not list((tmp_path / "backups").glob("*.partial"))
    copy = sqlite3.connect(files[-1])
    assert copy.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert copy.execute("SELECT kind FROM events").fetchall() == [("bot_stopped",)]
    assert "42" in copy.execute("SELECT value_json FROM settings WHERE key = 'isaret'").fetchone()[0]
    # Ayni gun yeniden alinirsa ustune yazilir, cogalmaz.
    backup.backup_database(repo.db_path, NOW + 19 * DAY + 60)
    assert len(list((tmp_path / "backups").glob("tradebot-*.db"))) == backup.KEEP_BACKUPS


def test_failed_backup_leaves_no_partial_file_and_keeps_older_backups(tmp_path, monkeypatch):
    repo = Repo(tmp_path / "bot.db", clock=lambda: NOW)
    backup.backup_database(repo.db_path, NOW)

    def corrupt(copy):
        raise sqlite3.DatabaseError("yedek butunluk denetiminden gecmedi")

    monkeypatch.setattr(backup, "_verify", corrupt)
    with pytest.raises(sqlite3.DatabaseError):
        backup.backup_database(repo.db_path, NOW + DAY)
    names = sorted(p.name for p in (tmp_path / "backups").iterdir())
    assert names == [f"tradebot-{backup.backup_day(NOW)}.db"]  # yarim dosya yok, eski yedek duruyor


def test_prune_removes_only_old_scan_noise(tmp_path):
    repo = Repo(tmp_path / "bot.db", clock=lambda: NOW)
    old, recent = NOW - 61 * DAY, NOW - 59 * DAY
    for kind in ("scan", "scan_skipped", "signal_observed", "signal", "order_sent", "settings_changed", "sl_missing"):
        repo.add_event("info", kind, "eski", at=old)
        repo.add_event("info", kind, "yeni", at=recent)
    repo.add_event("warning", "scan", "eski uyari", at=old)  # uyari duzeyi silinmez
    assert backup.prune_noise(repo.conn, NOW) == 3
    left = [(r[0], r[1]) for r in repo.conn.execute("SELECT kind, message FROM events WHERE message LIKE 'eski%'")]
    assert sorted(left) == [("order_sent", "eski"), ("scan", "eski uyari"), ("settings_changed", "eski"),
                            ("signal", "eski"), ("sl_missing", "eski")]
    assert repo.conn.execute("SELECT COUNT(*) FROM events WHERE message = 'yeni'").fetchone()[0] == 7


async def test_maintenance_runs_once_a_day_and_reports_on_health(tmp_path):
    app = await started(tmp_path, dry_run=True)
    first = await app.bot.maintenance()
    assert first is not None and first["bytes"] > 0
    assert await app.bot.maintenance() is None  # ayni gun ikinci kez calismaz
    assert len(list((tmp_path / "backups").glob("tradebot-*.db"))) == 1
    assert app.kinds().count("backup_done") == 1
    api = create_app(app.bot, clock=lambda: app.clock["now"])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://bot") as http:
        health = (await http.get("/health")).json()
    assert health["last_backup_at"] == app.clock["now"]
    assert "backups" not in str(health) and str(tmp_path) not in str(health)  # dosya yolu disari verilmez
    app.advance(DAY)
    assert await app.bot.maintenance() is not None
    assert len(list((tmp_path / "backups").glob("tradebot-*.db"))) == 2


async def test_maintenance_failure_warns_once_a_day_and_never_stops_trading(tmp_path, monkeypatch):
    app = await started(tmp_path)

    def boom(*args, **kwargs):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(backup, "backup_database", boom)
    assert await app.bot.maintenance() is None
    assert await app.bot.maintenance() is None  # yeniden dener ama ayni gun ikinci bildirim yok
    assert app.kinds().count("backup_failed") == 1
    assert app.repo.get_setting("maintenance_failures") == 2 and app.repo.get_setting("last_backup_at") is None
    summary = await app.bot.on_bar_close()  # bot calismaya devam eder
    assert summary.opened == 1
    monkeypatch.undo()
    assert await app.bot.maintenance() is not None  # ertesi denemede basarir
    assert app.repo.get_setting("maintenance_failures") == 0


def test_backup_finishes_while_the_bot_keeps_writing(tmp_path):
    """Inceleme I1: parca parca kopya, arada her yazmada bastan baslar ve hic bitmeyebilirdi."""
    import threading

    repo = Repo(tmp_path / "bot.db", clock=lambda: NOW)
    for n in range(3000):
        repo.add_event("info", "scan", "x" * 200, {"n": n})
    stop, errors = threading.Event(), []

    def writer():
        conn = sqlite3.connect(tmp_path / "bot.db", isolation_level=None, timeout=0.5)
        while not stop.is_set():
            try:
                conn.execute("INSERT INTO events (at, level, kind, message) VALUES (?, 'info', 'scan', 'y')", (NOW,))
            except sqlite3.Error as exc:  # yazan taraf yedek yuzunden hata almamali
                errors.append(exc)
        conn.close()

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        result = backup.backup_database(repo.db_path, NOW)
    finally:
        stop.set()
        thread.join()
    assert result["seconds"] < 5 and errors == []
    copy = sqlite3.connect(result["path"])
    assert copy.execute("SELECT COUNT(*) FROM events").fetchone()[0] >= 3000


def test_backup_is_skipped_when_the_disk_is_nearly_full(tmp_path, monkeypatch):
    import collections

    repo = Repo(tmp_path / "bot.db", clock=lambda: NOW)
    usage = collections.namedtuple("usage", "total used free")
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda path: usage(10**9, 10**9 - 10**6, 10**6))
    with pytest.raises(OSError):
        backup.backup_database(repo.db_path, NOW)
    assert list((tmp_path / "backups").iterdir()) == []  # diske tek bayt yazilmadi


async def test_backup_event_and_logs_do_not_reveal_the_backup_path(tmp_path, caplog, monkeypatch):
    import json
    import logging

    caplog.set_level(logging.DEBUG)
    app = await started(tmp_path, dry_run=True)
    await app.bot.maintenance()

    def boom(*args, **kwargs):
        raise OSError(28, "No space left on device", str(tmp_path / "backups" / "tradebot-x.db.partial"))

    monkeypatch.setattr(backup, "backup_database", boom)
    app.advance(DAY)
    await app.bot.maintenance()
    written = caplog.text + json.dumps(app.repo.events(limit=500), default=str)
    assert "backup_failed" in written and str(tmp_path) not in written and ".partial" not in written


def test_backup_survives_odd_characters_in_the_path_and_rejects_an_empty_copy(tmp_path, monkeypatch):
    """Inceleme: yolda `#` ya da `?` varsa URI kesiliyor, bos bir dosya "yedek" diye basarili sayiliyordu."""
    folder = tmp_path / "veri #1 ?x"
    folder.mkdir()
    repo = Repo(folder / "bot.db", clock=lambda: NOW)
    repo.add_event("warning", "bot_stopped", "durduruldu")
    result = backup.backup_database(repo.db_path, NOW)
    copy = sqlite3.connect(result["path"])
    assert copy.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1

    empty = sqlite3.connect(":memory:")
    with pytest.raises(sqlite3.DatabaseError):
        backup._verify(empty)  # butunlugu "ok" ama botun tablolari yok


def test_stale_partial_files_from_an_earlier_day_are_removed(tmp_path):
    repo = Repo(tmp_path / "bot.db", clock=lambda: NOW)
    (tmp_path / "backups").mkdir()
    stale = tmp_path / "backups" / "tradebot-20260101.db.partial"
    stale.write_bytes(b"yarim")
    backup.backup_database(repo.db_path, NOW)
    assert not stale.exists()
