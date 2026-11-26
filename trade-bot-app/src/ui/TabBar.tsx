import React from "react";
import { Pressable, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { c } from "./theme";

const ICONS: Record<string, React.ComponentProps<typeof Ionicons>["name"]> = {
  index: "grid",
  positions: "swap-vertical",
  reports: "pie-chart",
  events: "notifications",
  settings: "settings",
};

// Koyu hap biçimli sekme çubuğu: etkin sekme beyaz hap içinde adıyla, diğerleri yalnızca ikon.
// expo-router'ın sekme çubuğuna verdiği değerlerin burada kullanılan kısmı.
export type TabBarProps = {
  state: { index: number; routes: { key: string; name: string }[] };
  descriptors: Record<string, { options: { title?: string } }>;
};

export function TabBar({ state, descriptors }: TabBarProps) {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ paddingHorizontal: 14, paddingBottom: Math.max(12, insets.bottom), paddingTop: 6, backgroundColor: c.bg }}>
      <View accessibilityRole="tablist" style={{ flexDirection: "row", backgroundColor: c.text, borderRadius: 28, padding: 8 }}>
        {state.routes.map((route, index) => {
          const active = state.index === index;
          const title = String(descriptors[route.key].options.title ?? route.name);
          return (
            <Pressable
              key={route.key}
              testID={"tab-" + route.name}
              accessibilityRole="tab"
              accessibilityLabel={title}
              accessibilityState={{ selected: active }}
              onPress={() => {
                // Geçiş expo-router üzerinden yapılır (yol adıyla); sekme çubuğuna verilen navigation nesnesine
                // doğrudan navigate demek bu sürümde sekmeyi değiştirmiyor.
                if (!active) router.navigate(route.name === "index" ? "/" : "/" + route.name);
              }}
              style={{ flex: active ? 2.4 : 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, minHeight: 44, borderRadius: 22, backgroundColor: active ? c.white : "transparent" }}
            >
              <Ionicons name={ICONS[route.name] ?? "ellipse"} size={19} color={active ? c.hero : "#A9ADD0"} />
              {active ? <Text numberOfLines={1} style={{ color: c.hero, fontWeight: "800", fontSize: 13 }}>{title}</Text> : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
