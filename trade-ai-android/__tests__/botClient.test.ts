import { BotError, createBotApi, pairBot } from "../src/bot/client";
import type { BotConfig } from "../src/bot/types";

const config: BotConfig = {
  origin: "https://203-0-113-7.sslip.io",
  token: "t".repeat(43),
  pairedAt: 1,
};
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
  for (const body of [{}, { token: "kisa" }, { token: 5 }, null]) {
    const transport = jest.fn().mockResolvedValue(ok(body));
    await expect(pairBot("https://x.sslip.io", "482913", transport)).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
    });
  }
});

test("sends bearer token and parses status", async () => {
  const status = { equity: 3012.5, halted: false };
  const transport = jest.fn().mockResolvedValue(ok(status));
  await expect(createBotApi(config, transport).status()).resolves.toEqual(status);
  const [url, request] = transport.mock.calls[0];
  expect(url).toBe("https://203-0-113-7.sslip.io/status");
  expect(request.headers.Authorization).toBe("Bearer " + "t".repeat(43));
  expect(request.method).toBe("GET");
  expect(request.body).toBeUndefined();
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
  const transport = jest.fn().mockResolvedValue(ok({}));
  const api = createBotApi(config, transport);
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
  const calls = transport.mock.calls.map(([url, request]) => [
    request.method,
    url.replace(config.origin, ""),
    request.body ? JSON.parse(request.body) : null,
  ]);
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
  expect(transport.mock.calls[0][1].headers.Authorization).toBeUndefined(); // /health herkese açık
});

test("position ids are validated before building a url", async () => {
  const transport = jest.fn();
  await expect(createBotApi(config, transport).closePosition("../bot/stop")).rejects.toMatchObject({
    code: "INVALID_REQUEST",
  });
  expect(transport).not.toHaveBeenCalled();
});
