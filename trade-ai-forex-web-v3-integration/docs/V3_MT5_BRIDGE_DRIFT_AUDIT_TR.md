# TRADE AI V3 — MT5 Bridge drift denetimi ve 8008 başlangıç durumu önerisi

11 Kasım 2026, Europe/Istanbul. Durum: **AUDIT_COMPLETE_NO_OPERATIONAL_REBASELINE**.
Canlı geçiş: **BLOCKED_NEW_APPROVAL_REQUIRED**. Paket bir inceleme/başlangıç durumu önerisidir;
deploy edilebilir runtime paketi veya otomatik kabul edilmiş baseline değildir.

**A. Eski/güncel SHA-256.** Orijinal dosya
`%USERPROFILE%\trade-ai-forex-web\mt5_bridge.py`.

| Sürüm | SHA-256 |
|---|---|
| Eski | `1a47e33f13c929612f811a71c8bd1734ad1a74eb6b58c3d55473b579a3037718` |
| Güncel | `1a74d26f8b6ec217ff3122bfeb9bdda5db2839db6aab0d3af7f3d2a4163f8ef7` |

Eski gerçek baytlar değişmemiş onaylı ZIP içindeki
`release/runtime8008-56cbd7e/backup/mt5_bridge.py` üyesinden çıkarıldı.
`release/runtime8008-56cbd7e/backup/mt5_bridge.py` ve
`release/reconciled-56cbd7e/preapproval-backup/mt5_bridge.py` disk yedekleri de aynı eski hash'e sahip.
İki dosyanın ayrı snapshot'ları ve gerçek unified diff yeni kanıt paketinde bulunur.
Hash üzerinden içerik tahmini yapılmadı.

**B. Gerçek kod farkları ve güvenlik incelemesi.** İki diff bölgesi vardır:

- `SYMBOLS` ve sabit `MT5_SYMBOL_MAP` 4'ten 19'a çıkarılmıştır.
  Eklenenler: AUDJPY, AUDUSD, CADJPY, CHFJPY, EURAUD, EURCAD, EURCHF,
  EURGBP, EURJPY, GBPCHF, GBPJPY, NZDJPY, NZDUSD, USDCAD, USDCHF.
  Her biri açıkça `<sembol>c` alias'ına gider. Eski dört eşleme aynı kalmıştır.
  Sınıflandırma: **REQUIRES_REVIEW**; yazılım farkı sınırlı ve fixture sözleşmesi uyumludur,
  fakat yeni broker ürünlerinin canlı uygunluğu/visibility durumu onaylanmamıştır.
- Yeni `RISK_SYMBOLS`, XAUUSD/EURUSD/GBPUSD/USDJPY ile sınırlıdır;
  risk-preview guard'ı bu kümeye geçirilmiştir. Etkin risk kapsamı eskiyle aynıdır.
  Sınıflandırma: **SAFE**.

Bu bildirimler ve guard adı normalize edilince geri kalan AST tamamen aynıdır.
Yeni import, bağımlılık, route, shell/subprocess, dinamik kod çalıştırma veya emir yolu yoktur.
Bağlantı, account kontrolleri, quotes, timeframe kümesi, spread/fiyat alanları,
UTC epoch dönüşümü, hata/logging, retry, lock/global state ve yanıt sözleşmeleri değişmemiştir.
Eski dört sembolde BUY/SELL risk önizlemesi ve veri yanıtları karşılaştırmalı fixture ile eşittir.

