import { pairDevice, mobileSession } from "../src/api/gateway";
const metadata = () => ({
  session_id: "test-session",
  device_id: "test-device",
  device_name: "Telefon",
  expires_at_ms: Date.now() + 60000,
  scopes: ["read", "analyze"],
  accounts: ["AUTO", "MANUAL"],
  protocol_version: 1,
});
test("eşleştirme kodu yalnız HTTPS JSON gövdesinde gider, oturum ekranda yazılmaz", async () => {
  const transport = jest
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => ({ ...metadata(), session: "tg_" + "a".repeat(43) }),
    });
  await expect(
    pairDevice(
      "https://pc.example.ts.net",
      "a".repeat(32),
      "test-device",
      "Telefon",
      transport,
    ),
  ).resolves.toHaveProperty("session");
  const [url, request] = transport.mock.calls[0];
  expect(url).toBe("https://pc.example.ts.net/gateway/pair");
  expect(url).not.toContain("a".repeat(32));
  expect(JSON.parse(request.body).code).toBe("a".repeat(32));
  expect(request.headers.Authorization).toBeUndefined();
  expect(transport).toHaveBeenCalledTimes(1);
});
test("eski veya belirsiz oturum metadata yanıtı reddedilir", async () => {
  for (const value of [
    { ...metadata(), expires_at_ms: 1 },
    { ...metadata(), scopes: ["admin"] },
    { ...metadata(), accounts: ["REAL"] },
  ]) {
    const transport = jest
      .fn()
      .mockResolvedValue({ ok: true, json: async () => value });
    await expect(
      mobileSession(
        { origin: "https://pc.example.ts.net", session: "test" },
        transport,
      ),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  }
});
test("eşleştirme ağ hatası otomatik tekrar edilmez", async () => {
  const transport = jest.fn().mockRejectedValue(new Error("offline"));
  await expect(
    pairDevice(
      "https://pc.example.ts.net",
      "a".repeat(32),
      "device",
      "Telefon",
      transport,
    ),
  ).rejects.toMatchObject({ code: "NETWORK" });
  expect(transport).toHaveBeenCalledTimes(1);
});

test("gateway 403 erişim sınırı geçerli oturumu iptal edilmiş sayılmaz", async () => {
  const transport = jest.fn().mockResolvedValue({ ok: false, status: 403 });
  await expect(
    mobileSession({ origin: "https://pc.example.ts.net", session: "test" }, transport),
  ).rejects.toMatchObject({ code: "HTTP_403", status: 403 });
});
