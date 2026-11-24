import { useEffect, useState } from 'react'

type FedEvent = {
  id: string
  title_tr: string
  impact: 'HIGH' | 'MEDIUM'
  scheduled_at: string
  source_url: string
  source_status?: string
}

type Status = 'LOADING' | 'OK' | 'PARTIAL' | 'ERROR'

function validEvent(value: unknown): value is FedEvent {
  if (!value || typeof value !== 'object') return false

  const e = value as Partial<FedEvent>

  if (
    typeof e.id !== 'string' ||
    typeof e.title_tr !== 'string' ||
    typeof e.scheduled_at !== 'string' ||
    typeof e.source_url !== 'string' ||
    !['HIGH', 'MEDIUM'].includes(e.impact ?? '')
  ) return false

  try {
    const url = new URL(e.source_url)
    return (
      url.protocol === 'https:' &&
      (url.hostname === 'www.federalreserve.gov' || url.hostname === 'www.bls.gov') &&
      Number.isFinite(Date.parse(e.scheduled_at))
    )
  } catch {
    return false
  }
}

const titles: Record<string, string> = {
  'FOMC Toplanti Tutanaklari': 'FOMC Toplantı Tutanakları',
  'Fed Beige Book': 'Fed Beige Book',
  'FOMC Toplantisi': 'FOMC Toplantısı',
  'FOMC Basin Toplantisi': 'FOMC Basın Toplantısı'
}

function remaining(date: string, now: number) {
  const minutes = Math.ceil((Date.parse(date) - now) / 60000)

  if (minutes < 0) {
    return `Açıklama ${Math.abs(minutes)} dakika önce başladı`
  }

  if (minutes === 0) return 'Açıklama saati geldi'

  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const mins = minutes % 60

  return `${days} gün ${hours} saat ${mins} dakika kaldı`
}

function highRisk(event: FedEvent, now: number) {
  const minutes = (Date.parse(event.scheduled_at) - now) / 60000
  return event.impact === 'HIGH' && minutes >= -30 && minutes <= 120
}

export default function CalendarPanel() {
  const [items, setItems] = useState<FedEvent[]>([])
  const [status, setStatus] = useState<Status>('LOADING')
  const [now, setNow] = useState(Date.now())
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 30000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch('/news/api/calendar/combined', {
          signal: controller.signal,
          cache: 'no-store'
        })

        if (!response.ok) throw new Error('HTTP')

        const raw: unknown = await response.json()

        if (!raw || typeof raw !== 'object') {
          throw new Error('Invalid data')
        }

        const data = raw as Record<string, unknown>

        if (
          data.scope !== 'FED_LIVE_BLS_STATIC_2026' ||
          (data.data_status !== 'OK' && data.data_status !== 'PARTIAL') ||
          !Array.isArray(data.items) ||
          typeof data.retrieved_at !== 'string' ||
          !Number.isFinite(Date.parse(data.retrieved_at)) ||
          Math.abs(Date.now() - Date.parse(data.retrieved_at)) > 300000
        ) {
          throw new Error('Calendar unavailable or stale')
        }

        if (!controller.signal.aborted) {
          setItems(
            data.items
              .filter(validEvent)
              .sort((a, b) =>
                Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at)
              )
              .slice(0, 20)
          )
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
    const timer = setInterval(() => void load(), 60000)

    return () => {
      controller.abort()
      clearInterval(timer)
    }
  }, [refresh])

  const alerts = items.filter(event => highRisk(event, now))

  return (
    <section style={{
      marginTop: 16,
      marginBottom: 22,
      padding: 14,
      border: '1px solid #34445d',
      borderRadius: 12
    }}>
      <h3 style={{ marginTop: 0 }}>
        Ekonomik Takvim — Fed ve ABD Verileri
      </h3>

      {status === 'LOADING' && (
        <p>Ekonomik takvim yükleniyor...</p>
      )}

      {status === 'ERROR' && (
        <p style={{ color: '#ffb4a9' }}>
          Takvim verisi alınamadı veya güncel değil.
          Haber riski güvenilir şekilde değerlendirilemiyor.
        </p>
      )}

      {status === 'PARTIAL' && (
        <p style={{ color: '#f2c77d' }}>
          Fed takvimi ile sabit BLS kayıtları gösteriliyor. BLS tarihleri canlı güncellenmiyor. Bazı olaylar eksik olabilir.
        </p>
      )}

      {alerts.length > 0 && (
        <div role="alert" style={{
          padding: 14,
          marginBottom: 14,
          border: '1px solid #ef6666',
          background: 'rgba(239,68,68,0.12)',
          borderRadius: 10,
          color: '#ffd0d0'
        }}>
          <strong>YÜKSEK HABER RİSKİ — BEKLE</strong>
          {alerts.map(event => (
            <p key={event.id}>
              {titles[event.title_tr] ?? event.title_tr}
              {' — '}
              {remaining(event.scheduled_at, now)}
            </p>
          ))}
          <small>
            Bu uyarı bilgilendirme amaçlıdır.
            Otomatik işlem engeli veya al/sat sinyali değildir.
          </small>
        </div>
      )}

      {(status === 'OK' || status === 'PARTIAL') &&
        items.length === 0 && (
          <p>
            Erişilebilen Fed takviminde yaklaşan uygun olay bulunamadı.
          </p>
        )}

      {items.map(event => (
        <div key={event.id} style={{
          padding: '12px 0',
          borderBottom: '1px solid #34445d'
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 10,
            flexWrap: 'wrap'
          }}>
            <strong>
              {titles[event.title_tr] ?? event.title_tr}
            </strong>
            <span style={{
              color: event.impact === 'HIGH'
                ? '#ffad9f'
                : '#f2c77d'
            }}>
              {event.impact === 'HIGH'
                ? 'Yüksek etki'
                : 'Orta etki'}
            </span>
          </div>

          <p style={{ margin: '8px 0' }}>
            {new Date(event.scheduled_at).toLocaleString(
              'tr-TR',
              {
                timeZone: 'Europe/Istanbul',
                day: '2-digit',
                month: 'long',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
              }
            )}
            {' (Türkiye saati)'}
          </p>

          <p style={{
            margin: '6px 0',
            color: highRisk(event, now) ? '#ffad9f' : '#a9c5e6'
          }}>
            {remaining(event.scheduled_at, now)}
          </p>

          {event.source_status === 'STATIC_VERIFIED_NOT_LIVE' && (
            <p style={{ fontSize: 12, color: '#f2c77d' }}>
              BLS: 11.11.2026 tarihinde doğrulandı.
              Canlı güncellenmiyor; tarih değişmiş olabilir.
            </p>
          )}
          <a
            href={event.source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#8fc9ff' }}
          >
            {event.source_status === 'STATIC_VERIFIED_NOT_LIVE' ? 'Resmî BLS takvimi' : 'Resmî Fed takvimi'}
          </a>
        </div>
      ))}

      <button
        type="button"
        onClick={() => setRefresh(value => value + 1)}
        style={{ marginTop: 14 }}
      >
        Takvimi Yenile
      </button>

      <p style={{
        fontSize: 12,
        color: '#9aaac0',
        lineHeight: 1.6
      }}>
        Kapsam: Fed ile sabit CPI, NFP ve PPI kayıtları.
        BLS kayıtları 11 Kasım 2026 tarihinde doğrulandı.
        listede uyarı olmaması piyasanın güvenli olduğunu göstermez.
      </p>
    </section>
  )
}


