import React, {
  createContext,
  useContext,
  useState,
  type PropsWithChildren,
  useMemo,
  useEffect,
  useRef,
  useCallback,
} from "react";
import * as SecureStore from "expo-secure-store";
import { AppState, Platform } from "react-native";
import { userErrorText } from "./domain/presentation";
import { renewConnection } from "./api/renewal";
import { randomToken } from "./api/randomToken";
import { ApiError } from "./api/client";
import { mobileSession, type MobileSession } from "./api/gateway";
import { gatewayOrigin } from "./domain/safety";
import type { components } from "./api/schema";
import { createApi, type GatewayConfig } from "./api/client";
import type { Analysis, Account } from "./domain/safety";
import type { ConnectionPhase } from "./domain/connection";
type State = {
  connectionPhase: ConnectionPhase;
  lastVerifiedAt: number | null;
  uiMode: "basic" | "pro";
  setUiMode: (value: "basic" | "pro") => Promise<void>;
  mode: "demo" | "live";
  setMode: (m: "demo" | "live") => void;
  gatewayVerified: boolean;
  sessionInfo: MobileSession | null;
  connectionError: string;
  connectionErrorCode: string | null;
  connectionKey: number;
  config: GatewayConfig;
  configure: (
    c: GatewayConfig,
  ) => Promise<components["schemas"]["HealthResponse"]>;
  disconnect: () => Promise<void>;
  reconnect: () => Promise<components["schemas"]["HealthResponse"]>;
  renewing: boolean;
  api: ReturnType<typeof createApi>;
  history: Analysis[];
  addAnalysis: (a: Analysis) => void;
  paused: boolean;
  setPaused: (v: boolean) => void;
  watchlist: string[];
  addWatch: (s: string) => void;
  lastTick: number | null;
  setLastTick: (v: number) => void;
  account: Account;
  setAccount: (a: Account) => void;
};
const Context = createContext<State | null>(null);
export function AppProvider({ children }: PropsWithChildren) {
  const [uiMode, setExperience] = useState<"basic" | "pro">("basic");
  const uiRevision = useRef(0);
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [gatewayVerified, setGatewayVerified] = useState(false);
  const [sessionInfo, setSessionInfo] = useState<MobileSession | null>(null);
  const [connectionError, setConnectionError] = useState("");
  const [connectionErrorCode, setConnectionErrorCode] = useState<string | null>(
    null,
  );
  const [connectionPhase, setConnectionPhase] =
    useState<ConnectionPhase>("unconfigured");
  const [lastVerifiedAt, setLastVerifiedAt] = useState<number | null>(null);
  const activeSession = useRef("");
  const configureRef = useRef<
    | ((c: GatewayConfig) => Promise<components["schemas"]["HealthResponse"]>)
    | null
  >(null);
  const retryCount = useRef(0);
  const [connectionKey, setConnectionKey] = useState(0);
  const [config, setConfig] = useState<GatewayConfig>({
    origin: "",
    session: "",
  });
  const [renewing, setRenewing] = useState(false);
  const reconnectRef = useRef<
    (() => Promise<components["schemas"]["HealthResponse"]>) | null
  >(null);
  const flight = useRef<{
    scope: string;
    request: Promise<components["schemas"]["HealthResponse"]>;
  } | null>(null);
  const [history, setHistory] = useState<Analysis[]>([]);
  const [paused, setPaused] = useState(true);
  const [watchlist, setWatches] = useState(["BTCUSDT"]);
  const [lastTick, setLastTick] = useState<number | null>(null);
  const [account, setAccount] = useState<Account>("AUTO");
  const revision = useRef(0);
  const storageQueue = useRef(Promise.resolve());
  function persist(write: () => Promise<void>) {
    const next = storageQueue.current.catch(() => {}).then(write);
    storageQueue.current = next;
    return next;
  }
  useEffect(() => {
    let active = true;
    const revision = uiRevision.current;
    const load = (async () => {
      try {
        return Platform.OS === "web"
          ? typeof localStorage !== "undefined"
            ? localStorage.getItem("trade_ui_mode")
            : null
          : await SecureStore.getItemAsync("trade_ui_mode");
      } catch {
        return null;
      }
    })();
    load
      .then((value) => {
        if (
          active &&
          uiRevision.current === revision &&
          (value === "pro" || value === "basic")
        )
          setExperience(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  async function setUiMode(value: "basic" | "pro") {
    const revision = ++uiRevision.current;
    if (Platform.OS === "web") {
      if (typeof localStorage !== "undefined")
        localStorage.setItem("trade_ui_mode", value);
    } else
      await persist(() => SecureStore.setItemAsync("trade_ui_mode", value));
    if (uiRevision.current === revision) setExperience(value);
  }
  const handleUnauthorized = useCallback((expectedSession?: string) => {
    if (expectedSession && activeSession.current !== expectedSession) return;
    activeSession.current = "";
    revision.current += 1;
    setConnectionPhase("revoked");
    setConnectionErrorCode("UNAUTHORIZED");
    setGatewayVerified(false);
    setSessionInfo(null);
    setConnectionKey((v) => v + 1);
    setConnectionError(
      "Mobil oturum reddedildi veya sonlandırıldı. CANLI erişimi kapalı; Ayarlar’dan yeniden eşleştirin.",
    );
  }, []);
  const api = useMemo(
    () =>
      createApi(
        gatewayVerified
          ? { ...config, scopes: sessionInfo?.scopes }
          : { origin: "", session: "" },
        fetch,
        // eslint-disable-next-line react-hooks/refs -- Deferred transport callback; never invoked by createApi during render.
        () => handleUnauthorized(config.session),
        {
          profileScannerEnabled:
            sessionInfo?.capabilities?.includes("profile-scanner-v1") === true,
        },
      ),
    [config, gatewayVerified, handleUnauthorized, sessionInfo],
  );
  useEffect(() => () => api.dispose(), [api]);
  useEffect(() => {
    if (Platform.OS === "web") return;
    let active = true;
    const initialRevision = revision.current;
    SecureStore.getItemAsync("mobile_gateway")
      .then((raw) => {
        if (!raw || !active || revision.current !== initialRevision) return;
        const c = JSON.parse(raw) as GatewayConfig;
        if (typeof c.origin === "string" && typeof c.session === "string") {
          setConfig(c);
          setLastVerifiedAt(
            Number.isSafeInteger(c.lastVerifiedAt) ? c.lastVerifiedAt! : null,
          );
          void configureRef.current?.(c).catch(() => {});
        }
      })
      .catch(() => {
        /* Fail closed: an unreadable credential never enables live access. */
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!sessionInfo || !gatewayVerified) return;
    const canRefresh =
      !!config.refresh &&
      (sessionInfo.renewal_expires_at_ms ?? 0) >
        sessionInfo.expires_at_ms + 60000;
    const timer = setTimeout(
      () => {
        if (canRefresh) void reconnectRef.current?.().catch(() => {});
        else handleUnauthorized();
      },
      Math.max(
        0,
        sessionInfo.expires_at_ms - Date.now() - (canRefresh ? 300000 : 0),
      ),
    );
    return () => clearTimeout(timer);
  }, [sessionInfo, config.refresh, gatewayVerified, handleUnauthorized]);
  useEffect(() => {
    const listener = AppState.addEventListener("change", (state) => {
      if (
        state === "active" &&
        config.session &&
        connectionPhase !== "revoked" &&
        connectionPhase !== "checking" &&
        (!gatewayVerified ||
          (sessionInfo?.expires_at_ms ?? 0) - Date.now() < 300000)
      )
        void reconnectRef.current?.().catch(() => {});
    });
    return () => listener.remove();
  }, [config.session, connectionPhase, gatewayVerified, sessionInfo]);
  async function configure(candidate: GatewayConfig) {
    const attempt = ++revision.current;
    setConnectionKey((v) => v + 1);
    setSessionInfo(null);
    setConnectionError("");
    setConnectionErrorCode(null);
    setGatewayVerified(false);
    activeSession.current = "";
    setConnectionPhase("checking");
    try {
      let c: GatewayConfig = {
        ...candidate,
        origin: gatewayOrigin(candidate.origin),
        session: candidate.session.trim(),
      };
      if (!c.session || /[\r\n]/.test(c.session))
        throw new Error("Geçerli bir mobil oturum belirteci girin.");
      const saveCredential = async (value: GatewayConfig) => {
        if (attempt !== revision.current) throw new ApiError("SESSION_CHANGED");
        if (Platform.OS !== "web")
          await persist(async () => {
            if (attempt !== revision.current)
              throw new ApiError("SESSION_CHANGED");
            await SecureStore.setItemAsync(
              "mobile_gateway",
              JSON.stringify(value),
            );
          });
        if (attempt !== revision.current) throw new ApiError("SESSION_CHANGED");
        setConfig(value);
      };
      // Preserve a newly paired grant even if the backend health probe is offline.
      if (c.refresh) await saveCredential(c);
      let metadata: MobileSession;
      try {
        if (c.pendingRenewal) throw new ApiError("UNAUTHORIZED");
        metadata = await mobileSession(c);
        if (c.refresh && metadata.expires_at_ms - Date.now() <= 300000)
          throw new ApiError("UNAUTHORIZED");
      } catch (error) {
        if (
          !c.refresh ||
          !(error instanceof ApiError) ||
          error.code !== "UNAUTHORIZED"
        )
          throw error;
        setRenewing(true);
        try {
          const renewed = await renewConnection(c, saveCredential, randomToken);
          c = renewed.config;
          metadata = renewed.metadata;
        } finally {
          if (attempt === revision.current) setRenewing(false);
        }
      }
      const health = await createApi(c).health();
      if (health.real_execution !== false || health.data_mode !== "live")
        throw new Error(
          "Gateway canlı veri / sanal işlem sözleşmesini doğrulamadı.",
        );
      if (attempt !== revision.current)
        throw new Error("Bağlantı testi iptal edildi.");
      c = { ...c, lastVerifiedAt: Date.now() };
      await saveCredential(c);
      activeSession.current = c.session;
      retryCount.current = 0;
      setConnectionPhase("ready");
      setLastVerifiedAt(c.lastVerifiedAt!);
      setConfig(c);
      setSessionInfo(metadata);
      if (!metadata.accounts.includes(account))
        setAccount(metadata.accounts[0]);
      setConnectionError("");
      setConnectionErrorCode(null);
      setGatewayVerified(true);
      setConnectionKey((value) => value + 1);
      return health;
    } catch (error) {
      if (attempt === revision.current) {
        setConnectionErrorCode(error instanceof ApiError ? error.code : null);
        setConnectionPhase(
          error instanceof ApiError &&
            ["UNAUTHORIZED", "LOCAL_PAIR_REQUIRED"].includes(error.code)
            ? "revoked"
            : "offline",
        );
        setConnectionError(
          userErrorText(
            error,
            "Kayıtlı bağlantı doğrulanamadı. Yeniden bağlan ile kontrol edin.",
          ),
        );
      }
      throw error;
    }
  }
  async function reconnect() {
    const scope = [
      config.origin,
      config.session,
      config.refresh,
      config.deviceId,
    ].join("|");
    if (flight.current?.scope === scope) return flight.current.request;
    const attempt = revision.current + 1;
    const request = configure(config);
    flight.current = { scope, request };
    try {
      return await request;
    } catch (error) {
      if (revision.current === attempt)
        setConnectionError(
          userErrorText(
            error,
            "Bağlantı yenilenemedi. Yeniden bağlan ile kontrol edin.",
          ),
        );
      throw error;
    } finally {
      if (flight.current?.request === request) flight.current = null;
    }
  }
  useEffect(() => {
    reconnectRef.current = reconnect;
    configureRef.current = configure;
  });
  useEffect(() => {
    if (
      Platform.OS === "web" ||
      connectionPhase !== "offline" ||
      !config.session
    )
      return;
    const delay = Math.min(
      15000 * 2 ** Math.min(retryCount.current++, 5),
      300000,
    );
    const timer = setTimeout(() => {
      if (
        AppState.currentState !== "background" &&
        AppState.currentState !== "inactive"
      )
        void reconnectRef.current?.().catch(() => {});
    }, delay);
    return () => clearTimeout(timer);
  }, [connectionPhase, config.session]);
  async function disconnect() {
    ++revision.current;
    activeSession.current = "";
    setConnectionPhase("unconfigured");
    setLastVerifiedAt(null);
    retryCount.current = 0;
    setRenewing(false);
    setConnectionKey((v) => v + 1);
    setSessionInfo(null);
    setConnectionError("");
    setConnectionErrorCode(null);
    setMode("demo");
    setGatewayVerified(false);
    setConfig({ origin: "", session: "" });
    if (Platform.OS !== "web")
      await persist(() => SecureStore.deleteItemAsync("mobile_gateway"));
  }
  // No automatic live restoration. A new launch always begins in DEMO.
  return (
    <Context.Provider
      value={{
        connectionPhase,
        lastVerifiedAt,
        uiMode,
        setUiMode,
        mode,
        setMode: (next) =>
          setMode(next === "live" && !gatewayVerified ? "demo" : next),
        gatewayVerified,
        sessionInfo,
        connectionError,
        connectionErrorCode,
        connectionKey,
        config,
        configure,
        disconnect,
        reconnect,
        renewing,
        api,
        history,
        addAnalysis: (a) =>
          setHistory((h) => [
            a,
            ...h.filter((x) => x.analysis_id !== a.analysis_id),
          ]),
        paused,
        setPaused,
        watchlist,
        addWatch: (s) =>
          setWatches((w) =>
            w.includes(s) ? w : w.length < 10 ? [...w, s] : w,
          ),
        lastTick,
        setLastTick,
        account,
        setAccount,
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useApp() {
  const context = useContext(Context);
  if (!context) throw new Error("AppProvider missing");
  return context;
}
