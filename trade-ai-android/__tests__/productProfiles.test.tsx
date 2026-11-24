import React from "react";
import sample from "../docs/backend/v2_examples/analysis.json";
import Scanner from "../app/(tabs)/scanner";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { ThemeProvider } from "../src/theme";
import { ResearchDetails } from "../src/ResearchDetails";
import Profiles from "../app/strategy-profiles";
import { useApp } from "../src/state";
import { createApi, ApiError } from "../src/api/client";
const mockPush = jest.fn();
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-router", () => ({
  router: { push: (...args: unknown[]) => mockPush(...args) },
}));
jest.mock("expo-crypto", () => ({
  randomUUID: () => "fixture-profile-command-1",
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
const selection = {
  strategy_ids: ["trend_momentum_v2"],
  required_methods: ["roc12"],
  allowed_regimes: ["trend"],
  bias_timeframe: "1H",
  setup_timeframe: "1H",
  trigger_timeframe: "1H",
  minimum_confirmations: 2,
  analysis_every_bars: 10,
};
const profile = {
  profile_id: "a".repeat(64),
  portfolio_id: "MANUAL",
  group_id: "a".repeat(64),
  revision: 1,
  parent_id: null,
  content_id: "b".repeat(64),
  created_at_ms: 1800000000000,
  selection,
  strategy_versions: { trend_momentum_v2: "2" },
  scope: "restrict_existing_analysis_only",
  trade_permission: false,
};
function app(writable = false, saveProfile = jest.fn()) {
  const api = {
    profiles: jest.fn().mockResolvedValue([profile]),
    strategyCapabilities: jest.fn().mockResolvedValue({
      strategies: [{ strategy_id: "trend_momentum_v2" }],
      methods: [{ method_id: "roc12" }],
    }),
    saveProfile,
  };
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    connectionKey: 1,
    config: { session: "fixture" },
    account: "MANUAL",
    gatewayVerified: true,
    sessionInfo: {
      accounts: ["MANUAL"],
      scopes: ["read", ...(writable ? ["profiles:write"] : [])],
      capabilities: ["strategy-profiles-v1"],
    },
    api,
  } as unknown as ReturnType<typeof useApp>);
  return api;
}
test("legacy and malformed diagnostics stay explicit, no invented values", async () => {
  const ui = await render(
    <ThemeProvider>
      <ResearchDetails
        methods={{
          research_context: {
            patterns: { patterns: [null, 42] },
            methods: { methods: { x: { value: NaN } } },
          },
        }}
      />
    </ThemeProvider>,
  );
  expect(ui.getByText(/Araştırma verisi eksik/)).toBeTruthy();
  expect(
    ui.getByText(/işlem izni veya başarı olasılığı değildir/),
  ).toBeTruthy();
  await fireEvent.press(ui.getByText(/Ek teknik indikatörler/));
  expect(ui.queryByText("NaN")).toBeNull();
});
test("confirmed pattern time and descriptive profile rejection shown separately", async () => {
  const ui = await render(
    <ThemeProvider>
      <ResearchDetails
        methods={{
          profile_control: { passes: false, reason: "existing_risk_gate" },
          research_context: {
            status: "available",
            patterns: {
              patterns: [
                {
                  name: "Hammer",
                  formed_at: 1800000000000,
                  confirmed_at: null,
                  timeframe: "1H",
                  direction: "bullish",
                },
              ],
            },
          },
        }}
      />
    </ThemeProvider>,
  );
  expect(ui.getByText("Uygun değil · BEKLE")).toBeTruthy();
  await fireEvent.press(ui.getByText(/Mum formasyonları ve teyit zamanları/));
  expect(ui.getByText("Hammer")).toBeTruthy();
  expect(ui.getByText("Teyit kaydı yok")).toBeTruthy();
});
test("reader can select immutable profile but cannot see a write button", async () => {
  app();
  const ui = await render(
    <ThemeProvider>
      <Profiles />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Bu profille analiz al")).toBeTruthy(),
  );
  expect(ui.queryByText("Profili kaydet")).toBeNull();
  await fireEvent.press(ui.getByText("Bu profille analiz al"));
  expect(mockPush).toHaveBeenLastCalledWith(
    expect.objectContaining({
      params: expect.objectContaining({
        profileId: profile.profile_id,
        timeframe: "1H",
      }),
    }),
  );
});
test("lost write response retries frozen command and selection", async () => {
  const save = jest
    .fn()
    .mockRejectedValueOnce(new ApiError("NETWORK", true))
    .mockResolvedValueOnce(profile);
  app(true, save);
  const ui = await render(
    <ThemeProvider>
      <Profiles />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Profili kaydet")).toBeTruthy());
  await fireEvent.press(ui.getByText("Profili kaydet"));
  await waitFor(() =>
    expect(ui.getByText("Aynı kaydı yeniden dene")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Aynı kaydı yeniden dene"));
  await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
  expect(save.mock.calls[0]).toEqual(save.mock.calls[1]);
});
test("client requires explicit profile scope and keeps paper writes disabled", async () => {
  const fetcher = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => profile });
  const config = {
    origin: "https://gateway.example.com",
    session: "fixture-mobile-session",
  };
  await expect(
    createApi(config, fetcher).saveProfile("MANUAL", {
      idempotency_key: "fixture-profile-1",
    }),
  ).rejects.toMatchObject({ code: "SCOPE_DENIED" });
  expect(fetcher).not.toHaveBeenCalled();
  const api = createApi(
    { ...config, scopes: ["read", "profiles:write"] },
    fetcher,
  );
  await expect(
    api.saveProfile("MANUAL", { idempotency_key: "fixture-profile-1" }),
  ).resolves.toEqual(profile);
  await expect(
    api.createOrder("MANUAL", {
      analysis_id: "c".repeat(64),
      idempotency_key: "fixture-order-1",
    }),
  ).rejects.toMatchObject({ code: "PAPER_WRITES_DISABLED" });
});
test("cross-account and substituted profile IDs fail response validation", async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ ...profile, portfolio_id: "AUTO" }),
  });
  const api = createApi(
    {
      origin: "https://gateway.example.com",
      session: "fixture-mobile-session",
    },
    fetcher,
  );
  await expect(api.profile("MANUAL", profile.profile_id)).rejects.toMatchObject(
    { code: "INVALID_RESPONSE" },
  );
  fetcher.mockResolvedValue({
    ok: true,
    json: async () => ({ ...profile, profile_id: "d".repeat(64) }),
  });
  await expect(api.profile("MANUAL", profile.profile_id)).rejects.toMatchObject(
    { code: "INVALID_RESPONSE" },
  );
});

