import { renewConnection } from "../src/api/renewal";
import type { GatewayConfig } from "../src/api/client";
const initial = (): GatewayConfig => ({
  origin: "https://pc.example.ts.net",
  session: "tg_" + "a".repeat(43),
  refresh: "tr_" + "b".repeat(43),
  deviceId: "device",
  renewalExpiresAt: Date.now() + 300000000,
  scopes: ["read"],
  accounts: ["MANUAL"],
});
const random = async (prefix: string) => prefix + "c".repeat(43);
const metadata = (expires = Date.now() + 86400000) => ({
  session_id: "new",
  device_id: "device",
  device_name: "Phone",
  expires_at_ms: expires,
  scopes: ["read"],
  accounts: ["MANUAL"],
  protocol_version: 1,
  renewal_expires_at_ms: Date.now() + 200000000,
});
test("lost acknowledgement retains encrypted proposal; restart sends identical body, promotes only after durable save", async () => {
  let stored = initial();
  const bodies: string[] = [];
  const save = async (value: GatewayConfig) => {
    stored = JSON.parse(JSON.stringify(value));
  };
  const first = jest.fn(async (_url, init) => {
    bodies.push(init.body);
    throw new Error("lost");
  });
  await expect(
    renewConnection(stored, save, random, first),
  ).rejects.toMatchObject({ code: "RENEWAL_UNCERTAIN" });
  expect(stored.pendingRenewal).toBeDefined();
  expect(stored.session).toBe(initial().session);
  const second = jest.fn(async (_url, init) => {
    bodies.push(init.body);
    return { ok: true, json: async () => metadata() };
  });
  const result = await renewConnection(
    stored,
    save,
    random,
    second as unknown as typeof fetch,
  );
  expect(bodies[0]).toBe(bodies[1]);
  expect(result.config.session).toBe("tg_" + "c".repeat(43));
  expect(stored.pendingRenewal).toBeUndefined();
});
test("storage failure prevents network; concurrent refresh never invents a different successor", async () => {
  const transport = jest.fn();
  await expect(
    renewConnection(
      initial(),
      async () => {
        throw new Error("disk");
      },
      random,
      transport,
    ),
  ).rejects.toThrow("disk");
  expect(transport).not.toHaveBeenCalled();
  let release!: (value: unknown) => void;
  const first = renewConnection(
    initial(),
    async () => {},
    random,
    jest.fn().mockReturnValue(
      new Promise((r) => {
        release = r;
      }),
    ),
  );
  await expect(
    renewConnection(initial(), async () => {}, random, transport),
  ).rejects.toMatchObject({ code: "RENEWAL_IN_PROGRESS" });
  while (!release) await Promise.resolve();
  release({ ok: true, json: async () => metadata() });
  await first;
});
test.each([401])(
  "revoked or expired renewal requires local pairing (%i)",
  async (status) => {
    await expect(
      renewConnection(
        initial(),
        async () => {},
        random,
        jest.fn().mockResolvedValue({ ok: false, status }),
      ),
    ).rejects.toMatchObject({ code: "LOCAL_PAIR_REQUIRED" });
  },
);
test("gateway 403 erişim sınırı yenileme yetkisini silmez", async () => {
  const save = jest.fn();
  await expect(
    renewConnection(initial(), save, random, jest.fn().mockResolvedValue({ ok: false, status: 403 })),
  ).rejects.toMatchObject({ code: "HTTP_403", status: 403 });
  expect(save).toHaveBeenCalledTimes(1);
  expect(save.mock.calls[0][0].pendingRenewal).toBeDefined();
});
test("grant expansion, wrong device and corrupt response cannot promote tokens", async () => {
  for (const value of [
    { ...metadata(), accounts: ["AUTO"] },
    { ...metadata(), scopes: ["read", "scanner:write"] },
    { ...metadata(), device_id: "other" },
    {},
  ]) {
    const save = jest.fn();
    await expect(
      renewConnection(
        initial(),
        save,
        random,
        jest.fn().mockResolvedValue({ ok: true, json: async () => value }),
      ),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    expect(save).toHaveBeenCalledTimes(1);
    expect(save.mock.calls[0][0].pendingRenewal).toBeDefined();
  }
});
test("late committed receipt preserves expiry and rotates known successor, no PC needed", async () => {
  const receipt = metadata();
  const transport = jest
    .fn()
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...receipt, expires_at_ms: Date.now() - 1 }),
    })
    .mockResolvedValueOnce({ ok: true, json: async () => receipt });
  let counter = 0;
  const random = async (prefix: string) =>
    prefix + String(counter++).padStart(43, "x");
  await renewConnection(initial(), async () => {}, random, transport);
  const first = JSON.parse(transport.mock.calls[0][1].body),
    next = JSON.parse(transport.mock.calls[1][1].body);
  expect(next.refresh_token).toBe(first.next_refresh_token);
  expect(next.request_id).not.toBe(first.request_id);
});
