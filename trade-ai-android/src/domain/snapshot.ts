import type { components } from "../api/schema";
import type { Analysis } from "./safety";
export function snapshotMatches(
  a: Analysis,
  c: components["schemas"]["ChartResponse"],
): boolean {
  if (
    c.analysis_id !== a.analysis_id ||
    c.as_of_ms !== a.created_at_ms ||
    c.timeframe !== a.timeframe ||
    c.provider !== a.provider ||
    c.symbol !== a.symbol ||
    c.venue !== a.venue ||
    c.data_mode !== a.data_mode ||
    c.snapshot_only !== true ||
    !/^[a-f0-9]{64}$/.test(c.source_record_id)
  )
    return false;
  return (
    c.candles.length > 0 &&
    c.candles.every(
      (bar, i, bars) =>
        bar.is_final === true &&
        Number.isSafeInteger(bar.open_time_ms) &&
        Number.isSafeInteger(bar.close_time_ms) &&
        bar.open_time_ms < bar.close_time_ms &&
        bar.close_time_ms <= c.as_of_ms &&
        (i === 0 || bar.open_time_ms >= bars[i - 1].close_time_ms),
    )
  );
}
