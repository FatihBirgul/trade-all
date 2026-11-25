import React from "react";
import { AppState, Pressable, Text } from "react-native";
import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import { BotProvider, POLL_MS, useBot } from "../src/bot/state";

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));
const store = SecureStore as jest.Mocked<typeof SecureStore>;

const ORIGIN = "https://194-163-185-83.sslip.io";
const TOKEN = "t".repeat(43);
const saved = JSON.stringify({ origin: ORIGIN, token: TOKEN, pairedAt: 1 });
const START = 1_800_000_000_000;

type Server = {
  heartbeatAt: number | null;
  serverTime: number;
  unauthorized: boolean;
  down: boolean;
  events: { id: number; at: number; level: string; kind: string; message: string; data: null }[];
};
function fakeServer(overrides: Partial<Server> = {}) {
  const server: Server = {
    heartbeatAt: START / 1000 - 10,
    serverTime: START / 1000,
    unauthorized: false,
    down: false,
    events: [],
    ...overrides,
  };
  const reply = (body: unknown, status = 200) => ({ ok: status < 300, status, json: async () => body });
  const transport = jest.fn(async (input: unknown, init?: { body?: string }) => {
    const path = String(input).replace(ORIGIN, "");
    if (server.down) throw new TypeError("Network request failed");
    if (path === "/pair")
      return JSON.parse(init?.body ?? "{}").code === "482913" ? reply({ token: TOKEN }) : reply({ detail: "x" }, 401);
    if (server.unauthorized) return reply({ detail: "geçersiz ya da eksik token" }, 401);
    if (path === "/status")
      return reply({ equity: 3000, halted: false, heartbeat_at: server.heartbeatAt, server_time: server.serverTime });
    if (path === "/positions") return reply({ positions: [{ position_id: "2001", symbol: "EURUSD" }] });
    if (path.startsWith("/events?newest=true")) return reply({ events: server.events.slice().reverse() });
    if (path.startsWith("/events?after=")) {
      const after = Number(path.split("=")[1]);
      return reply({ events: server.events.filter((event) => event.id > after) });
    }
    return reply({ detail: "yok" }, 404);
  });
  return { server, transport: transport as unknown as typeof fetch, calls: transport };
}

function Probe() {
  const bot = useBot();
  return (
    <>
      <Text>{"phase:" + bot.phase}</Text>
      <Text>{"equity:" + (bot.status?.equity ?? "-")}</Text>
      <Text>{"positions:" + bot.positions.map((p) => p.position_id).join(",")}</Text>
      <Text>{"events:" + bot.events.map((e) => e.id).join(",")}</Text>
      <Text>{"stale:" + bot.heartbeatStale}</Text>
      <Text>{"error:" + bot.error}</Text>
      <Pressable onPress={() => void bot.pair(ORIGIN, "482913").catch(() => {})}>
        <Text>pair</Text>
      </Pressable>
      <Pressable onPress={() => void bot.disconnect()}>
        <Text>disconnect</Text>
      </Pressable>
    </>
  );
}

let clock = START;
let appListener: ((state: string) => void) | null = null;
const tick = async (ms: number) => {
  clock += ms;
  await act(async () => {
    await jest.advanceTimersByTimeAsync(ms);
  });
};
const flush = () => tick(0);
const mount = async (transport: typeof fetch) => {
  const ui = await render(
    <BotProvider transport={transport} now={() => clock}>
      <Probe />
    </BotProvider>,
  );
  await flush();
  return ui;
};
const paths = (calls: jest.Mock, prefix: string) =>
  calls.mock.calls.filter(([url]) => String(url).replace(ORIGIN, "").startsWith(prefix)).length;

beforeEach(() => {
  jest.useFakeTimers();
  clock = START;
  appListener = null;
  store.getItemAsync.mockReset().mockResolvedValue(null);
  store.setItemAsync.mockClear();
  store.deleteItemAsync.mockClear();
  Object.defineProperty(AppState, "currentState", { value: "active", configurable: true });
  jest.spyOn(AppState, "addEventListener").mockImplementation(((_: string, handler: (state: string) => void) => {
    appListener = handler;
    return { remove: jest.fn() };
  }) as never);
});
afterEach(() => {
  jest.useRealTimers();
  jest.restoreAllMocks();
});

test("starts unconfigured", async () => {
  const { transport, calls } = fakeServer();
  const ui = await mount(transport);
  expect(ui.getByText("phase:unconfigured")).toBeTruthy();
  await tick(POLL_MS * 3);
  expect(calls).not.toHaveBeenCalled();
});

test("becomes ready after pair and keeps the token only in secure storage", async () => {
  const { transport } = fakeServer();
  const ui = await mount(transport);
  await fireEvent.press(ui.getByText("pair"));
  await flush();
  expect(ui.getByText("phase:ready")).toBeTruthy();
  expect(ui.getByText("equity:3000")).toBeTruthy();
  expect(ui.getByText("positions:2001")).toBeTruthy();
  expect(store.setItemAsync).toHaveBeenCalledWith("trade_bot", expect.stringContaining(TOKEN));
  expect(ui.queryByText(new RegExp(TOKEN))).toBeNull();
});

