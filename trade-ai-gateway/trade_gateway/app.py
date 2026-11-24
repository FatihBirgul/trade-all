import asyncio
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from .contract import route, validate, query_parameters
from .store import AuthStore

BACKEND = "http://127.0.0.1:8002"
MAX_BODY, MAX_RESPONSE = 16384, 2_000_000
PUBLIC_ERRORS = {"DISCOVERY_ACTIVATION_BLOCKED","DISCOVERY_REVISION_CONFLICT","DISCOVERY_LIMIT","DISCOVERY_STALE_JOB","OPPORTUNITY_NOT_FOUND","RESEARCH_UNAVAILABLE","RESEARCH_SOURCE_MISMATCH","INVALID_RESEARCH_PARAMETERS","INVALID_RESEARCH_ANCHOR","NOTIFICATION_REVISION_CONFLICT","NOTIFICATION_HISTORY_LIMIT","PROFILE_NOT_FOUND", "PROFILE_REVISION_CONFLICT", "PROFILE_VERSION_UNAVAILABLE", "PROFILE_HISTORY_LIMIT", "PROFILE_TIMEFRAME_MISMATCH", "VALIDATION_ERROR", "ANALYSIS_NOT_FOUND", "CANDLE_SNAPSHOT_UNAVAILABLE", "IDEMPOTENCY_CONFLICT", "V2_VALIDATION_ERROR", "PAPER_RECOVERY_IN_PROGRESS", "SCANNER_BUSY", "STORAGE_CORRUPT", "QUOTE_PROVIDER_UNAVAILABLE", "QUOTE_BUSY", "TRACKING_NOT_FOUND", "TRACKING_ALREADY_ACTIVE", "TRACKING_LIMIT"}


@dataclass(repr=False)
class Settings:
    public_origin: str
    backend_token: str = field(repr=False)
    database: Path = Path("local_data/gateway.sqlite")
    timeout: float = 10.0
    # Injectable only from Python tests, never exposed by the production CLI.
    expected_mode: str = "live"
    # Deliberately absent from CLI/env: requires a separately reviewed device release.
    paper_writes_enabled: bool = False
    scanner_timeout: float = 45.0

    def __post_init__(self):
        u = urlsplit(self.public_origin)
        if u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ("", "/") or u.port not in (None, 443):
            raise ValueError("A root HTTPS origin is required")
        if len(self.backend_token) < 24 or re.search(r"[\r\n]", self.backend_token):
            raise ValueError("A private backend token is required")
        self.public_origin = "https://" + u.hostname
        self.host = u.hostname


