# Görev 13 — mimari ve transaction planı

Başlangıç GitHub PR #4 açık/Draft, HEAD 02152e9f869a14222860ff1b1aae526b4f592d09.
Fetch/ls-remote aynı; task13 dalı yoktu, bu HEAD'den açıldı. Android PR #5 a14c117
(0.7.2/11), Gateway PR #1 19038bd değişmedi. Cloud-runtime becerisiyle yalnız bulut
workspace kullanılır; canlı servis/DB/özel ağ erişimi ve deployment yok.

## Gerçek çağrı zinciri

- API order/cancel/close/pause → ProductDatabase.transaction BEGIN IMMEDIATE →
  ledger/place/close veya API projection update + commands remember → tek commit.
- AnalysisService provider I/O transaction dışında; final transaction içinde risk
  preview, immutable record, opsiyonel AUTO ledger.place ve command response.
- MarketPoller bir historical page'i tek transaction'da ledger.event'e verir;
  scanner on_event aynı transaction'da outbox yazar. Recovery 409 progress commit
  sonrasında atılabilir; bu committed progress rollback edilmemeli.
- ledger.event: manuel queued close önce, ardından ambiguity/stop/target; partial
  TP1, TP2 aynı barda mümkün; zero-volume stop sticky flag ve pause üretir.
- scanner.pause ve TrackingService.start/change/_save ayrı kısa transaction'lar.
  Tracking._save doğrudan SQL kullanır; yalnız Python put/update hook'u yetmez.

## A–F checkpoint'leri

A. Bu sözleşme, explicit activation ve migration sınırları.
B. domain_journal v1: SQLite AFTER trigger + connection-local kayıt fonksiyonu,
   append-only event/body hash + global sequence/previous hash + head anchor.
   Her financial/control mutation aynı connection/transaction'da gözlenir.
C. Command allowlist/preimage/digest, decision evidence, cancel/pause/SL/TP,
   scanner/follow geçişleri. Başarısız business transaction root savepoint'e
   döner; yalnız red kanıtı aynı write lock altında commit edilir. SQLite veya
   beklenmeyen hata bütün transaction'ı geri alır; sahte success event kalmaz.
D. Bağımsız domain_audit (writer/ledger import etmez): hash zinciri, state patch
   continuity, source/journal coverage, request digest, sahiplik ve karar oracle'ı.
   Task12 muhasebe hesabı korunur; kanıtlı yeni cancel/stop için INCOMPLETE azalır.
E. Negatif/migration/atomicity/restart testleri, bounded eski/yeni soak ve dört CI.
F. Kullanım, ölçüm, gerçek sınırlar ve Draft PR; main merge/force push yok.

## Veri sözleşmesi

Domain extension version 1, product/record-store schema v1 korunur. Sequence
SQLite write lock sırasıdır, timestamp değildir. Event body: schema_version,
sequence, event_type, recorded_at_ms, effective_at_ms, portfolio_id, source,
command reference, payload, previous_event_hash; event_id/event_hash canonical
SHA-256 ile bağlanır. Head anchor kuyruk silinmesini de fark ettirir. Bunlar imza
veya saldırgana karşı dış değiştirilemezlik garantisi değildir.

Mutable tablolar için değişen alanlar + before/after full-body hash saklanır;
immutable büyük analiz/mum kaynakları tekrar kopyalanmaz, ID/hash referansı tutulur.
Genesis veya explicit legacy boundary bir coverage olayıdır, geçmiş işlem icadı
olamaz. Request yalnız scope'a göre izinli normalize iş alanlarını içerir; HTTP
header/token/refresh/device/pairing bilgisi ve serbest payload kabul edilmez.

## Uyumluluk kapısı

- Varsayılan legacy mod davranışı korunur. Yeni, açıkça `domain_journal=True` ile
  oluşturulmuş DB full recording destekler. Bu flag worker/auto_paper açmaz.
- Eski DB'de aynı flag otomatik ALTER yapmaz; açık copy-upgrade gerekir.
- Journal'lı DB yeniden açılırken feature marker otomatik tanınır, kayıt sessiz
  kapanamaz. Eksik/yanlış schema/index/guard fail closed. Eski binary'nin yazması
  trigger'ın kayıt fonksiyonu bulunmadığı için başarısız olur.
- Migration yalnız doğrulanmış yeni kopyaya: source mode=ro backup, yeni dosyada
  atomic extension install/boundary snapshot; kaynak değişmez, mevcut hedef asla
  overwrite edilmez. Failure yeni extension DDL ve event'lerini rollback eder.
- Legacy auditor muhasebe scope'unu korur; `require_domain` veya journal DB'de
  domain scope açık doğrulanır. Eski tarihin eksikliği INCOMPLETE kalır.
