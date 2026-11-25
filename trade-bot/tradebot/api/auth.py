"""Cihaz eslestirme ve token dogrulama.

Eslestirme kodu sunucuda `python -m tradebot pair` ile uretilir (6 hane, 10 dakika, tek kullanim).
Token'in yalnizca SHA-256 ozeti saklanir; veritabani sizsa bile token elde edilemez.
"""

from __future__ import annotations

import hashlib
import secrets

from ..store.repo import Repo

PAIR_TTL = 600.0
MAX_PAIR_FAILURES = 5
_FAILURES = "pair_failures"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def issue_token(repo: Repo, *, now: float, label: str | None = None) -> str:
    token = secrets.token_urlsafe(32)
    repo.add_token(_hash(token), label, at=now)
    return token


def verify_token(repo: Repo, token: str | None) -> bool:
    return bool(token) and repo.has_token(_hash(token))


def create_pair_code(repo: Repo, *, now: float) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    repo.clear_pair_codes()  # ayni anda tek gecerli kod
    repo.add_pair_code(_hash(code), now + PAIR_TTL)
    repo.set_setting(_FAILURES, 0)
    return code


def redeem_pair_code(repo: Repo, code: str, *, now: float) -> str | None:
    """Gecerli kod icin token dondurur. Art arda hatali denemelerde bekleyen kodlar iptal edilir."""
    if repo.take_pair_code(_hash(code), now):
        repo.set_setting(_FAILURES, 0)
        return issue_token(repo, now=now, label="paired")
    failures = int(repo.get_setting(_FAILURES, 0)) + 1
    repo.set_setting(_FAILURES, failures)
    if failures >= MAX_PAIR_FAILURES:
        repo.clear_pair_codes()  # 6 haneli kod kaba kuvvetle denenemesin
    return None
