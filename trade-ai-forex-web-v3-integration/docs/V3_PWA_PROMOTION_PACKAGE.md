# Güvenli geçiş paketi

Durum: RELEASE_CANDIDATE_PREPARED / LIVE_NOT_PROMOTED. Yazma yetkisi yalnız izole klasör içindir. Çalışan 5173 henüz yeni UI kullanmaz.

`release/rc/manifest.json` kaynak manifesti, BASE/ISOLATED/LIVE_SOURCE hash matrisi, 9 runtime dosyasının SHA-256 ve beklenen hedef hash'lerini, 27 canlı koruma dosyasını ve envanterini içerir. `manifest.sha256` kazara bozulma kontrolüdür; dijital imza değildir. `release/rc/payload` yalnız dokuz allowlist dosyasını içerir. Git blobları LF, hedef hashleri gerçek disk baytlarıdır. Raporlardaki dosya yokluğu null/— ile gösterilir. Manifest source_head paketleme anındaki commit'i, dosya hashleri kesin payload'ı tanımlar.

Runtime listesi: AnalysisPanel.tsx/css, analysis/client.ts, analysis/contract.ts, App.tsx (chartSource prop), AnalysisNewsRisk.tsx, CalendarPanel.tsx, MarketChart.tsx (üç tek satır lazy clock düzeltmesi), RiskCalculator.tsx (transient reset/abort). NewsPanel korunur, payload değildir. Mevcut chart/news davranışı snapshot ile aynıdır; chart'ta yalnız izinli lint düzeltmesi vardır. Gelecekte tek bayt chart/news değişimi bile dry-run'ı BLOCK eder. Çatışma otomatik kopyalanmaz; yeni üç yönlü review gerekir.

Production dependencies orijinal package.json ile aynıdır; runtime aktarımı için bağımlılık eklemek gerekmez. package.json/lock içindeki Playwright dev bağımlılığı ve QA scriptleri, eslint.config.js, vite.config.ts test proxy override, tests/tools/docs runtime payload değildir. Canlı Vite yapılandırmasını ve lockfile'ı koru. Test için izole `npm ci` gerekir; node_modules arşive alınmaz. Source archive test/tool/doc/config içindir; build archive doğrulama kanıtıdır, canlı dist üzerine otomatik açılmaz. .env, credentials, Python bridge servisleri ve kullanıcı backup'ları kopyalanmaz.

## Salt okunur tek komut

İzole kökte `node tools/promotion-dry-run.mjs`. Varsayılan ve tek mod DRY_RUN_ONLY. Argüman, --apply dahil, reddedilir. Kaynak payload, manifest, hedef hash, envanter, guard coverage ve symlink/junction kontrolü yapılır. Değişiklikte BLOCK, başarılı koşuda writes=0/deletes=0. Yeni onay gerektiren canlı APPLY bu araçta uygulanmamıştır. Operatör dokuz dosyayı elle tek tek kopyalamamalı; ayrı onaylı bakım işi bu manifesti kullanarak tek kontrollü operasyonu hazırlamalıdır.

## Ayrı yetkili operasyon için sıra

1. Bu manifest/commit ve bakım penceresi için açık canlı yazma/HMR yetkisi al. Backend geçişi ayrı yetkidir. Yeni dosya hash'i varsa dur, güncel kaynaklarla yeniden paketle; manifesti elle değiştirip zorla geçme.
2. Dry-run'ı hemen önce tekrar çalıştır. Editör/diğer ajan yazmalarını bakım penceresinde durdur. Dry-run kilit veya atomik deployment sağlamaz; preflight ile yazma arasında tekrar hash kontrolü gerekir.
3. Backup kökü orijinal Vite ağacının DIŞINDA, izole `release/backups/<UTC>-<UUID>` olmalı. Overwrite yok; mevcut dokuz hedefin gerçek baytlarını, yok olan hedef listesini, manifest/hash ve 27 guard hash'ini kaydet. Backup hashlerini hedefin başlangıç hashleriyle doğrula. .env ve servis dosyalarını payload'a alma. Gerekirse ayrı yetkili dist backup al.
4. 5173 Vite aktifken src yazmak anında HMR tetikler; çok dosyalı kopya atomik değildir. Ayrı onaylı servis yönetimi/erişim kesme penceresi olmadan APPLY YAPMA. Bugünkü görev servis durdurmaz.
5. Onaylı operasyon tüm preflight'ları tamamlayıp tek seferde dosya listesini uygular, yazılan baytları kaynak hashleriyle karşılaştırır, types/build ve smoke yapar. Ara hata varsa hemen güvenli dur; kısmi sürümü kullanıma açma. Otomatik retry/force yok.
6. Backend eski kaldığında UI ret davranışı smoke kabulüdür; yeni broker/spread yetenekleri canlı çalışıyor diye işaretlenmez. 8006 yeni runtime loaded-build kabulü ayrıca gerekir.

## Restore

Tam hedef preflight yap: her uygulanmış dosya hâlâ RC hash'inde olmalı; sonradan kullanıcı değişikliği varsa STOP/REVIEW. Önceden var dosyaları doğrulanmış backup baytlarıyla geri koy ve başlangıç hashlerini doğrula. Önceden yok olan analysis dosyalarını silmek yerine backup kökündeki retained-new-files altına taşı (yalnız hâlâ RC hash'i ise); kullanıcı dosyası silme. Restore da watcher/HMR bakım yetkisi gerektirir. Restore otomasyonu bu görevde yoktur ve canlı prova yapılmadı.

## PWA/cache ve smoke

Generated SW autoUpdate/skipWaiting/clientsClaim + revisioned precache kullanır; 7 statik giriş vardır. Runtime caching tanımı yoktur. NavigationRoute index.html sunar; analiz POST'u precache değildir. Preview testi manifest standalone/scope, SW controller, cache URL'lerinde engine/mt5/news yokluğu ve çevrimdışı analiz POST'unun NETWORK_REFUSED oluşunu doğrular. Offline uygulama kabuğu eski UI tutabilir; autoUpdate açık olsa da gerçek telefonda güncel asset sürümü ve SW controller doğrulanmadan kabul verme.

Ayrı geçişte açık sekmeleri yenile, yeni SW/asset hashini kontrol et; gerekli olursa operatör onayıyla yalnız bu origin'in cache/SW kaydını temizle (diğer origin/storage'ı topluca temizleme). Tailscale HTTPS üzerinden gerçek Android/standalone kabulü henüz yapılmadı.

Smoke: 4 sembol, boş varsayımsal sermaye reddi, açık USC, tek manuel istek, çift tık tek istek, loading/timeout, sembol değişiminde abort/eski sonuç yokluğu, eski API eksik metadata için plan ret, 503 sanitizasyonu, WAIT/BLOCKED/NOT_EVALUATED ayrımı, V2 açıklayıcı-only, emir kontrolü yokluğu, chart/news/takvim davranışı. Auth/login/order/send/check kullanma. Hata halinde erişimi kapalı tut, backup restore veya review; eski API alanlarını frontend'de uydurma.

XAUUSDc exact quote/trade session kanıtı ve dört broker sembolü için operatör onaylı spread maksimum/birim/geçerlilik/provenance hâlâ eksiktir. Gözlem maksimum limit değildir; BLOCK korunur.
