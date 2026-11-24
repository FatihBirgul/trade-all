import React, {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import { THEME_DEADLINE_MS } from "./startup";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
export const dark = {
  bg: "#111316",
  card: "#1B2027",
  soft: "#171C22",
  text: "#F2F4F8",
  muted: "#AFB8C4",
  border: "#303842",
  gold: "#E2BD78",
  green: "#6ED5AC",
  red: "#FF9B9B",
};
export const design = {
  space: { xs: 4, sm: 8, md: 12, lg: 12, xl: 20, xxl: 28 },
  radius: { chip: 12, button: 14, card: 16 },
  type: { caption: 12, body: 14, section: 16, title: 23, price: 23 },
};
export const light: typeof dark = {
  bg: "#F1F3F7",
  card: "#FFFFFF",
  soft: "#E8EDF4",
  text: "#152235",
  muted: "#546477",
  border: "#CDD6E2",
  gold: "#896320",
  green: "#157451",
  red: "#AC3030",
};
const Context = createContext({
  colors: dark,
  isDark: true,
  ready: true,
  toggle: () => {},
});
const THEME_KEY = "trade_ai_theme";
async function readTheme(): Promise<string | null> {
  if (Platform.OS === "web") return window.localStorage.getItem(THEME_KEY);
  return SecureStore.getItemAsync(THEME_KEY);
}
async function saveTheme(value: "dark" | "light") {
  if (Platform.OS === "web") window.localStorage.setItem(THEME_KEY, value);
  else await SecureStore.setItemAsync(THEME_KEY, value);
}
export function ThemeProvider({ children }: PropsWithChildren) {
  const [ready, setReady] = useState(false);
  const [isDark, setDark] = useState(true);
  const touched = useRef(false);
  useEffect(() => {
    let active = true;
    const timeout = setTimeout(() => {
      active = false;
      setReady(true);
    }, THEME_DEADLINE_MS);
    readTheme()
      .then((stored) => {
        if (
          active &&
          !touched.current &&
          (stored === "dark" || stored === "light")
        )
          setDark(stored === "dark");
      })
      .catch(() => {})
      .finally(() => {
        if (active) {
          clearTimeout(timeout);
          setReady(true);
        }
      });
    return () => {
      clearTimeout(timeout);
      active = false;
    };
  }, []);
  function toggle() {
    touched.current = true;
    setReady(true);
    const next = !isDark;
    setDark(next);
    void saveTheme(next ? "dark" : "light").catch(() => {});
  }
  return (
    <Context.Provider
      value={{
        colors: isDark ? dark : light,
        isDark,
        ready,
        toggle,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export const useTheme = () => useContext(Context);
