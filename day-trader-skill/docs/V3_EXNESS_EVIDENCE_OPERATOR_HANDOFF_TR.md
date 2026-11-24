# Operatör teslimi ve tek komut

Gerçek XAUUSDc/EURUSDc takvimi: BLOCKED_BY_EXTERNAL_EVIDENCE. Bugün hiçbir
kullanıcı PowerShell işlemi gerekli değildir. Önce brokerın orijinal cevabı/belgesi gerekir.

## Hazır destek mesajı

Exness destek ekibine: Exness-MT5Real50 sunucusunda Standard Cent hesabın
exact XAUUSDc ve EURUSDc sembolleri için 6-11 Kasım 2026 tarihlerini kapsayan
tarihsel seans belgesini paylaşabilir misiniz? Her gün için fiyat akışının
quote açık/kapalı aralıklarını, ayrı yeni pozisyon trade açık/kapalı aralıklarını,
varsa close-only, rollover/bakım, cuma kapanışı/pazar açılışı, holiday/istisnai
kapanışları ve DST uygulamasını istiyoruz. Lütfen kaynak timezone ve tarihli UTC
offset'lerini, belgenin yayın/update ve geçerlilik tarihini belirtin. Genel
XAUUSD/EURUSD saatlerinin Standard Cent `c` sembollerini kapsayıp kapsamadığını
açıkça teyit edin. Hesap numarası, bakiye veya giriş bilgisi gerekmiyor.

Bu mesaj hazırlanmıştır; herhangi bir kişiye/servise gönderilmemiştir.

## Belge geldiğinde

1. Orijinal belgeyi ve alınma zamanını operator-owned yerel evidence dizininde sakla.
2. Kaynak kimliğini bağımsız broker kanalıyla doğrula; URL tek başına onay değildir.
3. Orijinal SHA-256 ve exact server/product/symbol kapsamını kaydet.
4. Yalnız kanıtlı günlerin coverage'ini yaz. Quote ve trade'ı ayrı çıkar; close-only'yi varsayma.
5. Yerel saatleri IANA zone, explicit fold ve dated offset rejimleriyle UTC'ye çevir.
6. Holiday/istisna completeness ve diğer kaynaklarla çatışmayı incele.
7. Yeni CLI ile format/hash/scope/reconcile raporu al; bu hâlâ onay değildir.
8. İnsan incelemesi bitince JSON ve orijinal belge hash'lerini bağlayan SourceReview
   kaydını ayrı code review ile production registry'ye ekle. İnceleme zamanı edinimden
   sonra olmalı; kaynağın broker kimliği ve Cent kapsamı review reference'ında kanıtlanmalı.
9. Aynı komutla scoped gap reconciliation yap, full regression ve izole API kabulünü tekrarla.
10. Ana V3 promotion ve canlı runtime cutover için ayrı yetkili iş yürüt.

8. adım gerçek kanıt olmadan yapılmadı. 10. adım bu görevde yapılmaz.

## Tek komut: validate / reconcile / report

İzole repo içinden, NumPy 2.2.6 kullanan mevcut izole Python ile örnek:

```powershell
& '%USERPROFILE%\trade-ai-v3-v2-p1\.venv\Scripts\python.exe' -m forex.historical_sessions --root '%USERPROFILE%\broker-evidence' --file 'xauusdc-history.json' --symbol XAUUSD --as-of 2026-11-11T12:00:00Z --gap-start 2026-11-09T22:00:00Z --gap-end 2026-11-09T23:00:00Z
```

Bu root örnektir; dizin bu görevde oluşturulmadı. Orijinal doküman JSON'daki
source.original_file relatif yolunda aynı root altında bulunmalıdır. Birden çok
dosya için `--file` tekrarlanabilir. EURUSDc için `--symbol EURUSD` ve exact ayrı
JSON kullanılır. CLI her zaman dry-run/read-only; onay veya servis değişikliği yapmaz.

Exit 0: bağımsız pin ile eligible kapsam mevcut; tek başına istenen gap'in kapalı
olduğunu garanti etmez, `gap.quote_closed` ayrıca okunur. Exit 3: belge/approval
kapısı kapalı; BLOCKED_BY_EXTERNAL_EVIDENCE. Exit 2: format/path/hash/config hatası.
`--as-of` replay/data-quality tarihidir; CLI acquisition bilgisini bugünkü knowledge
ile açık RETROSPECTIVE_DATA_QUALITY olarak değerlendirir. Eski canlı karar
confluence'ına geriye dönük onay yazılmaz.

Üretim dosya seçimi için `MT5_HISTORICAL_EVIDENCE_ROOT` ve relatif isimlerden
oluşan `MT5_HISTORICAL_EVIDENCE_FILES` JSON listesi vardır. Bunları değiştirmek
approval değildir; runtime'a uygulama ayrı cutover işi olarak kalır.
