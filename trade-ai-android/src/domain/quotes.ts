import type { components } from "../api/schema";
import { symbols } from "./safety";
export type Quotes = components["schemas"]["QuotesResponse"];
const decimal = (v: unknown, positive = false) =>
  typeof v === "string" &&
  /^-?[0-9]+(?:\.[0-9]+)?$/.test(v) &&
  Number.isFinite(Number(v)) &&
  (!positive || Number(v) > 0);
export function validQuotes(data: Quotes, now: number): boolean {
  return (
    data.real_execution === false &&
    data.data_mode === "live" &&
    data.items.length === 3 &&
    new Set(data.items.map((q) => q.symbol)).size === 3 &&
    Number.isSafeInteger(data.fetched_at_ms) &&
    data.fetched_at_ms > 0 &&
    data.fetched_at_ms <= now + 5000 &&
    data.items.every(
      (q) =>
        symbols.includes(q.symbol) &&
        decimal(q.price, true) &&
        decimal(q.change_percent_24h) &&
        q.source_time_ms > 0 &&
        q.source_time_ms <= data.fetched_at_ms + 5000 &&
        q.history.length <= 24 &&
        (q.chart_status === "available"
          ? q.history.length >= 2
          : q.history.length === 0) &&
        q.history.every(
          (p, i, all) =>
            decimal(p.price, true) &&
            Number.isSafeInteger(p.time_ms) &&
            p.time_ms <= data.fetched_at_ms &&
            (!i || p.time_ms > all[i - 1].time_ms),
        ),
    )
  );
}
export function quotesStale(data: Quotes, now: number) {
  return (
    data.stale ||
    now - data.fetched_at_ms > 60000 ||
    data.items.some((q) => now - q.source_time_ms > 60000)
  );
}
