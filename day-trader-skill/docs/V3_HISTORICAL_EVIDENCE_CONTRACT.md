# Tarihsel kanıt sözleşmesi

Şema: `broker-historical-sessions-1`, UTF-8 JSON. Çalışan örnek:
`tests/fixtures/historical/synthetic.json` ve aynı dizindeki `original.txt`.
İkisi de açıkça SYNTHETIC_TEST_EVIDENCE'dır; gerçek Exness çizelgesi değildir.

| Alan | Anlam / denetim |
| --- | --- |
| schema_version, evidence_id | Sabit şema, sınırlı ASCII kimlik |
| broker, server | Ayrı broker organizasyonu ve exact sunucu |
| product, account_currency | Standard Cent / USC kapsamı |
| canonical_symbol, broker_symbol | XAUUSD/XAUUSDc vb.; dört exact Cent alias desteklenir |
| source.kind, organization, reference | Broker belgesi / sentetik / operatör / güncel haftalık ayrımı; belge veya URL referansı |
| source.original_file, original_sha256 | Allowlist root'a göre relatif orijinal dosya ve gerçek baytlardan SHA-256 |
| published_at_utc, acquired_at_utc | Yayın/update anı ve edinim anı; yayın <= edinim <= import saati |
| effective_start_utc, effective_end_utc | En çok 366 günlük üst tarih zarfı; aralığın tamamını otomatik onaylamaz |
| source_timezone | Geçerli IANA zone; bilinmeyen server offset kabul edilmez |
| conversion_rule | EXPLICIT_UTC_WITH_OFFSET_REGIMES |
| dst_regime | start_utc, end_utc, offset_seconds; zarfı boşluksuz ve çakışmasız kapsar |
| completeness | quote, trade, calendar, timezone için ayrı COMPLETE / INCOMPLETE |
| verification_status | Aşağıdaki kanıt seviyelerinden biri; JSON alanı yetki vermez |
| operator_review | PENDING / APPROVED / REJECTED; APPROVED tek başına yetki değildir |
| conflicts | En fazla 16 kısa çatışma açıklaması |
| coverage | Takvimin açıkça eksiksiz olduğu tarihli alt aralıklar |
| quote_open | Yalnız fiyat akışının açık olduğu aralıklar |
| trade_open | Yalnız yeni pozisyon açılabilir aralıklar |
| close_only | Kaynak açıkça kanıtlıyorsa mevcut pozisyon kapatma aralıkları |
| maintenance, weekend_closed, holidays, exceptional_closures | Ayrı tarihli tam quote-kapalı dönemler |

Her interval `{start_utc, end_utc}` biçiminde `[start,end)` kullanır. UTC
timestamp'leri `YYYY-MM-DDTHH:MM:SSZ` biçiminde saniye hassasiyetlidir. Yerel
saatler doğrudan import edilmez; `local_to_utc()` ile dönüşüm yapılır. Ambiguous
saat explicit fold ister; nonexistent saat reddedilir. DST offset'leri explicit
başlangıç/bitişin iki yanında ve dönem boyunca saatlik IANA kontrolünden geçer.
Bu, brokerın hangi zone'u kullandığını ispatlamaz; kaynak incelemesinin bir parçasıdır.

Quote/trade saatleri birbirinden türetilmez. Trade-only belge quote
completeness=INCOMPLETE taşımalıdır. Quote completeness ayrıca calendar ve
timezone ile COMPLETE olmadan kapalı boşluk yetkisi verilmez. Trade eksikliği
veri açıklamasını engellemeyebilir, fakat trade eligibility sağlayamaz.
Tam quote-closed gün için quote_open=[] geçerlidir; ancak bu günün coverage ve
calendar completeness iddiası kaynak tarafından ayrıca kanıtlanmalıdır.
Kaynakta yer almayan tarih coverage'e eklenemez. Holiday listesi boşsa ilgili
kapsamda özel holiday olmadığı iddiası da bağımsız incelemede doğrulanmalıdır.

## Kanıt seviyeleri ve yetki

SOURCE_NOT_SUPPLIED, FORMAT_VALIDATED, OPERATOR_DECLARED, CURRENT_WEEKLY_ONLY,
HISTORICAL_SCOPE_INCOMPLETE, HISTORICAL_SOURCE_VERIFIED, CONFLICTING_EVIDENCE,
REJECTED durumları ayrıdır. Format/hash doğrulaması source authentication değildir.
Eski `mt5-session-evidence-1` şeması ve CURRENT_WEEKLY export değişmedi;
tarihsel şemaya otomatik çevrilmez ve historical_gap_authorized daima false'dur.

`SourceReview` yalnız Python/deployment tarafından sağlanır: tam JSON baytları
SHA-256, orijinal belge SHA-256, reviewed_at_utc, review_reference. Tam JSON pin'i
broker/symbol/date/URL/zone/calendar dahil bütün iddiaları bağlar. İnceleme edinimden
önce veya karar bilgisinden sonra olamaz. Gerçek belge kimliği, exact Cent ürün
kapsamı ve çevrimler insan tarafından doğrulanmadan production listesine pin
eklenmez. Şu an liste boştur. Sentetik kaynaklar varsayılan production registry'de
pin olsa bile kabul edilmez; yalnız testte explicit Python review injection vardır.

Çakışan kapsamlı kaynaklar aynı saatleri gösterse bile otomatik birleştirilmez;
ayrı uzlaştırma gerektirir. Aynı identity'de bilinen ancak henüz onaysız tarihsel
kaynakla çakışma da güvenli ret üretir. Farklı sembolün kaydı başka sembole yetki
vermez. Ayrık tarih aralıkları desteklenir; aradaki tarihler UNKNOWN'dır.

`historical_gap_authorized=true` yalnız bazı tarihli alt kapsamların policy'ye
girebildiğini bildirir. Her boşluk ayrıca `quote_closed(start,end)` ile kontrol edilir;
bu boolean genel geçmişe veya BUY/SELL'e izin değildir. Asıl yetki JSON içinde
değil, immutable code-owned policy nesnesindedir.
