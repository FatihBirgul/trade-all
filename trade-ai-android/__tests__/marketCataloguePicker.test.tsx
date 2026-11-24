import React from "react";
import { render, fireEvent, waitFor } from "@testing-library/react-native";
import { MarketCataloguePicker } from "../src/MarketCataloguePicker";
import { useApp } from "../src/state";
import { ApiError } from "../src/api/client";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
const now = 1800000000000;
async function setup(disabled = false, outage = false) {
  const api = {
    markets: jest.fn().mockImplementation(() =>
      outage
        ? Promise.reject(new ApiError("NETWORK"))
        : Promise.resolve({
            data_mode: "live",
            items: [
              {
                symbol: "BTCUSDT",
                market: "crypto_spot",
                contract_type: "spot",
                quote_currency: "USDT",
                venue: "fixture",
                provider: "fixture",
                availability: "configured",
                provider_status: "not_probed",
              },
              { symbol: "XAUUSD", market: "gold", availability: "unavailable" },
            ],
          }),
    ),
    analyses: jest.fn().mockResolvedValue([
      {
        symbol: "BTCUSDT",
        risk_portfolio: "AUTO",
        data_mode: "live",
        created_at_ms: now - 1000,
        expires_at_ms: now + 1000,
        direction: "SELL",
      },
      {
        symbol: "BTCUSDT",
        risk_portfolio: "MANUAL",
        data_mode: "live",
        created_at_ms: now - 2000,
        expires_at_ms: now - 1000,
        direction: "WAIT",
      },
    ]),
    activateMarketScanner: jest.fn(),
    updateMarketScanner: jest.fn(),
  };
  (useApp as jest.Mock).mockReturnValue({
    account: "MANUAL",
    connectionKey: "fixture",
    config: { session: "fixture-session" },
    api,
  });
  const toggle = jest.fn();
  const view = await render(
    <MarketCataloguePicker
      now={now}
      favorites={["BTCUSDT"]}
      disabled={disabled}
      onToggle={toggle}
    />,
  );
  return { api, toggle, ...view };
}
test("real catalogue search, unavailable pair and own-account historical label; mount is read-only", async () => {
  const v = await setup();
  await waitFor(() => expect(v.getByText("✓ BTCUSDT")).toBeTruthy());
  expect(v.getByText(/geçmiş\/eski kayıt/)).toBeTruthy();
  expect(v.queryByText(/SELL/)).toBeNull();
  expect(v.api.activateMarketScanner).not.toHaveBeenCalled();
  expect(v.api.updateMarketScanner).not.toHaveBeenCalled();
  await fireEvent.changeText(v.getByLabelText("Parite ara"), "XAU");
  expect(v.queryByText("✓ BTCUSDT")).toBeNull();
  await fireEvent.press(v.getByText("+ XAUUSD"));
  expect(v.toggle).not.toHaveBeenCalled();
  await fireEvent.changeText(v.getByLabelText("Parite ara"), "BTC");
  await fireEvent.press(v.getByText("✓ BTCUSDT"));
  expect(v.toggle).toHaveBeenCalledWith("BTCUSDT");
});
test("missing write permission leaves search usable but prevents favorite edits", async () => {
  const v = await setup(true);
  await waitFor(() => expect(v.getByText("✓ BTCUSDT")).toBeTruthy());
  await fireEvent.press(v.getByText("✓ BTCUSDT"));
  expect(v.toggle).not.toHaveBeenCalled();
  await fireEvent.changeText(v.getByLabelText("Parite ara"), "BTC");
  expect(v.getByText("✓ BTCUSDT")).toBeTruthy();
});
test("catalogue outage only offers removal of existing favorites, never an invented market", async () => {
  const v = await setup(false, true);
  await waitFor(() => expect(v.getByText(/yalnız çıkarma/)).toBeTruthy());
  expect(v.queryByText("+ XAUUSD")).toBeNull();
  await fireEvent.press(v.getByText("✓ BTCUSDT"));
  expect(v.toggle).toHaveBeenCalledWith("BTCUSDT");
});
