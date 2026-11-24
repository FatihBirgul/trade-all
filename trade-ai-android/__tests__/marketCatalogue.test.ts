import { catalogueRows, findMarkets } from "../src/domain/marketCatalogue";
import {
  opportunityPage,
  opportunityStale,
} from "../src/domain/opportunityView";
import type { components } from "../src/api/schema";
const row = (symbol = "BTCUSDT") => ({
  symbol,
  market: "crypto_spot",
  contract_type: "spot",
  provider: "configured_provider",
  venue: "test",
  quote_currency: "USDT",
  availability: "configured",
  provider_status: "not_probed",
});
test("catalogue deduplicates supported spot and keeps unavailable FX/XAU visible", () => {
  const rows = catalogueRows({
    data_mode: "live",
    items: [
      row(),
      row(),
      row("ETHUSDT"),
      { symbol: "XAUUSD", market: "gold_spot", availability: "unavailable" },
    ],
  });
  expect(rows).toHaveLength(3);
  expect(rows.filter((r) => r.selectable)).toHaveLength(2);
  expect(findMarkets(rows, "btc/usdt", "Hepsi", [])).toHaveLength(1);
  expect(findMarkets(rows, "", "Favoriler", ["ETHUSDT"])[0].symbol).toBe(
    "ETHUSDT",
  );
  expect(findMarkets(rows, "", "Kullanılamayan", [])[0].symbol).toBe("XAUUSD");
});
test("unknown pair, perpetual or delisted entry cannot become a favorite", () => {
  for (const item of [
    row("DOGEUSDT"),
    { ...row(), contract_type: "perpetual" },
    { ...row(), availability: "unavailable" },
  ])
    expect(
      catalogueRows({ data_mode: "live", items: [item] })[0].selectable,
    ).toBe(false);
});
test("fixture source, conflicting identity, invalid records and oversized catalogues reject", () => {
  for (const payload of [
    { data_mode: "fixture", items: [row()] },
    { data_mode: "live", items: [row(), { ...row(), venue: "other" }] },
    { data_mode: "live", items: [{ symbol: 1 }] },
    { data_mode: "live", items: Array(201).fill(row()) },
  ])
    expect(() => catalogueRows(payload)).toThrow();
});
type O = components["schemas"]["OpportunityRecord"];
const opportunity = {
  opportunity_id: "a".repeat(64),
  portfolio_id: "MANUAL",
  state: "EARLY",
  last_observed_ms: 100,
  last_source_ms: 1800000000000,
  expires_at_ms: 1800000600000,
  timeframe: "5m",
  stale: false,
} as O;
test("newest lifecycle observation wins before filtering and account denial", () => {
  const confirmed = {
    ...opportunity,
    state: "CONFIRMED",
    last_observed_ms: 200,
  } as O;
  const other = {
    ...confirmed,
    opportunity_id: "b".repeat(64),
    portfolio_id: "AUTO",
  } as O;
  expect(
    opportunityPage([confirmed, opportunity, other], "Hepsi", "MANUAL"),
  ).toEqual([confirmed]);
  expect(opportunityPage([confirmed, opportunity], "Erken", "MANUAL")).toEqual(
    [],
  );
  expect(
    opportunityPage(
      [{ ...confirmed, state: "INVALIDATED" }],
      "Geçersiz / süresi dolmuş",
      "MANUAL",
    ),
  ).toHaveLength(1);
});
test("cached record ages without fabricating a new lifecycle event", () => {
  expect(opportunityStale(opportunity, 1800000300001)).toBe(true);
  expect(opportunityStale(opportunity, 1800000000000)).toBe(false);
  expect(opportunityStale(opportunity, 1799999999999)).toBe(true);
  expect(opportunity.state).toBe("EARLY");
});
