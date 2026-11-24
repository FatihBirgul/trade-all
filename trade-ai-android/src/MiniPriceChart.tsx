import React, { useState } from "react";
import { View } from "react-native";
import { useTheme } from "./theme";
export function MiniPriceChart({
  prices,
  accessibilityLabel = "Son kapalı 1 saatlik mumların fiyat grafiği",
}: {
  prices: string[];
  accessibilityLabel?: string;
}) {
  const theme = useTheme(),
    [width, setWidth] = useState(240);
  if (prices.length < 2) return null;
  const values = prices.map(Number),
    lo = Math.min(...values),
    hi = Math.max(...values),
    range = hi - lo || 1;
  return (
    <View
      accessibilityLabel={accessibilityLabel}
      style={{ height: 48, width: "100%", overflow: "hidden" }}
      onLayout={(event) => setWidth(event.nativeEvent.layout.width)}
    >
      {values.slice(1).map((value, i) => {
        const x = (i * width) / (values.length - 1),
          nextX = ((i + 1) * width) / (values.length - 1),
          y = 44 - ((values[i] - lo) / range) * 40,
          nextY = 44 - ((value - lo) / range) * 40;
        const length = Math.hypot(nextX - x, nextY - y),
          angle = (Math.atan2(nextY - y, nextX - x) * 180) / Math.PI;
        return (
          <View
            key={i}
            style={{
              position: "absolute",
              left: (x + nextX) / 2 - length / 2,
              top: (y + nextY) / 2,
              width: length,
              height: 2,
              backgroundColor: theme.colors.gold,
              transform: [{ rotate: angle + "deg" }],
            }}
          />
        );
      })}
    </View>
  );
}
