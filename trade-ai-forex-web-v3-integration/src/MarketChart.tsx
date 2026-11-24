
import { useEffect, useRef, useState } from 'react'
import {
  createChart,
  CandlestickSeries,
  ColorType,
  type CandlestickData,
  type UTCTimestamp,
} from 'lightweight-charts'

type Candle = {
  time: number
  open: number
  high: number
  low: number
  close: number
}

export type Tick = {
  bid: number
  ask: number
  time: number
}

type ApiResponse = {
  candles?: Candle[]
  tick?: Tick | null
  digits?: number
  point?: number
  captured_at_utc?: number
  detail?: string
}

export type MarketSnapshot = {
  symbol: string
  timeframe: string
  tick: Tick | null
  digits: number | null
  point: number | null
  connected: boolean
  fresh: boolean
  verifying: boolean
  status: string
  lastChangeAt: number | null
  elapsedSeconds: number | null
}

type Props = {
  symbol?: string
  timeframe?: string
  onMarketUpdate?: (snapshot: MarketSnapshot) => void
}

const API_URL = '/mt5'
const REFRESH_MS = 500
const STALE_MS = 15000
const REQUEST_TIMEOUT_MS = 4000

export default function MarketChart({
  symbol = 'XAUUSD',
  timeframe = 'M5',
  onMarketUpdate,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  const [loaded, setLoaded] = useState(false)
  const [connected, setConnected] = useState(false)
  const [message, setMessage] = useState('Veriler yükleniyor...')
  const [tick, setTick] = useState<Tick | null>(null)
  const [decimals, setDecimals] = useState<number | null>(null)
  const [point, setPoint] = useState<number | null>(null)
  const [lastChangeAt, setLastChangeAt] = useState<number | null>(null)
  const [firstReceivedAt, setFirstReceivedAt] = useState<number | null>(null)
  const [now, setNow] = useState(Date.now)

  useEffect(() => {
    if (!containerRef.current) return

    let disposed = false
    let busy = false
    let initialized = false
    let lastCandleTime = -Infinity
    let previousTick: Tick | null = null
    let appliedPriceFormat = ''
    let activeRequest: AbortController | null = null

    setLoaded(false)
    setConnected(false)
    setMessage('Veriler yükleniyor...')
    setTick(null)
    setDecimals(null)
    setPoint(null)
    setLastChangeAt(null)
    setFirstReceivedAt(null)
    setNow(Date.now())

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: {
        background: {
          type: ColorType.Solid,
          color: '#0e1728',
        },
        textColor: '#98a9c6',
      },
      grid: {
        vertLines: { color: '#263349' },
        horzLines: { color: '#263349' },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
      },
    })

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#16a34a',
      wickDownColor: '#ef4444',
    })

    function invalidatePrice() {
      previousTick = null
      setTick(null)
      setLastChangeAt(null)
      setFirstReceivedAt(null)
    }

    async function updateChart() {
      if (busy || disposed) return

      busy = true

      const requestController = new AbortController()
      activeRequest = requestController

      const timeoutId = setTimeout(() => {
        requestController.abort()
      }, REQUEST_TIMEOUT_MS)

      try {
        const params = new URLSearchParams({
          symbol,
          timeframe,
          limit: initialized ? '2' : '200',
        })

        const response = await fetch(
          `${API_URL}/api/candles?${params}`,
          {
            signal: requestController.signal,
            cache: 'no-store',
          }
        )

        const result = (await response.json()) as ApiResponse

        if (disposed) return

        if (!response.ok) {
          throw new Error(
            result.detail || `Sunucu hatası: ${response.status}`
          )
        }

        if (!Array.isArray(result.candles) || !result.candles.length) {
          throw new Error('Mum verisi alınamadı')
        }

        if (
          typeof result.digits !== 'number' ||
          !Number.isInteger(result.digits) ||
          result.digits < 0 ||
          result.digits > 10 ||
          typeof result.point !== 'number' ||
          !Number.isFinite(result.point) ||
          result.point <= 0
        ) {
          throw new Error('MT5 fiyat hassasiyeti alınamadı')
        }

        const priceFormatKey = `${result.digits}:${result.point}`

        if (priceFormatKey !== appliedPriceFormat) {
          series.applyOptions({
            priceFormat: {
              type: 'price',
              precision: result.digits,
              minMove: result.point,
            },
          })

          appliedPriceFormat = priceFormatKey
          setDecimals(result.digits)
          setPoint(result.point)
        }

        const candles: CandlestickData<UTCTimestamp>[] =
          result.candles
            .filter((c) =>
              c.time > 0 &&
              [c.time, c.open, c.high, c.low, c.close]
                .every(Number.isFinite)
            )
            .map((c) => ({
              time: c.time as UTCTimestamp,
              open: c.open,
              high: c.high,
              low: c.low,
              close: c.close,
            }))
            .sort((a, b) => Number(a.time) - Number(b.time))

        const uniqueCandles = candles.filter(
          (c, i) =>
            i === 0 || c.time !== candles[i - 1].time
        )

        if (!uniqueCandles.length) {
          throw new Error('Geçerli mum bulunamadı')
        }

        if (!initialized) {
          series.setData(uniqueCandles)
          chart.timeScale().fitContent()

          lastCandleTime = Number(
            uniqueCandles[uniqueCandles.length - 1].time
          )

          initialized = true
          setLoaded(true)
        } else {
          for (const candle of uniqueCandles) {
            const time = Number(candle.time)

            if (time >= lastCandleTime) {
              series.update(candle)
              lastCandleTime = time
            }
          }
        }

        const currentTick = result.tick

        if (
          currentTick &&
          Number.isFinite(currentTick.bid) &&
          Number.isFinite(currentTick.ask) &&
          Number.isFinite(currentTick.time) &&
          currentTick.time > 0 &&
          currentTick.bid > 0 &&
          currentTick.ask >= currentTick.bid
        ) {
          const receivedAt = Date.now()

          if (!previousTick) {
            setFirstReceivedAt(receivedAt)
          } else if (
            currentTick.time !== previousTick.time ||
            currentTick.bid !== previousTick.bid ||
            currentTick.ask !== previousTick.ask
          ) {
            setLastChangeAt(receivedAt)
          }

          previousTick = currentTick
          setTick(currentTick)
        } else {
          invalidatePrice()
        }

        setConnected(true)
        setMessage('Bağlantı başarılı')
      } catch (error) {
        if (disposed) return

        setConnected(false)
        invalidatePrice()

        if (requestController.signal.aborted) {
          setMessage('MT5 veri sunucusu yanıt vermiyor')
        } else if (error instanceof TypeError) {
          setMessage('MT5 veri sunucusuna ulaşılamıyor')
        } else {
          setMessage(
            error instanceof Error
              ? error.message
              : 'MT5 veri bağlantısı kesildi'
          )
        }
      } finally {
        clearTimeout(timeoutId)

        if (activeRequest === requestController) {
          activeRequest = null
        }

        busy = false
      }
    }

    void updateChart()

    const interval = setInterval(() => {
      if (disposed) return

      setNow(Date.now())
      void updateChart()
    }, REFRESH_MS)

    return () => {
      disposed = true
      clearInterval(interval)
      activeRequest?.abort()
      chart.remove()
    }
  }, [symbol, timeframe])

  const fresh = connected &&
    tick !== null &&
    lastChangeAt !== null &&
    now - lastChangeAt < STALE_MS

  const verifying = connected &&
    tick !== null &&
    lastChangeAt === null &&
    firstReceivedAt !== null &&
    now - firstReceivedAt < STALE_MS

  const elapsed = lastChangeAt === null
    ? null
    : Math.max(
        0,
        Math.floor((now - lastChangeAt) / 1000)
      )

  const status = !connected
    ? message
    : !tick
      ? 'Geçerli fiyat alınamıyor'
      : fresh
        ? 'Canlı piyasa verisi'
        : verifying
          ? 'Fiyat akışı doğrulanıyor'
          : 'Güncel fiyat doğrulanamıyor'

  const statusColor = fresh
    ? '#4ade80'
    : '#fbbf72'

  const displayedDecimals = decimals ?? (
    symbol.endsWith('JPY')
      ? 3
      : symbol === 'XAUUSD'
        ? 2
        : 5
  )

  const spread = tick
    ? tick.ask - tick.bid
    : null

  useEffect(() => {
    if (!onMarketUpdate) return

    onMarketUpdate({
      symbol,
      timeframe,
      tick,
      digits: decimals,
      point,
      connected,
      fresh,
      verifying,
      status,
      lastChangeAt,
      elapsedSeconds: elapsed,
    })
  }, [
    onMarketUpdate,
    symbol,
    timeframe,
    tick,
    decimals,
    point,
    connected,
    fresh,
    verifying,
    status,
    lastChangeAt,
    elapsed,
  ])

  return (
    <div style={{ width: '100%' }}>
      <div style={{
        position: 'relative',
        width: '100%',
        height: 340,
      }}>
        <div
          ref={containerRef}
          style={{ width: '100%', height: '100%' }}
        />

        {!loaded && (
          <div style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
            textAlign: 'center',
            color: '#fbbf72',
            background: 'rgba(14,23,40,0.85)',
          }}>
            {message}
          </div>
        )}
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
        padding: '12px 4px',
        borderTop: '1px solid #263349',
        fontSize: 12,
      }}>
        <strong style={{ color: statusColor }}>
          ● {status}
        </strong>

        <span style={{ color: '#98a9c6' }}>
          Güncelleme: 0,50 saniye
        </span>
      </div>

      {tick && (
        <>
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 18,
            padding: '10px 4px',
            fontSize: 13,
            color: '#e9eef7',
          }}>
            <span>
              Satış:
              <strong style={{
                color: '#f87171',
                marginLeft: 6,
              }}>
                {tick.bid.toFixed(displayedDecimals)}
              </strong>
            </span>

            <span>
              Alış:
              <strong style={{
                color: '#4ade80',
                marginLeft: 6,
              }}>
                {tick.ask.toFixed(displayedDecimals)}
              </strong>
            </span>

            <span>
              Fiyat farkı:
              <strong style={{ marginLeft: 6 }}>
                {spread?.toFixed(displayedDecimals)}
              </strong>
            </span>
          </div>

          <div style={{
            color: '#98a9c6',
            fontSize: 12,
            padding: '0 4px 10px',
          }}>
            Son gözlenen yeni fiyat: {
              elapsed === null
                ? 'Henüz doğrulanmadı'
                : `${elapsed} saniye önce`
            }
            {' · '}
            MT5 fiyat saati: {
              new Date(tick.time * 1000)
                .toLocaleTimeString('tr-TR')
            }
          </div>
        </>
      )}

      {!fresh && loaded && (
        <div style={{
          padding: 12,
          marginTop: 6,
          border: '1px solid #77552c',
          borderRadius: 8,
          color: '#fbbf72',
          background: '#342717',
          fontSize: 12,
        }}>
          Güncel fiyat akışı doğrulanmadı.
          Bu fiyatla yeni işlem planı oluşturulmamalıdır.
        </div>
      )}
    </div>
  )
}


