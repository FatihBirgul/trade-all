import React from "react";
import { Alert, type AlertButton } from "react-native";
import { act, fireEvent, render, waitFor, within } from "@testing-library/react-native";
import Reports from "../app/(tabs)/reports";
import SettingsBot from "../app/(tabs)/settings-bot";
import ManualTrade from "../app/manual-trade";
import { BotError } from "../src/bot/client";
import { useBot } from "../src/bot/state";
import type { BotSettings, BotStrategy, TradePreview } from "../src/bot/types";
import { ThemeProvider } from "../src/theme";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({ router: { push: (...args: unknown[]) => mockPush(...args) } }));
jest.mock("../src/bot/state", () => ({ useBot: jest.fn() }));
let mockUuid = 0;
jest.mock("expo-crypto", () => ({ randomUUID: () => "11111111-2222-3333-4444-55555555555" + (mockUuid++ % 10) }));
const mockStore = new Map<string, string>();
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(async (key: string) => mockStore.get(key) ?? null),
  setItemAsync: jest.fn(async (key: string, value: string) => void mockStore.set(key, value)),
  deleteItemAsync: jest.fn(async (key: string) => void mockStore.delete(key)),
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));

const totals = (pnl: number, trades: number, wins: number) => ({ pnl, trades, wins, win_rate: trades ? wins / trades : null });
const report = {
  period: "day",
  totals: { bot: totals(12.5, 4, 3), manual: totals(-4, 1, 0), all: totals(8.5, 5, 3) },
  periods: { bot: [], manual: [], all: [{ period: "2026-11-24", pnl: -3 }, { period: "2026-11-25", pnl: 11.5 }] },
  max_drawdown: { bot: 6, manual: 4, all: 7.5 },
  by_strategy: { fx_trend_momentum_v6: { pnl: 12.5, trades: 4, wins: 3 } },
  by_symbol: { EURUSD: { pnl: 10, trades: 3, wins: 2 }, XAUUSD: { pnl: -1.5, trades: 2, wins: 1 } },
  history: [
    { position_id: "9", origin: "bot", symbol: "EURUSD", side: "BUY", entry: 1.1, close_price: 1.102, opened_at: 1, closed_at: 2, pnl: 6.25, strategy_id: "fx_trend_momentum_v6" },
  ],
};
const strategies: BotStrategy[] = [
  { strategy_id: "fx_trend_momentum_v6", source: "v9", mode: "live", paused: false, shadow: { trades: 0, wins: 0, win_rate: null, avg_r: null }, can_go_live: false, live_blocker: null },
  { strategy_id: "tb_ema_pullback_v1", source: "custom", mode: "shadow", paused: false, shadow: { trades: 7, wins: 4, win_rate: 0.57, avg_r: 0.4 }, can_go_live: false, live_blocker: "yeni strateji canlıya alınamaz: en az 20 sonuçlanmış gölge işlem gerekli (şu an 7)" },
  { strategy_id: "fx_range_reversion_v6", source: "v9", mode: "shadow", paused: true, shadow: { trades: 3, wins: 1, win_rate: 0.33, avg_r: -0.2 }, can_go_live: true, live_blocker: null },
];
const settings = (): BotSettings => ({
  risk: { risk_pct: 0.5, max_open_bot: 3, per_symbol: 1, per_currency_side: 2, daily_loss_pct: 5, total_loss_pct: 25 },
  news: { enabled: true, window_minutes: 30 },
  fusion: { enabled: true, min_score: 40, mid_score: 60, high_score: 80 },
  manage: { be_enabled: true, partial_enabled: true, trail_enabled: true },
  enabled_symbols: null,
  dry_run: true,
  strategy_modes: {},
});
const preview: TradePreview = {
  symbol: "EURUSD", side: "BUY", entry: 1.1002, sl: 1.0982, tp: 1.1042, lots: 0.08, suggested_lots: 0.08, loss: 16,
  profit: 32, loss_pct: 0.49, rr: 2, risk_pct: 0.5, currency: "USC", volume_min: 0.01, volume_step: 0.01, volume_max: 200, warnings: [],
};
type Bot = ReturnType<typeof useBot>;
function setBot(overrides: Record<string, unknown> = {}, phase = "ready") {
  const api = {
    reports: jest.fn().mockResolvedValue(report),
    strategies: jest.fn().mockResolvedValue(strategies),
    settings: jest.fn().mockImplementation(async () => settings()), // sunucu gibi: her okumada yeni nesne
    updateSettings: jest.fn().mockResolvedValue(settings()),
    setStrategyMode: jest.fn().mockResolvedValue({}),
    symbols: jest.fn().mockResolvedValue([
      { symbol: "EURUSD", kind: "forex", open: true, quoted: true, bid: 1.1, ask: 1.1002, digits: 5, tick_size: 0.00001, volume_min: 0.01, volume_step: 0.01, volume_max: 200 },
      { symbol: "XAUUSD", kind: "metal", open: false, quoted: true, bid: 1, ask: 1, digits: 3, tick_size: 0.001, volume_min: 0.01, volume_step: 0.01, volume_max: 200 },
      { symbol: "BTCUSD", kind: "crypto", open: true, quoted: false, bid: null, ask: null, digits: 2, tick_size: 0.01, volume_min: 0.01, volume_step: 0.01, volume_max: 200 },
    ]),
    previewTrade: jest.fn().mockResolvedValue(preview),
    openTrade: jest.fn().mockResolvedValue({ order: "man-x", state: "ACKED", lots: 0.08, sl: 1.0982, tp: 1.1042 }),
    resolveTrade: jest.fn().mockResolvedValue({ found: true, state: "FILLED", lots: 0.08 }),
    ...overrides,
  };
  const bot = {
    phase,
    config: { origin: "https://203-0-113-7.sslip.io", token: "t".repeat(43), pairedAt: 1 },
    status: { currency: "USC", dry_run: true },
    heartbeatStale: false,
    error: "",
    lastOkAt: 1,
    api,
    refresh: jest.fn().mockResolvedValue(undefined),
  } as unknown as Bot;
  jest.mocked(useBot).mockReturnValue(bot);
  return { bot, api };
}
const show = (node: React.ReactElement) => render(<ThemeProvider>{node}</ThemeProvider>);
let alert: jest.SpyInstance;
const dialog = () => {
  const call = alert.mock.calls.at(-1) as [string, string, AlertButton[]];
  return { title: call[0], message: call[1], buttons: call[2] };
};
const pressDialog = async (text: string) => {
  const button = dialog().buttons.find((candidate) => candidate.text === text);
  if (!button) throw new Error("düğme yok: " + text + " / " + dialog().buttons.map((b) => b.text).join(","));
  await act(async () => button.onPress?.());
};
beforeEach(() => {
  mockPush.mockClear();
  mockStore.clear();
  mockUuid = 0;
  alert = jest.spyOn(Alert, "alert").mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());

// ------------------------------------------------------------------ Raporlar
test("reports show bot / manual / total split, drawdown, strategies and history", async () => {
  const { api } = setBot();
  const ui = await show(<Reports />);
  await waitFor(() => expect(ui.getByText("Kapanan işlemler (tümü)")).toBeTruthy());
  expect(api.reports).toHaveBeenCalledWith("day");
  expect(within(ui.getByTestId("row-Bot")).getByText("+12,50 USC · 4 işlem")).toBeTruthy();
  expect(within(ui.getByTestId("row-Elle")).getByText("−4,00 USC · 1 işlem")).toBeTruthy();
  expect(within(ui.getByTestId("row-Toplam")).getByText("+8,50 USC · 5 işlem")).toBeTruthy();
  expect(within(ui.getByTestId("row-Bot kazanma oranı")).getByText("%75 (3/4)")).toBeTruthy();
  expect(within(ui.getByTestId("row-En büyük düşüş (bot)")).getByText("6,00 USC")).toBeTruthy();
  expect(ui.getByText("Trend momentum · Canlı")).toBeTruthy();
  expect(ui.getByText("EMA geri çekilme (yeni) · Gölge")).toBeTruthy();
  expect(ui.getByText("Bant içi dönüş · Gölge (duraklatıldı)")).toBeTruthy();
  expect(ui.getByText(/gölge: 7 işlem, ort\. \+0,4R/)).toBeTruthy();
  expect(ui.getByText("EURUSD · AL · Bot")).toBeTruthy();
});

test("changing the period reloads and a failed load is not shown as an empty report", async () => {
  const { api } = setBot();
  const ui = await show(<Reports />);
  await waitFor(() => expect(ui.getByText("Kapanan işlemler (tümü)")).toBeTruthy());
  api.reports.mockRejectedValue(new BotError("NETWORK"));
  await fireEvent.press(ui.getByText("Hafta"));
  await waitFor(() => expect(api.reports).toHaveBeenLastCalledWith("week"));
  await waitFor(() => expect(ui.getByText(/^Rapor alınamadı\./)).toBeTruthy());
  expect(ui.queryByText("Kapanan işlemler (tümü)")).toBeNull(); // günlük rapor haftalık gibi gösterilmez
  expect(ui.queryByText("Henüz kapanmış işlem yok.")).toBeNull();
});

test("reports when not connected show the connection hint", async () => {
  setBot({}, "unconfigured");
  const ui = await show(<Reports />);
  expect(ui.getByText("Bot ile bağlantı kurulmadı.")).toBeTruthy();
});

// ------------------------------------------------------------------ Ayarlar
test("settings save asks with old and new values and applies only the change to fresh settings", async () => {
  const { api } = setBot();
  const ui = await show(<SettingsBot />);
  await waitFor(() => expect(ui.getByLabelText("İşlem başı risk")).toBeTruthy());
  await fireEvent.changeText(ui.getByLabelText("İşlem başı risk"), "0,25");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(api.updateSettings).not.toHaveBeenCalled();
  expect(dialog().title).toBe("Ayarlar kaydedilsin mi?");
  expect(dialog().message).toBe("İşlem başı risk: 0,5% → 0,25%");
  await pressDialog("Kaydet");
  expect(api.updateSettings).toHaveBeenCalledTimes(1);
  const apply = api.updateSettings.mock.calls[0][0] as (s: BotSettings) => BotSettings;
  const fresh = settings();
  fresh.risk.max_open_bot = 2; // başka bir yerden değişmiş
  expect(apply(fresh).risk).toMatchObject({ risk_pct: 0.25, max_open_bot: 2 });
  await waitFor(() => expect(ui.getByText("Ayarlar kaydedildi.")).toBeTruthy());
});

test("raising risk needs an explicit warning; invalid values never reach the network", async () => {
  const { api } = setBot();
  const ui = await show(<SettingsBot />);
  await waitFor(() => expect(ui.getByLabelText("İşlem başı risk")).toBeTruthy());
  await fireEvent.changeText(ui.getByLabelText("İşlem başı risk"), "5");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(ui.getByText("İşlem başı risk: 0,25 ile 1 arasında bir sayı girin.")).toBeTruthy();
  expect(alert).not.toHaveBeenCalled();
  await fireEvent.changeText(ui.getByLabelText("İşlem başı risk"), "1");
  await fireEvent(ui.getByLabelText("Haber penceresi koruması"), "valueChange", false);
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(dialog().title).toBe("Dikkat: risk artıyor");
  expect(dialog().message).toContain("İşlem başı risk: 0,5% → 1%  ⚠ risk artar");
  expect(dialog().message).toContain("Haber penceresi koruması: Açık → Kapalı  ⚠ risk artar");
  expect(dialog().buttons.map((b) => b.text)).toEqual(["Vazgeç", "Riski artır ve kaydet"]);
  await pressDialog("Vazgeç");
  expect(api.updateSettings).not.toHaveBeenCalled();
});

test("a strategy goes live only through its own confirmed request and only when allowed", async () => {
  const { api } = setBot();
  const ui = await show(<SettingsBot />);
  await waitFor(() => expect(ui.getByText(/EMA geri çekilme \(yeni\) · Gölge/)).toBeTruthy());
  expect(ui.getByText(/en az 20 sonuçlanmış gölge işlem gerekli/)).toBeTruthy();
  await fireEvent.press(ui.getByLabelText("Canlıya al tb_ema_pullback_v1")); // karne koşulu yok: düğme kapalı
  expect(alert).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByLabelText("Canlıya al fx_range_reversion_v6"));
  expect(dialog().title).toBe("Bant içi dönüş canlıya alınsın mı?");
  expect(dialog().message).toContain("GERÇEK PARA");
  expect(api.setStrategyMode).not.toHaveBeenCalled();
  await pressDialog("Canlıya al");
  expect(api.setStrategyMode).toHaveBeenCalledWith("fx_range_reversion_v6", "live", true);
  await fireEvent.press(ui.getByLabelText("Kapat fx_trend_momentum_v6"));
  await pressDialog("Kapalı yap");
  expect(api.setStrategyMode).toHaveBeenLastCalledWith("fx_trend_momentum_v6", "off");
  await fireEvent.press(ui.getByText("Bağlantı ayarları"));
  expect(mockPush).toHaveBeenCalledWith("/connection");
});

