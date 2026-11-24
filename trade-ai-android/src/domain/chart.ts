import type { components } from "../api/schema";
export type Snapshot = components["schemas"]["ChartResponse"];
export type Bar = {
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  time: number;
};
export type Window = { start: number; count: number };
export const MAX_CANDLES = 4096;
export const MAX_VISIBLE = 96;
// Refuse oversized payloads before mapping: no silent truncation of an immutable record.
export function chartBars(snapshot: Snapshot): Bar[] {
  if (
    !snapshot.snapshot_only ||
    !snapshot.candles.length ||
    snapshot.candles.length > MAX_CANDLES
  )
    return [];
  const bars: Bar[] = [];
  for (const c of snapshot.candles) {
    const [open, high, low, close] = [c.open, c.high, c.low, c.close].map(
      Number,
    );
    if (
      ![open, high, low, close].every((v) => Number.isFinite(v) && v > 0) ||
      low > Math.min(open, close) ||
      high < Math.max(open, close) ||
      !c.is_final ||
      !Number.isSafeInteger(c.open_time_ms) ||
      !Number.isSafeInteger(c.close_time_ms) ||
      c.open_time_ms >= c.close_time_ms ||
      c.close_time_ms > snapshot.as_of_ms ||
      (bars.length > 0 && c.open_time_ms <= bars[bars.length - 1].time)
    )
      return [];
    bars.push({
      open,
      high,
      low,
      close,
      volume: Number(c.volume),
      time: c.open_time_ms,
    });
  }
  return bars;
}
export function clampWindow(
  start: number,
  count: number,
  total: number,
): Window {
  if (!total) return { start: 0, count: 0 };
  const size = Math.min(total, MAX_VISIBLE, Math.max(12, Math.round(count)));
  return {
    start: Math.max(0, Math.min(total - size, Math.round(start))),
    count: size,
  };
}
export function zoomWindow(
  window: Window,
  factor: number,
  total: number,
  anchor = 0.5,
): Window {
  if (!(factor > 0) || !Number.isFinite(factor)) return window;
  const count = clampWindow(0, window.count / factor, total).count;
  return clampWindow(
    window.start + (window.count - count) * Math.max(0, Math.min(1, anchor)),
    count,
    total,
  );
}
export function panWindow(
  window: Window,
  dx: number,
  width: number,
  total: number,
): Window {
  return clampWindow(
    window.start - (dx / Math.max(1, width)) * window.count,
    window.count,
    total,
  );
}
// Visual overlays only. SMA-seeded EMA; cumulative VWAP starts at this snapshot's first bar.
// These values never enter an analysis request, strategy decision or paper order.
export function ema(bars: Bar[], period: number): (number | null)[] {
  let sum = 0,
    previous = 0;
  return bars.map((bar, i) => {
    if (i < period) sum += bar.close;
    if (i < period - 1) return null;
    previous =
      i === period - 1
        ? sum / period
        : previous + (2 / (period + 1)) * (bar.close - previous);
    return previous;
  });
}
export function snapshotVwap(
  bars: Bar[],
  realVolume: boolean,
): (number | null)[] {
  if (
    !realVolume ||
    bars.some((b) => !Number.isFinite(b.volume) || b.volume < 0)
  )
    return bars.map(() => null);
  let volume = 0,
    mean = 0;
  return bars.map((b) => {
    volume += b.volume;
    if (volume > 0)
      mean +=
        (b.high / 3 + b.low / 3 + b.close / 3 - mean) * (b.volume / volume);
    return volume > 0 && Number.isFinite(mean) ? mean : null;
  });
}
