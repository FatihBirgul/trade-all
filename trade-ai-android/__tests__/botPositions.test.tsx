import React from "react";
import { Alert, type AlertButton } from "react-native";
import { act, fireEvent, render, waitFor, within } from "@testing-library/react-native";
import Positions from "../app/(tabs)/positions";
import { BotError } from "../src/bot/client";
import { parsePrice } from "../src/bot/PositionCard";
import { useBot } from "../src/bot/state";
import type { BotPosition } from "../src/bot/types";
import { ThemeProvider } from "../src/theme";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("../src/bot/state", () => ({ useBot: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));

const eurusd: BotPosition = {
  position_id: "2001",
  origin: "bot",
  symbol: "EURUSD",
  side: "BUY",
  volume: 0.05,
  initial_volume: 0.05,
  entry: 1.1,
  sl: 1.0972,
  tp1: 1.1042,
  tp2: 1.107,
  strategy_id: "fx_trend_momentum_v6",
  opened_at: 1,
  manage: true,
  user_sl_override: false,
  be_done: false,
  partial_done: false,
  realized_pnl: 0,
  price: 1.1035,
  unrealized_pnl: 17.5,
  r_multiple: 1.25,
};
const gold: BotPosition = {
  ...eurusd,
  position_id: "2002",
  origin: "manual",
  symbol: "XAUUSD",
  side: "SELL",
  volume: 0.01,
  entry: 2385.5,
  sl: 2391,
  tp1: null,
  tp2: null,
  price: 2388,
  unrealized_pnl: -2.5,
  r_multiple: -0.45,
  manage: false,
  user_sl_override: true,
};
type Bot = ReturnType<typeof useBot>;
function setBot(positions: BotPosition[], overrides: Partial<Bot> = {}) {
  const api = {
    closePosition: jest.fn().mockResolvedValue({ order: "k" }),
    patchPosition: jest.fn().mockResolvedValue({ order: "k", manage: true }),
  };
  const bot = {
    phase: "ready",
    status: { currency: "USC", dry_run: false },
    positions,
    events: [],
    error: "",
    heartbeatStale: false,
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
      <Positions />
    </ThemeProvider>,
  );
let alert: jest.SpyInstance;
const pressDialog = async (text: string) => {
  const buttons = (alert.mock.calls.at(-1) as [string, string, AlertButton[]])[2];
  await act(async () => buttons.find((button) => button.text === text)?.onPress?.());
};
beforeEach(() => {
  alert = jest.spyOn(Alert, "alert").mockImplementation(() => {});
});
afterEach(() => jest.restoreAllMocks());

test("lists positions with pnl and r multiple", async () => {
  setBot([eurusd, gold]);
  const ui = await screen();
  expect(ui.getByText("2 açık pozisyon")).toBeTruthy();
  expect(ui.getByText("EURUSD · AL")).toBeTruthy();
  expect(ui.getByText("+17,50 USC  ·  +1,25R")).toBeTruthy();
  expect(ui.getByText("XAUUSD · SAT")).toBeTruthy();
  expect(ui.getByText("−2,50 USC  ·  −0,45R")).toBeTruthy();
  expect(ui.getByText("Bot")).toBeTruthy();
  expect(ui.getByText("Elle")).toBeTruthy();
  expect(ui.getByText("SL kullanıcı tarafından ayarlandı")).toBeTruthy();
  const rows = ui.getAllByTestId("row-Zarar durdur (SL)");
  expect(within(rows[0]).getByText("1,0972")).toBeTruthy();
  expect(within(rows[1]).getByText("2391")).toBeTruthy();
  expect(within(ui.getAllByTestId("row-Kâr al (TP)")[1]).getByText("—")).toBeTruthy();
});

test("a position without a stop is flagged loudly", async () => {
  setBot([{ ...eurusd, sl: null }]);
  const ui = await screen();
  expect(ui.getByText(/zarar durdurma görünmüyor/)).toBeTruthy();
});

test("close asks for confirmation", async () => {
  const { bot, api } = setBot([eurusd]);
  const ui = await screen();
  await fireEvent.press(ui.getByText("Kapat"));
  expect(api.closePosition).not.toHaveBeenCalled();
  expect(alert.mock.calls[0][0]).toBe("EURUSD kapatılsın mı?");
  await pressDialog("Vazgeç");
  expect(api.closePosition).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByText("Kapat"));
  await pressDialog("Kapat");
  expect(api.closePosition).toHaveBeenCalledTimes(1);
  expect(api.closePosition).toHaveBeenCalledWith("2001");
  await waitFor(() => expect(ui.getByText("Kapama isteği gönderildi.")).toBeTruthy());
  expect(bot.refresh).toHaveBeenCalled();
});

test("edit sends only changed fields", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await fireEvent.press(ui.getByText("SL/TP düzenle"));
  await fireEvent.changeText(ui.getByLabelText("Yeni SL EURUSD"), "1,0990");
  await fireEvent.press(ui.getByText("Kaydet"));
  await waitFor(() => expect(api.patchPosition).toHaveBeenCalledWith("2001", { sl: 1.099 }));

  await fireEvent.press(ui.getByText("SL/TP düzenle"));
  await fireEvent.changeText(ui.getByLabelText("Yeni SL EURUSD"), "1.0972"); // şimdiki değerle aynı
  await fireEvent.changeText(ui.getByLabelText("Yeni TP EURUSD"), "1.1050");
  await fireEvent.press(ui.getByText("Kaydet"));
  await waitFor(() => expect(api.patchPosition).toHaveBeenLastCalledWith("2001", { tp: 1.105 }));
  expect(api.patchPosition).toHaveBeenCalledTimes(2);
});

