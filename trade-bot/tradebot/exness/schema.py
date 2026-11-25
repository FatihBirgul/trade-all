"""Exness API alan adlarinin gectigi TEK modul.

Baska hicbir modul ham API alan adi kullanmaz; kesif sonrasi duzeltmeler yalnizca burada yapilir.
(Imza basliklari `signing.py` icindedir; onlar protokolun parcasidir.)
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlsplit


def parse_error(raw: Any) -> tuple[int | None, str | None]:
    """Hata govdesi -> (kod, mesaj). Bicim taninmazsa (None, None)."""
    if not isinstance(raw, dict):
        return None, None
    code = raw.get("code")
    message = raw.get("error_message")
    return (code if isinstance(code, int) and not isinstance(code, bool) else None,
            message if isinstance(message, str) else None)


def parse_retry_after(raw: Any) -> float | None:
    if isinstance(raw, dict):
        value = raw.get("retry_after")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            return float(value)
    return None


def access_point_path(account_id: str) -> str:
    return f"/v1/trading/access-point?account_id={quote(str(account_id), safe='')}"


def parse_access_point(raw: Any) -> str:
    """Kesif yaniti -> 'https://host'. Guvensiz ya da bicimsiz deger ValueError verir."""
    value = raw.get("access_point") if isinstance(raw, dict) else None
    if not isinstance(value, str) or not value:
        raise ValueError("kesif yanitinda access point yok")
    return base_url(value)


def base_url(value: str, *, allow_insecure_loopback: bool = False) -> str:
    """Host ya da URL -> semali, yolsuz taban URL. Yalnizca https (yerel test icin loopback http)."""
    text = value.strip().rstrip("/")
    if "://" not in text:
        text = "https://" + text
    url = urlsplit(text)
    loopback = url.hostname in ("127.0.0.1", "localhost", "::1")
    if url.scheme != "https" and not (allow_insecure_loopback and loopback and url.scheme == "http"):
        raise ValueError("https taban URL bekleniyordu")
    if not url.hostname or url.username or url.password or url.path not in ("", "/") or url.query or url.fragment:
        raise ValueError("taban URL kimlik bilgisi, yol, sorgu ya da parca iceremez")
    return f"{url.scheme}://{url.netloc}"
