import React from "react";
import { useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tabs } from "expo-router";
import { tabBarHeight } from "../../src/navigationLayout";
import { TabIcon } from "../../src/TabIcon";
import { useApp } from "../../src/state";
import { useTheme } from "../../src/theme";
export default function Layout() {
  const { fontScale } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const { uiMode } = useApp();
  const { colors } = useTheme();
  const screens = [
    ["index", "Ana Sayfa", "home-outline"],
    ["analysis", "Analiz", "analytics-outline"],
    ["portfolios", "Portföyler", "wallet-outline"],
    ["scanner", "Tarayıcı", "scan-outline"],
    ["settings", "Ayarlar", "settings-outline"],
  ] as const;
  return (
    <Tabs
      backBehavior="firstRoute"
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.soft,
          borderTopColor: colors.border,
          height: tabBarHeight(fontScale, insets.bottom),
          paddingTop: 6,
          paddingBottom: Math.max(8, insets.bottom),
        },
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.muted,
        tabBarHideOnKeyboard: true,
        tabBarLabelPosition: "below-icon",
        tabBarLabelStyle: { fontSize: 11, lineHeight: 15, fontWeight: "600" },
        tabBarIconStyle: { width: 32, height: 28 },
        animation: "none",
        tabBarItemStyle: { paddingHorizontal: 2 },
      }}
    >
      {screens.map(([name, title, icon]) => (
        <Tabs.Screen
          key={name}
          name={name}
          options={{
            title,
            ...(name === "scanner" && uiMode !== "pro" ? { href: null } : {}),
            tabBarIcon: ({ color, focused }) => (
              <TabIcon
                name={icon}
                color={typeof color === "string" ? color : colors.muted}
                focused={focused}
              />
            ),
          }}
        />
      ))}
    </Tabs>
  );
}
