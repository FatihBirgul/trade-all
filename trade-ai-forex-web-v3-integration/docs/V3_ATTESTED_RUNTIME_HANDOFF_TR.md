# Doğrulanabilir 8008 runtime ve tek operasyon onayı

11 Kasım 2026. Durum **READY_FOR_APPROVAL — YALNIZ 8008 RUNTIME**.
Canlı değişiklik yapılmadı. **PWA_APPLY_NOT_AUTHORIZED** ayrıca korunur.
Bu belge önceki exact-version engelini yeniden aynı disk kontrolüyle aşmaya
çalışmaz; yeni process için test edilmiş startup provenance ve cutover hazırlar.

## A-C. Mevcut runtime hakkında kesin sonuç

Aktif 8008 PID **13988**, OS creation identity özel
`release/attested-8008-56cbd7e/current-runtime-backup.json` içindedir.
Parent 3944, V5CandidateRuntime launcher; cwd trade-ai-v3-runtime-candidate.
Plain uvicorn launch, reload/child watcher yok. Ana backend ve runtime checkout
`56cbd7e05a40b106deda9298e2be28b488d0d952` disk checkpoint'indedir.

Mevcut PID içinde önceden kaydedilmiş build ID / startup-frozen loaded fingerprint
bulunamadı. Private önceki manifestler farklı PID/portlarda başlatılmış QA
process'lerine aittir. Onları 13988'e atamadık; bugün oluşturulan gözlem dosyası
da startup kanıtı değildir. Sonuç:
**EXACT_RUNNING_VERSION_UNVERIFIABLE_WITHOUT_CUTOVER**.

Disk hash'i, public content fingerprint, schema, aynı executable ve benzer HTTP
cevabı tek başına eski process'in exact loaded SHA'sını ispatlamaz. Mevcut
process'e kod enjekte edilmedi, debugger bağlanmadı veya uygulama belleği okunmadı.
Yeni araç yalnız OS PID/creation/executable metadata'sını GetProcessTimes ve
QueryFullProcessImageName ile sorgular; eski process memory/command/env dump yoktur.

## D-E. Yeni release ve startup kimliği

Release: `release/attested-8008-56cbd7e/backend`; exact source SHA yukarıdaki
56cbd7e. Git archive'den yeni ve cachesiz çıkarıldı. `source.json` bütün source
inventory SHA-256'larını; `config.json` strict read-only ayarlarını;
`launch-inputs.json` exact source/config digest ve executable yollarını bağlar.
Config SHA **f620fcc36d34ba8f3ea64f7d19bab59053f6e6a9588584fd92275a5e1d6616ae**,
source manifest SHA **8d084781a16e992d69104fb38d311af82704935d1df38197afda7cd0c78554c2**.
Operasyon bunları paketten tekrar doğrular; elle yeni hash atamak onay değildir.

Bağımsız deployment venv `.artifacts/cutover/runtime-venv`: Python 3.11.9,
NumPy 2.2.6, FastAPI 0.115.14 / Starlette 0.46.2; include-system-site-packages=false.
Yeni paket bu ortamı kullanır. Mevcut V5CandidateRuntime veya global paketler
değiştirilmez. Dependency version/entry hashes, NumPy binary hash ve Python
prefix/executable identity config'e sabittir; drift start ve verify'da reddedilir.

`tools/attested-runtime.py` sırası:

1. Source/config digest, exact SHA, tam source inventory, symlink/reparse ve eski
   bytecode cache reddi; henüz Forex import etmeden kontrol.
2. Strict REAL_READONLY_DATA / Exness-MT5Real50 / USC / exact dört Cent mapping;
   MT5/V2 ortam kalıntıları temizlenir. Secrets/login alanları kabul edilmez.
3. Her Forex modülü yeni process'te preload edilir; gerçek import origin'i ve
   içerik hash'i source manifest ile ilişkilendirilir. Yeni cache namespace
   stale .pyc okunmasını engeller; bytecode yazımı kapalıdır.
