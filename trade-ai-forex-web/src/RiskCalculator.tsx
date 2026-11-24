
import { useEffect, useRef, useState } from 'react'

type Direction = 'BUY' | 'SELL'

type RiskResult = {
  symbol: string
  direction: Direction
  demo_only: boolean
  order_sent: boolean
  account_currency: string
  risk_budget: number
  volume_min: number
  volume_max: number
  volume_step: number
  min_lot_estimated_loss: number
  suggested_lot: number | null
  estimated_loss_at_sl: number | null
  status: string
  warning: string
}

type Props = {
  symbol: string
  marketFresh: boolean
}

const API_URL = '/mt5'

const styles = `
  .risk-calculator {
    color: #e8eef9;
  }

  .risk-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
  }

  .risk-heading {
    font-size: 14px;
    font-weight: 800;
  }

  .risk-badge {
    color: #91c8ff;
    background: #172e48;
    border: 1px solid #28527a;
    padding: 6px 8px;
    border-radius: 7px;
    font-size: 10px;
    font-weight: 800;
  }

  .risk-description {
    color: #91a4c0;
    font-size: 12px;
    line-height: 1.7;
    margin-bottom: 17px;
  }

  .risk-fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .risk-field {
    min-width: 0;
  }

  .risk-field label {
    display: block;
    margin-bottom: 7px;
    color: #9bb0cc;
    font-size: 11px;
    font-weight: 750;
  }

  .risk-field input,
  .risk-field select {
    width: 100%;
    min-width: 0;
    border: 1px solid #38506e;
    border-radius: 8px;
    background: #0c1729;
    color: #ffffff;
    padding: 11px 10px;
    outline-color: #49aaff;
    font-size: 13px;
  }

  .risk-field input::placeholder {
    color: #617792;
  }

  .risk-button {
    width: 100%;
    margin-top: 17px;
    padding: 13px;
    background: #176db4;
    border: 1px solid #3996e0;
    border-radius: 9px;
    color: white;
    font-size: 13px;
    font-weight: 800;
    cursor: pointer;
  }

  .risk-button:hover:not(:disabled) {
    background: #2384d0;
  }

  .risk-button:disabled {
    opacity: .5;
    cursor: not-allowed;
  }

  .risk-error {
    color: #ffb4a9;
    background: #351e25;
    border: 1px solid #74404b;
    padding: 12px;
    border-radius: 9px;
    font-size: 12px;
    line-height: 1.6;
    margin-top: 12px;
  }

  .risk-result {
    margin-top: 17px;
    padding: 15px;
    border: 1px solid #285b56;
    background: #102b2a;
    border-radius: 11px;
  }

  .risk-result-title {
    color: #55e5ae;
    font-size: 13px;
    font-weight: 850;
    margin-bottom: 12px;
  }

  .risk-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 9px 0;
    border-bottom: 1px solid #24433f;
    font-size: 12px;
  }

  .risk-row span {
    color: #a3beb8;
  }

  .risk-row strong {
    color: #f3fff9;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .risk-note {
    margin-top: 14px;
    color: #99aac0;
    font-size: 11px;
    line-height: 1.7;
  }

  @media(max-width: 420px) {
    .risk-fields {
      grid-template-columns: 1fr;
    }
  }
`

// DÜZELTİLDİ: Sayı kontrolü geçerli rakamları kabul eder.
// Virgül ve nokta ondalık ayırıcı olarak kullanılabilir.
function readNumber(value: string): number | null {
  const normalized = value.trim().replace(',', '.')

  if (!/^[0-9]+([.][0-9]+)?$/.test(normalized)) {
    return null
  }

  const parsed = Number(normalized)

  if (!Number.isFinite(parsed)) {
    return null
  }

  return parsed
}

