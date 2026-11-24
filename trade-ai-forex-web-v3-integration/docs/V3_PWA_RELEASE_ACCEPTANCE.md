# Release kabulü

| Kontrol | Sonuç | Kanıt |
|---|---|---|
| API/client | 42/42 PASS, skip 0 | .artifacts/rc-unit-final.log |
| Browser | 34/34 PASS, skip 0 | .artifacts/rc-browser-final.log |
| Production preview + cache | 3/3 PASS, skip 0 | .artifacts/rc-preview-cache-final.log |
| Promotion dry-run güvenliği | 12/12 PASS | .artifacts/rc-promotion-tests-final.log |
| Tam ESLint | PASS | .artifacts/rc-lint-final.log |
| TypeScript + Vite/PWA | PASS (tsc -b build'in ilk adımı) | .artifacts/rc-build-final.log |
| git diff --check | PASS | final git kontrolü |
| Orijinal 38 / backend 234 dosya | Hash değişikliği 0 | .artifacts/rc-preservation-and-schema.json |
| Canlı 5173/8005/8006/8007 | Aynı PID'ler korundu | .artifacts/rc-services-final.json |
| Gerçek telefon/Tailscale PWA | NOT_RUN | İzole mobil viewport cihaz kabulü değildir |
| Canlı promotion / restore | NOT_RUN | Ayrı yetki gerekir |
| Yeni backend canlı broker kabulü | BLOCKED | BACKEND_RUNTIME_OLD |

Browser kabulü: dört sembol, manuel-only, BUY/SELL/WAIT/NO_TRADE/INSUFFICIENT_DATA/MARKET_CLOSED/PROVIDER_UNAVAILABLE, risk/spread/session/metadata retleri, NOT_EVALUATED uyarısı, USC/hypothetical input, V2 hash/first_known/empty list, 503/disconnect, cancellation/race/timeout, çift tık, local expiry ve 390×844 taşmasız ekran. Ek 34. test legacy risk sonucunun sembolde temizlenmesini ve taslağın korunmasını doğrular. Mock ve fixture'lar broker onayı değildir.

Promotion testleri: sıfır yazma, chart/news/config drift, payload/manifest bozulması, traversal/.env/node_modules allowlist reddi, yeni hedef dosyası, yeni RC hedef çakışması, APPLY reddi, eksik guard coverage ve junction reddi. Sadece izole .artifacts altındaki sahte hedeflerde çalışır.

İlk browser koşusunda preview ile ortak test-results dizini çakıştı: trace ENOENT, 33 PASS/1 FAIL. Son koşular seri çalıştırıldı, 34/34 ve 3/3 PASS. Eski başarısız loglar saklandı. Test fixture'ındaki SELL stop yönü hatası uygulamanın beklenen doğrulamasına takıldı; fixture düzeltildi. Başarı test silerek/kuralları kapatarak elde edilmedi.

Son dört cevap: uzlaştırma YES; TypeScript/build/test YES; güvenli paket/dry-run YES (APPLY aracı yok); çalışan 5173 yeni UI NO. Canlı/gerçek telefon kabulü tamamlanmış sayılmaz.
