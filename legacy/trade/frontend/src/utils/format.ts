// Small formatting helpers shared across screens.

export function fmtPrice(v?: number | null): string {
  if (v === undefined || v === null || isNaN(v)) return "--";
  const abs = Math.abs(v);
  let digits = 2;
  if (abs < 1) digits = 5;
  else if (abs < 100) digits = 3;
  return v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtPct(v?: number | null): string {
  if (v === undefined || v === null || isNaN(v)) return "--";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(2)}%`;
}

export function fmtCompact(v?: number | null): string {
  if (v === undefined || v === null || isNaN(v)) return "--";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + "B";
  if (v >= 1e6) return (v / 1e6).toFixed(2) + "M";
  if (v >= 1e3) return (v / 1e3).toFixed(2) + "K";
  return v.toFixed(2);
}

export function timeAgo(iso?: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const d = Math.floor(hr / 24);
  return `${d}d ago`;
}