test("scanner pause/resume preserves bound immutable profile and cannot enable paper", async () => {
  const bound = {
    watch_id: "BTCUSDT:1H",
    symbol: "BTCUSDT",
    timeframe: "1H",
    enabled: true,
    auto_paper: false,
    profile_id: profile.profile_id,
  };
  const watch = jest.fn().mockResolvedValue({ ...bound, enabled: false });
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    uiMode: "pro",
    connectionKey: 1,
    config: { session: "fixture", origin: "https://pc.example.ts.net" },
    account: "AUTO",
    gatewayVerified: true,
    sessionInfo: {
      accounts: ["AUTO"],
      scopes: ["read", "scanner:write"],
      capabilities: ["profile-scanner-v1"],
    },
    api: {
      scanner: jest.fn().mockResolvedValue({
        paused: true,
        lease_id: null,
        lease_until_ms: 0,
        last_tick_ms: null,
        last_error: null,
        interval_seconds: 60,
        max_analyses_per_tick: 2,
      }),
      watches: jest.fn().mockResolvedValue([bound]),
      jobs: jest.fn().mockResolvedValue([]),
      profiles: jest
        .fn()
        .mockResolvedValue([{ ...profile, portfolio_id: "AUTO" }]),
      watch,
    },
  } as unknown as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <Scanner />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Durdur")).toBeTruthy());
  await fireEvent.press(ui.getByText("Durdur"));
  await waitFor(() =>
    expect(watch).toHaveBeenCalledWith({
      symbol: "BTCUSDT",
      timeframe: "1H",
      enabled: false,
      auto_paper: false,
      profile_id: profile.profile_id,
    }),
  );
});

