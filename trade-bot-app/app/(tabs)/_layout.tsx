import React, { useEffect, useRef } from "react";
import { Tabs, router } from "expo-router";
import { useBot } from "../../src/bot/state";
import { TabBar, type TabBarProps } from "../../src/ui/TabBar";

const TABS = [
  ["index", "Panel"],
  ["positions", "Pozisyonlar"],
  ["reports", "Raporlar"],
  ["events", "Bildirimler"],
  ["settings", "Ayarlar"],
] as const;

export default function Layout() {
  const { phase } = useBot();
  // Bağlantı yoksa uygulama açılışta bir kez bağlantı ekranını açar (kök rota; gizli sekme değil).
  const asked = useRef(false);
  useEffect(() => {
    if (asked.current || phase === "loading") return;
    asked.current = true;
    if (phase !== "ready") router.push("/connection");
  }, [phase]);
  return (
    <Tabs tabBar={(props) => <TabBar {...(props as unknown as TabBarProps)} />} screenOptions={{ headerShown: false }}>
      {TABS.map(([name, title]) => (
        <Tabs.Screen key={name} name={name} options={{ title }} />
      ))}
    </Tabs>
  );
}