test("restores a saved connection and polls every 5 seconds", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  const { transport, calls } = fakeServer();
  const ui = await mount(transport);
  expect(ui.getByText("phase:ready")).toBeTruthy();
  expect(paths(calls, "/status")).toBe(1);
  await tick(POLL_MS);
  await tick(POLL_MS);
  expect(paths(calls, "/status")).toBe(3);
  expect(paths(calls, "/events")).toBe(1); // olaylar 15 saniyede bir
  await tick(POLL_MS);
  expect(paths(calls, "/events")).toBe(2);
});

test("ignores a corrupted saved connection", async () => {
  store.getItemAsync.mockResolvedValue('{"origin":"http://x","token":"kisa"}');
  const { transport, calls } = fakeServer();
  const ui = await mount(transport);
  expect(ui.getByText("phase:unconfigured")).toBeTruthy();
  expect(calls).not.toHaveBeenCalled();
});

test("shows newest events first and appends only new ones", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  const event = (id: number) => ({ id, at: 1, level: "info", kind: "k", message: "m", data: null });
  const { transport, server } = fakeServer({ events: [event(1), event(2)] });
  const ui = await mount(transport);
  expect(ui.getByText("events:2,1")).toBeTruthy();
  server.events.push(event(3));
  await tick(POLL_MS * 3);
  expect(ui.getByText("events:3,2,1")).toBeTruthy();
  await tick(POLL_MS * 3);
  expect(ui.getByText("events:3,2,1")).toBeTruthy();
});

test("marks heartbeat stale after 5 minutes", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  const { transport, server } = fakeServer();
  const ui = await mount(transport);
  expect(ui.getByText("stale:false")).toBeTruthy();
  server.serverTime += 301; // sunucu yanıt veriyor ama botun döngüsü 5 dakikadır atmıyor
  await tick(POLL_MS);
  expect(ui.getByText("stale:true")).toBeTruthy();
  server.heartbeatAt = server.serverTime - 5;
  await tick(POLL_MS);
  expect(ui.getByText("stale:false")).toBeTruthy();
});

test("a wrong phone clock does not fake a stale or fresh heartbeat", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  clock = START + 3_600_000; // telefon saati bir saat ileri
  const { transport, server } = fakeServer();
  const ui = await mount(transport);
  expect(ui.getByText("stale:false")).toBeTruthy();
  server.heartbeatAt = null;
  await tick(POLL_MS);
  expect(ui.getByText("stale:true")).toBeTruthy();
});

test("marks data stale when the server stops answering for 5 minutes", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  const { transport, server } = fakeServer();
  const ui = await mount(transport);
  server.down = true;
  await tick(POLL_MS);
  expect(ui.getByText(/^error:Sunucuya ulaşılamadı/)).toBeTruthy();
  expect(ui.getByText("stale:false")).toBeTruthy();
  expect(ui.getByText("equity:3000")).toBeTruthy(); // son bilinen veri silinmez
  await tick(300_000);
  expect(ui.getByText("stale:true")).toBeTruthy();
  server.down = false;
  await tick(POLL_MS);
  expect(ui.getByText("stale:false")).toBeTruthy();
  expect(ui.getByText("error:")).toBeTruthy();
});

test("goes revoked on 401 and clears storage", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  const { transport, server, calls } = fakeServer();
  const ui = await mount(transport);
  server.unauthorized = true;
  await tick(POLL_MS);
  expect(ui.getByText("phase:revoked")).toBeTruthy();
  expect(ui.getByText("equity:-")).toBeTruthy();
  expect(ui.getByText("positions:")).toBeTruthy();
  expect(store.deleteItemAsync).toHaveBeenCalledWith("trade_bot");
  const before = calls.mock.calls.length;
  await tick(POLL_MS * 3);
  expect(calls.mock.calls.length).toBe(before);
});

test("stops polling in background and refreshes on return", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  const { transport, calls } = fakeServer();
  await mount(transport);
  const before = paths(calls, "/status");
  await act(async () => appListener?.("background"));
  await tick(POLL_MS * 4);
  expect(paths(calls, "/status")).toBe(before);
  await act(async () => appListener?.("active"));
  await flush();
  expect(paths(calls, "/status")).toBe(before + 1);
});

test("disconnect clears data and storage", async () => {
  store.getItemAsync.mockResolvedValue(saved);
  const { transport, calls } = fakeServer();
  const ui = await mount(transport);
  await fireEvent.press(ui.getByText("disconnect"));
  await flush();
  expect(ui.getByText("phase:unconfigured")).toBeTruthy();
  expect(ui.getByText("equity:-")).toBeTruthy();
  expect(store.deleteItemAsync).toHaveBeenCalledWith("trade_bot");
  const before = calls.mock.calls.length;
  await tick(POLL_MS * 2);
  expect(calls.mock.calls.length).toBe(before);
  await waitFor(() => expect(ui.getByText("stale:false")).toBeTruthy());
});
