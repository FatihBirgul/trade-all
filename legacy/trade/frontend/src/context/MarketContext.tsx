import React, { createContext, useContext, useEffect, useState } from "react";

import { Api, Market } from "@/src/api/client";
import { storage } from "@/src/utils/storage";

interface MarketContextValue {
  assets: { symbol: string; base: string; quote: string; name: string }[];
  timeframes: string[];
  defaultTimeframe: string;
  selectedSymbol: string;
  setSelectedSymbol: (s: string) => void;
  config: any;
  configReady: boolean;
  watchlist: string[];
  toggleWatch: (symbol: string) => void;
  isWatched: (symbol: string) => boolean;
}

const MarketContext = createContext<MarketContextValue | undefined>(undefined);

const FALLBACK_ASSETS = [
  { symbol: "BTCUSDT", base: "BTC", quote: "USDT", name: "Bitcoin" },
  { symbol: "ETHUSDT", base: "ETH", quote: "USDT", name: "Ethereum" },
  { symbol: "SOLUSDT", base: "SOL", quote: "USDT", name: "Solana" },
];

const STORE_KEY = "market_ai.selected_symbol";
const WATCH_KEY = "market_ai.watchlist";

export function MarketProvider({ children }: { children: React.ReactNode }) {
  const [assets, setAssets] = useState(FALLBACK_ASSETS);
  const [timeframes, setTimeframes] = useState<string[]>(["15m", "1H", "4H", "1D"]);
  const [defaultTimeframe, setDefaultTimeframe] = useState("4H");
  const [selectedSymbol, setSelectedSymbolState] = useState("BTCUSDT");
  const [config, setConfig] = useState<any>(null);
  const [configReady, setConfigReady] = useState(false);
  const [watchlist, setWatchlist] = useState<string[]>([]);

  useEffect(() => {
    (async () => {
      const saved = await storage.getItem<string>(STORE_KEY, "");
      if (saved) setSelectedSymbolState(saved);
      const savedWatch = await storage.getItem<string[]>(WATCH_KEY, []);
      if (Array.isArray(savedWatch)) setWatchlist(savedWatch);
      try {
        const cfg: any = await Api.config();
        setConfig(cfg);
        if (cfg.assets?.length) setAssets(cfg.assets);
        if (cfg.timeframes?.length) setTimeframes(cfg.timeframes);
        if (cfg.default_timeframe) setDefaultTimeframe(cfg.default_timeframe);
      } catch {
        // keep fallbacks; screens surface their own errors
      } finally {
        setConfigReady(true);
      }
    })();
  }, []);

  const setSelectedSymbol = (s: string) => {
    setSelectedSymbolState(s);
    storage.setItem(STORE_KEY, s);
  };

  const toggleWatch = (symbol: string) => {
    setWatchlist((prev) => {
      const next = prev.includes(symbol) ? prev.filter((s) => s !== symbol) : [...prev, symbol];
      storage.setItem(WATCH_KEY, next);
      return next;
    });
  };

  const isWatched = (symbol: string) => watchlist.includes(symbol);

  return (
    <MarketContext.Provider
      value={{
        assets,
        timeframes,
        defaultTimeframe,
        selectedSymbol,
        setSelectedSymbol,
        config,
        configReady,
        watchlist,
        toggleWatch,
        isWatched,
      }}
    >
      {children}
    </MarketContext.Provider>
  );
}

export function useMarket() {
  const ctx = useContext(MarketContext);
  if (!ctx) throw new Error("useMarket must be used within MarketProvider");
  return ctx;
}
