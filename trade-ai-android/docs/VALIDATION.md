# 0.3.0 — güvenli gateway entegrasyonu, 26 Ekim 2026

- Başlangıç branch/PR başı `9fc92d517a002d3cb60c11c4e7c295cea0622482` ile eşleşti. PR #1 birleştirilmedi. Backend `trade-ai-v2` başı `022e3e2173f2448de089945a41956517a643eb40` salt okunur alındı; kaynak/kalıcı DB/branch değiştirilmedi.
- Bağımsız gateway: tek kullanımlık 120 s kod, 24 saatlik hashli ve iptal edilebilir cihaz oturumu; sabit 127.0.0.1:8002 proxy, izinli endpoint ve hesap kapsamı, auto_paper=false, hız/boyut/zaman sınırları, güvenli hata yanıtları.
- Android: 16 Jest grubu / 50 test, TypeScript ve ESLint başarılı. Yerel SDK/lock kontrolü 17 Expo bağımlılığını doğruladı. Android JS export başarılı.
- Tam Expo Doctor otomatik inceleme tarafından engellendi: cdp.expo.dev/exp.host isteklerinin payload'ı bilinmediğinden proje metadata'sı paylaşımı için açık izin yoktu. Offline/telemetri bayrakları Doctor isteğini engellemedi. Tekrar denenmedi; CI bu istekleri dolaylı çalıştırmamak için yalnız ağsız doctor:local kullanır. Bu kontrol Expo Doctor 20/20 diye raporlanmaz.
- Gateway: 29 pytest testi başarılı; üç test değiştirilmemiş gerçek V2 uygulamasını geçici DB ile kullanır. Python 3.12 ortamında yürütüldü; gerçek Windows/Python 3.11 çalıştırması yapılmadı.
- Android üretim API modülleri → CA doğrulamalı gerçek yerel HTTPS soketi → gateway → gerçek V2 uygulaması zinciri başarılı. Kontrollü unavailable sağlayıcı kullanıldı; gerçek piyasa veya kullanıcı PC bağlantısı değildir. Eşleştirme/replay, auth, marketler, WAIT/idempotency, analiz/geçmiş, hesap okumaları, scanner okumaları, pending notification ve kapalı gateway denendi.
- Mum grafiği aynı analysis_id, source_record_id, zaman dilimi, kaynak ve as_of snapshot'ını doğrular. RSI14 mevcut gösterge olarak, stratejideki Wilder RSI14 ayrı etiketlenir. WAIT gerekçesi gerçek reason alanından gelir.
- 401/403/expiry açık hata ve kilitli CANLI erişimi üretir; sessiz DEMO ikamesi yoktur. Eski oturum istekleri iptal edilir ve geç yanıt gösterilmez. Sanal emir yazmaları ve Native IntentJournal sınırı korunur.
- Windows/Tailscale Serve betikleri yalnız hazırlandı; gerçek ağ ayarı değiştirilmedi. Ayrı PRIVATE gateway deposu oluşturma aracı mevcut değil; kaynak ayrı git dizini ve aktarılabilir ZIP/bundle olarak teslim edilir.
- Android 0.3.0 / versionCode 4 APK başarılı: [40279469216](https://github.com/FatihBirgul/trade-ai-android/actions/runs/40279469216). APK uygulama commit'i `0e2e84ca52f27ec9116e8ade78cfe86c54307455`; artifact `12631839790`.
- İlk 0.3.0 CI denemesi, uzak lock dosyasındaki üç transitive version alanının sürüm değişiminden etkilenmesi nedeniyle npm ci aşamasında başarısız oldu. Kilit sürümleri düzeltildi; sonraki temiz kurulum, 50 test, lint/typecheck ve native derleme geçti. doctor:local artık tüm registry tarball sürümlerini de denetler.
- APK SHA-256 `2de0b556329eefd016752b3da59e33e9c29ecd279e081fa3e98ec862fa8e645c`; artifact ZIP SHA-256 `f29bcafa47991242e732898364775b11a7403ca61cf4a666257281b841efa4e3`. İndirilen dosyalar bu değerlerle eşleşti. assets/index.android.bundle bulundu; Metro sunucusuna ihtiyaç duymayan gömülü JS doğrulandı. Bu, gerçek cihazda açılış testi değildir.
- APK v2 imzası apksigner ile doğrulandı. 0.2.2 ile sertifika SHA-256 eşit: `fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c`. Telefonda yerinde güncelleme henüz denenmedi.
- Gateway bağımsız kaynak commit'i `2d5a77fa412c3394ac88ac14b421ab4dcd8ace1f`, ZIP SHA-256 `82b778284d16da5e57a687825c141b0ea0527d05673f901c19454b58b05f4363`. ZIP tam git bundle ve yalnız takip edilen kaynakları içerir; gerçek token/.env/DB/özel sertifika yoktur.
- Web önizlemede 320/360/390/412 px genişliklerde 20 sekme görünümünde yatay taşma ve JS sayfa hatası görülmedi; ETH → MANUAL → WAIT, eşleştirmesiz CANLI kilidi ve Türkçe URL hatası geçti.

**Yerel entegrasyon test edildi; gerçek telefon-PC bağlantısı bekliyor.**

Kurulum: [PRIVATE_CONNECTION.md](PRIVATE_CONNECTION.md).

## Önceki oturum kayıtları

# 0.2.2 doğrulaması — 26 Ekim 2026

- Önceki oturumun `9cacf8df2f12ee81ac699dc337cf0941786101dc` commit'i ve PRIVATE depo durumu doğrulandı. 0.2.1 kontrolleri ve APK akışı başarılı: 40240792354 / 40240792333. Artifact 12617286223.
- Çakışmayı önlemek için `codex/android-stability-20261026` dalı kullanıldı; main üzerine yazılmadı.
- Yerelde TypeScript, ESLint ve 14 Jest grubu / 45 test başarılı. Expo Doctor 20/20; Android JS export başarılı.
- Web önizlemede 320/360/390/412 px genişliklerde beş sekmenin tümü ölçüldü; yatay taşma ve JavaScript sayfa hatası görülmedi. DEMO analiz → WAIT → geçmiş, AUTO/MANUAL seçimi, duraklatılmış tarayıcı, yerel kontrol, doğrulanmamış CANLI kilidi, Türkçe geçersiz URL hatası ve açık tema tarayıcıda çalıştırıldı. Web kontrolü gerçek Android cihaz testinin yerine geçmez.
- Yerel native Android proje üretimi başarılı. Manifestte allowBackup=false, klavye adjustResize, paket com.fatihbirgul.tradeai, sürüm 0.2.2 ve versionCode 3 doğrulandı.
- Sekmelerin üst sistem çubuğu boşluğu, başlıklı sayfalarda tekrar inset eklenmemesi, dar ekran / büyük yazıda satır düzeni test edildi. Gerçek Android cihaz testi yapılmadı.
- Gateway doğrulaması AppProvider'a taşındı. Başarısız sağlık yanıtı kaydedilmez; 401/403 CANLI kilidini kapatır. Oturum silme, bekleyen bağlantı testi yarışı ve yeniden doğrulama Jest ile test edildi. Gerçek gateway kurulmuş değildir.
- Portföylerde kapanan pozisyonlar gerçekleşen PnL gösterir. Filtrelenen sayfalarda devam kararı sunucudan alınan ham kayıt sayısına göre verilir; aradaki açık kayıtlar sonraki kapalı sayfayı gizlemez. Hesap değişiminde eski istek sonucu ve yenileme hataları ayrıca test edildi.
- Analiz geçerlilik süresi, fiyat ve kritik seviyeler kontrol edilir. Açık detay ekranı süre sonunda WAIT'e döner; seviyeler kapanır. AUTO/MANUAL yanıt kapsamı denetlenir.
- **0.2.2 APK başarılı:** [40272528140](https://github.com/FatihBirgul/trade-ai-android/actions/runs/40272528140), uygulama kodu commit'i `11fc764e116fb6cfad6e4347497340071076315f`, versionCode 3, `com.fatihbirgul.tradeai`, arm64-v8a. Metro JS gömülü; geliştirme sunucusu gerektirmez. Derleme akışında 42 test ve v2 imza doğrulaması geçti. Sonraki yalnız test/belge commit'i `19d341c7133cb2640bac2c82f4d0097b7225429f` üzerinde 45 test ve GitHub kontrolleri de başarılı; bu commit APK uygulama kodunu değiştirmez.
- Artifact `12629442088`; ZIP SHA-256 `29e4e3e0a78a47736fe9ac3c22802a4be7927d3b1df1ef7303e09d3625d08884`. APK SHA-256 `2e7aff2ee45ddbdd8a64414c02cba02c2b58e5c2a4b20b30ff9dcbd41a96f98b`. İndirilen ZIP ve APK bu değerlerle eşleşti. GitHub artifact saklama sonu: 2 Kasım 2026 08:23 TSİ.
- 0.2.1 ve 0.2.2 APK v2 bloklarından çıkarılan imzalama sertifikası SHA-256 değerleri eşit: `fac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c`. Bu iki sürüm için önceki kayıttaki imza değişebilir belirsizliği giderildi. Telefonda yerinde güncelleme yine denenmedi. Bu, herkese açık varsayılan debug sertifikasıdır; mağaza dağıtımı için kişisel kalıcı imza yönetimi gerekir.
- Gerçek para işlemleri yoktur. Backend deposunda değişiklik yapılmadı; APK'ya gizli backend token'ı konmadı.
- Dahili APK debug imzalıdır. Kalıcı dağıtım anahtarı ve cihazda güncelleme testi hâlâ gerekir. APK üretimi tek başına telefonda kararlılık doğrulaması değildir.

## Önceki oturumun doğrulama kaydı

# Doğrulama — 26 Ekim 2026

TypeScript, lint, 8 test grubu / 26 test ve Expo Doctor 20/20 başarılı. Android JavaScript paketi ve native proje üretildi. GitHub ön yüz kontrolleri 38ceeb4, b24ba13, 0235b4e, f1efeb1, 57d07a2 ve 01aecb1 üzerinde başarılı.

Backend `trade-ai-v2` dalı `022e3e2`: OpenAPI, frontend sözleşmesi ve handoff belgelerinin Git blob kimlikleri yerel `docs/backend` kopyalarıyla eşleşti. 28 API modeli yeniden üretildi ve dosya farkı oluşmadı.

Web önizlemede demo analiz → WAIT, bağımsız AUTO/MANUAL bakiyeleri ve Light temanın sayfa yenilemesinde korunması kontrol edildi. CANLI seçimi aynı açılışta başarılı gateway testi yapılana kadar kilitli. Ana Sayfa, Analiz, Portföyler, Tarayıcı, Ayarlar, Analiz Geçmişi, Analiz Detayı, Performans ve Bildirimler ekranlarının 320/360/390/412 px genişliklerinin tümünde web yatay taşma ölçülmedi. Tüm ekranlarda native test yapılmadı.

Yerel APK derlemesi Java bulunmadığı için başlayamadı. İlk GitHub APK denemesi 40194096113 kaldırılmış SDK tools paketini bulamadı. Son derleme [40235920043](https://github.com/FatihBirgul/trade-ai-android/actions/runs/40235920043) başarılı: `c55f7a90b6759eca7433ad73564d52bc55e47524`, sürüm 0.2.0, Android versionCode 1, `com.fatihbirgul.tradeai`, arm64-v8a, `assembleRelease` (R8 küçültme kapalı), CI sırasında üretilmiş debug imzası, Metro JS paketi APK içine gömülü. APK imzası `apksigner verify` ile v2 olarak doğrulandı. Artifact 12615816706, ZIP SHA-256 `ab056926ac46af236b6b763326089ef093f0b264a0687e84f04b296293a960b7`; GitHub 2 Kasım 2026 00:52 TSİ tarihine kadar saklayacağını bildiriyor. ZIP içinde APK ve BUILD_INFO.txt bulunur. Gerçek telefonda kurulum/açılış henüz denenmedi.

Gerçek cihaz/emülatör ve backend bağlantısı test edilmedi. Gateway kurulmuş değil. Sanal emir oluşturma arayüzü kapalı; SecureStore işlem günlüğü adaptörü Jest ile sınandı, gerçek cihaz ve gateway ile uzlaştırma eksik. Tema tercihi native SecureStore'da saklanıyor; yeniden açılış davranışı Jest ve web yenilemesiyle doğrulandı, gerçek cihazda henüz denenmedi. 19 referansın yalnız 10 görüntüsüne erişilebildi.

npm audit --omit=dev: Expo araç zincirinde 5 yüksek seviyeli bağımlılık bulgusu var; uyum bozacak zorunlu yükseltme uygulanmadı. Yayın öncesi yeniden değerlendirilmelidir.

Debug anahtarı CI sırasında üretilir ve kaynak deposuna kaydedilmez. Farklı derlemelerin imzası değişebilir; yeni dahili APK mevcut kurulumun üstüne yüklenemeyebilir. Kalıcı yükseltme yolu için güvenli CI secret veya EAS kimlik bilgisi yönetimi gerekir.

Backend deposunda yazma yapılmadı. Mobil depoya gizli backend token'ı eklenmedi. Normal commit/push ile geçmiş korundu.

## Task 5 / 0.4.0

- TypeScript, ESLint, 73 Jest testi (18 suite) ve 17 ağsız SDK kontrolü başarılı.
- Ayrı gateway kaynağı: FatihBirgul/trade-ai-gateway, 0.1.1. 35 yerel pytest geçti;
  6 test değişmemiş V2 uygulamasını geçici fixture DB ile kullanır. Test matrisi
  BTC/ETH/SOL × altı zaman dilimi, dört strateji, kalite WAIT, immutable snapshot,
  scanner/outbox ve create/cancel/queued-close/fill/recovery içerir.
- Gerçek üretim Android API modülleri → sertifikası doğrulanan yerel HTTPS gateway
  → gerçek V2 uygulaması zinciri iki senaryoda geçti: sağlayıcı kapalı WAIT;
  açıkça kontrollü sentetik test girdisi ile analiz/MTF/snapshot, tarayıcı,
  pending outbox ve kalıcı test günlüğü recovery. Gerçek fiyat bağlantısı değildir.
- Paper yazma bayrakları APK/AppProvider ve üretim gateway CLI'de kapalıdır.
  Gerçek telefon SecureStore/idempotency/hesap kalıcılığı doğrulanmadan açılmaz.
- İlk Task 5 CI denemesinde lock kök sürümünün aktarımda atlanması Doctor local
  tarafından yakalandı; sonraki commit'te yalnız kök sürümü düzeltildi. Bağımlılık
  sürümleri değişmedi. İlk hatalı deneme başarılı olarak sayılmaz.
- Tam çevrimiçi Expo Doctor çalıştırılmadı. Backend kodu/branch/kalıcı DB ve
  kullanıcının ağ ayarları değiştirilmedi. PR #1 birleştirilmedi.

## Premium scanner / brand continuation (2026-11-03)

Base: Android PR13 `d3a2e9ddccef7fe507dc43977147897a08c14ff7`;
Backend PR15 `4e5bb9bb3b5079bc7a8201a7b16b202ff6db8249`;
Gateway PR9 `d1c0e4d2263626a30e81af9e2b40d5e952cb7b76`.
No API, financial formulas, host process control or execution grants changed.

- `MarketCataloguePicker` uses the production catalogue, bounded search/filtering,
  current-account last-20 saved analyses and safe favorite removal during outages.
  Unknown/delisted/non-spot instruments cannot be added. Favorites remain passive
  edits until the existing explicit save; account activation is a separate action.
- `ScannerHealth` / `scannerHealth` distinguish explicit diagnostic evidence,
  current observations and unknown network failures. A generic network error does
  not prove phone offline, Gateway failure or PC shutdown. OFFLINE requires a trusted
  network observation; no physical network sensor or external monitor was installed.
  Gateway-unavailable requires an explicit diagnostic, not a fetch inference.
  A fresh configuration GET does not make an old provider scan fresh. The local
  30-second display clock makes cached observations stale without sending requests.
  Failure duration is approximate, begins with this screen's first failed observation,
  resets per account/session, and is not the true outage duration.
- Opportunity filters and duplicate-ID selection operate only on the current bounded
  server page, choosing the newest observation before filtering. TTL/source age warns
  about old data without inventing an EXPIRED lifecycle event. Previous analysis
  records remain immutable. Account scan enablement is separate from host worker health.
- Existing named configuration, frozen strategy revision/MTF roles, off/selected-
  profile/supported-markets modes, lost-ACK replay, explicit activation and permission
  gates are preserved. No startup writes, process-start endpoint or AUTO grants.
  One current scan configuration/account; not an arbitrary multi-profile scheduler.
- `assets/brand` contains reviewed SVG + 1024 PNG T assets, SHA manifest and distinct
  foreground/background/monochrome layers. Optional `generate-brand.cjs` requires
  Sharp only as a design tool; committed assets require no new app dependency.
  This is an interpretation of the supplied concept6 description, not a trace of
  an unavailable original image. `BrandMark` is shown on home/settings. Package and
  signing policy unchanged; internal0.7.6/code15 distinguishes the new test build.
- `verify-brand.py` binds source hashes/config, generated native launcher + round
  adaptive references, and the actual APK's compiled foreground/background/monochrome
  resource graph. Generated Expo WebP alpha silhouettes matched approved PNGs in
  disposable prebuild (IoU1.0). This is not physical launcher testing.

Validation at code checkpoint: 213 Jest tests /47 suites, TypeScript, ESLint,
17 local Expo compatibility checks and10 Python APK/brand tool tests passed.
Android JS export/native CI and exact APK evidence are recorded in the new PR
once completed; do not infer success from this note. Online Expo Doctor, physical
installation/update, live provider throughput, real push and Windows autostart remain
UNVERIFIED. No PC, phone, live DB, service or private network was accessed.

Next: verify the exact pushed native artifact against previous actual0.7.5 certificate,
package/version/JS/fonts and icon resources. Then a separately authorized physical
light/dark, small-screen, session continuity and launcher-shape check. Older Gateways
remain fail-closed through the existing capability/readiness gates.

## Final Android UX Polish

Newest Android handoff: [NEXT_ACTIONS](NEXT_ACTIONS.md). Baseline0.7.6/code15 kept.
Internal candidate0.7.7/code16 changes Android only, no Backend/Gateway API/financial
code. Native splash regression: real baseline APK has white splash color and grey
Expo grid resource; source/native checks now require dark day/night + Android12
Theme.SplashScreen + unchanged T + post-splash dark window + MainActivity binding.
This establishes a resource-level root cause/correction, not observed phone timing.

Font-error regression was red before implementation: navigation never appeared after
font load error. Now error/timeout opens text navigation. Tests cover theme timeout,
late response, failed session read, slow server entry, safe retry, system appearance
and no requests without credentials; unchanged worker/grants regressions preserved.
Lazy research test measures0 catalogue calls before evidence expansion/1 afterward,
not a device latency claim. Main styles use48dp controls and readable shared tokens.

Before/after WEB renders, same360x800 demo state:
- [Home before](ux-before-home-dark.png) / [after](ux-after-home-dark.png)
- [Result before](ux-before-result-dark.png) / [after](ux-after-result-dark.png)
- [React startup with controlled font stall](ux-react-loading-controlled.png)
- [Previous decoded native resource](ux-native-resource-before.png) /
  [new generated native resource](ux-native-resource-after.png)

The last pair contains raw drawables, not screenshots of a native splash. No attached
video, emulator or physical device: native visual transitions, splash mask/animation,
cold/warm/relaunch/update/SecureStore continuity remain UNVERIFIED. No fabricated
before/after native footage or startup-duration performance estimate.

Screen coverage: home, analysis, result, scanner/discovery, portfolio and settings in
both web themes;320/360px smoke/overflow and lazy evidence interactions. Other existing
screens retain routes/shared tokens; unit regression package protects their behavior.
Local223Jest/49 suites, TS/lint,19Expo compatibility checks, both exports and16Python
tools passed. Exact CI/APK/source and remaining warnings in the dependent Draft PR;
complete native verification before declaring APK delivery. Existing logo hashes
unchanged; required native modules and related build-tool patch updates are explicit.

Final native/e2e evidence verified: APK source41e47d013b1c9881ba4ffda62ddfcea91677988a,
internal0.7.7/code16, SHA256365f54a9556efdc9cfb441c1d82524a40618b0dfbf1677c4f4d264f320b4153b; native41600894140/frontend41600968167
successful. Actual previous0.7.6 certificate matches; compiled dark splash and actual
T raster variants independently checked. Exact artifact/expiry and limitations are
in newest NEXT_ACTIONS and FINAL_ANDROID_UX_ACCEPTANCE.json. Physical native visual
transition/update/phone performance remain UNVERIFIED. No further cosmetic milestone
is planned; return to core functional/security/reliability engineering.
