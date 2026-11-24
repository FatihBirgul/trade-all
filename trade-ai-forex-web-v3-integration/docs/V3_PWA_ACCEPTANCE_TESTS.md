# PWA kabul testleri

11 Kasım 2026. Orijinal projede test script/suite yoktu; mevcut build/lint başlangıçta çalıştırıldı. Başlangıç build PASS; full ESLint 5 hata. Yeni testler izole repo içinde, üretim chart/news kaynaklarını değiştirmeden çalışır.

| Kontrol | Nihai sonuç |
|---|---|
| TypeScript tsc -b | PASS, npm run build içinde |
| Vite production build | PASS, Vite 8.3.6 |
| PWA generateSW | PASS, manifest.webmanifest, registerSW.js, sw.js/workbox üretildi |
| Unit/API client | 42/42 PASS; 0 fail/skip/cancel |
| Edge browser / Playwright 1.65.0 | 33/33 PASS; 0 fail/skip |
| Production preview browser subset | 3/3 PASS; bu üç senaryo 33'ün alt kümesidir |
| Yeni analiz/App/proxy kapsamı ESLint | PASS |
| Full ESLint | FAIL: 4 korunmuş eski hata; baseline 5 |
| git diff --check | PASS |

Tam lint eksikleri: src/AnalysisNewsRisk.tsx:55, CalendarPanel.tsx:70, MarketChart.tsx:74 (react-hooks/purity) ve RiskCalculator.tsx:243 (react-hooks/set-state-in-effect). AnalysisPanel'in eski set-state-in-effect hatası giderildi. Bu dört dosya snapshot ile byte-identical; kurallar susturulmadı. Tam lint başarılı ilan edilmez. Baseline/full çıktılar .artifacts/baseline-lint.log ve full-lint.log içinde.

İlk geliştirme sonrası unit koşusunda SELL fixture'ının TP2'si BUY yönünde kaldığı için yeni ikinci-hedef kontrolü bir başarısızlık yakaladı. Sentetik fixture SELL TP2=1970 olarak düzeltildi; kontrol gevşetilmedi. Nihai 42/42 geçti. İlk kopya .bak dosyaları yalnız izole hedefte temizlendi; kaynak kopyalara dokunulmadı. Hatalı ilk patch UTF-8 BOM nedeniyle uygulanmadı; yalnız izole AnalysisPanel dosyası doğru UTF-8 olarak yazıldı.

## Tarayıcı kapsamı

1. Dört canonical sembolde manuel POST, USC hypothetical body, balance yok.
2. BUY, SELL, WAIT, NO_TRADE, INSUFFICIENT_DATA, MARKET_CLOSED, PROVIDER_UNAVAILABLE ayrı.
3. DATA_UNAVAILABLE, UNKNOWN broker/session, UNAPPROVED spread, UNVERIFIED contract, currency mismatch, null lot, execution=true retleri.
4. NOT_EVALUATED ancak tüm gate'ler geçince açık varsayımsal plan; broker onayı değil.
5. Double Top/Bottom, Doji candlestick; empty list, source mismatch; betimleyici rol korunur.
6. Missing capital hiç request göndermez; kimlik uyuşmazlığı, geç response/symbol change ve double-click yarışı.
7. API 503 private reason sızdırmaz; network disconnect ve timeout güvenli hata; automatic retry yok.
8. 120 saniye sonrası yerel expiry planı gizler; background analysis POST yok.
9. Eski schema optional alanları eksik: uyum uyarısı/plan kapalı. Yeni schema: typed güven alanları.
10. 390x844 mobil yatay overflow yok; emir/pozisyon açma butonu yok.
11. Ayrı gerçek localhost Python fixture API -> Vite proxy -> browser bileşeni: provider fixture etiketi, Double Top, candlestick ve varsayımsal plan.
12. Tailscale allowed Host header ile same-origin proxy OpenAPI; canlı Tailscale cihaz kabulü sayılmaz.

Unit senaryoları ayrıca D1 confirmation, yanlış timestamp/schema/provider, future/as-of, yanlış risk reward/TP2/broker identity, USC/USD/USDC, unknown execution/source mode, kaynak hash tutarsızlığı ve null first-known semantiğini doğrular. Sayılar örtüşen farklı gruplardır; toplam benzersiz kanıt sayısı diye toplanmaz.

## İzolasyon

run-browser.mjs boş loopback portları seçer; korumalı 5173/8005/8006/8007 seçilmez. Python fixture_server backend dosyasından read-only çalışır, terminale bağlanmaz; mock provider ve sentetik onaylı limitler yalnız QA sürecindedir. News/MT5 browser yolları testte intercept edilir, canlı servis çağrılmaz. Preview/dev server aynı izole kaynak/bundle'ı kullanır. Windows fixture launcher dahil yalnız kendi child process tree'leri kapatılır; kendi portlarının kapandığı doğrulanır. Süreç/screenshot/log artefaktları .artifacts içinde ve Git dışındadır.

```powershell
npm ci
npm run lint:analysis
npm test
npm run build
npm run test:browser
npm run test:browser -- --preview --grep 'mobile viewport|new backend real HTTP|Tailscale allowed'
npm run lint # Bilinen 4 eski hata; raporda saklanır
git diff --check
```

Windows test helper'ı mevcut Python 3.11 venv/backend/V2 read-only yollarını kullanır; başka makinede bu yollar ayarlanmalıdır. Edge kanalının kurulu olması gerekir. Global npm/Node/Python kurulumu değiştirilmedi. Tek yeni dev dependency @playwright/test; hazır Edge kullanıldı, browser paketi global kurulmadı.
