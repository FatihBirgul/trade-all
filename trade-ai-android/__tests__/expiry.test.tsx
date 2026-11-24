import React from "react";
import { Text } from "react-native";
import { act, render } from "@testing-library/react-native";
import { useAnalysisDecision } from "../src/useAnalysisDecision";
import type { Analysis } from "../src/domain/safety";
import example from "../docs/backend/v2_examples/analysis.json";
function Probe({ analysis }: { analysis: Analysis }) {
  return <Text>{useAnalysisDecision(analysis)}</Text>;
}
test("açık detay ekranı analiz bitişinde kendiliğinden WAIT olur", async () => {
  jest.useFakeTimers();
  try {
    const now = Date.now();
    const analysis = {
      ...example,
      price_time_ms: now - 1000,
      expires_at_ms: now + 1000,
    } as Analysis;
    const ui = await render(<Probe analysis={analysis} />);
    expect(ui.getByText("bullish")).toBeTruthy();
    await act(async () => {
      jest.advanceTimersByTime(1001);
    });
    expect(ui.getByText("WAIT")).toBeTruthy();
    await ui.unmount();
  } finally {
    jest.useRealTimers();
  }
});
