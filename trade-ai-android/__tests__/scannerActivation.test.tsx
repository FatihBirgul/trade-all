import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { router } from "expo-router";
import MarketDiscovery from "../app/market-discovery";
import { ThemeProvider } from "../src/theme";
import { useApp } from "../src/state";
import { ApiError } from "../src/api/client";
import { scannerReadiness } from "../src/domain/scannerReadiness";
jest.mock("react-native-safe-area-context", () => ({
  SafeAreaView: jest.requireActual("react-native").View,
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), back: jest.fn(), canGoBack: () => false },
}));
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-crypto", () => ({
  randomUUID: () => "fixture-explicit-activation",
}));
const base = {
  portfolio_id: "MANUAL",
  revision: 1,
  name: "Sabah taraması",
  runtime_mode: "supported_markets",
  enabled: false,
  discovery: true,
  favorites: ["BTCUSDT"],
  interval_seconds: 300,
  timeframe: "5m",
  profile_id: null,
  ttl_seconds: 3600,
};
const profile = {
  profile_id: "a".repeat(64),
  revision: 2,
  portfolio_id: "MANUAL",
  selection: {
    bias_timeframe: "4H",
    setup_timeframe: "1H",
    trigger_timeframe: "15m",
    strategy_ids: ["trend_momentum_v2"],
    required_methods: ["roc12"],
    minimum_confirmations: 2,
  },
};
function setup(
  options: {
    write?: boolean;
    ready?: boolean;
    enabled?: boolean;
    oldGateway?: boolean;
    config?: object;
    failure?: ApiError;
  } = {},
) {
  const config = {
    ...base,
    enabled: options.enabled ?? false,
    ...options.config,
  };
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
        worker_active: options.ready ?? false,
        provider_status: "not_probed",
        activation: {
          state: options.ready
            ? config.enabled
              ? "active"
              : "ready_to_activate"
            : "blocked",
          reasons: options.ready ? [] : ["runtime_not_running"],
          runtime_available: options.ready ?? false,
          account_enabled: config.enabled,
          starts_process: false,
        },
      },
      jobs: [],
      universe: {},
    }),
    opportunities: jest
      .fn()
      .mockResolvedValue({ items: [], next_offset: null }),
    profiles: jest.fn().mockResolvedValue([profile]),
    profile: jest.fn().mockResolvedValue(profile),
    configureMarketScanner: jest.fn().mockResolvedValue({ config }),
    marketScannerTick: jest.fn(),
  };
  if (options.failure) api.marketScanner.mockRejectedValue(options.failure);
  const state = {
    mode: "live",
    account: "MANUAL",
    setAccount: jest.fn(),
    connectionKey: 1,
    gatewayVerified: true,
    connectionPhase: "ready",
    config: { session: "fixture" },
    sessionInfo: {
      accounts: ["MANUAL"],
      scopes: ["read", ...(options.write === false ? [] : ["discovery:write"])],
      capabilities: [
        "dual-scanner-v1",
        "strategy-profiles-v1",
        ...(options.oldGateway ? [] : ["scanner-activation-v1"]),
      ],
    },
    api,
    reconnect: jest.fn().mockResolvedValue({}),
    disconnect: jest.fn(),
  };
  jest
    .mocked(useApp)
    .mockReturnValue(state as unknown as ReturnType<typeof useApp>);
  return { api, state };
}
async function screen() {
  return render(
    <ThemeProvider>
      <MarketDiscovery />
    </ThemeProvider>,
  );
}
test("opening app or loading profiles never sends configuration, tick or activation", async () => {
  const { api, state } = setup({ ready: true });
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByText("Yapılandırmayı kaydet")).toBeTruthy(),
  );
  expect(api.configureMarketScanner).not.toHaveBeenCalled();
  expect(api.marketScannerTick).not.toHaveBeenCalled();
  expect(state.reconnect).not.toHaveBeenCalled();
});
test("named single timeframe configuration always saves inactive", async () => {
  const { api } = setup();
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByLabelText("Tarama profili adı")).toBeTruthy(),
  );
  await fireEvent.changeText(
    ui.getByLabelText("Tarama profili adı"),
    "Akşam kontrolü",
  );
  await fireEvent.press(ui.getByText("15m"));
  await fireEvent.press(ui.getByText("900"));
  await fireEvent.press(ui.getByText("Yapılandırmayı kaydet"));
  await waitFor(() => expect(api.configureMarketScanner).toHaveBeenCalled());
  expect(api.configureMarketScanner.mock.calls[0][1]).toMatchObject({
    name: "Akşam kontrolü",
    timeframe: "15m",
    interval_seconds: 900,
    enabled: false,
    runtime_mode: "supported_markets",
    favorites: ["BTCUSDT"],
  });
});
test("strategy profile selection freezes exact revision and MTF roles", async () => {
  const { api } = setup();
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByLabelText("Tarama profili adı")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText(/Strateji \/ çoklu zaman dilimi bağlama/));
  await waitFor(() =>
    expect(ui.getByText("r2 · 4H / 1H / 15m · aaaaaaaa")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("r2 · 4H / 1H / 15m · aaaaaaaa"));
  await fireEvent.press(ui.getByText("Yalnız seçili profil"));
  await fireEvent.press(ui.getByText("Yapılandırmayı kaydet"));
  await waitFor(() => expect(api.configureMarketScanner).toHaveBeenCalled());
  expect(api.configureMarketScanner.mock.calls[0][1]).toMatchObject({
    profile_id: profile.profile_id,
    timeframe: "1H",
    runtime_mode: "selected_profile",
    discovery: false,
    enabled: false,
  });
  // A successful save reloads the server revision and remounts the collapsed editor.
  await waitFor(() =>
    expect(ui.getByText(/Strateji \/ çoklu zaman dilimi bağlama/)).toBeTruthy(),
  );
  if (!ui.queryByText("Strateji profili oluştur / düzenle"))
    await fireEvent.press(
      ui.getByText(/Strateji \/ çoklu zaman dilimi bağlama/),
    );
  await fireEvent.press(ui.getByText("Strateji profili oluştur / düzenle"));
  expect(router.push).toHaveBeenCalledWith("/strategy-profiles");
});
test("missing host runtime blocks explicit account activation without starting anything", async () => {
  const { api } = setup();
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByText("Bu hesabın taramasını etkinleştir")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Bu hesabın taramasını etkinleştir"));
  expect(api.configureMarketScanner).not.toHaveBeenCalled();
  expect(api.marketScannerTick).not.toHaveBeenCalled();
});
test("ready runtime still requires an explicit activation and uses saved configuration", async () => {
  const { api } = setup({ ready: true });
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByText("Bu hesabın taramasını etkinleştir")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Bu hesabın taramasını etkinleştir"));
  await waitFor(() =>
    expect(api.configureMarketScanner).toHaveBeenCalledTimes(1),
  );
  expect(api.configureMarketScanner.mock.calls[0][1]).toMatchObject({
    enabled: true,
    expected_revision: 1,
    name: base.name,
    runtime_mode: base.runtime_mode,
  });
  expect(api.marketScannerTick).not.toHaveBeenCalled();
});
test("dirty fields cannot silently activate and active config can be disabled", async () => {
  const { api } = setup({ ready: true, enabled: true });
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByLabelText("Tarama profili adı")).toBeTruthy(),
  );
  await fireEvent.changeText(
    ui.getByLabelText("Tarama profili adı"),
    "Kaydedilmedi",
  );
  await fireEvent.press(ui.getByText("Bu hesabın taramasını etkinleştir"));
  expect(api.configureMarketScanner).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByText(/Olay bildirim tercihleri/));
  await fireEvent.press(ui.getByText("○ Erken fırsat"));
  await fireEvent.press(ui.getByText("Bu hesabın taramasını pasifleştir"));
  await waitFor(() => expect(api.configureMarketScanner).toHaveBeenCalled());
  expect(api.configureMarketScanner.mock.calls[0][1]).toMatchObject({
    enabled: false,
    name: base.name,
    notify_early: false,
  });
});
test("uncertain activation replays exact original command, not a different save", async () => {
  const { api } = setup({ ready: true });
  api.configureMarketScanner.mockRejectedValueOnce(
    new ApiError("NETWORK", true),
  );
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByText("Bu hesabın taramasını etkinleştir")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Bu hesabın taramasını etkinleştir"));
  await waitFor(() =>
    expect(ui.getByText("Aynı isteği tekrar doğrula")).toBeTruthy(),
  );
  const first = api.configureMarketScanner.mock.calls[0];
  await fireEvent.press(ui.getByText("Aynı isteği tekrar doğrula"));
  await waitFor(() =>
    expect(api.configureMarketScanner).toHaveBeenCalledTimes(2),
  );
  expect(api.configureMarketScanner.mock.calls[1]).toEqual(first);
  expect(first[1].enabled).toBe(true);
});
test("403 is connected but unauthorized and never clears session or auto reconnects", async () => {
  const { state } = setup({
    failure: new ApiError("SCOPE_DENIED", false, 403),
  });
  const ui = await screen();
  await waitFor(() => expect(ui.getByText("Bağlı ama yetkisiz")).toBeTruthy());
  expect(state.disconnect).not.toHaveBeenCalled();
  expect(state.reconnect).not.toHaveBeenCalled();
});
test("network failure is offline with unknown cause and retry is explicit", async () => {
  const { state } = setup({ failure: new ApiError("NETWORK") });
  const ui = await screen();
  await waitFor(() =>
    expect(
      ui.getByText("Çevrimdışı · sunucu bağlantısı doğrulanamadı"),
    ).toBeTruthy(),
  );
  expect(state.reconnect).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByText("Bağlantıyı yeniden doğrula"));
  await waitFor(() => expect(state.reconnect).toHaveBeenCalledTimes(1));
});
test("old gateway exposes unavailable editor without privileged writes", async () => {
  const { api } = setup({ oldGateway: true });
  const ui = await screen();
  await waitFor(() =>
    expect(
      ui.getByText(
        /Bu düzenleyici için Backend ve Gateway güncellemesi gerekli/,
      ),
    ).toBeTruthy(),
  );
  expect(api.configureMarketScanner).not.toHaveBeenCalled();
});
test("empty name cannot create a scanner profile", async () => {
  const { api } = setup();
  const ui = await screen();
  await waitFor(() =>
    expect(ui.getByLabelText("Tarama profili adı")).toBeTruthy(),
  );
  await fireEvent.changeText(ui.getByLabelText("Tarama profili adı"), "   ");
  await fireEvent.press(ui.getByText("Yapılandırmayı kaydet"));
  expect(api.configureMarketScanner).not.toHaveBeenCalled();
  expect(ui.getByText(/Profil adı ve seçili zaman dilimi/)).toBeTruthy();
});
test("readiness distinguishes backend outage, write denial and current runtime observation", () => {
  const input = {
    mode: "live",
    gatewayVerified: true,
    account: "MANUAL",
    accounts: ["MANUAL"],
    scopes: ["read", "discovery:write"],
    capabilities: ["scanner-activation-v1"],
    runtime: {
      activation: {
        state: "ready_to_activate",
        reasons: [],
        runtime_available: true,
        account_enabled: false,
        starts_process: false,
      },
    },
  };
  expect(
    scannerReadiness({ ...input, errorCode: "BACKEND_UNAVAILABLE" }).status,
  ).toBe("partial");
  expect(
    scannerReadiness({ ...input, errorCode: "UPSTREAM_TIMEOUT" }).status,
  ).toBe("partial");
  expect(
    scannerReadiness({ ...input, errorCode: "INVALID_RESPONSE" }).status,
  ).toBe("partial");
  expect(scannerReadiness({ ...input, scopes: ["read"] }).status).toBe(
    "unauthorized",
  );
  expect(scannerReadiness(input).status).toBe("ready");
  expect(
    scannerReadiness({
      ...input,
      runtime: {
        activation: { ...input.runtime.activation, state: "unknown" },
      },
    }).status,
  ).toBe("partial");
  expect(
    scannerReadiness({
      ...input,
      runtime: {
        activation: { ...input.runtime.activation, runtime_available: false },
      },
    }).status,
  ).toBe("partial");
  expect(
    scannerReadiness({
      ...input,
      runtime: {
        activation: { state: "blocked", reasons: ["runtime_not_running"] },
      },
    }).status,
  ).toBe("partial");
});
