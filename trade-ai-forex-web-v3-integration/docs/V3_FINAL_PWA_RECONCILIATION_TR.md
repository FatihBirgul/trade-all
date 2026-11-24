# TRADE AI V3 — final PWA uzlaştırması ve canlıya geçiş değerlendirmesi

11–12 Kasım 2026, Europe/Istanbul. **Sonuç: BLOCKED_CONCURRENT_CHANGE / UNVERIFIED_NEW_8008_RUNTIME.**
AnalysisPanel uzlaştırması ve izole kaynak/fixture kalite kontrolleri tamamlandı. Son gözlemde
önce 8008 listener'ı bulunmadığı, ardından beklenmeyen PID12152 ile düz uvicorn süreci görüldüğü ve
diğer dört servisin PID'leri değiştiği için READY paketi üretilmedi.
Yeni başlangıç durumu otomatik kabul edilmedi. Canlı APPLY/HMR veya servis müdahalesi yapılmadı.

**A. Git HEAD.** Başlangıç HEAD'i `864bd603ffd27000b2d78e94ab848d6b649ebec9`.
Bu görev değişiklikleri izole depoda ayrı yerel commit'tedir; yeni exact SHA paket
`manifest.json/source_head` ve teslim mesajındadır. Önceden mevcut, commit edilmemiş runtime/bridge
audit dosyaları korunmuş ve bu PWA commit'ine katılmamıştır. Orijinal PWA Git deposu değildir.
Çalışma sırasında ayrı inceleme commit'i `903a1898728081ade10bd2f5e00c1725dd6ab46e` eklendi;
bu commit yalnız dört yeni inceleme/test/araç dosyası ekler, src/proxy/package değiştirmez.
Commit ve dosyaları korundu; görev commit'i bu HEAD üzerine, yalnız seçilmiş PWA değişiklikleriyle alınır.

**B. AnalysisPanel üç yönlü çözümü.** BASE, ilk snapshot'ın gerçek Git nesnesidir:
`01c96bb950804ed11fdb512937a81b554ddd669c`; CURRENT, başlangıçta orijinalden kopyalanan gerçek
baytlar; RC, izole manuel analiz ekranıdır. Her üçünün snapshot'ları ve SHA'ları pakettedir.
Bu, orijinalin Git geçmişi iddiası veya sahte otomatik merge değildir.

CURRENT–BASE diff'inde üç anlamlı değişiklik vardı:

| Değişiklik | Kategori | RC'de çözüm |
|---|---|---|
| INSUFFICIENT_DATA/STALE/PROVIDER_UNAVAILABLE/MARKET_CLOSED/BLOCKED ayrımı; her durumu WAIT göstermeme | Bug fix, API uyumu, güvenlik | Ayrı durum başlıkları ve risk/veri alanları korundu |
| İki tarihsel mum boşluğu gerekçesinin Türkçe açıklaması | Bug fix, güvenlik | Kullanıcının açıklaması reason çeviricisine alındı; doğrulanmış seans kanıtı yokluğu belirtildi |
| MANUEL DEMO yerine REAL MT5 / SALT OKUNUR etiketi | Kullanıcı tercihi, risk/USC, güvenlik | Gerçek kaynak için korundu; fixture için açık TEST etiketi kullanılır |

CURRENT'in kullanıcı girdili USC/%risk, manuel Analiz Et, iptal/context temizleme, fiyat saati,
motor entegrasyonu, haber riski ve uyarı davranışları korunmuştur. Sermaye/risk taslağı sembol ve
zaman değişiminde tutulur; eski sonuç ve pending istek temizlenir. RC'nin dört sembol, timeout,
race guard, V2 betimleyici gösterim, source provenance, null plan ve güçlü risk kontrolleri korunmuştur.
Zayıf eski `ELIGIBLE` kontrolü tek başına işlem izni olarak geri getirilmemiştir.
Yeni explicit İptal düğmesi yalnız isteği iptal eder; retry veya tarama başlatmaz.
UI düzeni manuel analiz RC'sidir; orijinal panel körlemesine üzerine kopyalanmadı.

