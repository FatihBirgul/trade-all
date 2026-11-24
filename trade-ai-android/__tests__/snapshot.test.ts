import { snapshotMatches } from "../src/domain/snapshot";
import example from "../docs/backend/v2_examples/analysis.json";
import type { Analysis } from "../src/domain/safety";
import type { components } from "../src/api/schema";
const a = example as Analysis;
const snapshot: components["schemas"]["ChartResponse"] = {
  analysis_id: a.analysis_id,
  as_of_ms: a.created_at_ms,
  source_record_id: "a".repeat(64),
  symbol: a.symbol,
  timeframe: a.timeframe,
  provider: a.provider,
  venue: a.venue,
  data_mode: a.data_mode,
  snapshot_only: true,
  contract_type: "spot",
  price_kind: "last",
  quote_currency: "USDT",
  source: "fixture_spot",
  candles: [
    {
      open_time_ms: a.created_at_ms - 60000,
      close_time_ms: a.created_at_ms,
      is_final: true,
      open: "1",
      high: "2",
      low: "1",
      close: "2",
      volume: "1",
    },
  ],
};
test("yalnız aynı analiz, zaman dilimi ve kayıt kaynağının kapalı mumları gösterilir", () => {
  expect(snapshotMatches(a, snapshot)).toBe(true);
  expect(snapshotMatches(a, { ...snapshot, analysis_id: "b".repeat(64) })).toBe(
    false,
  );
  expect(
    snapshotMatches(a, { ...snapshot, as_of_ms: a.created_at_ms + 1 }),
  ).toBe(false);
  expect(snapshotMatches(a, { ...snapshot, provider: "other" })).toBe(false);
  expect(
    snapshotMatches(a, {
      ...snapshot,
      candles: [{ ...snapshot.candles[0], close_time_ms: a.created_at_ms + 1 }],
    }),
  ).toBe(false);
});
