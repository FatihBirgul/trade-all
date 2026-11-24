import { useEffect, useState } from 'react'

type Event = {
  id: string
  title_tr: string
  scheduled_at: string
  impact: string
  source_status?: string
}

type Status = 'LOADING' | 'OK' | 'PARTIAL' | 'ERROR'

function validEvent(x: unknown): x is Event {
  if (!x || typeof x !== 'object') return false
  const e = x as Partial<Event>

  return (
    typeof e.id === 'string' &&
    typeof e.title_tr === 'string' &&
    typeof e.scheduled_at === 'string' &&
    typeof e.impact === 'string' &&
    /(?:Z|[+-]\d{2}:\d{2})$/.test(e.scheduled_at) &&
    Number.isFinite(Date.parse(e.scheduled_at))
  )
}

const names: Record<string, string> = {
  'FOMC Toplanti Tutanaklari': 'FOMC Toplantı Tutanakları',
  'FOMC Toplantisi': 'FOMC Toplantısı',
  'FOMC Basin Toplantisi': 'FOMC Basın Toplantısı',
  'PPI - Uretici Enflasyonu': 'PPI — Üretici Enflasyonu',
  'CPI - Tuketici Enflasyonu': 'CPI — Tüketici Enflasyonu',
  'NFP - Tarim Disi Istihdam': 'NFP — Tarım Dışı İstihdam'
}

function countdown(date: string, now: number) {
  const minutes = Math.ceil((Date.parse(date) - now) / 60000)

  if (minutes <= 0) {
    return `${Math.abs(minutes)} dakika önce`
  }

  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const mins = minutes % 60

  return days > 0
    ? `${days} gün ${hours} saat ${mins} dakika`
    : `${hours} saat ${mins} dakika`
}

export default function AnalysisNewsRisk() {
  const [items, setItems] = useState<Event[]>([])
  const [status, setStatus] = useState<Status>('LOADING')
  const [now, setNow] = useState(Date.now)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch('/news/api/calendar/combined', {
          cache: 'no-store',
          signal: controller.signal
        })

        if (!response.ok) throw new Error('HTTP')

        const value: unknown = await response.json()

        if (!value || typeof value !== 'object') {
          throw new Error('Invalid response')
        }

        const data = value as Record<string, unknown>

        if (
          data.scope !== 'FED_LIVE_BLS_STATIC_2026' ||
          !['OK', 'PARTIAL'].includes(String(data.data_status)) ||
          !Array.isArray(data.items) ||
          typeof data.retrieved_at !== 'string' ||
          !Number.isFinite(Date.parse(data.retrieved_at)) ||
          Math.abs(Date.now() - Date.parse(data.retrieved_at)) > 300000
        ) {
          throw new Error('Calendar not verified')
        }

        if (!controller.signal.aborted) {
          setItems(data.items.filter(validEvent))
          setStatus(data.data_status as Status)
          setNow(Date.now())
        }
      } catch {
        if (!controller.signal.aborted) {
          setItems([])
          setStatus('ERROR')
        }
      }
    }

    void load()

    const refresh = setInterval(() => void load(), 60000)
    const clock = setInterval(() => setNow(Date.now()), 30000)

    return () => {
      controller.abort()
      clearInterval(refresh)
      clearInterval(clock)
    }
  }, [])

  const upcoming = items
    .filter(event =>
      event.impact === 'HIGH' &&
      Date.parse(event.scheduled_at) - now >= -30 * 60000
    )
    .sort((a, b) =>
      Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at)
    )

  const alerts = upcoming.filter(event =>
    Date.parse(event.scheduled_at) - now <= 120 * 60000
  )

  const next = upcoming[0]

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        margin: '16px 0',
        padding: 14,
        border: `1px solid ${
          alerts.length ? '#e47777' : '#34445d'
        }`,
        borderRadius: 10,
        background: alerts.length
          ? 'rgba(220,65,65,0.10)'
          : 'rgba(25,40,60,0.35)'
      }}
    >
      <strong>Ekonomik Haber Riski</strong>

      {status === 'LOADING' && (
        <p>Ekonomik takvim kontrol ediliyor...</p>
      )}

      {status === 'ERROR' && (
        <p style={{ color: '#ffb4a9' }}>
          Takvim bağlantısı yok veya veriler güncel değil.
          Haber riski doğrulanamadı. İşlem öncesi
          ekonomik takvimi ayrıca kontrol et.
        </p>
      )}

      {alerts.length > 0 && (
        <div role="alert" style={{ color: '#ffb4a9' }}>
          <p>
            <strong>YÜKSEK HABER RİSKİ — BEKLE</strong>
          </p>

          {alerts.map(event => (
            <p key={event.id}>
              {names[event.title_tr] ?? event.title_tr}
              {' — '}
              {countdown(event.scheduled_at, now)}
              {event.source_status === 'STATIC_VERIFIED_NOT_LIVE'
                ? ' (BLS: sabit takvim, tarih değişmiş olabilir)'
                : ''}
            </p>
          ))}

          <p>
            Yüksek oynaklık oluşabilir.
            Yeni işlem öncesinde haberin gerçekleşmesini
            ve piyasanın sakinleşmesini değerlendir.
          </p>
        </div>
      )}

      {status !== 'ERROR' &&
        status !== 'LOADING' &&
        alerts.length === 0 && (
          <p>
            Listelenen olaylar için şu anda aktif
            iki saatlik yüksek haber riski uyarısı yok.
          </p>
        )}

      {status !== 'ERROR' &&
        status !== 'LOADING' &&
        alerts.length === 0 &&
        next && (
          <p>
            Sıradaki yüksek etkili olay:
            {' '}{names[next.title_tr] ?? next.title_tr}
            {' — '}{countdown(next.scheduled_at, now)} kaldı.
          </p>
        )}

      {status === 'PARTIAL' && (
        <p style={{ color: '#f2c77d', fontSize: 12 }}>
          Fed takvimi ve sabit BLS kayıtları kullanılıyor.
          BLS verileri canlı güncellenmiyor.
          Takvim kapsamı eksik olabilir.
        </p>
      )}

      <p style={{ fontSize: 12, color: '#a9b8cc' }}>
        Bilgilendirme amaçlıdır. V5 motorunun kararını
        değiştirmez, otomatik işlem engeli oluşturmaz.
        Uyarı bulunmaması işlemin güvenli olduğu
        anlamına gelmez.
      </p>
    </div>
  )
}
