import React from "react";
import { Text, StyleSheet, Platform } from "react-native";
import { act, fireEvent, render } from "@testing-library/react-native";
import * as SystemUI from "expo-system-ui";
import { NavigationBar } from "expo-navigation-bar";
import * as SecureStore from "expo-secure-store";
import { ThemeProvider, useTheme } from "../src/theme";
import { StartupGate, StartupScreen } from "../src/StartupScreen";
import { TabIcon } from "../src/TabIcon";
import { AppProvider, useApp } from "../src/state";
import { FONT_DEADLINE_MS, THEME_DEADLINE_MS } from "../src/startup";
jest.mock("expo-splash-screen", () => ({
  hideAsync: jest.fn().mockResolvedValue(undefined),
  preventAutoHideAsync: jest.fn().mockResolvedValue(true),
  setOptions: jest.fn(),
}));
jest.mock("expo-font", () => ({
  isLoaded: () => true,
  loadAsync: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("expo-system-ui", () => ({
  setBackgroundColorAsync: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("expo-navigation-bar", () => ({
  NavigationBar: { setStyle: jest.fn() },
}));
function ThemeProbe() {
  const t = useTheme();
  return (
    <Text>
      {t.ready ? (t.isDark ? "ready-dark" : "ready-light") : "theme-pending"}
    </Text>
  );
}
function SessionProbe() {
  const a = useApp();
  return (
    <>
      <Text>App entry</Text>
      <Text>{a.gatewayVerified ? "VERIFIED" : "NOT_VERIFIED"}</Text>
      <Text>{a.mode}</Text>
    </>
  );
}
afterEach(() => {
  jest.restoreAllMocks();
  jest.useRealTimers();
});
test("ready fonts enter immediately after local theme restoration, no minimum dwell", async () => {
  jest.spyOn(SecureStore, "getItemAsync").mockResolvedValue("light");
  const v = await render(
    <ThemeProvider>
      <StartupGate fontsReady fontError={null}>
        <ThemeProbe />
      </StartupGate>
    </ThemeProvider>,
  );
  expect(v.getByText("ready-light")).toBeTruthy();
  expect(v.queryByLabelText("Uygulama hazırlanıyor")).toBeNull();
});
test("slow font reaches bounded text navigation without broken glyphs, and later recovers", async () => {
  jest.useFakeTimers();
  jest.spyOn(SecureStore, "getItemAsync").mockResolvedValue(null);
  const tree = (ready: boolean) => (
    <ThemeProvider>
      <StartupGate fontsReady={ready} fontError={null}>
        <Text>Main</Text>
        <TabIcon name="home-outline" focused color="#fff" />
      </StartupGate>
    </ThemeProvider>
  );
  const v = await render(tree(false));
  expect(
    StyleSheet.flatten(v.getByTestId("startup-frame").props.style)
      .backgroundColor,
  ).toBe("#111316");
  await act(() => jest.advanceTimersByTime(FONT_DEADLINE_MS - 1));
  expect(v.queryByText("Main")).toBeNull();
  await act(() => jest.advanceTimersByTime(1));
  expect(v.getByText("Main")).toBeTruthy();
  expect(v.getByTestId("tab-icon-fallback")).toBeTruthy();
  await v.rerender(tree(true));
  expect(v.queryByTestId("tab-icon-fallback")).toBeNull();
  expect(v.queryByText(/İkonlar yüklenemedi/)).toBeNull();
});
test("theme storage timeout uses dark and ignores a late light response without flashing", async () => {
  jest.useFakeTimers();
  let resolve!: (s: string | null) => void;
  jest.spyOn(SecureStore, "getItemAsync").mockImplementation(
    () =>
      new Promise((r) => {
        resolve = r;
      }),
  );
  const v = await render(
    <ThemeProvider>
      <StartupGate fontsReady fontError={null}>
        <ThemeProbe />
      </StartupGate>
    </ThemeProvider>,
  );
  expect(v.queryByText("ready-dark")).toBeNull();
  await act(() => jest.advanceTimersByTime(THEME_DEADLINE_MS));
  expect(v.getByText("ready-dark")).toBeTruthy();
  await act(() => resolve("light"));
  expect(v.getByText("ready-dark")).toBeTruthy();
});
test("failed theme/session restoration still opens safely, without online success or worker writes", async () => {
  jest
    .spyOn(SecureStore, "getItemAsync")
    .mockRejectedValue(new Error("fixture read unavailable"));
  const fetch = jest
    .spyOn(global, "fetch")
    .mockRejectedValue(new Error("must not request without credentials"));
  const v = await render(
    <ThemeProvider>
      <AppProvider>
        <StartupGate fontsReady fontError={null}>
          <SessionProbe />
        </StartupGate>
      </AppProvider>
    </ThemeProvider>,
  );
  expect(v.getByText("App entry")).toBeTruthy();
  expect(v.getByText("NOT_VERIFIED")).toBeTruthy();
  expect(v.getByText("demo")).toBeTruthy();
  expect(fetch).not.toHaveBeenCalled();
});
test("restored session slow network cannot hold app entry; outage remains unverified", async () => {
  let respond!: (r: Response) => void;
  jest.spyOn(SecureStore, "getItemAsync").mockImplementation(async (key) =>
    key === "mobile_gateway"
      ? JSON.stringify({
          origin: "https://fixture.example",
          session: "fixture-session",
        })
      : null,
  );
  const fetch = jest.spyOn(global, "fetch").mockImplementation(
    () =>
      new Promise((r) => {
        respond = r;
      }),
  );
  const v = await render(
    <ThemeProvider>
      <AppProvider>
        <StartupGate fontsReady fontError={null}>
          <SessionProbe />
        </StartupGate>
      </AppProvider>
    </ThemeProvider>,
  );
  expect(v.getByText("App entry")).toBeTruthy();
  expect(v.getByText("NOT_VERIFIED")).toBeTruthy();
  expect(v.queryByLabelText("Uygulama hazırlanıyor")).toBeNull();
  expect(fetch).toHaveBeenCalled();
  expect(
    fetch.mock.calls.every(
      ([, init]) => !init?.method || init.method === "GET",
    ),
  ).toBe(true);
  await act(() =>
    respond({
      ok: false,
      status: 503,
      json: async () => ({ error: { code: "BACKEND_UNAVAILABLE" } }),
    } as Response),
  );
  expect(v.getByText("NOT_VERIFIED")).toBeTruthy();
  await v.unmount();
});
test("startup failure offers a real retry without deleting configuration", async () => {
  const retry = jest.fn();
  const remove = jest.spyOn(SecureStore, "deleteItemAsync");
  const v = await render(<StartupScreen failed retry={retry} />);
  await fireEvent.press(v.getByText("Yeniden dene"));
  expect(retry).toHaveBeenCalledTimes(1);
  expect(remove).not.toHaveBeenCalled();
});

test("restored light theme cannot turn system surface light while fonts still initialize", async () => {
  jest.replaceProperty(Platform, "OS", "android");
  jest.spyOn(SecureStore, "getItemAsync").mockResolvedValue("light");
  const tree = (ready: boolean) => (
    <ThemeProvider>
      <StartupGate fontsReady={ready} fontError={null}>
        <ThemeProbe />
      </StartupGate>
    </ThemeProvider>
  );
  const v = await render(tree(false));
  expect(SystemUI.setBackgroundColorAsync).toHaveBeenLastCalledWith("#111316");
  expect(NavigationBar.setStyle).toHaveBeenLastCalledWith("light");
  await v.rerender(tree(true));
  expect(SystemUI.setBackgroundColorAsync).toHaveBeenLastCalledWith("#F1F3F7");
  expect(NavigationBar.setStyle).toHaveBeenLastCalledWith("dark");
});
