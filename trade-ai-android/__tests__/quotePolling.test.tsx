import React from "react";
import { Text, Pressable, AppState } from "react-native";
import { render, fireEvent, waitFor, act } from "@testing-library/react-native";
import { useMarketQuotes } from "../src/useMarketQuotes";
let mockApp: any;
jest.mock("../src/state", () => ({ useApp: () => mockApp }));
jest.mock("expo-router", () => ({
  useFocusEffect(callback: () => void | (() => void)) {
    const React = jest.requireActual<typeof import("react")>("react");
    React.useEffect(() => callback(), [callback]);
  },
}));
function Probe() {
  const q = useMarketQuotes();
  return (
    <>
      <Text>{q.data?.items[0].price ?? "no-price"}</Text>
      <Text>{q.stale ? "stale" : "current"}</Text>
      <Pressable onPress={q.reload}>
        <Text>Reload</Text>
      </Pressable>
    </>
  );
}
const data = () => ({
  data_mode: "live",
  provider: "binance_public_spot",
  real_execution: false,
  stale: false,
  provider_status: "available",
  fetched_at_ms: Date.now(),
  refresh_after_seconds: 30,
  chart_timeframe: "1H",
  items: ["BTCUSDT", "ETHUSDT", "SOLUSDT"].map((symbol) => ({
    symbol,
    price: "100.00",
    change_percent_24h: "1.5",
    source_time_ms: Date.now(),
    chart_status: "unavailable",
    history: [],
  })),
});
test("failed refresh retains price explicitly stale; session/demo change clears it", async () => {
  const quotes = jest.fn().mockImplementation(async () => data());
  mockApp = {
    mode: "live",
    gatewayVerified: true,
    sessionInfo: { capabilities: ["market-quotes-v1"] },
    connectionKey: 1,
    config: { session: "s" },
    api: { quotes },
  };
  const ui = await render(<Probe />);
  await waitFor(() => expect(ui.getByText("100.00")).toBeTruthy());
  quotes.mockRejectedValue(new Error("Bağlantı kesildi."));
  await fireEvent.press(ui.getByText("Reload"));
  await waitFor(() => expect(ui.getByText("stale")).toBeTruthy());
  expect(ui.getByText("100.00")).toBeTruthy();
  mockApp = { ...mockApp, mode: "demo" };
  await ui.rerender(<Probe />);
  expect(ui.getByText("no-price")).toBeTruthy();
  await ui.unmount();
});

test("background blocks polling/reload; foreground rechecks without overlapping requests", async () => {
  let onChange: (state: "background" | "active") => void = () => {};
  const spy = jest
    .spyOn(AppState, "addEventListener")
    .mockImplementation((_event, listener) => {
      onChange = listener as typeof onChange;
      return { remove: jest.fn() };
    });
  const quotes = jest.fn(async () => data());
  mockApp = {
    mode: "live",
    gatewayVerified: true,
    sessionInfo: { capabilities: ["market-quotes-v1"] },
    connectionKey: 1,
    config: { session: "lifecycle" },
    api: { quotes },
  };
  try {
    const ui = await render(<Probe />);
    await waitFor(() => expect(ui.getByText("100.00")).toBeTruthy());
    await act(async () => onChange("background"));
    await fireEvent.press(ui.getByText("Reload"));
    expect(quotes).toHaveBeenCalledTimes(1);
    await act(async () => onChange("active"));
    await waitFor(() => expect(quotes).toHaveBeenCalledTimes(2));
    await ui.unmount();
  } finally {
    spy.mockRestore();
  }
});