test("typed settings survive a strategy change and a refused request shows the server reason", async () => {
  const { api } = setBot();
  const ui = await show(<SettingsBot />);
  await waitFor(() => expect(ui.getByLabelText("İşlem başı risk")).toBeTruthy());
  await fireEvent.changeText(ui.getByLabelText("İşlem başı risk"), "0,75");
  api.setStrategyMode.mockRejectedValueOnce(new BotError("HTTP_409", "gölge sonuçları yetersiz", false, 409));
  await fireEvent.press(ui.getByLabelText("Canlıya al fx_range_reversion_v6"));
  expect(dialog().message).toContain("DENEME modunda"); // bot deneme modunda: yanlış "hemen gerçek para" denmez
  expect(dialog().message).toContain("3 işlem, kazanma %33, ortalama -0,2 R");
  expect(dialog().message).toContain("ZARARDA");
  expect(dialog().message).toContain("duraklatmıştı");
  await pressDialog("Canlıya al");
  await waitFor(() => expect(dialog().title).toBe("İşlem yapılamadı"));
  expect(dialog().message).toBe("gölge sonuçları yetersiz");
  await waitFor(() => expect(api.settings).toHaveBeenCalledTimes(2)); // sunucudan yeni kopya geldi
  await waitFor(() => expect(ui.getByLabelText("İşlem başı risk").props.value).toBe("0,75")); // yazılan silinmedi
});