**C. Dış değişiklikler.** Orijinal App'teki 19 grafik sembolü izole App'e taşındı;
MarketChart'taki tüm JPY çiftleri için `endsWith('JPY')` ondalık düzeltmesi korundu.
RC'nin chartSource bağlantısı ve lazy clock düzeltmesiyle birleştirildi.
NewsPanel orijinalle aynı baytlardadır ve payload dışında tutulur. AnalysisNewsRisk/Calendar'da
yalnız mevcut lazy clock düzeltmeleri kullanılır; haber/takvim işlevi değiştirilmez.
Bridge, news bridge, package/lock ve aktif Vite proxy hedef dosyaları payload dışındadır.
Tüm dosyaların BASE/CURRENT/RC hash'leri, kategorileri ve kararları conflict-matrix.json'dadır.

**D. Dört sembollü manuel analiz.** XAUUSD, EURUSD, GBPUSD, USDJPY desteklenir.
19 grafik seçeneği V5 kapsamı değildir; diğer 15 sembolde Analiz Et ve risk önizlemesi kapalıdır.
Analiz yalnız düğmeye basınca gönderilir. Loading, timeout, explicit cancel, context abort,
geç yanıtın yok sayılması, double-click tek istek ve otomatik retry yapılmaması test edilmiştir.
BUY/SELL teknik aday olarak etiketlenir; WAIT, NO_TRADE, INSUFFICIENT_DATA, BLOCKED ayrıdır.

**E. V2.** Mum/Double Top/Double Bottom yalnız AVAILABLE + DESCRIPTIVE_ONLY + tutarlı kaynak
kimliğinde gösterilir. Null veya kaynak uyumsuzluğu halinde hayalî formasyon oluşturulmaz.
Fixture verileri TEST olarak işaretlidir; sentetik tarihsel onay broker kanıtı değildir.
Canlı 8008'in önceki güvenli ret yanıtlarında formasyonlar null'dır; üretildiği iddia edilmez.

**F. USC.** Varsayımsal sermaye ve risk girdisi korunur. API'ye hypothetical_capital,
hypothetical_currency=USC ve risk_pct gönderilir; broker gerçek bakiyesi kullanılmaz.
NOT_EVALUATED emir onayı değildir. Geçersiz tutar/para birimi, minimum lot reddi ve null lot
planı gizler. Legacy manuel risk paneli ayrı /mt5 yolundadır; V5 izin kapısı sayılamaz.

**G. Spread/tarihsel kanıt.** Spread UNAPPROVED/BLOCK veya eksik broker/risk/source alanları
uygulanabilir plan üretmez. Yeni historical_session_evidence alanı korunup gösterilir.
HISTORICAL_SOURCE_VERIFIED + historical_gap_authorized=true + cross_source_reconciled=true ve
evidence_ids bulunmadıkça frontend planı kapatır. Bu değerler frontend tarafından üretilmez.
Gerçek backend kaynağı sağlanmamış kanıt için BLOCKED_BY_EXTERNAL_EVIDENCE gösterilir.
Entry/SL/TP/lot gizlenir; kaynak yokluğu doğrulanmış Exness seansı gibi sunulmaz.
Grafik quote'u, analiz snapshot'ı ve broker seans durumu ayrı açıklanır.

**H. 8008 uyumu ve engel.** Başlangıçta PID9792, backend56 ve
`314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b` loaded-code fingerprint'i
same-process startup kaydıyla yeniden doğrulandı. Gerçek dört sembolün yanıtları client tarafından
okundu; izole 390×844 arayüzden dört manuel gerçek 8008 isteği de önce başarılıydı.
Bu önceki başarı kanıtları son durumun başarı kanıtı olarak kullanılmamaktadır.

