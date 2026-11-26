import statusJson from "../../fixtures/design_sample/status.json";
import positionsJson from "../../fixtures/design_sample/positions.json";
import summaryJson from "../../fixtures/design_sample/summary.json";

export type Position = (typeof positionsJson.positions)[number];
export const status = statusJson;
export const positions = positionsJson.positions;
export const summary = summaryJson;

const tr = (digits: number) =>
  new Intl.NumberFormat("tr-TR", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const money = (value: number, currency = status.currency) => tr(2).format(value) + " " + currency;
export const signed = (value: number, currency = status.currency) =>
  (value > 0 ? "+" : value < 0 ? "−" : "") + tr(2).format(Math.abs(value)) + " " + currency;
export const signedR = (value: number) => (value > 0 ? "+" : value < 0 ? "−" : "") + tr(2).format(Math.abs(value)) + "R";
export const price = (value: number | null, symbol: string) =>
  value === null ? "—" : tr(symbol.includes("JPY") || symbol.startsWith("XAU") ? 2 : 5).format(value);
export const lots = (value: number) => tr(2).format(value) + " lot";
export const minutesAgo = (at: number) => Math.max(0, Math.round((status.server_time - at) / 60)) + " dk önce";
export const STRATEGY: Record<string, string> = {
  fx_trend_momentum_v6: "Trend",
  fx_failed_breakout_v6: "Sahte kırılım",
  fx_range_reversion_v6: "Bant dönüşü",
  fx_confirmed_breakout_v6: "Kırılım",
};
export const openPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0);
// Kademeli stop: 0 = ilk stop, 1 = başa baş, 2 = yarı kâr alındı + iz süren
export const stage = (p: Position) => (p.partial_done ? 2 : p.be_done ? 1 : 0);
export const STAGES = ["İlk stop", "Başa baş", "İz süren"];