test("settings that could not be re-read cannot be saved against a stale copy", async () => {
  const { api } = setBot();
  const ui = await show(<SettingsBot />);
  await waitFor(() => expect(ui.getByLabelText("İşlem başı risk")).toBeTruthy());
  api.settings.mockRejectedValue(new BotError("NETWORK"));
  await fireEvent.press(ui.getByText("Yenile"));
  await waitFor(() => expect(ui.getByText(/^Ayarlar alınamadı\./)).toBeTruthy());
  await fireEvent.changeText(ui.getByLabelText("İşlem başı risk"), "1");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(alert).not.toHaveBeenCalled();
  expect(api.updateSettings).not.toHaveBeenCalled();
});

test("reports can be refreshed and show when they were read", async () => {
  const { api } = setBot();
  const ui = await show(<Reports />);
  await waitFor(() => expect(ui.getByText("Kapanan işlemler (tümü)")).toBeTruthy());
  expect(ui.getByText(/^Son güncelleme: \d/)).toBeTruthy();
  await fireEvent.press(ui.getByText("Yenile"));
  await waitFor(() => expect(api.reports).toHaveBeenCalledTimes(2));
});

test("settings: thresholds, stop stages and symbol list are saved through one confirmation", async () => {
  const { api } = setBot();
  const ui = await show(<SettingsBot />);
  await waitFor(() => expect(ui.getByLabelText("Orta güven eşiği (altı yarım lot)")).toBeTruthy());
  expect(ui.getByText(/^Hepsi açık \(3\)/)).toBeTruthy();
  await fireEvent.changeText(ui.getByLabelText("Orta güven eşiği (altı yarım lot)"), "30"); // en düşük puanın (40) altı
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(ui.getByText("Güven eşikleri sıralı olmalı: en düşük ≤ orta ≤ yüksek.")).toBeTruthy();
  expect(alert).not.toHaveBeenCalled();
  await fireEvent.changeText(ui.getByLabelText("Orta güven eşiği (altı yarım lot)"), "70");
  await fireEvent(ui.getByLabelText("İz süren stop"), "valueChange", false);
  await fireEvent.press(ui.getByText("BTCUSD")); // sembolü kapat
  expect(ui.getByText(/^2 \/ 3 açık/)).toBeTruthy();
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(dialog().title).toBe("Dikkat: risk artıyor");
  expect(dialog().message).toContain("Orta güven eşiği (altı yarım lot): 60 → 70");
  expect(dialog().message).toContain("İz süren stop: Açık → Kapalı  ⚠ risk artar");
  expect(dialog().message).toContain("Açık semboller: Hepsi → 2 (kapanan: BTCUSD)");
  await pressDialog("Riski artır ve kaydet");
  const apply = api.updateSettings.mock.calls[0][0] as (s: BotSettings) => BotSettings;
  const saved = apply(settings());
  expect(saved.fusion.mid_score).toBe(70);
  expect(saved.manage).toEqual({ be_enabled: true, partial_enabled: true, trail_enabled: false });
  expect(saved.enabled_symbols).toEqual(["EURUSD", "XAUUSD"]);
});