Son gerçek HTTP tekrarında isolated Vite üzerinden 503 alındı. İlk takip gözleminde 8008 bağlantısı yok,
aktif 5173 /engine health proxy'si 502 idi. OS son açılış zamanı 12 Kasım 12:11:51;
diğer dört mevcut süreç yaklaşık 13:09'da başlamış. Bu kayıtlar süreç değişimini gösterir;
aktör veya 8008'in neden başlamadığı hakkında kesin neden çıkarılmaz.
Sonraki 17:11 gözleminde 8008 PID12152 (başlangıç 17:04:31.763187) ve proxy health OK bulundu.
Sanitized launch düz `uvicorn forex.api:app`, attested launcher değil; cwd eski runtime-candidate'dır.
Ortamda REAL_READONLY_DATA/Exness-MT5Real50/USC bildirimi bulunması exact loaded-code kanıtı değildir.
Bu süreç görev tarafından başlatılmadı veya yeni baseline olarak kabul edilmedi.
Backend HEAD56 ve orijinal kaynaklar aynı olsa da PID9792'nin eski startup JSON'u yeni sürecin kanıtı değildir.
Güncel fingerprint manifestte null/UNVERIFIED; eski doğrulanmış fingerprint yalnız ayrı referans alanındadır.
8008 başlatılmadı/restart edilmedi, proxy8006'ya çevrilmedi.

**I. TypeScript/lint/build.** Tam proje ESLint, TypeScript `tsc -b` ve Vite/PWA build PASS.
Runtime bağımlılığı değişmedi. İzole Playwright dev aracı orijinal package/lock'a taşınmaz;
bu paketin npm install veya global Python/NumPy değişikliği yoktur.

**J. Testler.**

| Grup | Sonuç / kapsam |
|---|---|
| Önceki client regresyonu | 42/42 PASS |
| Ek historical/USC/source/min-lot ve recorded-runtime client | 13/13 PASS |
| Eski+yeni dry-run/backup/rollback/guard regresyonu | 62/62 PASS; tamamen fixture hedefleri |
| Tarayıcı regresyonu + uzlaştırma | 40/40 PASS |
| Production preview/cache/allowed-host proxy sözleşmesi | 3/3 PASS |
| Eski→yeni SW, eski cache temizliği, offline shell/API reddi | 7/7 PASS; disposable origin, final build |
| Gerçek8008 mobil ilk tur | 4/4 önceki PASS; artık güncel hazır olma kanıtı değil |
| Gerçek8008 mobil son tekrar | FAIL: HTTP503; önce listener yokluğu, sonra yeni unverified PID görüldü |

390×844 viewport ve uzun hata/BLOCK metinlerinde yatay taşma yok; NewsPanel ve MarketChart
korunuyor. Görseller kontrol edildi. **Fiziksel telefon testi yapılmadı**; PASS iddiası yoktur.
Tailscale allowed-host ve aynı origin proxy sözleşmesi izole sunucuda test edildi;
gerçek uzaktaki telefon/tünel erişiminin son durumda çalıştığı iddia edilmez.

**K. Source/target manifest.** Güncel RC payload, source-manifest.json; başlangıçla aynı kalan
orijinal hedef dosyalar destination-manifest.json; tam karşılaştırma conflict-matrix.json ve diffs/.
Her manifest gerçek SHA-256 baytlarını kullanır. CRLF/BOM normalize karşılaştırma yalnız diff
yorumlamak içindir; operasyon guard'ı gerçek bayt hash'idir. Allowlist **9 dosya**, hedef guard'ı **27**.
Vite config kopyalanmaz: aktif /engine→8008 korunur. İzole config default8008'e düzeltildi;
testlerin explicit izole proxy override'ı vardır.

**L. Dry-run.** Yeni araç varsayılan DRY_RUN, 0 yazma, 0 silmedir. Kaynak ve hedef hash'i,
inventory, allowlist ve symlink/junction kontrolleri vardır. Orijinal AnalysisPanel/MarketChart/
NewsPanel/proxy veya bridge yeniden değişirse BLOCK üretir. Kaynak dry-run geçse bile deployment
durumu BLOCKED kalır. CLI gerçek APPLY kabul etmez; ayrıca yetkilendirilmiş operasyon gerekir.
Programmatik apply/rollback fixture'da sınanmıştır; gerçek hedefte explicit yeni manifest onayı,
READY durumu ve taze runtime guard'ı olmadan yazmaz.

