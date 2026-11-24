import React from "react";
import { Pressable, Text } from "react-native";
import { fireEvent, render } from "@testing-library/react-native";
import { AppProvider, useApp } from "../src/state";

function ModeProbe() {
  const app = useApp();
  return (
    <>
      <Text>{app.mode}</Text>
      <Pressable onPress={() => app.setMode("live")}>
        <Text>CANLI seç</Text>
      </Pressable>
    </>
  );
}

test("uygulama doğrulanmamış gateway ile canlı moda geçmez", async () => {
  const ui = await render(
    <AppProvider>
      <ModeProbe />
    </AppProvider>,
  );
  await fireEvent.press(ui.getByText("CANLI seç"));
  expect(ui.getByText("demo")).toBeTruthy();
});
