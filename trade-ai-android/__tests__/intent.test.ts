import { IntentJournal, type Intent } from "../src/api/intent";
test("restart retains the same mutation key and blocks different orders", async () => {
  const data = new Map<string, string>();
  const storage = {
    getItem: async (k: string) => data.get(k) || null,
    setItem: async (k: string, v: string) => {
      data.set(k, v);
    },
    removeItem: async (k: string) => {
      data.delete(k);
    },
  };
  const intent: Intent = {
    scope: "https://gateway.example.com|live|MANUAL",
    path: "/portfolios/MANUAL/orders",
    body: { analysis_id: "a".repeat(64), quantity: "1" },
    idempotency_key: "persistent-key",
  };
  const first = new IntentJournal(storage);
  await expect(
    first.execute(intent, async () => {
      throw new Error("timeout");
    }),
  ).rejects.toThrow("timeout");
  const resumed = new IntentJournal(storage);
  expect(await resumed.pending()).toEqual(intent);
  await expect(
    resumed.execute(
      { ...intent, idempotency_key: "new-key" },
      async () => ({}),
    ),
  ).rejects.toThrow("bekleyen");
  const send = jest.fn(async (i: Intent) => ({
    status: "pending",
    key: i.idempotency_key,
  }));
  await expect(resumed.execute(intent, send)).resolves.toEqual({
    status: "pending",
    key: "persistent-key",
  });
  expect(await resumed.pending()).toBeNull();
});

test("journal instances serialize writes and snapshot caller body before asynchronous storage", async () => {
  const data = new Map<string, string>();
  let release!: () => void;
  const storage = {
    getItem: async (k: string) => data.get(k) ?? null,
    setItem: async (k: string, v: string) => {
      data.set(k, v);
      await new Promise<void>((r) => {
        release = r;
      });
    },
    removeItem: async (k: string) => {
      data.delete(k);
    },
  };
  const original: Intent = {
    scope: "device|MANUAL",
    path: "/portfolios/MANUAL/orders",
    body: { quantity: "0.1" },
    idempotency_key: "original-snapshot-key",
  };
  const send = jest.fn(async (i: Intent) => ({ quantity: i.body.quantity }));
  const first = new IntentJournal(storage).execute(original, send);
  original.body.quantity = "999";
  await expect(
    new IntentJournal(storage).execute(
      { ...original, idempotency_key: "other-instance-key" },
      send,
    ),
  ).rejects.toThrow("sürüyor");
  expect(send).not.toHaveBeenCalled();
  release();
  await expect(first).resolves.toEqual({ quantity: "0.1" });
  expect(send).toHaveBeenCalledTimes(1);
});