test("profile watch details require capability opt-in; legacy wire stays unchanged", async () => {
  const bound = {
    watch_id: "BTCUSDT:1H",
    symbol: "BTCUSDT",
    timeframe: "1H",
    enabled: true,
    auto_paper: false,
    profile_id: profile.profile_id,
  };
  const fetcher = jest
    .fn()
    .mockResolvedValue({ ok: true, json: async () => [bound] });
  const config = {
    origin: "https://gateway.example.com",
    session: "fixture-mobile-session",
  };
  await createApi(config, fetcher).watches();
  expect(fetcher.mock.calls[0][0]).toBe(config.origin + "/api/v2/watchlist");
  await createApi(config, fetcher, undefined, {
    profileScannerEnabled: true,
  }).watches();
  expect(fetcher.mock.calls[1][0]).toBe(
    config.origin + "/api/v2/watchlist?include_profile=true",
  );
});

test("profile-bound analysis cannot silently return an unprofiled legacy result", async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ ...sample, data_mode: "live" }),
  });
  const api = createApi(
    {
      origin: "https://gateway.example.com",
      session: "fixture-mobile-session",
    },
    fetcher,
  );
  await expect(
    api.analyze({
      idempotency_key: "profile-binding-verify",
      profile_id: profile.profile_id,
    }),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});

test("confirmed divergence remains research with known time, never executable levels", async () => {
  const ui = await render(
    <ThemeProvider>
      <ResearchDetails
        methods={{
          research_context: {
            status: "available",
            divergences: {
              status: "available",
              trade_permission: false,
              events: [
                {
                  method_id: "legacy_rsi14_sma",
                  direction: "bullish",
                  formed_at: 1800000000000,
                  known_at: 1800000120000,
                  trade_permission: false,
                  price_at_first_pivot: "89",
                  price_at_second_pivot: "88",
                  indicator_at_first_pivot: "10",
                  indicator_at_second_pivot: "40",
                },
              ],
            },
          },
        }}
      />
    </ThemeProvider>,
  );
  await fireEvent.press(ui.getByText(/Teyitli RSI\/MACD uyumsuzlukları/));
  expect(ui.getByText("RSI14 · SMA")).toBeTruthy();
  expect(ui.getByText(/Backtest\/forward doğrulaması değildir/)).toBeTruthy();
  expect(
    ui.getByText(/işlem izni veya başarı olasılığı değildir/),
  ).toBeTruthy();
});
test("saved chart confirmation and UTC session show explanations without trade permission", async () => {
  const ui = await render(
    <ThemeProvider>
      <ResearchDetails
        methods={{
          research_context: {
            status: "available",
            trade_permission: false,
            charts: {
              source_window_bars: 128,
              patterns: [
                {
                  pattern_id: "bull_flag",
                  direction: "bullish",
                  formed_at: 1800000000000,
                  known_at: 1800000060000,
                  confirmed_at: null,
                  trade_permission: false,
                  explanation: "Controlled saved chart evidence",
                },
              ],
            },
            session: {
              status: "available",
              session_started_at_ms: 1800000000000,
              session_high: "103",
              session_low: "99",
              session_vwap: { status: "unavailable" },
              anchored_vwap: { status: "unavailable" },
              orb: { status: "unavailable" },
              volatility: { status: "unavailable" },
            },
          },
        }}
      />
    </ThemeProvider>,
  );
  await fireEvent.press(ui.getByText(/Grafik yapıları ve gerçek teyit zamanı/));
  expect(ui.getByText("Yükseliş bayrağı")).toBeTruthy();
  expect(ui.getByText("Controlled saved chart evidence")).toBeTruthy();
  await fireEvent.press(ui.getByText(/UTC kripto seans araştırması/));
  expect(ui.getByText("Gerçek hacim veya kaynak eksik")).toBeTruthy();
  expect(ui.getByText("Açık, doğrulanmış anchor seçilmedi")).toBeTruthy();
});
test("invalidated boundary remains descriptive with actual invalidation time", async () => {
  const methods = {
    research_context: {
      status: "available",
      charts: {
        patterns: [
          {
            pattern_id: "rising_wedge_boundary",
            quality_status: "invalidated",
            interpretation: "reversal",
            invalidated_at: 1800000060000,
            known_at: 1800000000000,
            trade_permission: false,
          },
        ],
      },
    },
  };
  const ui = await render(
    <ThemeProvider>
      <ResearchDetails methods={methods} />
    </ThemeProvider>,
  );
  await fireEvent.press(ui.getByText(/Grafik yapıları ve gerçek teyit zamanı/));
  expect(ui.getByText("Yükselen kama sınırı")).toBeTruthy();
  expect(ui.getByText("invalidated")).toBeTruthy();
  expect(ui.getByText("Önceki trende karşı")).toBeTruthy();
});
