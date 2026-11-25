import { BotError, createBotApi, pairBot } from "../src/bot/client";
import type { BotConfig } from "../src/bot/types";

const config: BotConfig = {
  origin: "https://203-0-113-7.sslip.io",
  token: "t".repeat(43),
  pairedAt: 1,
};
const STATUS = {
  currency: "USC",
  balance: 3000,
  equity: 3012.5,
  margin_free: 2890,
  pnl_today: { bot: 1, manual: 0, total: 1 },
  open_bot: 1,
  open_manual: 0,
  halted: false,
  halt_reason: null,
  stopped: false,
  dry_run: true,
  start_capital: 3000,
  last_scan_at: null,
  heartbeat_at: 1,
  stream_connected: true,
  started: true,
};
const POSITION = { position_id: "2001", symbol: "EURUSD", side: "BUY", volume: 0.05, entry: 1.1 };
const ok = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
});

test("pairs with code and stores token", async () => {
  const transport = jest.fn().mockResolvedValue(ok({ token: "x".repeat(43) }));
  const result = await pairBot(" https://203-0-113-7.sslip.io/ ", "482913", transport);
  expect(result.origin).toBe("https://203-0-113-7.sslip.io");
  expect(result.token).toBe("x".repeat(43));
  const [url, request] = transport.mock.calls[0];
  expect(url).toBe("https://203-0-113-7.sslip.io/pair");
  expect(request.method).toBe("POST");
  expect(JSON.parse(request.body)).toEqual({ code: "482913" });
  expect(request.headers.Authorization).toBeUndefined();
  expect(request.redirect).toBe("error");
  expect(transport).toHaveBeenCalledTimes(1);
});

test("rejects http and malformed code without network", async () => {
  const transport = jest.fn();
  await expect(pairBot("http://203-0-113-7.sslip.io", "482913", transport)).rejects.toMatchObject({
    code: "INVALID_ORIGIN",
  });
  await expect(pairBot("https://x.sslip.io/yol", "482913", transport)).rejects.toMatchObject({
    code: "INVALID_ORIGIN",
  });
  for (const code of ["12345", "1234567", "12a456", ""])
    await expect(pairBot("https://x.sslip.io", code, transport)).rejects.toMatchObject({ code: "INVALID_CODE" });
  expect(transport).not.toHaveBeenCalled();
});

test("wrong pairing code shows a clear message and is not retried", async () => {
  const transport = jest.fn().mockResolvedValue(ok({ detail: "kod geçersiz ya da süresi dolmuş" }, 401));
  await expect(pairBot("https://x.sslip.io", "000000", transport)).rejects.toMatchObject({
    code: "PAIR_REJECTED",
    message: "Kod geçersiz ya da süresi dolmuş. Sunucuda yeni kod üretin.",
  });
  expect(transport).toHaveBeenCalledTimes(1);
});

test("pair rejects a response without a usable token", async () => {
  for (const body of [{}, { token: "kisa" }, { token: 5 }]) {
    const transport = jest.fn().mockResolvedValue(ok(body));
    await expect(pairBot("https://x.sslip.io", "482913", transport)).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  }
});

test("pairing failures tell the user what to check instead of 'result uncertain'", async () => {
  const offline = jest.fn().mockRejectedValue(new TypeError("Network request failed"));
  const error = await pairBot("https://yanlis-adres.sslip.io", "482913", offline).catch((e) => e);
  expect(error).toMatchObject({ code: "PAIR_NETWORK", uncertain: false });
  expect(error.message).toContain("Adresi ve internet bağlantınızı kontrol edin");
  expect(error.message).not.toContain("belirsiz");
  expect(offline).toHaveBeenCalledTimes(1);

  const wrongHost = jest.fn().mockResolvedValue(ok({ detail: "Not Found" }, 404));
  await expect(pairBot("https://x.sslip.io", "482913", wrongHost)).rejects.toMatchObject({
    code: "PAIR_NOT_FOUND",
    message: "Bu adreste Trade Bot bulunamadı. Sunucu adresini kontrol edin.",
  });
  const notJson = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => { throw new Error("html"); } });
  await expect(pairBot("https://x.sslip.io", "482913", notJson)).rejects.toMatchObject({ code: "PAIR_NETWORK" });
});

