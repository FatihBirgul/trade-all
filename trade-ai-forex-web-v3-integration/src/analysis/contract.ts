/** V5 read-only wire contract. Missing safety fields stay unknown. */
export const symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY'] as const
export const timeframes = ['M5', 'M15', 'M30', 'H1', 'H4', 'D1'] as const
export type SymbolName = typeof symbols[number]
export type Timeframe = typeof timeframes[number]
export type RecordValue = Record<string, unknown>
const decisions = ['BUY_CANDIDATE', 'SELL_CANDIDATE', 'WAIT', 'NO_TRADE', 'INSUFFICIENT_DATA', 'MARKET_CLOSED', 'STALE_DATA', 'PROVIDER_UNAVAILABLE']
export type Pattern = {
  name: string; direction?: string; timeframe?: string; first_known_utc?: number | null
  known_at_utc?: number; formed_at_utc?: number; confirmation_state?: string
  confirmed?: boolean; age_bars?: number; source_sha256?: string; integration_status?: string
}
export type PatternContext = {
  status?: string; role?: string; source_commit?: string; source_sha256?: string
  version?: string; items: Pattern[]; sourceMismatch?: boolean
}
export type Analysis = {
  schema_version: 'forex-analysis-5'; symbol: SymbolName; timeframe: Timeframe
  provider: string; final_decision: string; legacy_signal?: string; as_of_utc: string
  data_status: string; trading_eligibility: string; decision_reasons: string[]
  snapshot_id?: string | null; account_currency?: string | null; broker_symbol?: string | null
  market_status?: string; market_data_account_mode?: string; analysis_mode?: string
  execution_permission?: boolean; risk_balance_source?: string; integration_status?: string
  entry_zone: {low: number; high: number} | null; stop_loss: number | null
  take_profit_1: number | null; take_profit_2: number | null; risk_reward: number | null
  lot_size: number | null; risk_amount: number | null; spread?: number | null
  broker_contract?: RecordValue; spread_status?: RecordValue; risk_policy?: RecordValue
  historical_session_evidence?: RecordValue
  indicators?: RecordValue; private_extension?: RecordValue; source_versions?: RecordValue
  chart_patterns: PatternContext | null; candlestick_patterns: PatternContext | null
  warnings: string[]
}
export const isRecord = (x: unknown): x is RecordValue => typeof x === 'object' && x !== null && !Array.isArray(x)
export const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x)
export const positive = (x: unknown): x is number => finite(x) && x > 0
const text = (x: unknown): x is string => typeof x === 'string' && x.length <= 4000
const strings = (x: unknown): x is string[] => Array.isArray(x) && x.length <= 100 && x.every(text)
const optionalText = (x: unknown) => text(x) ? x : undefined
const record = (x: unknown) => isRecord(x) ? x : undefined
const nullableNumber = (x: unknown) => finite(x) ? x : null
export const utcTime = (x: unknown) => text(x) && /(?:Z|[+-]\d{2}:\d{2})$/.test(x) && Number.isFinite(Date.parse(x))

function patterns(raw: unknown): PatternContext | null {
  if (!isRecord(raw)) return null
  const source = optionalText(raw.source_sha256)
  const items: Pattern[] = []
  let mismatch = false
  if (Array.isArray(raw.items)) {
    for (const item of raw.items.slice(0, 20)) {
      if (!isRecord(item) || !text(item.name) || !item.name) continue
      if (source && item.source_sha256 !== undefined && item.source_sha256 !== source) { mismatch = true; continue }
      items.push({name: item.name, direction: optionalText(item.direction), timeframe: optionalText(item.timeframe),
        first_known_utc: finite(item.first_known_utc) ? item.first_known_utc : null,
        known_at_utc: finite(item.known_at_utc) ? item.known_at_utc : undefined,
        formed_at_utc: finite(item.formed_at_utc) ? item.formed_at_utc : undefined,
        confirmation_state: optionalText(item.confirmation_state), confirmed: typeof item.confirmed === 'boolean' ? item.confirmed : undefined,
        age_bars: finite(item.age_bars) && item.age_bars >= 0 ? item.age_bars : undefined,
        source_sha256: optionalText(item.source_sha256), integration_status: optionalText(item.integration_status)})
    }
  }
  return {status: optionalText(raw.status), role: optionalText(raw.role), version: optionalText(raw.version),
    source_commit: optionalText(raw.source_commit), source_sha256: source, items, sourceMismatch: mismatch}
}

