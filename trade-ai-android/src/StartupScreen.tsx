import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  type PropsWithChildren,
} from "react";
import {
  AppState,
  Platform,
  ActivityIndicator,
  Image,
  Pressable,
  Text,
  View,
} from "react-native";
import * as SystemUI from "expo-system-ui";
import { NavigationBar } from "expo-navigation-bar";
import { StatusBar } from "expo-status-bar";
import mark from "../assets/brand/adaptive-foreground.png";
import { useTheme } from "./theme";
import {
  FONT_DEADLINE_MS,
  STARTUP_BACKGROUND,
  releaseNativeSplash,
} from "./startup";
const IconContext = createContext(true);
export const useIconFontReady = () => useContext(IconContext);
function useSystemSurface(background: string, dark: boolean) {
  useEffect(() => {
    const apply = () => {
      void SystemUI.setBackgroundColorAsync(background).catch(() => {});
      if (Platform.OS === "android") {
        try {
          NavigationBar.setStyle(dark ? "light" : "dark");
        } catch {
          /* Noncritical system appearance, never block entry. */
        }
      }
    };
    apply();
    const listener = AppState.addEventListener("change", (state) => {
      if (state === "active") apply();
    });
    return () => listener.remove();
  }, [background, dark]);
}
export function StartupScreen({
  failed,
  retry,
}: {
  failed?: boolean;
  retry?: () => void;
}) {
  useSystemSurface(STARTUP_BACKGROUND, true);
  return (
    <View
      testID="startup-frame"
      onLayout={releaseNativeSplash}
      style={{
        flex: 1,
        backgroundColor: STARTUP_BACKGROUND,
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        gap: 18,
      }}
    >
      <StatusBar style="light" />
      <Image
        source={mark}
        accessibilityLabel="TRADE AI T simgesi"
        resizeMode="contain"
        style={{ width: 176, height: 176 }}
      />
      <Text
        style={{
          color: "#F1F3F5",
          fontSize: 18,
          fontWeight: "600",
          letterSpacing: 3,
        }}
      >
        TRADE AI
      </Text>
      {failed ? (
        <>
          <Text
            style={{ color: "#AFB8C4", textAlign: "center", lineHeight: 22 }}
          >
            Uygulama görünümü hazırlanamadı. Kayıtlı oturum ve veriler
            silinmedi.
          </Text>
          <Pressable
            accessibilityRole="button"
            onPress={retry}
            style={{
              minHeight: 48,
              padding: 14,
              borderWidth: 1,
              borderColor: "#AFB8C4",
              borderRadius: 14,
            }}
          >
            <Text style={{ color: "#F1F3F5" }}>Yeniden dene</Text>
          </Pressable>
        </>
      ) : (
        <ActivityIndicator
          accessibilityLabel="Uygulama hazırlanıyor"
          color="#AFB8C4"
          size="small"
        />
      )}
    </View>
  );
}
export function StartupGate({
  fontsReady,
  fontError,
  children,
}: PropsWithChildren<{ fontsReady: boolean; fontError: Error | null }>) {
  const theme = useTheme();
  const [fontTimedOut, setFontTimedOut] = useState(false);
  useEffect(() => {
    if (fontsReady || fontError) return;
    const timer = setTimeout(() => setFontTimedOut(true), FONT_DEADLINE_MS);
    return () => clearTimeout(timer);
  }, [fontsReady, fontError]);
  const initializing =
    !theme.ready || (!fontsReady && !fontError && !fontTimedOut);
  useSystemSurface(
    initializing ? STARTUP_BACKGROUND : theme.colors.bg,
    initializing || theme.isDark,
  );
  if (initializing) return <StartupScreen />;
  return (
    <IconContext.Provider value={fontsReady}>
      <View
        testID="startup-ready"
        onLayout={releaseNativeSplash}
        style={{ flex: 1, backgroundColor: theme.colors.bg }}
      >
        {!fontsReady ? (
          <Text
            accessibilityRole="alert"
            style={{
              color: theme.colors.text,
              backgroundColor: theme.colors.soft,
              padding: 10,
              fontSize: 12,
            }}
          >
            İkonlar yüklenemedi · metinli gezinme kullanılabilir.
          </Text>
        ) : null}
        {children}
      </View>
    </IconContext.Provider>
  );
}
