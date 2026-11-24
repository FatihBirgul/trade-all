import React from "react";
import { Pressable, Text } from "react-native";
import { act, fireEvent, render, waitFor } from "@testing-library/react-native";
import { useResource } from "../src/resource";
function Probe({
  scope,
  load,
}: {
  scope: string;
  load: () => Promise<string>;
}) {
  const q = useResource(load, scope);
  return (
    <>
      <Text>{q.loading ? "yükleniyor" : (q.data ?? q.error)}</Text>
      <Pressable onPress={q.reload}>
        <Text>Yenile</Text>
      </Pressable>
    </>
  );
}
test("eski AUTO isteği MANUAL ekranına veri yazamaz", async () => {
  let resolveAuto!: (value: string) => void;
  const auto = () =>
    new Promise<string>((resolve) => {
      resolveAuto = resolve;
    });
  const manual = jest.fn().mockResolvedValue("MANUAL bakiye");
  const ui = await render(<Probe scope="AUTO" load={auto} />);
  await ui.rerender(<Probe scope="MANUAL" load={manual} />);
  await waitFor(() => expect(ui.getByText("MANUAL bakiye")).toBeTruthy());
  await act(async () => resolveAuto("AUTO bakiye"));
  expect(ui.queryByText("AUTO bakiye")).toBeNull();
  expect(ui.getByText("MANUAL bakiye")).toBeTruthy();
});
test("yenileme hatalı veriyi başarı gibi göstermez ve yeniden denenebilir", async () => {
  const load = jest
    .fn()
    .mockRejectedValueOnce(new Error("Network failed"))
    .mockResolvedValueOnce("doğrulanmış veri");
  const ui = await render(<Probe scope="live" load={load} />);
  await waitFor(() => expect(ui.getByText("Veri alınamadı.")).toBeTruthy());
  await fireEvent.press(ui.getByText("Yenile"));
  await waitFor(() => expect(ui.getByText("doğrulanmış veri")).toBeTruthy());
  expect(load).toHaveBeenCalledTimes(2);
});

test("failed same-scope refresh retains explicitly stale data without double requests", async () => {
  function Retained({ load }: { load: () => Promise<string> }) {
    const q = useResource(load, "same-account-session");
    return (
      <>
        <Text>{q.data ?? "empty"}</Text>
        <Text>{q.stale ? "old-data" : "fresh-data"}</Text>
        <Text>{q.error}</Text>
        <Pressable onPress={q.reload}>
          <Text>Refresh retained</Text>
        </Pressable>
      </>
    );
  }
  const load = jest
    .fn()
    .mockResolvedValueOnce("saved-balance")
    .mockRejectedValueOnce(new Error("Network failed"));
  const ui = await render(<Retained load={load} />);
  await waitFor(() => expect(ui.getByText("saved-balance")).toBeTruthy());
  await fireEvent.press(ui.getByText("Refresh retained"));
  await waitFor(() => expect(ui.getByText("Veri alınamadı.")).toBeTruthy());
  expect(ui.getByText("saved-balance")).toBeTruthy();
  expect(ui.getByText("old-data")).toBeTruthy();
  expect(load).toHaveBeenCalledTimes(2);
});
