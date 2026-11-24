import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { useApp } from "../src/state";
import { ThemeProvider } from "../src/theme";
import { EquityHistoryPanel } from "../src/EquityHistoryPanel";
import { createApi } from "../src/api/client";
import type { components } from "../src/api/schema";
const mockChart = jest.fn((_props: unknown) => null);
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("../src/MiniPriceChart", () => ({
  MiniPriceChart: (props: unknown) => mockChart(props),
}));
type Point = components["schemas"]["EquityPoint"];
const point: Point = {
  schema_version: 1,
  snapshot_id: "a".repeat(64),
  portfolio_id: "MANUAL",
  data_mode: "live",
  sequence: 1,
  recorded_at_ms: 1800000000000,
  effective_at_ms: 1800000000000,
  source: { kind: "event", event_id: "b".repeat(64) },
  transaction_watermark: 1,
  cash_quote: "10000.00000000",
  reserved_cash_quote: "0.00000000",
  available_cash_quote: "10000.00000000",
  equity_quote: "10000.00000000",
  realized_pnl_quote: "0.00000000",
  unrealized_pnl_quote: "0.00000000",
  fees_quote: "0.00000000",
  open_positions: 0,
  closed_positions: 0,
  ambiguous_positions: 0,
  pending_orders: 0,
  marks: [],
  reservations: [],
  strategy_results: [],
  quality_status: "complete",
  chart_eligible: true,
  peak_equity_quote: "10000.00000000",
  maximum_drawdown_quote: "0.00000000",
  maximum_drawdown_pct: "0.00000000",
  proof_coverage: "domain_journal",
};
const data = {
  portfolio_id: "MANUAL",
  data_mode: "live",
  coverage: "forward_only",
  coverage_started_at_ms: 1800000000000,
  audit_coverage: "domain_journal",
  points: [point],
  has_more: false,
  period: "day",
  period_status: "complete",
  period_totals: [],
  note: "Controlled unit fixture, not market performance.",
};
function app(response: unknown = data, supported = true) {
  const history = jest.fn().mockResolvedValue(response);
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    account: "MANUAL",
    connectionKey: 1,
    config: { session: "fixture-mobile" },
    gatewayVerified: true,
    sessionInfo: {
      accounts: ["MANUAL"],
      scopes: ["read"],
      capabilities: supported ? ["equity-history-v1"] : [],
    },
    api: { equityHistory: history },
  } as unknown as ReturnType<typeof useApp>);
  return history;
}
beforeEach(() => mockChart.mockClear());
test("unsupported Gateway never loads or invents equity", async () => {
  const history = app(data, false);
  const ui = await render(
    <ThemeProvider>
      <EquityHistoryPanel />
    </ThemeProvider>,
  );
  expect(ui.getByText(/Örnek eğri oluşturulmadı/)).toBeTruthy();
  expect(history).not.toHaveBeenCalled();
  expect(mockChart).not.toHaveBeenCalled();
});
test("empty history stays empty with explicit forward-only message", async () => {
  app({ ...data, points: [] });
  const ui = await render(
    <ThemeProvider>
      <EquityHistoryPanel />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText(/kalıcı özsermaye gözlemi yok/)).toBeTruthy(),
  );
  expect(mockChart).not.toHaveBeenCalled();
});
test("stale mark is excluded from chart while actual complete records remain", async () => {
  app({
    ...data,
    points: [
      point,
      {
        ...point,
        sequence: 2,
        quality_status: "stale",
        chart_eligible: false,
        equity_quote: "999999.00000000",
      },
      { ...point, sequence: 3, equity_quote: "9999.00000000" },
    ],
  });
  const ui = await render(
    <ThemeProvider>
      <EquityHistoryPanel />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText(/Eski veya eksik mark/)).toBeTruthy(),
  );
  expect(mockChart).toHaveBeenLastCalledWith(
    expect.objectContaining({ prices: ["10000.00000000", "9999.00000000"] }),
  );
});
test("calendar period selector sends frozen explicit week and month query choices", async () => {
  const history = app();
  const ui = await render(
    <ThemeProvider>
      <EquityHistoryPanel />
    </ThemeProvider>,
  );
  await waitFor(() => expect(history).toHaveBeenCalled());
  await fireEvent.press(ui.getByText("Haftalık"));
  await waitFor(() =>
    expect(history).toHaveBeenLastCalledWith(
      "MANUAL",
      expect.any(Number),
      expect.any(Number),
      "week",
    ),
  );
  await fireEvent.press(ui.getByText("Aylık"));
  await waitFor(() =>
    expect(history).toHaveBeenLastCalledWith(
      "MANUAL",
      expect.any(Number),
      expect.any(Number),
      "month",
    ),
  );
});
test("live client rejects nested foreign-account and fixture observations", async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      ...data,
      points: [{ ...point, portfolio_id: "AUTO" }],
    }),
  });
  const api = createApi(
    { origin: "https://gateway.example.com", session: "fixture-mobile" },
    fetcher,
  );
  await expect(api.equityHistory("MANUAL")).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
  });
  fetcher.mockResolvedValue({
    ok: true,
    json: async () => ({
      ...data,
      points: [{ ...point, data_mode: "fixture" }],
    }),
  });
  await expect(api.equityHistory("MANUAL")).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
  });
});
test("window client validates nested account and escapes opaque cursor", async () => {
  const payload = {
    portfolio_id: "MANUAL",
    data_mode: "live",
    points: [{ ...point, portfolio_id: "AUTO" }],
    watermark: 1,
    request_cursor: "fixture",
    next_cursor: null,
    has_more: false,
    sampling: "raw",
    status: "complete",
    observations_scanned: 1,
    excluded_incomplete: 0,
  };
  const fetcher = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => payload });
  const api = createApi(
    { origin: "https://gateway.example.com", session: "fixture-mobile" },
    fetcher,
  );
  await expect(
    api.equityWindow("MANUAL", 0, 1800000000000, "a&b"),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  expect(String(fetcher.mock.calls[0][0])).toContain("cursor=a%26b");
});

test("window rejects invalid UTC timestamps before chart rendering", async () => {
  const fetcher = jest
    .fn()
    .mockResolvedValue({
      ok: true,
      json: async () => ({
        portfolio_id: "MANUAL",
        data_mode: "live",
        points: [{ ...point, recorded_at_ms: 9000000000000000 }],
        watermark: 1,
        request_cursor: "fixture",
        next_cursor: null,
        has_more: false,
        sampling: "raw",
        status: "complete",
        observations_scanned: 1,
        excluded_incomplete: 0,
      }),
    });
  const api = createApi(
    { origin: "https://gateway.example.com", session: "fixture-mobile" },
    fetcher,
  );
  await expect(
    api.equityWindow("MANUAL", 0, 1800000000000),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});
