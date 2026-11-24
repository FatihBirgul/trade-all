# PWA salt okunur entegrasyon handoff

11 Kasım 2026. Aktif kaynaklar `%USERPROFILE%\trade-ai-forex-web` altında yeniden incelendi. Bu dizin Git deposu değildir; yedekler aktif kod sayılmadı. PWA, bridge ve haber dosyaları değiştirilmedi. Önceki handoff'un sabit 10.000 sermaye iddiası artık güncel değildir.

Koruma notu: Yukarıdaki değiştirilmedi ifadesi bu görevin yazım kapsamıdır. Son hash karşılaştırmasında haber bileşeni `src/NewsPanel.tsx` ve `news_bridge.py` dış eşzamanlı değişiklik gösterdi; 8007 PID'si de değişti. Bu görev bunları yazmadı veya restart etmedi. AnalysisPanel.tsx, App.tsx, MarketChart.tsx, RiskCalculator.tsx, vite.config.ts ve mt5_bridge.py hash'leri aynı kaldı; buradaki analiz sözleşmesi bulguları geçerlidir.

## Mevcut durum

`src/AnalysisPanel.tsx:147` manuel POST ile /engine/api/v5/analysis çağırır. Kullanıcıdan hypothetical_capital, exact hypothetical_currency='USC', %0'dan büyük/en çok %5 risk, seçili symbol/timeframe, H4 confirmation ve require_private=false gönderilir. Sermaye başlangıçta boştur; sabit 10.000 gönderilmez. Varsayımsal USC açıklaması vardır. Bu iki eksik giderilmiştir.

`vite.config.ts:20` /engine prefix'ini kaldırıp http://127.0.0.1:8006 hedefler; /mt5 8005, /news 8007 hedefler. allowedHosts içinde pc.example.ts.net vardır. Local proxy ve https://pc.example.ts.net/engine/openapi.json HTTP 200; DNS başarılı. Bu, telefon/service-worker veya bütün Tailscale istemcilerinin kabulü değildir.

App.tsx dört chart sembolünü sunar; MarketChart ve AnalysisPanel aynı selected symbol/timeframe alır. AnalysisPanel.tsx:100 analiz desteğini yalnız XAUUSD/EURUSD ile sınırlar. Chart seçilebilirliği dört sembollü analiz desteği değildir.

isAnalysis provider mt5, V5 şema adı ve temel alanları doğrular; ek chart_patterns alanı yanıtı bozmaz. Yanlış symbol/timeframe reddedilir, eski istekler AbortController ile iptal edilir. Null planlar tire gösterilir. approved yalnız ELIGIBLE + doğru yön/geometri + pozitif lot/risk kabul eder; REAL hypothetical NOT_EVALUATED yanıtında bütün aday planı gizler. Bu durumda başlık WAIT, ayrı motor kararı BUY_CANDIDATE olabilir.

## Frontend ekibi için somut işler

Aşağıdaki yollar %USERPROFILE%\trade-ai-forex-web köküne göredir. Bu liste mevcut görevde frontend yazımı veya backend gate gevşetme talimatı değildir.