export function parseAnalysis(raw: unknown, symbol: string, timeframe: string): Analysis {
  if (!isRecord(raw) || raw.schema_version !== 'forex-analysis-5' ||
      raw.symbol !== symbol || raw.timeframe !== timeframe ||
      !symbols.includes(raw.symbol as SymbolName) || !timeframes.includes(raw.timeframe as Timeframe) ||
      !text(raw.provider) || !['mt5', 'fixture-test-only'].includes(raw.provider) ||
      !text(raw.final_decision) || !decisions.includes(raw.final_decision) ||
      !text(raw.data_status) || !text(raw.trading_eligibility) || !strings(raw.decision_reasons) || !utcTime(raw.as_of_utc)) {
    throw new Error('Analiz yanıtının şeması veya seçili sembol/zaman kimliği uyuşmuyor. Eski sonuç gösterilmiyor.')
  }
  const entry = isRecord(raw.entry_zone) && positive(raw.entry_zone.low) && positive(raw.entry_zone.high)
    ? {low: raw.entry_zone.low, high: raw.entry_zone.high} : null
  return {schema_version: 'forex-analysis-5', symbol: raw.symbol as SymbolName, timeframe: raw.timeframe as Timeframe,
    provider: raw.provider, final_decision: raw.final_decision, legacy_signal: optionalText(raw.legacy_signal),
    as_of_utc: raw.as_of_utc as string, data_status: raw.data_status, trading_eligibility: raw.trading_eligibility,
    decision_reasons: raw.decision_reasons, snapshot_id: optionalText(raw.snapshot_id),
    account_currency: optionalText(raw.account_currency), broker_symbol: optionalText(raw.broker_symbol),
    market_status: optionalText(raw.market_status), market_data_account_mode: optionalText(raw.market_data_account_mode),
    analysis_mode: optionalText(raw.analysis_mode), execution_permission: typeof raw.execution_permission === 'boolean' ? raw.execution_permission : undefined,
    risk_balance_source: optionalText(raw.risk_balance_source), integration_status: optionalText(raw.integration_status), entry_zone: entry,
    stop_loss: nullableNumber(raw.stop_loss), take_profit_1: nullableNumber(raw.take_profit_1), take_profit_2: nullableNumber(raw.take_profit_2),
    risk_reward: nullableNumber(raw.risk_reward), lot_size: nullableNumber(raw.lot_size), risk_amount: nullableNumber(raw.risk_amount),
    spread: nullableNumber(raw.spread), broker_contract: record(raw.broker_contract), spread_status: record(raw.spread_status),
    risk_policy: record(raw.risk_policy), indicators: record(raw.indicators), private_extension: record(raw.private_extension),
    source_versions: record(raw.source_versions), historical_session_evidence: record(raw.historical_session_evidence),
    chart_patterns: patterns(raw.chart_patterns), candlestick_patterns: patterns(raw.candlestick_patterns),
    warnings: strings(raw.warnings) ? raw.warnings : []}
}

export function capitalInput(capital: string, risk: string) {
  const valid = /^\d+(?:[.,]\d+)?$/
  const amount = Number(capital.replace(',', '.')); const percent = Number(risk.replace(',', '.'))
  if (!valid.test(capital.trim()) || !positive(amount) || amount > 1e9 || !valid.test(risk.trim()) || !positive(percent) || percent > 5)
    throw new Error('Varsayımsal sermayeyi USC olarak girin. Risk oranı %0’dan büyük, en fazla %5 olmalı.')
  return {hypothetical_capital: amount, hypothetical_currency: 'USC' as const, risk_pct: percent}
}

export function freshness(a: Analysis, now = Date.now()) {
  const age = now - Date.parse(a.as_of_utc)
  return age < -5000 ? 'FUTURE' : age > 120000 ? 'STALE' : 'FRESH'
}

