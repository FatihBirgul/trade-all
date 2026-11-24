# Yeni doğrulanabilir 8008 runtime — 11 Kasım 2026

READY_FOR_APPROVAL yalnız 8008 runtime replacement + test edilmiş failback içindir. Mevcut13988 exact loaded sürümü EXACT_RUNNING_VERSION_UNVERIFIABLE_WITHOUT_CUTOVER; yeni aynı-process startup provenance ayrı portlarda doğrulandı. Güncel belge V3_ATTESTED_RUNTIME_HANDOFF_TR.md; ZIP TRADE_AI_V3_ATTESTED_8008_56cbd7e_READY.zip. Controller varsayılanı read-only preflight, canlı dalı henüz çalıştırılmadı. PWA_APPLY_NOT_AUTHORIZED korunur; original AnalysisPanel dış değişikliği ayrıca inceleme ister. Backend/proxy hash kapıları ve beş servis korunur. Yeni ve yalnız runtime kapsamlı tek kullanıcı onayı beklenir.

Aşağıdaki kayıtlar önceki tarihsel bağlamdır.

# 8008 PWA release uzlaştırması — 11 Kasım 2026

Onaylı /engine -> 8008 korunur; routing drift artık engel değildir. V5 API ve actual proxy kabulü geçti. Kalan engel VERSION_UNVERIFIED: PID13988 için aynı process'e ait loaded-code attestation yok. Son durum BLOCKED_BACKEND_RUNTIME; şu an PWA APPLY onayı istenmez. Güncel belgeler V3_RUNTIME8008_RECONCILIATION_TR.md ve V3_RUNTIME8008_RELEASE_PLAN.md. Eski 8006 restart planları uygulanmaz. Yeni review ZIP ayrı oluşturulur; eski BLOCKED ZIP değiştirilmez.

Aşağıdaki notlar önceki tarihsel bağlamdır.

# Son mühürleme engeli: dış proxy değişikliği

11 Kasım 2026 21:55:25 İstanbul: orijinal PWA vite.config.ts dışarıdan /engine hedefini 8006 -> 8008 değiştirdi. 8008 PID 13988 yeni historical alanlı schema sunuyor; 5173 proxy artık bu schema'yı veriyor. 8006 PID 8284 aynı ve exact loaded sürümü VERSION_UNVERIFIED. Görev bu değişikliği yapmadı veya geri almadı. Son preflight BLOCKED; paket yalnız inceleme içindir (deployable=false). Aşağıdaki 8006 operasyon sırası uygulanamaz: önce yetkili backend/proxy hedefi uzlaştırılmalı, sonra manifest/backup ve uçtan uca kabul yeniden mühürlenmelidir. Yeni canlı operasyon onayı bu aşamada istenmiyor. Önceki başarılı kabul sonuçları test edilmiş adayın kanıtıdır; değişmiş canlı routing kabulü değildir.

# 11 Kasım 2026 final release uzlaştırması

Backend 56cbd7e + değişmeyen PWA UI RC 34c6ec2 için yeni paket:
`release/TRADE_AI_V3_RECONCILED_56cbd7e_34c6ec2_BLOCKED_REVIEW.zip`.
Durum BLOCKED; eski backend 3c8adb8 paketini bu geçişte kullanma.
Güncel rapor V3_FINAL_RELEASE_RECONCILIATION_TR.md; tek geçerli yeni operasyon
sırası V3_FINAL_CONTROLLED_CUTOVER_PLAN.md ve compatibility matrix'tedir.
Main/original PWA değişmedi; canlı restart/APPLY/HMR yapılmadı. Gerçek Exness
kanıtı ve spread onayı yok; güvenli BLOCK korunur. Yeni kullanıcı onayı beklenir.
Aşağıdaki önceki kayıtlar tarihsel bağlamdır.

# Kontrollü geçiş için sonraki adım

Hazırlık READY_FOR_APPROVAL. Önce V3_LIVE_CUTOVER_PREFLIGHT_TR.md ve V3_LIVE_CUTOVER_PLAN.md incelenir. Kullanıcının tek açık operasyon onayı 8006 kontrollü stop/start, orijinal9 PWA dosyasının backup/apply işlemi,5173 HMR/UI yenilemesi ve güvenli rollback denemesini kapsamalıdır. 8005/8007 ve Tailscale ayarları korunur. Bu onay gelmeden canlı işlem yapılmaz.

Onay sonrası fresh process/config/source/account preflight → yeni8006/private manifest → canlı dört-sembol API kabul receipt'i → backup/hash guarded PWA APPLY → local/Tailscale UI/manual smoke. Hata/user drift'inde STOP veya safe rollback; ikinci rutin izin akışı gerekmez, ilk onay bu rollback denemesini kapsar.

Onay gelmezse mevcut backend/PWA çalışmaya devam eder. PID7532 artık geçerli değil; son doğrulanan backend child15996/parent8532 V5Runtime'dır. Son gözlem anındaki kimlik gelecekte sabit kabul edilmez.

Dört maximum spread/birim/effective date/provenance onayı ve exact XAUUSDc tarihsel seans kanıtı ayrı dış girdilerdir. Bu eksikler güvenli ret veren runtime geçişini engellemez; işlem planını bloke eder. Gerçek telefon PWA kabulü ayrıca gereklidir. Push/merge veya emir talep edilmemiştir.