test("sends bearer token and parses status", async () => {
  const transport = jest.fn().mockResolvedValue(ok(STATUS));
  await expect(createBotApi(config, transport).status()).resolves.toEqual(STATUS);
  const [url, request] = transport.mock.calls[0];
  expect(url).toBe("https://203-0-113-7.sslip.io/status");
  expect(request.headers.Authorization).toBe("Bearer " + "t".repeat(43));
  expect(request.method).toBe("GET");
  expect(request.body).toBeUndefined();
  expect(request.redirect).toBe("error");
  expect(url).not.toContain("t".repeat(43)); // token asla adres satırında taşınmaz
});

test("a malformed success response is an error, never 'no positions'", async () => {
  const api = (body: unknown) => createBotApi(config, jest.fn().mockResolvedValue(ok(body)));
  for (const body of [{}, [], { positions: "x" }, { positions: [{ symbol: "EURUSD" }] }, { positions: null }])
    await expect(api(body).positions()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  await expect(api({ positions: [] }).positions()).resolves.toEqual([]);
  await expect(api({ positions: [POSITION] }).positions()).resolves.toEqual([POSITION]);
  for (const body of [[], {}, { ...STATUS, pnl_today: null }, { ...STATUS, halted: "no" }])
    await expect(api(body).status()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  for (const body of [{}, { events: [{ id: "1" }] }])
    await expect(api(body).events(0)).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});

test("a response from another origin is rejected", async () => {
  const redirected = { ...ok(STATUS), url: "https://baska-sunucu.example/status" };
  await expect(createBotApi(config, jest.fn().mockResolvedValue(redirected)).status()).rejects.toMatchObject({
    code: "REDIRECTED",
  });
  const same = { ...ok(STATUS), url: config.origin + "/status" };
  await expect(createBotApi(config, jest.fn().mockResolvedValue(same)).status()).resolves.toEqual(STATUS);
  const lookalike = { ...ok(STATUS), url: config.origin + ".evil.example/status" };
  await expect(createBotApi(config, jest.fn().mockResolvedValue(lookalike)).status()).rejects.toMatchObject({
    code: "REDIRECTED",
  });
});

test("gateway errors and unreadable success on a mutation are uncertain and not retried", async () => {
  for (const status of [502, 503, 504]) {
    const transport = jest.fn().mockResolvedValue(ok({ detail: "Bad Gateway" }, status));
    const error = await createBotApi(config, transport).closeAll().catch((e) => e);
    expect(error).toMatchObject({ code: "HTTP_" + status, uncertain: true, status });
    expect(error.message).toContain("belirsiz");
    expect(transport).toHaveBeenCalledTimes(1);
  }
  const unreadable = jest.fn().mockResolvedValue({ ok: true, status: 200, json: async () => { throw new Error("kesildi"); } });
  await expect(createBotApi(config, unreadable).closePosition("2001")).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
    uncertain: true,
  });
  expect(unreadable).toHaveBeenCalledTimes(1);
  // Okuma isteklerinde aynı hatalar belirsiz değildir.
  const readFailure = jest.fn().mockResolvedValue(ok({ detail: "Bad Gateway" }, 502));
  await expect(createBotApi(config, readFailure).status()).rejects.toMatchObject({ uncertain: false });
  // Sunucunun açık reddi (409/422) belirsiz değildir.
  const conflict = jest.fn().mockResolvedValue(ok({ detail: "bekleyen istek var" }, 409));
  await expect(createBotApi(config, conflict).closePosition("2001")).rejects.toMatchObject({ uncertain: false });
});

test("unconfigured client never touches the network", async () => {
  const transport = jest.fn();
  await expect(createBotApi(null, transport).status()).rejects.toMatchObject({ code: "UNCONFIGURED" });
  expect(transport).not.toHaveBeenCalled();
});

test("mutation network error is uncertain and not retried", async () => {
  const transport = jest.fn().mockRejectedValue(new TypeError("Network request failed"));
  const api = createBotApi(config, transport);
  await expect(api.closePosition("2001")).rejects.toMatchObject({ code: "NETWORK", uncertain: true });
  expect(transport).toHaveBeenCalledTimes(1);
  await expect(api.status()).rejects.toMatchObject({ code: "NETWORK", uncertain: false });
  expect(transport).toHaveBeenCalledTimes(2);
});

test("401 calls onUnauthorized", async () => {
  const onUnauthorized = jest.fn();
  const transport = jest.fn().mockResolvedValue(ok({ detail: "geçersiz ya da eksik token" }, 401));
  await expect(createBotApi(config, transport, onUnauthorized).positions()).rejects.toMatchObject({
    code: "UNAUTHORIZED",
    status: 401,
  });
  expect(onUnauthorized).toHaveBeenCalledTimes(1);
});

