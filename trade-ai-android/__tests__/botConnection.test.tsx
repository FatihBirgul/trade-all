import React from "react";
import { Alert } from "react-native";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import Connection from "../app/(tabs)/connection";
import { BotError } from "../src/bot/client";
import { useBot } from "../src/bot/state";
import { ThemeProvider } from "../src/theme";

jest.mock("../src/bot/state", () => ({ useBot: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));

const ORIGIN = "https://203-0-113-7.sslip.io";
type Bot = ReturnType<typeof useBot>;
function setBot(overrides: Partial<Bot>) {
  const bot = {
    phase: "unconfigured",
    config: null,
    status: null,
    positions: [],
    events: [],
    error: "",
    heartbeatStale: false,
    lastOkAt: null,
    pair: jest.fn().mockResolvedValue(undefined),
    disconnect: jest.fn().mockResolvedValue(undefined),
    refresh: jest.fn(),
    ...overrides,
  } as unknown as Bot;
  jest.mocked(useBot).mockReturnValue(bot);
  return bot;
}
const screen = () =>
  render(
    <ThemeProvider>
      <Connection />
    </ThemeProvider>,
  );

afterEach(() => jest.restoreAllMocks());

test("connection screen pairs and shows connected state", async () => {
  const bot = setBot({});
  const ui = await screen();
  expect(ui.getByText(/sudo tradebot-pair/)).toBeTruthy();
  await fireEvent.changeText(ui.getByLabelText("Sunucu adresi"), ORIGIN);
  await fireEvent.changeText(ui.getByLabelText("Eşleştirme kodu"), "482913");
  await fireEvent.press(ui.getByText("Bağlan"));
  await waitFor(() => expect(bot.pair).toHaveBeenCalledWith(ORIGIN, "482913"));
  expect(bot.pair).toHaveBeenCalledTimes(1);

  setBot({ phase: "ready", config: { origin: ORIGIN, token: "t".repeat(43), pairedAt: 1 } });
  await ui.rerender(
    <ThemeProvider>
      <Connection />
    </ThemeProvider>,
  );
  expect(ui.getByText("Bağlı")).toBeTruthy();
  expect(ui.getByText("203-0-113-7.sslip.io")).toBeTruthy();
  expect(ui.queryByLabelText("Eşleştirme kodu")).toBeNull();
  expect(ui.queryByText(/t{43}/)).toBeNull(); // token ekranda gösterilmez
});

test("connection screen shows server error text", async () => {
  const pair = jest.fn().mockRejectedValue(new BotError("PAIR_REJECTED", undefined, false, 401));
  setBot({ pair });
  const ui = await screen();
  await fireEvent.changeText(ui.getByLabelText("Sunucu adresi"), ORIGIN);
  await fireEvent.changeText(ui.getByLabelText("Eşleştirme kodu"), "000000");
  await fireEvent.press(ui.getByText("Bağlan"));
  await waitFor(() =>
    expect(ui.getByText("Kod geçersiz ya da süresi dolmuş. Sunucuda yeni kod üretin.")).toBeTruthy(),
  );
  expect(ui.getByText("Bağlan")).toBeTruthy(); // yeniden denenebilir
});

test("revoked connection explains that pairing is needed again", async () => {
  setBot({ phase: "revoked" });
  const ui = await screen();
  expect(ui.getByText(/artık geçerli değil/)).toBeTruthy();
  expect(ui.getByLabelText("Eşleştirme kodu")).toBeTruthy();
});

test("disconnect clears config", async () => {
  const bot = setBot({ phase: "ready", config: { origin: ORIGIN, token: "t".repeat(43), pairedAt: 1 } });
  const alert = jest.spyOn(Alert, "alert").mockImplementation(() => {});
  const ui = await screen();
  await fireEvent.press(ui.getByText("Bağlantıyı sil"));
  expect(bot.disconnect).not.toHaveBeenCalled(); // önce onay
  const buttons = alert.mock.calls[0][2] ?? [];
  expect(buttons.map((button) => button.text)).toEqual(["Vazgeç", "Bağlantıyı sil"]);
  buttons[1].onPress?.();
  expect(bot.disconnect).toHaveBeenCalledTimes(1);
});

test("an address typed without https:// is completed, never downgraded", async () => {
  const bot = setBot({});
  const ui = await screen();
  await fireEvent.changeText(ui.getByLabelText("Sunucu adresi"), " 203-0-113-7.sslip.io ");
  await fireEvent.changeText(ui.getByLabelText("Eşleştirme kodu"), "482913");
  await fireEvent.press(ui.getByText("Bağlan"));
  await waitFor(() => expect(bot.pair).toHaveBeenCalledWith(ORIGIN, "482913"));
  await fireEvent.changeText(ui.getByLabelText("Sunucu adresi"), "http://203-0-113-7.sslip.io");
  await fireEvent.press(ui.getByText("Bağlan"));
  await waitFor(() => expect(bot.pair).toHaveBeenLastCalledWith("http://203-0-113-7.sslip.io", "482913")); // pairBot reddeder
});
