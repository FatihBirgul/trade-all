import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import Follows from "../app/follows";
import { ThemeProvider } from "../src/theme";
import { useApp } from "../src/state";
import {
  allowedFollows,
  latestFollowChange,
  loadFollowChanges,
  type Follow,
  type Notice,
} from "../src/domain/follows";
const mockPush = jest.fn();
let mockParams: { analysis?: string } = {};
beforeEach(() => {
  mockParams = {};
});
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-router", () => ({
  useLocalSearchParams: () => mockParams,
  router: { push: (...args: unknown[]) => mockPush(...args) },
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));
const follow: Follow = {
  tracking_id: "a".repeat(64),
  origin_analysis_id: "b".repeat(64),
  last_analysis_id: "c".repeat(64),
  portfolio_id: "AUTO",
  symbol: "BTCUSDT",
  timeframe: "1H",
  data_mode: "live",
  enabled: true,
  status: "monitoring",
  last_checked_ms: 1,
  last_direction: "WAIT",
  last_reason: "regime_not_eligible",
  notified_changes: 1,
  worker_running: false,
};
function app(api: object) {
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    gatewayVerified: true,
    config: { session: "test" },
    sessionInfo: {
      capabilities: ["analysis-follow-v1"],
      scopes: ["read", "scanner:write"],
      accounts: ["AUTO"],
    },
    api,
  } as unknown as ReturnType<typeof useApp>);
}
test("follow manager stop/resume targets exact ID and opens last immutable record", async () => {
  let current = follow;
  const changeFollow = jest.fn(
    async (_id: string, enabled: boolean) =>
      (current = { ...current, enabled }),
  );
  app({ follows: async () => [current], changeFollow });
  const ui = await render(
    <ThemeProvider>
      <Follows />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("PC işçisi kapalı")).toBeTruthy());
  await fireEvent.press(ui.getByText("Takibi durdur"));
  await waitFor(() => expect(ui.getByText("Takibe devam et")).toBeTruthy());
  expect(changeFollow).toHaveBeenLastCalledWith(follow.tracking_id, false);
  await fireEvent.press(ui.getByText("Takibe devam et"));
  await waitFor(() =>
    expect(changeFollow).toHaveBeenLastCalledWith(follow.tracking_id, true),
  );
  await fireEvent.press(ui.getByText("Son takip analizini aç"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/result",
    params: { id: follow.last_analysis_id },
  });
});
test("uncertain change performs no automatic second POST and failed GET never reports working", async () => {
  const changeFollow = jest.fn().mockRejectedValue(new Error("Kesinti"));
  const reads = jest
    .fn()
    .mockResolvedValueOnce([follow])
    .mockRejectedValue(new Error("Çevrimdışı"));
  app({ follows: reads, changeFollow });
  const ui = await render(
    <ThemeProvider>
      <Follows />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Takibi durdur")).toBeTruthy());
  await fireEvent.press(ui.getByText("Takibi durdur"));
  await waitFor(() =>
    expect(
      ui.getByText(/Bağlantı yok · takip\/işçi durumu doğrulanamadı/),
    ).toBeTruthy(),
  );
  expect(changeFollow).toHaveBeenCalledTimes(1);
  expect(ui.queryByText("Son sorguda izliyordu")).toBeNull();
});
test("account boundary and last meaningful change join never cross accounts", () => {
  expect(() => allowedFollows([follow], ["MANUAL"])).toThrow(/hesap/);
  const notice = {
    notification_id: "n",
    kind: "analysis",
    created_at_ms: 10,
    data_mode: "live",
    delivery_status: "pending",
    delivery_service: "not_configured",
    details: {
      change_kind: "analysis_condition_changed",
      tracking_id: follow.tracking_id,
      portfolio_id: "AUTO",
      analysis_id: follow.last_analysis_id,
      direction: "bullish",
      reason: "ok",
    },
  } as Notice;
  expect(
    latestFollowChange(
      [
        {
          ...notice,
          created_at_ms: 20,
          details: { ...notice.details, portfolio_id: "MANUAL" },
        },
        notice,
      ],
      follow,
    ),
  ).toEqual(notice);
  expect(
    latestFollowChange([{ ...notice, data_mode: "fixture" }], follow),
  ).toBeUndefined();
});
test("outbox lookback is bounded to five read-only pages", async () => {
  const notifications = jest.fn(
    async () => Array(20).fill({ notification_id: "same" }) as Notice[],
  );
  expect(await loadFollowChanges({ notifications })).toHaveLength(1);
  expect(notifications.mock.calls).toHaveLength(5);
});

test("summary handoff starts tracking the exact pinned analysis instead of another recent record", async () => {
  mockParams = { analysis: "d".repeat(64) };
  const sample = require("../docs/backend/v2_examples/analysis.json");
  let rows: Follow[] = [];
  const detail = jest
    .fn()
    .mockResolvedValue({
      ...sample,
      analysis_id: mockParams.analysis,
      data_mode: "live",
    });
  const start = jest.fn(async () => {
    rows = [
      {
        ...follow,
        origin_analysis_id: mockParams.analysis!,
        last_analysis_id: mockParams.analysis!,
      },
    ];
    return rows[0];
  });
  app({ follows: async () => rows, detail, follow: start });
  const ui = await render(
    <ThemeProvider>
      <Follows />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("BTCUSDT · 1H · AUTO takip et")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("BTCUSDT · 1H · AUTO takip et"));
  await waitFor(() => expect(start).toHaveBeenCalledWith(mockParams.analysis));
  expect(detail).toHaveBeenCalledWith(mockParams.analysis);
  expect(start).toHaveBeenCalledTimes(1);
});
