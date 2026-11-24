import { useEffect, useState } from 'react'
import CalendarPanel from './CalendarPanel'

type News = {
  title: string
  url: string
  published_at: string
  source: string
}

function validNews(x: unknown): x is News {
  if (!x || typeof x !== 'object') return false
  const n = x as Partial<News>

  if (
    typeof n.title !== 'string' ||
    typeof n.url !== 'string' ||
    typeof n.published_at !== 'string' ||
    typeof n.source !== 'string'
  ) return false

  try {
    const url = new URL(n.url)
    return url.protocol === 'https:' &&
      url.hostname === 'www.federalreserve.gov' &&
      !Number.isNaN(Date.parse(n.published_at))
  } catch {
    return false
  }
}


function newsInfo(item: News) {
  const t = item.title.toLowerCase()
  const impact =
    'Alt\u0131na olas\u0131 etki: Beklenenden s\u0131k\u0131 Fed mesajlar\u0131 ' +
    'USD lehine ve alt\u0131n aleyhine olabilir. Daha gev\u015fek ' +
    'mesajlar ters etki yaratabilir. Bu ba\u015fl\u0131k tek ba\u015f\u0131na ' +
    'y\u00f6n tahmini i\u00e7in yeterli de\u011fildir.'

  if (t.includes('labor market dynamism')) {
    return {
      title: 'Fed yetkilisi Waller: Ekonomik g\u00f6r\u00fcn\u00fcm ve i\u015f g\u00fcc\u00fc piyasas\u0131',
      meaning:
        'Christopher Waller, ABD ekonomisi ve i\u015f g\u00fcc\u00fc ' +
        'piyasas\u0131 hakk\u0131nda bir konu\u015fma yapt\u0131. ' +
        'Bu a\u00e7\u0131klama yaln\u0131zca haber ba\u015fl\u0131\u011f\u0131na dayan\u0131yor; ' +
        'konu\u015fman\u0131n tam metni hen\u00fcz analiz edilmedi.',
      impact:
        'Alt\u0131na olas\u0131 etki: \u0130stihdam ve faiz beklentilerini ' +
        'de\u011fi\u015ftiren ifadeler alt\u0131nda oynakl\u0131\u011f\u0131 art\u0131rabilir. ' +
        'Y\u00fckseli\u015f veya d\u00fc\u015f\u00fc\u015f y\u00f6n\u00fc do\u011frulanmad\u0131.'
    }
  }

  if (t.includes('fomc statement')) {
    return {
      title: 'Fed - FOMC para politikas\u0131 a\u00e7\u0131klamas\u0131',
      meaning: 'Fed para politikas\u0131 a\u00e7\u0131klamas\u0131 yay\u0131mlad\u0131. Karar\u0131n i\u00e7eri\u011fi yaln\u0131zca ba\u015fl\u0131ktan anla\u015f\u0131lamaz.',
      impact
    }
  }

  if (t.includes('discount rate meetings')) {
    return {
      title: 'Fed - \u0130skonto faizi toplant\u0131 tutanaklar\u0131',
      meaning: 'Fed ge\u00e7mi\u015f faiz g\u00f6r\u00fc\u015fmelerinin tutanaklar\u0131n\u0131 yay\u0131mlad\u0131. Yeni faiz karar\u0131 de\u011fildir.',
      impact
    }
  }

  if (t.includes('minutes of the federal open market committee')) {
    return {
      title: 'Fed - FOMC toplant\u0131 tutanaklar\u0131',
      meaning: 'Fed, daha \u00f6nceki FOMC toplant\u0131s\u0131n\u0131n tutanaklar\u0131n\u0131 yay\u0131mlad\u0131.',
      impact
    }
  }

  return {
    title: 'Fed - Para politikas\u0131 haberi',
    meaning: 'Bu ba\u015fl\u0131\u011f\u0131n ayr\u0131nt\u0131l\u0131 T\u00fcrk\u00e7e incelemesi bulunmuyor.',
    impact: 'Alt\u0131n i\u00e7in y\u00f6n ve risk do\u011frulanamad\u0131.'
  }
}