Önceden de bulunan sınırlar: `ensure_connection` IPC kopunca 5 saniye throttle ile
`shutdown/initialize(timeout=5000)` çağırabilir. Görünmeyen ürünlerde `symbol_select(..., True)`
MarketWatch durumunu değiştirebilir. Dolayısıyla bütün bridge uçları koşulsuz salt okunur değildir.
Candles pozisyon 0'dan okur; açık grafik mumu da döner. Quote yaşı bridge tarafından engellenmez.
Market-data route'larında tam REAL/server/USC guard'ı bulunmaz; symbol-spec yalnız hesap para birimini verir.
Risk preview DEMO dışında REAL+USC+`Exness-*` prefix'ine de izin verir; buna rağmen `demo_only=true`
etiketi taşır. Bunlar bu diff'in eklediği davranışlar değildir ve V5 finansal karar sözleşmesi sayılamaz.
Risk miktarı kullanıcı girdisinden gelir; gerçek bakiye okunmaz. `order_calc_profit` hesaplama oracle'ıdır.
`last_error` broker hata metni döndürebilir; yeni hassas veri logging'i bulunmamıştır.

Authentication yoktur. CORS sabit localhost/127.0.0.1:5173/4173 ve GET ile sınırlı kalmıştır;
CORS bir authentication mekanizması değildir. Listener 127.0.0.1'dedir; PWA aynı origin `/mt5`
proxy'si üzerinden de bridge'i sunar. Dış erişimin mevcut güvenliğini bu görev yeniden yapılandırmaz.

**C. Doğrulanabilir zaman çizelgesi.** Saatler İstanbul saatidir.

| Olay | Zaman |
|---|---|
| Backend PID 13988 yaratılması | 21:44:26.345655 |
| Bridge parent PowerShell PID 13556 yaratılması | 22:55:48.492334 |
| Bridge güncel dosya mtime | 22:55:52.205658 |
| Önceki operasyonun drift nedeniyle durması | 22:59:28.210493 |
| Yeni bridge PID 9124 yaratılması | 22:59:38.449790 |
| Bu denetimin servis başlangıç snapshot'ı | 23:08:05 |
| Bu denetimin servis bitiş snapshot'ı | 23:15:33 |

Dosya mtime'ı yeni process creation'dan yaklaşık 3 dakika 46 saniye öncedir.
Önceki durdurma kaydı 9880→9124 değişimini kaydeder. PID 9880'in neden/kim tarafından
sonlandırıldığını gösteren güvenilir audit kaydı yoktur. Mtime da tek başına içeriğin kim tarafından
ve hangi komutla yazıldığını kanıtlamaz.

**D. Değişikliğin kaynağı.** Teknik içerik farkı tamamen açıklandı; aktör, yetkilendirme kaynağı
ve restart nedeni **UNVERIFIED**. Parent Explorer→PowerShell zinciri aktör ataması değildir.
Kullanıcının shell geçmişi, parolaları veya token'ları rapora alınmadı.

**E. Yeni bridge güvenliği.** **PARTIAL**. Yeni emir/account-write yolu yoktur;
eski dört sembolün sözleşmesi korunmuştur. Genişletilen grafik listesi için ürün onayı ve
bridge'in yukarıdaki eski güvenlik sınırlamaları ayrı değerlendirilmelidir.
Bu sonuç bütün 19 ürünün üretim kullanımını veya risk önizlemesini onaylamaz.

**F. Çalışan 8005 sürüm güveni.** **BRIDGE_LOADED_VERSION_UNVERIFIED**.
PID 9124; executable `%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe`;
parent PID 13556 Windows PowerShell. Sanitized launch gözlemi:
`python -B -m uvicorn mt5_bridge:app --host 127.0.0.1 --port 8005`; reload bayrağı yok.
Salt okunur process-parameter incelemesinde cwd orijinal PWA dizinidir;
allowlist kapsamındaki MT5/V2 ortam ayarları bulunmamıştır.
Beklenen import kaynağı bu cwd altındaki `mt5_bridge.py` dosyasıdır.
Bu, Python belleğindeki gerçek module origin veya loaded-code fingerprint kanıtı değildir.
Same-process startup manifest bulunmadığı için sonradan attestation üretmedik.
Kod enjekte edilmedi, debugger ile kod çalıştırılmadı, restart yapılmadı.

