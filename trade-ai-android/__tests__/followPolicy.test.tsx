import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { useApp } from "../src/state";
import { ThemeProvider } from "../src/theme";
import { FollowPolicyControls } from "../src/FollowPolicyControls";
import { ApiError } from "../src/api/client";
import Notifications from "../app/notifications";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("expo-router", () => ({ router: { push: jest.fn() } }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }),
}));
const id = "a".repeat(64);
function app(write = false, set = jest.fn()) {
  jest
    .mocked(useApp)
    .mockReturnValue({
      mode: "live",
      config: {
        origin: "https://gateway.example.com",
        session: "fixture-mobile",
      },
      connectionKey: 1,
      gatewayVerified: true,
      account: "MANUAL",
      sessionInfo: {
        accounts: ["MANUAL"],
        scopes: ["read", ...(write ? ["scanner:write"] : [])],
        capabilities: ["follow-source-events-v1"],
      },
      api: {
        followPolicy: jest
          .fn()
          .mockResolvedValue({
            tracking_id: id,
            portfolio_id: "MANUAL",
            data_mode: "live",
            notify_source_changes: false,
            source_event_ttl_ms: 900000,
            delivery_service: "not_configured",
          }),
        setFollowPolicy: set,
        notifications: jest
          .fn()
          .mockResolvedValue([
            {
              notification_id: "fixture-expired",
              kind: "analysis",
              created_at_ms: 1,
              delivery_status: "pending",
              delivery_service: "not_configured",
              data_mode: "live",
              details: {
                tracking_id: id,
                change_kind: "source_unavailable",
                expires_at_ms: 2,
              },
            },
          ]),
      },
    } as unknown as ReturnType<typeof useApp>);
}
test("read-only source preference never offers an active write control", async () => {
  const set = jest.fn();
  app(false, set);
  const ui = await render(
    <ThemeProvider>
      <FollowPolicyControls id={id} account="MANUAL" />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText(/Kapalı/)).toBeTruthy());
  expect(ui.queryByText("Kaynak uyarılarını aç")).toBeNull();
  expect(set).not.toHaveBeenCalled();
});
test("lost preference response retries same desired boolean, not inverse toggle", async () => {
  const set = jest
    .fn()
    .mockRejectedValueOnce(new ApiError("NETWORK", true))
    .mockResolvedValueOnce({ notify_source_changes: true });
  app(true, set);
  const ui = await render(
    <ThemeProvider>
      <FollowPolicyControls id={id} account="MANUAL" />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Kaynak uyarılarını aç")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Kaynak uyarılarını aç"));
  await waitFor(() =>
    expect(ui.getByText("Aynı tercihi yeniden dene")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Aynı tercihi yeniden dene"));
  await waitFor(() => expect(set).toHaveBeenCalledTimes(2));
  expect(set.mock.calls).toEqual([
    [id, true],
    [id, true],
  ]);
});
test("expired pending source warning is never shown as delivered", async () => {
  app();
  const ui = await render(
    <ThemeProvider>
      <Notifications />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("Takip verisi geçerli değil")).toBeTruthy(),
  );
  expect(
    ui.getByText("Uyarının geçerlilik süresi doldu · Gönderilmedi"),
  ).toBeTruthy();
});
