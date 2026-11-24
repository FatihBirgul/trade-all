import { safeDecision, type Analysis } from "./safety";
export type HistoryFilters = {
  symbol: string;
  timeframe: string;
  account: string;
  decision: string;
  order: string;
};
export function recordedDecision(a: Analysis) {
  return safeDecision(a, a.created_at_ms);
}
export function filterHistory(rows: Analysis[], f: HistoryFilters): Analysis[] {
  return rows
    .filter(
      (a) =>
        (f.symbol === "Tümü" || a.symbol === f.symbol) &&
        (f.timeframe === "Tümü" || a.timeframe === f.timeframe) &&
        (f.account === "Tümü" || a.risk_portfolio === f.account) &&
        (f.decision === "Tümü" ||
          recordedDecision(a) ===
            (
              {
                BEKLE: "WAIT",
                Yükseliş: "bullish",
                Düşüş: "bearish",
              } as Record<string, string>
            )[f.decision]),
    )
    .sort(
      (a, b) =>
        (f.order === "Yeni → Eski"
          ? b.created_at_ms - a.created_at_ms
          : a.created_at_ms - b.created_at_ms) ||
        a.analysis_id.localeCompare(b.analysis_id),
    );
}
