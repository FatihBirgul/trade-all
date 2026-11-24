# TRADE AI V3 — 8008 kontrollü runtime geçiş sonucu

11 Kasım 2026, Europe/Istanbul. Sonuç: **PRIMARY_ACCEPTED**.
Yeni kullanıcı onayı yalnız 8008 runtime geçişi için kullanıldı. Failback gerekmedi.

**Süreç ve exact sürüm**

| Alan | Sonuç |
|---|---|
| Eski 8008 PID | 13988; başlangıç 21:44:26.345655 |
| Yeni 8008 PID | 9792; başlangıç 23:32:15.685200 |
| Yeni süreç parent | 556, izole runtime venv launcher |
| Startup kaydı zamanı | 23:32:18.800314 |
| Canlı kabul bitişi | 23:32:46.912855 |
| Doğrulanan build | `56cbd7e05a40b106deda9298e2be28b488d0d952` |
| Runtime kaynak dizini | `release/attested-8008-56cbd7e/backend` |
| Loaded-code algoritması | `local-code-structure-1`, CPython311, 173 fonksiyon |
| Loaded-code SHA-256 | `314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b` |
| Startup binding SHA-256 | `6f6eb094995b069021f6588532ef3ec0f07f7abdd2472a14d8a26508cbcd96ba` |
| Source manifest SHA-256 | `8d084781a16e992d69104fb38d311af82704935d1df38197afda7cd0c78554c2` |
| Startup config SHA-256 | `f620fcc36d34ba8f3ea64f7d19bab59053f6e6a9588584fd92275a5e1d6616ae` |

Doğrulama disk hash'i veya public API digest'iyle sınırlı değildir: doğrulanmış source
manifestinden yeni süreçte yüklenen module origin'leri ve fonksiyon kod yapıları bağımsız
referansla eşleştirildi. Same-process startup kaydı PID+OS creation kimliğine bağlandı.
HTTP öncesi/sonrası provenance kontrolü ve her HTTP isteğinde source/config/dependency/loaded-code
integrity guard'ı çalıştı. Güven modeli operatöre ait yerel dosya ve süreç güvenidir;
donanımsal/uzak kriptografik attestation iddiası değildir. Eski PID13988'in exact RAM sürümü
sonradan doğrulanmış sayılmadı.

Startup kaydı:
`%USERPROFILE%\trade-ai-forex-web-v3-integration\release\attested-8008-56cbd7e\live-dbf3fb74b4e948fc8bcb3a08fd5d5709.json`.

**Paketler ve hazırlık**

- Kullanıcının kabul ettiği öneri ZIP SHA-256:
  `25de726317a2a04a60a37594d3d2fc6e32082d1bd76cce07e1c596cfe64409db`.
- Kullanılan değişmemiş runtime ZIP SHA-256:
  `a7e21cfca44c0963b689ff88f6d7e3f85f8a39c8a5a3b47e2dbeeaece6f66ef9`.
- ZIP CRC ve bütün manifest üyeleri, diskteki operasyon araç/config pin'leri, primary/failback
  kaynak envanterleri, backend HEAD/temiz çalışma ağacı ve yedekler kontrol edildi.
- Kabul edilen proposal dosyaları ve eski baseline dosyaları değiştirilmedi.
  Yeni yetki ve sonuç kayıtları ayrı `release/approved-8008-62c78b12170f4c8a88896846f4ff152f`
  dizinine yazıldı. Yeni araç yalnız bu kullanıcı onayını ve exact proposal SHA'sını kabul eder.
- Primary/failback provası canlı stop'tan önce izole portlarda yapıldı; sonra tam preflight tekrarlandı.
  Son anda beş süreç ve korunan kaynaklar yeniden karşılaştırıldı. Yalnız doğrulanan PID13988
  durduruldu; başka servis yöneticisine/restart komutuna başvurulmadı.

**Bağımlılıklar**

Yeni runtime'ın sabitlenmiş ortamı Python **3.11.9**, NumPy **2.2.6**, MetaTrader5 **5.0.6231**,
FastAPI **0.115.14**, Starlette **0.46.2**, Uvicorn **0.54.0**, Pydantic **2.14.3**,
pydantic_core **2.50.4** olarak doğrulandı. Kritik entry dosyalarının byte hash'leri de config ile
eşleştirildi. Global Python/NumPy ortamı değiştirilmedi.

**Test ve kabul sonuçları**

| Kontrol grubu | Sonuç |
|---|---|
| Yeni operasyon approval/PID/source/foreign-owner/failback guard fixture'ları | 11/11 PASS |
| Primary izole startup/HTTP/provenance/drift provası | 18/18 PASS |
| Failback izole startup/HTTP/provenance provası | 14/14 PASS |
| Yeni canlı 8008 kabul listesi | 24/24 PASS |
| Aynı release'in V2 chart/candlestick bridge fixture'ları | 15/15 PASS |
| Son kaynak/PID/proxy/health/provenance kontrolü | postflight.json içinde PASS |