test("manual trade: a risk percentage sizes the preview; the order carries the previewed lot only", async () => {
  const { api } = setBot({
    previewTrade: jest.fn().mockResolvedValue({ ...preview, lots: 0.16, loss: 32, loss_pct: 0.98, risk_pct: 1, settings_risk_pct: 0.5,
      warnings: ["Bu lotla zarar, risk sınırınızın (%0.5) üstünde"] }),
  });
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.changeText(ui.getByLabelText("Risk yüzdesi"), "3");
  await fireEvent.press(ui.getByText("Önizle"));
  expect(ui.getByText("Risk yüzdesi 0,05 ile 2 arasında olmalı.")).toBeTruthy();
  await fireEvent.changeText(ui.getByLabelText("Risk yüzdesi"), "1");
  await fireEvent.changeText(ui.getByLabelText("Lot"), "0,5");
  await fireEvent.press(ui.getByText("Önizle"));
  expect(ui.getByText("Lot ya da risk yüzdesinden yalnızca birini girin.")).toBeTruthy();
  expect(api.previewTrade).not.toHaveBeenCalled();
  await fireEvent.changeText(ui.getByLabelText("Lot"), "");
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText("Emri gönder")).toBeTruthy());
  expect(api.previewTrade).toHaveBeenCalledWith({ symbol: "EURUSD", side: "BUY", sl_distance: 0.002, tp_distance: 0.004, risk_pct: 1 });
  expect(within(ui.getByTestId("row-Hesabın yüzdesi")).getByText("%0,98 (ayardaki sınır: %0,5)")).toBeTruthy();
  await fireEvent.press(ui.getByText("Emri gönder"));
  expect(dialog().message).toContain("⚠ Bu lotla zarar, risk sınırınızın");
  await pressDialog("Emri gönder");
  expect(api.openTrade.mock.calls[0][0]).toEqual({ symbol: "EURUSD", side: "BUY", sl_distance: 0.002, tp_distance: 0.004, lots: 0.16 });
});

