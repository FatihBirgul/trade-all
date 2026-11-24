import React from "react";
import { render, waitFor } from "@testing-library/react-native";
import Home from "../app/(tabs)/index";
import { useApp } from "../src/state";
import { useMarketQuotes } from "../src/useMarketQuotes";
import { ThemeProvider } from "../src/theme";
import { emptyPortfolio } from "../src/domain/safety";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("../src/useMarketQuotes", () => ({ useMarketQuotes: jest.fn() }));
jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));
beforeEach(() => {
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    uiMode: "basic",
    history: [],
    config: { session: "test" },
    gatewayVerified: true,
    sessionInfo: {
      capabilities: ["market-quotes-v1"],
      accounts: ["AUTO", "MANUAL"],
    },
    api: {
      analyses: async () => [],
      portfolios: async () => [
        emptyPortfolio("AUTO"),
        emptyPortfolio("MANUAL"),
      ],
    },
  } as unknown as ReturnType<typeof useApp>);
});
test("empty market response shows no invented price or performance series", async () => {
  jest.mocked(useMarketQuotes).mockReturnValue({
    loading: false,
    now: 0,
    stale: false,
    scope: "test",
    reload: jest.fn(),
  });
  const ui = await render(
    <ThemeProvider>
      <Home />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(
      ui.getByText("Piyasa fiyatı yüklenemedi; örnek fiyat gösterilmedi."),
    ).toBeTruthy(),
  );
  expect(
    ui.queryByLabelText("Son kapalı 1 saatlik mumların fiyat grafiği"),
  ).toBeNull();
  expect(ui.queryByText("Piyasa verisi güncel")).toBeNull();
});
test("retained prices remain visibly stale after connection failure", async () => {
  jest.mocked(useMarketQuotes).mockReturnValue({
    loading: false,
    now: 100,
    stale: true,
    scope: "test",
    reload: jest.fn(),
    error: "Bağlantı kesildi",
    data: {
      fetched_at_ms: 1,
      stale: false,
      provider_status: "available",
      items: [
        {
          symbol: "BTCUSDT",
          price: "43210.25",
          change_percent_24h: "-1.25",
          source_time_ms: 1,
          chart_status: "unavailable",
          history: [],
        },
      ],
    },
  });
  const ui = await render(
    <ThemeProvider>
      <Home />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(
      ui.getByText("Güncel değil · Son başarılı fiyatlar gösteriliyor."),
    ).toBeTruthy(),
  );
  expect(
    ui.getByText("Güncel değil · Son başarılı fiyatlar gösteriliyor."),
  ).toBeTruthy();
  expect(ui.getByText("-1,25% · 24 sa.")).toBeTruthy();
  expect(ui.queryByText("Piyasa verisi güncel")).toBeNull();
});
