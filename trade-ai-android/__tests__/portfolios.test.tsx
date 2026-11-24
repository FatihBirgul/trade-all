import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import Portfolios from "../app/(tabs)/portfolios";
import { useApp } from "../src/state";
import { emptyPortfolio } from "../src/domain/safety";
import { ThemeProvider } from "../src/theme";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
jest.mock("react-native-safe-area-context", () => ({
  ...jest.requireActual("react-native-safe-area-context"),
  useSafeAreaInsets: () => ({ top: 24, bottom: 24, left: 0, right: 0 }),
}));
test("kapanan pozisyon gerçekleşen PnL gösterir ve filtre sayfalamayı kesmez", async () => {
  const positions = jest
    .fn()
    .mockImplementation(async (_account, _open, offset) =>
      offset
        ? []
        : Array.from({ length: 20 }, (_, i) => ({
            position_id: String(i),
            portfolio_id: "MANUAL",
            data_mode: "live",
            quantity: i === 0 ? "0" : "1",
            symbol: "BTCUSDT",
            status: i === 0 ? "closed" : "open",
            realized_pnl_quote: "12.34",
            unrealized_pnl_quote: "999",
            mark_time_ms: 1,
          })),
    );
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    account: "MANUAL",
    config: { origin: "https://gateway.example.com", session: "test" },
    api: {
      portfolios: async () => [
        { ...emptyPortfolio("MANUAL"), data_mode: "live" },
      ],
      positions,
    },
  } as unknown as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <Portfolios />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("TOPLAM SANAL VARLIK · MANUAL")).toBeTruthy(),
  );
  await fireEvent.press(ui.getByText("Kapanan pozisyonlar"));
  await waitFor(() => expect(ui.getByText(/12,34 USDT/)).toBeTruthy());
  expect(ui.queryByText(/999,00 USDT/)).toBeNull();
  await fireEvent.press(ui.getByText("Sonraki sayfa"));
  await waitFor(() =>
    expect(positions).toHaveBeenLastCalledWith("MANUAL", false, 20),
  );
  await waitFor(() =>
    expect(ui.getByText(/Bu sayfada kayıt yok/)).toBeTruthy(),
  );
});

test("ambiguous positions with open quantity remain visible as unresolved holdings", async () => {
  jest
    .mocked(useApp)
    .mockReturnValue({
      mode: "live",
      uiMode: "pro",
      account: "AUTO",
      config: { origin: "https://qa.example.test", session: "test" },
      api: {
        portfolios: async () => [
          { ...emptyPortfolio("AUTO"), data_mode: "live" },
        ],
        positions: async () => [
          {
            position_id: "ambiguous",
            portfolio_id: "AUTO",
            data_mode: "live",
            quantity: "1",
            symbol: "BTCUSDT",
            status: "ambiguous",
            realized_pnl_quote: "0",
            unrealized_pnl_quote: "1.25",
            mark_time_ms: 1,
          },
        ],
      },
    } as unknown as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <Portfolios />
    </ThemeProvider>,
  );
  await waitFor(() =>
    expect(ui.getByText("BTCUSDT · Belirsiz · açık miktar")).toBeTruthy(),
  );
  expect(ui.getByText(/1,25 USDT/)).toBeTruthy();
});
