# İki aşamalı bakım operasyonu — 12 Kasım 2026

**Durum: BLOCKED. Bu belge çalıştırma yetkisi değildir.** Canlı mutation controller'ı eklenmedi; mevcut controller'ların eski baseline guardları atlatılmadı. Hazırlık aracı yalnız audit, advisory lease ve salt-okunur preflight yapabilir. Bu plandaki adımlar ancak ayrı açık kullanıcı yetkisi ve tek operatör koordinasyonu altında uygulanabilir.

## Giriş koşulları

1. Kullanıcı, 5173/8005/8006/8007/8008 kaynaklarını veya başlatıcılarını değiştirebilen diğer iş akışlarını bakım süresi boyunca duraklatır. Bu görev hiçbir ajanı veya servisi durdurmaz. Masaüstü `Trade AI Başlat.cmd`, açık PowerShell 7464, V5Runtime/V5CandidateRuntime komutları ve başka görevlerin deployment işlemleri bakım penceresinde çalıştırılmaz. Komut dosyaları silinmez/değiştirilmez.
2. Tek bir kalıcı operator shell/process kimliği (PID + creation time + exe) belirlenir. Yeni benzersiz `.artifacts/operator-state/<operation-id>` altında exclusive advisory lease alınır. TTL en fazla 900 saniye; stale/corrupt/released lease otomatik devralınmaz veya silinmez. Yeni dizin ancak açık operatör incelemesiyle oluşturulur. Lease, başkalarının işlemlerini teknik olarak engellemez; her canlı adımdan hemen önce taze OS/hash guard tekrar gerekir.
3. Paket SHA-256, operasyon planı, dokuz dosyalı source/destination manifesti ve taze port/process baseline kullanıcıya sunulur. Mevcut A baseline yalnız gözlemdir: `12152` runtime'ına sürüm onayı vermez.
4. Eski runtime controller salt-okunur preflight'ta `Active 8008 process changed; do not use old stop identity` ile durmaktadır. Önceki `approved-8008` ve PWA `final-pwa-release` guardları da eski süreçlere bağlıdır. Bunların eski JSON'ları düzenlenemez ve guard bypass yapılamaz. Yeni, ayrı incelemeye tabi operator binding/controller bu planın A/B receipt'lerini kullanacak şekilde hazırlanıp QA'dan geçirilmeden operasyon uygulanamaz. Bu açık eksiklik nedeniyle paket READY değildir.

## Aşama A — yalnız 8008 runtime

Kapsam yeni onayda açıkça yazmalıdır. Stop hedefi yalnız yeni onaylı baseline'daki 8008 sahibi olmalıdır; geçmiş PID 9792 veya yalnız sayısal 12152 kullanılmaz. Tam exe/creation time/port ve launcher parent kimliği doğrulanır. Diğer dört servis ve proxy korunur.

1. Preflight: current process identity, main backend HEAD/clean status, immutable backend ZIP `a7e21cfca44c0963b689ff88f6d7e3f85f8a39c8a5a3b47e2dbeeaece6f66ef9`, source/config/launcher/dependency byte pinleri, Python 3.11.9/NumPy 2.2.6 ve PWA guardları geçer. Bakım lease'i ve insan koordinasyonu doğrulanır.
2. Var olan primary ve failback kaynakları değiştirilmeden kullanılır. Launcher `tools/attested-runtime.py` ve sabit `release/attested-8008-56cbd7e/launch-inputs.json` esas alınır. Yeni startup dosyaları yeni operasyon dizinine `open('x')` ile yazılır. Önceki paketlere veya startup kayıtlarına yazılmaz.
3. Geçişten önce primary ve failback owned testleri yeni kopya/staging alanında, ayrı portlarda tekrar kabul edilir. Eski `attested_acceptance.owned` yordamı orijinal sealed release içine sonuç yazar ve drift deneyi yapar; doğrudan eski paket üstünde çalıştırılmaz. Bu inceleme bunun yerine disk/config pinlerini, iki fresh-interpreter reference'ı ve 28 attestation/rollback unit guardını doğruladı; yeni canlı failback provası yaptığını iddia etmez.
4. Yalnız onaylı eski 8008 process identity kontrollü kapatılır. Port yabancı PID tarafından alınırsa durulur; ikinci bir süreç otomatik öldürülmez. Yeni headless runtime attested launcher ile başlatılır; reload/watch kapalı kalır. Aynı process tarafından dondurulan startup record, yeni PID/creation time ve portla eşleştirilir.
5. Yeni 173 fonksiyon fingerprint'i `314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b` ve exact source `56cbd7e05a40b106deda9298e2be28b488d0d952` doğrulanır. Fresh reference tek başına mevcut sürecin kanıtı sayılmaz. Aynı owned startup için mevcut launcher `verify` kontrolü geçmelidir.
6. Health/schema, direct/proxy eşitliği; dört sembolde salt-okunur metadata ve kullanıcı USC girdili manual analysis kabulü geçer. Broker server Exness-MT5Real50, USC, REAL_READONLY_DATA, execution_permission=false zorunludur. Spread **UNAPPROVED/BLOCK** olmalıdır; mevcut runtime'ın **UNVERIFIED/BLOCK** durumu bu kapının yerine geçmez. Tarihsel kaynak yetkisiz/SOURCE_NOT_SUPPLIED kalır; entry/SL/TP/lot null ve emir yolları kapalı kalır. Quote ve trade seansı eşit sayılmaz.
7. Primary başarısızsa yalnız operasyonun başlattığı ve kimliği doğrulanan yeni süreç kapatılır; yabancı port sahibine dokunulmaz. Bağımsız pinli failback başlatılır, startup ve güvenlik kabulü tekrar yapılır. Failback bellek snapshot'ı değildir; aynı onaylı kaynak/konfigürasyonun ayrı yeniden başlatmasıdır. Failback de başarısızsa STOP/manuel müdahale, PWA'ya geçiş yok.
8. A sonucu immutable receipt'e bağlanır: operation ID, paket SHA, yeni process identity, startup hash, fingerprint, test sonuçları ve korunan dört servis/hash. Failback'e düşüldüyse veya herhangi bir kapı eksikse A geçmedi sayılır; B çalışmaz.