Global Python311 disk metadata'sı: MetaTrader5 5.0.6231, NumPy 2.4.6,
FastAPI 0.162.0, Starlette 1.10.0, Uvicorn 0.54.0. Bu liste çalışan süreçte
yüklenmiş bağımlılıkların kesin sürüm kanıtı değildir. Global ortam değiştirilmedi.
Bridge HTTP'si sadece connected ve account_currency gibi kısıtlı bilgiler verir;
bridge ile V5'in aynı account login'ini kullandığı bağımsız biçimde kanıtlanamaz.

**G. Gerçek bağımlılık zinciri.** `5173 /engine → 8008 → forex.providers.MT5Provider → MetaTrader5`.
8008 provider'ında 8005'e HTTP bağlantısı veya bridge modülü import'u bulunmaz.
`5173 /mt5 → 8005` MarketChart ve RiskCalculator için ayrı yoldur;
`/news → 8007` ayrı kalır. 8006 eski API'dir. 8005, V5'in fiyat/lot/veri kaynağı değildir.
Ortak terminal üzerinden dış müdahale ihtimali sıfır sayılamaz; V5 account guard'ları ve
freshness kontrolleri geçişte yeniden doğrulanmalıdır. Bridge loaded-version sınırı,
V5 doğrudan provider testlerinin yerine geçirilmedi ve bağımlılık varmış gibi yorumlanmadı.

**H. REAL_READONLY_DATA ve USC.** Mevcut 8008 process allowlist ayarları
REAL_READONLY_DATA / Exness-MT5Real50 / USC ve eski dört açık alias'tır.
Dört sembolün localhost metadata ve analiz yanıtları exact server, REAL ve USC kimliğini
doğruladı; risk kaynağı HYPOTHETICAL_CAPITAL ve execution_permission=false.
Gerçek bakiye veya hesap numarası alınmadı/raporlanmadı. Bridge'in kendi exact account
guard'ı olduğu iddia edilmemektedir.

**I. No-order ve lot güvenliği.** Eski ve güncel kaynakta `order_send/order_check/login/logout`
çağrıları yoktur. No-order static inceleme, fixture tripwire'ları ve API route kontrolüyle desteklenir;
bu, başka süreçlerin broker hesabında hiçbir işlem yapmadığına dair global kanıt değildir.
İzole BUY/SELL oracle ve minimum lot testleri geçti; ek 15 risk sembolü terminale ulaşmadan reddedilir.
V5'in dört canlı yanıtında entry/SL/TP/lot alanları null ve trading_eligibility=BLOCKED kaldı;
gözlenen legacy_signal WAIT/final_decision INSUFFICIENT_DATA emir yetkisi vermez.

**J. Spread/historical/V2.** Dört V5 yanıtında spread policy UNVERIFIED,
decision BLOCK ve max_allowed_price=null; historical status SOURCE_NOT_SUPPLIED ve
historical_gap_authorized=false. Broker contract CURRENT_MT5_OBSERVED geçmiş güveni sayılmaz.
V2 pattern bağlamlarının rolü DESCRIPTIVE_ONLY sınırında kaldı. Yeni bridge sembolleri bu engelleri aşmaz.

**K. Yeniden çalıştırılan testler ve sınırları.**

| Test grubu | Sonuç | Ortam |
|---|---|---|
| Bridge diff/kontrat/no-order/19 alias/4 risk/15 reject/V5 ayrımı | 19/19 | Tamamen sahte MT5; gerçek extension yüklenmez |
| Startup/identity/approval/owned-failback/foreign-PID guard | 28/28 | İzole fixture/mock |
| Proxy/version/backup/dry-run/apply-restore | 9/9 | Geçici fixture hedefi; canlı PWA'ya yazılmaz |
| HTTP uyumluluk ve finansal güvenlik kontrolleri | 21/21 | Localhost; gerçek analiz salt okunur |
| ZIP CRC+manifest / source / failback / pinned dependencies | PASS | Disk doğrulaması; yeni servis başlatılmaz |