4. V2 exact candlestick ve chart Git pin'leri, boş production historical review/
   candidate listesi ve read-only terminal adapter doğrulanır. Broker preflight
   gerçek balance'ı sermaye olarak döndürmez.
5. Yeni process'in code object alanlarından `local-code-structure-1` fingerprint
   üretilir. Ayrı fresh interpreter referansıyla eşleşme zorunludur. CPython
   adaptive caches ve marshal interning flags dışarıdadır; gerçek bytecode,
   constants, arguments, names, flags ve exception/line tables kapsanır.
6. Release ID + build SHA + source/config/launcher/dependency identity + UTC
   startup zamanı + PID/OS creation + module origins + loaded code fingerprint
   aynı process'te, exclusive UUID private dosyaya bir kez yazılır.
7. Uvicorn aynı process'teki aynı app'i localhost'ta reload'suz sunar. HTTP
   IntegrityGuard source/config/assets/dependency-entry ve loaded-function drift
   kontrol eder. Drift halinde yalnız generic 503/false execution döner.
8. Operatör verifier private startup kaydını fresh port owner/creation kimliği,
   config/source pins ve independent reference ile karşılaştırır.

Bu mekanizma **yerel startup provenance**'dır; imzalı remote attestation değildir.
Self binding hash yanlışlıkla corruption'ı saptar, HMAC/signature değildir.
Operator-owned source/config/record dizinleri güven sınırıdır. Kötü niyetli
aynı kullanıcı/admin tüm dosyaları değiştirebiliyorsa mutlak güvence yoktur.
Python function code alanları kapsanır; globals, arbitrary C-extension memory,
harici servisler ve private V2 runtime globals mutlak bellek ispatı değildir.
Private V2 source pin'leri ayrıca kontrol edilir. Sonraki dinamik monkeypatch
ve yeni Forex functions drift kontrolüne takılabilir; tüm runtime state'i
kriptografik olarak dondurduğumuz iddia edilmez. Public build/diagnostic endpoint yoktur.

## F-L. Gerçek kabul ve güvenlik sonuçları

| Grup | Sonuç |
| --- | --- |
| Yeni startup/identity/source/no-order/controller guard testleri | **28/28 PASS** |
| Yeni gerçek read-only primary runtime | **18/18 kontrol grubu PASS**, yalnız kendi ephemeral portu |
| Ayrı source/config ile failback runtime | **14/14 PASS**, yalnız kendi ephemeral portu |
| Exact source backend full Python 3.11 | **600/600 PASS**, 75.300 s, bağımsız deployment venv |
| Exact source backend full Python 3.13 | **600/600 PASS**, 55.757 s, mevcut izole QA venv |
| Mevcut HTTP fixture | **63/63 PASS** |
| Historical HTTP fixture | **14/14 PASS** |
| Eski PWA pure contract | **9/9 PASS** |
| RC API/client | **42/42 PASS** |
| Primary/failback actual responses -> RC parser | **2/2 PASS**; dört sembol her iki grupta |
| TypeScript + production build + full ESLint | **PASS** |
| Python compilation | **PASS**, source'da .pyc üretmeden |
| RC browser34 / preview-cache3 | Önceki aynı RC/runner için 34/34 ve 3/3 referansı; tekrar edilmedi |

Sayılara örtüşen kapsamlar dahildir; bunlar benzersiz test toplamı diye toplanmaz.
Fixture HTTP ile gerçek broker read-only primary/failback kabulleri ayrıdır.
Testte açılan bütün süreç/listener'lar kendi Popen kimlikleriyle kapatıldı.

