import React from "react";
import { Alert, type AlertButton } from "react-native";
import { act, fireEvent, render, waitFor, within } from "@testing-library/react-native";
import Panel from "../app/(tabs)/index";
import { BotError } from "../src/bot/client";
import { useBot } from "../src/bot/state";
import type { BotStatus } from "../src/bot/types";
import { ThemeProvider } from "../src/theme";

const mockPush = jest.fn();
jest.mock("expo-router", () => ({ router: { push: (...args: unknown[]) => mockPush(...args) } }));
jest.mock("../src/bot/state", () => ({ useBot: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));

const NOW = 1_800_000_000;
const status: BotStatus = {
  currency: "USC",
  balance: 3000,
  equity: 3012.5,
  margin_free: 2890.25,
  pnl_today: { bot: 12.5, manual: -4, total: 8.5 },
  open_bot: 2,
  open_manual: 1,
  halted: false,
  halt_reason: null,
  stopped: false,
  dry_run: false,
  start_capital: 3000,
  last_scan_at: NOW - 125,
  heartbeat_at: NOW - 5,
  stream_connected: true,
  started: true,
  server_time: NOW,
};
type Bot = ReturnType<typeof useBot>;
function setBot(overrides: Partial<Bot> = {}, statusOverrides: Partial<BotStatus> = {}) {
  const api = {
    stop: jest.fn().mockResolvedValue({}),
    resume: jest.fn().mockResolvedValue({}),
    closeAll: jest.fn().mockResolvedValue({ requested: 3, skipped: [], stopped: true }),
    setDryRun: jest.fn().mockResolvedValue({}),
  };
  const bot = {
    phase: "ready",
    config: { origin: "https://203-0-113-7.sslip.io", token: "t".repeat(43), pairedAt: 1 },
    status: { ...status, ...statusOverrides },
    positions: [],
    events: [],
    error: "",
    heartbeatStale: false,
    lastOkAt: 1,
    api,
    refresh: jest.fn().mockResolvedValue(undefined),
    ...overrides,
  } as unknown as Bot;
  jest.mocked(useBot).mockReturnValue(bot);
  return { bot, api };
}
const screen = () =>
  render(
    <ThemeProvider>
      <Panel />
    </ThemeProvider>,
  );
let alert: jest.SpyInstance;
const dialog = (index = -1) => {
  const call = alert.mock.calls.at(index) as [string, string, AlertButton[]];
  return { title: call[0], message: call[1], buttons: call[2] };
};
const pressDialog = async (text: string) => {
  const button = dialog().buttons.find((candidate) => candidate.text === text);
  if (!button) throw new Error("düğme yok: " + text);
  await act(async () => button.onPress?.());
};

beforeEach(() => {
  mockPush.mockClear();
  alert = jest.spyOn(Alert, "alert").mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());

test("shows balance equity and pnl split", async () => {
  setBot();
  const ui = await screen();
  expect(within(ui.getByTestId("row-Bakiye")).getByText("3.000,00 USC")).toBeTruthy();
  expect(within(ui.getByTestId("row-Varlık (equity)")).getByText("3.012,50 USC")).toBeTruthy();
  expect(within(ui.getByTestId("row-Bot")).getByText("+12,50 USC")).toBeTruthy();
  expect(within(ui.getByTestId("row-Elle")).getByText("−4,00 USC")).toBeTruthy();
  expect(within(ui.getByTestId("row-Toplam")).getByText("+8,50 USC")).toBeTruthy();
  expect(within(ui.getByTestId("row-Bot işlemleri")).getByText("2")).toBeTruthy();
  expect(within(ui.getByTestId("row-Elle işlemler")).getByText("1")).toBeTruthy();
  expect(within(ui.getByTestId("row-Son tarama")).getByText("2 dk önce")).toBeTruthy();
  expect(ui.getByText("Çalışıyor")).toBeTruthy();
  expect(ui.getByText("● CANLI · GERÇEK HESAP")).toBeTruthy();
});

test("dry run is announced so no one mistakes it for live trading", async () => {
  setBot({}, { dry_run: true });
  const ui = await screen();
  expect(ui.getByText("Deneme modu: bot emir göndermiyor")).toBeTruthy();
  expect(ui.getByText("● DENEME MODU · BOT EMİR GÖNDERMİYOR")).toBeTruthy();
  expect(ui.queryByText("● CANLI · GERÇEK HESAP")).toBeNull();
});

test("in dry run the close-all dialog says the action is real", async () => {
  const { api } = setBot({}, { dry_run: true });
  const ui = await screen();
  await fireEvent.press(ui.getByText("Hepsini kapat"));
  expect(dialog().message).toContain("Deneme modunda bile bu işlem GERÇEK hesapta yapılır.");
  expect(api.closeAll).not.toHaveBeenCalled();
});

test("a double tap sends the action once", async () => {
  const { api } = setBot();
  let finish!: () => void;
  api.stop.mockReturnValue(new Promise<void>((resolve) => (finish = resolve)));
  const ui = await screen();
  await fireEvent.press(ui.getByText("Durdur"));
  const buttons = dialog().buttons;
  await act(async () => {
    buttons.find((b) => b.text === "Durdur")?.onPress?.();
    buttons.find((b) => b.text === "Durdur")?.onPress?.();
  });
  expect(api.stop).toHaveBeenCalledTimes(1);
  await act(async () => finish());
});

test("stop asks for confirmation then calls api", async () => {
  const { bot, api } = setBot();
  const ui = await screen();
  expect(ui.queryByText("Devam")).toBeNull();
  await fireEvent.press(ui.getByText("Durdur"));
  expect(api.stop).not.toHaveBeenCalled();
  expect(dialog().title).toBe("Bot durdurulsun mu?");
  await pressDialog("Durdur");
  expect(api.stop).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(ui.getByText("Bot durduruldu.")).toBeTruthy());
  expect(bot.refresh).toHaveBeenCalled();
});

test("cancelling a confirmation sends nothing", async () => {
  const { api } = setBot();
  const ui = await screen();
  await fireEvent.press(ui.getByText("Durdur"));
  await pressDialog("Vazgeç");
  await fireEvent.press(ui.getByText("Hepsini kapat"));
  await pressDialog("Vazgeç");
  expect(api.stop).not.toHaveBeenCalled();
  expect(api.closeAll).not.toHaveBeenCalled();
});

test("resume after a plain stop does not send confirm_halt", async () => {
  const { api } = setBot({}, { stopped: true });
  const ui = await screen();
  expect(ui.getByText("Durduruldu")).toBeTruthy();
  expect(ui.queryByText("Durdur")).toBeNull();
  await fireEvent.press(ui.getByText("Devam"));
  await pressDialog("Devam et");
  expect(api.resume).toHaveBeenCalledWith(false);
});

test("resume after halt requires explicit confirmation and sends confirm_halt", async () => {
  const { api } = setBot({}, { halted: true, stopped: true, halt_reason: "toplam kayıp sınırı (%25) aşıldı" });
  const ui = await screen();
  expect(ui.getByText("Durdu: toplam kayıp sınırı (%25) aşıldı")).toBeTruthy();
  await fireEvent.press(ui.getByText("Devam"));
  expect(dialog().title).toBe("Bot kayıp sınırı nedeniyle durdu");
  expect(dialog().message).toContain("toplam kayıp sınırı (%25) aşıldı");
  await pressDialog("Devam etmek istiyorum");
  expect(api.resume).not.toHaveBeenCalled(); // ikinci onay bekleniyor
  expect(dialog().title).toBe("Emin misiniz?");
  await pressDialog("Evet, devam et");
  expect(api.resume).toHaveBeenCalledTimes(1);
  expect(api.resume).toHaveBeenCalledWith(true);
});

test("close all requires confirmation", async () => {
  const { api } = setBot();
  const ui = await screen();
  await fireEvent.press(ui.getByText("Hepsini kapat"));
  expect(api.closeAll).not.toHaveBeenCalled();
  expect(dialog().message).toContain("3 pozisyonun tamamı");
  expect(dialog().message).toContain("geri alınamaz");
  await pressDialog("Hepsini kapat");
  expect(api.closeAll).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(ui.getByText(/Kapama istekleri gönderildi/)).toBeTruthy());
});

