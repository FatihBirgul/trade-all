
import { useCallback, useState } from 'react'
import MarketChart, { type MarketSnapshot } from './MarketChart'
import RiskCalculator from './RiskCalculator'
import AnalysisPanel from './AnalysisPanel'
import NewsPanel from './NewsPanel'

const styles = `
  :root {
    font-family: Inter, -apple-system, BlinkMacSystemFont,
      "Segoe UI", Arial, sans-serif;
    color: #e8eef9;
    background: #080e1b;
    font-synthesis: none;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    min-width: 320px;
    background: #080e1b;
  }

  #root {
    width: 100%;
    max-width: none;
    margin: 0;
    padding: 0;
    text-align: left;
  }

  button, select { font: inherit; }
  button { cursor: pointer; }

  .app {
    min-height: 100vh;
    color: #e8eef9;
    background:
      radial-gradient(
        ellipse at 80% -10%,
        rgba(31,103,175,.15),
        transparent 45%
      ),
      #080e1b;
  }

  .shell {
    width: min(1440px, calc(100% - 64px));
    margin: 0 auto;
  }

  .site-header {
    background: rgba(12,20,35,.95);
    border-bottom: 1px solid #24324a;
  }

  .header-inner {
    min-height: 76px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .brand-icon {
    width: 42px;
    height: 42px;
    border-radius: 12px;
    display: grid;
    place-items: center;
    color: #fff;
    background: linear-gradient(145deg,#0879d5,#15416d);
    border: 1px solid #328ce1;
    font-size: 16px;
    font-weight: 900;
    letter-spacing: -1px;
  }

  .brand-title {
    font-size: 20px;
    font-weight: 850;
    letter-spacing: -.7px;
    color: #fff;
  }

  .brand-title span { color: #53b7ff; }

  .brand-subtitle {
    font-size: 10px;
    letter-spacing: 2px;
    color: #8499b5;
    margin-top: 3px;
    font-weight: 700;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .header-chip {
    border: 1px solid #2c3d58;
    background: #152137;
    padding: 9px 13px;
    border-radius: 9px;
    color: #a9bdd8;
    font-size: 11px;
    font-weight: 750;
    letter-spacing: .4px;
  }

  .header-chip.demo {
    color: #e6b86a;
    border-color: #5b4829;
    background: #292315;
  }

  .main {
    padding-top: 34px;
    padding-bottom: 40px;
  }

  .overview {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 24px;
    margin-bottom: 26px;
  }

  .eyebrow {
    color: #48b4ff;
    font-size: 11px;
    letter-spacing: 2px;
    font-weight: 850;
    margin-bottom: 10px;
  }

  h1 {
    margin: 0;
    font-size: clamp(26px,3.2vw,38px);
    letter-spacing: -1.3px;
    line-height: 1.2;
    color: #fff;
  }

  .subtitle {
    color: #92a5c0;
    font-size: 13px;
    line-height: 1.7;
    margin: 12px 0 0;
  }

  .connection-box {
    flex-shrink: 0;
    display: flex;
    gap: 11px;
    align-items: center;
    border: 1px solid #2b3b52;
    background: #111c2e;
    padding: 14px 17px;
    border-radius: 12px;
    max-width: 300px;
  }

  .indicator {
    display: inline-block;
    width: 9px;
    height: 9px;
    flex: 0 0 9px;
    border-radius: 50%;
    background: #f2ae59;
  }

  .indicator.online {
    background: #38d994;
    box-shadow: 0 0 0 4px rgba(56,217,148,.1);
  }

  .connection-title {
    font-size: 12px;
    font-weight: 800;
    color: #f1f6ff;
  }

  .connection-desc {
    font-size: 11px;
    color: #91a4bd;
    line-height: 1.5;
    margin-top: 4px;
  }

  .toolbar {
    background: #111b2d;
    border: 1px solid #263651;
    border-radius: 14px;
    padding: 18px;
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    justify-content: space-between;
    gap: 18px;
    margin-bottom: 18px;
  }

  .control-label {
    display: block;
    font-size: 10px;
    font-weight: 800;
    color: #8196b3;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    margin-bottom: 9px;
  }

  .symbol-select {
    min-width: 220px;
    padding: 11px 14px;
    border-radius: 9px;
    background: #1b2940;
    color: #f4f8ff;
    border: 1px solid #39506e;
    outline-color: #53b7ff;
  }

  .timeframes {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    padding: 4px;
    border-radius: 10px;
    background: #0b1526;
    border: 1px solid #293954;
  }

  .tf {
    min-width: 43px;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 9px 10px;
    background: transparent;
    color: #91a5c1;
    font-size: 12px;
    font-weight: 750;
  }

  .tf:hover {
    color: #fff;
    background: #1b304e;
  }

  .tf.active {
    color: #fff;
    background: #1766ac;
    border-color: #3291e0;
  }

  .quote-grid {
    display: grid;
    grid-template-columns: repeat(4,minmax(0,1fr));
    gap: 14px;
    margin-bottom: 18px;
  }

  .quote-card {
    position: relative;
    overflow: hidden;
    min-width: 0;
    padding: 19px 20px;
    background: #121d30;
    border: 1px solid #293950;
    border-radius: 13px;
  }

  .quote-card.bid { border-top: 2px solid #ef6b78; }
  .quote-card.ask { border-top: 2px solid #31d59b; }
  .quote-card.spread { border-top: 2px solid #499ef2; }
  .quote-card.market { border-top: 2px solid #d5a654; }

  .quote-label {
    color: #8fa4c0;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
  }

  .quote-value {
    margin-top: 13px;
    font-size: clamp(20px,2.4vw,28px);
    font-weight: 850;
    letter-spacing: -.6px;
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }

  .quote-value.red { color: #ff7d87; }
  .quote-value.green { color: #55e5ae; }
  .quote-value.blue { color: #8ec8ff; }

  .quote-caption {
    font-size: 11px;
    color: #748aa9;
    line-height: 1.5;
    margin-top: 9px;
  }

  .state-value {
    font-size: 15px;
    font-weight: 800;
    line-height: 1.5;
    margin-top: 13px;
  }

  .state-value.online { color: #55e5ae; }
  .state-value.caution { color: #f2be72; }

  .workspace {
    display: grid;
    grid-template-columns: minmax(0,1.85fr) minmax(310px,.95fr);
    gap: 18px;
    align-items: stretch;
  }

  .panel {
    background: #111b2d;
    border: 1px solid #283750;
    border-radius: 15px;
    padding: 20px;
    min-width: 0;
  }

  .panel-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 18px;
  }

  .panel-title {
    color: #f0f5ff;
    font-size: 15px;
    font-weight: 850;
    margin: 0;
  }

  .panel-description {
    color: #8a9eb8;
    font-size: 11px;
    line-height: 1.5;
    margin-top: 6px;
  }

  .panel-tag {
    color: #8fc8ff;
    background: #122b46;
    border: 1px solid #24517d;
    padding: 7px 10px;
    border-radius: 7px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: .5px;
  }

  .panel-tag.waiting {
    background: #292317;
    border-color: #544127;
    color: #e7bf80;
  }

  .chart-box {
    padding: 8px;
    background: #0e1728;
    border: 1px solid #293c59;
    border-radius: 11px;
    overflow: hidden;
  }

  .chart-footnote {
    margin-top: 14px;
    color: #7e91ac;
    font-size: 11px;
    line-height: 1.6;
  }

  .analysis-status {
    background: #192337;
    border: 1px dashed #3a4a63;
    border-radius: 11px;
    padding: 23px 14px;
    text-align: center;
    margin-bottom: 16px;
  }

  .analysis-icon {
    width: 44px;
    height: 44px;
    border-radius: 13px;
    background: #29364c;
    color: #e8bc77;
    display: grid;
    place-items: center;
    margin: 0 auto 13px;
    font-weight: 900;
    font-size: 20px;
  }

  .analysis-main {
    font-size: 16px;
    font-weight: 850;
    color: #efc17d;
  }

  .analysis-sub {
    font-size: 11px;
    color: #9baac1;
    line-height: 1.7;
    margin-top: 9px;
  }

  .data-row {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    border-bottom: 1px solid #26364e;
    padding: 13px 0;
    font-size: 12px;
  }

  .data-row span { color: #8fa2bd; }

  .data-row strong {
    color: #ecf3ff;
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .disabled-action {
    display: block;
    width: 100%;
    padding: 13px;
    border-radius: 10px;
    border: 1px solid #34445e;
    background: #26354b;
    color: #91a3ba;
    font-weight: 800;
    margin-top: 18px;
    cursor: not-allowed;
  }

  .section-heading {
    margin: 29px 0 15px;
    font-size: 17px;
    font-weight: 850;
    color: #f2f6ff;
  }

  .secondary-grid {
    display: grid;
    grid-template-columns: repeat(2,minmax(0,1fr));
    gap: 16px;
  }

  .risk-module {
    grid-column: 1 / -1;
    border-top: 2px solid #278ed6;
  }

  .feature-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .feature-title {
    font-size: 14px;
    font-weight: 800;
    color: #eaf1fd;
  }

  .feature-badge {
    font-size: 10px;
    color: #93a9c5;
    background: #202d43;
    padding: 6px 8px;
    border-radius: 6px;
    white-space: nowrap;
  }

  .feature-value {
    font-size: 24px;
    font-weight: 850;
    color: #9dc5ea;
    margin: 24px 0 9px;
  }

  .feature-text {
    font-size: 12px;
    line-height: 1.8;
    color: #91a4c0;
    margin: 0;
  }

  .safety {
    display: flex;
    align-items: flex-start;
    gap: 11px;
    padding: 16px 19px;
    background: #172318;
    border: 1px solid #335039;
    border-radius: 11px;
    margin-top: 20px;
    color: #b7dec0;
    font-size: 12px;
    line-height: 1.7;
  }

  .safety strong { color: #67df98; }

  .footer {
    border-top: 1px solid #26344b;
    color: #7286a4;
    padding: 23px 0 30px;
    font-size: 11px;
  }

  .footer-inner {
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 12px;
  }

  @media(max-width: 1050px) {
    .quote-grid {
      grid-template-columns: repeat(2,minmax(0,1fr));
    }

    .workspace {
      grid-template-columns: minmax(0,1fr);
    }
  }

  @media(max-width: 700px) {
    .shell {
      width: calc(100% - 28px);
    }

    .header-inner {
      min-height: 68px;
    }

    .header-chip {
      font-size: 10px;
      padding: 7px 9px;
    }

    .header-chip:not(.demo) {
      display: none;
    }

    .brand-title { font-size: 18px; }
    .brand-subtitle { font-size: 9px; }

    .main { padding-top: 24px; }

    .overview {
      flex-direction: column;
      gap: 16px;
    }

    .connection-box {
      width: 100%;
      max-width: none;
    }

    .toolbar {
      padding: 14px;
      align-items: stretch;
    }

    .symbol-control {
      width: 100%;
    }

    .symbol-select {
      width: 100%;
    }

    .timeframes {
      width: 100%;
    }

    .tf {
      flex: 1 1 12%;
      min-width: 0;
      padding: 10px 5px;
    }

    .quote-grid {
      gap: 10px;
    }

    .quote-card {
      padding: 15px 13px;
    }

    .quote-value {
      font-size: clamp(17px,4.7vw,24px);
    }

    .state-value {
      font-size: 13px;
    }

    .panel {
      padding: 15px;
    }

    .secondary-grid {
      grid-template-columns: 1fr;
    }

    .risk-module {
      grid-column: auto;
    }

    .feature-value {
      margin-top: 16px;
    }
  }

  @media(max-width: 380px) {
    .quote-value { font-size: 17px; }
    .quote-label { font-size: 10px; }
    .brand-icon { width: 36px; height: 36px; }
  }
`

