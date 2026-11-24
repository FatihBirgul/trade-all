# Tarihsel kanıt güvenlik sınırı

`forex/historical_sessions.py` yalnız açıkça seçilmiş operator-owned yerel root
ve relatif dosyaları okur. Root ve içeriği güvenilmeyen başka süreçlerin
yazımına açık olmamalıdır. Bu önkoşul, dosya sistemi yarışlarını güvenlik sınırı
dışında bırakır; importer bir hostile-filesystem sandbox değildir.

JSON en fazla 256 KiB; orijinal belge en fazla 8 MiB; en fazla 32 record,
toplam 2048 interval/record ve 32 DST rejimi vardır. Unknown fields, duplicate
JSON keys, nonfinite sabitler, hatalı UTF-8, aşırı nesting, yanlış tarih/zone,
overlap, duplicate interval ve scope dışı zamanlar reddedilir. Cross-source
interval kesişimleri sıralı taranır; sınırsız interval çarpımı kullanılmaz.

Absolute/drive/UNC-root/parent traversal/ADS yolları reddedilir. Her path
bileşeninde symlink ve Windows reparse/junction biti incelenir; resolved yol root
içinde kalmalıdır. Dosya regular ve single-link olmalıdır. Açılan handle'ın
inode/device kimliği önceki lstat ile eşleştirilir; read(limit+1) kullanılır.
Kanıtın referans verdiği orijinal belge de aynı path sınırından geçer ve gerçek
SHA-256 eşleştirilir. Testler gerçek hardlink, native reparse-bit enjeksiyonu,
path traversal, absolute path, ADS, hash değişimi ve boyut sınırlarını kapsar.
Windows symlink privilege gerektiren oluşturma testi atlanmaz; lstat sonucu
bağımsız olarak enjekte edilir. Bu test gerçek symlink yaratıldığı iddiası değildir.

Parser/importer yalnız FORMAT_VALIDATED üretir. `verified=true`, APPROVED veya
HISTORICAL_SOURCE_VERIFIED yazmak yetki kazandırmaz. SHA-256 kaynak organizasyonu
kanıtlamaz. SourceReview bağımsız belge kimliği ve kapsam incelemesinin deployment
attestation'ıdır; otomatik web doğrulaması değildir. Production registry boş,
sentetik kaynak production yolunda ayrıca reddedilir. Unreviewed dosya ve
registry dışı değişiklikler geçmiş mum kabulünü açmaz.

`MT5_HISTORICAL_EVIDENCE_ROOT` ve `MT5_HISTORICAL_EVIDENCE_FILES` yalnız allowlist
ve aday dosyaları seçer. İkisi birlikte verilir; ikinci değer sınırlı JSON string
listesidir. Ortamdan/API'den review, test bayrağı, Python module veya approval
alınmaz. Dosya importunda eval, pickle, subprocess, ağ erişimi veya keyfi Python
çalıştırma yoktur. CLI yalnız validate/reconcile/report yapar, onay yazmaz.

API'ye yalnız hash, kimlik kapsamı, aşama sonuçları ve zamanlar yansır;
orijinal reference/path, ham belge, hesap login/balance veya key bilgisi yansımaz.
Path hataları sabit metne çevrilir. Kaynak metni loglanmaz. CLI JSON raporu
stdout'a basar; yazma/promotion/restart işlemi yapmaz.

REAL metadata'daki quote_hours veya historical_gap_authorized boolean'ı candle
kapısında yetki değildir. Asıl policy Python dependency sınırından alınır,
snapshot identity ve as-of ile bağlanır. Üçüncü taraf Python kodu çalıştırabilen
bir aktör bu process'i zaten kontrol eder; capability mekanizması böyle bir
aktöre karşı Python sandbox iddiasında bulunmaz.

Mevcut `execution_permission=false`, REAL salt-okunur, USC/PnL, spread/risk/lot
ve V2 descriptive-only kod yolları korunur. Yeni emir fonksiyonu/işlem otomasyonu
yoktur. Canlı MT5 bağlantısı, login/logout, hesap seçimi, servis kill/restart,
push, merge veya ana V3 promotion yapılmadı.
