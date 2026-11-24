import { paperOperations } from "../src/api/paper";
import { IntentJournal } from "../src/api/intent";
import { createApi } from "../src/api/client";
function storage() {
  const rows = new Map<string, string>();
  return {
    getItem: async (k: string) => rows.get(k) ?? null,
    setItem: async (k: string, v: string) => {
      rows.set(k, v);
    },
    removeItem: async (k: string) => {
      rows.delete(k);
    },
  };
}
const config = {
  origin: "https://pc.example.ts.net",
  session: "controlled-test-only",
};
const context = {
  origin: config.origin,
  deviceId: "test-device",
  account: "MANUAL" as const,
  enabled: true,
  scopes: ["read", "paper:write"],
};
test("production API paper flag blocks all writes before transport", async () => {
  const transport = jest.fn();
  const api = createApi(config, transport);
  await expect(
    api.createOrder("MANUAL", {
      analysis_id: "a".repeat(64),
      idempotency_key: "create-test-key",
    }),
  ).rejects.toMatchObject({ code: "PAPER_WRITES_DISABLED" });
  await expect(
    api.cancelOrder("AUTO", "b".repeat(64), {
      idempotency_key: "cancel-test-key",
    }),
  ).rejects.toMatchObject({ code: "PAPER_WRITES_DISABLED" });
  await expect(
    api.closePosition("MANUAL", "c".repeat(64), {
      quantity: "1",
      idempotency_key: "close-test-key",
    }),
  ).rejects.toMatchObject({ code: "PAPER_WRITES_DISABLED" });
  await expect(api.pausePortfolio("AUTO", true)).rejects.toMatchObject({
    code: "PAPER_WRITES_DISABLED",
  });
  expect(transport).not.toHaveBeenCalled();
});
test("lost acknowledgement survives journal restart; wrong account cannot reconcile; original key only", async () => {
  const saved = storage();
  const closePosition = jest
    .fn()
    .mockRejectedValueOnce(new Error("lost acknowledgement"))
    .mockResolvedValue({ status: "pending" });
  const api = { closePosition } as unknown as ReturnType<typeof createApi>;
  const path = "/portfolios/MANUAL/positions/" + "c".repeat(64) + "/close";
  const first = paperOperations(new IntentJournal(saved), api, context);
  await expect(
    first.execute(path, { quantity: "0.1" }, "close-original-key"),
  ).rejects.toThrow("lost acknowledgement");
  const restarted = paperOperations(new IntentJournal(saved), api, context);
  await expect(
    restarted.execute(path, { quantity: "0.1" }, "new-unsafe-key"),
  ).rejects.toThrow("bekleyen");
  const wrong = paperOperations(new IntentJournal(saved), api, {
    ...context,
    account: "AUTO",
  });
  await expect(wrong.recover()).rejects.toThrow("hesabını");
  expect(closePosition).toHaveBeenCalledTimes(1);
  await expect(restarted.recover()).resolves.toEqual({ status: "pending" });
  expect(closePosition).toHaveBeenLastCalledWith("MANUAL", "c".repeat(64), {
    quantity: "0.1",
    idempotency_key: "close-original-key",
  });
  expect(await restarted.pending()).toBeNull();
});
test("feature flag and session grant both required, no journal write on denial", async () => {
  const journal = new IntentJournal(storage());
  const api = {} as ReturnType<typeof createApi>;
  const disabled = paperOperations(journal, api, {
    ...context,
    enabled: false,
  });
  expect(() =>
    disabled.execute("/portfolios/MANUAL/orders", {}, "write-test-key"),
  ).toThrow("kapalı");
  const noGrant = paperOperations(journal, api, {
    ...context,
    scopes: ["read"],
  });
  await expect(noGrant.recover()).rejects.toThrow("kapalı");
  expect(await journal.pending()).toBeNull();
});

test.each([0.1, 0, -1, "0", "0.00", "-1", "1,2", "1e2", null, true, {}, []])(
  "unsupported quantity %p is rejected before journal or transport",
  async (quantity) => {
    const journal = new IntentJournal(storage());
    const createOrder = jest.fn();
    const ops = paperOperations(
      journal,
      { createOrder } as unknown as ReturnType<typeof createApi>,
      context,
    );
    expect(() =>
      ops.execute(
        "/portfolios/MANUAL/orders",
        { analysis_id: "a".repeat(64), quantity },
        "strict-quantity-key",
      ),
    ).toThrow("miktarı");
    expect(await journal.pending()).toBeNull();
    expect(createOrder).not.toHaveBeenCalled();
  },
);
test("valid decimal text is preserved exactly; cancel cannot silently drop a body", async () => {
  const journal = new IntentJournal(storage());
  const createOrder = jest.fn().mockResolvedValue({ status: "pending" });
  const ops = paperOperations(
    journal,
    { createOrder } as unknown as ReturnType<typeof createApi>,
    context,
  );
  await ops.execute(
    "/portfolios/MANUAL/orders",
    { analysis_id: "a".repeat(64), quantity: "0.10000001" },
    "exact-decimal-key",
  );
  expect(createOrder).toHaveBeenCalledWith("MANUAL", {
    analysis_id: "a".repeat(64),
    quantity: "0.10000001",
    idempotency_key: "exact-decimal-key",
  });
  expect(() =>
    ops.execute(
      "/portfolios/MANUAL/orders/" + "b".repeat(64) + "/cancel",
      { quantity: "1" },
      "cancel-extra-key",
    ),
  ).toThrow("gövdesi");
  expect(await journal.pending()).toBeNull();
});