// ------------------------------------------------------------------ Elle işlem
async function fillTrade(ui: Awaited<ReturnType<typeof show>>) {
  await waitFor(() => expect(ui.getByText("EURUSD")).toBeTruthy());
  await fireEvent.press(ui.getByText("EURUSD"));
  await fireEvent.changeText(ui.getByLabelText("Zarar durdurma mesafesi"), "0,0020");
  await fireEvent.changeText(ui.getByLabelText("Kâr al mesafesi"), "0.0040");
}

test("manual trade lists only open, quoted symbols and requires a stop distance", async () => {
  const { api } = setBot();
  const ui = await show(<ManualTrade />);
  await waitFor(() => expect(ui.getByText("EURUSD")).toBeTruthy());
  expect(ui.queryByText("XAUUSD")).toBeNull(); // piyasa kapalı
  expect(ui.queryByText("BTCUSD")).toBeNull(); // güncel fiyat yok
  await fireEvent.press(ui.getByText("EURUSD"));
  await fireEvent.press(ui.getByText("Önizle"));
  expect(ui.getByText("Zarar durdurma mesafesi zorunludur (pozitif sayı).")).toBeTruthy();
  expect(api.previewTrade).not.toHaveBeenCalled();
  expect(ui.queryByText("Emri gönder")).toBeNull(); // önizleme olmadan gönderilemez
});

