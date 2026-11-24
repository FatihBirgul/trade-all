import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { SnapshotResearchControls } from "../src/SnapshotResearchControls";
import { ThemeProvider } from "../src/theme";
import { useApp } from "../src/state";
import type { components } from "../src/api/schema";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
const id = "a".repeat(64),
  source = "b".repeat(64);
const analysis = {
  analysis_id: id,
  risk_portfolio: "MANUAL",
} as components["schemas"]["AnalysisResponse"];
const cat = {
  analysis_id: id,
  portfolio_id: "MANUAL",
  source_record_id: source,
  symbol: "BTCUSDT",
  timeframe: "1H",
  source: "saved-fixture",
  as_of_ms: 1800000000000,
  data_mode: "fixture",
  status: "available",
  anchors: [
    { open_time_ms: 1799992800000, close_time_ms: 1799996400000 },
    { open_time_ms: 1799996400000, close_time_ms: 1800000000000 },
  ],
  parameters: { ema_period: 20 },
  warmup_bars: 61,
};
function setup(supported = true) {
  const api = {
    researchCatalogue: jest.fn().mockResolvedValue(cat),
    computeResearch: jest
      .fn()
      .mockResolvedValue({
        ...cat,
        configuration_id: "c".repeat(64),
        indicator_research: { status: "available", methods: { ema: "100" } },
        anchored_vwap: { status: "available", value: "101" },
      }),
  };
  jest
    .mocked(useApp)
    .mockReturnValue({
      mode: "live",
      gatewayVerified: true,
      connectionKey: 1,
      config: { session: "fixture" },
      sessionInfo: {
        accounts: ["MANUAL"],
        scopes: ["read"],
        capabilities: supported ? ["snapshot-research-v1"] : [],
      },
      api,
    } as unknown as ReturnType<typeof useApp>);
  return api;
}
test("old gateway does not request or fabricate research", async () => {
  const api = setup(false);
  const ui = await render(
    <ThemeProvider>
      <SnapshotResearchControls analysis={analysis} />
    </ThemeProvider>,
  );
  expect(ui.getByText(/güncel Gateway/)).toBeTruthy();
  expect(api.researchCatalogue).not.toHaveBeenCalled();
});
test("actual closed anchor and source are sent; result remains descriptive", async () => {
  const api = setup();
  const ui = await render(
    <ThemeProvider>
      <SnapshotResearchControls analysis={analysis} />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText(/Anchor: /)).toBeTruthy());
  await fireEvent.press(ui.getByText("Sonraki anchor mumu"));
  await fireEvent.press(ui.getByText("Seçili kaynakla araştırmayı hesapla"));
  await waitFor(() => expect(ui.getByText("101")).toBeTruthy());
  expect(api.computeResearch).toHaveBeenCalledWith(
    id,
    "MANUAL",
    expect.objectContaining({
      source_record_id: source,
      anchor_ms: cat.anchors[1].open_time_ms,
      parameters: {},
    }),
  );
  expect(
    ui.getByText(/tick\/trade VWAP veya işlem teyidi değildir/),
  ).toBeTruthy();
  await fireEvent.press(ui.getByText("Önceki anchor mumu"));
  expect(ui.queryByText("101")).toBeNull();
});
test("server rejection produces error, never a stale successful result", async () => {
  const api = setup();
  api.computeResearch.mockRejectedValue(new Error("Fixture unavailable"));
  const ui = await render(
    <ThemeProvider>
      <SnapshotResearchControls analysis={analysis} />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText(/Anchor: /)).toBeTruthy());
  await fireEvent.press(ui.getByText("Seçili kaynakla araştırmayı hesapla"));
  await waitFor(() => expect(api.computeResearch).toHaveBeenCalled());
  expect(ui.queryByText("101")).toBeNull();
});
