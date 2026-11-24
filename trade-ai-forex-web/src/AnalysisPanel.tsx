import { useEffect, useRef, useState } from 'react'
import AnalysisNewsRisk from './AnalysisNewsRisk'

type Analysis = {
  schema_version: string
  symbol: string
  timeframe: string
  provider: string
  final_decision: string
  legacy_signal: string
  decision_reasons: string[]
  data_status: string
  trading_eligibility: string
  integration_status: string
  entry_zone: { low: number; high: number; price_side?: string } | null
  stop_loss: number | null
  take_profit_1: number | null
  take_profit_2: number | null
  risk_reward: number | null
  lot_size: number | null
  risk_amount: number | null
  warnings: string[]
}

type Props = {
  symbol: string
  timeframe: string
  reportedTickTime: string | null
}

const supportedTimes = ['M5', 'M15', 'M30', 'H1', 'H4', 'D1']

function isAnalysis(value: unknown): value is Analysis {
  if (typeof value !== 'object' || value === null) return false
  const a = value as Partial<Analysis>

  return a.schema_version === 'forex-analysis-5' &&
    a.provider === 'mt5' &&
    typeof a.symbol === 'string' &&
    typeof a.timeframe === 'string' &&
    typeof a.final_decision === 'string' &&
    typeof a.data_status === 'string' &&
    typeof a.trading_eligibility === 'string' &&
    Array.isArray(a.decision_reasons) &&
    a.decision_reasons.every((x) => typeof x === 'string')
}

function positive(value: number | null | undefined): value is number {
  return typeof value === 'number' &&
    Number.isFinite(value) && value > 0
}

function approved(a: Analysis): boolean {
  const buy = a.final_decision === 'BUY_CANDIDATE'
  const sell = a.final_decision === 'SELL_CANDIDATE'

  if (!buy && !sell) return false

  const entry = a.entry_zone

  if (
    a.data_status !== 'OK' ||
    a.trading_eligibility !== 'ELIGIBLE' ||
    a.legacy_signal !== (buy ? 'BUY' : 'SELL') ||
    !entry ||
    !positive(entry.low) ||
    !positive(entry.high) ||
    entry.low > entry.high ||
    !positive(a.stop_loss) ||
    !positive(a.take_profit_1) ||
    !positive(a.lot_size) ||
    !positive(a.risk_amount)
  ) return false

  return buy
    ? a.stop_loss < entry.low && a.take_profit_1 > entry.high
    : a.stop_loss > entry.high && a.take_profit_1 < entry.low
}

