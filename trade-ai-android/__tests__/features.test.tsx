import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { useApp } from "../src/state";
import { ThemeProvider } from "../src/theme";
import Result from "../app/result";
import History from "../app/history";
import Notifications from "../app/notifications";
import Detail from "../app/detail";
import Scanner from "../app/(tabs)/scanner";
import Performance from "../app/performance";
import sample from "../docs/backend/v2_examples/analysis.json";
const mockPush = jest.fn();
let mockParams: Record<string, string> = {};
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-router", () => ({
  router: { push: (...args: unknown[]) => mockPush(...args) },
  useLocalSearchParams: () => mockParams,
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 24, left: 0, right: 0 }),
}));
function app(overrides: object) {
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    config: {
      origin: "https://pc.example.ts.net",
      session: "controlled-test",
    },
    history: [],
    connectionKey: 1,
    account: "AUTO",
    setAccount: jest.fn(),
    gatewayVerified: true,
    sessionInfo: {
      scopes: ["read", "scanner:write"],
      accounts: ["AUTO", "MANUAL"],
    },
    ...overrides,
  } as unknown as ReturnType<typeof useApp>);
}
beforeEach(() => {
  mockPush.mockClear();
  mockParams = {};
});
test("immutable history selection compares only matching market/timeframe/account", async () => {
  const a = { ...sample, data_mode: "live", analysis_id: "a".repeat(64) };
  const b = { ...a, analysis_id: "b".repeat(64) };
  const other = { ...a, analysis_id: "c".repeat(64), risk_portfolio: "MANUAL" };
  app({ api: { analyses: jest.fn().mockResolvedValue([a, b, other, a]) } });
  const ui = await render(
    <ThemeProvider>
      <History />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getAllByText("Detayı aç")).toHaveLength(3));
  await fireEvent.press(ui.getAllByText("Karşılaştırma için seç")[0]);
  expect(ui.getAllByText("Seçilen kayıtla karşılaştır")).toHaveLength(1);
  await fireEvent.press(ui.getByText("Seçilen kayıtla karşılaştır"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/detail",
    params: { id: b.analysis_id, compare: a.analysis_id },
  });
});
test("pending outbox deduplicates, opens exact analysis, refreshes and resets pagination on session change", async () => {
  const n = {
    notification_id: "n",
    kind: "analysis",
    created_at_ms: 1,
    details: { analysis_id: "a".repeat(64) },
  };
  const notifications = jest
    .fn()
    .mockImplementation(async (offset) => (offset ? [] : Array(20).fill(n)));
  app({ api: { notifications } });
  const ui = await render(
    <ThemeProvider>
      <Notifications />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getAllByText("İlgili analizi aç")).toHaveLength(1),
  );
  await fireEvent.press(ui.getByText("İlgili analizi aç"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/detail",
    params: { id: "a".repeat(64) },
  });
  await fireEvent.press(ui.getByText("Sonraki"));
  await waitFor(() => expect(notifications).toHaveBeenLastCalledWith(20));
  app({ connectionKey: 2, api: { notifications } });
  await ui.rerender(
    <ThemeProvider>
      <Notifications />
    </ThemeProvider>,
  );
  await waitFor(() => expect(notifications).toHaveBeenLastCalledWith(0));
  expect(ui.getByText("Teslim bekliyor · Gönderilmedi")).toBeTruthy();
});
test("detail displays immutable comparison and carries timeframe to a new analysis", async () => {
  const a = { ...sample, data_mode: "live", analysis_id: "a".repeat(64) };
  const b = {
    ...a,
    analysis_id: "b".repeat(64),
    created_at_ms: a.created_at_ms - 3600000,
  };
  const setAccount = jest.fn();
  app({
    setAccount,
    api: {
      detail: jest
        .fn()
        .mockImplementation(async (id) => (id === a.analysis_id ? a : b)),
    },
  });
  mockParams = { id: a.analysis_id, compare: b.analysis_id };
  const ui = await render(
    <ThemeProvider>
      <Detail />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Kaydedilen karar · bu / diğer")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Yeni analiz al"));
  expect(setAccount).toHaveBeenCalledWith(a.risk_portfolio);
  expect(mockPush.mock.lastCall![0]).toMatchObject({
    pathname: "/analysis",
    params: {
      symbol: a.symbol,
      timeframe: a.timeframe,
      previous: a.analysis_id,
    },
  });
});
test("authorized scanner uses selected timeframe, disables watch and links job analysis", async () => {
  const watch = jest.fn();
  const watches = [
    {
      watch_id: "BTCUSDT:1H",
      symbol: "BTCUSDT",
      timeframe: "1H",
      enabled: true,
      auto_paper: false,
    },
  ];
  app({
    api: {
      scanner: async () => ({
        paused: true,
        last_tick_ms: null,
        last_error: null,
        interval_seconds: 60,
        max_analyses_per_tick: 2,
      }),
      watches: async () => watches,
      jobs: async () => [
        {
          job_id: "j",
          symbol: "ETHUSDT",
          timeframe: "4H",
          status: "completed",
          analysis_id: "a".repeat(64),
        },
      ],
      watch,
    },
  });
  const ui = await render(
    <ThemeProvider>
      <Scanner />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByLabelText("İzlemeyi kapat · BTCUSDT:1H")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText(/Yeni izleme kaydı/));
  await fireEvent.press(ui.getByText("ETHUSDT"));
  await fireEvent.press(ui.getByText("4H"));
  await fireEvent.press(ui.getByText("İzlemeye ekle · 4H"));
  await waitFor(() =>
    expect(watch).toHaveBeenCalledWith({
      symbol: "ETHUSDT",
      timeframe: "4H",
      enabled: true,
      auto_paper: false,
    }),
  );
  await waitFor(() =>
    expect(ui.getByLabelText("İzlemeyi kapat · BTCUSDT:1H")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByLabelText("İzlemeyi kapat · BTCUSDT:1H"));
  await waitFor(() =>
    expect(watch).toHaveBeenLastCalledWith({
      symbol: "BTCUSDT",
      timeframe: "1H",
      enabled: false,
      auto_paper: false,
    }),
  );
  await waitFor(() => expect(ui.getByText("Tarama analizini aç")).toBeTruthy());
  await fireEvent.press(ui.getByText("Tarama analizini aç"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/detail",
    params: { id: "a".repeat(64) },
  });
});
test("performance displays backend ambiguity for chosen account, no invented metrics", async () => {
  app({
    account: "MANUAL",
    api: {
      performance: async () => ({
        portfolios: [
          { portfolio_id: "AUTO", closed_positions: 88 },
          {
            portfolio_id: "MANUAL",
            closed_positions: 2,
            ambiguous_positions: 1,
            wins: 1,
            losses: 0,
            win_rate: "100",
            realized_pnl_quote: "3",
            fees_quote: "1",
          },
        ],
      }),
    },
  });
  const ui = await render(
    <ThemeProvider>
      <Performance />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Belirsiz pozisyonlar")).toBeTruthy(),
  );
  expect(ui.queryByText("88")).toBeNull();
  expect(ui.getByText("100%")).toBeTruthy();
});

test("summary uses the same immutable record, translates WAIT reason and opens exact detail", async () => {
  const record = {
    ...sample,
    data_mode: "live",
    analysis_id: "a".repeat(64),
    direction: "WAIT",
    reason: "regime_not_eligible",
    levels: null,
  };
  const original = JSON.stringify(record),
    detail = jest.fn().mockResolvedValue(record);
  mockParams = { id: record.analysis_id };
  app({ api: { detail } });
  const ui = await render(
    <ThemeProvider>
      <Result />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("BEKLE")).toBeTruthy());
  expect(
    ui.getByText(
      "Piyasanın mevcut yapısı bu stratejinin koşullarını sağlamıyor.",
    ),
  ).toBeTruthy();
  expect(ui.queryByText("regime_not_eligible")).toBeNull();
  await fireEvent.press(ui.getByText("Detaylı analizi aç"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/detail",
    params: { id: record.analysis_id },
  });
  expect(JSON.stringify(record)).toBe(original);
});

