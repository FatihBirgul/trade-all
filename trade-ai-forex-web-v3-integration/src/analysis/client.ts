import { capitalInput, parseAnalysis, type SymbolName, type Timeframe } from './contract'

export const ANALYSIS_TIMEOUT_MS = 20000
export async function requestAnalysis(symbol: SymbolName, timeframe: Timeframe, capital: string, risk: string,
  signal: AbortSignal, timeoutMs = ANALYSIS_TIMEOUT_MS) {
  const values = capitalInput(capital, risk)
  const controller = new AbortController()
  const cancel = () => controller.abort('cancelled')
  signal.addEventListener('abort', cancel, {once: true})
  if (signal.aborted) cancel()
  const timer = setTimeout(() => controller.abort('timeout'), timeoutMs)
  try {
    const response = await fetch('/engine/api/v5/analysis', {method: 'POST', signal: controller.signal,
      headers: {'Content-Type': 'application/json'}, body: JSON.stringify({symbol, timeframe,
        confirmations: [timeframe === 'D1' ? 'D1' : 'H4'], require_private: false, ...values})})
    if (!response.ok) {
      let status: string | undefined
      try { const body = await response.json(); status = body?.detail?.status } catch { /* Ignore untrusted error bodies. */ }
      if (status === 'ACCOUNT_PREFLIGHT_BLOCKED') throw new Error('Hesap/sunucu/USC ön kontrolü reddedildi. Analiz planı gösterilmiyor.')
      if (status === 'DATA_UNAVAILABLE') throw new Error('Veri veya V2 kaynak yapılandırması kullanılamıyor (HTTP 503). Kaynak uyuşmazlığı olabilir; plan gösterilmiyor.')
      throw new Error(`Analiz servisi isteği tamamlayamadı (HTTP ${response.status}).`)
    }
    const body = await response.text()
    if (body.length > 2_000_000) throw new Error('Analiz yanıtı izin verilen boyutu aşıyor.')
    return parseAnalysis(JSON.parse(body), symbol, timeframe)
  } catch (error) {
    if (controller.signal.reason === 'timeout') throw new Error('Analiz isteği zaman aşımına uğradı (20 saniye). Yeniden denemek için Analiz Et’e basın.', {cause: error})
    if (signal.aborted) throw error
    if (error instanceof TypeError) throw new Error('Analiz servisine bağlanılamadı. Ağ bağlantısını kontrol edip elle yeniden deneyin.', {cause: error})
    if (error instanceof SyntaxError) throw new Error('Analiz sunucusundan geçerli JSON alınamadı; plan gösterilmiyor.', {cause: error})
    throw error
  } finally {
    clearTimeout(timer); signal.removeEventListener('abort', cancel)
  }
}
