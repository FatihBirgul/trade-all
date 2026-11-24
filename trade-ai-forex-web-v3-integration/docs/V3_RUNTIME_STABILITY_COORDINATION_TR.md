# Runtime kararlılığı ve son deployment koordinasyonu

12 Kasım 2026, Europe/Istanbul. **Sonuç: BLOCKED.** Yeni özellik veya AnalysisPanel geliştirmesi yapılmadı. Backend, orijinal PWA ve canlı servisler değiştirilmedi. Bu incelemenin kapsamı kanıt toplama, salt-okunur QA, advisory koordinasyon guardı ve operasyon planıdır.

**A — Güncel port/process matrisi.** Her satır ayrı TCP listener ve OS creation time ile doğrulandı. Başlangıç ve bitiş kanıtları yeni `release/coordinated-operation-20261112-01` paketindedir; environment/komutlar allowlist/sanitizasyonla saklanır. Token, hesap numarası veya gerçek bakiye dışa aktarılmaz.

| Port | PID | Başlangıç (İstanbul) | Parent | Kaynak/komut | Health |
|---|---:|---|---:|---|---|
| 5173 | 8592 | 12 Kasım 13:09:59.635 | OS parent zinciri begin/end.json'da | Orijinal PWA, Vite/Node; dev HMR açık | 200; engine proxy 200 |
| 8005 | 1676 | 12 Kasım 13:09:54.025 | begin/end.json'da | Orijinal PWA, mt5_bridge:app | connected=true |
| 8006 | 8804 | 12 Kasım 13:09:55.776 | begin/end.json'da | Main backend, forex.api:app | OK |
| 8007 | 6592 | 12 Kasım 13:09:57.198 | 4724 | Orijinal PWA, news_bridge:app | 200 |
| 8008 | 12152 | 12 Kasım 17:04:31.763 | 12100 | runtime-candidate, forex.api:app | OK; exact version UNVERIFIED |

8008 executable global Python311 yoludur; bu tek başına global environment kullanıldığını göstermez. Parent 12100, `AppData/Local/TradeAI/V5CandidateRuntime/Scripts/python.exe` launcher'ıdır; başlangıcı 17:04:31.615. Parent PowerShell 7464, 16:57:23.381'de açılmıştır; onun parent'ı Explorer 5480'dir. Zincir yalnız parent creation time çocuğu önceliyorsa izlenmiştir; sonradan yeniden kullanılan parent PID'leri gerçek ancestor varsayılmaz. Tüm beş portun exe/parent/start/cwd/safe environment bilgisi makine raporundadır. Python servislerinde --reload/--watch bayrağı gözlenmedi; bütün olası harici restart mekanizmalarının yokluğu iddia edilmez.

**B — Kök neden ve PID yeniden kullanımı.** Geçmiş onaylı postflight'ta 8007 sahibi PID 12152'nin creation FILETIME değeri `134388755316673854`; güncel 8008 sahibi aynı sayısal PID'nin değeri `134389658717631879`. Bunlar farklı süreç kimlikleridir. Güncel 8007 PID 6592'dir; 12152'nin şu anda iki portu dinlediği gözlenmedi. Böylece eski/new PID eşleştirmesi yalnız sayıdan çıkarılmadı.

Doğrulanan yeni başlangıç mekanizması PowerShell → V5CandidateRuntime → doğrudan `python -B -m uvicorn forex.api:app --host 127.0.0.1 --port 8008` zinciridir. `19SymbolBackups/v5-8008-20261112-170431.err.log` aynı PID ve portla server başlangıcını doğrular. Bu komut attested launcher değildir. PowerShell'in Explorer parent'ı olması interaktif başlatmayla uyumludur; hangi kişi/ajan/komut geçmişinin bu işlemi tetiklediğini kanıtlamaz.

PID 9792'nin kesin sona erme zamanı **UNVERIFIED**. Eski frozen startup 11 Kasım 23:32:18 İstanbul'a aittir; mevcut Windows boot zamanı 12 Kasım 12:11:51.500 İstanbul'dur. Eski process bu boot'tan önceki oturuma aittir ve mevcut süreç olamaz; ne zaman/neden sona erdiği yalnız bu bulgudan belirlenemez. System/Security event sorguları erişilebilir sonuç vermedi; bunlar “olay yok” kanıtı sayılmadı. Özet statü **ROOT_CAUSE_UNVERIFIED**: başlatma yolu doğrulandı, actor/tetikleyici ve attested launcher'ın neden bypass edildiği kanıtlanmadı.

