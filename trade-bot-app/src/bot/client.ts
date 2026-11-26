// Trade bot API istemcisi. Eski V2 istemcisinden (src/api/client.ts) bağımsızdır: o istemci
// "/api/v2" önekini ve V2 şema doğrulamasını zorunlu kılar.
import { ApiError, serverOrigin } from "./base";
import { recordRequest } from "./requestLog";
import type { BacktestReport,
  BotSummary,
  BotConfig,
  BotEvent,
  BotHealth,
  BotPosition,
  BotReport,
  BotSettings,
  BotStatus,
  BotStrategy,
  BotSymbol,
  PositionPatch,
  ReportPeriod,
  StrategyMode,
  TradePreview,
  PreviewRequest,
  TradeRequest,
  TradeResult,
} from "./types";

const TIMEOUT_MS = 15000;
const MESSAGES: Record<string, string> = {
  UNCONFIGURED: "Trade Bot bağlantısı kurulmadı. Bağlantı ekranından eşleştirin.",
  NETWORK: "Sunucuya ulaşılamadı. İnternet bağlantınızı ve sunucu adresini kontrol edin.",
  UNAUTHORIZED: "Bağlantı anahtarı geçersiz. Bağlantı ekranından yeniden eşleştirin.",
  INVALID_ORIGIN: "Geçerli bir sunucu adresi girin. Adres https:// ile başlamalı.",
  INVALID_CODE: "Eşleştirme kodu 6 rakamdan oluşur.",
  PAIR_REJECTED: "Kod geçersiz ya da süresi dolmuş. Sunucuda yeni kod üretin.",
  INVALID_RESPONSE: "Sunucu yanıtı anlaşılamadı. Sunucu adresini kontrol edin.",
  INVALID_REQUEST: "İstek geçersiz.",
  PAIR_NETWORK:
    "Sunucuya ulaşılamadı. Adresi ve internet bağlantınızı kontrol edin. Kod kullanılmış olabilir; gerekirse sunucuda yeni kod üretin.",
  PAIR_NOT_FOUND: "Bu adreste Trade Bot bulunamadı. Sunucu adresini kontrol edin.",
  REDIRECTED: "Sunucu isteği başka bir adrese yönlendirdi. Bağlantı güvenli değil; sunucu adresini kontrol edin.",
  HTTP_429: "Çok fazla istek gönderildi. Biraz bekleyip yeniden deneyin.",
};

export class BotError extends ApiError {
  detail?: string;
  constructor(code: string, detail?: string, uncertain = false, status = 0) {
    super(code, uncertain, status);
    this.name = "BotError";
    this.detail = detail;
    // Değişiklik yapan bir isteğin sonucu bilinmiyorsa ApiError'ın "sonuç belirsiz" metni korunur.
    if (detail) this.message = detail;
    else if (!uncertain && MESSAGES[code]) this.message = MESSAGES[code];
    else if (!uncertain && /^HTTP_[0-9]+$/.test(code))
      this.message = "Sunucu isteği yanıtlayamadı (hata " + code.slice(5) + "). Biraz sonra yeniden deneyin.";
  }
}

type Transport = typeof fetch;

function detailText(payload: unknown): string | undefined {
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length) {
    // FastAPI doğrulama hatası: [{ loc: ["body", "alan"], msg }]
    const fields = detail
      .map((item) => (Array.isArray(item?.loc) ? String(item.loc[item.loc.length - 1]) : ""))
      .filter(Boolean);
    return "Girilen değer geçersiz" + (fields.length ? ": " + fields.join(", ") : "");
  }
  return undefined;
}

