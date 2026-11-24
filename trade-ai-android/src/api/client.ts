import { gatewayOrigin } from "../domain/safety";
import type { components } from "./schema";
import { validateResponse } from "./validate";
type Models = components["schemas"];
export class ApiError extends Error {
  constructor(
    public code: string,
    public uncertain = false,
    public status = 0,
  ) {
    super(
      code === "BACKEND_UPDATE_REQUIRED"
        ? "Bu özellik için PC’de backend’i güncelleyin ve yeniden başlatın."
        : code === "TRACKING_LIMIT"
          ? "Takip sınırına ulaşıldı. Aynı anda en çok altı aktif takip olabilir."
          : code === "TRACKING_ALREADY_ACTIVE"
            ? "Bu market, zaman dilimi ve hesap zaten takip ediliyor."
            : code === "QUOTE_PROVIDER_UNAVAILABLE"
              ? "Piyasa veri kaynağına ulaşılamıyor. Gerçek fiyat yerine örnek değer gösterilmedi."
              : code === "QUOTE_BUSY"
                ? "Piyasa verisi isteği sürüyor. Biraz bekleyin."
                : code === "RENEWAL_IN_PROGRESS"
                  ? "Oturum zaten yenileniyor. Tamamlanmasını bekleyin."
                  : code === "LOCAL_PAIR_REQUIRED"
                    ? "Yenileme yetkisi süresi dolmuş veya iptal edilmiş. Bilgisayardan yeniden eşleştirin."
                    : code === "RENEWAL_UNCERTAIN"
                      ? "Oturum yenileme yanıtı alınamadı. Yeniden bağlan ile aynı güvenli isteği uzlaştırın; yeni kod gerekmeyebilir."
                      : uncertain
                        ? "İşlemin sonucu belirsiz. Durumu kontrol edin; yeni işlem göndermeyin."
                        : code === "UNCONFIGURED"
                          ? "HTTPS gateway ve mobil oturum yapılandırılmadı."
                          : code === "PAPER_WRITES_DISABLED"
                            ? "Sanal işlem yazma işlevleri cihaz doğrulaması tamamlanana kadar kapalı."
                            : code === "SCANNER_AUTO_PAPER_DISABLED"
                              ? "Bilgisayardaki otomatik emirli izleme kaydını kapatmadan mobil tarama başlatılamaz."
                              : code === "NETWORK"
                                ? "Gateway bağlantısı kurulamadı. Telefon ağı, özel ağ veya PC/Gateway erişimi doğrulanamadı."
                                : code === "UNAUTHORIZED"
                                  ? "Mobil oturum geçersiz veya süresi dolmuş."
                                  : code === "SCOPE_DENIED"
                                    ? "Mobil oturumun bu işlem veya hesap için yetkisi yok."
                                    : code === "SESSION_CHANGED"
                                      ? "Oturum değişti. Eski istek sonucu gösterilmedi."
                                      : code === "BACKEND_AUTH_FAILED"
                                        ? "Bilgisayardaki backend yetkisi doğrulanamadı. Gateway yapılandırmasını kontrol edin."
                                        : code === "UPSTREAM_TIMEOUT"
                                          ? "Analiz sunucusunun yanıt süresi aşıldı. Aynı istek anahtarını koruyun."
                                          : code === "BACKEND_UNAVAILABLE"
                                            ? "Bilgisayardaki analiz sunucusuna ulaşılamıyor. Backend’in açık olduğunu kontrol edin."
                                            : code === "RATE_LIMITED"
                                              ? "İstek sınırına ulaşıldı. Biraz bekleyip yeniden deneyin."
                                              : code ===
                                                  "CANDLE_SNAPSHOT_UNAVAILABLE"
                                                ? "Bu analiz için doğrulanmış mum kaydı yok. Yeni fiyatlarla değiştirilmedi."
                                                : code === "INVALID_RESPONSE"
                                                  ? "Sunucu yanıtı doğrulanamadı. Yeniden bağlantı testi yapın."
                                                  : code === "HTTP_429"
                                                    ? "Çok fazla istek gönderildi. Biraz bekleyip yeniden deneyin."
                                                    : code.startsWith("HTTP_5")
                                                      ? "Sunucuya şu anda ulaşılamıyor. Daha sonra yeniden deneyin."
                                                      : "İstek tamamlanamadı. Hata kodu: " +
                                                        code,
    );
    this.name = "ApiError";
  }
}
export type GatewayConfig = {
  origin: string;
  session: string;
  refresh?: string;
  lastVerifiedAt?: number;
  deviceId?: string;
  renewalExpiresAt?: number;
  scopes?: string[];
  accounts?: ("AUTO" | "MANUAL")[];
  pendingRenewal?: { requestId: string; session: string; refresh: string };
};
function validResearchTimes(r: Models["SnapshotResearchResponse"]): boolean {
  const anchors = r.anchors;
  const utc = (v: number) =>
    Number.isSafeInteger(v) && v >= 0 && v <= 253402300799999;
  return (
    utc(r.as_of_ms) &&
    Array.isArray(anchors) &&
    anchors.length <= 300 &&
    anchors.every(
      (a, i) =>
        utc(a.open_time_ms) &&
        utc(a.close_time_ms) &&
        a.open_time_ms < a.close_time_ms &&
        a.close_time_ms <= r.as_of_ms &&
        (i === 0 || a.open_time_ms >= anchors[i - 1].close_time_ms),
    )
  );
}
export function createApi(
  config: GatewayConfig,
  transport: typeof fetch = fetch,
  onUnauthorized?: () => void,
  features: {
    paperWritesEnabled?: boolean;
    profileScannerEnabled?: boolean;
  } = {},
) {
  const controllers = new Set<AbortController>();
  let generation = 0;
  const reads = new Map<string, Promise<unknown>>();
  async function performRequest<T>(
    path: string,
    method = "GET",
    body?: unknown,
    timeoutMs = 15000,
  ): Promise<T> {
    const requestGeneration = generation;
    if (
      method !== "GET" &&
      path.includes("/strategy-profiles") &&
      !path.endsWith("/evaluate") &&
      !config.scopes?.includes("profiles:write")
    )
      throw new ApiError("SCOPE_DENIED");
    if (
      method !== "GET" &&
      path.startsWith("/portfolios/") &&
      !path.includes("/strategy-profiles") &&
      !path.endsWith("/notification-preferences") &&
      !path.includes("/market-scanner") &&
      !features.paperWritesEnabled
    )
      throw new ApiError("PAPER_WRITES_DISABLED");
    if (
      method !== "GET" &&
      path.endsWith("/notification-preferences") &&
      !config.scopes?.includes("notifications:write")
    )
      throw new ApiError("SCOPE_DENIED");
    if (
      method !== "GET" &&
      path.includes("/market-scanner") &&
      !config.scopes?.includes("discovery:write")
    )
      throw new ApiError("SCOPE_DENIED");
    if (!config.origin || !config.session.trim())
      throw new ApiError("UNCONFIGURED");
    const origin = gatewayOrigin(config.origin);
    const controller = new AbortController();
    controllers.add(controller);
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await transport(origin + "/api/v2" + path, {
        method,
        signal: controller.signal,
        redirect: "error",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          Authorization: "Bearer " + config.session,
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      if (requestGeneration !== generation)
        throw new ApiError("SESSION_CHANGED");
      if (!response.ok) {
        if (response.status === 401) onUnauthorized?.();
        let code = "HTTP_" + response.status;
        try {
          const payload = await response.json();
          if (
            typeof payload?.error?.code === "string" &&
            /^[A-Z0-9_]{1,64}$/.test(payload.error.code)
          )
            code = payload.error.code;
        } catch {}
        if (response.status === 401) code = "UNAUTHORIZED";
        throw new ApiError(
          code,
          method !== "GET" && response.status >= 500,
          response.status,
        );
      }
      try {
        const payload: unknown = await response.json();
        if (requestGeneration !== generation || controller.signal.aborted)
          throw new ApiError("SESSION_CHANGED");
        if (!validateResponse(path, method, payload))
          throw new Error("Response contract mismatch");
        const record = payload as Models["AnalysisResponse"];
        if (
          path.startsWith("/analyses/") &&
          path.split("/").length === 3 &&
          record.analysis_id !== decodeURIComponent(path.split("/")[2])
        )
          throw new Error("Analysis identity mismatch");
        const account = /^\/portfolios\/(AUTO|MANUAL)(?:\/|$)/.exec(path)?.[1];
        if (
          account &&
          (Array.isArray(payload)
            ? payload.some((row) => row.portfolio_id !== account)
            : "portfolio_id" in (payload as object)
              ? (payload as Models["PortfolioResponse"]).portfolio_id !==
                account
              : !path.endsWith("/close"))
        )
          throw new Error("Account mismatch");
        if (
          path === "/analyze" &&
          (payload as Models["AnalysisResponse"]).risk_portfolio !==
            ((body as Models["AnalyzeRequest"]).risk_portfolio ?? "AUTO")
        )
          throw new Error("Risk account mismatch");
        if (path.includes("/opportunities")) {
          const value = payload as Models["OpportunityList"] &
            Models["OpportunityDetail"];
          const entries = value.items ?? [value.opportunity];
          if (
            value.data_mode !== "live" ||
            entries.some(
              (o) =>
                o.portfolio_id !== account ||
                o.trade_permission !== false ||
                ![
                  o.first_known_ms,
                  o.expires_at_ms,
                  o.last_observed_ms,
                  o.last_source_ms,
                ].every(
                  (t) =>
                    Number.isSafeInteger(t) && t >= 0 && t <= 253402300799999,
                ),
            )
          )
            throw new Error("Opportunity account/source mismatch");
          const id = /\/opportunities\/([^/?]+)/.exec(path)?.[1];
          if (id && value.opportunity.opportunity_id !== decodeURIComponent(id))
            throw new Error("Opportunity identity mismatch");
          if (
            value.events?.some(
              (e) => e.portfolio_id !== account || e.opportunity_id !== id,
            )
          )
            throw new Error("Opportunity event mismatch");
        }
        if (
          path.includes("/market-scanner") &&
          (payload as Models["DiscoveryView"]).data_mode !== "live"
        )
          throw new Error("Discovery mode mismatch");
        if (path === "/analyze") {
          const expected = body as Models["AnalyzeRequest"];
          const control = record.technical_methods?.profile_control as
            { profile_record_id?: unknown } | undefined;
          if (
            expected.profile_id &&
            control?.profile_record_id !== expected.profile_id
          )
            throw new Error("Profile analysis binding mismatch");
          if (
            record.symbol !== (expected.symbol ?? "BTCUSDT") ||
            record.timeframe !== (expected.timeframe ?? "1H")
          )
            throw new Error("Analysis selection mismatch");
        }
        if (
          path === "/analysis-tracking" &&
          method === "POST" &&
          (payload as Models["TrackingResponse"]).origin_analysis_id !==
            (body as Models["TrackingCreate"]).analysis_id
        )
          throw new Error("Follow origin identity mismatch");
        const trackingId =
          /^\/analysis-tracking\/([^/]+)(?:\/notification-policy)?$/.exec(
            path,
          )?.[1];
        if (
          trackingId &&
          (payload as Models["TrackingResponse"]).tracking_id !==
            decodeURIComponent(trackingId)
        )
          throw new Error("Follow identity mismatch");
        if (/\/equity-history(?:-window)?$/.test(path.split("?")[0])) {
          const history = payload as Models["EquityHistoryResponse"];
          if (
            history.points.some(
              (p) =>
                p.portfolio_id !== account ||
                p.data_mode !== "live" ||
                ![p.recorded_at_ms, p.effective_at_ms].every(
                  (t) =>
                    Number.isSafeInteger(t) && t >= 0 && t <= 253402300799999,
                ),
            )
          )
            throw new Error("Equity history account/mode mismatch");
        }
        if (
          path.endsWith("/notification-preferences") &&
          (payload as Models["NoticePreferences"]).data_mode !== "live"
        )
          throw new Error("Notification mode mismatch");
        const profileId = /\/strategy-profiles\/([a-f0-9]{64})$/.exec(
          path,
        )?.[1];
        if (
          profileId &&
          (payload as Models["ProfileRecord"]).profile_id !== profileId
        )
          throw new Error("Profile identity mismatch");
        const closeId = /\/positions\/([^/]+)\/close$/.exec(path)?.[1];
        const cancelId = /\/orders\/([^/]+)\/cancel$/.exec(path)?.[1];
        if (
          closeId &&
          (payload as Models["CloseResult"]).position_id !== closeId
        )
          throw new Error("Position identity mismatch");
        if (
          cancelId &&
          (payload as Models["OrderResponse"]).order_id !== cancelId
        )
          throw new Error("Order identity mismatch");
        return payload as T;
      } catch (error) {
        if (error instanceof ApiError) throw error;
        throw new ApiError("INVALID_RESPONSE", method !== "GET");
      }
    } catch (error) {
      if (requestGeneration !== generation)
        throw new ApiError("SESSION_CHANGED");
      if (error instanceof ApiError) throw error;
      throw new ApiError("NETWORK", method !== "GET");
    } finally {
      clearTimeout(timeout);
      controllers.delete(controller);
    }
  }
  function request<T>(
    path: string,
    method = "GET",
    body?: unknown,
    timeoutMs = 15000,
  ): Promise<T> {
    if (method !== "GET")
      return performRequest<T>(path, method, body, timeoutMs);
    const existing = reads.get(path);
    if (existing) return existing as Promise<T>;
    const pending = performRequest<T>(path, method, body, timeoutMs).finally(
      () => {
        if (reads.get(path) === pending) reads.delete(path);
      },
    );
    reads.set(path, pending);
    return pending;
  }
  return {
    dispose: () => {
      generation += 1;
      controllers.forEach((c) => c.abort());
      controllers.clear();
      reads.clear();
    },
    marketScanner: (account: "AUTO" | "MANUAL") =>
      request<Models["DiscoveryView"]>(
        "/portfolios/" + account + "/market-scanner",
      ),
    configureMarketScanner: (
      account: "AUTO" | "MANUAL",
      body: Models["DiscoveryWrite"],
    ) =>
      request<Models["DiscoveryReceipt"]>(
        "/portfolios/" + account + "/market-scanner",
        "POST",
        body,
      ),
    marketScannerTick: (account: "AUTO" | "MANUAL") =>
      request<Models["DiscoveryTick"]>(
        "/portfolios/" + account + "/market-scanner/tick",
        "POST",
        undefined,
        45000,
      ),
    opportunities: (account: "AUTO" | "MANUAL", offset = 0) =>
      request<Models["OpportunityList"]>(
        "/portfolios/" + account + "/opportunities?limit=20&offset=" + offset,
      ),
    opportunity: (account: "AUTO" | "MANUAL", id: string) =>
      request<Models["OpportunityDetail"]>(
        "/portfolios/" + account + "/opportunities/" + encodeURIComponent(id),
      ),
    strategyCapabilities: () =>
      request<Record<string, unknown>>("/strategy-capabilities"),
    profiles: (account: "AUTO" | "MANUAL", offset = 0) =>
      request<Models["ProfileRecord"][]>(
        "/portfolios/" +
          account +
          "/strategy-profiles?limit=20&offset=" +
          offset,
      ),
    profile: (account: "AUTO" | "MANUAL", id: string) =>
      request<Models["ProfileRecord"]>(
        "/portfolios/" +
          account +
          "/strategy-profiles/" +
          encodeURIComponent(id),
      ),
    saveProfile: (
      account: "AUTO" | "MANUAL",
      body: Models["ProfileWrite"],
      parent?: string,
    ) =>
      request<Models["ProfileRecord"]>(
        "/portfolios/" +
          account +
          "/strategy-profiles" +
          (parent ? "/" + encodeURIComponent(parent) + "/revisions" : ""),
        "POST",
        body,
      ),
    evaluateProfile: (
      account: "AUTO" | "MANUAL",
      id: string,
      analysisId: string,
    ) =>
      request<Models["ProfileEvaluation"]>(
        "/portfolios/" +
          account +
          "/strategy-profiles/" +
          encodeURIComponent(id) +
          "/evaluate",
        "POST",
        { analysis_id: analysisId },
      ),
    researchCatalogue: (id: string, account: "AUTO" | "MANUAL") =>
      request<Models["SnapshotResearchResponse"]>(
        "/analyses/" + encodeURIComponent(id) + "/research",
      ).then((r) => {
        if (
          !validResearchTimes(r) ||
          r.portfolio_id !== account ||
          r.analysis_id !== id
        )
          throw new ApiError("INVALID_RESPONSE");
        return r;
      }),
    computeResearch: (
      id: string,
      account: "AUTO" | "MANUAL",
      body: Models["SnapshotResearchRequest"],
    ) => {
      if (!config.scopes?.includes("read"))
        return Promise.reject(new ApiError("SCOPE_DENIED"));
      return request<Models["SnapshotResearchResponse"]>(
        "/analyses/" + encodeURIComponent(id) + "/research",
        "POST",
        body,
      ).then((r) => {
        if (
          !validResearchTimes(r) ||
          r.portfolio_id !== account ||
          r.analysis_id !== id ||
          r.source_record_id !== body.source_record_id ||
          r.symbol !== body.symbol ||
          r.timeframe !== body.timeframe
        )
          throw new ApiError("INVALID_RESPONSE");
        return r;
      });
    },
    candles: (id: string, timeframe?: string) =>
      request<Models["ChartResponse"]>(
        "/analyses/" +
          encodeURIComponent(id) +
          "/candles?limit=80" +
          (timeframe ? "&timeframe=" + encodeURIComponent(timeframe) : ""),
      ),
    jobs: (offset = 0) =>
      request<Models["ScannerJob"][]>(
        "/scanner/jobs?limit=20&offset=" + offset,
      ),
    followPolicy: (id: string) =>
      request<Models["TrackingSourcePolicy"]>(
        "/analysis-tracking/" + encodeURIComponent(id) + "/notification-policy",
      ),
    setFollowPolicy: (id: string, enabled: boolean) =>
      request<Models["TrackingSourcePolicy"]>(
        "/analysis-tracking/" + encodeURIComponent(id) + "/notification-policy",
        "POST",
        { notify_source_changes: enabled },
      ),
    follows: () => request<Models["TrackingResponse"][]>("/analysis-tracking"),
    follow: (analysisId: string) =>
      request<Models["TrackingResponse"]>("/analysis-tracking", "POST", {
        analysis_id: analysisId,
      }),
    changeFollow: (id: string, enabled: boolean) =>
      request<Models["TrackingResponse"]>(
        "/analysis-tracking/" + encodeURIComponent(id),
        "POST",
        { enabled },
      ),
    quotes: () => request<Models["QuotesResponse"]>("/quotes"),
    health: () => request<Models["HealthResponse"]>("/health"),
    markets: () => request<Models["MarketsResponse"]>("/markets"),
    analyses: (offset = 0) =>
      request<Models["AnalysisResponse"][]>(
        "/analyses?limit=20&offset=" + offset,
      ),
    detail: (id: string) =>
      request<Models["AnalysisResponse"]>(
        "/analyses/" + encodeURIComponent(id),
      ),
    analyze: (body: Models["AnalyzeRequest"]) =>
      request<Models["AnalysisResponse"]>("/analyze", "POST", {
        ...body,
        auto_paper: false,
      }),
    // AppProvider never enables this flag. Only isolated tests opt in.
    createOrder: (account: "AUTO" | "MANUAL", body: Models["OrderRequest"]) =>
      request<Models["OrderResponse"]>(
        "/portfolios/" + account + "/orders",
        "POST",
        body,
      ),
    cancelOrder: (
      account: "AUTO" | "MANUAL",
      id: string,
      body: Models["CancelRequest"],
    ) =>
      request<Models["OrderResponse"]>(
        "/portfolios/" +
          account +
          "/orders/" +
          encodeURIComponent(id) +
          "/cancel",
        "POST",
        body,
      ),
    closePosition: (
      account: "AUTO" | "MANUAL",
      id: string,
      body: Models["CloseRequest"],
    ) =>
      request<Models["CloseResult"]>(
        "/portfolios/" +
          account +
          "/positions/" +
          encodeURIComponent(id) +
          "/close",
        "POST",
        body,
      ),
    pausePortfolio: (account: "AUTO" | "MANUAL", paused: boolean) =>
      request<Models["PortfolioResponse"]>(
        "/portfolios/" + account + "/pause",
        "POST",
        { paused },
      ),
    portfolios: () => request<Models["PortfolioResponse"][]>("/portfolios"),
    orders: (id: string, offset = 0) =>
      request<Models["OrderResponse"][]>(
        "/portfolios/" + id + "/orders?limit=20&offset=" + offset,
      ),
    positions: (id: string, open = true, offset = 0) =>
      request<Models["PositionResponse"][]>(
        "/portfolios/" +
          id +
          "/positions?open_only=" +
          open +
          "&limit=20&offset=" +
          offset,
      ),
    transactions: (id: string, offset = 0) =>
      request<Models["TransactionResponse"][]>(
        "/portfolios/" + id + "/transactions?limit=20&offset=" + offset,
      ),
    scanner: () => request<Models["ScannerState"]>("/scanner"),
    watches: () =>
      request<Models["WatchResponse"][]>(
        "/watchlist" +
          (features.profileScannerEnabled ? "?include_profile=true" : ""),
      ),
    pause: (paused: boolean) =>
      request<Models["ScannerState"]>("/scanner/pause", "POST", { paused }),
    watch: (body: Models["WatchRequest"]) =>
      request<Models["WatchResponse"]>(
        "/watchlist" +
          (features.profileScannerEnabled ? "?include_profile=true" : ""),
        "POST",
        {
          ...body,
          auto_paper: false,
        },
      ),
    tick: () =>
      request<Models["TickResponse"]>(
        "/scanner/tick",
        "POST",
        undefined,
        50000,
      ),
    equityHistory: (
      account: "AUTO" | "MANUAL",
      fromMs = 0,
      toMs = Date.now(),
      period: "day" | "week" | "month" = "day",
    ) =>
      request<Models["EquityHistoryResponse"]>(
        "/portfolios/" +
          account +
          "/equity-history?limit=200&from_ms=" +
          fromMs +
          "&to_ms=" +
          toMs +
          "&period=" +
          period,
      ),
    equityWindow: (
      account: "AUTO" | "MANUAL",
      fromMs: number,
      toMs: number,
      cursor?: string,
      sampling: "raw" | "minmax" = "raw",
    ) =>
      request<Models["EquityWindowResponse"]>(
        "/portfolios/" +
          account +
          "/equity-history-window?limit=200&from_ms=" +
          fromMs +
          "&to_ms=" +
          toMs +
          "&sampling=" +
          sampling +
          (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""),
      ),
    performance: () => request<Models["PerformanceResponse"]>("/performance"),
    notificationPreferences: (account: "AUTO" | "MANUAL") =>
      request<Models["NoticePreferences"]>(
        "/portfolios/" + account + "/notification-preferences",
      ),
    setNotificationPreferences: (
      account: "AUTO" | "MANUAL",
      body: Models["NoticePreferencesWrite"],
    ) =>
      request<Models["NoticePreferences"]>(
        "/portfolios/" + account + "/notification-preferences",
        "POST",
        body,
      ),
    notifications: (offset = 0) =>
      request<Models["NotificationResponse"][]>(
        "/notifications?limit=20&offset=" + offset,
      ),
  };
}
