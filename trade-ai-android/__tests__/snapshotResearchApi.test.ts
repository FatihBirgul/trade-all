import { createApi } from "../src/api/client";
import example from "../docs/backend/v2_examples/snapshot_research.json";
const config = {
  origin: "https://gateway.example.com",
  session: "fixture-session",
  scopes: ["read"],
};
const body = {
  source_record_id: example.source_record_id,
  symbol: "BTCUSDT" as const,
  timeframe: "1H" as const,
  anchor_ms: example.anchors[0].open_time_ms,
};
test("research calculation uses read scope and validates immutable source/account identity", async () => {
  const transport = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ ...example, data_mode: "live" }),
  });
  const r = await createApi(config, transport).computeResearch(
    example.analysis_id,
    "MANUAL",
    body,
  );
  expect(r.trade_permission).toBe(false);
  expect(JSON.parse(transport.mock.calls[0][1].body)).toEqual(body);
  for (const changed of [
    { portfolio_id: "AUTO" },
    { source_record_id: "0".repeat(64) },
    { symbol: "ETHUSDT" },
    { timeframe: "5m" },
    { trade_permission: true },
    { data_mode: "fixture" },
    { as_of_ms: Number.MAX_SAFE_INTEGER },
    { anchors: [{ open_time_ms: 1, close_time_ms: Number.MAX_SAFE_INTEGER }] },
    { anchors: [example.anchors[1], example.anchors[0]] },
    { anchors: [example.anchors[0], example.anchors[0]] },
    { anchors: Array(301).fill(example.anchors[0]) },
    { anchors: undefined },
  ]) {
    transport.mockResolvedValue({
      ok: true,
      json: async () => ({ ...example, data_mode: "live", ...changed }),
    });
    await expect(
      createApi(config, transport).computeResearch(
        example.analysis_id,
        "MANUAL",
        body,
      ),
    ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  }
});
test("missing read permission fails before transport and 403 does not revoke session", async () => {
  const transport = jest.fn();
  await expect(
    createApi({ ...config, scopes: [] }, transport).computeResearch(
      example.analysis_id,
      "MANUAL",
      body,
    ),
  ).rejects.toMatchObject({ code: "SCOPE_DENIED" });
  expect(transport).not.toHaveBeenCalled();
  const revoke = jest.fn();
  transport.mockResolvedValue({
    ok: false,
    status: 403,
    json: async () => ({ error: { code: "SCOPE_DENIED" } }),
  });
  await expect(
    createApi(config, transport, revoke).researchCatalogue(
      example.analysis_id,
      "MANUAL",
    ),
  ).rejects.toMatchObject({ status: 403 });
  expect(revoke).not.toHaveBeenCalled();
});