function newsAge(published: string) {
  const days = Math.max(0, Math.floor(
    (Date.now() - Date.parse(published)) / 86400000
  ))
  return days >= 7
    ? `AR\u015e\u0130V - ${days} g\u00fcn \u00f6nce. G\u00fcncel uyar\u0131 de\u011fil.`
    : `SON 7 G\u00dcN - ${days} g\u00fcn \u00f6nce.`
}

export default function NewsPanel() {
  const [items, setItems] = useState<News[]>([])
  const [status, setStatus] = useState('LOADING')
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setStatus('LOADING')

      try {
        const response = await fetch('/news/api/news', {
          signal: controller.signal,
          cache: 'no-store'
        })

        if (!response.ok) throw new Error('HTTP')

        const data: unknown = await response.json()

        if (
          !data ||
          typeof data !== 'object' ||
          !('data_status' in data) ||
          data.data_status !== 'OK' ||
          !('items' in data) ||
          !Array.isArray(data.items)
        ) {
          throw new Error('Invalid response')
        }

        if (!controller.signal.aborted) {
          setItems(data.items.filter(validNews).slice(0, 10))
          setStatus('OK')
        }
      } catch {
        if (!controller.signal.aborted) {
          setItems([])
          setStatus('ERROR')
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [refresh])

  return (
    <article className="panel">
      <div className="feature-head">
        <div className="feature-title">
          Ekonomik Takvim ve Haberler
        </div>
        <span className="feature-badge">
          {status === 'OK' ? 'FED RSS' : 'HABER SERVISI'}
        </span>
      </div>

      <p className="feature-text">
        {'Fed para politikas\u0131 haberleri. '}
        {'Fed takvimi a\u015fa\u011f\u0131da; CPI ve NFP hen\u00fcz ba\u011fl\u0131 de\u011fil.'}
      </p>

      <CalendarPanel />

      {status === 'LOADING' && (
        <p className="feature-text">
          {'Haberler y\u00fckleniyor...'}
        </p>
      )}

      {status === 'ERROR' && (
        <p className="feature-text">
          {'Haber kayna\u011f\u0131na ula\u015f\u0131lamad\u0131.'}
        </p>
      )}

      {status === 'OK' && items.length === 0 && (
        <p className="feature-text">
          {'Uygun haber bulunamad\u0131.'}
        </p>
      )}

      {items.map((item) => (
        <div
          key={item.url}
          style={{
            padding: '14px 0',
            borderBottom: '1px solid #24324a'
          }}
        >
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: '#8fc9ff',
              fontWeight: 600,
              textDecoration: 'none',
              lineHeight: 1.6,
              overflowWrap: 'anywhere'
            }}
          >
            {newsInfo(item).title}
          </a>

          <p style={{ color: '#d5dfef', lineHeight: 1.6 }}>
            {newsInfo(item).meaning}
          </p>
          <p style={{ color: '#f2c77d', lineHeight: 1.6 }}>
            {newsInfo(item).impact}
          </p>
          <p style={{ color: '#9aaac0', fontSize: 12 }}>
            {newsAge(item.published_at)}
          </p>

          <div style={{
            color: '#9aaac0',
            fontSize: 12,
            marginTop: 6
          }}>
            {new Date(item.published_at).toLocaleString(
              'tr-TR',
              {
                timeZone: 'Europe/Istanbul',
                dateStyle: 'medium',
                timeStyle: 'short'
              }
            )}
            {' (TS\u0130) \u00b7 '}{item.source}
          </div>
        </div>
      ))}

      <button
        type="button"
        onClick={() => setRefresh(x => x + 1)}
        disabled={status === 'LOADING'}
        style={{ marginTop: 14 }}
      >
        Haberleri Yenile
      </button>

      <p className="feature-text">
        {'Bilgilendirme ama\u00e7l\u0131d\u0131r. '}
        {'Al/sat sinyali de\u011fildir.'}
      </p>
    </article>
  )
}