test("uncertain result is shown instead of success and is not retried", async () => {
  const { api } = setBot();
  api.closeAll.mockRejectedValue(new BotError("NETWORK", undefined, true));
  const ui = await screen();
  await fireEvent.press(ui.getByText("Hepsini kapat"));
  await pressDialog("Hepsini kapat");
  await waitFor(() => expect(ui.queryByText(/Kapama istekleri gönderildi/)).toBeNull());
  expect(api.closeAll).toHaveBeenCalledTimes(1);
  expect(ui.getByText(new BotError("NETWORK", undefined, true).message)).toBeTruthy();
});

test("stale heartbeat card is shown and the bot is not presented as running", async () => {
  setBot({ heartbeatStale: true, lastOkAt: new Date(2026, 10, 25, 14, 32, 5).getTime() });
  const ui = await screen();
  expect(ui.getByText("Bottan 5 dakikadır haber yok")).toBeTruthy();
  expect(ui.getByText(/Son güncelleme: 14:32:05\./)).toBeTruthy();
  expect(ui.getByText("3.012,50 USC")).toBeTruthy(); // son bilinen veri görünür kalır
  expect(ui.queryByText("Çalışıyor")).toBeNull();
  expect(ui.getByText("Bot yanıt vermiyor (son bilinen durum: Çalışıyor)")).toBeTruthy();
  expect(ui.queryByText("● CANLI · GERÇEK HESAP")).toBeNull();
  expect(ui.getByText("● BOTTAN HABER YOK · BİLGİLER ESKİ")).toBeTruthy();
});

