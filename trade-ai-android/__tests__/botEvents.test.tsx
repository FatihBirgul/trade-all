import React from "react";
import { fireEvent, render } from "@testing-library/react-native";
import Events from "../app/(tabs)/events";
import { timeText } from "../src/bot/presentation";
import { useBot } from "../src/bot/state";
import type { BotEvent } from "../src/bot/types";
import { ThemeProvider } from "../src/theme";

jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("../src/bot/state", () => ({ useBot: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 0, left: 0, right: 0 }),
}));

const AT = Math.floor(new Date(2026, 10, 25, 14, 32).getTime() / 1000);
const event = (id: number, kind: string, level: string, message: string): BotEvent => ({
  id,
  at: AT + id,
  level,
  kind,
  message,
  data: null,
});
type Bot = ReturnType<typeof useBot>;
function setBot(events: BotEvent[], overrides: Partial<Bot> = {}) {
  jest.mocked(useBot).mockReturnValue({
    phase: "ready",
    status: { currency: "USC", dry_run: true },
    positions: [],
    events,
    error: "",
    heartbeatStale: false,
    lastOkAt: 1,
    refresh: jest.fn(),
    ...overrides,
  } as unknown as Bot);
}
const screen = () =>
  render(
    <ThemeProvider>
      <Events />
    </ThemeProvider>,
  );
// Sağlayıcı olayları en yeni üstte verir.
const feed = [
  event(4, "sl_missing", "error", "EURUSD pozisyonunda stop görünmüyor"),
  event(3, "scan", "info", "12 sembol tarandı"),
  event(2, "trade_opened", "info", "EURUSD AL 0.05 lot"),
  event(1, "rate_limited", "warning", "İstek sınırı: 30 sn beklenecek"),
];

test("lists events newest first with turkish labels", async () => {
  setBot(feed);
  const ui = await screen();
  expect(ui.getByText("Stop eksik")).toBeTruthy();
  expect(ui.getByText("İşlem açıldı")).toBeTruthy();
  expect(ui.getByText("İstek sınırına takıldı")).toBeTruthy();
  expect(ui.getByText("EURUSD AL 0.05 lot")).toBeTruthy();
  expect(ui.getAllByText("25.11 14:32").length).toBe(3);
  expect(timeText(AT)).toBe("25.11 14:32");
  const order = ui
    .getAllByText(/^(Stop eksik|İşlem açıldı|İstek sınırına takıldı)$/)
    .map((node) => node.props.children);
  expect(order).toEqual(["Stop eksik", "İşlem açıldı", "İstek sınırına takıldı"]);
});

test("routine scans are hidden until all events are requested", async () => {
  setBot(feed);
  const ui = await screen();
  expect(ui.queryByText("12 sembol tarandı")).toBeNull();
  await fireEvent.press(ui.getByText("Tümü"));
  expect(ui.getByText("12 sembol tarandı")).toBeTruthy();
  expect(ui.getByText("Tarama")).toBeTruthy();
});

test("errors and warnings are coloured differently from routine events", async () => {
  setBot(feed);
  const ui = await screen();
  const colour = (text: string) => [ui.getByText(text).props.style].flat(5).find((style) => style?.color)?.color;
  const flat = (text: string) => Object.assign({}, ...[ui.getByText(text).props.style].flat(5));
  expect(flat("Stop eksik").color).not.toBe(flat("İşlem açıldı").color);
  expect(flat("İstek sınırına takıldı").color).not.toBe(flat("İşlem açıldı").color);
  expect(flat("Stop eksik").color).not.toBe(flat("İstek sınırına takıldı").color);
  expect(colour("Stop eksik")).toBeTruthy();
});

test("empty states", async () => {
  setBot([]);
  const ui = await screen();
  expect(ui.getByText("Henüz olay yok.")).toBeTruthy();
  setBot([event(1, "scan", "info", "12 sembol tarandı")]);
  await ui.rerender(
    <ThemeProvider>
      <Events />
    </ThemeProvider>,
  );
  expect(ui.getByText(/Önemli bir olay yok/)).toBeTruthy();
});

test("not connected shows the connection hint", async () => {
  setBot(feed, { phase: "revoked", status: null });
  const ui = await screen();
  expect(ui.getByText("Bu telefonun bağlantı anahtarı artık geçerli değil.")).toBeTruthy();
  expect(ui.queryByText("Stop eksik")).toBeNull();
});

test("events never loaded plus an error is a failure, not 'no events'", async () => {
  setBot([], { status: null, lastOkAt: null, error: "Sunucuya ulaşılamadı." });
  const ui = await screen();
  expect(ui.getByText("Veri alınamadı. Sunucuya ulaşılamadı.")).toBeTruthy();
  expect(ui.queryByText("Henüz olay yok.")).toBeNull();
});
