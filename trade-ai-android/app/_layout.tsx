import React from "react";
import { StartupGate, StartupScreen } from "../src/StartupScreen";
import { prepareNativeSplash } from "../src/startup";
import {
  SafeAreaProvider,
  initialWindowMetrics,
} from "react-native-safe-area-context";
import { useFonts } from "expo-font";
import { Ionicons } from "@expo/vector-icons";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { ThemeProvider, useTheme } from "../src/theme";
import { AppProvider } from "../src/state";
import { BotProvider } from "../src/bot/state";
prepareNativeSplash();

function Navigation() {
  const { colors, isDark } = useTheme();
  const [fontsReady, fontError] = useFonts(Ionicons.font);
  return (
    <StartupGate fontsReady={fontsReady} fontError={fontError}>
      <StatusBar style={isDark ? "light" : "dark"} />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.bg },
          headerTintColor: colors.text,
          headerTitleStyle: { fontSize: 18, fontWeight: "700" },
          headerShadowVisible: false,
          contentStyle: { backgroundColor: colors.bg },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="strategy-profiles"
          options={{ title: "Strateji Profilleri" }}
        />
        <Stack.Screen
          name="market-discovery"
          options={{ title: "Tarayıcı ve Fırsatlar" }}
        />
        <Stack.Screen name="follows" options={{ title: "Analiz Takipleri" }} />
        <Stack.Screen name="history" options={{ title: "Analiz Geçmişi" }} />
        <Stack.Screen name="result" options={{ title: "Analiz Sonucu" }} />
        <Stack.Screen name="detail" options={{ title: "Analiz Detayı" }} />
        <Stack.Screen name="performance" options={{ title: "Performans" }} />
        <Stack.Screen name="notifications" options={{ title: "Bildirimler" }} />
        <Stack.Screen name="manual-trade" options={{ title: "Elle işlem" }} />
      </Stack>
    </StartupGate>
  );
}
export default function Layout() {
  return (
    <SafeAreaProvider initialMetrics={initialWindowMetrics}>
      <ThemeProvider>
        <AppProvider>
          <BotProvider>
            <Navigation />
          </BotProvider>
        </AppProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}

export function ErrorBoundary({ retry }: { retry: () => Promise<void> }) {
  return (
    <StartupScreen
      failed
      retry={() => {
        void retry().catch(() => {});
      }}
    />
  );
}
