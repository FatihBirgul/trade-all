import React from "react";
import { useWindowDimensions } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Tabs } from "expo-router";
import { useConnectOnStart } from "../../src/bot/connectOnStart";
import { tabBarHeight } from "../../src/navigationLayout";
import { TabIcon } from "../../src/TabIcon";
import { useTheme } from "../../src/theme";
export default function Layout() {
  const { fontScale } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const { colors } = useTheme();
  useConnectOnStart();
  // Görünen sekmeler trade bot ekranlarıdır. Eski kripto ekranları yerinde durur ama sekme
  // çubuğunda gösterilmez (spec §8). Gizli sekmeye (href: null) router.push ÇALIŞMAZ (expo-router gizli sekmeyi
  // yönlendirir); başka ekrandan açılacak her ekran kök Stack rotası olmalıdır (örn. app/connection.tsx).
  const screens = [
    ["index", "Panel", "speedometer-outline", true],
    ["positions", "Pozisyonlar", "list-outline", true],
    ["reports", "Raporlar", "bar-chart-outline", true],
    ["events", "Bildirimler", "notifications-outline", true],
    ["settings-bot", "Ayarlar", "options-outline", true],
    ["legacy", "Eski Ana Sayfa", "home-outline", false],
    ["analysis", "Analiz", "analytics-outline", false],
    ["portfolios", "Portföyler", "wallet-outline", false],
    ["scanner", "Tarayıcı", "scan-outline", false],
    ["settings", "Ayarlar", "settings-outline", false],
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
      {screens.map(([name, title, icon, visible]) => (
        <Tabs.Screen
          key={name}
          name={name}
          options={{
            title,
            ...(visible ? {} : { href: null }),
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
