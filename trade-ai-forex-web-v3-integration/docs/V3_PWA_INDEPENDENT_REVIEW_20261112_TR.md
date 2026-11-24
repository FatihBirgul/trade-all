# PWA son kabul — 12 Kasım 2026

Sonuç: **BLOCKED — CONCURRENT_RUNTIME_CHANGE / LOADED_FINGERPRINT_UNVERIFIED**. Bu inceleme yalnız izole PWA deposuna yazar. Canlı APPLY yetkisi yoktur. Yeni paket, önceki READY/BLOCKED paketlerden ayrı `release/final-pwa-review-20261112-01` dizininde hazırlanır; ZIP SHA-256 değeri bitişik `.zip.sha256` dosyasındadır.

**A / P — Git.** Başlangıç HEAD: `864bd603ffd27000b2d78e94ab848d6b649ebec9`. İnceleme araçları, yeni regresyon testi ve bu rapor ayrı yerel commit'e alınır. Bitiş HEAD ve çalışma ağacı durumu `end.json` içindedir. Önceden mevcut runtime uzlaştırması ve diğer iş akışının commit edilmemiş dosyaları korunur. Paket içeriğinin kesin kimliği PWA HEAD ile birlikte dosya SHA-256 manifestidir; çalışma ağacının temiz olduğu iddia edilmez.

**B — Üç yönlü AnalysisPanel incelemesi.** BASE `01c96bb950804ed11fdb512937a81b554ddd669c`, ilk Git snapshot nesnesidir. CURRENT orijinal PWA'nın güncel baytlarıdır. RC izole manuel analiz ekranıdır. Üç kaynağın hash ve snapshot'ları pakette bulunur. Orijinalin Git geçmişi olduğu veya otomatik merge yapıldığı iddia edilmez.

| CURRENT–BASE değişikliği | Kategori | RC sonucu |
|---|---|---|
| Veri yetersiz/güncel değil/kaynak yok/piyasa kapalı/engelli durumlarını WAIT'ten ayırma | Bug fix, API uyumu, güvenlik | Ayrı karar etiketleri ve veri/uygunluk alanları korunmuş |
| İki tarihsel mum boşluğu nedeninin Türkçe açıklaması | Bug fix, güvenlik | Aynı açıklama `explainReason` içinde korunmuş |
| REAL MT5 / SALT OKUNUR etiketi | Kullanıcı tercihi, Risk/USC | Korunmuş; fixture sonucu açık TEST etiketi taşır |
| BOM farkı | Dosya kodlaması | Anlamsal özellik değişikliği sayılmaz |

RC'nin manuel istek, loading, timeout, explicit cancel, sembol/zaman değişiminde abort, geç yanıtı atma ve input değişiminde sonuç temizleme davranışları korunur. Kullanıcının USC ve risk taslakları sembol/zaman değişiminden sonra kalır. Yeni regresyon testi, bekleyen analiz sırasında sermaye değişince eski yanıtın atıldığını ve yeni tutarın yalnız yeni düğme tıklamasıyla gönderildiğini doğrular.

**C — Dış değişikliklerin korunması.** Güncel App'in 19 grafik seçeneği ve MarketChart'ın tüm JPY çiftlerinde üç ondalık düzeltmesi izole RC'de bulunur. Bunlar dört sembollü V5 kapsamını genişletmez. Yeni 15 grafik sembolünde analiz ve risk hesaplama kapalıdır. NewsPanel payload dışındadır. AnalysisNewsRisk/Calendar'ın mevcut davranışı korunur; RC'deki lazy clock lint düzeltmeleri pakette kalır. Güncel hedefteki NewsPanel, bridge dosyaları, paket/lock, Vite proxy ve var olan yedek dosyaları değiştirilmez. Başka iş akışında hazırlanan rapor/araçlar silinmez veya bu incelemeyle üzerlerine yazılmaz.

