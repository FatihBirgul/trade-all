import React from "react";
import { render, waitFor } from "@testing-library/react-native";
import { useFonts } from "expo-font";
import { releaseNativeSplash } from "../src/startup";
import Layout from "../app/_layout";
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  initialWindowMetrics: {
    frame: { x: 0, y: 0, width: 390, height: 844 },
    insets: { top: 24, bottom: 0, left: 0, right: 0 },
  },
}));
jest.mock("expo-font", () => ({ useFonts: jest.fn() }));
jest.mock("expo-system-ui", () => ({
  setBackgroundColorAsync: jest.fn().mockResolvedValue(undefined),
}));
jest.mock("../src/state", () => ({
  AppProvider: ({ children }: React.PropsWithChildren) => children,
}));
jest.mock("expo-router", () => {
  const Text = jest.requireActual("react-native").Text;
  const Stack = ({ children }: React.PropsWithChildren) => (
    <>
      <Text>Navigasyon hazır</Text>
      {children}
    </>
  );
  Stack.Screen = function MockScreen() {
    return null;
  };
  return { Stack };
});
test("navigation waits for the explicit Ionicons asset before showing icon-dependent screens", async () => {
  jest.mocked(useFonts).mockReturnValue([false, null]);
  const ui = await render(<Layout />);
  expect(ui.getByLabelText("Uygulama hazırlanıyor")).toBeTruthy();
  expect(useFonts).toHaveBeenCalledWith(
    expect.objectContaining({ ionicons: expect.anything() }),
  );
  await ui.unmount();
});
test("font failure is visible instead of an endless blank loading screen", async () => {
  jest.mocked(useFonts).mockReturnValue([false, new Error("asset failure")]);
  const ui = await render(<Layout />);
  expect(
    ui.getByText("İkonlar yüklenemedi · metinli gezinme kullanılabilir."),
  ).toBeTruthy();
  await waitFor(() => expect(ui.getByText("Navigasyon hazır")).toBeTruthy());
  await ui.unmount();
});

afterAll(() => releaseNativeSplash());