export function planVisibility(a: Analysis, now = Date.now()) {
  const buy = a.final_decision === 'BUY_CANDIDATE'; const sell = a.final_decision === 'SELL_CANDIDATE'
  const candidate = buy || sell
  const blockers: string[] = []
  if (!candidate) blockers.push('Motor teknik BUY/SELL adayı üretmedi.')
  if (freshness(a, now) !== 'FRESH' || a.data_status !== 'OK') blockers.push('Analiz verisi güncel ve eksiksiz değil.')
  if (!['OPEN', 'CLOSING_SOON'].includes(a.market_status ?? '')) blockers.push('Broker seansı yeni plan için doğrulanmadı.')
  const contract = a.broker_contract
  if (contract?.status !== 'CURRENT_MT5_OBSERVED' || !strings(contract.missing_fields) || contract.missing_fields.length ||
      !strings(contract.conflicting_fields) || contract.conflicting_fields.length) blockers.push('Güncel broker sözleşmesi eksik veya çelişkili.')
  const fields = isRecord(contract?.fields) ? contract.fields : undefined
  const consistentIdentity = Object.entries({symbol:a.symbol, broker_symbol:a.broker_symbol, account_currency:a.account_currency}).every(([key,value]) => {
    const field = isRecord(fields?.[key]) ? fields[key] : undefined
    return field?.trust === 'CURRENT_MT5_OBSERVED' && field.value === value && value !== undefined
  })
  if (!consistentIdentity) blockers.push('Broker alanlarının sembol/para birimi kimliği analiz yanıtıyla eşleşmiyor.')
  const historical = a.historical_session_evidence
  if (historical?.status !== 'HISTORICAL_SOURCE_VERIFIED' || historical.historical_gap_authorized !== true ||
      historical.cross_source_reconciled !== true || !strings(historical.evidence_ids) || !historical.evidence_ids.length)
    blockers.push('BLOCKED_BY_EXTERNAL_EVIDENCE · Tarihsel Exness seans kanıtı doğrulanmadı; plan gösterilmiyor.')
  const spread = a.spread_status; const observed = isRecord(spread?.observed) ? spread.observed : undefined
  if (spread?.decision !== 'PASS' || spread.policy_status !== 'OPERATOR_APPROVED' || !positive(spread.max_allowed_price) ||
      !positive(observed?.price) || observed.price > spread.max_allowed_price) blockers.push('Onaylı spread politikası sağlanmadı.')
  if (a.execution_permission !== false || a.analysis_mode !== 'MANUAL_SIMULATION') blockers.push('Salt okunur simülasyon sözleşmesi doğrulanmadı.')
  if (a.market_data_account_mode !== 'REAL') blockers.push('REAL salt okunur piyasa kaynağı doğrulanmadı.')
  if (!a.snapshot_id || !/^[0-9a-f]{64}$/.test(a.snapshot_id) || !a.broker_symbol) blockers.push('Analiz snapshot/kaynak kimliği eksik.')
  if (a.account_currency !== 'USC' || a.risk_balance_source !== 'HYPOTHETICAL_CAPITAL') blockers.push('Varsayımsal USC sermaye kaynağı doğrulanmadı.')
  if (!['ELIGIBLE', 'NOT_EVALUATED'].includes(a.trading_eligibility)) blockers.push('Risk/işlem uygunluğu engellenmiş.')
  if (a.risk_policy?.decision !== 'PASS' || !positive(a.lot_size) || !positive(a.risk_amount)) blockers.push('Varsayımsal lot ve risk hesabı mevcut değil.')
  if (!positive(a.risk_reward)) blockers.push('Risk/ödül bilgisi mevcut değil.')
  const e = a.entry_zone
  const geometry = e && e.low <= e.high && positive(a.stop_loss) && positive(a.take_profit_1) &&
    (buy ? a.stop_loss < e.low && a.take_profit_1 > e.high : sell && a.stop_loss > e.high && a.take_profit_1 < e.low)
  if (!geometry || a.legacy_signal !== (buy ? 'BUY' : sell ? 'SELL' : 'WAIT')) blockers.push('Teknik seviyelerin yönü veya geometrisi doğrulanmadı.')
  if (a.take_profit_2 !== null && (!positive(a.take_profit_2) || !positive(a.take_profit_1) ||
      (buy ? a.take_profit_2 <= a.take_profit_1 : sell ? a.take_profit_2 >= a.take_profit_1 : true))) blockers.push('İkinci hedef yönü doğrulanmadı.')
  return {candidate, showPlan: blockers.length === 0, blockers}
}

export function explainReason(reason: string) {
  if (reason.startsWith('trend=')) return 'Teknik trend yönü: ' + reason.slice(6)
  if (reason.startsWith('confirmations=')) return 'Üst zaman dilimi yönü: ' + reason.slice(14)
  const rules: [RegExp, string][] = [
    [/missing candle.*(verified broker hours|open or unknown historical quote interval)/i, 'Geçmiş mum verilerinde boşluk var. Brokerın bu saatlerde kapalı olduğu doğrulanamadı. Bu nedenle işlem planı engellendi. Doğrulanmış seans kanıtı yok.'],
    [/missing candle|insufficient.*candle/i, 'Gerekli kapanmış mum verileri eksik.'],
    [/spread.*approval|spread.*unapproved/i, 'Maksimum spread limiti henüz onaylanmadı.'],
    [/spread.*exceed/i, 'Gözlenen spread izin verilen limiti aşıyor.'],
    [/broker market unknown/i, 'Broker seansı doğrulanmadı.'],
    [/broker market.*(closed|disabled)/i, 'Broker seansı kapalı veya yeni işlem yönleri kapalı.'],
    [/opening_soon/i, 'Broker açılışa yaklaşıyor; açık seans olarak kabul edilmedi.'],
    [/stale/i, 'Fiyat veya mum verisi güncelliğini yitirdi.'],
    [/minimum lot|minimum volume/i, 'Minimum lot varsayımsal risk bütçesini aşıyor.'],
    [/currency|conversion/i, 'Para birimi veya dönüşüm doğrulaması sağlanmadı.'],
    [/broker contract/i, 'Broker sözleşmesi doğrulanamadı veya finansal hesapla uyuşmuyor.'],
    [/opposing|conflict/i, 'Teknik kanıtlar arasında yön uyuşmazlığı var.'],
  ]
  return rules.find(([pattern]) => pattern.test(reason))?.[1] ?? `Motor gerekçesi: ${reason}`
}