export default function AnalysisPanel({
  symbol,
  timeframe,
  reportedTickTime
}: Props) {
  const [result, setResult] = useState<Analysis | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [balance, setBalance] = useState('')
  const [riskPct, setRiskPct] = useState('1')
  const pending = useRef<AbortController | null>(null)

  useEffect(() => {
    pending.current?.abort()
    setResult(null)
    setError(null)
    setLoading(false)

    return () => pending.current?.abort()
  }, [symbol, timeframe])

  const supported =
    (symbol === 'XAUUSD' || symbol === 'EURUSD') &&
    supportedTimes.includes(timeframe)

  const shown =
    result?.symbol === symbol && result.timeframe === timeframe
      ? result
      : null

  const allowed = shown ? approved(shown) : false

  const direction = allowed && shown
    ? shown.final_decision === 'BUY_CANDIDATE' ? 'BUY' : 'SELL'
    : null

  const digits = symbol === 'XAUUSD' ? 2 : 5

  const price = (value: number | null | undefined) =>
    positive(value) ? value.toFixed(digits) : '—'

  async function analyze() {
    if (!supported || loading) return

    const b = balance.trim()
    const r = riskPct.trim()
    const valid = /^\d+(?:[.,]\d+)?$/
    const balanceValue = Number(b.replace(',', '.'))
    const riskValue = Number(r.replace(',', '.'))

    if (!valid.test(b) || !valid.test(r) ||
        !Number.isFinite(balanceValue) || balanceValue <= 0 ||
        balanceValue > 1000000000 ||
        !Number.isFinite(riskValue) || riskValue <= 0 || riskValue > 5) {
      setResult(null)
      setError("Ge\u00e7erli USC bakiyesi ve %0\u0027dan b\u00fcy\u00fck, en fazla %5 risk oran\u0131 gir.")
      return
    }

    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const response = await fetch('/engine/api/v5/analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          symbol,
          timeframe,
          confirmations: ['H4'],
          require_private: false,
          hypothetical_capital: balanceValue,
          hypothetical_currency: 'USC',
          risk_pct: riskValue
        })
      })

      if (!response.ok) {
        throw new Error(`Analiz sunucusu HTTP ${response.status}`)
      }

      const value: unknown = await response.json()

      if (
        !isAnalysis(value) ||
        value.symbol !== symbol ||
        value.timeframe !== timeframe
      ) {
        throw new Error('Analiz motorundan beklenmeyen yanıt alındı')
      }

      if (!controller.signal.aborted) setResult(value)
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(
          err instanceof Error ? err.message : 'Analiz bağlantı hatası'
        )
      }
    } finally {
      if (!controller.signal.aborted) setLoading(false)
    }
  }

  const status = loading
    ? 'ANALİZ YAPILIYOR'
    : error
      ? 'ANALİZ ALINAMADI'
      : shown
        ? shown.final_decision === 'INSUFFICIENT_DATA'
          ? 'VERİ DOĞRULANAMADI'
          : shown.final_decision === 'STALE_DATA'
            ? 'VERİ GÜNCEL DEĞİL'
            : shown.final_decision === 'PROVIDER_UNAVAILABLE'
              ? 'VERİ SAĞLAYICISI YOK'
              : shown.final_decision === 'MARKET_CLOSED'
                ? 'PİYASA KAPALI'
                : shown.data_status !== 'OK'
                  ? 'VERİ DOĞRULANAMADI'
                  : direction
                    ? direction
                    : shown.trading_eligibility === 'BLOCKED'
                      ? 'İŞLEM ENGELLENDİ'
                      : shown.final_decision === 'WAIT'
                        ? 'BEKLE'
                        : shown.final_decision === 'NO_TRADE'
                          ? 'İŞLEM YOK'
                          : 'İŞLEM ONAYLANMADI'
        : 'ANALİZ BEKLENİYOR'

  const explanation = error ?? (
    !supported
      ? 'İlk sürümde XAUUSD/EURUSD ve M5-D1 analiz dilimleri desteklenir.'
      : !shown
        ? 'Gerçek V5 analizini çalıştırmak için Analiz Et butonuna bas.'
        : shown.decision_reasons.map((reason) =>
            reason === 'missing candle during open or unknown historical quote interval' ||
            reason === 'missing candle without verified broker hours'
              ? 'Geçmiş mum verilerinde boşluk var. Brokerın bu saatlerde kapalı olduğu doğrulanamadı. Bu nedenle işlem planı engellendi.'
              : reason
          ).join(' · ') ||
          (direction
            ? 'Motor aday işlem planı oluşturdu.'
            : 'Motor uygun bir işlem planı doğrulamadı.')
  )

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2 className="panel-title">Yapay Zekâ Analizi</h2>
          <div className="panel-description">
            Codex 1 · Gerçek MT5 V5 analiz motoru
          </div>
        </div>
        <span className="panel-tag waiting">REAL MT5 / SALT OKUNUR</span>
      </div>

      <div className="analysis-status" role="status" aria-live="polite">
        <div className="analysis-icon">AI</div>
        <div className="analysis-main">{status}</div>
        <div className="analysis-sub">{explanation}</div>
      </div>

      <AnalysisNewsRisk />

      <div className="risk-fields">
        <div className="risk-field">
          <label htmlFor="analysis-balance">Varsayımsal Sermaye (USC)</label>
          <input
            id="analysis-balance"
            type="text"
            inputMode="decimal"
            placeholder="?rn. 1084.14"
            value={balance}
            onChange={(e) => {
              pending.current?.abort()
              setResult(null)
              setError(null)
              setLoading(false)
              setBalance(e.target.value)
            }}
          />
        </div>
        <div className="risk-field">
          <label htmlFor="analysis-risk">Risk Oranı (%)</label>
          <input
            id="analysis-risk"
            type="text"
            inputMode="decimal"
            value={riskPct}
            onChange={(e) => {
              pending.current?.abort()
              setResult(null)
              setError(null)
              setLoading(false)
              setRiskPct(e.target.value)
            }}
          />
        </div>
      </div>

      <div className="data-row">
        <span>Enstrüman / Zaman</span>
        <strong>{symbol} / {timeframe}</strong>
      </div>

      <div className="data-row">
        <span>Motor kararı</span>
        <strong>{shown?.final_decision ?? '—'}</strong>
      </div>

      <div className="data-row">
        <span>Veri / Risk uygunluğu</span>
        <strong>
          {shown
            ? `${shown.data_status} / ${shown.trading_eligibility}`
            : '—'}
        </strong>
      </div>

      <div className="data-row">
        <span>İşlem yönü</span>
        <strong>{direction ?? '—'}</strong>
      </div>

      <div className="data-row">
        <span>Giriş bölgesi</span>
        <strong>
          {allowed && shown
            ? `${price(shown.entry_zone?.low)} – ${price(shown.entry_zone?.high)}`
            : '—'}
        </strong>
      </div>

      <div className="data-row">
        <span>Stop Loss</span>
        <strong>{allowed ? price(shown?.stop_loss) : '—'}</strong>
      </div>

      <div className="data-row">
        <span>Take Profit 1 / 2</span>
        <strong>
          {allowed && shown
            ? `${price(shown.take_profit_1)} / ${price(shown.take_profit_2)}`
            : '—'}
        </strong>
      </div>

      <div className="data-row">
        <span>Risk / Ödül</span>
        <strong>
          {allowed && positive(shown?.risk_reward)
            ? shown?.risk_reward.toFixed(2)
            : '—'}
        </strong>
      </div>

      <div className="data-row">
        <span>Lot</span>
        <strong>
          {allowed && shown?.lot_size != null
            ? shown.lot_size.toFixed(2)
            : '—'}
        </strong>
      </div>

      <div className="data-row">
        <span>Tahmini risk (hesap para birimi)</span>
        <strong>
          {allowed && shown?.risk_amount != null
            ? shown.risk_amount.toFixed(2)
            : '—'}
        </strong>
      </div>

      <div className="data-row">
        <span>MT5 bildirilen fiyat saati</span>
        <strong>{reportedTickTime ?? '—'}</strong>
      </div>

      <div className="data-row">
        <span>Motor entegrasyonu</span>
        <strong>{shown?.integration_status ?? '—'}</strong>
      </div>

      {shown && !allowed &&
        ['BUY_CANDIDATE', 'SELL_CANDIDATE'].includes(shown.final_decision) && (
          <p className="analysis-sub">
            Aday sinyal güvenlik kontrolünden geçmedi.
            İşlem planı gösterilmiyor.
          </p>
        )}

      {shown?.warnings?.length ? (
        <p className="analysis-sub">
          Uyarı: {shown.warnings.slice(0, 2).join(' · ')}
        </p>
      ) : null}

      <p className="analysis-sub">
        Varsayımsal sermaye (USC) ve seçilen risk oranı kullanılır. Gerçek emir gönderilmez.
      </p>

      <button
        type="button"
        className="disabled-action"
        disabled={!supported || loading}
        onClick={analyze}
        style={supported && !loading ? {
          background: '#1766ac',
          borderColor: '#3291e0',
          color: '#fff',
          cursor: 'pointer'
        } : undefined}
      >
        {loading ? 'Analiz Yapılıyor...' : 'Analiz Et'}
      </button>
    </section>
  )
}