async function send(
  transport: Transport,
  origin: string,
  path: string,
  method: string,
  token: string | null,
  body?: unknown,
): Promise<{ status: number; ok: boolean; payload: unknown }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const mutation = method !== "GET";
  let response: Awaited<ReturnType<Transport>>;
  try {
    response = await transport(origin + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      redirect: "error",
      signal: controller.signal,
    });
  } catch {
    clearTimeout(timer);
    // Değişiklik yapan isteklerde sonuç bilinmez: asla kendiliğinden yeniden denenmez.
    throw new BotError("NETWORK", undefined, mutation);
  }
  try {
    // React Native'in fetch'i "redirect: error" seçeneğini uygulamayabilir; yanıtın gerçekten
    // eşleşilen sunucudan geldiği ayrıca doğrulanır.
    if (typeof response.url === "string" && response.url && !response.url.startsWith(origin + "/"))
      throw new BotError("REDIRECTED", undefined, mutation);
    let payload: unknown = null;
    let readable = true;
    try {
      payload = await response.json();
    } catch {
      readable = false;
    }
    // Vekil sunucu hatası ya da okunamayan başarılı yanıt: istek sunucuya ulaşmış ve işlenmiş olabilir.
    // Sunucu hatası (500 dahil) emir aracıya gittikten SONRA da oluşabilir; zaman aşımı (408) da öyle.
    if (mutation && (response.status >= 500 || response.status === 408))
      throw new BotError("HTTP_" + response.status, undefined, true, response.status);
    if (mutation && response.ok && (!readable || payload === null || typeof payload !== "object"))
      throw new BotError("INVALID_RESPONSE", undefined, true, response.status);
    return { status: response.status, ok: response.ok, payload };
  } finally {
    clearTimeout(timer);
  }
}

export async function pairBot(originInput: string, code: string, transport: Transport = fetch): Promise<BotConfig> {
  let origin: string;
  try {
    origin = serverOrigin(originInput);
  } catch {
    throw new BotError("INVALID_ORIGIN");
  }
  if (!/^[0-9]{6}$/.test(code)) throw new BotError("INVALID_CODE");
  let result: Awaited<ReturnType<typeof send>>;
  try {
    result = await send(transport, origin, "/pair", "POST", null, { code });
  } catch (reason) {
    // Eşleştirme bir işlem emri değildir: "sonuç belirsiz" yerine ne yapılacağı söylenir.
    if (reason instanceof BotError && (reason.code === "NETWORK" || reason.uncertain))
      throw new BotError(reason.code === "REDIRECTED" ? "REDIRECTED" : "PAIR_NETWORK");
    throw reason;
  }
  if (result.status === 401) throw new BotError("PAIR_REJECTED", undefined, false, 401);
  if (result.status === 404 || result.status === 405) throw new BotError("PAIR_NOT_FOUND", undefined, false, result.status);
  if (!result.ok) throw new BotError("HTTP_" + result.status, detailText(result.payload), false, result.status);
  const token = (result.payload as { token?: unknown } | null)?.token;
  if (typeof token !== "string" || token.length < 32) throw new BotError("INVALID_RESPONSE");
  return { origin, token, pairedAt: Date.now() };
}

const isObject = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);

// Yanıtın biçimi ekranlara verilmeden önce doğrulanır: bozuk bir yanıt "pozisyon yok" gibi görünmemeli.
function statusShape(value: unknown): value is BotStatus {
  if (!isObject(value) || !isObject(value.pnl_today)) return false;
  const pnl = value.pnl_today;
  return (
    ["bot", "manual", "total"].every((key) => typeof pnl[key] === "number") &&
    ["halted", "stopped", "dry_run", "stream_connected"].every((key) => typeof value[key] === "boolean") &&
    typeof value.open_bot === "number" &&
    typeof value.open_manual === "number"
  );
}
function listShape<T>(value: unknown, key: string, item: (entry: Record<string, unknown>) => boolean): T[] {
  const list = isObject(value) ? value[key] : undefined;
  if (!Array.isArray(list) || !list.every((entry) => isObject(entry) && item(entry)))
    throw new BotError("INVALID_RESPONSE");
  return list as T[];
}
const positionShape = (entry: Record<string, unknown>) =>
  typeof entry.position_id === "string" &&
  typeof entry.symbol === "string" &&
  (entry.side === "BUY" || entry.side === "SELL") &&
  typeof entry.volume === "number" &&
  typeof entry.entry === "number";
const eventShape = (entry: Record<string, unknown>) =>
  typeof entry.id === "number" && typeof entry.at === "number" && typeof entry.kind === "string";

