import React from "react";
import { Text, Pressable } from "react-native";
import { render, fireEvent, waitFor, act } from "@testing-library/react-native";
import { filterHistory } from "../src/domain/history";
import { comparable } from "../src/domain/records";
import { usePagedHistory } from "../src/usePagedHistory";
import type { Analysis } from "../src/domain/safety";
import sample from "../docs/backend/v2_examples/analysis.json";
const record = (i: number, account: "AUTO" | "MANUAL" = "AUTO") =>
  ({
    ...sample,
    analysis_id: i.toString(16).padStart(64, "0"),
    risk_portfolio: account,
    created_at_ms: sample.created_at_ms + i,
  }) as Analysis;
test("combined symbol/timeframe/account/decision filters sort copies of immutable records", () => {
  const rows = [
    record(1),
    {
      ...record(2, "MANUAL"),
      symbol: "ETHUSDT",
      timeframe: "4H",
      direction: "WAIT" as const,
      levels: null,
    },
    record(3),
  ];
  const before = JSON.stringify(rows);
  const filters = {
    symbol: "ETHUSDT",
    timeframe: "4H",
    account: "MANUAL",
    decision: "BEKLE",
    order: "Eski → Yeni",
  };
  expect(filterHistory(rows, filters)).toEqual([rows[1]]);
  expect(
    filterHistory(rows, {
      ...filters,
      symbol: "Tümü",
      timeframe: "Tümü",
      account: "Tümü",
      decision: "Tümü",
    }).map((a) => a.analysis_id),
  ).toEqual(rows.map((a) => a.analysis_id));
  expect(JSON.stringify(rows)).toBe(before);
  expect(comparable(rows[0], { ...rows[2], provider: "other" })).toBe(false);
});
function Probe({
  load,
  scope,
}: {
  load: (offset: number) => Promise<Analysis[]>;
  scope: string;
}) {
  const q = usePagedHistory(load, scope);
  return (
    <>
      <Text>{q.rows.map((a) => a.risk_portfolio).join(",") || "empty"}</Text>
      <Pressable onPress={q.more}>
        <Text>More</Text>
      </Pressable>
    </>
  );
}
test("history paging uses the next server offset and coalesces rapid load-more taps", async () => {
  let complete!: (a: Analysis[]) => void;
  const load = jest
    .fn()
    .mockResolvedValueOnce(Array.from({ length: 20 }, (_, i) => record(i)))
    .mockImplementationOnce(
      () =>
        new Promise<Analysis[]>((resolve) => {
          complete = resolve;
        }),
    );
  const ui = await render(<Probe scope="same" load={load} />);
  await waitFor(() => expect(load).toHaveBeenCalledWith(0));
  await waitFor(() => expect(ui.queryByText("empty")).toBeNull());
  await fireEvent.press(ui.getByText("More"));
  await fireEvent.press(ui.getByText("More"));
  expect(load).toHaveBeenCalledTimes(2);
  expect(load).toHaveBeenLastCalledWith(20);
  await act(async () => complete([record(20)]));
  await ui.unmount();
});
test("late history page from another connection/account cannot enter the current list", async () => {
  let finish!: (a: Analysis[]) => void;
  const ui = await render(
    <Probe
      scope="old"
      load={() =>
        new Promise((resolve) => {
          finish = resolve;
        })
      }
    />,
  );
  await ui.rerender(
    <Probe scope="new" load={async () => [record(1, "MANUAL")]} />,
  );
  await waitFor(() => expect(ui.getByText("MANUAL")).toBeTruthy());
  await act(async () => finish([record(2, "AUTO")]));
  expect(ui.queryByText("AUTO")).toBeNull();
  expect(ui.getByText("MANUAL")).toBeTruthy();
});
