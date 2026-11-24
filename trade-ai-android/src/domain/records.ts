import type { Analysis } from "./safety";
export function uniqueRecords<T>(rows: T[], id: (row: T) => string): T[] {
  return [...new Map(rows.map((row) => [id(row), row])).values()];
}
export function comparable(a: Analysis, b: Analysis): boolean {
  return (
    a.analysis_id !== b.analysis_id &&
    a.symbol === b.symbol &&
    a.timeframe === b.timeframe &&
    a.risk_portfolio === b.risk_portfolio &&
    a.data_mode === b.data_mode &&
    a.market === b.market &&
    a.provider === b.provider &&
    a.venue === b.venue &&
    a.contract_type === b.contract_type &&
    a.price_kind === b.price_kind
  );
}
export function linkedAnalysis(
  details: Record<string, unknown>,
): string | null {
  return typeof details.analysis_id === "string" &&
    /^[a-f0-9]{64}$/.test(details.analysis_id)
    ? details.analysis_id
    : null;
}
