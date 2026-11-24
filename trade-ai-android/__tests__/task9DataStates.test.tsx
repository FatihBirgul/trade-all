import React from "react";
import { render, fireEvent, waitFor, act } from "@testing-library/react-native";
import { useApp } from "../src/state";
import { ThemeProvider } from "../src/theme";
import { demoAnalysis } from "../src/demo";
import {
  hasMarketEvaluation,
  regimeText,
  validityText,
} from "../src/domain/analysisPresentation";
import { directionText } from "../src/domain/presentation";
import { safeDecision } from "../src/domain/safety";
import Detail from "../app/detail";
import Notifications from "../app/notifications";
import * as uiComponents from "../src/ui";
import Scanner from "../app/(tabs)/scanner";
import Portfolios from "../app/(tabs)/portfolios";
import sample from "../docs/backend/v2_examples/analysis.json";
import type { Analysis } from "../src/domain/safety";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-router", () => ({
  router: { push: jest.fn() },
  useLocalSearchParams: () => ({ id: "demo-id" }),
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 24, left: 0, right: 0 }),
}));
const notifications = jest.fn();
function state(overrides: object = {}) {
  jest.mocked(useApp).mockReturnValue({
    mode: "demo",
    uiMode: "pro",
    account: "AUTO",
    gatewayVerified: false,
    config: { origin: "https://qa.example.test", session: "test" },
    connectionKey: 1,
    connectionPhase: "offline",
    connectionErrorCode: "NETWORK",
    connectionError: "Bağlantı hatası",
    history: [],
    api: { notifications },
    ...overrides,
  } as unknown as ReturnType<typeof useApp>);
}
beforeEach(() => {
  notifications.mockReset();
});
test("missing DEMO data cannot inherit assessed range/neutral; record times/decision stay immutable", async () => {
  const a = demoAnalysis("BTCUSDT", "1H", "AUTO", "demo-id");
  const before = JSON.stringify(a);
  state({ history: [a] });
  const ui = await render(
    <ThemeProvider>
      <Detail />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Teknik değerlendirme")).toBeTruthy(),
  );
  expect(ui.queryByText("range")).toBeNull();
  expect(ui.queryByText("neutral")).toBeNull();
  expect(ui.queryByText("Yatay piyasa")).toBeNull();
  expect(ui.getByText(/Uygulanabilir işlem senaryosu yok/)).toBeTruthy();
  expect(ui.getByText("Kayıtlı geçerlilik sonu")).toBeTruthy();
  expect(safeDecision(a)).toBe("WAIT");
  expect(JSON.stringify(a)).toBe(before);
});
test("valid historical market state is translated without treating expired decision as active", () => {
  const a = {
    ...sample,
    data_mode: "live",
    regime: { ...sample.regime, regime: "range" },
  } as Analysis;
  expect(hasMarketEvaluation(a)).toBe(true);
  expect(regimeText(a)).toBe("Yatay piyasa");
  expect(directionText("neutral")).toBe("Nötr");
  expect(directionText("wait")).toBe("Bekle");
  expect(hasMarketEvaluation({ ...a, price: "Infinity" })).toBe(false);
  expect(regimeText({ ...a, quality: { ok: false, issues: [] } })).toContain(
    "değerlendirilemedi",
  );
  expect(validityText({ ...a, direction: "WAIT" })).toContain(
    "işlem senaryosu oluşturulmadı",
  );
  expect(safeDecision(a, a.expires_at_ms + 1)).toBe("WAIT");
});
test("DEMO notification absence is local, never a successful server empty list", async () => {
  state();
  const ui = await render(
    <ThemeProvider>
      <Notifications />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText(/sunucunun bildirim durumu bilinmiyor/)).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Bildirimleri yenile"));
  expect(notifications).not.toHaveBeenCalled();
  expect(ui.queryByText("Bekleyen bildirim yok.")).toBeNull();
});
test("failed notification read and successful empty response remain distinct", async () => {
  notifications
    .mockRejectedValueOnce(new Error("Veri alınamadı."))
    .mockResolvedValueOnce([]);
  state({ mode: "live", gatewayVerified: true });
  const ui = await render(
    <ThemeProvider>
      <Notifications />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Veri alınamadı.")).toBeTruthy());
  expect(
    ui.queryByText("Sunucu bu sayfa için boş bildirim listesi döndürdü."),
  ).toBeNull();
  await fireEvent.press(ui.getByText("Yeniden dene"));
  await waitFor(() =>
    expect(
      ui.getByText("Sunucu bu sayfa için boş bildirim listesi döndürdü."),
    ).toBeTruthy(),
  );
});
test("DEMO portfolio explicitly identifies local seed without claiming backend risk evaluation", async () => {
  const portfolios = jest.fn();
  state({ api: { portfolios } });
  const ui = await render(
    <ThemeProvider>
      <Portfolios />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText(/10.000 USDT örnek başlangıç bakiyesi/)).toBeTruthy(),
  );
  expect(ui.getByText("DEMO · risk değerlendirmesi yapılmadı")).toBeTruthy();
  expect(portfolios).not.toHaveBeenCalled();
});

