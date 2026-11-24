import type { components } from "../api/schema";
export type Analysis = components["schemas"]["AnalysisResponse"];
export type Portfolio = components["schemas"]["PortfolioResponse"];
export type Account = "AUTO" | "MANUAL";
export const symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"] as const;
export const timeframes = ["1m", "5m", "15m", "1H", "4H", "1D"] as const;
export type Timeframe = (typeof timeframes)[number];
function positiveDecimal(value: unknown): boolean {
  return (
    typeof value === "string" &&
    /^\d+(?:\.\d+)?$/.test(value) &&
    /[1-9]/.test(value)
  );
}
export function safeDecision(
  a: Analysis,
  now = Date.now(),
): "WAIT" | "bullish" | "bearish" {
  if (
    (a.direction !== "bullish" && a.direction !== "bearish") ||
    a.quality.ok !== true ||
    !positiveDecimal(a.price) ||
    !Number.isSafeInteger(a.price_time_ms) ||
    !a.price_time_ms ||
    a.price_time_ms > now ||
    !Number.isSafeInteger(a.expires_at_ms) ||
    a.expires_at_ms <= now ||
    !a.levels ||
    ![
      a.levels.entry_low,
      a.levels.entry_high,
      a.levels.invalidation,
      a.levels.target_1,
      a.levels.target_2,
    ].every(positiveDecimal) ||
    a.risk.status !== "eligible_for_paper"
  )
    return "WAIT";
  return a.direction;
}
export function gatewayOrigin(value: string): string {
  let u: URL;
  try {
    u = new URL(value.trim());
  } catch {
    throw new Error("Geçerli bir HTTPS gateway adresi girin.");
  }
  if (
    u.protocol !== "https:" ||
    u.username ||
    u.password ||
    u.search ||
    u.hash ||
    u.pathname !== "/" ||
    /^(localhost|127\.|0\.|\[::1\])/.test(u.hostname)
  )
    throw new Error(
      "Gateway için yalnız HTTPS kök adresi kullanın. Yerel döngü adresi kullanılamaz.",
    );
  return u.origin;
}
export function money(value: string | undefined | null): string {
  if (value == null) return "—";
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return "—";
  return (
    match[1] +
    match[2].replace(/\B(?=(\d{3})+(?!\d))/g, ".") +
    "," +
    (match[3] || "").padEnd(2, "0").slice(0, 2)
  );
}
export function emptyPortfolio(id: Account): Portfolio {
  return {
    portfolio_id: id,
    quote_currency: "USDT",
    data_mode: "fixture",
    seed_equity_quote: "10000",
    cash_quote: "10000",
    available_cash_quote: "10000",
    equity_quote: "10000",
    reserved_cash_quote: "0",
    realized_pnl_quote: "0",
    unrealized_pnl_quote: "0",
    realized_loss_today_quote: "0",
    open_positions: 0,
    pending_orders: 0,
    paused: false,
    paper_only: true,
  };
}
export function age(timestamp?: number | null): string {
  if (!timestamp) return "Zaman bilgisi yok";
  return Math.max(0, Math.floor((Date.now() - timestamp) / 60000)) + " dk önce";
}
export function lastScanText(timestamp?: number | null): string {
  return timestamp ? age(timestamp) : "Henüz tarama yapılmadı";
}
