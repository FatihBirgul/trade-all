import React from "react";
import { Pressable, Text, AppState } from "react-native";
import { act, render, fireEvent, waitFor } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import { AppProvider, useApp } from "../src/state";
import { createApi } from "../src/api/client";
const first = { origin: "https://qa.example.test", session: "mobile-one" };
const health = {
  status: "ok",
  version: "2",
  data_mode: "live",
  storage: "sqlite",
  provider: "test",
  provider_status: "available",
  real_execution: false,
};
const metadata = () => ({
  session_id: "id",
  device_id: "device",
  device_name: "QA",
  protocol_version: 1,
  expires_at_ms: Date.now() + 3600000,
  scopes: ["read"],
  accounts: ["AUTO"],
});
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(),
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));
function Probe() {
  const app = useApp();
  return (
    <>
      <Text>
        {app.mode + "|" + app.gatewayVerified + "|" + app.connectionPhase}
      </Text>
      <Text>{app.connectionError}</Text>
      <Pressable
        onPress={() =>
          app.configure({ ...first, session: "mobile-two" }).catch(() => {})
        }
      >
        <Text>New connection</Text>
      </Pressable>
      <Pressable
        onPress={() => {
          void app.api.markets().catch(() => {});
        }}
      >
        <Text>Slow query</Text>
      </Pressable>
    </>
  );
}
const original = global.fetch;
afterEach(() => {
  global.fetch = original;
});
test("saved connection is verified read-only on native startup while DEMO remains DEMO", async () => {
  jest
    .mocked(SecureStore.getItemAsync)
    .mockImplementation(async (key) =>
      key === "mobile_gateway" ? JSON.stringify(first) : null,
    );
  const transport = jest.fn(async (url: string) => ({
    ok: true,
    json: async () => (url.endsWith("/gateway/session") ? metadata() : health),
  }));
  global.fetch = transport as unknown as typeof fetch;
  const ui = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  await waitFor(() => expect(ui.getByText("demo|true|ready")).toBeTruthy());
  expect(transport).toHaveBeenCalledTimes(2);
  expect(
    transport.mock.calls.every((call) => !String(call[0]).includes("analyze")),
  ).toBe(true);
  await ui.unmount();
});
test("a late old-session 401 cannot revoke a newly verified connection", async () => {
  jest
    .mocked(SecureStore.getItemAsync)
    .mockImplementation(async (key) =>
      key === "mobile_gateway" ? JSON.stringify(first) : null,
    );
  let finish!: (v: unknown) => void;
  global.fetch = jest.fn(async (url: string) =>
    url.endsWith("/markets")
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : {
          ok: true,
          json: async () =>
            url.endsWith("/gateway/session") ? metadata() : health,
        },
  ) as unknown as typeof fetch;
  const ui = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  await waitFor(() => expect(ui.getByText("demo|true|ready")).toBeTruthy());
  await fireEvent.press(ui.getByText("Slow query"));
  await fireEvent.press(ui.getByText("New connection"));
  await waitFor(() => expect(ui.getByText("demo|true|ready")).toBeTruthy());
  await act(async () =>
    finish({ ok: false, status: 401, json: async () => ({}) }),
  );
  expect(ui.getByText("demo|true|ready")).toBeTruthy();
  await ui.unmount();
});
test("concurrent identical GETs coalesce but subsequent refresh performs a new request", async () => {
  let complete!: (v: unknown) => void;
  const transport = jest.fn(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  const api = createApi(first, transport as unknown as typeof fetch);
  const a = api.health(),
    b = api.health();
  expect(transport).toHaveBeenCalledTimes(1);
  complete({ ok: true, json: async () => health });
  await Promise.all([a, b]);
  transport.mockResolvedValue({ ok: true, json: async () => health });
  await api.health();
  expect(transport).toHaveBeenCalledTimes(2);
  api.dispose();
});

test("foreground events do not start a second verification while startup is already checking", async () => {
  const callbacks: ((state: "active") => void)[] = [];
  const spy = jest
    .spyOn(AppState, "addEventListener")
    .mockImplementation((_event, listener) => {
      callbacks.push(listener as (state: "active") => void);
      return { remove: jest.fn() };
    });
  jest
    .mocked(SecureStore.getItemAsync)
    .mockImplementation(async (key) =>
      key === "mobile_gateway" ? JSON.stringify(first) : null,
    );
  let finish!: (response: unknown) => void;
  const transport = jest.fn(async (url: string) =>
    url.endsWith("/gateway/session")
      ? new Promise((resolve) => {
          finish = resolve;
        })
      : { ok: true, json: async () => health },
  );
  global.fetch = transport as unknown as typeof fetch;
  try {
    const ui = await render(
      <AppProvider>
        <Probe />
      </AppProvider>,
    );
    await waitFor(() =>
      expect(ui.getByText("demo|false|checking")).toBeTruthy(),
    );
    await act(async () => callbacks.forEach((callback) => callback("active")));
    expect(transport).toHaveBeenCalledTimes(1);
    await act(async () => finish({ ok: true, json: async () => metadata() }));
    await waitFor(() => expect(ui.getByText("demo|true|ready")).toBeTruthy());
    expect(transport).toHaveBeenCalledTimes(2);
    await ui.unmount();
  } finally {
    spy.mockRestore();
  }
});

test("unreachable saved gateway stays DEMO/offline with evidence code; no backend writes", async () => {
  jest
    .spyOn(AppState, "addEventListener")
    .mockReturnValue({ remove: jest.fn() });
  jest
    .mocked(SecureStore.getItemAsync)
    .mockImplementation(async (key) =>
      key === "mobile_gateway" ? JSON.stringify(first) : null,
    );
  const transport = jest
    .fn()
    .mockRejectedValue(new TypeError("Network request failed"));
  global.fetch = transport as unknown as typeof fetch;
  const ui = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  await waitFor(() => expect(ui.getByText("demo|false|offline")).toBeTruthy());
  expect(ui.getByText(/Gateway bağlantısı kurulamadı/)).toBeTruthy();
  expect(transport).toHaveBeenCalledTimes(1);
  expect(transport.mock.calls[0][1].method).toBe("GET");
  await ui.unmount();
});
