import React from "react";
import { render } from "@testing-library/react-native";
import TabsLayout from "../app/(tabs)/_layout";
import { ThemeProvider } from "../src/theme";
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 24, left: 0, right: 0 }),
}));
jest.mock("expo-router", () => {
  const React = jest.requireActual<typeof import("react")>("react");
  const { Text } =
    jest.requireActual<typeof import("react-native")>("react-native");
  function Tabs({
    children,
    backBehavior,
  }: React.PropsWithChildren<{
    backBehavior: string;
  }>) {
    return (
      <>
        <Text>{backBehavior}</Text>
        {children}
      </>
    );
  }
  Tabs.Screen = function Screen({
    name,
    options,
  }: {
    name: string;
    options: { href?: null };
  }) {
    return (
      <Text>{name + (options.href === null ? ":hidden" : ":visible")}</Text>
    );
  };
  return { Tabs };
});
test("tabs show bot screens and hide legacy ones", async () => {
  const ui = await render(
    <ThemeProvider>
      <TabsLayout />
    </ThemeProvider>,
  );
  expect(ui.getByText("firstRoute")).toBeTruthy();
  for (const name of ["index", "positions", "reports", "events", "settings-bot"])
    expect(ui.getByText(name + ":visible")).toBeTruthy();
  for (const name of ["connection", "legacy", "analysis", "portfolios", "scanner", "settings"])
    expect(ui.getByText(name + ":hidden")).toBeTruthy();
});
