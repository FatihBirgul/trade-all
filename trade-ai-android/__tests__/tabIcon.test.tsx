import React from "react";
import { StyleSheet } from "react-native";
import { render } from "@testing-library/react-native";
import { tabBarHeight } from "../src/navigationLayout";
import { TabIcon } from "../src/TabIcon";
jest.mock("expo-font", () => ({ isLoaded: () => true, loadAsync: jest.fn() }));
test("native icon glyph has its own fixed unpadded width and ignores text scaling", async () => {
  const ui = await render(
    <TabIcon name="home-outline" color="#ffffff" focused />,
  );
  const slot = StyleSheet.flatten(ui.getByTestId("tab-icon-slot").props.style);
  expect(slot.width).toBe(32);
  expect(slot.height).toBe(28);
  expect(slot.paddingHorizontal).toBeUndefined();
});

test("navigation reserves native item padding, glyph, label and system inset at large text sizes", () => {
  for (const fontScale of [1, 1.5, 2])
    for (const inset of [0, 24, 48]) {
      const content =
        tabBarHeight(fontScale, inset) - Math.max(8, inset) - 6 - 10;
      expect(content).toBeGreaterThanOrEqual(28 + 15 * fontScale);
    }
});
