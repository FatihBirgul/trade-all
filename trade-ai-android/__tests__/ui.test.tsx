import React from "react";
import { fireEvent, render } from "@testing-library/react-native";
import { ThemeProvider } from "../src/theme";
import { Button, Choices } from "../src/ui";
test("disabled actions cannot be activated", async () => {
  const action = jest.fn();
  const ui = await render(
    <ThemeProvider>
      <Button title="Analiz" disabled onPress={action} />
    </ThemeProvider>,
  );
  await fireEvent.press(ui.getByText("Analiz"));
  expect(action).not.toHaveBeenCalled();
});
test("market selection is accessible and interactive", async () => {
  const change = jest.fn();
  const ui = await render(
    <ThemeProvider>
      <Choices
        values={["BTCUSDT", "ETHUSDT"]}
        value="BTCUSDT"
        onChange={change}
      />
    </ThemeProvider>,
  );
  await fireEvent.press(ui.getByText("ETHUSDT"));
  expect(change).toHaveBeenCalledWith("ETHUSDT");
});

test("doğrulanmamış canlı mod seçilemez", async () => {
  const change = jest.fn();
  const ui = await render(
    <ThemeProvider>
      <Choices
        values={["DEMO", "CANLI"]}
        value="DEMO"
        onChange={change}
        disabledValues={["CANLI"]}
      />
    </ThemeProvider>,
  );
  await fireEvent.press(ui.getByText("CANLI"));
  expect(change).not.toHaveBeenCalled();
});
