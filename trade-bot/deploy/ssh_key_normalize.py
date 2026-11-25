#!/usr/bin/env python3
"""GitHub Secret'a yapistirilan SSH ozel anahtarini duzgun PEM bicimine getirir.

Elle yapistirmada sik bozulan seyler onarilir: Windows satir sonlari (CR), satir sonlarinin bosluga
donmesi (tek satir), satir basi/sonu bosluklari, bos satirlar, "\\n" olarak yazilmis satir sonlari ve
basa/sona eklenmis fazladan metin. Anahtarin icerigi degistirilmez; yalnizca bosluklar duzenlenir.

    VPS_SSH_KEY=... python3 ssh_key_normalize.py <cikti dosyasi>

Onarilamiyorsa anahtari YAZDIRMADAN yalnizca tanilayici sayilari bildirir ve 1 ile cikar.
"""
from __future__ import annotations

import os
import re
import sys

BLOCK = re.compile(r"-----BEGIN ([A-Z0-9 ]*PRIVATE KEY)-----(.*?)-----END \1-----", re.S)
BODY = re.compile(r"^[A-Za-z0-9+/=]+$")
MARKER = re.compile(r"-----(?:BEGIN|END) [A-Z0-9 ]+-----")
OPENSSH_MAGIC = "b3BlbnNzaC1rZXktdjEA"  # base64("openssh-key-v1\0")


class KeyError_(ValueError):
    pass


def diagnose(raw: str) -> str:
    """Anahtarin kendisini iceremeyen, yalnizca bicimi anlatan ozet."""
    return (f"uzunluk={len(raw)} satir={raw.count(chr(10)) + 1} CR={'var' if chr(13) in raw else 'yok'} "
            f"BEGIN={'var' if '-----BEGIN ' in raw else 'yok'} END={'var' if '-----END ' in raw else 'yok'} "
            f"acik_anahtar={'evet' if raw.lstrip().startswith(('ssh-ed25519 ', 'ssh-rsa ', 'ecdsa-')) else 'hayir'} "
            f"openssh_govdesi={'evet' if re.sub(r'\\s+', '', raw).startswith(OPENSSH_MAGIC) else 'hayir'}")


def normalize(raw: str) -> str:
    text = raw.replace("\r", "").replace("\\n", "\n")
    match = BLOCK.search(text)
    if match is None:
        # Baslik/bitis satirlari olmadan (ya da yalnizca biri ile) yapistirilmis govde: OpenSSH ozel
        # anahtarinin govdesi her zaman "openssh-key-v1\0" imzasiyla baslar. Imza tutuyorsa satirlar eklenir.
        bare = re.sub(r"\s+", "", MARKER.sub("", text))
        if bare.startswith(OPENSSH_MAGIC) and BODY.match(bare):
            lines = [bare[i:i + 70] for i in range(0, len(bare), 70)]
            return "\n".join(["-----BEGIN OPENSSH PRIVATE KEY-----", *lines,
                              "-----END OPENSSH PRIVATE KEY-----"]) + "\n"
        raise KeyError_("ozel anahtar blogu bulunamadi (-----BEGIN ... PRIVATE KEY----- ile "
                        "-----END ... PRIVATE KEY----- satirlari dahil tamami yapistirilmali)")
    label, body = match.group(1), re.sub(r"\s+", "", match.group(2))
    if not body or not BODY.match(body):
        raise KeyError_("anahtar govdesinde beklenmeyen karakter var (eksik ya da bozuk kopyalanmis)")
    lines = [body[i:i + 70] for i in range(0, len(body), 70)]
    return "\n".join([f"-----BEGIN {label}-----", *lines, f"-----END {label}-----"]) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("kullanim: VPS_SSH_KEY=... ssh_key_normalize.py <cikti dosyasi>", file=sys.stderr)
        return 2
    raw = os.environ.get("VPS_SSH_KEY", "")
    try:
        key = normalize(raw)
    except KeyError_ as exc:
        print(f"::error::VPS_SSH_KEY okunamadi: {exc}. Tani: {diagnose(raw)}")
        return 1
    fd = os.open(argv[1], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as handle:
        handle.write(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