Canlı 24 kontrol: aynı süreç startup provenance, health, yeni API şeması, no-order route yüzeyi;
XAUUSD/EURUSD/GBPUSD/USDJPY için exact broker alias/server/USC, güvenli V5 analiz,
fresh quote ve kapalı M5 mum; HTTP sonrası kaynak/bellek kimliği; gerçek `/engine → 8008`
şema ve analiz POST'u; yeni sembollerin V5 sözleşmesi dışında kalması.
AUDUSD metadata isteği, terminale ürün erişimi olmadan enum validation ile HTTP422 döndü.
Diğer 14 yeni sembole broker isteği yapılmadı. API şeması dört sembolle sınırlı kaldı.

Dört sembolde REAL_READONLY_DATA / Exness-MT5Real50 / USC, HYPOTHETICAL_CAPITAL,
execution_permission=false, trading_eligibility=BLOCKED ve null entry/SL/TP/lot alanları korundu.
Spread policy **UNAPPROVED**, decision **BLOCK**, max_allowed_price=null.
Historical evidence **SOURCE_NOT_SUPPLIED**, historical_gap_authorized=false;
broker contract CURRENT_MT5_OBSERVED geçmiş seansları onaylamaz.
Terminal erişimi read-call allowlist'iyle sınırlıdır; order_send/order_check/login/logout yoktur.
Gerçek hesap numarası/bakiye veya kimlik bilgileri sonuçlara yazılmadı.

**Veri ve V2 sınırları**

Health ve quote/kısa kapalı mum erişimi çalışmaktadır. M15/H4 birleşik analizinde gerçek tarihsel
mum boşluğu `DATA_UNAVAILABLE / INSUFFICIENT_DATA` ile güvenli ret üretir. Bu durum eski runtime'da
da geçiş öncesi görüldü; veri engeli kaldırılmadı. Desteklenen M5/M5 kontrolünde DATA_STATUS=OK,
fakat doğrulanmamış broker seansı nedeniyle NO_TRADE döndü. Ayrı gözlemler `v2-readonly-live.json` içindedir.

Bu canlı koşullarda V2 değerlendirme aşamasına geçilmediğinden chart/candlestick alanları null'dır.
Canlıda formasyon üretildiği iddia edilmez. V2'nin sabitlenmiş adapter kaynakları/config asset'ları
ve yüklenen Forex kodu doğrulandı; 15 fixture testi DESCRIPTIVE_ONLY, nedensellik, BUY/SELL/WAIT
ve risk/seans kararlarının korunmasını doğruladı. Canlı çıktıda decision-vote veya emir yetkisi
kazanan formasyon bulunmaz. Tarihsel kanıt/seans/spread guard'ları formasyon elde etmek için aşılmadı.

**Korunan servisler**

| Port | PID | Başlangıç (İstanbul) | Son durum |
|---|---|---|---|
| 5173 | 10320 | 15:31:24.868844 | Aynı süreç; gerçek /engine proxy kontrolü geçti |
| 8005 | 9124 | 22:59:38.449790 | Aynı süreç; health connected=true |
| 8006 | 8284 | 19:45:05.101785 | Aynı süreç; health OK |
| 8007 | 12152 | 15:58:51.667385 | Aynı süreç; news erişilebilir |
| 8008 | 9792 | 23:32:15.685200 | Yeni attested runtime; health OK |

Diğer dört servisin OS creation kimlikleri de aynı kaldı. 8008 provider kaynağının ana checkout,
eski candidate checkout ve deploy edilen release'de aynı olduğu yeniden doğrulandı:
`4b184b3710f22ada68e1b2458daa791aff39567fe5980c00985857d6f339b6d7`.
Provider doğrudan MetaTrader5 kullanır; 8005 HTTP bağımlılığı yoktur.
8005'in eski loaded-code güven sınırı BRIDGE_LOADED_VERSION_UNVERIFIED olarak kalır.
Bu kabul, yeni 15 ürün veya bridge restart/değişikliği onayı değildir.

**Failback ve kapsam**

Gerçek failback **NOT_NEEDED**. Onaylı ayrı failback kaynak/config/env hazırlığı ve izole başlangıcı
geçti. Bir kabul hatasında yalnız owned yeni süreç kapatılır; portta yabancı süreç varsa öldürülmez.
Geri dönüş doğrulanmış kaynaktan ayrı başlangıçtır; eski PID13988'in RAM imajını geri yükleme değildir.

Orijinal backend/bridge/frontend kaynakları ve proxy/Tailscale değiştirilmedi. Korunan tam envanter
öneri paketindeki hash'lerle eşleşti. PWA APPLY/HMR tetiklemesi, 5173/8005/8006/8007 restart,
hesap değiştirme, gerçek/demo emir, order_check, spread onayı, historical VERIFIED işaretleme,
GitHub push/merge yapılmadı. PWA canlıya alma onayı hâlâ ayrıdır.

Operasyon kanıtı:
`%USERPROFILE%\trade-ai-forex-web-v3-integration\release\approved-8008-62c78b12170f4c8a88896846f4ff152f\result.json`.
Taze son gözlem: aynı dizindeki `postflight.json`. İlerideki operasyonlarda yeni PID ve startup
kaydı dikkate alınmalı; eski PID13988'e bağlı preflight/cutover komutları tekrar kullanılmamalıdır.
