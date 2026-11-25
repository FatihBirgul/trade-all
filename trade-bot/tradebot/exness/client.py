"""Imzali REST istemcisi.

Bu katman hicbir istegi kendiliginden tekrarlamaz: 401/429/5xx tek bir net hataya donusur ve
karari cagiran verir (spec §7; 429 dongude denenmez, emirler cift gonderilmez).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

import httpx

from ..config import Settings
from . import schema
from .errors import ExnessAuthError, ExnessRateLimited, ExnessRejected, ExnessUnavailable
from .limits import RateLimiter
from .signing import load_private_key, sign_headers


class ExnessClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None, *,
                 clock: Callable[[], float] = time.time, limiter: RateLimiter | None = None,
                 timeout: float = 15.0):
        self.account_id = settings.exness_account_id
        self.limiter = limiter or RateLimiter()
        self._api_key = settings.exness_api_key.get_secret_value()
        self._key = load_private_key(settings.exness_private_key.get_secret_value())
        self._gateway = schema.base_url(settings.exness_gateway_host, allow_insecure_loopback=True)
        self._host = (schema.base_url(settings.exness_ap_host, allow_insecure_loopback=True)
                      if settings.exness_ap_host else None)
        self._clock = clock
        # Yonlendirme izlenmez: imzali basliklar baska bir hosta tasinmamali.
        self._http = httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=False)

    async def aclose(self) -> None:
        await self._http.aclose()

    def _headers(self, method: str, path: str, body: bytes, idempotency_key: str) -> dict[str, str]:
        return sign_headers(method=method, path=path, body=body, api_key=self._api_key, key=self._key,
                            idempotency_key=idempotency_key, timestamp_ms=int(self._clock() * 1000))

    async def resolve_host(self) -> str:
        """Hesabin Access Point taban URL'i; bir kez kesfedilir ve onbellekte tutulur."""
        if self._host is None:
            raw = await self._send(self._gateway, "GET", schema.access_point_path(self.account_id), None, "")
            try:
                self._host = schema.parse_access_point(raw)
            except ValueError as exc:
                raise ExnessUnavailable(f"access point kesfi basarisiz: {exc}") from None
        return self._host

    async def ws_endpoint(self, path: str) -> tuple[str, dict[str, str]]:
        """WebSocket el sikismasi GET olarak imzalanir; (url, basliklar) doner."""
        host = await self.resolve_host()
        return "ws" + host[len("http"):] + path, self._headers("GET", path, b"", "")

    async def get(self, path: str) -> dict:
        return await self._request("GET", path, None, "")

    async def post(self, path: str, payload: dict, idempotency_key: str) -> dict:
        return await self._request("POST", path, payload, idempotency_key)

    async def patch(self, path: str, payload: dict, idempotency_key: str) -> dict:
        return await self._request("PATCH", path, payload, idempotency_key)

    async def delete(self, path: str, idempotency_key: str) -> dict:
        return await self._request("DELETE", path, None, idempotency_key)

    async def _request(self, method: str, path: str, payload: dict | None, idempotency_key: str) -> dict:
        host = await self.resolve_host()
        await self.limiter.acquire(method, path)
        return await self._send(host, method, path, payload, idempotency_key)

    async def _send(self, host: str, method: str, path: str, payload: dict | None,
                    idempotency_key: str) -> dict:
        body = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = self._headers(method, path, body, idempotency_key)
        if payload is not None:
            headers["Content-Type"] = "application/json"
        request = self._http.build_request(method, host + path, content=body or None, headers=headers)
        if request.url.raw_path != path.encode("ascii", "strict"):
            # Imzalanan yol gonderilenle birebir ayni olmali; kacis gerektiren bir yol programlama hatasidir.
            raise ValueError("istek yolu URL kacisi gerektiriyor; imza ile uyusmaz")
        try:
            response = await self._http.send(request)
        except httpx.HTTPError as exc:
            raise ExnessUnavailable(f"ag hatasi: {type(exc).__name__}") from None
        return self._interpret(response)

    @staticmethod
    def _interpret(response: httpx.Response) -> dict:
        try:
            data: Any = response.json()
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            data = None
        status = response.status_code
        if 200 <= status < 300:
            if not isinstance(data, dict):
                raise ExnessUnavailable("beklenmeyen yanit govdesi", status=status)
            return data
        code, message = schema.parse_error(data)
        message = message or f"http {status}"
        if status == 429:
            retry_after = schema.parse_retry_after(data)
            header = response.headers.get("Retry-After")
            if header is not None:
                try:
                    retry_after = float(header)
                except ValueError:
                    pass
            raise ExnessRateLimited(message, retry_after=retry_after, code=code, status=status)
        if status == 401 or (code is not None and 1000 <= code < 2000):
            raise ExnessAuthError(message, code=code, status=status)
        if status >= 500:
            raise ExnessUnavailable(message, code=code, status=status)
        raise ExnessRejected(message, code=code, status=status)
