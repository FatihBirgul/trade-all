import React from "react";
import { PanResponder } from "react-native";
import { render, fireEvent, waitFor, act } from "@testing-library/react-native";
import {
  chartBars,
  clampWindow,
  ema,
  panWindow,
  snapshotVwap,
  zoomWindow,
  type Snapshot,
} from "../src/domain/chart";
import { SnapshotChart } from "../src/SnapshotChart";
import { SnapshotPanel } from "../src/SnapshotPanel";
import { useApp } from "../src/state";
import { ThemeProvider } from "../src/theme";
import sample from "../docs/backend/v2_examples/analysis.json";
import type { Analysis } from "../src/domain/safety";
jest.mock("../src/state", () => ({ useApp: jest.fn() }));
function snapshot(count = 100): Snapshot {
  return {
    analysis_id: "a".repeat(64),
    source_record_id: "b".repeat(64),
    symbol: sample.symbol,
    timeframe: sample.timeframe,
    provider: sample.provider,
    venue: sample.venue,
    data_mode: "live",
    source: "immutable",
    as_of_ms: sample.created_at_ms,
    price_kind: "last",
    contract_type: "spot",
    quote_currency: "USDT",
    snapshot_only: true,
    volume_kind: "real",
    candles: Array.from({ length: count }, (_, i) => ({
      open_time_ms: sample.created_at_ms - (count - i) * 3600000,
      close_time_ms: sample.created_at_ms - (count - i - 1) * 3600000 - 1,
      is_final: true,
      open: String(100 + i),
      close: String(101 + i),
      high: String(102 + i),
      low: String(99 + i),
      volume: "10",
    })),
  };
}
test("invalid OHLC, nonfinal, chronology and oversized snapshots fail closed", () => {
  const s = snapshot();
  expect(chartBars(s)).toHaveLength(100);
  const before = JSON.stringify(s);
  chartBars(s);
  expect(JSON.stringify(s)).toBe(before);
  for (const patch of [
    { high: "1" },
    { low: "500" },
    { close: "NaN" },
    { is_final: false },
    { open_time_ms: s.as_of_ms + 1 },
  ]) {
    expect(
      chartBars({ ...s, candles: [{ ...s.candles[0], ...patch }] } as Snapshot),
    ).toEqual([]);
  }
  expect(chartBars(snapshot(4097))).toEqual([]);
  expect(chartBars({ ...s, candles: [s.candles[1], s.candles[0]] })).toEqual(
    [],
  );
});
test("viewport pan and anchored pinch remain bounded for long and short records", () => {
  expect(clampWindow(-100, 900, 300)).toEqual({ start: 0, count: 96 });
  const w = { start: 200, count: 48 };
  expect(zoomWindow(w, 2, 300)).toEqual({ start: 212, count: 24 });
  expect(zoomWindow(w, 2, 300, 0)).toEqual({ start: 200, count: 24 });
  expect(panWindow(w, 240, 240, 300).start).toBe(152);
  expect(panWindow(w, -10000, 240, 300).start).toBe(252);
  expect(clampWindow(100, 50, 3)).toEqual({ start: 0, count: 3 });
  expect(zoomWindow(w, 0, 300)).toEqual(w);
});
test("EMA warmup is honest and cumulative real-volume VWAP is reproducible", () => {
  const bars = chartBars(snapshot(60));
  const e = ema(bars, 20);
  expect(e.slice(0, 19)).toEqual(Array(19).fill(null));
  expect(e[19]).toBe(110.5);
  expect(e[20]).toBe(111.5);
  expect(snapshotVwap(bars, false).every((v) => v === null)).toBe(true);
  const v = snapshotVwap(bars, true);
  expect(v[0]).toBeCloseTo((102 + 99 + 101) / 3);
  expect(v[1]).toBeCloseTo((102 + 99 + 101) / 3 + 0.5);
  expect(snapshotVwap([{ ...bars[0], volume: 0 }], true)).toEqual([null]);
  expect(snapshotVwap([{ ...bars[0], volume: NaN }], true)).toEqual([null]);
});
test("basic chart has readable snapshot labels and bounded zoom without pro indicators", async () => {
  const ui = await render(
    <ThemeProvider>
      <SnapshotChart snapshot={snapshot()} />
    </ThemeProvider>,
  );
  expect(ui.getByText("KAYITLI ANALİZ · CANLI GRAFİK DEĞİL")).toBeTruthy();
  expect(ui.getAllByTestId("snapshot-candle")).toHaveLength(48);
  expect(ui.queryByText("EMA20 kapalı")).toBeNull();
  await fireEvent.press(ui.getByText("Yakınlaştır"));
  expect(ui.getAllByTestId("snapshot-candle")).toHaveLength(32);
  await fireEvent.press(ui.getByText("Uzaklaştır"));
  expect(ui.getAllByTestId("snapshot-candle")).toHaveLength(48);
});
test("pro toggles EMA/VWAP and only passed verified levels; no record mutation", async () => {
  const s = snapshot(),
    before = JSON.stringify(s);
  const ui = await render(
    <ThemeProvider>
      <SnapshotChart snapshot={s} pro levels={sample.levels} />
    </ThemeProvider>,
  );
  await fireEvent.press(ui.getByText("EMA20 kapalı"));
  expect(ui.getByText("EMA20 açık")).toBeTruthy();
  await fireEvent.press(ui.getByText("VWAP kapalı"));
  expect(ui.getByText("VWAP açık")).toBeTruthy();
  await fireEvent.press(ui.getByText("Seviyeler kapalı"));
  expect(ui.getByText("Seviyeler açık")).toBeTruthy();
  expect(JSON.stringify(s)).toBe(before);
  await ui.rerender(
    <ThemeProvider>
      <SnapshotChart snapshot={s} pro levels={null} />
    </ThemeProvider>,
  );
  expect(ui.queryByText("Seviyeler açık")).toBeNull();
});
test("snapshot load is opt-in and rejects another analysis identity", async () => {
  const a = {
    ...sample,
    analysis_id: "a".repeat(64),
    data_mode: "live",
  } as Analysis;
  const candles = jest
    .fn()
    .mockResolvedValue({ ...snapshot(), analysis_id: "c".repeat(64) });
  jest.mocked(useApp).mockReturnValue({
    mode: "live",
    config: { session: "test" },
    connectionKey: 1,
    uiMode: "basic",
    api: { candles },
  } as unknown as ReturnType<typeof useApp>);
  const ui = await render(
    <ThemeProvider>
      <SnapshotPanel analysis={a} levelsAllowed={false} />
    </ThemeProvider>,
  );
  expect(candles).not.toHaveBeenCalled();
  await fireEvent.press(ui.getByText("Analiz mumlarını yükle"));
  await waitFor(() =>
    expect(
      ui.getByText("Analiz mumlarının kaynağı doğrulanamadı."),
    ).toBeTruthy(),
  );
  expect(ui.queryByTestId("snapshot-plot")).toBeNull();
  expect(candles).toHaveBeenCalledWith(a.analysis_id, a.timeframe);
});

