// Trade bot API yanıtlarının (trade-bot/tradebot/api/routes.py) birebir karşılığı.
export type BotConfig = { origin: string; token: string; pairedAt: number };

export type BotHealth = {
  status: "ok" | "stale";
  last_scan_at: number | null;
  heartbeat_at: number | null;
  stream_connected: boolean;
  halted: boolean;
};

export type BotStatus = {
  currency: string | null;
  balance: number | null;
  equity: number | null;
  margin_free: number | null;
  pnl_today: { bot: number; manual: number; total: number };
  open_bot: number;
  open_manual: number;
  halted: boolean;
  halt_reason: string | null;
  stopped: boolean;
  dry_run: boolean;
  start_capital: number | null;
  last_scan_at: number | null;
  heartbeat_at: number | null;
  stream_connected: boolean;
  started: boolean;
  server_time?: number;
};

export type BotPosition = {
  position_id: string;
  origin: "bot" | "manual";
  symbol: string;
  side: "BUY" | "SELL";
  volume: number;
  initial_volume: number | null;
  entry: number;
  sl: number | null;
  tp1: number | null;
  tp2: number | null;
  strategy_id: string | null;
  opened_at: number;
  manage: boolean;
  user_sl_override: boolean;
  be_done: boolean;
  partial_done: boolean;
  realized_pnl: number;
  price: number | null;
  unrealized_pnl: number | null;
  r_multiple: number | null;
};

export type BotEvent = {
  id: number;
  at: number;
  level: "info" | "warning" | "error" | string;
  kind: string;
  message: string;
  data: Record<string, unknown> | null;
};

export type PositionPatch = { sl?: number; tp?: number; manage?: boolean };

export type Totals = { pnl: number; trades: number; wins: number; win_rate: number | null };
export type Breakdown = Record<string, { pnl: number; trades: number; wins: number }>;
export type ReportPeriod = "day" | "week" | "month";
export type BotReport = {
  period: ReportPeriod;
  totals: { bot: Totals; manual: Totals; all: Totals };
  periods: { bot: { period: string; pnl: number }[]; manual: { period: string; pnl: number }[]; all: { period: string; pnl: number }[] };
  max_drawdown: { bot: number; manual: number; all: number };
  by_strategy: Breakdown;
  by_symbol: Breakdown;
  history: {
    position_id: string;
    origin: "bot" | "manual";
    symbol: string;
    side: "BUY" | "SELL";
    entry: number;
    close_price: number | null;
    opened_at: number;
    closed_at: number | null;
    pnl: number;
    strategy_id: string | null;
  }[];
};
export type ShadowStats = { trades: number; wins: number; win_rate: number | null; avg_r: number | null };
export type StrategyMode = "live" | "shadow" | "off";
export type BotStrategy = {
  strategy_id: string;
  source: "v9" | "custom";
  mode: StrategyMode;
  paused: boolean;
  shadow: ShadowStats;
  can_go_live: boolean;
  live_blocker: string | null;
};
export type BotSettings = {
  risk: { risk_pct: number; max_open_bot: number; daily_loss_pct: number; total_loss_pct: number; [key: string]: unknown };
  news: { enabled: boolean; window_minutes: number };
  fusion: { enabled: boolean; min_score: number; mid_score: number; high_score: number; [key: string]: unknown };
  dry_run: boolean;
  strategy_modes: Record<string, StrategyMode>;
  [key: string]: unknown;
};
export type BotSymbol = {
  symbol: string;
  kind: string;
  open: boolean;
  quoted: boolean;
  bid: number | null;
  ask: number | null;
  digits: number;
  tick_size: number;
  volume_min: number;
  volume_step: number;
  volume_max: number;
};
export type TradeRequest = {
  symbol: string;
  side: "BUY" | "SELL";
  sl_distance: number;
  tp_distance?: number;
  lots?: number;
};
export type TradePreview = {
  symbol: string;
  side: "BUY" | "SELL";
  entry: number;
  sl: number;
  tp: number | null;
  lots: number;
  suggested_lots: number;
  loss: number;
  profit: number | null;
  loss_pct: number | null;
  rr: number | null;
  risk_pct: number;
  currency: string;
  volume_min: number;
  volume_step: number;
  volume_max: number;
  warnings: string[];
};
export type TradeResult = { order: string; state: string | null; lots: number; sl: number; tp: number | null; duplicate?: boolean };