test("409 carries server detail", async () => {
  const detail = "toplam kayıp sınırı nedeniyle durdu; devam için confirm_halt=true gerekli";
  const transport = jest.fn().mockResolvedValue(ok({ detail }, 409));
  const error = await createBotApi(config, transport)
    .resume()
    .catch((e) => e);
  expect(error).toBeInstanceOf(BotError);
  expect(error).toMatchObject({ code: "HTTP_409", status: 409, detail, message: detail });
});

test("422 validation list becomes a readable message", async () => {
  const transport = jest
    .fn()
    .mockResolvedValue(ok({ detail: [{ loc: ["body", "sl"], msg: "Input should be greater than 0" }] }, 422));
  await expect(createBotApi(config, transport).patchPosition("1", { sl: -1 })).rejects.toMatchObject({
    code: "HTTP_422",
    message: "Girilen değer geçersiz: sl",
  });
});

test("closeAll sends exact confirm phrase", async () => {
  const transport = jest.fn().mockResolvedValue(ok({ requested: 2, skipped: [], stopped: true }));
  await createBotApi(config, transport).closeAll();
  const [url, request] = transport.mock.calls[0];
  expect(url).toBe("https://203-0-113-7.sslip.io/bot/close-all");
  expect(JSON.parse(request.body)).toEqual({ confirm: "CLOSE-ALL" });
});

test("endpoints use the documented paths and bodies", async () => {
  const transport = jest.fn(async (url: string) => {
    const path = String(url).replace(config.origin, "");
    if (path === "/status") return ok(STATUS);
    if (path === "/positions") return ok({ positions: [] });
    if (path.startsWith("/events")) return ok({ events: [] });
    return ok({});
  });
  const api = createBotApi(config, transport as unknown as typeof fetch);
  await api.health();
  await api.positions();
  await api.patchPosition("2001", { sl: 1.0972, manage: false });
  await api.closePosition("2001", 0.05);
  await api.closePosition("2001");
  await api.stop();
  await api.resume(true);
  await api.events(41);
  await api.recentEvents(50);
  await api.registerDevice("ExponentPushToken[abc]");
  const calls = (transport.mock.calls as unknown as [string, { method: string; body?: string; redirect?: string; headers: Record<string, string> }][]).map(
    ([url, request]) => [request.method, url.replace(config.origin, ""), request.body ? JSON.parse(request.body) : null],
  );
  expect(calls).toEqual([
    ["GET", "/health", null],
    ["GET", "/positions", null],
    ["PATCH", "/positions/2001", { sl: 1.0972, manage: false }],
    ["POST", "/positions/2001/close", { volume: 0.05 }],
    ["POST", "/positions/2001/close", {}],
    ["POST", "/bot/stop", null],
    ["POST", "/bot/resume", { confirm_halt: true }],
    ["GET", "/events?after=41", null],
    ["GET", "/events?newest=true&limit=50", null],
    ["POST", "/devices", { expo_token: "ExponentPushToken[abc]" }],
  ]);
  const requests = (transport.mock.calls as unknown as [string, { redirect?: string; headers: Record<string, string> }][]).map(
    ([, request]) => request,
  );
  expect(requests[0].headers.Authorization).toBeUndefined(); // /health herkese açık
  expect(requests.every((request) => request.redirect === "error")).toBe(true);
  expect(requests.slice(1).every((request) => request.headers.Authorization === "Bearer " + config.token)).toBe(true);
});

test("position ids are validated before building a url", async () => {
  const transport = jest.fn().mockResolvedValue(ok({ order: "k" }));
  for (const bad of ["../bot/stop", "20 01", "2001?x=1", "", "a".repeat(65)])
    await expect(createBotApi(config, transport).closePosition(bad)).rejects.toMatchObject({
      code: "INVALID_REQUEST",
    });
  expect(transport).not.toHaveBeenCalled();
  // Kimlik biçimi broker'a aittir: yalnızca rakam varsayılmaz.
  await createBotApi(config, transport).closePosition("AB-12_cd");
  expect(transport.mock.calls[0][0]).toBe(config.origin + "/positions/AB-12_cd/close");
});

