import { IntentJournal, type Intent } from "./intent";
import { gatewayOrigin, type Account } from "../domain/safety";
import type { createApi } from "./client";
// Bound to a verified device and account, never to a bearer token. Re-pairing
// the same device can reconcile the original body/key after a process restart.
export function paperOperations(
  journal: IntentJournal,
  api: ReturnType<typeof createApi>,
  context: {
    origin: string;
    deviceId: string;
    account: Account;
    enabled: boolean;
    scopes: string[];
  },
) {
  const scope = [
    gatewayOrigin(context.origin),
    "live",
    context.deviceId,
    context.account,
  ].join("|");
  function authorize() {
    if (!context.enabled || !context.scopes.includes("paper:write"))
      throw new Error(
        "Sanal işlem yazma doğrulaması tamamlanmadı; işlem kapalı.",
      );
  }
  function verify(intent: Intent) {
    if (intent.scope !== scope)
      throw new Error("Bekleyen işlem başka cihaz veya hesaba ait.");
    const base = "/portfolios/" + context.account;
    const keys = Object.keys(intent.body);
    const quantity = intent.body.quantity;
    const validQuantity =
      typeof quantity === "string" &&
      quantity.length <= 80 &&
      /^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$/.test(quantity) &&
      /[1-9]/.test(quantity);
    const create =
      intent.path === base + "/orders" &&
      typeof intent.body.analysis_id === "string" &&
      /^[a-f0-9]{64}$/.test(intent.body.analysis_id) &&
      keys.every((k) => ["analysis_id", "quantity"].includes(k)) &&
      (!("quantity" in intent.body) || validQuantity);
    const cancel =
      new RegExp("^" + base + "/orders/[a-f0-9]{64}/cancel$").test(
        intent.path,
      ) && keys.length === 0;
    const close =
      new RegExp("^" + base + "/positions/[a-f0-9]{64}/close$").test(
        intent.path,
      ) &&
      keys.length === 1 &&
      validQuantity;
    if (
      !/^[a-zA-Z0-9_.:-]{8,128}$/.test(intent.idempotency_key) ||
      !(create || cancel || close)
    )
      throw new Error(
        "Sanal işlem gövdesi, miktarı veya anahtarı geçersiz. Miktarı pozitif ondalık metin olarak girin.",
      );
  }
  async function send(intent: Intent) {
    authorize();
    verify(intent);
    const base = "/portfolios/" + context.account;
    const body: Record<string, unknown> & { idempotency_key: string } = {
      ...intent.body,
      idempotency_key: intent.idempotency_key,
    };
    if (
      intent.path === base + "/orders" &&
      typeof body.analysis_id === "string"
    )
      return api.createOrder(context.account, {
        analysis_id: body.analysis_id,
        idempotency_key: body.idempotency_key,
        ...(typeof body.quantity === "string"
          ? { quantity: body.quantity }
          : {}),
      });
    const match = new RegExp(
      "^" + base + "/(orders|positions)/([a-f0-9]{64})/(cancel|close)$",
    ).exec(intent.path);
    if (match?.[1] === "orders" && match[3] === "cancel")
      return api.cancelOrder(context.account, match[2], {
        idempotency_key: body.idempotency_key,
      });
    if (
      match?.[1] === "positions" &&
      match[3] === "close" &&
      typeof body.quantity === "string"
    )
      return api.closePosition(context.account, match[2], {
        quantity: body.quantity,
        idempotency_key: body.idempotency_key,
      });
    throw new Error("Bekleyen sanal işlem sözleşmesi geçersiz.");
  }
  return {
    pending: () => journal.pending(),
    execute: (path: string, body: Record<string, unknown>, key: string) => {
      authorize();
      const intent = { scope, path, body, idempotency_key: key };
      verify(intent);
      return journal.execute(intent, send);
    },
    // Explicit replay to the backend command journal is reconciliation: no new key,
    // no automatic loop, and a pending close remains pending until a market event.
    recover: async () => {
      authorize();
      const intent = await journal.pending();
      if (!intent) return null;
      if (intent.scope !== scope)
        throw new Error(
          "Önce bekleyen işlemin kendi hesabını ve cihazını seçin.",
        );
      return journal.execute(intent, send);
    },
  };
}