test("follow registration shows worker-off honestly and stop uses exact tracking ID", async () => {
  const a = { ...sample, data_mode: "live", analysis_id: "a".repeat(64) };
  let rows: unknown[] = [];
  const track = {
    tracking_id: "c".repeat(64),
    origin_analysis_id: a.analysis_id,
    last_analysis_id: a.analysis_id,
    enabled: true,
    worker_running: false,
    last_checked_ms: null,
    last_reason: "regime_not_eligible",
  };
  const follow = jest.fn(async () => {
    rows = [track];
    return track;
  });
  const changeFollow = jest.fn(async () => {
    rows = [{ ...track, enabled: false }];
    return rows[0];
  });
  app({
    sessionInfo: {
      scopes: ["read", "scanner:write"],
      accounts: ["AUTO", "MANUAL"],
      capabilities: ["analysis-follow-v1"],
    },
    api: {
      detail: async () => a,
      follows: async () => rows,
      follow,
      changeFollow,
    },
  });
  mockParams = { id: a.analysis_id };
  const ui = await render(
    <ThemeProvider>
      <Result />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Bu analizi takip et")).toBeTruthy());
  await fireEvent.press(ui.getByText("Bu analizi takip et"));
  await waitFor(() =>
    expect(ui.getByText("Kapalı · otomatik takip başlamadı")).toBeTruthy(),
  );
  expect(follow).toHaveBeenCalledWith(a.analysis_id);
  await fireEvent.press(ui.getByText("Takibi durdur"));
  await waitFor(() =>
    expect(changeFollow).toHaveBeenCalledWith(track.tracking_id, false),
  );
});

test("active follow for the same market/account wins over a paused older origin", async () => {
  const a = { ...sample, data_mode: "live", analysis_id: "a".repeat(64) };
  const paused = {
    tracking_id: "b".repeat(64),
    origin_analysis_id: a.analysis_id,
    last_analysis_id: a.analysis_id,
    enabled: false,
    symbol: a.symbol,
    timeframe: a.timeframe,
    portfolio_id: a.risk_portfolio,
    worker_running: false,
    last_reason: a.reason,
  };
  const active = {
    ...paused,
    enabled: true,
    tracking_id: "c".repeat(64),
    origin_analysis_id: "d".repeat(64),
    last_analysis_id: "e".repeat(64),
  };
  const changeFollow = jest
    .fn()
    .mockResolvedValue({ ...active, enabled: false });
  app({
    sessionInfo: {
      scopes: ["read", "scanner:write"],
      accounts: ["AUTO", "MANUAL"],
      capabilities: ["analysis-follow-v1"],
    },
    api: {
      detail: async () => a,
      follows: async () => [paused, active],
      changeFollow,
    },
  });
  mockParams = { id: a.analysis_id };
  const ui = await render(
    <ThemeProvider>
      <Result />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Takibi durdur")).toBeTruthy());
  await fireEvent.press(ui.getByText("Son takip analizini aç"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/result",
    params: { id: active.last_analysis_id },
  });
  await fireEvent.press(ui.getByText("Takibi durdur"));
  await waitFor(() =>
    expect(changeFollow).toHaveBeenCalledWith(active.tracking_id, false),
  );
});
