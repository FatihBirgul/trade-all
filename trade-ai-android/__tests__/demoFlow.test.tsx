import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";
import { AppProvider, useApp } from "../src/state";
import { ThemeProvider } from "../src/theme";
import Home from "../app/(tabs)/index";
import Analysis from "../app/(tabs)/analysis";
import Result from "../app/result";
import Detail from "../app/detail";
import History from "../app/history";
import Settings from "../app/(tabs)/settings";
import Scanner from "../app/(tabs)/scanner";
const mockPush = jest.fn();
let mockParams: Record<string, string> = {};
jest.mock("expo-router", () => ({
  useFocusEffect: jest.fn(),
  router: { push: (...args: unknown[]) => mockPush(...args) },
  useLocalSearchParams: () => mockParams,
}));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 24, left: 0, right: 0 }),
}));
jest.mock("expo-crypto", () => ({ randomUUID: () => "demo-test-uuid" }));
function ProTestSwitch() {
  const app = useApp();
  return (
    <Pressable onPress={() => app.setUiMode("pro")}>
      <Text>Pro test görünümü</Text>
    </Pressable>
  );
}
function Root({ children }: React.PropsWithChildren) {
  return (
    <ThemeProvider>
      <AppProvider>
        <ProTestSwitch />
        {children}
      </AppProvider>
    </ThemeProvider>
  );
}
beforeEach(() => {
  mockPush.mockClear();
  mockParams = {};
});
test("ana sayfa seçimi → MANUAL analiz → güvenli WAIT detayı → geçmiş", async () => {
  const ui = await render(
    <Root>
      <Home />
    </Root>,
  );
  await fireEvent.press(ui.getByText("Pro test görünümü"));
  await fireEvent.press(ui.getByText("ETHUSDT"));
  await fireEvent.press(ui.getByText("Analiz Et"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/analysis",
    params: { symbol: "ETHUSDT", requestId: "demo-test-uuid" },
  });
  mockParams = mockPush.mock.lastCall![0].params;
  await ui.rerender(
    <Root>
      <Analysis />
    </Root>,
  );
  await fireEvent.press(ui.getByText("MANUAL"));
  await fireEvent.press(ui.getByText("Analizi başlat"));
  expect(mockPush).toHaveBeenLastCalledWith({
    pathname: "/result",
    params: { id: "demo-test-uuid" },
  });
  mockParams = mockPush.mock.lastCall![0].params;
  await ui.rerender(
    <Root>
      <Result />
    </Root>,
  );
  await waitFor(() => expect(ui.getByText("BEKLE")).toBeTruthy());
  await fireEvent.press(ui.getByText("Detaylı analizi aç"));
  expect(mockPush.mock.lastCall![0].pathname).toBe("/detail");
  await ui.rerender(
    <Root>
      <Detail />
    </Root>,
  );
  await waitFor(() => expect(ui.getByText("ETHUSDT · 1H")).toBeTruthy());
  expect(ui.getByText("MANUAL")).toBeTruthy();
  expect(
    ui.getByText("Bekle · İşlem seviyeleri ve emir oluşturma kapalı."),
  ).toBeTruthy();
  expect(ui.queryByText("Koşullu seviyeler")).toBeNull();
  await ui.rerender(
    <Root>
      <History />
    </Root>,
  );
  await waitFor(() =>
    expect(ui.getByText("ETHUSDT · 1H · BEKLE")).toBeTruthy(),
  );
});
test("ayarlar canlı kilidini korur ve geçersiz adresi Türkçe açıklar", async () => {
  const ui = await render(
    <Root>
      <Settings />
    </Root>,
  );
  await fireEvent.press(ui.getByText("CANLI"));
  expect(ui.getByText("● DEMO · ÖRNEK VERİ")).toBeTruthy();
  await fireEvent.press(ui.getByText("Bağlantıyı test et ve kaydet"));
  await waitFor(() =>
    expect(
      ui.getByText("Geçerli bir HTTPS gateway adresi girin."),
    ).toBeTruthy(),
  );
  expect(ui.getByText("Doğrulanmadı · CANLI kilitli")).toBeTruthy();
});
test("demo tarayıcı duraklatılmış başlar, yalnız yerel kontrol yapar", async () => {
  const ui = await render(
    <Root>
      <Scanner />
    </Root>,
  );
  await fireEvent.press(ui.getByText("Pro test görünümü"));
  await waitFor(() =>
    expect(ui.getByText("Yerel kontrol yapılmadı")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Yerel kontrolü dene"));
  expect(
    ui.queryByText(
      "Demo kontrolü tamamlandı. Piyasa verisi veya emir üretilmedi.",
    ),
  ).toBeNull();
  await fireEvent.press(ui.getByText("DEMO örneğini sürdür"));
  await waitFor(() =>
    expect(ui.getByText("DEMO örneğini duraklat")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Yerel kontrolü dene"));
  await waitFor(() =>
    expect(
      ui.getByText(
        "Demo kontrolü tamamlandı. Piyasa verisi veya emir üretilmedi.",
      ),
    ).toBeTruthy(),
  );
});