test("manual trade: preview, confirmation with the previewed numbers, single send with a client id", async () => {
  const { api } = setBot();
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText("Önizleme: EURUSD AL")).toBeTruthy());
  expect(api.previewTrade).toHaveBeenCalledWith({ symbol: "EURUSD", side: "BUY", sl_distance: 0.002, tp_distance: 0.004 });
  expect(within(ui.getByTestId("row-En çok zarar")).getByText("−16,00 USC (%0,49)")).toBeTruthy();
  expect(api.openTrade).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByText("Emri gönder"));
  expect(api.openTrade).not.toHaveBeenCalled(); // önce onay
  expect(dialog().title).toBe("EURUSD AL emri gönderilsin mi?");
  expect(dialog().message).toContain("0,08 lot");
  expect(dialog().message).toContain("en çok yaklaşık −16,00 USC");
  expect(dialog().message).toContain("GERÇEK hesapta"); // deneme modunda da gerçek
  await pressDialog("Emri gönder");
  expect(api.openTrade).toHaveBeenCalledTimes(1);
  expect(api.openTrade).toHaveBeenCalledWith(
    { symbol: "EURUSD", side: "BUY", sl_distance: 0.002, tp_distance: 0.004, lots: 0.08 },
    "11111111-2222-3333-4444-555555555550",
  );
  await waitFor(() => expect(ui.getByText(/Emir gönderildi: 0,08 lot/)).toBeTruthy());
});

test("editing any field discards the preview so a stale preview cannot be sent", async () => {
  setBot();
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText("Emri gönder")).toBeTruthy());
  await fireEvent.changeText(ui.getByLabelText("Zarar durdurma mesafesi"), "0.0010");
  expect(ui.queryByText("Emri gönder")).toBeNull();
});

async function sendUncertain(api: ReturnType<typeof setBot>["api"], error: Error = new BotError("NETWORK", undefined, true)) {
  api.openTrade.mockRejectedValueOnce(error);
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText("Emri gönder")).toBeTruthy());
  await fireEvent.press(ui.getByText("Emri gönder"));
  await pressDialog("Emri gönder");
  await waitFor(() => expect(ui.getByText("Emrin sonucu bilinmiyor")).toBeTruthy());
  return ui;
}

test("uncertain result: no new order; the check asks about the same id and never re-sends the order", async () => {
  const { api } = setBot();
  const ui = await sendUncertain(api);
  expect(api.openTrade).toHaveBeenCalledTimes(1); // kendiliğinden yeniden denenmedi
  await fireEvent.press(ui.getByText("Önizle")); // belirsizken yeni emir hazırlanamaz
  expect(api.previewTrade).toHaveBeenCalledTimes(1);
  await fireEvent.press(ui.getByText("Sonucu kontrol et"));
  await waitFor(() => expect(ui.getByText(/Emir daha önce alınmış: 0,08 lot/)).toBeTruthy());
  expect(api.openTrade).toHaveBeenCalledTimes(1); // kontrol emir GÖNDERMEZ
  expect(api.resolveTrade).toHaveBeenCalledWith(api.openTrade.mock.calls[0][1]); // aynı kimlik
  expect(ui.queryByText("Emrin sonucu bilinmiyor")).toBeNull();
});

test("the check failing (429, 500, network) keeps the lock and the id", async () => {
  const { api } = setBot();
  const ui = await sendUncertain(api);
  for (const error of [new BotError("HTTP_429", "çok istek", false, 429), new BotError("HTTP_500", undefined, true, 500), new BotError("NETWORK", undefined, true)]) {
    api.resolveTrade.mockRejectedValueOnce(error);
    await fireEvent.press(ui.getByText("Sonucu kontrol et"));
    await waitFor(() => expect(ui.getByText(/Sonuç öğrenilemedi/)).toBeTruthy());
    expect(ui.getByText("Emrin sonucu bilinmiyor")).toBeTruthy();
  }
  await fireEvent.press(ui.getByText("Önizle"));
  expect(api.previewTrade).toHaveBeenCalledTimes(1);
  expect(api.openTrade).toHaveBeenCalledTimes(1);
  expect(new Set(api.resolveTrade.mock.calls.map((call: unknown[]) => call[0]))).toEqual(new Set([api.openTrade.mock.calls[0][1]]));
});

test("order that never reached the server is cancelled by the check, not opened", async () => {
  const { api } = setBot({ resolveTrade: jest.fn().mockResolvedValue({ found: false, state: null, lots: null }) });
  const ui = await sendUncertain(api);
  await fireEvent.press(ui.getByText("Sonucu kontrol et"));
  await waitFor(() => expect(ui.getByText(/pozisyon AÇILMADI/)).toBeTruthy());
  expect(api.openTrade).toHaveBeenCalledTimes(1);
  expect(ui.queryByText("Emrin sonucu bilinmiyor")).toBeNull();
});