Bridge localhost testleri health, OpenAPI ve iki geçersiz girdi reddidir.
Bridge candles/spec/risk-preview ve yeni 15 ürün canlıda çağrılmadı; olası reconnect/MarketWatch
yan etkileri fixture ile sınırlandı. Dolayısıyla bridge'in canlı market-data yanıt eşitliği doğrulanmış sayılmaz.
V5 dört sembolde metadata, ≤120 saniye quote freshness, UTC epoch, kapalı M5 mum ve V5 analiz güvenliğini geçti.
Fixture'da disconnect/retry/503 ve validation400/422 sınırları da test edildi;
canlı MT5 bağlantısı kesilerek timeout simülasyonu yapılmadı. HTTP client timeout 20 saniyedir.
Referans backend 600/600, owned primary18/failback14 ve client42 sonuçları eski değişmemiş paketin
kanıtlarıdır; bu görevde tekrar çalıştırıldığı iddia edilmez.

**L. Beş servis.** Başlangıç ve bitiş kimlikleri aynıdır; hepsi 127.0.0.1 listener'ıdır.

| Port | PID | Durum |
|---|---|---|
| 5173 | 10320 | /engine OpenAPI 8008 ile eşleşiyor |
| 8005 | 9124 | Health connected=true |
| 8006 | 8284 | Health OK / mt5 |
| 8007 | 12152 | /api/news erişilebilir |
| 8008 | 13988 | Health OK / mt5; değiştirilmedi |

23:08:05–23:15:33 aralığında PID+OS creation kimlikleri, bridge hash ve proxy hash değişmedi.
Geniş PWA/backend dosya envanteri 23:12:09'dan bitişe kadar da aynı kaldı.
Backend HEAD `56cbd7e05a40b106deda9298e2be28b488d0d952`, working tree temizdir.
Servis başlangıç snapshot'ından önceki bütün dosya yazmalarını bu gözlem dışlamaz.
Yeni PID/source/config/proxy farkı görülürse öneri geçersizdir: BLOCKED_CONCURRENT_CHANGE.

**M. Kaynak/baseline farkları.** Eski protected manifest'e göre bridge dışında
AnalysisPanel.tsx (22:20:52), App.tsx ve MarketChart.tsx (23:04:12) farklıdır.
Tam hash'ler `prior-protected-drift.json` içindedir. Kaydedilmiş mtime'lar servis başlangıç
snapshot'ından öncedir; aktör kanıtı değildir. Bu frontend farkları değerlendirilip onaylanmadı,
geri alınmadı ve runtime-only onayına dahil edilmez. Aktif proxy hash'i
`1ffbc679ebbe8bccc9c222768497f053080f0f6d23732d9d765664552c2f516d` olarak kaldı.
İzole release deposunda yalnız yeni audit aracı, fixture testi, bu rapor ve ignored kanıtlar üretildi;
commit yapılmadı, mevcut HEAD 864bd603ffd27000b2d78e94ab848d6b649ebec9 kaldı.
Aktif controller/config/protected baseline dosyaları güncellenmedi.

**N. Paket ve yedek/failback.** Yeni ayrı kanıt paketi:
`release/TRADE_AI_V3_BRIDGE9124_AUDIT_BASELINE_PROPOSAL.zip`.
SHA-256 mühürlemeden sonra aynı adlı `.zip.sha256` sidecar'da ve teslim mesajında verilir;
self-referential rapor hash'i üretilmez. Source manifest bütün üyelerin hash'lerini içerir;
`deployable=false`, `approval_received=false`, operational_baseline_activated=false.
Mevcut onaylı runtime ZIP SHA'sı değişmedi:
`a7e21cfca44c0963b689ff88f6d7e3f85f8a39c8a5a3b47e2dbeeaece6f66ef9`.
İki ayrı primary/failback source envanteri ve pinned config/dependency doğrulaması geçti.
Failback, doğrulanmış kaynaktan ayrı başlangıçtır; PID13988'in eski RAM/özel ortamını birebir geri yüklemek değildir.
Gerçek rollback gerekmedi ve çalıştırılmadı. Yeni ZIP eski runtime dosyalarını değiştiren bir overlay değildir;
eski değişmemiş artifact'a hash ile başvurur.

