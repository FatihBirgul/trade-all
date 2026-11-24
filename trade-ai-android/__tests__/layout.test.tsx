import React from "react";
import { StyleSheet, useWindowDimensions } from "react-native";
import { render } from "@testing-library/react-native";
import { ThemeProvider } from "../src/theme";
import { Page, Row } from "../src/ui";

jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 32, bottom: 24, left: 0, right: 0 }),
}));
jest.mock("react-native/Libraries/Utilities/useWindowDimensions", () => ({
  __esModule: true,
  default: jest.fn(),
}));
const dimensions = jest.mocked(useWindowDimensions);
beforeEach(() =>
  dimensions.mockReturnValue({
    width: 320,
    height: 640,
    scale: 2,
    fontScale: 1.5,
  }),
);

test("sekme içeriği durum çubuğunu aşmaz; başlıklı ekran üst boşluğu iki kez eklemez", async () => {
  const ui = await render(
    <ThemeProvider>
      <Page>
        <Row name="Bakiye" value="10.000,00 USDT" />
      </Page>
    </ThemeProvider>,
  );
  const style = () =>
    StyleSheet.flatten(
      ui.getByTestId("page-scroll").props.contentContainerStyle,
    );
  expect(style().paddingTop).toBe(8);
  expect(ui.getByTestId("page-safe-frame").props.edges).toMatchObject({ top: "additive", bottom: "off" });
  expect(style().paddingBottom).toBe(16);
  await ui.rerender(
    <ThemeProvider>
      <Page headerShown>
        <Row name="Bakiye" value="10.000,00 USDT" />
      </Page>
    </ThemeProvider>,
  );
  expect(style().paddingTop).toBe(8);
  expect(ui.getByTestId("page-safe-frame").props.edges).toMatchObject({ top: "off", bottom: "additive" });
  expect(style().paddingBottom).toBe(16);
});

test("dar ekran ve büyük yazıda uzun hesap satırları alt alta yerleşir", async () => {
  const ui = await render(
    <ThemeProvider>
      <Row name="Kullanılabilir bakiye" value="123.456.789,00 USDT" />
    </ThemeProvider>,
  );
  expect(
    StyleSheet.flatten(ui.getByTestId("row-Kullanılabilir bakiye").props.style)
      .flexDirection,
  ).toBe("column");
  dimensions.mockReturnValue({
    width: 420,
    height: 800,
    scale: 2,
    fontScale: 1,
  });
  await ui.rerender(
    <ThemeProvider>
      <Row name="Kullanılabilir bakiye" value="123.456.789,00 USDT" />
    </ThemeProvider>,
  );
  expect(
    StyleSheet.flatten(ui.getByTestId("row-Kullanılabilir bakiye").props.style)
      .flexDirection,
  ).toBe("row");
});