Primary'de çalışan kendi staged source dosyası test amaçlı değiştirildi:
HTTP 503, operatör verify ret ve frozen startup dosyasının aynı kalması
doğrulandı. Dosya orijinal baytlarına geri konunca health200 oldu. Bu yalnız
görevin kendi release/test process'idir; main veya canlı 8008 değiştirilmedi.
Unit testte code.__code__ replacement (yalnız test process'inde) disk okumadan
fingerprint'i değiştirdi; normal execution/warmup fingerprint'i değiştirmedi.

Dört gerçek sembolde exact broker/server/USC, UNAPPROVED spread BLOCK/null max,
historical SOURCE_NOT_SUPPLIED/authorized=false, null Entry/SL/TP/lot,
execution_permission=false ve hypothetical USC kontrol edildi. Real balance,
login/logout, order_send/order_check yok. Terminal adapter symbol_select dahil
yazma/control yöntemlerini dışlar; mevcut REAL provider bu yöntemi çağırmaz.
V2 DESCRIPTIVE_ONLY, Double Top/Bottom, BUY/SELL/WAIT/Entry/SL/TP/lot/risk ve
PnL oracle regresyonları 600/63 fixture paketlerinde korunur. Gerçek snapshot QC
retlerinde pattern listesi null/unavailable olabilir; formasyon uydurulmaz.

Ara denemeler saklandı: V2 asset ilk taslakta engines parent şartını karşılamadı,
paket yolu düzeltildi. Windows symlink privilege eksikliği gerçek junction testiyle
çözüldü; skip yapılmadı. Eski marshal fingerprint normal HTTP akışında false
drift verdi; kararlı code-structure algoritması ve iki bağımsız test eklendi.
Mevcut global-site CandidateRuntime'da full suite TestClient için httpx2 eksikti
(388 test/20 import error); o ortam değiştirilmedi. Tam 600 yeni bağımsız pinned
ortamda ve Python3.13'te tekrar geçti. Son kabul koşullarında fail/error/skip sıfır.

## M. Backup/failback ve kesinti sınırı

`failback-backend` ayrı exact 56cbd7e source kopyasıdır. Primary source drift'i
failback source'u bozmaz. `failback-assets/engines` ve `failback-config.json`
ayrıdır; aynı pinli dependency ortamı kullanılır. Failback config SHA:
**628acefbea7210023e065b57ec51c2fd45d6916704c8f76f833bba899a6c22e0**.
Referans code/origin kimlikleri relative paths ile her iki source için geçer.

Bu failback **eski process RAM'ini/private env'ini birebir geri kurmaz**; mevcut
exact loaded sürüm zaten bilinmiyor. Backup; doğrulanmış source archive, gözlenen
safe launch metadata, önceki PID/creation, pinli config/dependency ve test edilmiş
güvenli 56cbd7e reproduction'dır. Sonuçların ve bu sınırın onayı istenir.

8008 aynı portta korunacağı ve proxy değişmeyeceği için kısa bir stop/start
boşluğu gerekir. Graceful drain garantisi yoktur. Önceden ayrı portta staging ve
failback provası kesinti riskini azaltır, sıfır downtime iddiası değildir. Yeni
runtime kabul olmazsa yalnız yeni owned process kapatılır, bağımsız failback
aynı 8008'de başlatılıp tekrar attestation/API kabulünden geçer. Foreign owner,
config drift veya failback başarısızlığında başka process öldürülmez; safe STOP
ve operatör müdahalesi gerekir. 8006 otomatik fallback hedefi değildir.

## N-Q. Korunan servisler, PWA ve dosyalar

5173=10320, 8005=9880, 8006=8284, 8007=12152, 8008=13988 korunur.
/engine -> 8008 ve Tailscale ayarları değişmedi. Ana backend branch/HEAD56cbd7e
temiz kaldı. Yalnız izole PWA tools/tests/docs/release çıktıları yazıldı;
yerel commit/ZIP kimliği package-manifest.json ve teslim yanıtındadır. Push/merge yok.

Original AnalysisPanel.tsx bu görev sırasında dışarıdan değişti:
önce `5b79d59ebaa57288baebe67f95c2b002e08d7bbae63333037ae0b10d23dbab47`,
sonra `6ffa4737dc1e26d5031b63b44960f4a7ccc9dd944b571ef47060e03bf25ce7fd`.
Bu görev değişikliği yapmadı/geri almadı. Eski dokuz dosyalı original-target
dry-run artık **TARGET_DRIFT_REQUIRES_REVIEW** üretir; kapı gevşetilmedi.
RC source/client/build kabulü bu dış dosyanın promotion onayı değildir.

Yeni controller sadece backend runtime yönetir, frontend write çağrısı yoktur.
Bu nedenle frontend drift'i ayrıca raporlanır; runtime preflight exact backend,
source/config/dependency ve original proxy hash'ini zorunlu kontrol eder.
PWA guard/NewsPanel/chart/proxy kopyalama veya APPLY bu paketin yetkisi değildir.
**PWA_APPLY_NOT_AUTHORIZED**, hem mevcut runtime sürüm belirsizliği hem yeni
frontend target drift incelemesi tamamlanana kadar korunur. Mevcut BLOCKED ZIP'ler
değiştirilmez veya deployable=true yapılmaz.

## R. Tek açık onayla uygulanacak minimum operasyon

Paket: `release/TRADE_AI_V3_ATTESTED_8008_56cbd7e_READY.zip` ve `.sha256`.
Manifest scope **8008_RUNTIME_ONLY**, approval_received=false,
pwa_apply_authorized=false. Eski runtime hakkında yeniden hash döngüsü yoktur.

Şimdi çalıştırılan tek controller modu read-only preflight'tır:

```powershell
& '.artifacts/cutover/runtime-venv/Scripts/python.exe' -B tools/attested-cutover.py
```

**Yalnız yeni kullanıcı onayından sonra**, bu exact ZIP hash'i ile:

```text
python.exe -B tools/attested-cutover.py --apply-runtime --operator-approved --package-sha256 <ZIP-SHA256>
```

`python.exe` yukarıdaki bağımsız deployment executable'ıdır; komut izole PWA
kökünde çalışır. Paket/source/config/tool hash'leri, dependency ve mevcut
8008 PID/creation kimliği önce doğrulanır. Sonra primary/failback ayrı portlarda
yeniden prova edilir. Güncel preflight tekrar geçerse yalnız exact eski 8008
child process ağacı durdurulur. Port boşluğu kontrolü ardından yeni runtime
UUID startup kaydıyla başlatılır; aynı-process attestation + dört sembol API
kabulü tamamlanır. Hata olursa yalnız yeni owned process kapatılıp bağımsız
failback kabulü denenir. Kullanıcı değişikliği/foreign owner varsa STOP.

Canlı stop/start dalı bu hazırlıkta **NOT_RUN**. Gerçek isolated primary/failback
çalıştırıldı; orchestration success/failure/foreign-owner dalları mocks ile
ayrıca sınandı. Controller port8008 dışını veya PWA/proxy dosyalarını yönetmez.
Cutover receipt'i de PWA onayı vermez. Local/proxy/Tailscale smoke aynı schema'yı
göstermeli; fiziksel telefon/cache kabulü ayrıca sonraki PWA operasyonuna aittir.

## Dört net cevap

1. Mevcut 8008 exact loaded sürümü kesin doğrulandı mı? **NO**.
2. Yeni 56cbd7e doğrulanabilir startup paketi hazır mı? **YES**.
3. Güvenlik/test/rollback kapıları geçti mi? **PARTIAL**: runtime scope tamamı
   geçti; original PWA target guard dış değişiklik nedeniyle kapalıdır.
4. Kontrollü 8008 runtime geçişi için onay istenebilir mi? **YES — yalnız runtime
   replacement + test edilmiş failback; PWA APPLY hariç**.