const periods = [
  'M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1',
]

function formatPrice(
  value: number | null | undefined,
  digits: number
): string {
  if (value == null || !Number.isFinite(value)) {
    return '—'
  }

  return value.toFixed(digits)
}

function App() {
  const [symbol, setSymbol] = useState('XAUUSD')
  const [timeframe, setTimeframe] = useState('M5')
  const [market, setMarket] = useState<MarketSnapshot | null>(null)

  const handleMarketUpdate = useCallback(
    (snapshot: MarketSnapshot) => {
      setMarket(snapshot)
    },
    []
  )

  const activeMarket =
    market?.symbol === symbol &&
    market?.timeframe === timeframe
      ? market
      : null

  const isLive = Boolean(
    activeMarket?.connected &&
    activeMarket?.fresh &&
    activeMarket?.tick &&
    activeMarket?.digits !== null
  )

  const digits = activeMarket?.digits ?? 2

  const liveTick = isLive && activeMarket
    ? activeMarket.tick
    : null

  const bid = formatPrice(liveTick?.bid, digits)
  const ask = formatPrice(liveTick?.ask, digits)

  const spread = formatPrice(
    liveTick ? liveTick.ask - liveTick.bid : null,
    digits
  )

  const marketStatus =
    activeMarket?.status ?? 'MT5 verisi bekleniyor'

  const lastTickTime = activeMarket?.tick?.time
    ? new Date(activeMarket.tick.time * 1000)
        .toLocaleTimeString('tr-TR')
    : '—'

  return (
    <div className="app">
      <style>{styles}</style>

      <header className="site-header">
        <div className="shell header-inner">
          <div className="brand">
            <div className="brand-icon">TA</div>

            <div>
              <div className="brand-title">
                TRADE <span>AI</span> V3
              </div>

              <div className="brand-subtitle">
                FOREX INTELLIGENCE
              </div>
            </div>
          </div>

          <div className="header-right">
            <span className="header-chip">
              YEREL GELİŞTİRME
            </span>

            <span className="header-chip demo">
              DEMO MOD
            </span>
          </div>
        </div>
      </header>

      <main className="shell main">
        <section className="overview">
          <div>
            <div className="eyebrow">
              TRADE AI / MARKET TERMINAL
            </div>

            <h1>Piyasa Kontrol Merkezi</h1>

            <p className="subtitle">
              Canlı Forex verileri, teknik analiz altyapısı
              ve profesyonel işlem planlama platformu.
            </p>
          </div>

          <div className="connection-box">
            <span
              className={`indicator ${
                isLive ? 'online' : ''
              }`}
            />

            <div>
              <div className="connection-title">
                MT5 Veri Bağlantısı
              </div>

              <div className="connection-desc">
                {marketStatus}
              </div>
            </div>
          </div>
        </section>

        <section className="toolbar">
          <div className="symbol-control">
            <label
              className="control-label"
              htmlFor="market-symbol"
            >
              İşlem Enstrümanı
            </label>

            <select
              id="market-symbol"
              className="symbol-select"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            >
              <option value="XAUUSD">
                XAU/USD — Altın
              </option>

              <option value="EURUSD">
                EUR/USD — Euro / Dolar
              </option>

              <option value="GBPUSD">
                GBP/USD — Sterlin / Dolar
              </option>

              <option value="USDJPY">
                USD/JPY — Dolar / Yen
              </option>
              <option value="CHFJPY">CHF/JPY</option>
              <option value="EURCAD">EUR/CAD</option>
              <option value="USDCAD">USD/CAD</option>
              <option value="USDCHF">USD/CHF</option>
              <option value="EURGBP">EUR/GBP</option>
              <option value="EURCHF">EUR/CHF</option>
              <option value="GBPCHF">GBP/CHF</option>
              <option value="NZDUSD">NZD/USD</option>
              <option value="EURAUD">EUR/AUD</option>
              <option value="CADJPY">CAD/JPY</option>
              <option value="NZDJPY">NZD/JPY</option>
              <option value="AUDUSD">AUD/USD</option>
              <option value="EURJPY">EUR/JPY</option>
              <option value="GBPJPY">GBP/JPY</option>
              <option value="AUDJPY">AUD/JPY</option>
            </select>
          </div>

          <div>
            <div className="control-label">
              Grafik Zaman Dilimi
            </div>

            <div className="timeframes">
              {periods.map((period) => (
                <button
                  key={period}
                  type="button"
                  aria-pressed={timeframe === period}
                  className={`tf ${
                    timeframe === period ? 'active' : ''
                  }`}
                  onClick={() => setTimeframe(period)}
                >
                  {period}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="quote-grid">
          <div className="quote-card bid">
            <div className="quote-label">
              BID / SATIŞ
            </div>

            <div className="quote-value red">
              {bid}
            </div>

            <div className="quote-caption">
              {symbol} · MT5 satış fiyatı
            </div>
          </div>

          <div className="quote-card ask">
            <div className="quote-label">
              ASK / ALIŞ
            </div>

            <div className="quote-value green">
              {ask}
            </div>

            <div className="quote-caption">
              {symbol} · MT5 alış fiyatı
            </div>
          </div>

          <div className="quote-card spread">
            <div className="quote-label">
              SPREAD / FARK
            </div>

            <div className="quote-value blue">
              {spread}
            </div>

            <div className="quote-caption">
              Alış ve satış fiyatı farkı
            </div>
          </div>

          <div className="quote-card market">
            <div className="quote-label">
              PİYASA VERİ DURUMU
            </div>

            <div
              className={`state-value ${
                isLive ? 'online' : 'caution'
              }`}
            >
              {isLive
                ? '● CANLI VERİ'
                : '● DOĞRULANMADI'}
            </div>

            <div className="quote-caption">
              {activeMarket?.elapsedSeconds == null
                ? 'Yeni fiyat henüz doğrulanmadı'
                : `Son fiyat değişimi: ${
                    activeMarket.elapsedSeconds
                  } sn önce`}
            </div>
          </div>
        </section>

        <div className="workspace">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2 className="panel-title">
                  {symbol} / {timeframe} — Fiyat Grafiği
                </h2>

                <div className="panel-description">
                  TradingView Lightweight Charts · MT5 verisi
                </div>
              </div>

              <span className="panel-tag">
                MT5 VERİ KAYNAĞI
              </span>
            </div>

            <div className="chart-box">
              <MarketChart
                symbol={symbol}
                timeframe={timeframe}
                onMarketUpdate={handleMarketUpdate}
              />
            </div>

            <div className="chart-footnote">
              Mum grafiği MT5 üzerinden alınır. Geçmiş
              mumların görüntülenmesi tek başına canlı
              fiyat doğrulaması anlamına gelmez.
            </div>
          </section>

          <AnalysisPanel symbol={symbol} timeframe={timeframe} reportedTickTime={isLive ? lastTickTime : null} />
        </div>

        <h2 className="section-heading">
          İşlem ve Araştırma Modülleri
        </h2>

        <section className="secondary-grid">
          <article className="panel risk-module">
            <RiskCalculator
              symbol={symbol}
              marketFresh={isLive}
            />
          </article>

          <NewsPanel />

          <article className="panel">
            <div className="feature-head">
              <div className="feature-title">
                Demo İşlem Takibi
              </div>

              <span className="feature-badge">
                HAZIRLANIYOR
              </span>
            </div>

            <div className="feature-value">—</div>

            <p className="feature-text">
              Demo işlem planları, işlem geçmişi
              ve performans değerlendirmeleri bu
              modülde takip edilecek.
            </p>
          </article>
        </section>

        <div className="safety">
          <span>●</span>

          <div>
            <strong>
              Güvenli geliştirme modu aktif.
            </strong>
            {' '}
            Gerçek para ile emir gönderimi kapalıdır.
            Güncelliği doğrulanmayan fiyatlarla işlem
            planı oluşturulmaz. Analiz motoru bağlantısı
            tamamlanmadan yapay zekâ sinyali gösterilmez.
          </div>
        </div>
      </main>

      <footer className="footer">
        <div className="shell footer-inner">
          <span>
            TRADE AI V3 · FOREX INTELLIGENCE PLATFORM
          </span>

          <span>
            Yerel geliştirme · MT5 REAL Cent veri (salt-okunur)
          </span>
        </div>
      </footer>
    </div>
  )
}

export default App
