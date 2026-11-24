import type { components } from "../api/schema";
import type { Account, Portfolio } from "./safety";
export function decimal(value: unknown, nonnegative = false): value is string {
  return (
    typeof value === "string" &&
    /^-?\d+(?:\.\d+)?$/.test(value) &&
    Number.isFinite(Number(value)) &&
    (!nonnegative || Number(value) >= 0)
  );
}
export function validatePortfolio(
  p: Portfolio,
  account: Account,
  mode = "live",
): Portfolio {
  const signed = [p.equity_quote, p.realized_pnl_quote, p.unrealized_pnl_quote];
  const positive = [
    p.seed_equity_quote,
    p.cash_quote,
    p.reserved_cash_quote,
    p.available_cash_quote,
    p.realized_loss_today_quote,
  ];
  if (
    p.portfolio_id !== account ||
    p.data_mode !== mode ||
    (p.paper_only !== undefined && p.paper_only !== true) ||
    p.quote_currency !== "USDT" ||
    !signed.every((v) => decimal(v)) ||
    !positive.every((v) => decimal(v, true)) ||
    ![p.open_positions, p.pending_orders].every(
      (v) => Number.isSafeInteger(v) && v >= 0,
    ) ||
    typeof p.paused !== "boolean"
  )
    throw new Error("Sanal hesap verisi veya hesap ayrımı doğrulanamadı.");
  return p;
}
export function validateLedgerRows<
  T extends { portfolio_id: string; data_mode: string },
>(rows: T[], account: Account): T[] {
  if (
    rows.length > 20 ||
    rows.some((r) => r.portfolio_id !== account || r.data_mode !== "live")
  )
    throw new Error("Hesap hareketlerinin kaynağı doğrulanamadı.");
  return rows;
}
export function performanceForAccount(
  rows: Record<string, unknown>[],
  account: Account,
) {
  const selected = rows.filter((p) => p.portfolio_id === account);
  if (!selected.length) return null;
  const p = selected[0];
  if (
    selected.length !== 1 ||
    ![p.closed_positions, p.wins, p.losses, p.ambiguous_positions ?? 0].every(
      (v) => typeof v === "number" && Number.isSafeInteger(v) && v >= 0,
    ) ||
    Number(p.wins) + Number(p.losses) > Number(p.closed_positions) ||
    !decimal(p.realized_pnl_quote) ||
    !decimal(p.fees_quote, true) ||
    (p.win_rate !== null &&
      (!decimal(p.win_rate, true) ||
        Number(p.win_rate) > 100 ||
        Number(p.wins) + Number(p.losses) === 0))
  )
    throw new Error("Performans verisi doğrulanamadı.");
  return p;
}
export function pnlWindow(
  rows: components["schemas"]["TransactionResponse"][],
  account: Account,
) {
  validateLedgerRows(rows, account);
  if (
    rows.some(
      (r) =>
        !decimal(r.realized_pnl_quote) ||
        !Number.isSafeInteger(r.time_ms) ||
        r.time_ms <= 0,
    )
  )
    throw new Error("PnL kayıtları doğrulanamadı.");
  const ordered = [
    ...new Map(rows.map((r) => [r.transaction_id, r])).values(),
  ].sort(
    (a, b) =>
      a.time_ms - b.time_ms || a.transaction_id.localeCompare(b.transaction_id),
  );
  let sum = 0n;
  return ordered.map((r) => {
    const match = /^(-?)(\d+)(?:\.(\d{1,8}))?$/.exec(r.realized_pnl_quote);
    if (!match) throw new Error("PnL hassasiyeti doğrulanamadı.");
    const value =
      BigInt(match[2]) * 100000000n + BigInt((match[3] ?? "").padEnd(8, "0"));
    sum += match[1] ? -value : value;
    const absolute = sum < 0n ? -sum : sum;
    const text =
      (sum < 0n ? "-" : "") +
      (absolute / 100000000n).toString() +
      "." +
      (absolute % 100000000n).toString().padStart(8, "0");
    if (!Number.isFinite(Number(text)) || Math.abs(Number(text)) > 1e15)
      throw new Error("PnL grafik gösterim sınırı aşıldı.");
    return { time: r.time_ms, value: text };
  });
}