test("saving with nothing changed sends nothing", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await fireEvent.press(ui.getByText("SL/TP düzenle"));
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(ui.getByText("Değişiklik yok.")).toBeTruthy();
  expect(api.patchPosition).not.toHaveBeenCalled();
});

test("rejects non-positive stop before network", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await fireEvent.press(ui.getByText("SL/TP düzenle"));
  for (const bad of ["0", "-1.1", "abc", "1.1.1", "1e5"]) {
    await fireEvent.changeText(ui.getByLabelText("Yeni SL EURUSD"), bad);
    await fireEvent.press(ui.getByText("Kaydet"));
    expect(ui.getByText("SL pozitif bir sayı olmalı.")).toBeTruthy();
  }
  await fireEvent.changeText(ui.getByLabelText("Yeni SL EURUSD"), "");
  await fireEvent.changeText(ui.getByLabelText("Yeni TP EURUSD"), "0");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(ui.getByText("TP pozitif bir sayı olmalı.")).toBeTruthy();
  expect(api.patchPosition).not.toHaveBeenCalled();
  expect(parsePrice(" 1,25 ")).toBe(1.25);
  expect(parsePrice("")).toBeUndefined();
});

test("manage toggle patches position", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await fireEvent(ui.getByLabelText("Kademeli stop EURUSD"), "valueChange", false);
  await waitFor(() => expect(api.patchPosition).toHaveBeenCalledWith("2001", { manage: false }));
  expect(ui.getByText("Kademeli stop kapatıldı.")).toBeTruthy();
});

test("conflict shows server message", async () => {
  const { api } = setBot([eurusd]);
  const detail = "pozisyonda sonucu beklenen başka bir istek var";
  api.patchPosition.mockRejectedValue(new BotError("HTTP_409", detail, false, 409));
  const ui = await screen();
  await fireEvent.press(ui.getByText("SL/TP düzenle"));
  await fireEvent.changeText(ui.getByLabelText("Yeni SL EURUSD"), "1.0990");
  await fireEvent.press(ui.getByText("Kaydet"));
  await waitFor(() => expect(ui.getByText(detail)).toBeTruthy());
  expect(ui.getByDisplayValue("1.0990")).toBeTruthy(); // form açık kalır, yazılan kaybolmaz
  expect(api.patchPosition).toHaveBeenCalledTimes(1);
});

test("empty state", async () => {
  setBot([]);
  const ui = await screen();
  expect(ui.getByText("Açık pozisyon yok.")).toBeTruthy();
});

test("not connected shows the connection hint instead of positions", async () => {
  setBot([eurusd], { phase: "unconfigured", status: null });
  const ui = await screen();
  expect(ui.getByText("Bot ile bağlantı kurulmadı.")).toBeTruthy();
  expect(ui.queryByText("EURUSD · AL")).toBeNull();
});
