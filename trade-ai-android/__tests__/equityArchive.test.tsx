import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { useApp } from "../src/state";
import { ThemeProvider } from "../src/theme";
import { EquityArchivePanel } from "../src/EquityArchivePanel";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("../src/MiniPriceChart", () => ({ MiniPriceChart: () => null }));
const response = {
  status: "complete",
  points: [],
  next_cursor: "fixture-bound-cursor",
  has_more: true,
  watermark: 241,
  sampling: "raw",
  observations_scanned: 201,
  excluded_incomplete: 0,
};
function setup(supported = true) {
  const window = jest.fn().mockResolvedValue(response);
  jest
    .mocked(useApp)
    .mockReturnValue({
      mode: "live",
      account: "MANUAL",
      gatewayVerified: true,
      connectionKey: 1,
      config: { session: "fixture-session" },
      sessionInfo: {
        accounts: ["MANUAL"],
        scopes: ["read"],
        capabilities: supported ? ["equity-history-window-v1"] : [],
      },
      api: { equityWindow: window },
    } as unknown as ReturnType<typeof useApp>);
  return window;
}
test("old Gateway never requests unsupported archive", async () => {
  const window = setup(false);
  const ui = await render(
    <ThemeProvider>
      <EquityArchivePanel range="Tümü" />
    </ThemeProvider>,
  );
  expect(ui.getByText(/Eski Gateway/)).toBeTruthy();
  expect(window).not.toHaveBeenCalled();
});
test("older page uses opaque cursor and frozen date boundaries", async () => {
  const window = setup();
  const ui = await render(
    <ThemeProvider>
      <EquityArchivePanel range="7 gün" />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Daha eski gözlemler")).toBeTruthy());
  const first = window.mock.calls[0];
  await fireEvent.press(ui.getByText("Daha eski gözlemler"));
  await waitFor(() =>
    expect(window).toHaveBeenLastCalledWith(
      "MANUAL",
      first[1],
      first[2],
      "fixture-bound-cursor",
      "raw",
    ),
  );
});
test("oversized range reports incomplete rather than fake partial chart", async () => {
  const window = setup();
  window.mockResolvedValue({
    ...response,
    status: "incomplete_budget",
    has_more: true,
    next_cursor: null,
    sampling: "minmax",
  });
  const ui = await render(
    <ThemeProvider>
      <EquityArchivePanel range="Tümü" />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText(/Kısmi grafik üretilmedi/)).toBeTruthy(),
  );
  expect(ui.queryByText("Daha eski gözlemler")).toBeNull();
  await fireEvent.press(ui.getByText("Aralık özeti"));
  await waitFor(() =>
    expect(window).toHaveBeenLastCalledWith(
      "MANUAL",
      0,
      expect.any(Number),
      undefined,
      "minmax",
    ),
  );
});