test("offline DEMO scanner controls stay local and cannot call backend", async () => {
  const api = {
    scanner: jest.fn(),
    watches: jest.fn(),
    jobs: jest.fn(),
    pause: jest.fn(),
    watch: jest.fn(),
    tick: jest.fn(),
  };
  const setPaused = jest.fn();
  state({ api, paused: true, lastTick: null, setPaused });
  const ui = await render(
    <ThemeProvider>
      <Scanner />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("DEMO · yerel örnek duraklatıldı")).toBeTruthy(),
  );
  expect(ui.getByText(/gerçek tarama işleri sorgulanmadı/)).toBeTruthy();
  await fireEvent.press(ui.getByText("DEMO örneğini sürdür"));
  expect(setPaused).toHaveBeenCalledWith(false);
  await fireEvent.press(ui.getByText("Durdur"));
  Object.values(api).forEach((fn) => expect(fn).not.toHaveBeenCalled());
});
test("failed scanner read does not claim paused/empty server and cannot send writes", async () => {
  const pause = jest.fn(),
    watch = jest.fn();
  state({
    mode: "live",
    gatewayVerified: false,
    sessionInfo: { scopes: ["scanner:write"], accounts: ["AUTO"] },
    api: {
      scanner: jest
        .fn()
        .mockRejectedValue(new Error("Sunucu erişimi doğrulanamadı.")),
      watches: async () => [],
      jobs: async () => [],
      pause,
      watch,
    },
  });
  const ui = await render(
    <ThemeProvider>
      <Scanner />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText(/sunucu durumu doğrulanamadı/)).toBeTruthy(),
  );
  expect(ui.queryByText("Son sorguda duraklatıldı")).toBeNull();
  expect(ui.queryByText(/boş tarama işi listesi/)).toBeNull();
  expect(ui.queryByText("Devam ettir")).toBeNull();
  expect(pause).not.toHaveBeenCalled();
  expect(watch).not.toHaveBeenCalled();
});
test("scanner resume is a single explicit POST, not proof of worker execution", async () => {
  const buttons = jest.spyOn(uiComponents, "Button");
  let finish!: () => void;
  const pause = jest.fn(
    () =>
      new Promise<void>((resolve) => {
        finish = resolve;
      }),
  );
  state({
    mode: "live",
    gatewayVerified: true,
    sessionInfo: { scopes: ["scanner:write"], accounts: ["AUTO"] },
    api: {
      scanner: async () => ({
        paused: true,
        last_tick_ms: null,
        last_error: null,
        interval_seconds: 60,
        max_analyses_per_tick: 2,
      }),
      watches: async () => [],
      jobs: async () => [],
      pause,
    },
  });
  const ui = await render(
    <ThemeProvider>
      <Scanner />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Devam ettir")).toBeTruthy());
  expect(
    ui.getByText("Sunucu bu sayfa için boş tarama işi listesi döndürdü."),
  ).toBeTruthy();
  const press = buttons.mock.calls.find(
    ([props]) => props.title === "Devam ettir",
  )![0].onPress;
  await act(async () => {
    void press();
    void press();
  });
  expect(pause).toHaveBeenCalledTimes(1);
  expect(pause).toHaveBeenCalledWith(false);
  await act(async () => finish());
  await waitFor(() =>
    expect(
      ui.getByText(/Bu yanıt PC işçisinin çalıştığını doğrulamaz/),
    ).toBeTruthy(),
  );
  buttons.mockRestore();
});
