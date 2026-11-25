"""Ed25519 istek imzalama.

Imzalanan sey EXN-DATA'nin cozulmus baytlaridir; bu yuzden payload tek kez serilestirilir
ve ayni baytlar hem kodlanir hem imzalanir.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SIGN_VERSION = 1
_IDEMPOTENCY = re.compile(r"^[A-Za-z0-9._~-]{5,128}$")
_HEX = re.compile(r"^[0-9a-fA-F]+$")


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def b64url_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def body_hash(body: bytes) -> str:
    return b64url(hashlib.sha256(body).digest())


EMPTY_BODY_HASH = body_hash(b"")


def _raw_public(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def load_private_key(raw: str) -> Ed25519PrivateKey:
    """PEM (PKCS#8), 128 hex (tohum + acik anahtar), 64 hex veya base64/base64url 32 bayt kabul eder.

    Hata metinlerine anahtar materyali yazilmaz.
    """
    text = raw.strip().replace("\\n", "\n")
    if text.startswith("-----BEGIN"):
        try:
            key = serialization.load_pem_private_key(text.encode(), password=None)
        except (ValueError, TypeError) as exc:
            raise ValueError("ozel anahtar PEM olarak okunamadi") from None
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("Ed25519 ozel anahtari bekleniyordu")
        return key
    if _HEX.match(text) and len(text) in (64, 128):
        data = bytes.fromhex(text)
        key = Ed25519PrivateKey.from_private_bytes(data[:32])
        if len(data) == 64 and _raw_public(key) != data[32:]:
            raise ValueError("ozel anahtarin acik yarisi tohumla eslesmiyor")
        return key
    try:
        data = b64url_decode(text.replace("+", "-").replace("/", "_").rstrip("="))
    except (binascii.Error, ValueError):
        data = b""
    if len(data) == 32:
        return Ed25519PrivateKey.from_private_bytes(data)
    raise ValueError("ozel anahtar bicimi taninmadi (PEM, 128/64 hex veya base64 32 bayt)")


def sign_headers(*, method: str, path: str, body: bytes, api_key: str, key: Ed25519PrivateKey,
                 idempotency_key: str, timestamp_ms: int) -> dict[str, str]:
    method = method.upper()
    if not path.startswith("/"):
        raise ValueError("imzalanan path tam URL degil, '/' ile baslayan yol + sorgu olmali")
    if method == "GET":
        if idempotency_key != "":
            raise ValueError("GET isteklerinde idempotency key bos olmali")
    elif not _IDEMPOTENCY.match(idempotency_key):
        raise ValueError("degisiklik yapan istekler 5..128 karakterlik idempotency key ister")
    payload = json.dumps(
        {
            "api_key": api_key,
            "idempotency_key": idempotency_key,
            "timestamp": int(timestamp_ms),
            "sign_version": SIGN_VERSION,
            "method": method,
            "path": path,
            "body_hash": body_hash(body),
        },
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return {
        "EXN-API-KEY": api_key,
        "EXN-IDEMPOTENCY-KEY": idempotency_key,
        "EXN-TIMESTAMP": str(int(timestamp_ms)),
        "EXN-SIGN-VERSION": str(SIGN_VERSION),
        "EXN-DATA": b64url(payload),
        "EXN-SIGN": b64url(key.sign(payload)),
    }