def error(status, code, message):
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def create_app(settings: Settings, *, backend_transport=None, clock=None):
    store = AuthStore(settings.database, **({"clock": clock} if clock else {}))
    # Never use environment proxy settings for the privileged loopback connection.
    client = httpx.AsyncClient(base_url=BACKEND, timeout=settings.timeout, trust_env=False,
        follow_redirects=False, transport=backend_transport)
    slots = asyncio.Semaphore(2)
    @asynccontextmanager
    async def lifespan(app):
        yield
        await client.aclose()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.auth = store
    app.state.backend_client = client

    @app.middleware("http")
    async def boundary(request: Request, call_next):
        try:
            # TLS is terminated by Serve. Only a local reverse proxy can reach the listener.
            if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
                return error(403, "PRIVATE_NETWORK_REQUIRED", "Özel HTTPS bağlantısı gerekli.")
            if request.headers.get("host", "").lower() not in (settings.host, settings.host+":443"):
                return error(400, "INVALID_HOST", "Gateway adresi doğrulanamadı.")
            if request.headers.get("x-forwarded-proto", "https") != "https":
                return error(403, "HTTPS_REQUIRED", "HTTPS bağlantısı gerekli.")
            if request.headers.get("origin") not in (None, settings.public_origin):
                return error(403, "ORIGIN_DENIED", "Bu kaynaktan erişime izin verilmedi.")
            if not store.permit("all", 240):
                return error(429, "RATE_LIMITED", "İstek sınırı aşıldı. Biraz bekleyin.")
            if request.method not in ("GET", "POST") or "%" in request.scope.get("raw_path", b"").decode("ascii", "replace") or "//" in request.url.path:
                return error(403, "ENDPOINT_DENIED", "Bu işleme izin verilmedi.")
            body = bytearray()
            async with asyncio.timeout(5):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > MAX_BODY:
                        return error(413, "REQUEST_TOO_LARGE", "İstek boyutu sınırı aşıldı.")
            request._body = bytes(body)
            response = await call_next(request)
        except Exception:
            # No request body, credential, exception string or privileged URL is logged.
            response = error(500, "GATEWAY_INTERNAL", "Gateway isteği tamamlayamadı.")
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def authenticated(request):
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Bearer ") or len(authorization) > 256:
            return None
        return store.session(authorization[7:])

    @app.post("/gateway/pair")
    async def pair(request: Request):
        if not store.permit("pair", 5):
            return error(429, "RATE_LIMITED", "Eşleştirme deneme sınırı aşıldı.")
        try:
            body = await request.json()
            renewal = body.pop("renewal", False) if isinstance(body, dict) else False
            if type(renewal) is not bool or set(body) != {"code", "device_id", "device_name"} or not all(isinstance(v, str) for v in body.values()):
                raise ValueError()
            if not re.fullmatch(r"[A-Za-z0-9_-]{32}", body["code"]) or not re.fullmatch(r"[a-f0-9-]{36}", body["device_id"]) or not 1 <= len(body["device_name"]) <= 60 or any(ord(c) < 32 for c in body["device_name"]):
                raise ValueError()
            result = store.exchange(body["code"], body["device_id"], body["device_name"])
            if result and renewal:
                result["refresh_token"] = store.grant_renewal(result["session"])
                result.update(store.session(result["session"]))
            return JSONResponse(result) if result else error(401, "PAIRING_INVALID", "Eşleştirme kodu geçersiz veya süresi dolmuş.")
        except (ValueError, TypeError):
            return error(422, "INVALID_PAIRING", "Eşleştirme alanları geçersiz.")

    @app.post("/gateway/refresh")
    async def refresh(request: Request):
        if not store.permit("refresh", 20):
            return error(429, "RATE_LIMITED", "Yenileme sınırı aşıldı. Biraz bekleyin.")
        try:
            body=await request.json()
            if not isinstance(body,dict) or set(body)!={"refresh_token","next_refresh_token","next_session","device_id","request_id"}: raise ValueError()
            for key,prefix in [("refresh_token","tr_"),("next_refresh_token","tr_"),("next_session","tg_"),("request_id","rq_")]:
                if not isinstance(body[key],str) or not re.fullmatch(prefix+r"[A-Za-z0-9_-]{43}",body[key]): raise ValueError()
            if not isinstance(body["device_id"],str) or not re.fullmatch(r"[a-f0-9-]{36}",body["device_id"]): raise ValueError()
            result=store.rotate(body)
            return JSONResponse(result) if result else error(401,"RENEWAL_REJECTED","Yenileme yetkisi geçersiz, iptal edilmiş veya süresi dolmuş. Bilgisayardan yeniden eşleştirin.")
        except (ValueError,TypeError):
            return error(422,"INVALID_RENEWAL","Yenileme isteği geçersiz.")

    @app.get("/gateway/session")
    async def session(request: Request):
        current = authenticated(request)
        return JSONResponse(current) if current else error(401, "UNAUTHORIZED", "Mobil oturum geçersiz, iptal edilmiş veya süresi dolmuş.")

    @app.api_route("/api/v2/{path:path}", methods=["GET", "POST"])
    async def proxy(path: str, request: Request):
        current = authenticated(request)
        if not current:
            return error(401, "UNAUTHORIZED", "Mobil oturum geçersiz, iptal edilmiş veya süresi dolmuş.")
        operation, params = route(request.url.path, request.method, settings.paper_writes_enabled)
        if operation is None:
            return error(403, "ENDPOINT_DENIED", "Bu endpoint mobil istemciye kapalı.")
        if (path == "notifications" and len(current["accounts"]) != 2) or ((path.startswith("scanner") or path == "watchlist") and request.method == "POST" and "AUTO" not in current["accounts"]):
            return error(403, "SCOPE_DENIED", "Bu işlem AUTO hesap kapsamı gerektirir.")
        scope = "read" if request.method == "GET" or path.endswith("/research") or path.endswith("/evaluate") and "strategy-profiles/" in path else "notifications:write" if path.endswith("/notification-preferences") else "profiles:write" if "strategy-profiles" in path else "discovery:write" if "/market-scanner" in path else "paper:write" if path.startswith("portfolios/") else "analyze" if path == "analyze" else "scanner:write"
        if scope not in current["scopes"] or params.get("portfolio_id", current["accounts"][0]) not in current["accounts"]:
            return error(403, "SCOPE_DENIED", "Oturumun bu işlem için yetkisi yok.")
        if not store.permit(current["session_id"]+":"+scope, 6 if scope == "analyze" else 60):
            return error(429, "RATE_LIMITED", "İstek sınırı aşıldı. Biraz bekleyin.")
        try:
            query = query_parameters(operation, request.query_params)
            body = None
            if request.method == "POST":
                raw = await request.body()
                body = json.loads(raw) if raw else None
                if path in ("analyze", "watchlist"):
                    if not isinstance(body, dict):
                        raise ValueError()
                    body["auto_paper"] = False
                if path == "analyze":
                    if body.get("data_mode", "live") != settings.expected_mode or body.get("risk_portfolio", "AUTO") not in current["accounts"]:
                        raise ValueError()
                schema = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
                if schema:
                    validate(schema, body)
                elif body is not None:
                    raise ValueError()
        except Exception:
            return error(422, "INVALID_REQUEST", "İstek alanları veya hesap kapsamı geçersiz.")
        try:
            deadline = settings.scanner_timeout if path == "scanner/tick" or path.endswith("/market-scanner/tick") else settings.timeout
            async with asyncio.timeout(deadline):
                async with slots:
                    # A local PC may already have AUTO watches. A mobile tick must
                    # never activate those orders, even though mobile watch writes
                    # themselves always force auto_paper=false.
                    if path == "scanner/tick":
                        async with client.stream("GET", "/api/v2/watchlist", headers={"Authorization": "Bearer " + settings.backend_token}) as watches_response:
                            watch_bytes = bytearray()
                            async for chunk in watches_response.aiter_bytes():
                                watch_bytes.extend(chunk)
                                if len(watch_bytes) > MAX_RESPONSE: raise ValueError()
                            if watches_response.status_code != 200: raise ValueError()
                            watches = json.loads(watch_bytes)
                        watch_operation, _ = route("/api/v2/watchlist", "GET")
                        validate(watch_operation["responses"]["200"]["content"]["application/json"]["schema"], watches)
                        if any(w.get("enabled", True) and w.get("auto_paper", False) for w in watches):
                            return error(409, "SCANNER_AUTO_PAPER_DISABLED", "Bilgisayardaki otomatik emirli izleme kaydını kapatmadan mobil tarama başlatılamaz.")
                    if (path.endswith("/candles") and len(current["accounts"]) != 2) or path.endswith("/research") or (scope == "paper:write" and path.endswith("/orders")) or (path == "analysis-tracking" and request.method == "POST"):
                        async with client.stream("GET", "/api/v2/analyses/" + (body["analysis_id"] if scope == "paper:write" or path == "analysis-tracking" else params["analysis_id"]), headers={"Authorization": "Bearer " + settings.backend_token}) as parent_response:
                            parent_bytes = bytearray()
                            async for chunk in parent_response.aiter_bytes():
                                parent_bytes.extend(chunk)
                                if len(parent_bytes) > MAX_RESPONSE: raise ValueError()
                            if parent_response.status_code == 404:
                                return error(404,"ANALYSIS_NOT_FOUND","Analiz kaydı bulunamadı.")
                            if parent_response.status_code != 200: raise ValueError()
                            parent = json.loads(parent_bytes)
                        validate({"$ref": "#/components/schemas/AnalysisResponse"}, parent)
                        if parent["data_mode"] != settings.expected_mode: raise ValueError()
                        if parent["analysis_id"] != (body["analysis_id"] if path == "analysis-tracking" or scope == "paper:write" else params["analysis_id"]): raise ValueError()
                        if parent["risk_portfolio"] not in current["accounts"] or (scope == "paper:write" and parent["risk_portfolio"] != params["portfolio_id"]):
                            return error(403, "SCOPE_DENIED", "Bu analiz oturumun hesap kapsamı dışında.")
                    if "tracking_id" in params and request.method == "POST":
                        async with client.stream("GET", "/api/v2/analysis-tracking/"+params["tracking_id"], headers={"Authorization":"Bearer "+settings.backend_token}) as prior_response:
                            prior_bytes=bytearray()
                            async for chunk in prior_response.aiter_bytes():
                                prior_bytes.extend(chunk)
                                if len(prior_bytes)>MAX_RESPONSE: raise ValueError()
                            if prior_response.status_code==404:
                                return error(404,"TRACKING_NOT_FOUND","Takip kaydı bulunamadı veya backend güncellemesi gerekli.")
                            if prior_response.status_code!=200: raise ValueError()
                            prior=json.loads(prior_bytes)
                        validate({"$ref":"#/components/schemas/TrackingResponse"},prior)
                        if prior["data_mode"] != settings.expected_mode or prior["tracking_id"] != params["tracking_id"]: raise ValueError()
                        if prior["portfolio_id"] not in current["accounts"]:
                            return error(403,"SCOPE_DENIED","Takip kaydı bu oturumun hesap kapsamı dışında.")
                    if authenticated(request) is None:
                        return error(401, "UNAUTHORIZED", "Mobil oturum sonlandırıldı.")
                    upstream_headers={"Authorization":"Bearer "+settings.backend_token,"Accept":"application/json"}
                    if path.endswith('/notification-preferences'):
                        from .store import digest
                        principal=current.get('renewal_id') or current['session_id']
                        upstream_headers.update({'X-V2-Notification-Owner':digest('v2-notification-owner:'+principal),'X-V2-Recipient-Expires':str(current['expires_at_ms'])})
                    async with client.stream(request.method, request.url.path, params=query, timeout=deadline,
                        headers=upstream_headers,
                        **({"json": body} if body is not None else {})) as upstream:
                        data = bytearray()
                        async for chunk in upstream.aiter_bytes():
                            data.extend(chunk)
                            if len(data) > MAX_RESPONSE:
                                raise ValueError()
                        if settings.backend_token.encode() in data:
                            raise ValueError()
                        payload = json.loads(data, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                        status = upstream.status_code
            if status != 200:
                if status == 404 and (path == "quotes" or path.endswith(("/equity-history","/equity-history-window","/research")) or "strategy-profiles" in path or path.startswith("analysis-tracking") or path.endswith("/notification-preferences") or "/market-scanner" in path or "/opportunities" in path) and payload.get("error",{}).get("code") not in PUBLIC_ERRORS:
                    return error(404,"BACKEND_UPDATE_REQUIRED","Bu özellik için bilgisayardaki backend güncellemesi gerekli.")
                if status in (401, 403):
                    return error(503, "BACKEND_AUTH_FAILED", "Backend yetkisi doğrulanamadı; bilgisayardaki yapılandırmayı kontrol edin.")
                code = payload.get("error", {}).get("code") if isinstance(payload, dict) else None
                return error(status if status in (404, 409, 422, 429, 503) else 502,
                    code if code in PUBLIC_ERRORS else "BACKEND_UNAVAILABLE", "Backend isteği tamamlamadı. Durumu kontrol edin.")
            validate(operation["responses"]["200"]["content"]["application/json"]["schema"], payload)
            if path == "analyses":
                payload = [row for row in payload if row["risk_portfolio"] in current["accounts"]]
            if path == "watchlist" and isinstance(payload,list) and "AUTO" not in current["accounts"]:
                payload = [row for row in payload if not row.get("profile_id")]
            if path in ("portfolios", "analysis-tracking") and isinstance(payload,list):
                payload = [row for row in payload if row["portfolio_id"] in current["accounts"]]
            if path == "performance":
                payload["portfolios"] = [row for row in payload["portfolios"] if row.get("portfolio_id") in current["accounts"]]
            if path == "health" and payload.get("real_execution") is not False:
                raise ValueError()
            rows = payload if isinstance(payload, list) else [payload]
            for row in rows:
                if "risk_portfolio" in row and row["risk_portfolio"] not in current["accounts"]:
                    return error(403, "SCOPE_DENIED", "Bu analiz oturumun hesap kapsamı dışında.")
                if "data_mode" in row and row["data_mode"] != settings.expected_mode:
                    raise ValueError()
                if row.get("real_execution", False) is not False or row.get("paper_only", True) is not True:
                    raise ValueError()
                if "portfolio_id" in row and row["portfolio_id"] not in current["accounts"]:
                    return error(403,"SCOPE_DENIED","Bu kayıt oturumun hesap kapsamı dışında.")
                if "portfolio_id" in row and params.get("portfolio_id", row["portfolio_id"]) != row["portfolio_id"]:
                    raise ValueError()
            if path.endswith(('/equity-history','/equity-history-window')) and any(point['portfolio_id']!=params['portfolio_id'] or point['data_mode']!=settings.expected_mode for point in payload['points']):
                raise ValueError()
            if "/opportunities" in path:
                entries=payload.get('items',[payload.get('opportunity')])
                if any(not isinstance(o,dict) or o['portfolio_id']!=params['portfolio_id'] or o['trade_permission'] is not False for o in entries):raise ValueError()
                if 'opportunity_id' in params and payload['opportunity']['opportunity_id']!=params['opportunity_id']:raise ValueError()
                if any(e.get('portfolio_id')!=params['portfolio_id'] or e.get('opportunity_id')!=params['opportunity_id'] or e.get('trade_permission') is not False for e in payload.get('events',[])):raise ValueError()
            if "/market-scanner" in path:
                if payload.get('config',{}).get('portfolio_id',params['portfolio_id'])!=params['portfolio_id']:raise ValueError()
                if any(j.get('portfolio_id')!=params['portfolio_id'] for j in payload.get('jobs',[])):raise ValueError()
            if path == "analyze" and (payload["risk_portfolio"] != body.get("risk_portfolio", "AUTO") or payload["symbol"] != body.get("symbol", "BTCUSDT")):
                raise ValueError()
            if path == "analyze" and body.get("profile_id") and payload.get("technical_methods",{}).get("profile_control",{}).get("profile_record_id") != body["profile_id"]:
                raise ValueError()
            if "analysis_id" in params and payload.get("analysis_id") != params["analysis_id"]:
                raise ValueError()
            if path.endswith('/research'):
                if payload['portfolio_id']!=parent['risk_portfolio'] or payload['symbol']!=parent['symbol'] or payload['as_of_ms']!=parent['created_at_ms']:raise ValueError()
                if request.method=='POST' and (payload['source_record_id']!=body['source_record_id'] or payload['symbol']!=body['symbol'] or payload['timeframe']!=body['timeframe']):raise ValueError()
            if path == "analysis-tracking" and request.method == "POST" and payload.get("origin_analysis_id") != body["analysis_id"]:
                raise ValueError()
            if "tracking_id" in params and payload.get("tracking_id") != params["tracking_id"]:
                raise ValueError()
            if "order_id" in params and payload.get("order_id") != params["order_id"]:
                raise ValueError()
            if "position_id" in params and payload.get("position_id") != params["position_id"]:
                raise ValueError()
            # Recheck expiry/revocation after an upstream request has completed.
            if authenticated(request) is None:
                return error(401, "UNAUTHORIZED", "Mobil oturum sonlandırıldı.")
            return JSONResponse(payload)
        except (httpx.TimeoutException, TimeoutError):
            return error(504, "UPSTREAM_TIMEOUT", "Backend yanıt süresi aşıldı. Yeni anahtarla tekrar göndermeyin.")
        except httpx.HTTPError:
            return error(503, "BACKEND_UNAVAILABLE", "Backend bağlantısı kurulamadı.")
        except Exception:
            return error(502, "INVALID_RESPONSE", "Backend yanıtı doğrulanamadı.")
    return app