**O. Kullanıcı dosyaları.** Orijinal bridge/PWA/backend dosyalarına yazılmadı.
Kullanıcı farkları korundu. Global paket kurulmadı/değiştirilmedi. Hesap numarası/token/parola dışa aktarılmadı.

**P. Operasyon sınırı.** Restart, kill, port/proxy değişikliği, PWA APPLY/HMR tetiklemesi,
push/merge, gerçek/demo emir, order_check ve hesap login/logout yapılmadı.
Guard testindeki PRIMARY_ACCEPTED/FAILBACK_ACCEPTED logları mocked geçici fixture sonuçlarıdır;
canlı cutover başarısı değildir. Önceki canlı onay yeniden kullanılmadı.

**Q. Yeni onay koşulları.** Sınırlı kod farkı ve dört sembollü bağımsız V5 uyumluluğu,
bir **PROPOSED_NOT_APPROVED** başlangıç durumu hazırlamak için yeterlidir.
Aktör ve bridge loaded-code belirsizliği çözülmüş gibi kabul edilmez; bu sınırlar operatöre açık sunulur.
Yeni 15 ürünün kullanımı, bridge restart'ı veya frontend değişikliği bu öneriyle yetkilendirilmez.

Yeni runtime-only onayının bağlanacağı inceleme: bu öneri ZIP'inin exact SHA'sı,
değişmeyen eski runtime ZIP SHA'sı, backend56, 8005 PID9124/creation/hash ve 8008 PID13988/creation.
Operatör bağımsız grafik bridge'inin loaded-version güven sınırını açıkça değerlendirmelidir.
Bu kabul yoksa operasyon BLOCKED kalır. Ardından yeni ve açık 8008-only operasyon onayı gerekir.
Sonraki operasyonda proposal guard'ları gerçek stop'tan hemen önce yeniden çalıştırılmalı;
eski controller'ın yalnız backend/proxy kontrolü yeterli sayılmamalıdır.
8005/5173/8006/8007 kimlikleri ve config'leri, tam protected envanter, exact source ve ZIP hash'leri,
primary/failback config+dependencies, proxy, REAL/USC, no-order, spread/historical ve yeni startup
same-process loaded-code fingerprint kabulü zorunludur. Beklenmeyen her farkta durulur.

Salt okunur tekrar kontrolü, izole release dizininde:
`.artifacts/cutover/runtime-venv/Scripts/python.exe -B tools/bridge-drift-audit.py check`.
Bu komut approval vermez veya baseline yazmaz. Mühürlü proposal ZIP hash'i de ayrıca doğrulanmalıdır.
Mevcut 8008'in loaded sürümü de startup kaydı olmadığı için UNVERIFIED kalır;
yeni attestation yalnız ayrıca yetkilendirilmiş yeni başlangıçta üretilebilir.

**Beş net cevap.**

1. Bridge değişikliği tam olarak açıklandı mı? **PARTIAL** — içerik farkı tam; aktör/restart nedeni bilinmiyor.
2. Yeni bridge güvenli ve V5 uyumlu mu? **PARTIAL** — dört sembollü sözleşme uyumlu; loaded kimlik, eski sınırlamalar ve 15 ürün canlı uygunluğu açık.
3. Çalışan bridge sürümü yeterli güvenle doğrulandı mı? **UNVERIFIED** — startup/loaded-code attestation yok.
4. Yeni operasyon baseline'ı güvenle hazırlanabilir mi? **YES** — yalnız açık sınırları olan öneri; aktive edilmiş operasyon baseline'ı değil.
5. 8008 için yeniden operatör onayı istenebilir mi? **YES** — Q'daki sınırlamalar ve exact artifact'lar sunularak, yeni ve yalnız 8008 kapsamlı onay için.
