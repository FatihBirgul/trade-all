import React from "react";
import { Text, Pressable } from "react-native";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import { AppProvider, useApp } from "../src/state";
import { demoAnalysis } from "../src/demo";
const mockSaved = new Map<string, string>();
jest.mock("expo-secure-store", () => ({
  getItemAsync: jest.fn(async (key: string) => mockSaved.get(key) ?? null),
  setItemAsync: jest.fn(async (key: string, value: string) => {
    mockSaved.set(key, value);
  }),
  deleteItemAsync: jest.fn(async () => {}),
}));
function Probe() {
  const app = useApp();
  return (
    <>
      <Text>
        {[
          app.uiMode,
          app.mode,
          app.account,
          app.history[0]?.analysis_id ?? "empty",
        ].join("|")}
      </Text>
      <Pressable onPress={() => app.setUiMode("pro")}>
        <Text>Pro aç</Text>
      </Pressable>
      <Pressable onPress={() => app.setUiMode("basic")}>
        <Text>Basit aç</Text>
      </Pressable>
      <Pressable
        onPress={() => {
          app.setAccount("MANUAL");
          app.addAnalysis(
            demoAnalysis("BTCUSDT", "1H", "MANUAL", "immutable-record"),
          );
        }}
      >
        <Text>Kayıt ekle</Text>
      </Pressable>
      <Pressable onPress={() => app.setMode("live")}>
        <Text>Canlı aç</Text>
      </Pressable>
    </>
  );
}
beforeEach(() => {
  mockSaved.clear();
  jest.clearAllMocks();
});
test("basic default, pro persists, mode flip preserves immutable record/account and does not unlock live", async () => {
  const ui = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  expect(ui.getByText("basic|demo|AUTO|empty")).toBeTruthy();
  await fireEvent.press(ui.getByText("Kayıt ekle"));
  await fireEvent.press(ui.getByText("Pro aç"));
  await waitFor(() =>
    expect(ui.getByText("pro|demo|MANUAL|immutable-record")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Canlı aç"));
  expect(ui.getByText("pro|demo|MANUAL|immutable-record")).toBeTruthy();
  expect(SecureStore.setItemAsync).toHaveBeenCalledWith("trade_ui_mode", "pro");
  await ui.unmount();
  const reopened = await render(
    <AppProvider>
      <Probe />
    </AppProvider>,
  );
  await waitFor(() =>
    expect(reopened.getByText("pro|demo|AUTO|empty")).toBeTruthy(),
  );
  await fireEvent.press(reopened.getByText("Basit aç"));
  await waitFor(() =>
    expect(reopened.getByText("basic|demo|AUTO|empty")).toBeTruthy(),
  );
});