**M. Backup/rollback/cache planı.** 27 hedef dosyanın ayrı izole yedeği gerçek hash'lerle
doğrulandı. Gerçek APPLY öncesinde tekrar taze backup alınmalıdır. Smoke hatasında kısmi/tam
aktarımı eski baytlara döndürme sınandı. Yeni dosyalar silinmez; retained-new-files'a taşınır.
Kullanıcının eşzamanlı yeni değişikliği veya bozuk backup varsa otomatik rollback durur.
Bağımlı modüller önce, App en son yazılacak şekilde sıra bellidir; HMR etkisi ayrıca onaylanmalıdır.
Mevcut 5173 Vite source/HMR yoludur; preview dist ve worker testi production-build kanıtıdır.
Source kopyalamak tek başına bir fiziksel telefondaki eski production worker'ı güncelleme garantisi değildir.
Canlı smoke'da yeni source/UI, manifest/worker/cache ve offline API reddi ayrıca doğrulanmalıdır;
kullanıcının mevcut cache'leri bu görevde temizlenmedi.

**N. Arşiv.** READY frontend ZIP'i üretilmedi. Yeni benzersiz **BLOCKED_EVIDENCE** arşivi
uzlaştırılmış aday, manifest/diff/backup/test ve blocker kanıtlarını içerir; deployable=false.
Exact ZIP adı/SHA sidecar'da ve teslim mesajındadır. Eski READY/BLOCKED/runtime ZIP'lerine yazılmadı.

**O. Servis başlangıç→sonuç.**

| Port | Başlangıç PID | Son PID | Son gözlem |
|---|---|---|---|
| 5173 | 10320 | 8592 | Orijinal PWA cwd; son /engine health OK |
| 8005 | 9124 | 1676 | connected=true |
| 8006 | 8284 | 8804 | health OK / mt5 |
| 8007 | 12152 | 6592 | news erişilebilir |
| 8008 | 9792 | 12152 | Health OK; düz uvicorn, exact loaded-code UNVERIFIED |

Başlangıç/bitiş OS creation kimlikleri begin.json/end-blocked.json içindedir.
İlk dört sürecin başlangıcı 12 Kasım 13:09:54–13:09:59 aralığındadır; yeni8008 17:04:31'de başlamıştır. Görev yalnız kendi izole test
süreçlerini başlatıp kapatmıştır; beş servis portu test process stop hedefi yapılmamıştır.

**P–R. Commit/push/canlı dosyalar.** PWA kaynak ve test/araçları izole depoda yerel commit'e
alındı. Push/merge yok. Orijinal PWA/backend dosyaları başlangıç hash'leriyle aynıdır.
Canlı APPLY, 5173 HMR tetiklemesi, proxy/Tailscale değişikliği veya gerçek/demo emir yoktur.

**S. Kalan engeller.** Güncel 8008 onaylı PID9792 yerine unverified PID12152'dir ve dört korunan servisin süreç başlangıçları değişmiştir.
Bu görev bu durumu kabul etme veya runtime restore yetkisi vermez. Fiziksel telefon yapılmadı;
güncel uzak Tailscale+8008 e2e kabulü de yapılmış sayılmaz. Bunlar fixture PASS ile örtülmemiştir.

**T. Tek PWA operasyon onayından önce.** Yeni8008 sürecinin ayrıca değerlendirilmesi; gerekiyorsa
ayrı yetkili runtime işlemiyle exact56 source/dependency/startup/loaded fingerprint + REAL/USC/no-order/spread/historical kabulü,
yeni servis kimliklerinin ayrıca değerlendirilmesi ve taze dört sembol client/browser kontrolü gerekir.
Sonra değişmeyen hedef kaynak hash'leriyle yeni READY manifest/ZIP mühürlenebilir.
Onay, yalnız bu exact yeni ZIP+manifest ve 9 source dosyalı frontend aktarımı/HMR/backup/rollback
kapsamını açıkça bağlamalı; backend, bridge veya diğer servisleri kapsamaz. Şu anda PWA APPLY'e geçilmez.

**Beş cevap:** 1) AnalysisPanel çözüldü: **YES**. 2) Canlı8008 uyumu: **PARTIAL** — sözleşme/önceki
gerçek yanıtlar uyumlu, yeni backend kimliği doğrulanmadı. 3) TS/lint/build ve testler: **PARTIAL** — kaynak/fixture
kapıları PASS, zorunlu son canlı kontrol FAIL. 4) Release/dry-run: **PARTIAL** — izole aday ve
hash dry-run var, operasyon READY değil. 5) Ayrı onayla şimdi yalnız5173 aktarımı: **NO**.