**D / E / F / G — Analiz ve güvenlik.** XAUUSD, EURUSD, GBPUSD, USDJPY; BUY/SELL teknik aday, WAIT, INSUFFICIENT_DATA, BLOCKED, null Entry/SL/TP/lot, NOT_EVALUATED, broker contract kimliği, kaynak hash'i, API 503, timeout ve iptal davranışları fixture testlerinde doğrulanır. Double Top/Bottom ve mum formasyonları DESCRIPTIVE_ONLY kalır; null/boş/uyuşmayan kaynak hayalî formasyon üretmez. Sermaye kullanıcı girdili varsayımsal USC'dir. REAL_READONLY_DATA ve execution_permission=false güvenliği korunur. Onaysız spread ile tarihsel Exness kanıtı eksikliği planı kapatır. Eksik kanıt kabul edilmiş veya gözlenen spread onaylı limitmiş gibi sunulmaz. Quote/trade seansı ve grafik/analiz kaynağı aynı şey sayılmaz. Minimum lot reddinde plan gösterilmez.

**H — Canlı 8008.** Backend diskte `56cbd7e05a40b106deda9298e2be28b488d0d952`, temizdir. Başlangıçta 8008 listener'ı yoktu; doğrudan health/schema başarısız ve 5173 engine health 502 idi. Bitişte dış iş akışı 8008'i PID 12152 ile başlatmıştı (12 Kasım 17:04:31 İstanbul); health/schema ve proxy health 200 oldu. Başlangıç/bitiş süreç eşitliği bu nedenle FAIL/BLOCKED'dır. Yeni çalışma dizini trade-ai-v3-runtime-candidate olarak gözlendi; loaded fingerprint doğrulanmadı. Canlı analiz isteği gönderilmemiştir. Önceki gerçek yanıt kayıtları yalnız geçmiş uyum regresyonu olarak sınanır. Önceki loaded fingerprint `314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b` güncel süreç kanıtı değildir; manifestte current fingerprint null'dır. Yeni PID veya runtime baseline otomatik kabul edilmez.

**I / J — Kalite kapıları.**

| Kontrol | Bu incelemede sonuç |
|---|---|
| TypeScript + Vite/PWA production build | PASS |
| Tam proje ESLint | PASS |
| Temel client | 42/42 PASS |
| Ek client / eski-yeni paket / apply-rollback fixture güvenliği | 63/63 PASS |
| Canlı kabul validator birim testleri; canlı istek değildir | 12/12 PASS |
| Tarayıcı: mevcut 34 + uzlaştırma 6 | 40/40 PASS |
| Yeni USC bekleyen istek regresyonu, production preview | 1/1 PASS |
| Production preview / cache / allowed-host | 3/3 PASS |
| Ayrı origin eski-yeni SW, offline/cache/manifest | 7/7 PASS |
| 390×844 emülasyon ve uzun BLOCK mesajı | PASS; görüntü görsel incelendi |
| Fiziksel telefon | NOT_TESTED |
| Güncel gerçek 8008 kabulü | BLOCKED_CONCURRENT_RUNTIME_CHANGE / NOT_TESTED |

Testler canlı servis portlarını hedefleyen süreç başlatmaz veya kapatmaz. Fixture servisleri dinamik ayrı portlardadır; yalnız testin başlattığı süreçler kapatılmıştır. Fixture verisi canlı broker analizi olarak sunulmaz. Test logları ve tarayıcı sonuçları pakete eklenir. Önbellek kontrolü ilk çıkarılan bağımsız testteki hata düzeltildikten sonra 7/7 geçti; ilk hata araç çıktısında raporlandı; teslim logu düzeltilmiş son çalıştırmaya aittir.

**K / L — Manifest ve dry-run.** Dokuz runtime dosyası: AnalysisPanel.tsx/.css, analysis/contract.ts, analysis/client.ts, App.tsx, AnalysisNewsRisk.tsx, CalendarPanel.tsx, MarketChart.tsx, RiskCalculator.tsx. Kaynak/hedef SHA-256, her dosyanın diff'i ve conflict matrix pakettedir. Varsayılan araç DRY_RUN'dır: 0 hedef yazma, 0 silme. AnalysisPanel/NewsPanel/MarketChart/proxy dahil herhangi bir hedef guard veya envanter farkında durur. Yeni bir AnalysisPanel değişikliği yeni APPLY için BLOCK gerektirir. CLI `--apply` reddeder. Bu pakette deployment_readiness BLOCKED olduğundan ayrı bir boolean onayla bile canlı apply kapısı açılmaz.

