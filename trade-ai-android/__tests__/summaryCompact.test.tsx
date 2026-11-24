import React from "react";
import { render, waitFor, fireEvent } from "@testing-library/react-native";
import Result from "../app/result";
import { ThemeProvider } from "../src/theme";
import { useApp } from "../src/state";
import sample from "../docs/backend/v2_examples/analysis.json";
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: "test" }),
  router: { push: jest.fn() },
}));
test("Basic DEMO summary keeps detail access visible without passive follow card or technical wall", async () => {
  jest.mocked(useApp).mockReturnValue({
    mode: "demo",
    uiMode: "basic",
    history: [{ ...sample, analysis_id: "test" }],
    config: { session: "" },
    sessionInfo: null,
  } as unknown as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <Result />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Detaylı analizi aç")).toBeTruthy());
  expect(ui.queryByText("Analiz takip asistanı")).toBeNull();
  expect(ui.queryByText("Bu analizi takip et")).toBeNull();
  expect(ui.queryByText("Kayıtlı geçerlilik sonu")).toBeNull();
  expect(ui.queryByText("Analiz mumlarını yükle")).toBeNull();
  await fireEvent.press(ui.getByText(/Kaynak, risk ve teknik notlar/));
  expect(ui.getByText("Kayıtlı geçerlilik sonu")).toBeTruthy();
});

test("Basic summary prioritizes the selected strategy instead of unrelated rejected setups", async () => {
  const record = {
    ...sample,
    analysis_id: "test",
    data_mode: "live",
    router: {
      ...sample.router,
      strategy_id: "trend_momentum_v2",
      reason: "eligible_priority",
    },
    strategy_setups: {
      trend_momentum_v2: {
        reason: "continuation_confirmed_requires_legacy_confluence",
      },
      other: { reason: "entry_confirmation_missing" },
    },
  };
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    uiMode: "basic",
    history: [],
    api: { detail: async () => record },
    config: { session: "" },
    sessionInfo: null,
  } as unknown as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <Result />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText(/Router, koşulları sağlayan stratejiler/)).toBeTruthy(),
  );
  expect(ui.queryByText(/Giriş koşulları henüz teyit edilmedi/)).toBeNull();
});

test("optional immutable research catalogue is not requested until the user opens evidence", async () => {
  const record = { ...sample, analysis_id: "test", data_mode: "live" };
  const catalogue = jest.fn().mockResolvedValue(null);
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    uiMode: "basic",
    gatewayVerified: true,
    history: [],
    account: sample.risk_portfolio,
    config: { session: "fixture" },
    sessionInfo: {
      accounts: [sample.risk_portfolio],
      scopes: ["read"],
      capabilities: ["snapshot-research-v1"],
    },
    api: { detail: async () => record, researchCatalogue: catalogue },
  } as unknown as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <Result />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Detaylı analizi aç")).toBeTruthy());
  expect(catalogue).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByText(/Gelişmiş araştırma ve parametreler/));
  await waitFor(() => expect(catalogue).toHaveBeenCalledTimes(1));
  expect(catalogue).toHaveBeenCalledWith("test", sample.risk_portfolio);
});
