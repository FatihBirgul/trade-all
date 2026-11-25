import React from "react";
import { Alert, type AlertButton } from "react-native";
import { act, fireEvent, render, waitFor, within } from "@testing-library/react-native";
import Positions from "../app/(tabs)/positions";
import { BotError } from "../src/bot/client";
import { checkLevel, parsePrice } from "../src/bot/PositionCard";
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
  tp2: 2370,
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
      <Positions />
    </ThemeProvider>,
  );
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
const edit = async (ui: Awaited<ReturnType<typeof screen>>, field: "SL" | "TP", value: string, symbol = "EURUSD") => {
  if (!ui.queryByLabelText("Yeni SL " + symbol)) await fireEvent.press(ui.getAllByText("SL/TP düzenle")[0]);
  await fireEvent.changeText(ui.getByLabelText("Yeni " + field + " " + symbol), value);
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
});

test("take profit shown is the broker order (tp2), not the partial-profit level", async () => {
  setBot([eurusd, gold]);
  const ui = await screen();
  const tp = ui.getAllByTestId("row-Kâr al (TP)");
  expect(within(tp[0]).getByText("1,107")).toBeTruthy(); // tp2
  expect(within(tp[1]).getByText("2370")).toBeTruthy(); // elle açılmış pozisyonun broker TP'si
  expect(within(ui.getByTestId("row-Kısmi kâr seviyesi")).getByText("1,1042")).toBeTruthy(); // tp1 yalnızca bilgi
});

test("positions never loaded plus an error is a failure, not 'no open positions'", async () => {
  const { bot } = setBot([], { status: null, lastOkAt: null, error: "Sunucuya ulaşılamadı." } as never);
  const ui = await screen();
  expect(ui.getByText("Veri alınamadı. Sunucuya ulaşılamadı.")).toBeTruthy();
  expect(ui.queryByText("Açık pozisyon yok.")).toBeNull();
  expect(ui.queryByText(/açık pozisyon$/)).toBeNull();
  await fireEvent.press(ui.getByText("Yeniden dene"));
  expect(bot.refresh).toHaveBeenCalled();
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

test("edit sends only changed fields after showing old and new values", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await edit(ui, "SL", "1,0990");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(api.patchPosition).not.toHaveBeenCalled(); // önce onay
  expect(dialog().title).toBe("EURUSD değişikliği onaylansın mı?");
  expect(dialog().message).toContain("Zarar durdur (SL): 1,0972 → 1,099");
  expect(dialog().message).toContain("Anlık fiyat: 1,1035");
  expect(dialog().message).not.toContain("Kâr al");
  await pressDialog("Kaydet");
  await waitFor(() => expect(api.patchPosition).toHaveBeenCalledWith("2001", { sl: 1.099 }));

  await edit(ui, "SL", "1.0972"); // şimdiki değerle aynı
  await edit(ui, "TP", "1.1090");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(dialog().message).toContain("Kâr al (TP): 1,107 → 1,109");
  await pressDialog("Kaydet");
  await waitFor(() => expect(api.patchPosition).toHaveBeenLastCalledWith("2001", { tp: 1.109 }));
  expect(api.patchPosition).toHaveBeenCalledTimes(2);
});

test("tp equal to the broker tp is no change; tp equal to the partial level is a change", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await edit(ui, "TP", "1.107"); // broker TP ile aynı
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(ui.getByText("Değişiklik yok.")).toBeTruthy();
  expect(alert).not.toHaveBeenCalled();
  await edit(ui, "TP", "1.1042"); // tp1: broker'da böyle bir emir yok, gönderilmeli
  await fireEvent.press(ui.getByText("Kaydet"));
  await pressDialog("Kaydet");
  await waitFor(() => expect(api.patchPosition).toHaveBeenCalledWith("2001", { tp: 1.1042 }));
});

test("cancelling the confirmation sends nothing and keeps the form", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await edit(ui, "SL", "1.0990");
  await fireEvent.press(ui.getByText("Kaydet"));
  await pressDialog("Vazgeç");
  expect(api.patchPosition).not.toHaveBeenCalled();
  expect(ui.getByDisplayValue("1.0990")).toBeTruthy();
});

test("a thousands separator or a dropped digit cannot silently remove protection", async () => {
  const btc: BotPosition = { ...eurusd, position_id: "2003", symbol: "BTCUSD", entry: 65000, sl: 64500, tp1: 65500, tp2: 66000, price: 65100 };
  const { api } = setBot([btc]);
  const ui = await screen();
  for (const typed of ["64.800", "64,800", "6480", "648000"]) {
    await edit(ui, "SL", typed, "BTCUSD");
    await fireEvent.press(ui.getByText("Kaydet"));
    expect(ui.getByText(/çok uzak\. Yazım hatası olabilir/)).toBeTruthy();
  }
  expect(alert).not.toHaveBeenCalled();
  expect(api.patchPosition).not.toHaveBeenCalled();
  await edit(ui, "SL", "64800", "BTCUSD");
  await fireEvent.press(ui.getByText("Kaydet"));
  await pressDialog("Kaydet");
  await waitFor(() => expect(api.patchPosition).toHaveBeenCalledWith("2003", { sl: 64800 }));
});

