import { createApi, ApiError } from "../src/api/client";
import analysis from "../docs/backend/v2_examples/analysis.json";
const config = {
  origin: "https://gateway.example.com",
  session: "test-mobile-session-not-a-secret",
};
test("no configured gateway means no network and no fake success", async () => {
  const transport = jest.fn();
  await expect(
    createApi({ origin: "", session: "" }, transport).health(),
  ).rejects.toMatchObject({ code: "UNCONFIGURED" });
  expect(transport).not.toHaveBeenCalled();
});
test("analysis always overrides auto_paper to false", async () => {
  const transport = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ ...analysis, data_mode: "live" }),
  });
  await createApi(config, transport).analyze({
    idempotency_key: "test-key-001",
    auto_paper: true,
  });
  expect(JSON.parse(transport.mock.calls[0][1].body).auto_paper).toBe(false);
});
test("network failure on mutation is uncertain and not retried", async () => {
  const transport = jest.fn().mockRejectedValue(new Error("network"));
  await expect(
    createApi(config, transport).analyze({ idempotency_key: "test-key-001" }),
  ).rejects.toMatchObject({ uncertain: true });
  expect(transport).toHaveBeenCalledTimes(1);
});
test("401 returned honestly", async () => {
  const transport = jest.fn().mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({
      error: { code: "UNAUTHORIZED", message: "private debug" },
    }),
  });
  await expect(createApi(config, transport).health()).rejects.toMatchObject({
    code: "UNAUTHORIZED",
    uncertain: false,
  });
});
test("500 mutation is uncertain", async () => {
  const transport = jest.fn().mockResolvedValue({
    ok: false,
    status: 500,
    json: async () => ({ error: { code: "V2_INTERNAL_ERROR" } }),
  });
  await expect(createApi(config, transport).tick()).rejects.toBeInstanceOf(
    ApiError,
  );
});

test("MANUAL analizi AUTO risk hesabı yanıtını kabul etmez", async () => {
  const transport = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      ...analysis,
      data_mode: "live",
      risk_portfolio: "AUTO",
    }),
  });
  await expect(
    createApi(config, transport).analyze({
      risk_portfolio: "MANUAL",
      idempotency_key: "manual-test",
    }),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE", uncertain: true });
});

test("401 oturum reddi gövde olmadan da Türkçe hataya dönüşür", async () => {
  const revoked = jest.fn();
  const transport = jest.fn().mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => {
      throw new Error("html");
    },
  });
  await expect(
    createApi(config, transport, revoked).health(),
  ).rejects.toMatchObject({ code: "UNAUTHORIZED", uncertain: false });
  expect(revoked).toHaveBeenCalledTimes(1);
});

test("geçerli oturumun kapsam reddi oturumu iptal etmez", async () => {
  const revoked = jest.fn();
  const transport = jest.fn().mockResolvedValue({
    ok: false,
    status: 403,
    json: async () => ({ error: { code: "SCOPE_DENIED" } }),
  });
  await expect(createApi(config, transport, revoked).follows()).rejects.toMatchObject({
    code: "SCOPE_DENIED",
    uncertain: false,
    status: 403,
  });
  expect(revoked).not.toHaveBeenCalled();
});

test("AUTO hareketlerinde MANUAL satırı tüm yanıtı reddettirir", async () => {
  const order = {
    adverse_rate: "0",
    analysis_id: "test",
    created_at_ms: 1,
    data_mode: "live",
    execution_model: "paper",
    expires_at_ms: 2,
    fee_rate: "0",
    order_id: "order-test",
    paper_only: true,
    participation_fraction: "0.1",
    portfolio_id: "MANUAL",
    quantity: "1",
    remaining_quantity: "1",
    risk: {},
    status: "pending",
    symbol: "BTCUSDT",
  };
  const transport = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => [order] });
  await expect(
    createApi(config, transport).orders("AUTO"),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE", uncertain: false });
  transport.mockResolvedValue({
    ok: true,
    json: async () => [{ ...order, portfolio_id: "AUTO" }],
  });
  await expect(
    createApi(config, transport).orders("AUTO"),
  ).resolves.toHaveLength(1);
});

test("oturum değiştikten sonra geç gelen başarılı yanıt gösterilmez", async () => {
  let resolve!: (value: unknown) => void;
  const transport = jest.fn().mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  const api = createApi(config, transport);
  const pending = api.analyze({ idempotency_key: "late-session-test" });
  api.dispose();
  resolve({ ok: true, json: async () => ({ ...analysis, data_mode: "live" }) });
  await expect(pending).rejects.toMatchObject({ code: "SESSION_CHANGED" });
});

test("late 401 from disposed session cannot revoke replacement session", async () => {
  let resolve!: (value: unknown) => void;
  const revoked = jest.fn();
  const api = createApi(
    config,
    jest.fn().mockReturnValue(
      new Promise((r) => {
        resolve = r;
      }),
    ),
    revoked,
  );
  const pending = api.health();
  api.dispose();
  resolve({ ok: false, status: 401, json: async () => ({}) });
  await expect(pending).rejects.toMatchObject({ code: "SESSION_CHANGED" });
  expect(revoked).not.toHaveBeenCalled();
});

test("follow mutation rejects wrong origin or tracking identity without replay", async () => {
  const record = {
    tracking_id: "b".repeat(64),
    origin_analysis_id: "c".repeat(64),
    last_analysis_id: "c".repeat(64),
    portfolio_id: "AUTO",
    symbol: "BTCUSDT",
    timeframe: "1H",
    data_mode: "live",
    enabled: true,
    status: "waiting",
    last_checked_ms: null,
    last_direction: "WAIT",
    last_reason: "provider_unavailable",
    notified_changes: 0,
    worker_running: false,
    paper_only: true,
  };
  const transport = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => record });
  const api = createApi(config, transport);
  await expect(api.follow("a".repeat(64))).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
    uncertain: true,
  });
  await expect(api.changeFollow("a".repeat(64), false)).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
    uncertain: true,
  });
  expect(transport).toHaveBeenCalledTimes(2);
});
