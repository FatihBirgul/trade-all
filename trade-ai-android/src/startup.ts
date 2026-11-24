/** Local UI initialization only. Never reads a server or changes scan/order state. */
import { Platform } from "react-native";
import * as Splash from "expo-splash-screen";
export const STARTUP_BACKGROUND = "#111316";
export const FONT_DEADLINE_MS = 2500;
export const THEME_DEADLINE_MS = 750;
let held = false,
  released = false;
let watchdog: ReturnType<typeof setTimeout> | undefined;
export function releaseNativeSplash() {
  if (Platform.OS === "web" || released) return;
  released = true;
  if (watchdog) clearTimeout(watchdog);
  void Splash.hideAsync().catch(() => {});
}
export function prepareNativeSplash() {
  if (Platform.OS === "web" || held) return;
  held = true;
  try {
    // No fade/dwell requirement: first painted branded React frame owns the handoff.
    Splash.setOptions({ fade: false });
    void Splash.preventAutoHideAsync().catch(() => {});
  } catch {
    /* A missing noncritical animation API must not freeze entry. */
  }
  watchdog = setTimeout(releaseNativeSplash, 6000);
}
