"""Gunluk SQLite yedegi ve veri temizligi.

Yedek, bot surecinin icinde alinir (root gerektiren zamanlayici yok) ve yalnizca veritabani dizininin altina
yazilir. `sqlite3.Connection.backup()` calisan veritabaninin tutarli bir kopyasini cikarir; kopya gecici dosyaya
yazilir, butunlugu denetlenir ve ancak ondan sonra yerine tasinir. Yedekte erisim anahtari ozetleri bulunur:
dosyalar yalnizca servis kullanicisinca okunabilir (600) ve depo/gunluklere yazilmaz.
"""

from __future__ import annotations

import errno
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

KEEP_BACKUPS = 14
MIN_FREE_FACTOR = 2  # yedekten once en az veritabaninin bu kati kadar bos alan olmali
MIN_FREE_BYTES = 50 * 1024 * 1024
BACKUP_PREFIX = "tradebot-"
NOISE_KINDS = ("scan", "scan_skipped", "signal_observed")  # yalnizca bunlar eskiyince silinir
NOISE_KEEP_DAYS = 60


def backup_day(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y%m%d")


def _verify(copy: sqlite3.Connection) -> None:
    verdict = copy.execute("PRAGMA quick_check").fetchone()
    if not verdict or verdict[0] != "ok":
        raise sqlite3.DatabaseError(f"yedek butunluk denetiminden gecmedi: {verdict}")


def backup_database(db_path: Path | str, now: float, *, keep: int = KEEP_BACKUPS) -> dict:
    """Bugunun yedegini alir -> {"path", "bytes", "seconds", "removed"}. Hata olursa istisna firlatir.

    Ayri bir baglanti kullanir: cagiran bunu is parcaciginda calistirabilir, botun baglantisi mesgul edilmez.
    """
    source_path = Path(db_path)
    folder = source_path.parent / "backups"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    size = source_path.stat().st_size
    free = shutil.disk_usage(folder).free
    if free < MIN_FREE_FACTOR * size + MIN_FREE_BYTES:
        # Dolmak uzere olan diske tam boy bir kopya yazmak asil veritabanini da yazilamaz hale getirebilir.
        raise OSError(errno.ENOSPC, "yedek icin yeterli bos alan yok")
    target = folder / f"{BACKUP_PREFIX}{backup_day(now)}.db"
    partial = target.with_suffix(".db.partial")
    started = time.monotonic()
    partial.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True, timeout=10)
    try:
        # Dosya, icine veri yazilmadan once yalnizca sahibine acik olusturulur.
        os.close(os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
        copy = sqlite3.connect(str(partial))
        try:
            # Tek adimda (pages=-1): kopya tek bir WAL okuma goruntusunden alinir, yazan baglantiyi kilitlemez.
            # Parca parca kopyalama, arada her yazmada bastan baslar ve yogun yazma altinda hic bitmeyebilirdi.
            source.backup(copy, pages=-1)
            _verify(copy)
        finally:
            copy.close()
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    finally:
        source.close()
    os.replace(partial, target)
    removed = 0
    for old in sorted(folder.glob(f"{BACKUP_PREFIX}*.db"), reverse=True)[max(1, keep):]:
        old.unlink(missing_ok=True)
        removed += 1
    return {"path": str(target), "bytes": target.stat().st_size, "seconds": round(time.monotonic() - started, 2),
            "removed": removed}


def prune_noise(conn: sqlite3.Connection, now: float, *, keep_days: float = NOISE_KEEP_DAYS) -> int:
    """Eski tarama gurultusunu siler. Islem, emir, ayar, uyari ve hata olaylarina DOKUNMAZ."""
    marks = ",".join("?" for _ in NOISE_KINDS)
    cursor = conn.execute(f"DELETE FROM events WHERE at < ? AND level = 'info' AND kind IN ({marks})",
                          (now - keep_days * 86400.0, *NOISE_KINDS))
    return cursor.rowcount
