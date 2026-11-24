# Son mühürleme engeli: dış proxy değişikliği

11 Kasım 2026 21:55:25 İstanbul: orijinal PWA vite.config.ts dışarıdan /engine hedefini 8006 -> 8008 değiştirdi. 8008 PID 13988 yeni historical alanlı schema sunuyor; 5173 proxy artık bu schema'yı veriyor. 8006 PID 8284 aynı ve exact loaded sürümü VERSION_UNVERIFIED. Görev bu değişikliği yapmadı veya geri almadı. Son preflight BLOCKED; paket yalnız inceleme içindir (deployable=false). Aşağıdaki 8006 operasyon sırası uygulanamaz: önce yetkili backend/proxy hedefi uzlaştırılmalı, sonra manifest/backup ve uçtan uca kabul yeniden mühürlenmelidir. Yeni canlı operasyon onayı bu aşamada istenmiyor. Önceki başarılı kabul sonuçları test edilmiş adayın kanıtıdır; değişmiş canlı routing kabulü değildir.

# Final release reconciliation ve cutover preflight

11 Kasım 2026. Son durum: **BLOCKED**. Canlı restart, PWA APPLY,
HMR, push veya gerçek/demo işlem yapılmadı. Bu belge önceki 3c8adb8 preflight
sonucunun güncel backend ile yeniden uzlaştırılmış halidir.

## Kaynak kimlikleri ve korunma

Backend main: `%USERPROFILE%\trade-ai-v3-core`, branch
`codex/v3-real-readonly-analysis`, HEAD
`56cbd7e05a40b106deda9298e2be28b488d0d952`; temiz ve değiştirilmedi.
PWA izolasyonu: `%USERPROFILE%\trade-ai-forex-web-v3-integration`, branch
`codex/pwa-v3-manual-analysis`; başlangıç/UI RC SHA
`34c6ec2e1a02893cd1d8301d8bf6c5048c6aeb05`. Son tooling commit'i manifestte
yer alır. src/public/package/Vite UI kaynak farkı sıfırdır.
Orijinal `trade-ai-forex-web` Git deposu değildir; sahte HEAD atanmadı.
Original src/public/config/bridge ve backend tracked dosyaları hash snapshot
ile yeniden doğrulandı. Dış MarketChart/NewsPanel değişiklikleri korunur.

Eski `TRADE_AI_V3_CONTROLLED_CUTOVER_34c6ec2.zip` SHA sidecar ile doğrulandı ve
korundu. Yeni paket `TRADE_AI_V3_RECONCILED_56cbd7e_34c6ec2_BLOCKED_REVIEW.zip`; dosya hash'leri
`release/reconciled-56cbd7e/source-manifest.json`, ZIP hash'i `.zip.sha256` içindedir.
Yeni manifest backend SHA, değişmeyen UI RC SHA ve yeni tooling SHA'yı ayrı tutar.

## Yeniden hesaplanan kabul

| Kapı | Sonuç |
| --- | --- |
| Exact backend archive Python 3.11.9 / NumPy 2.2.6 | 600/600 PASS, 79.372 s |
| Exact backend archive Python 3.13.15 / NumPy 2.2.6 | 600/600 PASS, 54.068 s |
| Mevcut backend HTTP | İki Python'da 63/63 PASS |
| Historical HTTP | İki Python'da 14/14 PASS |
| Orijinal PWA contract baseline | İki Python çıktısıyla 9/9 PASS |
| Hazır PWA API/client | 42/42 PASS |
| Yeni response/version/historical release guard | 3/3 PASS |
| Browser | 34/34 PASS, 1.8 dakika |
| Production preview / SW cache | 3/3 PASS, 9.0 s |
| Promotion dry-run / APPLY rollback / live guard | 42/42 PASS = 12 + 18 + 12 |
| Runtime launcher guard | 4/4 PASS |
| Gerçek yeni read-only candidate | 47/47 PASS; kendi portu kapandı |
| Baseline failback provası | 14/14 PASS; kendi portu kapandı |
| Yeni backend + gerçek read-only UI E2E | PASS, dört manuel analiz, order calls 0; iki port kapandı |
| TypeScript + production build | PASS; tsc -b build'in ilk aşamasıdır |
| Tam ESLint / Python compilation / diff check | PASS |
| Ön yedek | 27 dosya, hash doğrulaması PASS |
| Original PWA dry-run | 9 payload / 27 guard, writes=0, deletes=0 |

Test sayıları benzersiz toplam diye toplanmaz: historical/TestClient testleri
600'ün içindedir; HTTP/client/browser kapsamları örtüşür. 9 kontrol eski live
PWA pure-guard baseline'ıdır, yeni RC'nin 42 client testi yerine geçmez.
Son başarılı koşularda failure/error/skipped yoktur. Fiziksel telefon/standalone
kabulü NOT_RUN; checklist güncel operasyon planında hazırdır.

İlk archive testi 588 metodda iki hata verdi: eski testler pinned V2 Git repo'sunu
kardeş dizinde bekliyordu. QA release'inin yanında bağımsız no-hardlinks local Git
kopyası oluşturuldu; üretim/test kodu değiştirilmeden iki sürümde 600 tekrarlandı.
Bu QA Git kopyası ZIP'e dahil edilmez; runtime config mevcut V2 root ve exact
candlestick pin'i kullanır. İlk browser 31/34, sonraki 33/34 oldu; navigation/fill
timeout'ları ve watched .artifacts içindeki Chromium cookie EBUSY hataları görüldü.
Yalnız test runner temp profilleri source root dışına taşıdı, fixture Vite config'i
test/release çıktıları izlemesini dışladı ve entry warmup ekledi. Beklentiler ve
20s test timeout değişmedi. Son 34/34 ve preview 3/3 başarıları bu düzende alındı.
Başarısız loglar/trace kopyaları .artifacts altında korunur.

