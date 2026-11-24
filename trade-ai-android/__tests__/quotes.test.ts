import { validQuotes, quotesStale, type Quotes } from "../src/domain/quotes";
const now = 1792584000000;
const quote = (): Quotes => ({
  data_mode: "live",
  provider: "binance_public_spot",
  real_execution: false,
  stale: false,
  provider_status: "available",
  fetched_at_ms: now,
  refresh_after_seconds: 30,
  chart_timeframe: "1H",
  items: (["BTCUSDT", "ETHUSDT", "SOLUSDT"] as const).map((symbol) => ({
    symbol,
    price: "100.00",
    change_percent_24h: "-1.5",
    source_time_ms: now,
    chart_status: "available",
    history: [
      { time_ms: now - 3600000, price: "99" },
      { time_ms: now, price: "100" },
    ],
  })),
});
test("real contract quote is fresh only within its observed source window", () => {
  const q = quote();
  expect(validQuotes(q, now)).toBe(true);
  expect(quotesStale(q, now)).toBe(false);
  expect(quotesStale(q, now + 60001)).toBe(true);
  expect(quotesStale({ ...q, stale: true }, now)).toBe(true);
});
test("wrong asset, duplicate record, NaN, future time and mismatched chart rejected", () => {
  const bad = [
    { ...quote(), fetched_at_ms: now + 60000 },
    {
      ...quote(),
      items: [quote().items[0], quote().items[0], quote().items[1]],
    },
    { ...quote(), items: quote().items.map((q) => ({ ...q, price: "NaN" })) },
    {
      ...quote(),
      items: quote().items.map((q) => ({
        ...q,
        chart_status: "unavailable" as const,
      })),
    },
  ];
  for (const q of bad) expect(validQuotes(q, now)).toBe(false);
});