**M — Backup/rollback.** Başlangıçtaki tüm orijinal src/public/config/bridge ve `.bak` baytları izole `snapshots/current` yedeğine alınır ve tekrar SHA-256 doğrulanır. Canlı apply yedeği oluşturulmuş sayılmaz. Fixture testlerinde tam/yarım aktarım, başarısız smoke sonrası geri alma, yedek bozulması ve eşzamanlı kullanıcı değişikliğinde güvenli durma doğrulanmıştır. Gerçek aktarım öncesinde yeni manifest onayı, hash-guard ve doğrulanmış operasyon yedeği gerekir. Rollback yalnız onaylı manifest ve receipt hash'leriyle; yeni dosyaları silmeden yedekte tutarak çalışır. Kullanıcının sonradan değiştirdiği baytlar ezilmez.

**N — Yeni paket.** `release/final-pwa-review-20261112-01.zip`, aynı isimli SHA dosyası, manifest/diff/snapshot/test logları ve production preview build içerir. ZIP CRC ve her arşiv girdisinin SHA-256 değeri kaynak paketle karşılaştırılır. Bu, BLOCKED inceleme/RC paketidir; canlıya hazır release iddiası taşımaz. Önceki paketlere yazılmaz.

**O — Servisler.** Başlangıç PID'leri: 5173=8592, 8005=1676, 8006=8804, 8007=6592, 8008=yok. UTC start time, kaynak dizini ve salt okunur health kanıtı begin/end.json içindedir. 5173 kaynağı orijinal PWA'dır. 8005/8006/8007 health erişilebilir. `/engine → http://127.0.0.1:8008` ve Tailscale allowed host korunmuştur. Bitişte 5173/8005/8006/8007 PID/start/source eşitliği PASS; 8008 yok → PID 12152 geçişi nedeniyle toplam servis eşitliği BLOCKED. Orijinal ve izole runtime kaynak hash eşitliği PASS. Kanıt preservation.json ve end.json içindedir. Bu görev hiçbir servisi yeniden başlatmaz.

**Q / R — Operasyon sınırı.** Push/merge, emir/order_check/order_send, otomatik tarama, backend değişikliği, proxy/Tailscale değişikliği, 5173 HMR veya canlı APPLY yapılmadı. Orijinal kaynak hash'lerinin başlangıç/bitiş eşitliği doğrulanır.

**S / T — Kalan engeller ve tek operasyon onayı koşulları.** Dış iş akışında yeniden başlayan 8008'in yeni sürecinin SHA/173-fonksiyon loaded fingerprint/startup kimliğinin doğrulanması; direct/proxy health/schema eşitliği; dört sembollü güncel gerçek salt okunur kabul; beş servisin taze kimlik kaydı; hedef dosya guardlarının tekrar geçmesi gerekir. Bunlardan sonra yeni READY manifesti, hash'i, backup/rollback/smoke planı üzerinden yalnız 5173 kaynak aktarımı için ayrı açık onay istenir. Mevcut onaysız spread/tarihsel kanıt engelleri bu işlemle kaldırılmaz. Fiziksel telefon sonucu hâlâ NOT_TESTED olarak açıklanır.

HMR ve cache planı: bu görevde canlı kaynak kopyalanmaz. Gelecekte onaylı dokuz kaynak dosyasının dev-server aktarımı HMR/yeniden yükleme tetikleyebilir; açık analizin sıfırlanması ve tutarlı final kaynak hash'i smoke ile kontrol edilmelidir. Vite config korunur, servis restartı bu PWA aktarımına dahil değildir. Production build ayrı staging'de doğrulanır; SW autoUpdate eski shell'i değiştirebilir. İlk açılış/offline shell/yeniden çevrimiçi analiz ve API yanıtlarının cache'e girmemesi kontrol edilir. Bu fixture SW sınaması gerçek cihaz ve mevcut canlı origin'deki tüm önbellek geçmişi için kanıt değildir.

Son beş cevap: **YES / PARTIAL / YES / PARTIAL / NO**.
