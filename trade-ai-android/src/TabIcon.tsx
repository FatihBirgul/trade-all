import React from "react";
import { View } from "react-native";
import { useIconFontReady } from "./StartupScreen";
import { Ionicons } from "@expo/vector-icons";
// The navigator's icon slot is 31x28. Horizontal padding inside an auto-sized
// child can leave a ~3px text width in native Yoga; never pad the glyph container.
export function TabIcon({
  name,
  color,
  focused,
}: {
  name: React.ComponentProps<typeof Ionicons>["name"];
  color: string;
  focused: boolean;
}) {
  const ready = useIconFontReady();
  return (
    <View
      testID="tab-icon-slot"
      pointerEvents="none"
      style={{
        width: 32,
        height: 28,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      {ready ? (
        <Ionicons
          name={name}
          size={23}
          color={color}
          allowFontScaling={false}
          style={{
            width: 26,
            height: 26,
            lineHeight: 26,
            textAlign: "center",
            includeFontPadding: false,
          }}
        />
      ) : (
        <View
          testID="tab-icon-fallback"
          style={{
            width: 8,
            height: 8,
            borderWidth: 1,
            borderRadius: 4,
            borderColor: color,
          }}
        />
      )}
      {focused ? (
        <View
          style={{
            position: "absolute",
            bottom: 0,
            width: 12,
            height: 2,
            borderRadius: 1,
            backgroundColor: color,
          }}
        />
      ) : null}
    </View>
  );
}
