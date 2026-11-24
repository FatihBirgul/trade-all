import type { Analysis, Account, Timeframe } from "./domain/safety";
import fixture from "../docs/backend/v2_examples/wait.json";
// Static, explicitly labelled UX sample. It never masquerades as a backend result.
export function demoAnalysis(
  symbol: string,
  timeframe: Timeframe,
  account: Account,
  id: string,
): Analysis {
  return {
    ...fixture,
    analysis_id: id,
    created_at_ms: Date.now(),
    expires_at_ms: Date.now(),
    symbol,
    timeframe,
    timeframes: [timeframe],
    data_mode: "fixture",
    direction: "WAIT",
    levels: null,
    auto_order_id: null,
    risk_portfolio: account,
    price: null,
    price_time_ms: null,
    quality: { ok: false, issues: ["local_demo_no_market_data"] },
    reason: "local_demo_no_market_data",
    indicators: {},
    risk: { status: "blocked" },
    technical_methods: {},
    strategy_setups: {},
    warnings: ["Yerel DEMO örneği; piyasa verisi alınmadı."],
  } as Analysis;
}