## Aşama B — yalnız PWA allowlist

Kullanıcı onayı PWA APPLY'ı da açıkça içermeli; A receipt'i tam PASS olmalıdır. Bu incelemenin manifesti BLOCKED kalır. A sonrasında yeni kimliğe bağlı manifest/baseline türetimi kullanıcı onayı kapsamına açıkça alınmadan READY bayrağı veya manifest hash'i değiştirilmez.

1. Yeni post-A baseline ve same-process startup record ile read-only B preflight. Eski A baseline veya eski 9792 startup kaydı geçerli sayılmaz.
2. Orijinal PWA'nın 27 runtime/config guardı ve tüm ilgili envanteri yeniden kontrol edilir. AnalysisPanel/MarketChart/NewsPanel veya başka bir hedef değişmişse APPLY öncesinde BLOCK. Git fast-forward yoktur; orijinal Git değildir.
3. Taze operasyon yedeği alınır, her dosya SHA-256 doğrulanır, backup receipt immutable tutulur. Bu incelemenin mevcut yedeği 27 guard için doğrulanmıştır; bu, gelecekteki canlı apply yedeği yerine geçmez.
4. Yalnız dokuz payload dosyası. Bağımlılık yükleme, package/lock/proxy/news/bridge kopyalama yoktur. Yeni AnalysisPanel implementasyonu yazılmaz; `7890715` frontend payload hash'leri korunur. Her dosyadan önce source/target hash ve dış değişiklik kontrolü, sonra yazılan hash doğrulaması yapılır.
5. HMR canlı dev server'da beklenen etkidir; aynı bakım onayında açıkça yer almalıdır. Oturumdaki pending analiz temizlenir. Health/proxy ve frontend final hash'leri, dört sembollü manuel ekran, BUY/SELL/WAIT/INSUFFICIENT/BLOCK, loading/cancel/timeout, null plan/lot, USC varsayımsal sermaye ve V2 DESCRIPTIVE_ONLY doğrulanır. 19 bridge grafik sembolü V5 kapsamı kabul edilmez.
6. Service-worker için yeni production shell/autoUpdate, eski shell geçişi, offline analiz reddi ve API cache yasağı sınanır. Şu anki 5173 Vite dev server'dır; fixture cache başarısı gerçek telefondaki tüm eski cache'leri kanıtlamaz. Fiziksel telefon testi NOT_TESTED açıklaması korunur.
7. Smoke başarısızsa yalnız receipt kapsamındaki frontend dosyaları doğrulanmış yedekten geri alınır. Yeni dosyalar silinmez, yedekte retained alanına taşınır. Kullanıcı sonradan değiştirmişse otomatik overwrite/rollback yok; STOP ve kullanıcı baytları korunur. Backend/diğer servisler bu frontend geri alma işlemiyle değiştirilmez.

## Onaydan önce kapatılacak açık maddeler

- Dış workflow freeze/tek operatör teyidi: YOK.
- Güncel 8008 exact attestation: YOK; yeni A işlemiyle üretilecek.
- Aktif runtime spread policy: UNVERIFIED/BLOCK; hedef kabul UNAPPROVED/BLOCK.
- Eski A/B controller baseline'ları: stale ve BLOCK; yeni operator binding/controller + isolated phase/failback QA gerekli.

Bu maddelerden dolayı **bugün doğrudan uygulanabilir tek bakım onayı istenmez**. Tek onay metni taslağı hazırlanmıştır; eksikler kapanıp exact operasyon paketi hash'i sabitlendikten sonra kullanıcıya sunulur. Bu görevde A veya B çalıştırılmaz.