function formatMoney(
  value: number,
  currency: string
): string {
  return (
    value.toLocaleString('tr-TR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }) +
    ' ' +
    currency
  )
}

export default function RiskCalculator({
  symbol,
  marketFresh,
}: Props) {
  const [direction, setDirection] =
    useState<Direction>('BUY')

  const [balance, setBalance] = useState('')
  const [riskPercent, setRiskPercent] = useState('1')
  const [entry, setEntry] = useState('')
  const [stopLoss, setStopLoss] = useState('')

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<RiskResult | null>(null)

  const activeRequest = useRef<AbortController | null>(null)

  function invalidate() {
    activeRequest.current?.abort()
    activeRequest.current = null
    setLoading(false)
    setResult(null)
    setError('')
  }

  useEffect(() => {
    activeRequest.current?.abort()
    activeRequest.current = null

    setLoading(false)
    setResult(null)
    setError('')

    return () => {
      activeRequest.current?.abort()
    }
  }, [symbol, marketFresh])

  async function calculateRisk() {
    invalidate()

    if (!marketFresh) {
      setError(
        'Canlı piyasa verisi doğrulanmadı. ' +
        'Risk önizlemesi için güncel fiyat akışı gereklidir.'
      )
      return
    }

    const numericBalance = readNumber(balance)
    const numericRisk = readNumber(riskPercent)
    const numericEntry = readNumber(entry)
    const numericStop = readNumber(stopLoss)

    if (
      numericBalance === null ||
      numericBalance <= 0 ||
      numericBalance > 1000000000
    ) {
      setError('Geçerli bir hesap bakiyesi gir.')
      return
    }

    if (
      numericRisk === null ||
      numericRisk <= 0 ||
      numericRisk > 10
    ) {
      setError(
        'Risk yüzdesi 0 ile 10 arasında olmalıdır.'
      )
      return
    }

    if (
      numericEntry === null ||
      numericStop === null ||
      numericEntry <= 0 ||
      numericStop <= 0 ||
      numericEntry > 10000000 ||
      numericStop > 10000000
    ) {
      setError(
        'Geçerli giriş ve Stop Loss fiyatları gir.'
      )
      return
    }

    if (
      direction === 'BUY' &&
      numericStop >= numericEntry
    ) {
      setError(
        'BUY işleminde Stop Loss giriş fiyatından düşük olmalı.'
      )
      return
    }

    if (
      direction === 'SELL' &&
      numericStop <= numericEntry
    ) {
      setError(
        'SELL işleminde Stop Loss giriş fiyatından yüksek olmalı.'
      )
      return
    }

    const controller = new AbortController()
    activeRequest.current = controller

    let timedOut = false

    const timeout = setTimeout(() => {
      timedOut = true
      controller.abort()
    }, 8000)

    setLoading(true)

    try {
      const params = new URLSearchParams({
        symbol,
        direction,
        balance: String(numericBalance),
        risk_percent: String(numericRisk),
        entry: String(numericEntry),
        stop_loss: String(numericStop),
      })

      const response = await fetch(
        `${API_URL}/api/risk-preview?${params}`,
        {
          signal: controller.signal,
          cache: 'no-store',
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(
          typeof data.detail === 'string'
            ? data.detail
            : 'Risk hesaplaması başarısız oldu.'
        )
      }

      const calculated = data as RiskResult

      if (
        calculated.symbol !== symbol ||
        calculated.direction !== direction ||
        calculated.demo_only !== true ||
        calculated.order_sent !== false ||
        !Number.isFinite(calculated.risk_budget) ||
        typeof calculated.account_currency !== 'string'
      ) {
        throw new Error(
          'MT5 risk yanıtı doğrulanamadı.'
        )
      }

      if (
        !controller.signal.aborted &&
        marketFresh
      ) {
        setResult(calculated)
      }
    } catch (err) {
      if (controller.signal.aborted) {
        if (timedOut) {
          setError(
            'MT5 hesaplama isteği zaman aşımına uğradı.'
          )
        }
        return
      }

      if (err instanceof TypeError) {
        setError(
          'MT5 risk sunucusuna ulaşılamıyor.'
        )
      } else {
        setError(
          err instanceof Error
            ? err.message
            : 'Bilinmeyen hesaplama hatası.'
        )
      }
    } finally {
      clearTimeout(timeout)

      if (activeRequest.current === controller) {
        activeRequest.current = null
        setLoading(false)
      }
    }
  }

  return (
    <div className="risk-calculator">
      <style>{styles}</style>

      <div className="risk-header">
        <div className="risk-heading">
          Risk ve Lot Hesaplayıcı
        </div>

        <span className="risk-badge">
          DEMO
        </span>
      </div>

      <div className="risk-description">
        {symbol} için MT5 üzerinden manuel risk
        hesaplaması. Değerler kullanıcı tarafından
        girilir; otomatik işlem sinyali oluşturulmaz.
      </div>

      <div className="risk-fields">
        <div className="risk-field">
          <label htmlFor="risk-balance">
            Hesap Bakiyesi (USC - Cent)
          </label>

          <input
            id="risk-balance"
            type="text"
            inputMode="decimal"
            placeholder="Örn. 10000"
            value={balance}
            onChange={(e) => {
              invalidate()
              setBalance(e.target.value)
            }}
          />
        </div>

        <div className="risk-field">
          <label htmlFor="risk-percent">
            Risk (%)
          </label>

          <input
            id="risk-percent"
            type="text"
            inputMode="decimal"
            value={riskPercent}
            onChange={(e) => {
              invalidate()
              setRiskPercent(e.target.value)
            }}
          />
        </div>

        <div className="risk-field">
          <label htmlFor="risk-direction">
            İşlem Yönü
          </label>

          <select
            id="risk-direction"
            value={direction}
            onChange={(e) => {
              invalidate()
              setDirection(
                e.target.value as Direction
              )
            }}
          >
            <option value="BUY">
              BUY / Alış
            </option>

            <option value="SELL">
              SELL / Satış
            </option>
          </select>
        </div>

        <div className="risk-field">
          <label htmlFor="risk-entry">
            Manuel Giriş Fiyatı
          </label>

          <input
            id="risk-entry"
            type="text"
            inputMode="decimal"
            placeholder="Giriş fiyatı"
            value={entry}
            onChange={(e) => {
              invalidate()
              setEntry(e.target.value)
            }}
          />
        </div>

        <div className="risk-field">
          <label htmlFor="risk-stop">
            Stop Loss
          </label>

          <input
            id="risk-stop"
            type="text"
            inputMode="decimal"
            placeholder="Stop fiyatı"
            value={stopLoss}
            onChange={(e) => {
              invalidate()
              setStopLoss(e.target.value)
            }}
          />
        </div>
      </div>

      <button
        className="risk-button"
        type="button"
        onClick={() => void calculateRisk()}
        disabled={loading || !marketFresh}
      >
        {loading
          ? 'MT5 Hesaplıyor...'
          : 'Demo Riskini Hesapla'}
      </button>

      {!marketFresh && (
        <div
          className="risk-error"
          role="status"
        >
          Güncel piyasa akışı doğrulanmadığı
          için hesaplama devre dışı.
        </div>
      )}

      {error && (
        <div
          className="risk-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {result && (
        <div
          className="risk-result"
          aria-live="polite"
        >
          <div className="risk-result-title">
            MT5 Risk Önizlemesi
          </div>

          <div className="risk-row">
            <span>Risk bütçesi</span>

            <strong>
              {formatMoney(
                result.risk_budget,
                result.account_currency
              )}
            </strong>
          </div>

          <div className="risk-row">
            <span>Hesaplanan lot</span>

            <strong>
              {result.suggested_lot ??
                'Uygun lot yok'}
            </strong>
          </div>

          <div className="risk-row">
            <span>
              Stop Loss tahmini zarar
            </span>

            <strong>
              {result.estimated_loss_at_sl !== null
                ? formatMoney(
                    result.estimated_loss_at_sl,
                    result.account_currency
                  )
                : '—'}
            </strong>
          </div>

          <div className="risk-row">
            <span>Minimum lot</span>

            <strong>
              {result.volume_min}
            </strong>
          </div>

          <div className="risk-row">
            <span>
              Minimum lot tahmini zarar
            </span>

            <strong>
              {formatMoney(
                result.min_lot_estimated_loss,
                result.account_currency
              )}
            </strong>
          </div>

          {result.status === 'below_minimum' && (
            <div className="risk-error">
              Minimum lot bile seçilen risk
              bütçesini aşıyor. Bu koşullarda
              uygun lot bulunamadı.
            </div>
          )}

          {result.status === 'max_lot_reached' && (
            <div className="risk-note">
              Brokerın izin verdiği maksimum
              lot sınırına ulaşıldı.
            </div>
          )}
        </div>
      )}

      <div className="risk-note">
        Bu araç yalnızca manuel DEMO senaryo
        önizlemesidir. Emir göndermez.
        Komisyon, swap, fiyat kayması ve marjin
        yeterliliği hesaplanmaz. Girilen
        fiyatların mevcut piyasa fiyatına
        uygunluğu ayrıca doğrulanmalıdır.
      </div>
    </div>
  )
}