test("no data yet plus an error is a failure, not an empty panel", async () => {
  const { bot } = setBot({ status: null, lastOkAt: null, error: "Sunucuya ulaşılamadı." });
  const ui = await screen();
  expect(ui.getByText("Veri alınamadı. Sunucuya ulaşılamadı.")).toBeTruthy();
  expect(ui.queryByText(/Son bilinen bilgiler/)).toBeNull(); // hiç veri alınmadı
  expect(ui.queryByText("Durdur")).toBeNull();
  await fireEvent.press(ui.getByText("Yeniden dene"));
  expect(bot.refresh).toHaveBeenCalled();
});

test("unconfigured shows link to connection", async () => {
  setBot({ phase: "unconfigured", config: null, status: null });
  const ui = await screen();
  expect(ui.getByText("Bot ile bağlantı kurulmadı.")).toBeTruthy();
  expect(ui.queryByText("Durdur")).toBeNull();
  await fireEvent.press(ui.getByText("Bağlantı sekmesine git"));
  expect(mockPush).toHaveBeenCalledWith("/connection");
});

test("going live needs two explicit confirmations and is offered only in dry run", async () => {
  const { api } = setBot({}, { dry_run: true });
  const ui = await screen();
  expect(ui.queryByText("Deneme moduna dön")).toBeNull();
  await fireEvent.press(ui.getByText("Canlı moda geç"));
  expect(api.setDryRun).not.toHaveBeenCalled();
  expect(dialog().title).toBe("Canlı moda geçilsin mi?");
  expect(dialog().message).toContain("GERÇEK PARA");
  expect(dialog().message).toContain("3.012,50 USC");
  await pressDialog("Canlıya geçmek istiyorum");
  expect(api.setDryRun).not.toHaveBeenCalled(); // ikinci onay bekleniyor
  expect(dialog().title).toBe("Emin misiniz?");
  await pressDialog("Vazgeç");
  expect(api.setDryRun).not.toHaveBeenCalled();

  await fireEvent.press(ui.getByText("Canlı moda geç"));
  await pressDialog("Canlıya geçmek istiyorum");
  await pressDialog("Evet, canlıya geç");
  expect(api.setDryRun).toHaveBeenCalledTimes(1);
  expect(api.setDryRun).toHaveBeenCalledWith(false);
  await waitFor(() => expect(ui.getByText("Canlı moda geçildi.")).toBeTruthy());
});

test("going live is not offered while the bot is not answering", async () => {
  setBot({ heartbeatStale: true }, { dry_run: true });
  const ui = await screen();
  await fireEvent.press(ui.getByText("Canlı moda geç"));
  expect(alert).not.toHaveBeenCalled();
});

test("returning to dry run asks once", async () => {
  const { api } = setBot();
  const ui = await screen();
  expect(ui.queryByText("Canlı moda geç")).toBeNull();
  await fireEvent.press(ui.getByText("Deneme moduna dön"));
  expect(api.setDryRun).not.toHaveBeenCalled();
  await pressDialog("Deneme moduna dön");
  expect(api.setDryRun).toHaveBeenCalledWith(true);
});
