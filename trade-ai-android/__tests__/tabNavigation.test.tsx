import React from "react";
import { render } from "@testing-library/react-native";
import TabsLayout from "../app/(tabs)/_layout";
import { ThemeProvider } from "../src/theme";
import { useApp } from "../src/state";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
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
test("Basic/Pro keeps a visible Home back destination instead of hidden scanner history", async () => {
  jest
    .mocked(useApp)
    .mockReturnValue({ uiMode: "basic" } as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <TabsLayout />
    </ThemeProvider>,
  );
  expect(ui.getByText("firstRoute")).toBeTruthy();
  expect(ui.getByText("scanner:hidden")).toBeTruthy();
  expect(ui.getByText("index:visible")).toBeTruthy();
  jest
    .mocked(useApp)
    .mockReturnValue({ uiMode: "pro" } as ReturnType<typeof useApp>);
  await ui.rerender(
    <ThemeProvider>
      <TabsLayout />
    </ThemeProvider>,
  );
  expect(ui.getByText("scanner:visible")).toBeTruthy();
  expect(ui.getByText("firstRoute")).toBeTruthy();
});
