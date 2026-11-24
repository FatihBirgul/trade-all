import { gatewayOrigin } from "../domain/safety";
import { ApiError, type GatewayConfig } from "./client";
export type MobileSession = {
  session_id: string;
  device_id: string;
  device_name: string;
  expires_at_ms: number;
  scopes: string[];
  accounts: ("AUTO" | "MANUAL")[];
  protocol_version: 1;
  capabilities?: string[];
  renewal_id?: string;
  renewal_expires_at_ms?: number;
};
export function isMobileSession(
  value: unknown,
  allowExpired = false,
): value is MobileSession {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.session_id === "string" &&
    typeof v.device_id === "string" &&
    typeof v.device_name === "string" &&
    v.protocol_version === 1 &&
    (v.capabilities === undefined ||
      (Array.isArray(v.capabilities) &&
        v.capabilities.length <= 16 &&
        v.capabilities.every(
          (c) => typeof c === "string" && /^[a-z0-9-]{1,48}$/.test(c),
        ))) &&
    typeof v.expires_at_ms === "number" &&
    Number.isSafeInteger(v.expires_at_ms) &&
    v.expires_at_ms > (allowExpired ? 0 : Date.now()) &&
    Array.isArray(v.scopes) &&
    v.scopes.includes("read") &&
    v.scopes.every((s) =>
      [
        "read",
        "analyze",
        "scanner:write",
        "paper:write",
        "profiles:write",
        "notifications:write",
        "discovery:write",
      ].includes(s),
    ) &&
    Array.isArray(v.accounts) &&
    v.accounts.length > 0 &&
    v.accounts.every((a) => a === "AUTO" || a === "MANUAL")
  );
}
async function call(
  origin: string,
  path: string,
  body?: object,
  session?: string,
  transport: typeof fetch = fetch,
) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await transport(gatewayOrigin(origin) + path, {
      method: body ? "POST" : "GET",
      redirect: "error",
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(session ? { Authorization: "Bearer " + session } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    if (!response.ok)
      throw new ApiError(
        response.status === 401 ? "UNAUTHORIZED" : "HTTP_" + response.status,
        false,
        response.status,
      );
    const value: unknown = await response.json();
    if (!isMobileSession(value)) throw new ApiError("INVALID_RESPONSE");
    return value;
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError("NETWORK");
  } finally {
    clearTimeout(timer);
  }
}
export async function mobileSession(
  config: GatewayConfig,
  transport: typeof fetch = fetch,
) {
  return call(
    config.origin,
    "/gateway/session",
    undefined,
    config.session,
    transport,
  );
}
export async function pairDevice(
  origin: string,
  code: string,
  deviceId: string,
  deviceName: string,
  transport: typeof fetch = fetch,
) {
  if (
    !/^[A-Za-z0-9_-]{32}$/.test(code.trim()) ||
    !deviceName.trim() ||
    deviceName.trim().length > 60
  )
    throw new Error(
      "Bilgisayardaki 120 saniyelik eşleştirme kodunu ve cihaz adını girin.",
    );
  const value = await call(
    origin,
    "/gateway/pair",
    {
      code: code.trim(),
      device_id: deviceId,
      device_name: deviceName.trim(),
      renewal: true,
    },
    undefined,
    transport,
  );
  const session = (value as MobileSession & { session?: unknown }).session;
  if (typeof session !== "string" || !/^tg_[A-Za-z0-9_-]{43}$/.test(session))
    throw new ApiError("INVALID_RESPONSE");
  const refresh = (value as MobileSession & { refresh_token?: unknown })
    .refresh_token;
  if (
    refresh !== undefined &&
    (typeof refresh !== "string" ||
      !/^tr_[A-Za-z0-9_-]{43}$/.test(refresh) ||
      !Number.isSafeInteger(value.renewal_expires_at_ms) ||
      value.renewal_expires_at_ms! <= Date.now())
  )
    throw new ApiError("INVALID_RESPONSE");
  return { session, metadata: value, refresh: refresh as string | undefined };
}