export function createBotApi(config: BotConfig | null, transport: Transport = fetch, onUnauthorized?: () => void) {
  async function request<T>(path: string, method = "GET", body?: unknown, authenticated = true): Promise<T> {
    if (!config) throw new BotError("UNCONFIGURED");
    const started = Date.now();
    const log = (status: number, error: string | null) =>
      recordRequest({ at: started, method, path: path.split("?")[0], status, ms: Date.now() - started, error });
    let result: Awaited<ReturnType<typeof send>>;
    try {
      result = await send(transport, config.origin, path, method, authenticated ? config.token : null, body);
    } catch (reason) {
      log(reason instanceof BotError ? reason.status : 0, reason instanceof BotError ? reason.code : "HATA");
      throw reason;
    }
    log(result.status, result.ok ? null : "HTTP_" + result.status);
    if (result.status === 401) {
      onUnauthorized?.();
      throw new BotError("UNAUTHORIZED", undefined, false, 401);
    }
    if (!result.ok) throw new BotError("HTTP_" + result.status, detailText(result.payload), false, result.status);
    if (result.payload === null || typeof result.payload !== "object") throw new BotError("INVALID_RESPONSE");
    return result.payload as T;
  }
  const position = (id: string) => {
    // Kimlik biçimi broker'a aittir; yalnızca URL'yi bozabilecek karakterler reddedilir.
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(id)) throw new BotError("INVALID_REQUEST");
    return "/positions/" + encodeURIComponent(id);
  };
  return {
    health: () => request<BotHealth>("/health", "GET", undefined, false),
    // Son 24 saatin tarama özeti (herkese açık uç; yalnızca sayılar ve nedenler).
    summary: () => request<BotSummary>("/health/summary?hours=24", "GET", undefined, false),
    status: async () => {
      const value = await request<unknown>("/status");
      if (!statusShape(value)) throw new BotError("INVALID_RESPONSE");
      return value;
    },
    positions: async () => listShape<BotPosition>(await request<unknown>("/positions"), "positions", positionShape),
    patchPosition: async (id: string, patch: PositionPatch) =>
      request<{ order: string | null; manage: boolean }>(position(id), "PATCH", patch),
    closePosition: async (id: string, volume?: number) =>
      request<{ order: string }>(position(id) + "/close", "POST", volume === undefined ? {} : { volume }),
    stop: () => request<BotStatus>("/bot/stop", "POST"),
    resume: (confirmHalt = false) =>
      request<BotStatus>("/bot/resume", "POST", confirmHalt ? { confirm_halt: true } : {}),
    // Deneme/canlı kipi. Ayarlar her seferinde yeniden okunur (eski bir kopya gönderilmez); canlıya
    // geçiş sunucuda ayrı bir onay değeri ister ve yalnızca kullanıcı onayladıktan sonra çağrılır.
    setDryRun: async (dryRun: boolean) => {
      const settings = await request<Record<string, unknown>>("/settings");
      if (typeof settings.dry_run !== "boolean") throw new BotError("INVALID_RESPONSE");
      return request<Record<string, unknown>>(
        "/settings" + (dryRun ? "" : "?confirm_live=true"),
        "PUT",
        { ...settings, dry_run: dryRun },
      );
    },
    reports: async (period: ReportPeriod) => {
      const value = await request<BotReport>("/reports?period=" + period);
      if (!isObject(value.totals) || !Array.isArray(value.history)) throw new BotError("INVALID_RESPONSE");
      return value;
    },
    // Yıllık backtestin tam sonucu (sembol tabloları ve bakiye eğrileri dahil). Sonuç henüz yoksa `result` null.
    backtest: async () => {
      const value = await request<BacktestReport>("/backtest");
      if (typeof value.state !== "string" || (value.result !== null && !isObject(value.result?.strategies))) throw new BotError("INVALID_RESPONSE");
      return value;
    },
    strategies: async () =>
      listShape<BotStrategy>(await request<unknown>("/strategies"), "strategies", (entry) =>
        typeof entry.strategy_id === "string" && typeof entry.mode === "string" && isObject(entry.shadow),
      ),
    // Canlıya almak sunucuda ayrı onay ister; `confirm` yalnızca kullanıcı onayladıktan sonra true gönderilir.
    setStrategyMode: (id: string, mode: StrategyMode, confirm = false) => {
      if (!/^[a-z0-9_]{3,64}$/.test(id)) throw new BotError("INVALID_REQUEST");
      return request<{ strategy_id: string; mode: StrategyMode }>("/strategies/" + id + "/mode", "POST", {
        mode,
        confirm,
      });
    },
    settings: async () => {
      const value = await request<BotSettings>("/settings");
      if (!isObject(value.risk) || !isObject(value.news) || !isObject(value.fusion) || typeof value.dry_run !== "boolean")
        throw new BotError("INVALID_RESPONSE");
      return value;
    },
    // Ayarlar her kayıtta yeniden okunur ve değişiklik o güncel kopyaya uygulanır: eski bir kopya gönderilmez.
    // Deneme/canlı kipi ve strateji kipleri bu yoldan değişmez (kendi onaylı uç noktaları vardır).
    updateSettings: async (apply: (current: BotSettings) => BotSettings) => {
      const current = await request<BotSettings>("/settings");
      if (!isObject(current.risk) || typeof current.dry_run !== "boolean") throw new BotError("INVALID_RESPONSE");
      const next = apply(JSON.parse(JSON.stringify(current)) as BotSettings);
      return request<BotSettings>("/settings", "PUT", {
        ...next,
        dry_run: current.dry_run,
        strategy_modes: current.strategy_modes,
      });
    },
    symbols: async () =>
      listShape<BotSymbol>(await request<unknown>("/symbols"), "symbols", (entry) =>
        typeof entry.symbol === "string" && typeof entry.open === "boolean" && typeof entry.volume_min === "number",
      ),
    previewTrade: async (trade: PreviewRequest) => {
      const value = await request<TradePreview>("/trades/preview", "POST", trade);
      if (typeof value.lots !== "number" || typeof value.loss !== "number" || !Array.isArray(value.warnings))
        throw new BotError("INVALID_RESPONSE");
      return value;
    },
    // `clientId` aynı kaldıkça sunucu ikinci bir emir açmaz: sonucu belirsiz kalan istek güvenle yeniden sorulabilir.
    openTrade: (trade: TradeRequest, clientId: string) => {
      if (!/^[A-Za-z0-9._~-]{8,64}$/.test(clientId)) throw new BotError("INVALID_REQUEST");
      return request<TradeResult>("/trades", "POST", { ...trade, client_id: clientId });
    },
    // Sonucu bilinmeyen elle emri sorar; emir AÇMAZ. Sunucuda kayıt yoksa o kimlik geçersiz kılınır.
    resolveTrade: async (clientId: string) => {
      if (!/^[A-Za-z0-9._~-]{8,64}$/.test(clientId)) throw new BotError("INVALID_REQUEST");
      const value = await request<{ found: boolean; state: string | null; lots: number | null }>(
        "/trades/" + clientId + "/resolve", "POST", {});
      if (typeof value.found !== "boolean") throw new BotError("INVALID_RESPONSE", undefined, true);
      return value;
    },
    closeAll: () =>
      request<{ requested: number; skipped: string[]; stopped: boolean }>("/bot/close-all", "POST", {
        confirm: "CLOSE-ALL",
      }),
    events: async (after = 0) =>
      listShape<BotEvent>(await request<unknown>("/events?after=" + Math.max(0, Math.floor(after))), "events", eventShape),
    // İlk açılış: en yeni olaylar, yeniden eskiye.
    recentEvents: async (limit = 100) =>
      listShape<BotEvent>(
        await request<unknown>("/events?newest=true&limit=" + Math.min(500, Math.max(1, Math.floor(limit)))),
        "events",
        eventShape,
      ),
    registerDevice: (expoToken: string) =>
      request<{ registered: boolean }>("/devices", "POST", { expo_token: expoToken }),
  };
}

export type BotApi = ReturnType<typeof createBotApi>;
