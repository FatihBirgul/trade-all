import type { components } from "../api/schema";
type Opportunity = components["schemas"]["OpportunityRecord"];
export function opportunityPage(
  rows: Opportunity[],
  filter: string,
  account: string,
) {
  const chosen = new Map<string, Opportunity>();
  for (const o of rows.slice(0, 50)) {
    if (o.portfolio_id !== account) continue;
    const prior = chosen.get(o.opportunity_id);
    if (!prior || o.last_observed_ms > prior.last_observed_ms)
      chosen.set(o.opportunity_id, o);
  }
  return [...chosen.values()].filter(
    (o) =>
      filter === "Hepsi" ||
      (filter === "Erken" && o.state === "EARLY") ||
      (filter === "Teyitli" && o.state === "CONFIRMED") ||
      (filter === "Geçersiz / süresi dolmuş" &&
        ["INVALIDATED", "EXPIRED", "UNAVAILABLE"].includes(o.state)),
  );
}
export function opportunityStale(o: Opportunity, now: number) {
  const frame = {
    "5m": 300000,
    "15m": 900000,
    "1H": 3600000,
    "4H": 14400000,
    "1D": 86400000,
  }[o.timeframe];
  return (
    o.stale ||
    !Number.isSafeInteger(now) ||
    !Number.isSafeInteger(o.last_source_ms) ||
    !Number.isSafeInteger(o.expires_at_ms) ||
    now < o.last_source_ms ||
    now >= o.expires_at_ms ||
    now - o.last_source_ms > frame
  );
}
