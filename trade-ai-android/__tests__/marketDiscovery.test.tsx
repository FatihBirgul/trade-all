import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import MarketDiscovery from "../app/market-discovery";
import { ThemeProvider } from "../src/theme";
import { useApp } from "../src/state";
import { ApiError, createApi } from "../src/api/client";
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: jest.requireActual("react-native").View,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), back: jest.fn(), canGoBack: () => false },
}));
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-crypto", () => ({
  randomUUID: () => "fixture-discovery-command",
}));
const config = {
  portfolio_id: "MANUAL",
  revision: 0,
  enabled: false,
  discovery: false,
  favorites: [],
  interval_seconds: 300,
  timeframe: "5m",
  profile_id: null,
  ttl_seconds: 3600,
};
function setup(write = false, cap = true) {
  const api = {
    markets: jest
      .fn()
      .mockResolvedValue({
        data_mode: "live",
        items: ["BTCUSDT", "ETHUSDT", "SOLUSDT"].map((symbol) => ({
          symbol,
          market: "crypto_spot",
          contract_type: "spot",
          quote_currency: "USDT",
          venue: "test",
          provider: "configured_provider",
          availability: "configured",
          provider_status: "not_probed",
        })),
      }),
    analyses: jest.fn().mockResolvedValue([]),
    marketScanner: jest.fn().mockResolvedValue({
      portfolio_id: "MANUAL",
      data_mode: "live",
      config,
      runtime: {
        activation: {
          state: "blocked",
          reasons: ["runtime_not_running"],
          runtime_available: false,
          account_enabled: false,
          starts_process: false,
        },
        worker_active: false,
        provider_status: "not_probed",
        eligible: 0,
        screened: 0,
        backlog: 0,
      },
      jobs: [],
      universe: {},
    }),
    opportunities: jest
      .fn()
      .mockResolvedValue({ items: [], next_offset: null }),
    configureMarketScanner: jest
      .fn()
      .mockResolvedValue({ config: { ...config, revision: 1 } }),
  };
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    account: "MANUAL",
    setAccount: jest.fn(),
    connectionKey: 1,
    gatewayVerified: true,
    config: { session: "fixture" },
    sessionInfo: {
      accounts: ["MANUAL"],
      scopes: ["read", ...(write ? ["discovery:write"] : [])],
      capabilities: cap ? ["dual-scanner-v1", "scanner-activation-v1"] : [],
    },
    api,
  } as unknown as ReturnType<typeof useApp>);
  return api;
}
test("old gateway never requests unsupported scanner or fabricates opportunities", async () => {
  const api = setup(false, false);
  const ui = await render(
    <ThemeProvider>
      <MarketDiscovery />
    </ThemeProvider>,
  );
  expect(ui.getByText(/Güncel Gateway, canlı bağlantı/)).toBeTruthy();
  expect(api.marketScanner).not.toHaveBeenCalled();
  expect(api.opportunities).not.toHaveBeenCalled();
});
test("readonly empty state distinguishes inactive worker from reachable gateway", async () => {
  const api = setup();
  const ui = await render(
    <ThemeProvider>
      <MarketDiscovery />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Aktif worker doğrulanmadı")).toBeTruthy(),
  );
  expect(ui.getByText(/Bu hesapta kayıtlı fırsat yok/)).toBeTruthy();
  await fireEvent.press(ui.getByText("Yapılandırmayı kaydet"));
  expect(api.configureMarketScanner).not.toHaveBeenCalled();
});
test("lost configuration acknowledgement retries exact frozen command", async () => {
  const api = setup(true);
  api.configureMarketScanner.mockRejectedValueOnce(
    new ApiError("NETWORK", true),
  );
  const ui = await render(
    <ThemeProvider>
      <MarketDiscovery />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Yapılandırmayı kaydet")).toBeTruthy(),
  );
  await waitFor(() => expect(ui.getByText("+ BTCUSDT")).toBeTruthy());
  await fireEvent.press(ui.getByText("+ BTCUSDT"));
  await fireEvent.press(ui.getByText("Yapılandırmayı kaydet"));
  await waitFor(() =>
    expect(ui.getByText("Aynı isteği tekrar doğrula")).toBeTruthy(),
  );
  const first = api.configureMarketScanner.mock.calls[0];
  await fireEvent.press(ui.getByText("Aynı isteği tekrar doğrula"));
  await waitFor(() =>
    expect(api.configureMarketScanner).toHaveBeenCalledTimes(2),
  );
  expect(api.configureMarketScanner.mock.calls[1]).toEqual(first);
});
test("old scanner and paper scopes never authorize dual scanner", async () => {
  const fetcher = jest.fn();
  const api = createApi(
    {
      origin: "https://gateway.example.com",
      session: "fixture",
      scopes: ["read", "scanner:write", "paper:write"],
    },
    fetcher,
  );
  await expect(
    api.configureMarketScanner("MANUAL", {
      idempotency_key: "fixture-request",
    }),
  ).rejects.toMatchObject({ code: "SCOPE_DENIED" });
  expect(fetcher).not.toHaveBeenCalled();
});
test("new discovery grant does not require or enable paper writes", async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ portfolio_id: "MANUAL", data_mode: "live", config }),
  });
  const api = createApi(
    {
      origin: "https://gateway.example.com",
      session: "fixture",
      scopes: ["read", "discovery:write"],
    },
    fetcher,
  );
  await api.configureMarketScanner("MANUAL", {
    idempotency_key: "fixture-request",
  });
  expect(fetcher).toHaveBeenCalledTimes(1);
});
test("fixture scanner response cannot be displayed as live source", async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      portfolio_id: "MANUAL",
      data_mode: "fixture",
      config,
      runtime: {
        activation: {
          state: "blocked",
          reasons: ["runtime_not_running"],
          runtime_available: false,
          account_enabled: false,
          starts_process: false,
        },
      },
      jobs: [],
      universe: {},
    }),
  });
  const api = createApi(
    { origin: "https://gateway.example.com", session: "fixture" },
    fetcher,
  );
  await expect(api.marketScanner("MANUAL")).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
  });
});
