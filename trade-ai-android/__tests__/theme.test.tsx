import React from "react";
import { fireEvent, render, waitFor } from "@testing-library/react-native";
import * as SecureStore from "expo-secure-store";
import { Button } from "../src/ui";
import { ThemeProvider, useTheme } from "../src/theme";

function ThemeSwitch() {
  const { isDark, toggle } = useTheme();
  return <Button title={isDark ? "Koyu" : "Açık"} onPress={toggle} />;
}

test("seçilen tema yeniden açılışta korunur", async () => {
  const read = jest.spyOn(SecureStore, "getItemAsync").mockResolvedValue("light");
  const write = jest.spyOn(SecureStore, "setItemAsync").mockResolvedValue();
  const ui = await render(
    <ThemeProvider>
      <ThemeSwitch />
    </ThemeProvider>,
  );
  await waitFor(() => expect(ui.getByText("Açık")).toBeTruthy());
  await fireEvent.press(ui.getByText("Açık"));
  await waitFor(() => expect(write).toHaveBeenCalledWith("trade_ai_theme", "dark"));
  await ui.unmount();
  read.mockResolvedValue("dark");
  const reopened = await render(
    <ThemeProvider>
      <ThemeSwitch />
    </ThemeProvider>,
  );
  await waitFor(() => expect(reopened.getByText("Koyu")).toBeTruthy());
  read.mockRestore();
  write.mockRestore();
});