**C — Başlatıcılar ve çakışma riski.** Masaüstü `Trade AI Başlat.cmd` yalnız 5173/8005/8006/8007 başlatır; mevcut dosyada 8008 başlatma komutu yoktur. Bu dosyanın güncel 8008 başlangıcına neden olduğu söylenemez. Port dolu/boş denetimi process SHA/creation time doğrulamaz. Script ayrıca MT5/Tailscale başlatma davranışı içerdiğinden bu görevde çalıştırılmadı/değiştirilmedi. Açık PowerShell'den doğrudan Uvicorn, V5Runtime/V5CandidateRuntime ve diğer deployment araçları advisory lease'e uymadan 8008'i yeniden başlatabilir. İlgili Windows service veya scheduled-task eşleşmesi gözlenmedi; event/history kanıtının sınırları root-cause-evidence.json'da açıklanır. Ortamların kurulu disk metadata'sı çalışan process'in yüklediği NumPy sürümünün kanıtı sayılmaz.

**D / E — Attestation.** İncelenen release startup kayıtları ile candidate/TradeAI startup dosyalarında güncel PID/creation time'a bağlı güvenilir frozen loaded-code kaydı bulunmadı. Güncel komut doğrudan Uvicorn'dur. Durum **EXACT_RUNNING_VERSION_UNVERIFIED** olarak korunur. Eski 9792 kaydı veya yeni fresh interpreter reference'ı 12152'ye atanmadı. Önceki fingerprint yalnız hedef referanstır.

**F / K — Backend ve failback hazırlığı.** Main HEAD exact `56cbd7e05a40b106deda9298e2be28b488d0d952`, clean. Mevcut attested ZIP SHA `a7e21cfca44c0963b689ff88f6d7e3f85f8a39c8a5a3b47e2dbeeaece6f66ef9`, CRC ve 582 arşiv girdisi hash'i doğrulandı. Source manifest, primary/failback kaynak envanteri, config/assets/launcher/reference/dependency pinleri kontrol edilir. Pinli izole environment Python 3.11.9 ve NumPy 2.2.6'dır; global paketlere yazılmaz.

Primary ve failback için ayrı fresh interpreter'larda salt-okunur reference üretildi; ikisi de 173 fonksiyon ve `314eab9f6fb646919191851e5fd04a6a618a525c628e8f5bc1783290a2dace7b` verdi. Server başlatılmadı; bu mevcut 8008 attestation'ı veya yeni canlı failback provası değildir. Önceki sealed acceptance kayıtları tarihsel kanıttır. Yeni bakım öncesi owned primary/failback QA, eski immutable pakete yazmayan ayrı staging'de yapılmalıdır.

Mevcut `attested-cutover.py` default read-only preflight çalıştırıldı ve beklendiği gibi eski process baseline nedeniyle BLOCK verdi. Eski guardı gevşetmek veya 12152'yi onaylı göstermek için eski JSON'lar değiştirilmedi. PWA'nın mevcut live guardı da eski 9792 kabulüne bağlıdır. Yeni baseline/operator binding ve A→B receipt entegrasyonu ayrıca QA edilmeden eski APPLY komutları kullanılamaz.

**G / H — PWA korunması.** Başlangıç gerçek HEAD `789071541377cb926f9c9904ae46aabf4250dc21`. AnalysisPanel yeniden yazılmadı. Güncel dokuz payload dosyası bu release'in source SHA değerleriyle eşleşir. AnalysisPanel, MarketChart, NewsPanel, package/lock, Vite config, source/public ve var olan user `.bak` dosyalarının başlangıç/bitiş hash'leri korunur. `/engine → 8008`, `/mt5 → 8005`, `/news → 8007` ve Tailscale allowed host değiştirilmedi. PWA dev-server kaynağı orijinal dizindir; Git fast-forward uygulanmadı.

Yeni `pwa/manifest.json`, önceki revision2 paketini değiştirmeden yeni dizinde hazırlanır. Current backend fingerprint/startup null/UNVERIFIED, readiness BLOCKED kalır. Hedef referans ayrı alandadır; mevcut process'e sürüm atamaz. Dokuz dosyalı allowlist, 27 hedef guard, diff/conflict ve yedekler korunur. Manifest/hash/source_head değerleri paket içinde kesinleştirilir. Orijinal dist SW/manifest varlığı ayrı raporlanır; mevcut live origin'in cache durumu veya fiziksel telefon testi yapılmış sayılmaz.

**I — Test sonuçları.** Bu görevde yalnız ilgili güncel gruplar çalıştırıldı; sayılar birbirine eklenip toplam benzersiz test iddiası yapılmaz:

| Grup | Bu görevde son sonuç | Kapsam |
|---|---|---|
| Yeni koordinasyon/lease/preflight unit testleri | 20/20 PASS | Sentetik durumlar; stale lock/PID reuse/drift/no takeover/provider health/attestation |
| Mevcut attested runtime unit testleri | 28/28 PASS | Mock/sentetik startup, source/dependency, no-order, failback/controller guardları |
| PWA promotion/rollback | 17/17 PASS | Yalnız disposable target; target corruption/user edits/backup/rollback/CLI guards |
| Primary/failback reference | İki reference PASS | Fresh interpreter; 173 fonksiyon; serving process yok |
| Current 8008 broker/readonly API | Dört kayıt | Güvenli null plan/USC/historical BLOCK geçer; spread UNAPPROVED kabulü FAIL |
| A_PLAN read-only preflight | Paket logunda | Yalnız baseline/release pin hazırlığı; APPLY=false |
| B preflight, startup kanıtı olmadan | Beklenen BLOCK | EXACT_RUNNING_VERSION_UNVERIFIED |

