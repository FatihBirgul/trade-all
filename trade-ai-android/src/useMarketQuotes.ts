import { useCallback, useRef, useState } from "react";
import { AppState } from "react-native";
import { useFocusEffect } from "expo-router";
import { useApp } from "./state";
import { quotesStale, validQuotes, type Quotes } from "./domain/quotes";
import { userErrorText } from "./domain/presentation";
export function useMarketQuotes() {
  const app = useApp();
  const scope = [app.mode, app.connectionKey, app.config.session].join("|");
  const [state, setState] = useState<{
    scope: string;
    data?: Quotes;
    error?: string;
    loading: boolean;
    now: number;
  }>({ scope, loading: false, now: 0 });
  const reloadRef = useRef<() => void>(() => {});
  useFocusEffect(
    useCallback(() => {
      if (
        app.mode !== "live" ||
        !app.gatewayVerified ||
        !app.sessionInfo?.capabilities?.includes("market-quotes-v1")
      )
        return;
      let active = true,
        foreground =
          AppState.currentState !== "background" &&
          AppState.currentState !== "inactive",
        running = false;
      let timer: ReturnType<typeof setTimeout>;
      async function load() {
        if (!active || !foreground || running) return;
        running = true;
        clearTimeout(timer);
        setState((old) =>
          old.scope === scope
            ? { ...old, scope, loading: true, now: Date.now() }
            : { scope, loading: true, now: Date.now() },
        );
        try {
          const data = await app.api.quotes();
          if (!validQuotes(data, Date.now()))
            throw new Error("Piyasa verisi doğrulanamadı.");
          if (active)
            setState({ scope, data, loading: false, now: Date.now() });
        } catch (error) {
          if (active)
            setState((old) => ({
              ...old,
              scope,
              loading: false,
              error: userErrorText(error),
              now: Date.now(),
            }));
        } finally {
          running = false;
          if (active && foreground) timer = setTimeout(load, 30000);
        }
      }
      reloadRef.current = () => {
        void load();
      };
      void load();
      const clock = setInterval(() => {
        if (active && foreground)
          setState((old) => ({ ...old, now: Date.now() }));
      }, 15000);
      const sub = AppState.addEventListener("change", (value) => {
        foreground = value === "active";
        clearTimeout(timer);
        if (foreground) void load();
      });
      return () => {
        active = false;
        clearTimeout(timer);
        clearInterval(clock);
        sub.remove();
        reloadRef.current = () => {};
      };
    }, [
      app.api,
      app.mode,
      app.gatewayVerified,
      app.sessionInfo?.capabilities,
      scope,
    ]),
  );
  const current =
    state.scope === scope ? state : { scope, loading: false, now: 0 };
  return {
    ...current,
    stale:
      !!current.data &&
      (!!current.error || quotesStale(current.data, current.now)),
    reload: () => reloadRef.current(),
  };
}