| Dosya / bileşen | Gerekli değişiklik | Backend sözleşmesi / beklenen sonuç | Kabul testi |
|---|---|---|---|
| src/AnalysisPanel.tsx:100 / supported | GBPUSD/USDJPY analiz kapısı ve destek metni | Dört canonical sembol; alias backend'de c; yanlış symbol yanıtı reddedilir | Dört sembolde tek manuel POST; 200/ret; sembol değişince eski plan temizlenir |
| src/AnalysisPanel.tsx:52 / approved ve plan gösterimi | Betimleyici aday planı broker işlem uygunluğundan ayrı değerlendir | REAL + HYPOTHETICAL_CAPITAL + NOT_EVALUATED açık varsayımsal etiketle plan/lot gösterebilir; execution false kalır. Backend ELIGIBLE yapılmaz | BUY/SELL hypothetical plan görünür; BLOCKED/null/stale/eksik veride görünmez; emir kontrolü yok |
| src/AnalysisPanel.tsx:3 / Analysis type ve context | chart_patterns, candlestick_patterns, source, timeframe, first-known/confirmation | DESCRIPTIVE_ONLY; boş AVAILABLE listesi unavailable'dan ayrılır; pattern yönü V5 kararı yerine geçmez | BUY + bearish Double Top birlikte etiketlenir; Bottom/empty/null/unavailable/expired/left-censored |
| src/AnalysisPanel.tsx:327 / risk satırları | Yanıttaki account_currency, risk_balance_source, market_data_account_mode | USC exact; USD/USDC varsayılmaz; gerçek bakiye izlenimi verilmez | USC/HYPOTHETICAL_CAPITAL etiketi; null risk; yanlış currency ret |
| src/AnalysisPanel.tsx:216 / panel tag | Sabit MANUEL DEMO yerine doğrulanmış kaynak modu | REAL piyasa verisi DEMO değildir; varsayımsal risk gerçek hesap riski değildir | REAL salt okunur ve no execution etiketi; UNVERIFIED'da uygulanabilirlik iddiası yok |
| src/AnalysisPanel.tsx:164 / HTTP hata ve reasons | 503 status ayrımını güvenli parse et | DATA_UNAVAILABLE / ACCOUNT_PREFLIGHT_BLOCKED; hassas bilgi gösterilmez | Source mismatch/account preflight 503 ve INSUFFICIENT_DATA 200; retry yalnız manuel |
| src/AnalysisPanel.tsx:115 / digits | Hassasiyeti doğrulanmış instrument metadata'sıyla bağla | Mevcut XAUUSDc/USDJPYc tick 0.001; XAU 2/diğerleri 5 varsayımı broker seviyesini yuvarlayabilir | Tick-grid round-trip, JPY 3 hane, stale metadata kullanılmaz |
| src/App.tsx:924, src/MarketChart.tsx, src/AnalysisPanel.tsx:267 / kaynak bağlamı | Chart/analiz provider, alias ve as-of eşleşmesi | Aynı alias tek başına hesap/source eşitliğini ispatlamaz; hesap ID paylaşılmaz | Farklı kaynak/as-of'da uygulanabilirlik iddiası yok; quote/kapanış zamanı karıştırılmaz |
| vite.config.ts:20 / proxy | Aynı-origin route korunur; production proxy ayrıca doğrulanır | /engine/api/v5/analysis -> localhost:8006/api/v5/analysis | Local/Tailscale HTTPS 200/503; Android/service-worker stale cache yok; host/CORS kapıları korunur |

## Gerçekleştirilen kabul

tools/runtime_acceptance/pwa_contract.cjs, PWA'nın kendi isAnalysis ve approved fonksiyonlarını TypeScript'ten bellekte transpile edip çalıştırır; PWA dosyası üretmez. 9/9 kontrol geçti: güncel hypothetical istek, ek pattern alanı kabulü, NOT_EVALUATED plan gizleme, doğru ELIGIBLE geometri, null plan gizleme, sembol kontrolü ve kalan eksiklerin doğrulanması. mt5 provider şekli bu saf guard testi için sentetiktir; canlı UI başarısı değildir.

```powershell
$qa = Join-Path $env:TEMP 'trade-ai-runtime-acceptance-20261111'
node tools\runtime_acceptance\pwa_contract.cjs --inspect-readonly %USERPROFILE%\trade-ai-forex-web (Join-Path $qa 'http311\results.json') (Join-Path $qa 'pwa-contract.json')
```

Transport uyumu YES; yeni özelliklerin eksiksiz gösterimi ve canlı PWA kabulü PARTIAL. Frontend build/lint çalıştırılmadı; kaynaklar ve build çıktıları değiştirilmedi. Referanslar: V3_RUNTIME_ACCEPTANCE_TR.md, V3_P1_API_ACCEPTANCE.md ve V3_RUNTIME_CUTOVER_PLAN.md.