test("stop or target on the wrong side of the price is blocked before the network", async () => {
  const { api } = setBot([eurusd, gold]);
  const ui = await screen();
  await edit(ui, "SL", "1.1050"); // AL: SL fiyatın üstünde olamaz
  await fireEvent.press(ui.getAllByText("Kaydet")[0]);
  expect(ui.getByText("SL anlık fiyatın (1,1035) altında olmalı.")).toBeTruthy();
  await edit(ui, "SL", "");
  await edit(ui, "TP", "1.1000"); // AL: TP fiyatın altında olamaz
  await fireEvent.press(ui.getAllByText("Kaydet")[0]);
  expect(ui.getByText("TP anlık fiyatın (1,1035) üstünde olmalı.")).toBeTruthy();
  expect(alert).not.toHaveBeenCalled();
  expect(api.patchPosition).not.toHaveBeenCalled();
  // SAT pozisyonunda yönler terstir.
  expect(checkLevel("sl", 2380, gold)).toMatchObject({ ok: false });
  expect(checkLevel("sl", 2390, gold)).toEqual({ ok: true, widens: false });
  expect(checkLevel("sl", 2395, gold)).toEqual({ ok: true, widens: true });
  expect(checkLevel("tp", 2395, gold)).toMatchObject({ ok: false });
  expect(checkLevel("tp", 2360, gold)).toEqual({ ok: true, widens: false });
});

test("moving the stop further away needs an explicit risk warning", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await edit(ui, "SL", "1.0900"); // 1.0972'den daha uzak
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(dialog().title).toBe("Dikkat: zarar durdurma uzaklaşıyor");
  expect(dialog().message).toContain("BÜYÜR");
  expect(dialog().buttons.map((b) => b.text)).toEqual(["Vazgeç", "Riski büyüt ve kaydet"]);
  expect(api.patchPosition).not.toHaveBeenCalled();
  await pressDialog("Riski büyüt ve kaydet");
  await waitFor(() => expect(api.patchPosition).toHaveBeenCalledWith("2001", { sl: 1.09 }));
});

test("in dry run every position dialog says the action is real", async () => {
  setBot([eurusd], { status: { currency: "USC", dry_run: true } } as never);
  const ui = await screen();
  await fireEvent.press(ui.getByText("Kapat"));
  expect(dialog().message).toContain("GERÇEK hesapta");
  await edit(ui, "SL", "1.0990");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(dialog().message).toContain("GERÇEK hesapta");
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
  for (const bad of ["0", "-1.1", "abc", "1.1.1", "1e5", "99999999999999999999999"]) {
    await fireEvent.changeText(ui.getByLabelText("Yeni SL EURUSD"), bad);
    await fireEvent.press(ui.getByText("Kaydet"));
    expect(ui.getByText("SL pozitif bir sayı olmalı.")).toBeTruthy();
  }
  await fireEvent.changeText(ui.getByLabelText("Yeni SL EURUSD"), "");
  await fireEvent.changeText(ui.getByLabelText("Yeni TP EURUSD"), "0");
  await fireEvent.press(ui.getByText("Kaydet"));
  expect(ui.getByText("TP pozitif bir sayı olmalı.")).toBeTruthy();
  expect(api.patchPosition).not.toHaveBeenCalled();
  expect(alert).not.toHaveBeenCalled();
  expect(parsePrice(" 1,25 ")).toBe(1.25);
  expect(parsePrice("")).toBeUndefined();
});

test("turning managed stop off asks first; turning it on does not", async () => {
  const { api } = setBot([eurusd]);
  const ui = await screen();
  await fireEvent(ui.getByLabelText("Kademeli stop EURUSD"), "valueChange", false);
  expect(api.patchPosition).not.toHaveBeenCalled();
  expect(dialog().title).toBe("Kademeli stop kapatılsın mı?");
  await pressDialog("Vazgeç");
  expect(api.patchPosition).not.toHaveBeenCalled();
  await fireEvent(ui.getByLabelText("Kademeli stop EURUSD"), "valueChange", false);
  await pressDialog("Kapat");
  await waitFor(() => expect(api.patchPosition).toHaveBeenCalledWith("2001", { manage: false }));
  expect(ui.getByText("Kademeli stop kapatıldı.")).toBeTruthy();
  alert.mockClear();
  await fireEvent(ui.getByLabelText("Kademeli stop EURUSD"), "valueChange", true);
  await waitFor(() => expect(api.patchPosition).toHaveBeenLastCalledWith("2001", { manage: true }));
  expect(alert).not.toHaveBeenCalled();
});

test("conflict shows server message", async () => {
  const { api } = setBot([eurusd]);
  const detail = "pozisyonda sonucu beklenen başka bir istek var";
  api.patchPosition.mockRejectedValue(new BotError("HTTP_409", detail, false, 409));
  const ui = await screen();
  await edit(ui, "SL", "1.0990");
  await fireEvent.press(ui.getByText("Kaydet"));
  await pressDialog("Kaydet");
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