test("native gesture handlers distinguish vertical scrolling, pan and two-finger zoom", async () => {
  let handlers: Parameters<typeof PanResponder.create>[0] = {};
  const spy = jest
    .spyOn(PanResponder, "create")
    .mockImplementation((config) => {
      handlers = config;
      return { panHandlers: {} } as ReturnType<typeof PanResponder.create>;
    });
  try {
    const ui = await render(
      <ThemeProvider>
        <SnapshotChart snapshot={snapshot()} pro />
      </ThemeProvider>,
    );
    const event = (points: number[]) =>
      ({
        nativeEvent: {
          touches: points.map((x) => ({ pageX: x, pageY: 0, locationX: x })),
        },
      }) as unknown as Parameters<
        NonNullable<typeof handlers.onPanResponderGrant>
      >[0];
    const gesture = (dx: number, dy = 0) =>
      ({ dx, dy }) as unknown as Parameters<
        NonNullable<typeof handlers.onPanResponderGrant>
      >[1];
    expect(
      handlers.onMoveShouldSetPanResponder!(event([0]), gesture(3, 30)),
    ).toBe(false);
    expect(
      handlers.onMoveShouldSetPanResponder!(event([0]), gesture(30, 3)),
    ).toBe(true);
    await act(async () =>
      handlers.onPanResponderGrant!(event([0, 100]), gesture(0)),
    );
    await act(async () =>
      handlers.onPanResponderMove!(event([0, 200]), gesture(0)),
    );
    expect(ui.getAllByTestId("snapshot-candle")).toHaveLength(24);
    await act(async () =>
      handlers.onPanResponderGrant!(event([100]), gesture(0)),
    );
    await act(async () =>
      handlers.onPanResponderMove!(event([200]), gesture(100)),
    );
    expect(ui.getAllByTestId("snapshot-candle")).toHaveLength(24);
    expect(ui.getByText(/48–71 \/ 100 mum/)).toBeTruthy();
  } finally {
    spy.mockRestore();
  }
});
