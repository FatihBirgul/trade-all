import React from "react";
import { fireEvent, render } from "@testing-library/react-native";
import { connectionPresentation } from "../src/domain/connection";
import { ApiError } from "../src/api/client";
import { Page } from "../src/ui";
import { ThemeProvider } from "../src/theme";
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 24, left: 0, right: 0 }),
}));
const mockPush = jest.fn();
jest.mock("expo-router", () => ({
  router: { push: (...args: unknown[]) => mockPush(...args) },
}));
test("connection evidence distinguishes missing, checking, unknown reachability, rejected and aged verification", () => {
  expect(connectionPresentation({}).title).toBe("Kayıtlı bağlantı yok");
  expect(
    connectionPresentation({ connectionPhase: "checking" }).title,
  ).toContain("doğrulanıyor");
  const network = connectionPresentation({
    connectionPhase: "offline",
    connectionErrorCode: "NETWORK",
  });
  expect(network.detail).toContain("kesin neden belirlenemedi");
  expect(network.title).not.toContain("Telefon çevrimdışı");
  expect(new ApiError("NETWORK").message).not.toContain("Ağınızı kontrol edin");
  expect(
    connectionPresentation({
      connectionPhase: "offline",
      connectionErrorCode: "BACKEND_UNAVAILABLE",
    }).title,
  ).toContain("Gateway yanıtladı");
  expect(connectionPresentation({ connectionPhase: "revoked" }).attention).toBe(
    true,
  );
  expect(
    connectionPresentation(
      { connectionPhase: "ready", lastVerifiedAt: 1000 },
      301001,
    ).stale,
  ).toBe(true);
  expect(
    connectionPresentation(
      { connectionPhase: "ready", lastVerifiedAt: 1000 },
      2000,
    ).stale,
  ).toBe(false);
});
test("offline DEMO page exposes compact actionable status without duplicating raw errors", async () => {
  const ui = await render(
    <ThemeProvider>
      <Page
        connection={{
          connectionPhase: "offline",
          connectionErrorCode: "NETWORK",
          connectionError: "raw network error",
        }}
      />
    </ThemeProvider>,
  );
  expect(ui.getByText("● DEMO · ÖRNEK VERİ")).toBeTruthy();
  expect(ui.queryByText("raw network error")).toBeNull();
  await fireEvent.press(ui.getByLabelText("Bağlantı ayrıntılarını aç"));
  expect(mockPush).toHaveBeenCalledWith("/settings");
});
