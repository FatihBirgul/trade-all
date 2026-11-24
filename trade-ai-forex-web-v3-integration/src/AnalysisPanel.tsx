import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import AnalysisNewsRisk from './AnalysisNewsRisk'
import type { MarketSnapshot } from './MarketChart'
import { capitalInput, explainReason, finite, freshness, isRecord, planVisibility, symbols, timeframes,
  type Analysis, type PatternContext, type SymbolName, type Timeframe } from './analysis/contract'
import { requestAnalysis } from './analysis/client'
import './AnalysisPanel.css'

type Props = { symbol: string; timeframe: string; reportedTickTime: string | null; chartSource?: MarketSnapshot | null }
type DraftProps = {capital:string;risk:string;onCapital:(value:string)=>void;onRisk:(value:string)=>void}
const num = (value: unknown, digits?: number) => finite(value)
  ? new Intl.NumberFormat('tr-TR', digits === undefined ? {maximumSignificantDigits: 12} : {minimumFractionDigits: digits, maximumFractionDigits: digits}).format(value) : '—'
const date = (value: unknown) => {
  const ms = typeof value === 'number' ? value * 1000 : typeof value === 'string' ? Date.parse(value) : NaN
  return Number.isFinite(ms) ? new Intl.DateTimeFormat('tr-TR', {dateStyle:'short',timeStyle:'medium',timeZone:'Europe/Istanbul'}).format(ms) + ' İstanbul' : 'Bildirilmedi'
}
const labels: Record<string,string> = {
  BUY_CANDIDATE:'BUY · teknik aday', SELL_CANDIDATE:'SELL · teknik aday', WAIT:'WAIT · bekle',
  NO_TRADE:'NO_TRADE · plan reddedildi', INSUFFICIENT_DATA:'INSUFFICIENT_DATA · veri yetersiz',
  MARKET_CLOSED:'MARKET_CLOSED · piyasa kapalı', STALE_DATA:'STALE_DATA · güncel olmayan veri',
  PROVIDER_UNAVAILABLE:'PROVIDER_UNAVAILABLE · kaynak kullanılamıyor', OK:'Tamam', DATA_UNAVAILABLE:'Veri kullanılamıyor',
  STALE:'Güncel değil', BLOCKED:'Engellendi', NOT_EVALUATED:'İşlem uygunluğu değerlendirilmedi', ELIGIBLE:'Backend risk kontrolü geçti',
  UNKNOWN:'Bilinmiyor', UNVERIFIED:'Doğrulanmadı', CONFLICTING:'Çelişkili', CURRENT_MT5_OBSERVED:'Güncel MT5 gözlemi',
  OPERATOR_APPROVED:'Operatör onaylı', UNAPPROVED:'Onaylanmadı', PASS:'Kontrol geçti', BLOCK:'Engellendi',
  OPEN:'Açık', CLOSING_SOON:'Kapanışa yaklaşıyor', OPENING_SOON:'Açılışa yaklaşıyor', CLOSED:'Kapalı',
  DISABLED:'Yeni işlem yönleri kapalı', STRUCTURAL_CONFIRMED:'Yapısal teyit', UNCONFIRMED:'Teyitsiz',
  EXPIRED:'Süresi dolmuş', LEFT_CENSORED:'İlk bilgi zamanı pencere dışında', AVAILABLE:'Mevcut', UNAVAILABLE:'Kullanılamıyor',
  PARTIAL:'Kısmi', HYPOTHETICAL_CAPITAL:'Kullanıcının varsayımsal sermayesi', NOT_PROVIDED:'Sağlanmadı',
  SOURCE_NOT_SUPPLIED:'Kaynak sağlanmadı', HISTORICAL_SOURCE_VERIFIED:'Backend tarafından tarihsel kaynak doğrulanmış',
}
const label = (value: unknown) => typeof value === 'string' ? labels[value] ?? value : 'Bildirilmedi'
function Row({title,children}: {title:string;children:ReactNode}) {
  return <div className="ma-row"><dt>{title}</dt><dd>{children}</dd></div>
}
function Patterns({title,context,analysis}: {title:string;context:PatternContext|null;analysis:Analysis}) {
  const unavailable = !context || context.status !== 'AVAILABLE' || context.role !== 'DESCRIPTIVE_ONLY' || context.sourceMismatch
  return <section className="ma-context" aria-label={title}><h3>{title}</h3>
    <p className="ma-caption">Yalnız betimleyici bağlam. Formasyon işlem kararı veya emir izni değildir.</p>
    {unavailable ? <p className="ma-notice">{context?.sourceMismatch ? 'Formasyon kaynak kimliği uyuşmuyor; sonuçlar gösterilmiyor.'
      : 'Formasyon kaynağı kullanılamıyor veya betimleyici sözleşmesi doğrulanmadı.'}</p>
      : !context.items.length ? <p>Bu snapshot içinde formasyon bulunmadı.</p>
      : <ul className="ma-patterns">{context.items.map((item,i) => <li key={item.name+i}>
        <strong>{item.name}</strong><span className="ma-badge">DESCRIPTIVE_ONLY</span><details><summary>Zaman ve teyit ayrıntıları</summary><dl>
          <Row title="Zaman dilimi">{item.timeframe ?? analysis.timeframe}</Row>
          <Row title="Yön betimlemesi">{item.direction === 'BULLISH' ? 'Yukarı yönlü' : item.direction === 'BEARISH' ? 'Aşağı yönlü' : item.direction === 'NEUTRAL' ? 'Nötr' : 'Bildirilmedi'}</Row>
          <Row title="İlk bilinen zaman">{date(item.first_known_utc ?? item.known_at_utc)}</Row>
          <Row title="Teyit / kanıt">{label(item.confirmation_state ?? (item.confirmed === true ? 'STRUCTURAL_CONFIRMED' : item.confirmed === false ? 'UNCONFIRMED' : undefined))}</Row>
          <Row title="Yaş">{item.age_bars === undefined ? 'Bildirilmedi' : item.age_bars+' mum'}</Row>
        </dl></details></li>)}</ul>}
    <details><summary>Backend kaynak kimliği</summary><dl><Row title="Kaynak sürümü">{context?.version ?? 'Bildirilmedi'}</Row>
      <Row title="Backend’in bildirdiği kaynak hash’i"><code>{context?.source_sha256 ?? 'Bu bağlamda bildirilmedi'}</code></Row></dl></details>
  </section>
}
export default function AnalysisPanel(props: Props) {
  const [capital,setCapital] = useState('')
  const [risk,setRisk] = useState('1')
  return <ManualAnalysis key={props.symbol+':'+props.timeframe} {...props} capital={capital} risk={risk} onCapital={setCapital} onRisk={setRisk} />
}
function ManualAnalysis({symbol,timeframe,reportedTickTime,chartSource,capital,risk,onCapital,onRisk}: Props & DraftProps) {
  const [result,setResult] = useState<Analysis|null>(null)
  const [error,setError] = useState<string|null>(null)
  const [loading,setLoading] = useState(false)
  const [now,setNow] = useState(Date.now)
  const pending = useRef<AbortController|null>(null)
  useEffect(() => () => pending.current?.abort(), [])
  useEffect(() => {
    const refresh = () => setNow(Date.now())
    window.addEventListener('focus',refresh); document.addEventListener('visibilitychange',refresh)
    return () => {window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh)}
  },[])
  useEffect(() => {
    if (!result) return
    const delay = Date.parse(result.as_of_utc)+120001-Date.now()
    if (delay <= 0 || delay > 125001) return
    const timer = setTimeout(() => setNow(Date.now()),delay)
    return () => clearTimeout(timer)
  },[result])
  function reset() {
    pending.current?.abort(); pending.current=null
    setLoading(false); setResult(null); setError(null)
  }
  const supported = symbols.includes(symbol as SymbolName) && timeframes.includes(timeframe as Timeframe)
  async function analyze() {
    if (!supported || pending.current) return
    try { capitalInput(capital,risk) } catch (e) {
      setError(e instanceof Error ? e.message : 'Sermaye girdisi geçersiz.'); setResult(null); return
    }
    const controller = new AbortController(); pending.current=controller
    setLoading(true); setError(null); setResult(null)
    try {
      const value = await requestAnalysis(symbol as SymbolName,timeframe as Timeframe,capital,risk,controller.signal)
      if (pending.current === controller && !controller.signal.aborted) {setNow(Date.now());setResult(value)}
    } catch (e) {
      if (pending.current === controller && !controller.signal.aborted) setError(e instanceof Error ? e.message : 'Analiz tamamlanamadı.')
    } finally {
      if (pending.current === controller) {pending.current=null;setLoading(false)}
    }
  }
  const evaluation = result ? planVisibility(result,now) : null
  const showPlan = evaluation?.showPlan === true
  const oldContract = result && (!result.broker_contract?.status || !result.spread_status?.policy_status)
  const spread = result?.spread_status
  const observed = isRecord(spread?.observed) ? spread.observed : undefined
  const fields = isRecord(result?.broker_contract?.fields) ? result.broker_contract.fields : undefined
  const digitField = isRecord(fields?.digits) ? fields.digits : undefined
  const digits = finite(digitField?.value) && Number.isInteger(digitField.value) && digitField.value>=0 && digitField.value<=10 ? digitField.value : undefined
  const chart = chartSource?.symbol === symbol && chartSource.timeframe === timeframe ? chartSource : null
  const chartFresh = chart?.fresh && chart.connected
  const stale = result && freshness(result,now) !== 'FRESH'

  return <section className="panel manual-analysis" aria-label="Manuel Forex analizi">
    <div className="panel-head"><div><h2 className="panel-title">Manuel Forex Analizi</h2>
      <p className="ma-caption">Kapanmış verilerle teknik bağlam ve varsayımsal risk</p></div><span className="ma-badge">{result?.provider==='fixture-test-only'?'TEST / SALT OKUNUR':'REAL MT5 / SALT OKUNUR'}</span></div>
    <p className="ma-notice">Gerçek emir gönderilmez. USC sermayesi kullanıcı tarafından belirlenen varsayımsal tutardır.</p>
    <div className="ma-form">
      <label htmlFor="analysis-capital">Varsayımsal sermaye (USC)<input id="analysis-capital" inputMode="decimal" autoComplete="off" value={capital} placeholder="USC tutarı girin" onChange={e=>{reset();onCapital(e.target.value)}} /></label>
      <label htmlFor="analysis-risk">Risk oranı (%)<input id="analysis-risk" inputMode="decimal" autoComplete="off" value={risk} onChange={e=>{reset();onRisk(e.target.value)}} /></label>
      <button className="ma-analyze" disabled={!supported||loading} onClick={analyze} type="button">{loading?'Analiz yapılıyor…':'Analiz Et'}</button>
      {loading && <button className="ma-cancel" onClick={reset} type="button">Analizi İptal Et</button>}
    </div>
    {!supported && <p role="alert">Bu sembol veya zaman dilimi backend sözleşmesinde desteklenmiyor.</p>}
    <div className="ma-result" aria-live="polite" aria-busy={loading}>
      <h3>{loading?'Analiz yapılıyor…':error?'Analiz alınamadı':result?label(result.final_decision):'Analiz bekleniyor'}</h3>
      <p>{symbol} / {timeframe} · Her analiz yalnız düğmeye basıldığında istenir.</p>
      {error && <p className="ma-warning" role="alert">{error}</p>}
      {stale && <p className="ma-warning" role="alert">Snapshot güncel değil veya zamanı gelecekte. Plan gizlendi; yeniden analiz isteyin.</p>}
      {result?.provider==='fixture-test-only' && <p className="ma-warning">TEST VERİSİ · Canlı broker kabulü değildir.</p>}
      {oldContract && <p className="ma-warning">Backend sürüm/yapılandırma uyumu doğrulanmadı: yeni broker/spread güven alanları eksik. Plan gizlendi.</p>}
      {result?.execution_permission!==undefined && result.execution_permission!==false && <p className="ma-warning">Beklenmeyen işlem izni bildirimi; plan kapalı.</p>}
      {result && <>
        <dl>
          <Row title="Veri durumu">{label(result.data_status)}</Row>
          <Row title="İşlem uygunluğu">{label(result.trading_eligibility)}</Row>
          <Row title="Broker seansı">{label(result.market_status)}</Row>
          <Row title="Broker contract güveni">{label(result.broker_contract?.status)}</Row>
          <Row title="Tarihsel contract güveni">{label(result.broker_contract?.historical_status)}</Row>
          <Row title="Tarihsel seans kanıtı">{label(result.historical_session_evidence?.status)}</Row>
          <Row title="Tarihsel boşluk yetkisi">{result.historical_session_evidence?.historical_gap_authorized===true?'Backend tarafından bildirilmiş':'BLOCKED_BY_EXTERNAL_EVIDENCE'}</Row>
          <Row title="Motor entegrasyonu">{label(result.integration_status)}</Row>
          <Row title="Spread politikası">{label(spread?.policy_status)} / {label(spread?.decision)}</Row>
          <Row title="Doğrulanan hesap birimi">{result.account_currency??'Bildirilmedi'}</Row>
          <Row title="Analiz zamanı">{date(result.as_of_utc)}</Row>
        </dl>
        <details className="ma-details"><summary>Spread, risk kaynağı ve snapshot ayrıntıları</summary><dl>
          <Row title="Gözlenen spread (fiyat farkı)">{num(observed?.price??result.spread)}</Row>
          <Row title="Gözlenen spread (point)">{num(observed?.points)}</Row>
          <Row title="MT5 sembol spread’i (point)">{num(observed?.symbol_spread_points)}</Row>
          <Row title="Onaylı maksimum spread (fiyat farkı)">{spread?.policy_status==='OPERATOR_APPROVED'?num(spread.max_allowed_price):'—'}</Row>
          <Row title="Risk sermayesi kaynağı">{label(result.risk_balance_source)}</Row>
          <Row title="Piyasa veri hesabı">{result.market_data_account_mode??'Bildirilmedi'}</Row>
          <Row title="Emir izni">{result.execution_permission===false?'YOK':'Doğrulanmadı; plan kapalı'}</Row>
          <Row title="Snapshot kimliği"><code>{result.snapshot_id??'Bildirilmedi'}</code></Row>
        </dl></details>
        {spread?.policy_status==='UNAPPROVED' && <p className="ma-warning">Maksimum spread limiti henüz onaylanmadı. Gözlenen spread izin limiti değildir.</p>}
        <h4>Motor gerekçeleri</h4>
        <ul className="ma-reasons">{result.decision_reasons.map((r,i)=><li key={i}>{explainReason(r)}</li>)}</ul>
        {Array.isArray(spread?.reasons) && <ul className="ma-reasons">{spread.reasons.filter((r):r is string=>typeof r==='string').map((r,i)=><li key={i}>{explainReason(r)}</li>)}</ul>}
        <div className="ma-plan" data-testid="analysis-plan">
          <h4>{showPlan?'Varsayımsal teknik plan — emir izni yok':evaluation?.candidate?'Teknik aday · uygulanabilir plan gösterilmiyor':'İşlem planı mevcut değil'}</h4>
          {!showPlan && <ul className="ma-reasons">{evaluation?.blockers.map(reason=><li key={reason}>{reason}</li>)}</ul>}
          <dl>
            <Row title="Giriş bölgesi">{showPlan?num(result.entry_zone?.low,digits)+' – '+num(result.entry_zone?.high,digits):'—'}</Row>
            <Row title="Stop Loss">{showPlan?num(result.stop_loss,digits):'—'}</Row>
            <Row title="Take Profit 1 / 2">{showPlan?num(result.take_profit_1,digits)+' / '+num(result.take_profit_2,digits):'—'}</Row>
            <Row title="Risk / ödül (backend bildirimi)">{showPlan?num(result.risk_reward):'—'}</Row>
            <Row title="Varsayımsal lot">{showPlan?num(result.lot_size):'—'}</Row>
            <Row title="Varsayımsal risk (USC)">{showPlan?num(result.risk_amount):'—'}</Row>
          </dl>
          {showPlan && <p className="ma-caption">NOT_EVALUATED bir emir onayı değildir. Bu değerler yalnız varsayımsal USC sermayesine aittir.</p>}
        </div>
        <details className="ma-context"><summary>Teknik göstergeler</summary>{result.indicators?<dl>{[['ema20','EMA 20'],['ema50','EMA 50'],['ema200','EMA 200'],['rsi14','RSI 14'],['atr14','ATR 14'],['macd_histogram','MACD histogram']].map(([key,title])=><Row key={key} title={title}>{num(result.indicators?.[key])}</Row>)}</dl>:<p>Gösterge verisi bildirilmedi.</p>}</details>
        <Patterns title="V2 çift tepe / çift dip" context={result.chart_patterns} analysis={result} />
        <Patterns title="V2 mum formasyonları" context={result.candlestick_patterns} analysis={result} />
        {result.warnings.length>0 && <details><summary>Backend uyarıları</summary><ul>{result.warnings.map((r,i)=><li key={i}>{r}</li>)}</ul></details>}
      </>}
    </div>
    <section className="ma-context" aria-label="Veri kaynakları"><h3>Grafik ve analiz kaynakları</h3><dl>
      <Row title="Grafik yolu">/mt5 · ayrı 8005 veri servisi</Row>
      <Row title="Grafik bid / ask">{chartFresh?num(chart?.tick?.bid,chart?.digits??undefined)+' / '+num(chart?.tick?.ask,chart?.digits??undefined):'Güncel grafik quote’u bildirilmedi'}</Row>
      <Row title="Grafik bildirilen fiyat saati">{reportedTickTime??'Bildirilmedi'}</Row>
      <Row title="Analiz yolu">/engine/api/v5/analysis · 8008</Row>
      <Row title="Analiz provider / broker sembolü">{result?result.provider+' / '+(result.broker_symbol??'Bildirilmedi'):'Analiz bekleniyor'}</Row>
      <Row title="Backend’in bildirdiği public kaynak hash’i"><code>{typeof result?.source_versions?.public_code_sha256==='string'?result.source_versions.public_code_sha256:'Bildirilmedi'}</code></Row>
    </dl><p className="ma-caption">Analiz sözleşmesi bid/ask taşımaz. Grafik fiyatları analiz snapshot’ı değildir; aynı sembol hesap/kaynak eşitliğini kanıtlamaz.</p></section>
    <AnalysisNewsRisk />
  </section>
}
