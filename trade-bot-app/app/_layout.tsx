import React from "react";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { SafeAreaProvider, initialWindowMetrics } from "react-native-safe-area-context";
import { BotProvider } from "../src/bot/state";
import { ConfirmProvider } from "../src/ui/confirm";
import { c } from "../src/ui/theme";

export default function Layout() {
  return (
    <SafeAreaProvider initialMetrics={initialWindowMetrics}>
      <BotProvider>
        <ConfirmProvider>
          <StatusBar style="dark" />
          <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: c.bg } }} />
        </ConfirmProvider>
      </BotProvider>
    </SafeAreaProvider>
  );
}