TypeScript/ESLint/build/browser40/preview3/cache7, önceki aynı frontend kaynakları için başarılı kanıttır; bu görevde yeniden çalıştırılmış gibi sunulmaz. Önceki 62/62 ve 17/17 gibi alt gruplar tekrar sayılıp bir toplam üretilmez. İlk canlı strict spread assertion'ı UNVERIFIED gördüğü için durdu; sonraki bounded inceleme bu farkı dört sembolde kaydetti. Toplam bir ilk deneme + dört kayıtlı manuel analitik POST; otomatik tarama/retry döngüsü yoktur.

**J — Dry-run.** Hem önceki revision2 hem yeni türetilmiş PWA manifesti güncel hedefe karşı read-only kontrol edildi. Yeni paket sonucu 9 dosya/27 guard/**0 yazma/0 silme**. Kaynak/hedef payload veya envanter değişirse BLOCK. Bu sonuç deployment izni veya runtime acceptance değildir. Canlı backup/APPLY/rollback yapılmadı; 27 yedek dosyanın SHA'sı mevcut hedef guardlarıyla doğrulandı.

**L / M — Güvenlik ve mevcut config farkı.** Güncel dört sembolde Exness-MT5Real50/USC broker kimliği, REAL readonly safety validator, execution_permission=false, INSUFFICIENT_DATA/BLOCKED ve null Entry/SL/TP/lot doğrulandı. Tarihsel registry SOURCE_NOT_SUPPLIED; historical_gap_authorized=false. Ancak spread policy **UNVERIFIED / BLOCK**, onaylı kaynak paketin hedeflediği **UNAPPROVED / BLOCK** değildir. Başlangıç safe environment'ında pinli MT5_SPREAD_POLICY_FILE bulunmaması bu farkla uyumludur; tek başına tüm sebebi kanıtlamaz. Limit uydurulmadı, onay verilmedi. PWA bu durumda plan göstermez. Direct/proxy schema eşittir; emir route'u yoktur. MT5 login/logout veya order_check/order_send çağrısı yapılmadı.

**N — Yeni operasyon paketi.** `release/coordinated-operation-20261112-01` ve benzersiz `TRADE_AI_V3_COORDINATED_OPERATION_20261112_01_BLOCKED.zip`; SHA-256 yan dosyası bulunur. Paket begin/end process matrix, root cause, release/config pinleri, fresh reference'lar, güncel API güvenlik gözlemleri, PWA manifest/diff/yedek, guard kaynak/test logları ve A/B planını içerir. Önceki BLOCKED/READY paketleri değiştirilmez. Yeni yerel commit yalnız bu operasyon QA/rapor araçlarına aittir; önceden mevcut untracked kullanıcı dosyaları korunur. Push/merge yapılmaz.

**O / P — Minimum kullanıcı işlemleri ve onay sınırı.** Önce servis/kaynak değiştirebilen dış iş akışlarının duraklatıldığı ve tek operatör sorumluluğu açıkça teyit edilmelidir. Ardından yeni operator binding/controller ve owned A/failback QA kapatılıp exact operasyon ZIP/baseline hash'leri tek bakım onay metnine bağlanmalıdır. Hazır taslak `V3_COORDINATED_APPROVAL_DRAFT_TR.md` içindedir. Kullanıcıdan şu anda eksik alanlı bir onay istenmez. A runtime geçişi ve conditional B PWA APPLY/HMR/cache/rollback kapsamı açıkça ayrı belirtilir; A başarısızsa B yoktur. Aktif runtime'ın fingerprint eksikliği veya spread farkı yalnız disk hash tekrarıyla kapatılmaz.

Advisory guard diğer ajanları durdurmaz. Lease yalnız benzersiz izole operator state dizininde çalışır; exclusive create ve owner PID/creation time/expiry kontrolü yapar. Stale lock raporlanır; başka actor'ın dosyası silinmez veya eski PID otomatik öldürülmez. Bu görevde canlı bakım lease'i alınmadı; `ADVISORY_UNACQUIRED` planı hazırlanmıştır. Release SHA, config/source/dependency pinleri, beş port kimliği, hedef/source hash'leri ve proxy/provider health kontrolü taze preflight'ta tekrarlanır. B için same-process startup ve launcher verify zorunludur.

Son cevaplar: **PARTIAL / NO / PARTIAL / YES / NO**. Aktif runtime exact sürüm kabulü, insan koordinasyonu ve yeni operator binding/controller QA kapanmadan canlı değişikliğe geçilmez.
