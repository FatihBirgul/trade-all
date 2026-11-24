/** Synthetic V5 response shapes only; never broker approval or market evidence. */
export function response(overrides = {}) {
  const stamp = Math.floor(Date.now()/1000)
  const symbol=overrides.symbol??'XAUUSD'
  const aliases={XAUUSD:'XAUUSDc',EURUSD:'EURUSDc',GBPUSD:'GBPUSDc',USDJPY:'USDJPYc'}
  return {
    schema_version:'forex-analysis-5',engine_version:'forex-unified-5.1',symbol:'XAUUSD',timeframe:'M5',provider:'fixture-test-only',
    historical_session_evidence:{status:'HISTORICAL_SOURCE_VERIFIED',historical_gap_authorized:true,cross_source_reconciled:true,evidence_ids:['SYNTHETIC-UNIT-TEST-NOT-BROKER-EVIDENCE']},
    final_decision:'BUY_CANDIDATE',legacy_signal:'BUY',as_of_utc:new Date().toISOString(),snapshot_id:'a'.repeat(64),
    data_status:'OK',trading_eligibility:'NOT_EVALUATED',market_status:'OPEN',market_data_account_mode:'REAL',
    analysis_mode:'MANUAL_SIMULATION',execution_permission:false,risk_balance_source:'HYPOTHETICAL_CAPITAL',
    account_currency:'USC',broker_symbol:aliases[symbol],integration_status:'PRIVATE_PARTIAL',decision_reasons:['trend=BUY','confirmations=BUY'],
    entry_zone:{low:2000,high:2000},stop_loss:1990,take_profit_1:2020,take_profit_2:2030,risk_reward:2,lot_size:.05,risk_amount:50,
    risk_policy:{decision:'PASS'},spread:.2,broker_contract:{status:'CURRENT_MT5_OBSERVED',historical_status:'UNVERIFIED',missing_fields:[],conflicting_fields:[],fields:{digits:{value:3,trust:'CURRENT_MT5_OBSERVED'},symbol:{value:symbol,trust:'CURRENT_MT5_OBSERVED'},broker_symbol:{value:aliases[symbol],trust:'CURRENT_MT5_OBSERVED'},account_currency:{value:'USC',trust:'CURRENT_MT5_OBSERVED'}}},
    spread_status:{decision:'PASS',policy_status:'OPERATOR_APPROVED',observed:{price:.2,points:200,symbol_spread_points:199},max_allowed_price:.3,reasons:[]},
    indicators:{ema20:1998,ema50:1995,ema200:1980,rsi14:55,atr14:2,macd_histogram:0},warnings:[],
    chart_patterns:{status:'AVAILABLE',role:'DESCRIPTIVE_ONLY',version:'v2-chart-pivot-descriptive-1',source_sha256:'b'.repeat(64),items:[{name:'Double Top',timeframe:'M5',direction:'BEARISH',first_known_utc:stamp-300,formed_at_utc:stamp-1200,confirmation_state:'STRUCTURAL_CONFIRMED',age_bars:4,source_sha256:'b'.repeat(64)}]},
    candlestick_patterns:{status:'AVAILABLE',role:'DESCRIPTIVE_ONLY',version:'v2-candlestick-bridge-1',items:[{name:'Doji',direction:'NEUTRAL',known_at_utc:stamp-300,confirmed:true,age_bars:1}]},
    ...overrides,
  }
}
