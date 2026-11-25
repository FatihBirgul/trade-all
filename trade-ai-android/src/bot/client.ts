// Trade bot API istemcisi. Eski V2 istemcisinden (src/api/client.ts) bağımsızdır: o istemci
// "/api/v2" önekini ve V2 şema doğrulamasını zorunlu kılar.
import { ApiError } from "../api/client";
import { gatewayOrigin } from "../domain/safety";
import type { BotConfig, BotEvent, BotHealth, BotPosition, BotStatus, PositionPatch } from "./types";

const TIMEOUT_MS = 15000;
const MESSAGES: Record<string, string> = {
  UNCONFIGURED: "Trade Bot bağlantısı kurulmadı. Bağlantı sekmesinden eşleştirin.",
  NETWORK: "Sunucuya ulaşılamadı. İnternet bağlantınızı ve sunucu adresini kontrol edin.",
  UNAUTHORIZED: "Bağlantı anahtarı geçersiz. Bağlantı sekmesinden yeniden eşleştirin.",
  INVALID_ORIGIN: "Geçerli bir sunucu adresi girin. Adres https:// ile başlamalı.",
  INVALID_CODE: "Eşleştirme kodu 6 rakamdan oluşur.",
  PAIR_REJECTED: "Kod geçersiz ya da süresi dolmuş. Sunucuda yeni kod üretin.",
  INVALID_RESPONSE: "Sunucu yanıtı anlaşılamadı. Sunucu adresini kontrol edin.",
  INVALID_REQUEST: "İstek geçersiz.",
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
  url: string,
  method: string,
  token: string | null,
  body?: unknown,
): Promise<{ status: number; ok: boolean; payload: unknown }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const headers: Record<string, string> = { Accept: "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  try {
    const response = await transport(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      redirect: "error",
      signal: controller.signal,
    });
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    return { status: response.status, ok: response.ok, payload };
  } catch {
    // Değişiklik yapan isteklerde sonuç bilinmez: asla kendiliğinden yeniden denenmez.
    throw new BotError("NETWORK", undefined, method !== "GET");
  } finally {
    clearTimeout(timer);
  }
}

export async function pairBot(originInput: string, code: string, transport: Transport = fetch): Promise<BotConfig> {
  let origin: string;
  try {
    origin = gatewayOrigin(originInput);
  } catch {
    throw new BotError("INVALID_ORIGIN");
  }
  if (!/^[0-9]{6}$/.test(code)) throw new BotError("INVALID_CODE");
  const result = await send(transport, origin + "/pair", "POST", null, { code });
  if (result.status === 401) throw new BotError("PAIR_REJECTED", undefined, false, 401);
  if (!result.ok) throw new BotError("HTTP_" + result.status, detailText(result.payload), false, result.status);
  const token = (result.payload as { token?: unknown } | null)?.token;
  if (typeof token !== "string" || token.length < 32) throw new BotError("INVALID_RESPONSE");
  return { origin, token, pairedAt: Date.now() };
}

export function createBotApi(config: BotConfig | null, transport: Transport = fetch, onUnauthorized?: () => void) {
  async function request<T>(path: string, method = "GET", body?: unknown, authenticated = true): Promise<T> {
    if (!config) throw new BotError("UNCONFIGURED");
    const result = await send(transport, config.origin + path, method, authenticated ? config.token : null, body);
    if (result.status === 401) {
      onUnauthorized?.();
      throw new BotError("UNAUTHORIZED", undefined, false, 401);
    }
    if (!result.ok) throw new BotError("HTTP_" + result.status, detailText(result.payload), false, result.status);
    if (result.payload === null || typeof result.payload !== "object") throw new BotError("INVALID_RESPONSE");
    return result.payload as T;
  }
  const position = (id: string) => {
    if (!/^[0-9]{1,20}$/.test(id)) throw new BotError("INVALID_REQUEST");
    return "/positions/" + id;
  };
  return {
    health: () => request<BotHealth>("/health", "GET", undefined, false),
    status: () => request<BotStatus>("/status"),
    positions: async () => (await request<{ positions: BotPosition[] }>("/positions")).positions ?? [],
    patchPosition: async (id: string, patch: PositionPatch) =>
      request<{ order: string | null; manage: boolean }>(position(id), "PATCH", patch),
    closePosition: async (id: string, volume?: number) =>
      request<{ order: string }>(position(id) + "/close", "POST", volume === undefined ? {} : { volume }),
    stop: () => request<BotStatus>("/bot/stop", "POST"),
    resume: (confirmHalt = false) =>
      request<BotStatus>("/bot/resume", "POST", confirmHalt ? { confirm_halt: true } : {}),
    closeAll: () =>
      request<{ requested: number; skipped: string[]; stopped: boolean }>("/bot/close-all", "POST", {
        confirm: "CLOSE-ALL",
      }),
    events: async (after = 0) =>
      (await request<{ events: BotEvent[] }>("/events?after=" + Math.max(0, Math.floor(after)))).events ?? [],
    // İlk açılış: en yeni olaylar, yeniden eskiye.
    recentEvents: async (limit = 100) =>
      (await request<{ events: BotEvent[] }>("/events?newest=true&limit=" + Math.min(500, Math.max(1, Math.floor(limit)))))
        .events ?? [],
    registerDevice: (expoToken: string) =>
      request<{ registered: boolean }>("/devices", "POST", { expo_token: expoToken }),
  };
}

export type BotApi = ReturnType<typeof createBotApi>;