test("going live re-reads settings and sends the separate confirmation; going back to dry run does not", async () => {
  const settings = { dry_run: true, risk: { risk_pct: 0.5 }, strategy_modes: { fx_trend_momentum_v6: "shadow" } };
  const transport = jest.fn(async (_url: string, request: { method: string; body?: string }) =>
    request.method === "GET" ? ok(settings) : ok(JSON.parse(request.body ?? "{}")),
  );
  const api = createBotApi(config, transport as unknown as typeof fetch);
  await api.setDryRun(false);
  const calls = transport.mock.calls as unknown as [string, { method: string; body?: string }][];
  expect(calls.map(([url, request]) => [request.method, url.replace(config.origin, "")])).toEqual([
    ["GET", "/settings"],
    ["PUT", "/settings?confirm_live=true"],
  ]);
  // Okunan ayarlar aynen geri gönderilir; yalnızca dry_run değişir (strateji kipleri korunur).
  expect(JSON.parse(calls[1][1].body ?? "")).toEqual({ ...settings, dry_run: false });
  transport.mockClear();
  await api.setDryRun(true);
  expect((transport.mock.calls as unknown as [string][])[1][0]).toBe(config.origin + "/settings");

  const refused = jest.fn(async (_url: string, request: { method: string }) =>
    request.method === "GET" ? ok(settings) : ok({ detail: "strateji bu yoldan canlıya alınamaz" }, 409),
  );
  await expect(createBotApi(config, refused as unknown as typeof fetch).setDryRun(false)).rejects.toMatchObject({
    code: "HTTP_409",
    message: "strateji bu yoldan canlıya alınamaz",
    uncertain: false,
  });
  expect(refused).toHaveBeenCalledTimes(2); // yeniden denenmez
});

test("updateSettings applies the change to freshly read settings and never alters mode or strategy modes", async () => {
  const fresh = {
    risk: { risk_pct: 0.5, max_open_bot: 2 },
    news: { enabled: true, window_minutes: 30 },
    fusion: { enabled: true, min_score: 40, mid_score: 60, high_score: 80 },
    dry_run: true,
    strategy_modes: { fx_trend_momentum_v6: "shadow" },
  };
  const transport = jest.fn(async (_url: string, request: { method: string; body?: string }) =>
    request.method === "GET" ? ok(fresh) : ok(JSON.parse(request.body ?? "{}")),
  );
  const api = createBotApi(config, transport as unknown as typeof fetch);
  await api.updateSettings((current) => {
    current.risk.risk_pct = 0.25;
    current.dry_run = false; // form bunu değiştirmeye çalışsa bile
    current.strategy_modes = {}; // duraklatılmış stratejiyi canlıya döndürmeye çalışsa bile
    return current;
  });
  const calls = transport.mock.calls as unknown as [string, { method: string; body?: string }][];
  expect(calls.map(([url, request]) => [request.method, url.replace(config.origin, "")])).toEqual([
    ["GET", "/settings"],
    ["PUT", "/settings"], // canlıya geçiş onayı (confirm_live) bu yoldan asla gönderilmez
  ]);
  expect(JSON.parse(calls[1][1].body ?? "")).toEqual({ ...fresh, risk: { risk_pct: 0.25, max_open_bot: 2 } });
});

test("manual trade and strategy mode requests", async () => {
  const transport = jest.fn().mockResolvedValue(ok({ order: "man-1", state: "ACKED", lots: 0.08, sl: 1, tp: null }));
  const api = createBotApi(config, transport);
  const trade = { symbol: "EURUSD", side: "BUY" as const, sl_distance: 0.002 };
  await api.openTrade(trade, "11111111-2222-3333-4444-555555555555");
  expect(JSON.parse(transport.mock.calls[0][1].body)).toEqual({ ...trade, client_id: "11111111-2222-3333-4444-555555555555" });
  await expect(async () => api.openTrade(trade, "kisa")).rejects.toMatchObject({ code: "INVALID_REQUEST" });
  await api.setStrategyMode("tb_ema_pullback_v1", "live");
  expect(JSON.parse(transport.mock.calls[1][1].body)).toEqual({ mode: "live", confirm: false }); // onay varsayılan olarak yok
  await api.setStrategyMode("tb_ema_pullback_v1", "live", true);
  expect(transport.mock.calls[2][0]).toBe(config.origin + "/strategies/tb_ema_pullback_v1/mode");
  await expect(async () => api.setStrategyMode("../bot/stop", "off")).rejects.toMatchObject({ code: "INVALID_REQUEST" });
  expect(transport).toHaveBeenCalledTimes(3);
});