## Güncel runtime gerçeği

8006 PID **8284**, başlangıç 11 Kasım 19:45:05 Europe/Istanbul, cwd main V3.
Child executable global Python311 yolunda olsa da parent 11380 gerçek
`AppData/Local/TradeAI/V5Runtime/Scripts/python.exe` launcher'ıdır. Launch env
paket metadata'sı NumPy 2.2.6, FastAPI 0.162.0, MetaTrader5 5.0.6231;
bu, eski process'teki her modülün load anının ispatı değildir. Aynı process'e
ait güvenilir loaded-code attestation bulunamadı: **VERSION_UNVERIFIED**.
Live schema historical_session_evidence alanını içermez; disk 56cbd7e SHA'sı
loaded-code kanıtı olarak kullanılmadı.

Policy env REAL_READONLY_DATA / Exness-MT5Real50 / USC, XAUUSDc metadata kimliği
ile tutarlı. Yeni adayda dört exact alias ve bridge contract/currency alanları
eşleşti; login yalnız RAM'de önce/sonra karşılaştırıldı ve loglanmadı. Bridge
API hesap ID attestation sağlamaz; iki process'in birebir account-ID belgesi
iddia edilmez. 8005 PID **9880**, başlangıç 16:54:32, cwd original PWA, global
Python311; /api/health connected=true. İlk /health yolu 404 döndü, doğru API
yoluyla tekrarlandı. 5173 PID **10320**, 8007 PID **12152** korundu.

8006 reload CLI/env veya child watcher yok; manuel PowerShell parent zinciri
korundu. Vite orijinal frontend root'undadır; /engine proxy değişmedi.
Tailscale HTTPS /engine/openapi.json HTTP200, browser allowed-host/proxy kontrolü
PASS. Tailscale konfigürasyonu değiştirilmedi. Global NumPy 2.4.6 ve mevcut
venv'ler değiştirilmedi; yeni paket kurulmadı.

## Güvenlik ve paket kapsamı

Yeni historical modül stdlib importları kullanır; bağımlılık gereksinimi değişmez.
Store varsayılan boş; JSON onayı source review yerine geçmez. Yeni startup
wrapper production reviews ve historical candidate inputs boşluğunu ayrıca
zorunlu tutar. Güncel live receipt gate artık eski SHA yerine backend 56cbd7e ve
new config hash'i ister. SOURCE_NOT_SUPPLIED/authorized=false dört gerçek aday
yanıtında doğrulandı. Spread UNAPPROVED/BLOCK ve null Entry/SL/TP/lot korunur;
gerçek bakiye sermaye yapılmaz. V2 pattern'ler DESCRIPTIVE_ONLY; veri QC nedeniyle
gerçekte boş/unavailable olabilir. Emir/order_check/login/logout veya otomasyon yok.

Gerçek 6-11 Kasım XAUUSDc/EURUSDc kanıtı hâlâ
**BLOCKED_BY_EXTERNAL_EVIDENCE**. Weekly MT5 veya genel XAUUSD saatleri Cent
sembollere taşınmadı; bu paket evidence approval içermez.

ZIP exact source/config hash manifest, RC payload/guards, 27-file backup,
baseline source/config/pins, güncel araç/plan/matrix ve seçilmiş test kanıtlarını
içerir. Archive CRC ve bütün dosyaların SHA-256 içeriği seal sırasında karşılaştırılır.
.env, credentials, account number, node_modules/venv, cache/profile veya Git history
dahil edilmez. Paket host-bound çalışma yollarını taşır; başka dizine kopyalamak
otomatik deploy değildir. Eski operasyon planları arşiv bağlamıdır; yalnız
V3_FINAL_CONTROLLED_CUTOVER_PLAN.md güncel operasyon sırasıdır.

## Dokuz net cevap ve durma noktası

1. Backend 56cbd7e release için hazır mı? **YES**, fail-closed veri analizi release'i olarak.
2. PWA RC uyumlu mu? **YES**, UI payload değiştirilmedi; old/new response parser testi geçti.
3. Tüm son kabul testleri geçti mi? Kod/aday testleri **YES**; son canlı routing preflight **BLOCKED**.
4. Backup/rollback testleri geçti mi? **YES**, original'e APPLY yapılmadan.
5. Çalışan 8006'nın gerçek exact sürümü? **VERSION_UNVERIFIED**.
6. Yeni release'i yüklemek için backend restart gerekli mi? **YES**, ayrı onayla.
7. PWA güncellemesi güvenli mi? **ŞU ANDA BLOCKED**: aynı hash/guard'lar taze preflight'ta
   geçmeli ve yeni backend receipt'i alınmalı; henüz APPLY yapılmadı.
8. Spread/historical engeller korunuyor mu? **YES**.
9. Tek operatör onayı? Exact yeni paketle yalnız 8006 kontrollü geçişi, dokuz PWA
   dosyasının APPLY/HMR adımı, smoke ve gerektiğinde doğrulanmış backup rollback/failback.

Bu noktada dış routing değişikliği nedeniyle DURULDU; geçmiş onay kullanılamaz. Önce hedef uzlaştırılmalı, ardından kullanıcının yeni operasyon onayı
gerekir. Gerçek telefon kabulü operasyon sonrası ayrıca kaydedilmelidir.

Not: Kendi compile testinin ürettiği tools/__pycache__ temizliği otomatik onay
denetiminde blocked by policy ile reddedildi. Klasör korundu; yalnız izole Git'in
local exclude kaydına alındı ve paket filtresiyle dışarıda bırakıldı.
