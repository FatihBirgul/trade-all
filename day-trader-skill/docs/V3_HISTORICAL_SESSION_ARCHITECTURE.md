# Tarihsel broker seansı mimarisi

11 Kasım 2026. Başlangıç commit: `3c8adb810058b4738640f46bde84de8ec12205ad`.

## İncelenen mevcut davranış

`MT5Provider.metadata()` REAL salt-okunur modda `bound_hours=None` üretir.
`MT5_BROKER_HOURS` yalnız operator declaration'dır; exact broker symbol eşleşmesi
bile REAL tarihsel onayı sağlamaz. `session_evidence.parse_session_evidence()`
güncel haftalık export'u doğrular ve daima `historical_gap_authorized=False` döndürür.
Bu modül değiştirilmedi. MQL5 export tarih arşivi değildir.

`contracts._bars()` 200-256 gerçek kapalı mum, kimlik, OHLC, tick volume,
sıralama, üst üste binme ve eksik zaman aralıklarını denetler. M5=300, M15=900
saniyedir. Önceki mumun kapanışı ile sonraki mumun açılışı arasındaki bütün
aralık kontrol edilir. Takvim yokken hafta sonu etiketi boşluğu açıklamaz.
`validate_bars()` kapanmamış/future mumları reddeder; `capture()` son kapanışın
iki timeframe'den fazla geride olmasını reddeder. H4 dahil confirmation
mumları primary kapanışına kesilir. Off-grid provider zamanları mevcut
sözleşme gereği otomatik yuvarlanmaz.

`unified_analyze()` eksik mum DataError'ını `INSUFFICIENT_DATA`,
`DATA_UNAVAILABLE`, `trading_eligibility=BLOCKED` ve null plan ile döndürür.
Bu davranış yalnız önceki rapordan alınmadı; baseline ve yeni API testleriyle sınandı.
`core.analyze()` broker contract, trade session ve spread kontrollerini stratejiden
önce çalıştırır. `risk_check`, `size_lots`, `policy.assess` ve broker PnL oracle
ayrı kapılardır. USC/USD eşitliği varsayılmaz. V2 adaptörleri DESCRIPTIVE_ONLY;
confluence bağlamı kapıları atlayamaz. AST no-order denetimleri mevcut pakettedir.
Spread template dosyasında dört limit hâlâ UNAPPROVED/null; bu görev onları değiştirmez.

## Dar entegrasyon

Akış: MT5 salt-okunur kaynak -> metadata/quote -> bağımsız tarihsel policy ->
snapshot `_bars` -> market data kontrolleri -> mevcut V4/V5 analiz -> finansal
kapılar -> final karar. Mevcut motor/strateji yeniden yazılmadı.

`historical_sessions.py` strict importer, immutable Candidate, code-owned
SourceReview ve HistoricalEvidenceStore sağlar. `MT5Provider` varsayılan boş
store'u ya da açık allowlist'ten okunan adayları kullanır. Ortam yalnız dosya
seçer; onay tanımlamaz. Testler Python constructor dependency injection ile
sentetik SourceReview sağlar. Production pin listesi boş bırakıldı.

`contracts.bind_historical()` provider'ın code-owned capability'sini alır;
snapshot symbol/server/currency ve decision as-of ile tekrar eşleştirir.
Retrospective capability burada reddedilir. `_bars(historical=...)` gerçek
boşluğun tamamının tarih kapsamına girmesini ve quote-open ile hiç kesişmemesini
ister. REAL metadata içindeki serialized quote_hours/onay boolean'ı bunu aşamaz.
Kısmi kapsam içindeki açıklanamayan tek boşluk bütün snapshot'ı reddeder.
OHLC doldurulmaz; snapshot'taki timestamp listesi provider ile aynı kalır.

Boşluktan sonraki mumun başlangıcı quote-open olmalı veya bütün bucket
kapsanırken bucket içinde açık quote aralığı ve gerçek mumda pozitif tick volume
bulunmalıdır. Böylece 23:00:30 ilk quote'u olan 23:00 M15 bucket'ı 23:15'te
geçerli olabilir. Trade saatleri bu veri kontrolüne katılmaz.

İncelenmiş trade aralıkları yalnız tarihli `VERIFIED_HISTORICAL_TRADE` olarak
snapshot'a yazılır. `broker_status()` kapsam dışında UNKNOWN, close-only'de
DISABLED döndürür. Quote geçerli olsa bile trade completeness eksikse yeni
pozisyon uygunluğu UNKNOWN kalır. Haftalık saatlere dönüşüm yapılmaz.

## API ve zaman bilgisi

`/api/v5/analysis` request şeması değişmedi; evidence/review alanları 422'dir.
Yanıta eklenen `historical_session_evidence` audit sözlüğü, başarısız capture
durumunda da kalır. Aşamalar, hash'ler, kapsam, as-of ve durum bildirilir;
orijinal dosya yolu/referansı/hesap kimliği yayımlanmaz.

Effective, publication, acquisition, operator review ve decision knowledge
zamanları ayrıdır. Provider replay/live için `DECISION_AS_OF` kullanır; belge ve
inceleme karar anında bilinmelidir. CLI `RETROSPECTIVE_DATA_QUALITY` ile daha
sonra edinilen belgeyi geçmiş veri açıklamasında kullanabilir. Bu nesne canlı
snapshot'a veya confluence oylarına taşınamaz. Gelecek bucket kapalı diye
tarihsel veri kabul edilmez.

Baseline 519 test korunmuştur. Gerçek Exness kaynağı edinilmedi; gerçek hesap
veya 8006 servisiyle yeni market-data kabul testi yapılmadı. Üretim durum:
`BLOCKED_BY_EXTERNAL_EVIDENCE`.
