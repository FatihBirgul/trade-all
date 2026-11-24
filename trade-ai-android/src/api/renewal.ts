import { ApiError, type GatewayConfig } from "./client";
import { gatewayOrigin } from "../domain/safety";
import { isMobileSession, type MobileSession } from "./gateway";
// A single encrypted SecureStore record contains current and proposed credentials.
// No API/order POST is retried here. Only explicit refresh receipts are replayed.
async function rotateConnection(
  initial: GatewayConfig,
  save: (value: GatewayConfig) => Promise<void>,
  random: (prefix: string) => Promise<string>,
  transport: typeof fetch = fetch,
): Promise<{ config: GatewayConfig; metadata: MobileSession }> {
  let current = initial;
  if (!current.refresh || !current.deviceId)
    throw new ApiError("LOCAL_PAIR_REQUIRED");
  for (let attempt = 0; attempt < 2; attempt++) {
    if (!current.pendingRenewal) {
      current = {
        ...current,
        pendingRenewal: {
          requestId: await random("rq_"),
          session: await random("tg_"),
          refresh: await random("tr_"),
        },
      };
      await save(current); // A storage failure must prevent the network request.
    }
    const proposed = current.pendingRenewal!;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await transport(
        gatewayOrigin(current.origin) + "/gateway/refresh",
        {
          method: "POST",
          redirect: "error",
          signal: controller.signal,
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            refresh_token: current.refresh,
            device_id: current.deviceId,
            request_id: proposed.requestId,
            next_session: proposed.session,
            next_refresh_token: proposed.refresh,
          }),
        },
      );
      if (!response.ok)
        throw new ApiError(
          response.status === 401
            ? "LOCAL_PAIR_REQUIRED"
            : "HTTP_" + response.status,
          false,
          response.status,
        );
      const metadata: unknown = await response.json();
      if (
        !isMobileSession(metadata, true) ||
        metadata.device_id !== current.deviceId ||
        !Number.isSafeInteger(metadata.renewal_expires_at_ms) ||
        metadata.renewal_expires_at_ms! <= Date.now() ||
        metadata.expires_at_ms > metadata.renewal_expires_at_ms! ||
        (current.renewalExpiresAt !== undefined &&
          metadata.renewal_expires_at_ms! > current.renewalExpiresAt) ||
        (current.accounts &&
          metadata.accounts.some((a) => !current.accounts!.includes(a))) ||
        (current.scopes &&
          metadata.scopes.some((s) => !current.scopes!.includes(s)))
      )
        throw new ApiError("INVALID_RESPONSE");
      const { pendingRenewal: _pending, ...rest } = current;
      current = {
        ...rest,
        session: proposed.session,
        refresh: proposed.refresh,
        renewalExpiresAt: metadata.renewal_expires_at_ms,
        scopes: metadata.scopes,
        accounts: metadata.accounts,
      };
      await save(current);
      if (metadata.expires_at_ms > Date.now())
        return { config: current, metadata };
      // Recovered a committed rotation after >24h offline: rotate its successor.
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError("RENEWAL_UNCERTAIN");
    } finally {
      clearTimeout(timeout);
    }
  }
  throw new ApiError("LOCAL_PAIR_REQUIRED");
}

const active = new Set<string>();
export function renewConnection(
  initial: GatewayConfig,
  save: (value: GatewayConfig) => Promise<void>,
  random: (prefix: string) => Promise<string>,
  transport: typeof fetch = fetch,
) {
  const key = gatewayOrigin(initial.origin) + "|" + initial.deviceId;
  if (active.has(key))
    return Promise.reject(new ApiError("RENEWAL_IN_PROGRESS"));
  active.add(key);
  return rotateConnection(initial, save, random, transport).finally(() =>
    active.delete(key),
  );
}