test("the uncertain lock survives leaving the screen", async () => {
  const { api } = setBot();
  const first = await sendUncertain(api);
  await first.unmount();
  const ui = await show(<ManualTrade />);
  await waitFor(() => expect(ui.getByText("Emrin sonucu bilinmiyor")).toBeTruthy());
  await fireEvent.press(ui.getByText("Önizle"));
  expect(api.previewTrade).toHaveBeenCalledTimes(1);
  await fireEvent.press(ui.getByText("Sonucu kontrol et"));
  await waitFor(() => expect(api.resolveTrade).toHaveBeenCalledWith(api.openTrade.mock.calls[0][1]));
});

test("a rejected or unresolved order is not reported as sent", async () => {
  const { api } = setBot();
  api.openTrade.mockResolvedValueOnce({ order: "man-x", state: "REJECTED", lots: 0.08, sl: 1, tp: null });
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText("Emri gönder")).toBeTruthy());
  await fireEvent.press(ui.getByText("Emri gönder"));
  await pressDialog("Emri gönder");
  await waitFor(() => expect(ui.getByText(/Emir REDDEDİLDİ/)).toBeTruthy());
  expect(ui.queryByText(/Emir gönderildi/)).toBeNull();
});

test("a late preview for other inputs is dropped and inputs are frozen while a request runs", async () => {
  let release: (value: TradePreview) => void = () => {};
  const { api } = setBot({
    previewTrade: jest.fn().mockImplementation(() => new Promise<TradePreview>((resolve) => { release = resolve; })),
  });
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.press(ui.getByText("Önizle"));
  await fireEvent.press(ui.getByText("SAT")); // istek sürerken yön değişmez
  await act(async () => release({ ...preview, symbol: "XAUUSD" })); // başka sembolün önizlemesi
  await waitFor(() => expect(ui.getByText(/başka bir işlem için geldi/)).toBeTruthy());
  expect(ui.queryByText("Emri gönder")).toBeNull();
  expect(api.openTrade).not.toHaveBeenCalled();
});

test("double confirmation sends one order with one id; an old preview must be renewed", async () => {
  const { api } = setBot();
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText("Emri gönder")).toBeTruthy());
  const now = jest.spyOn(Date, "now");
  const base = Date.now();
  now.mockReturnValue(base + 61_000);
  await fireEvent.press(ui.getByText("Emri gönder"));
  expect(ui.getByText(/Önizleme eskidi/)).toBeTruthy();
  expect(ui.queryByText("Emri gönder")).toBeNull();
  now.mockRestore();
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText("Emri gönder")).toBeTruthy());
  await fireEvent.press(ui.getByText("Emri gönder"));
  const button = dialog().buttons.find((candidate) => candidate.text === "Emri gönder");
  await act(async () => {
    button?.onPress?.();
    button?.onPress?.();
  });
  await waitFor(() => expect(ui.getByText(/Emir gönderildi/)).toBeTruthy());
  expect(api.openTrade).toHaveBeenCalledTimes(1);
});

test("server refusal shows its message and warnings are repeated in the confirmation", async () => {
  const { api } = setBot({
    previewTrade: jest.fn().mockResolvedValue({ ...preview, lots: 1, loss: 200, warnings: ["Bu lotla zarar, risk sınırınızın (%0.5) üstünde"] }),
  });
  api.openTrade.mockRejectedValue(new BotError("HTTP_409", "güncel fiyat yok", false, 409));
  const ui = await show(<ManualTrade />);
  await fillTrade(ui);
  await fireEvent.changeText(ui.getByLabelText("Lot"), "1");
  await fireEvent.press(ui.getByText("Önizle"));
  await waitFor(() => expect(ui.getByText(/⚠ Bu lotla zarar/)).toBeTruthy());
  await fireEvent.press(ui.getByText("Emri gönder"));
  expect(dialog().message).toContain("⚠ Bu lotla zarar, risk sınırınızın");
  await pressDialog("Emri gönder");
  await waitFor(() => expect(ui.getByText("güncel fiyat yok")).toBeTruthy());
  expect(ui.queryByText("Emrin sonucu bilinmiyor")).toBeNull();
});
