import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { NotificationPreferences } from "../src/NotificationPreferences";
import { ThemeProvider } from "../src/theme";
import { useApp } from "../src/state";
import { ApiError, createApi } from "../src/api/client";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-crypto", () => ({
  randomUUID: () => "fixture-preference-request-1",
}));
const prefs = {
  portfolio_id: "MANUAL",
  data_mode: "live",
  revision: 0,
  observed_at_ms: 1800000000000,
  enabled: false,
  categories: { analysis: false, source: false, risk: false, system: false },
  recipient_id: null,
  recipient_status: "not_registered",
  expires_at_ms: null,
  push_status: "NOT_CONFIGURED",
  device_credentials_supported: false,
  sender_running: false,
};
function setup(writable = false, supported = true) {
  const api = {
    notificationPreferences: jest.fn().mockResolvedValue(prefs),
    setNotificationPreferences: jest
      .fn()
      .mockResolvedValue({ ...prefs, revision: 1 }),
  };
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    account: "MANUAL",
    connectionKey: 1,
    gatewayVerified: true,
    config: { session: "fixture-session" },
    sessionInfo: {
      accounts: ["MANUAL"],
      scopes: ["read", ...(writable ? ["notifications:write"] : [])],
      capabilities: supported ? ["notification-controls-v1"] : [],
    },
    api,
  } as unknown as ReturnType<typeof useApp>);
  return api;
}
test("old Gateway does not request new controls", async () => {
  const api = setup(false, false);
  const ui = await render(
    <ThemeProvider>
      <NotificationPreferences />
    </ThemeProvider>,
  );
  expect(ui.getByText(/Güncel Gateway/)).toBeTruthy();
  expect(api.notificationPreferences).not.toHaveBeenCalled();
});
test("read only permissions display unconfigured state without successful registration claim", async () => {
  const api = setup();
  const ui = await render(
    <ThemeProvider>
      <NotificationPreferences />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText(/yalnız okunabilir/)).toBeTruthy());
  expect(ui.getByText("NOT_CONFIGURED")).toBeTruthy();
  await fireEvent.press(ui.getByText("Bildirim tercihlerini kaydet"));
  expect(api.setNotificationPreferences).not.toHaveBeenCalled();
});
test("lost response retries exact frozen preference command", async () => {
  const api = setup(true);
  api.setNotificationPreferences.mockRejectedValueOnce(
    new ApiError("NETWORK_ERROR", true),
  );
  const ui = await render(
    <ThemeProvider>
      <NotificationPreferences />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Bildirim tercihi: Kapalı")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Analiz: Kapalı"));
  await fireEvent.press(ui.getByText("Bildirim tercihlerini kaydet"));
  await waitFor(() =>
    expect(ui.getByText("Aynı tercih isteğini yeniden dene")).toBeTruthy(),
  );
  const first = api.setNotificationPreferences.mock.calls[0];
  await fireEvent.press(ui.getByText("Aynı tercih isteğini yeniden dene"));
  await waitFor(() =>
    expect(api.setNotificationPreferences).toHaveBeenCalledTimes(2),
  );
  expect(api.setNotificationPreferences.mock.calls[1]).toEqual(first);
});
test("client does not infer notification authority from paper grants", async () => {
  const fetcher = jest.fn();
  const api = createApi(
    {
      origin: "https://gateway.example.com",
      session: "fixture",
      scopes: ["read", "paper:write"],
    },
    fetcher,
  );
  await expect(
    api.setNotificationPreferences("MANUAL", {
      idempotency_key: "fixture-request-1",
      expected_revision: 0,
      enabled: true,
    }),
  ).rejects.toMatchObject({ code: "SCOPE_DENIED" });
  expect(fetcher).not.toHaveBeenCalled();
});
test("fixture-mode response cannot be shown as a live preference", async () => {
  const fetcher = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ ...prefs, data_mode: "fixture" }),
  });
  const api = createApi(
    {
      origin: "https://gateway.example.com",
      session: "fixture-session",
      scopes: ["read"],
    },
    fetcher,
  );
  await expect(api.notificationPreferences("MANUAL")).rejects.toMatchObject({
    code: "INVALID_RESPONSE",
  });
});
