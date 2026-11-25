import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import { AppState } from "react-native";
import { BotError, createBotApi, pairBot, type BotApi } from "./client";
import { clearBotConfig, loadBotConfig, saveBotConfig } from "./storage";
import type { BotConfig, BotEvent, BotPosition, BotStatus } from "./types";

export const POLL_MS = 5000;
export const EVENTS_EVERY = 3; // olaylar her 3 yoklamada bir (15 sn)
export const STALE_SECONDS = 300;
const MAX_EVENTS = 300;

export type BotPhase = "loading" | "unconfigured" | "ready" | "revoked";

type BotState = {
  phase: BotPhase;
  config: BotConfig | null;
  status: BotStatus | null;
  positions: BotPosition[];
  events: BotEvent[];
  error: string;
  // Sunucu yanıt vermiyor ya da botun kalp atışı 5 dakikadan eski: ekrandaki veri güncel değil.
  heartbeatStale: boolean;
  lastOkAt: number | null;
  api: BotApi;
  pair: (origin: string, code: string) => Promise<void>;
  disconnect: () => Promise<void>;
  refresh: () => Promise<void>;
};

const Context = createContext<BotState | null>(null);

type Props = PropsWithChildren<{ transport?: typeof fetch; now?: () => number }>;

export function BotProvider({ children, transport, now = Date.now }: Props) {
  const [phase, setPhase] = useState<BotPhase>("loading");
  const [config, setConfig] = useState<BotConfig | null>(null);
  const [status, setStatus] = useState<BotStatus | null>(null);
  const [positions, setPositions] = useState<BotPosition[]>([]);
  const [events, setEvents] = useState<BotEvent[]>([]);
  const [error, setError] = useState("");
  const [lastOkAt, setLastOkAt] = useState<number | null>(null);
  const [checkedAt, setCheckedAt] = useState(() => now());
  const [since, setSince] = useState(() => now()); // bu bağlantının izlenmeye başladığı an
  // Bağlantı değişince eski isteklerin yanıtı yeni bağlantının ekranına yazılmaz.
  const generation = useRef(0);
  const lastEventId = useRef<number | null>(null);
  const busy = useRef(false);
  const ticks = useRef(0);

  const reset = useCallback(() => {
    generation.current += 1;
    lastEventId.current = null;
    ticks.current = 0;
    setStatus(null);
    setPositions([]);
    setEvents([]);
    setError("");
    setLastOkAt(null);
    setSince(now());
    setCheckedAt(now());
  }, [now]);

  // Sunucu token'ı reddetti. Render sırasında API'ye verildiği için ref'lere dokunmaz;
  // sayaçlar bir sonraki eşleştirmede reset() ile sıfırlanır.
  const revoke = useCallback(() => {
    setConfig(null);
    setPhase("revoked");
    setStatus(null);
    setPositions([]);
    setEvents([]);
    setError("");
    setLastOkAt(null);
    void clearBotConfig();
  }, []);

  const api = useMemo(
    () => createBotApi(config, transport ?? fetch, revoke),
    [config, transport, revoke],
  );

  useEffect(() => {
    let active = true;
    void loadBotConfig().then((stored) => {
      if (!active) return;
      setConfig(stored);
      setPhase((current) => (current === "loading" ? (stored ? "ready" : "unconfigured") : current));
    });
    return () => {
      active = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!config || busy.current) return;
    busy.current = true;
    const mine = generation.current;
    const withEvents = ticks.current % EVENTS_EVERY === 0;
    ticks.current += 1;
    try {
      const [nextStatus, nextPositions] = await Promise.all([api.status(), api.positions()]);
      let fresh: BotEvent[] | null = null;
      if (withEvents) {
        fresh =
          lastEventId.current === null
            ? (await api.recentEvents()).slice().reverse()
            : await api.events(lastEventId.current);
      }
      if (mine !== generation.current) return;
      setStatus(nextStatus);
      setPositions(nextPositions);
      if (fresh) {
        if (lastEventId.current === null) lastEventId.current = 0;
        const known = lastEventId.current;
        const added = fresh.filter((event) => event.id > known);
        if (added.length) {
          lastEventId.current = added[added.length - 1].id;
          setEvents((current) => [...added.slice().reverse(), ...current].slice(0, MAX_EVENTS));
        }
      }
      setError("");
      setLastOkAt(now());
    } catch (reason) {
      if (mine !== generation.current) return;
      if (reason instanceof BotError && reason.code === "UNAUTHORIZED") return; // revoke() halletti
      setError(reason instanceof Error ? reason.message : "Sunucuya ulaşılamadı.");
    } finally {
      busy.current = false;
      if (mine === generation.current) setCheckedAt(now());
    }
  }, [api, config, now]);

  useEffect(() => {
    if (phase !== "ready" || !config) return;
    let timer: ReturnType<typeof setInterval> | null = null;
    const start = () => {
      if (timer) return;
      void refresh();
      timer = setInterval(() => void refresh(), POLL_MS);
    };
    const stop = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };
    if (AppState.currentState !== "background" && AppState.currentState !== "inactive") start();
    const listener = AppState.addEventListener("change", (next) => {
      if (next === "active") start();
      else stop();
    });
    return () => {
      stop();
      listener.remove();
    };
  }, [phase, config, refresh]);

  const pair = useCallback(
    async (origin: string, code: string) => {
      const next = await pairBot(origin, code, transport ?? fetch);
      await saveBotConfig(next);
      reset();
      setConfig(next);
      setPhase("ready");
    },
    [reset, transport],
  );

  const disconnect = useCallback(async () => {
    reset();
    setConfig(null);
    setPhase("unconfigured");
    await clearBotConfig();
  }, [reset]);

  const heartbeatStale = useMemo(() => {
    if (phase !== "ready") return false;
    // 1) Sunucu 5 dakikadır yanıt vermiyor.
    if (checkedAt - (lastOkAt ?? since) > STALE_SECONDS * 1000) return true;
    if (!status) return false;
    // 2) Sunucu yanıt veriyor ama botun döngüsü durmuş. Telefon saati yanlış olabileceği için
    //    sunucunun kendi saati esas alınır.
    if (status.heartbeat_at === null) return true;
    const serverNow = status.server_time ?? (lastOkAt ?? checkedAt) / 1000;
    return serverNow - status.heartbeat_at > STALE_SECONDS;
  }, [phase, lastOkAt, since, checkedAt, status]);

  const value = useMemo(
    () => ({
      phase,
      config,
      status,
      positions,
      events,
      error,
      heartbeatStale,
      lastOkAt,
      api,
      pair,
      disconnect,
      refresh,
    }),
    [phase, config, status, positions, events, error, heartbeatStale, lastOkAt, api, pair, disconnect, refresh],
  );
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useBot(): BotState {
  const value = useContext(Context);
  if (!value) throw new Error("useBot, BotProvider içinde kullanılmalı");
  return value;
}
