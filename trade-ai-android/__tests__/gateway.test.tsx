import React from "react";
import { Pressable, Text } from "react-native";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import { AppProvider, useApp } from "../src/state";

jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn().mockResolvedValue(null),
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));
const config = {
  origin: "https://gateway.example.com",
  session: "mobile-test-session",
};
const health = {
  status: "ok",
  version: "2.0",
  provider: "test",
  real_execution: false,
  data_mode: "live",
  provider_status: "available",
  storage: "sqlite",
};
function Probe() {
  const app = useApp();
  const [error, setError] = React.useState("");
  return (
    <>
      <Text>
        {app.mode + ":" + app.gatewayVerified + ":" + app.config.session}
      </Text>
      <Text>{error}</Text>
      <Text>{app.connectionError}</Text>
      <Pressable
        onPress={() => {
          void app
            .configure(config)
            .catch(() => setError("bağlantı reddedildi"));
        }}
      >
        <Text>Bağlan</Text>
      </Pressable>
      <Pressable onPress={() => app.setMode("live")}>
        <Text>Canlı seç</Text>
      </Pressable>
      <Pressable onPress={() => app.disconnect()}>
        <Text>Oturumu sil</Text>
      </Pressable>
      <Pressable onPress={() => app.api.health().catch(() => {})}>
        <Text>Sorgula</Text>
      </Pressable>
    </>
  );
}
const originalFetch = global.fetch;
let transport: jest.Mock;
beforeEach(() => {
  jest.clearAllMocks();
  transport = jest.fn().mockImplementation(async (url: string) => ({
    ok: true,
    json: async () =>
      url.endsWith("/gateway/session")
        ? {
            session_id: "test-session-id",
            device_id: "test-device-id",
            device_name: "Test",
            expires_at_ms: Date.now() + 60000,
            scopes: ["read", "analyze"],
            accounts: ["AUTO", "MANUAL"],
            protocol_version: 1,
          }
        : health,
  }));
  global.fetch = transport;
});
afterAll(() => {
  global.fetch = originalFetch;
});

test("sağlık doğrulanmadan oturum kaydedilmez veya CANLI açılmaz", async () => {
  transport.mockResolvedValue({
    ok: true,
    json: async () => ({ ...health, real_execution: true }),
  });
  const ui = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  await fireEvent.press(ui.getByText("Bağlan"));
  await waitFor(() => expect(ui.getByText("bağlantı reddedildi")).toBeTruthy());
  await fireEvent.press(ui.getByText("Canlı seç"));
  expect(ui.getByText("demo:false:")).toBeTruthy();
  expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
});

test("doğrulama, oturum silme ve 401 yeniden kilitleme", async () => {
  const ui = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  await fireEvent.press(ui.getByText("Bağlan"));
  await waitFor(() =>
    expect(ui.getByText("demo:true:mobile-test-session")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Canlı seç"));
  expect(ui.getByText("live:true:mobile-test-session")).toBeTruthy();
  transport.mockResolvedValue({
    ok: false,
    status: 401,
    json: async () => ({}),
  });
  await fireEvent.press(ui.getByText("Sorgula"));
  await waitFor(() =>
    expect(ui.getByText("live:false:mobile-test-session")).toBeTruthy(),
  );
  expect(ui.getByText(/CANLI erişimi kapalı/)).toBeTruthy();
  const calls = transport.mock.calls.length;
  await fireEvent.press(ui.getByText("Sorgula"));
  expect(transport.mock.calls.length).toBe(calls);
  await fireEvent.press(ui.getByText("Canlı seç"));
  expect(ui.getByText("demo:false:mobile-test-session")).toBeTruthy();
  await fireEvent.press(ui.getByText("Oturumu sil"));
  await waitFor(() => expect(ui.getByText("demo:false:")).toBeTruthy());
  expect(SecureStore.deleteItemAsync).toHaveBeenCalledWith("mobile_gateway");
});

test("bekleyen bağlantı testi oturum silindikten sonra CANLI kilidini açamaz", async () => {
  let resolve!: (value: unknown) => void;
  transport.mockReturnValue(
    new Promise((r) => {
      resolve = r;
    }),
  );
  const ui = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  await fireEvent.press(ui.getByText("Bağlan"));
  await fireEvent.press(ui.getByText("Oturumu sil"));
  resolve({ ok: true, json: async () => health });
  await waitFor(() => expect(ui.getByText("bağlantı reddedildi")).toBeTruthy());
  expect(ui.getByText("demo:false:")).toBeTruthy();
  expect(SecureStore.setItemAsync).not.toHaveBeenCalled();
});