- Public endpoint/schema/response değişmez. Journal HTTP endpoint'i eklenmez.

## Checkpoint B kanıtı

- Extension v1, head anchor, immutable registry ve connection-local trigger capture
  uygulandı. Metadata marker sayesinde feature sessizce devre dışı kalamaz.
- Beş temel test: yeni zincir, legacy'yi yükseltmeme, iki yönlü atomik rollback,
  copy upgrade/repeat/restore ve eski writer/missing guard fail-closed başarılı.
- İlk kırmızı test import eksikliğini, uygulama testi trigger namespace çakışmasını
  gösterdi. Capture trigger adları ayrı namespace'e alınarak giderildi; mevcut
  finansal motor hatası olarak değerlendirilmez.
- Factory/finansal karar notları ve ASGI testleri sonraki checkpoint'te kaydedilir.

## Checkpoint C kanıtı

- Explicit factory/launcher flag, market/entry/exit/protective decision kanıtları,
  risk snapshot/preimage, account/scanner/follow kontrolleri bağlandı. Kaynak
  body'leri trigger ile izlendiğinden Tracking._save yolu da kapsanır.
- Beş ASGI testi cancel/pause/follow, preimage/reject, concurrent replay/restart,
  domain-write rollback, TP1/manual ve zero-volume sticky stop kanıtı ile lost
  acknowledgement davranışını doğrular. (Test metotları kapsamla birlikte artar.)
- Validation red kaydı yalnız sabit sebep/hesap içerir; raw body/header kaydedilmez.
  Uygulama hatası veya journal IO arızası sahte başarı oluşturmaz.

## Doğrulanmış receipt düzeltmesi ve kayıt sınırı

- Görev 12'de de bulunan ambiguous branch, manuel kısmi exit'in journal'ını
  commit ettiği hâlde market receipt.processed'a order'ı eklemiyordu. Legacy
  ve journal fixture'da aynı test önce başarısız oldu. Yalnız gerçekleşmiş manuel
  çıkış varsa ambiguous order receipt'e eklendi; hesaplama ve response şeması aynı.
  Scanner'ın receipt.processed üzerinden outbox üretimi bu olayları artık görebilir.
- Yeni journal'da unknown analysis red preimage'i ve doğrudan remember allowlist
  bypass'ı iki kırmızı testle gösterildi, düzeltildi. Bunlar yeni kodun kayıt
  açıklarıdır; eski finansal motor hatası diye sunulmaz.

## Checkpoint D kanıtı

- Writer/ledger/API import etmeyen domain_audit; chain/head/registry, delta-fold,
  source/fact/ack coverage, preimage/digest ve hesap ilişkilerini kontrol eder.
- Entry ve exit miktar/fiyatı, hesap başına kalan likidite, TP1/TP2, sticky stop,
  zero-volume trigger, manuel kapanış önceliği ve market-bar değerlendirme kapsamı
  bağımsız Decimal oracle ile denetlenir. Cash ve position değişimleri tek tek
  financial journal fact'iyle eşleştirilir; yalnız net bakiye kontrolü değildir.
- Eski schema raporu ayrı domain INCOMPLETE verir; --require-domain bu eksikliği
  overall'a taşır. Legacy boundary geçmişi tamamlanmış sayılmaz. Yeni kanıtı
  gerçekten doğrulanan cancel/stop kontrolleri eski INCOMPLETE yerine PASS alır.
- Eksik zero-volume değerlendirmesi, baseline account header, missing control
  source, unfinished command ve bool-as-version açıkları kırmızı testlerle
  gösterilip kapatıldı. Partial refill yanlış pozitif oracle'ı düzeltildi.
- 285 V2 offline test (253 mevcut + 32 yeni) Linux'ta ResourceWarning=error ile
  geçti. Bu yerel kanıttır; dört kombinasyon CI ayrıca doğrulanacaktır.

## Checkpoint E ölçüm sözleşmesi

- Eski soak varsayılanı korunur. --domain-journal ile yeni mod, --compare-domain
  ile aynı binary/seed/clock/istek dizisinin iki moddaki eşlenik koşusu çalışır.
  Financial tablo ID/body_hash digest'i aynı değilse karşılaştırma hata verir.
- Event append denemeleri (rollback edilenler dahil), mean/max, başarılı financial
  HTTP çağrısı mean/max (ASGI/lock wait dahil), DB boyutu, toplam/domain audit süresi,
  Python allocation peak ve INCOMPLETE ayrı ölçülür. İstatistiksel üretim benchmark'ı
  iddiası yok; Task12'nin eski ortam ölçümüyle kesin hız oranı çıkarılmaz.
- CI aynı dört OS/Python kombinasyonunda tüm suite'i çalıştırır; yeni bounded
  chain/soak yükü için job timeout 10 dakika, test azaltma veya atlama yok.
