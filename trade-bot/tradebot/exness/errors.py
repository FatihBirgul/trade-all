"""Exness istemci hatalari. Hicbiri istek basliklarini ya da sirlari tasimaz."""

from __future__ import annotations


class ExnessError(Exception):
    def __init__(self, message: str, *, code: int | None = None, status: int | None = None):
        super().__init__(message if code is None else f"{message} (kod {code})")
        self.message = message
        self.code = code
        self.status = status


class ExnessAuthError(ExnessError):
    """Anahtar, imza ya da yetki reddi (1000-1999). Tekrar denemek anlamsizdir."""


class ExnessRateLimited(ExnessError):
    """429. Otomatik tekrar yok; cagiran limitleri yenileyip bekler."""

    def __init__(self, message: str, *, retry_after: float | None = None, code: int | None = None,
                 status: int | None = 429):
        super().__init__(message, code=code, status=status)
        self.retry_after = retry_after


class ExnessRejected(ExnessError):
    """Istek bicimi ya da is kurali reddi. Ayni istek tekrarlanmamali."""


class ExnessUnavailable(ExnessError):
    """Ag hatasi ya da 5xx. Yalnizca tekrarlanmasi guvenli islemler yeniden denenebilir."""
