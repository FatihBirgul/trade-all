import {
  validatePortfolio,
  validateLedgerRows,
  pnlWindow,
  performanceForAccount,
} from "../src/domain/portfolio";
import { emptyPortfolio } from "../src/domain/safety";
import type { components } from "../src/api/schema";
test("portfolio numeric validation rejects NaN, negative cash and wrong account", () => {
  const p = { ...emptyPortfolio("AUTO"), data_mode: "live" };
  expect(validatePortfolio(p, "AUTO")).toBe(p);
  expect(() => validatePortfolio(p, "MANUAL")).toThrow();
  for (const value of ["NaN", "Infinity", "-Infinity", "9".repeat(400)]) {
    expect(() =>
      validatePortfolio({ ...p, equity_quote: value }, "AUTO"),
    ).toThrow();
  }
  expect(() =>
    validatePortfolio({ ...p, available_cash_quote: "-1" }, "AUTO"),
  ).toThrow();
  expect(() =>
    validateLedgerRows(
      [{ portfolio_id: "AUTO", data_mode: "fixture" }],
      "AUTO",
    ),
  ).toThrow();
});
test("PnL window accumulates real signed decimals exactly, sorts and never crosses accounts", () => {
  type Transaction = components["schemas"]["TransactionResponse"];
  const rows = [
    {
      transaction_id: "a",
      portfolio_id: "AUTO",
      data_mode: "live",
      time_ms: 1,
      realized_pnl_quote: "0.1",
    },
    {
      transaction_id: "b",
      portfolio_id: "AUTO",
      data_mode: "live",
      time_ms: 2,
      realized_pnl_quote: "0.2",
    },
  ] as Transaction[];
  expect(pnlWindow([...rows].reverse(), "AUTO").map((p) => p.value)).toEqual([
    "0.10000000",
    "0.30000000",
  ]);
  expect(() => pnlWindow(rows, "MANUAL")).toThrow();
  expect(pnlWindow([], "AUTO")).toEqual([]);
  expect(rows[0].realized_pnl_quote).toBe("0.1");
});
test("performance never invents a rate with no decided outcomes", () => {
  const row = {
    portfolio_id: "AUTO",
    closed_positions: 0,
    wins: 0,
    losses: 0,
    ambiguous_positions: 0,
    realized_pnl_quote: "0",
    fees_quote: "0",
    win_rate: null,
  };
  expect(performanceForAccount([row], "AUTO")?.win_rate).toBeNull();
  expect(() =>
    performanceForAccount([{ ...row, win_rate: "100" }], "AUTO"),
  ).toThrow();
  expect(performanceForAccount([row], "MANUAL")).toBeNull();
});
