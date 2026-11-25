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
