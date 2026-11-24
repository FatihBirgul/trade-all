# Görev 13 — sürümlü domain journal ve bağımsız karar denetimi

31 Ekim 2026. Üretime dağıtılmamış geliştirme teslimatıdır.
Başlangıç: `02152e9f869a14222860ff1b1aae526b4f592d09`, PR #4 açık/Draft.
GitHub PR, fetch ve ls-remote bağımsız doğrulandı; Görev 12 dalında daha yeni commit yoktu.
Dal: `codex/task13-domain-event-journal`; base `codex/task12-ledger-replay-audit`.
[Draft PR #5](https://github.com/FatihBirgul/trade-ai/pull/5).

## A. Yeni geliştirilen özellikler

### Kayıt ve transaction mimarisi

`domain_journal.py`, product schema v1'i koruyan opt-in extension v1'dir.
`product_meta.domain_version` marker; `domain_meta`, `domain_head`, `domain_tables`,
`domain_events` ve account/source sequence indeksleri eklenir. Global INTEGER sequence
SQLite BEGIN IMMEDIATE write lock sırasıdır; aynı timestamp taşıyan işlemler ayrılır.
Event body schema_version, sequence, event_type, recorded/effective zamanları,
portfolio/source/command referansları, payload ve previous_event_hash içerir.
Kanonik sıralı JSON SHA-256 event_hash ve deterministik event_id üretir. Head anchor
kuyruk kaybını da kontrol eder. Hash zinciri imza, dış zaman damgası veya kötü niyetli
DB yöneticisine karşı değiştirilemezlik kanıtı değildir. Dış imza/ayrı anchor geleceğe bırakıldı.

Mutable accounts/orders/positions/scanner_state/watchlist/scanner_jobs/
analysis_tracking/analysis_tracking_state için değişen alanlar ve tam before/after
hash'leri; immutable transactions/events/commands/analyses/notifications için ID/hash
referansları kaydedilir. Büyük immutable kaynaklar tekrar kopyalanmaz.
`coverage.started`, `schema.table_registered`, `state.baseline`, `state.changed`,
`record.created`, komut requested/accepted/rejected/replayed ve gerçek entry/exit/
protective/bar/control kararları kapsanır. Yeni strateji veya otomatik emir davranışı eklenmedi.

SQLite AFTER trigger'ları connection-local capture fonksiyonunu çağırır; doğrudan
Tracking._save SQL'i de aynı transaction'da izlenir. Ledger projection, finansal
journal, receipt, command ve domain event ayrı commit edilmez. Zorunlu event yazımı
başarısızsa hepsi rollback olur. Domain append sonrasındaki projection/commit hatası
da aynı biçimde geri alınır. Başarılı commit sonrası kayıp HTTP yanıtı finansal
idempotency ile korunur; tekrar yalnız replay kanıtı ekler, ikinci fill/cash üretmez.

Business V2Error için transaction başındaki savepoint'e dönülüp yalnız red kanıtı
aynı write lock altında commit edilir; başarısız finansal değişiklik kalmaz.
SQLite/IO veya beklenmeyen teknik hatada tüm transaction rollback edilir, sahte
success/rejection kaydı kalmaz. SQLite arızaları kontrollü enjeksiyondur; fiziksel
power-loss/disk firmware garantisi değildir. Yeni bağlantılar kapanır; ResourceWarning
hata kabul edilerek Windows/Linux dosya yaşam döngüsü test edilir.

### Request preimage ve kontrol kanıtı

Scope allowlist'leri yalnız normalize iş girdilerini saklar: order analysis/quantity,
cancel order, close quantity/key, analyze symbol/market/timeframe/risk account ve ilgili
izinli seçenekler. Hesap scope'u, source ID/hash, eski request digest ve model/policy
bağlamı bağlanır. İstemci girdisi ile runtime risk/market snapshot ayrıdır. Mevcut
finansal command hash/ID ve immutable journal değiştirilmez. Header, bearer/refresh,
pairing/device sırları, raw validation payload veya kişisel bilgi eklenmez. Şema
reddinde yalnız sabit sebep kaydı vardır; yetkisiz istek kaydedilmez.

Cancel, account pause/resume, scanner pause ve follow start/change kontrol kaynakları
kaydedilir. Entry/TP1/TP2/stop/gap/manual öncelik, bar ve likidite kararları motorun
mevcut kapalı-mum kurallarıyla kaydedilir. Zero-volume sticky stop değerlendirmesi,
koruyucu engel ve sonraki devam kanıtı dahildir. Tick execution veya desteklenmeyen
expiry/strateji icat edilmez.

### Eski veriler ve güvenli kullanım

- Varsayılan eski DB legacy modda aynı davranışı korur. Yeni boş DB yalnız açık
  `domain_journal=True` / `--domain-journal` ile genesis kapsamı kazanır.
- Eski DB'yi flag ile açmak otomatik migration yapmaz; açıkça reddeder.
- Journal DB yeniden açılınca marker otomatik tanınır; flag olmaması kaydı kapatmaz.
  Eksik tablo/index/guard ve yanlış sürüm fail closed. Eski binary UDF olmadığı için
  protected yazımı tamamlayamaz. Migration kaynak finansal kayıtları yeniden yazmaz.
- Copy-upgrade yalnız yeni hedef oluşturur. Kaynak mode=ro backup ve audit ile
  doğrulanır; MISMATCH/CORRUPT/ERROR reddedilir. Extension install tek transaction'dır.
  Hata yalnız yeni oluşturulan hedefi kaldırır; kaynak/mevcut hedefe dokunmaz.
- Legacy boundary snapshot gözlenen mevcut durumdur; geçmiş olayı değildir.
  Migration tekrarında yeni hedef kopyalanabilir, geçmiş çoğalmaz. In-place veya
  canlı DB upgrade/deployment bu görevde yapılmadı.

Aşağıdaki komutlar backend klasöründe yalnız seçilmiş test/yedek kopyaları içindir:

```sh
python scripts/audit_v2.py /path/to/existing-copy.sqlite --require-domain
python scripts/migrate_v2_domain.py /path/to/old-copy.sqlite /path/to/NEW-copy.sqlite
python scripts/soak_v2_audit.py --cycles 3 --seed 12 --compare-domain
```

Audit dosya yolunu zorunlu ister, yoksa yeni DB oluşturmaz; mode=ro/query_only ve
snapshot kullanır. Exit: PASS=0, MISMATCH=1, INCOMPLETE=2, CORRUPT=3, ERROR=4.
Runtime launcher `--domain-journal`, app factory `domain_journal=True` ve env
`V2_DOMAIN_JOURNAL=1` destekler. Bunlar scanner/tracking/auto_paper etkinleştirmez.
Launcher'ın mevcut token gereksinimi korunur; örnek token üretilmedi/kaydedilmedi.
Önce sağlam bağımsız yedek, izole copy migration, audit ve uygulama uyumluluğu gerekir.

## B. Bulunan ve düzeltilen hatalar

**Mevcut motor — orta önem:** ambiguous durumundaki pozisyonda queued manuel kısmi
çıkış, nakit/pozisyon/journal'ı commit edip `receipt.processed` listesine order eklemiyordu.
Scanner receipt üzerinden bildirim ürettiği için bu gerçekleşmeyi atlayabiliyordu.
`test_v2_domain_api` legacy ve enabled varyantları önce eksik liste nedeniyle başarısız
oldu. Eski Görev 12 kaynak branch'inde aynı continue yolu doğrulandı. `manual_changed`
yalnız gerçekten çıkış olduğunda ambiguous receipt'e order ekler. İki varyant ve tüm
285 test geçti. Nakit/PnL formülleri ve response alanları aynı; processed içeriğinin
eksikliği düzeltilmiştir. Eski receipt/hash yeniden yazılmadı. Tarihsel bu hatayı taşıyan
DB preflight audit'te reddedilebilir; kullanıcı geçmişini otomatik tamir etmek güvenli
migration kapsamına alınmadı.

**Yeni kodun geliştirme sırasında bulunan sorunları:** capture trigger namespace
çakışması; unknown-analysis red preimage eksikliği; remember allowlist bypass;
partial-refill oracle yanlış pozitifi; baseline header/control source eksik denetimi;
zero-volume stop değerlendirmesinin sonradan stop fill ile yanlış örtülmesi;
yarım command outcome ve bool-as-version kabulü. Önce kırmızı regresyonlarla
kanıtlandı, en küçük kayıt/oracle kontrolleriyle düzeltildi. Bunlar eski finansal
motorun üretim hataları olarak sunulmaz. ASGI framework response-loss ve SQLite
fault trace'leri beklenen test enjeksiyonlarıdır.

## C. Replay denetimindeki ilerleme

`domain_audit.py` writer/ledger/API import etmez. Kendi canonical hash ve Decimal
oracle'ıyla sıralamayı, hash/head'i, state delta zincirini, preimage digest'ini,
account/order/position referanslarını, fact/ack kapsamını ve final projection'ı kontrol eder.
Her cash ve quantity/basis mutation ayrı finansal fact ile eşleşir. Entry/exit fiyat ve
miktarı, account başına kalan hacim, TP1/TP2, sticky stop, gap ve manuel öncelik
bağımsız denetlenir. Decimal local context kullanılır; NaN/Infinity reddi ve mevcut
ROUND_HALF_EVEN/sekiz basamak para kuralları korunur. Fiyat/miktar rastgele 8 haneye
indirgenmez; model dışı currency dönüşümü yoktur.

| Kapsam | Sonuç |
|---|---|
| Legacy DB | Muhasebe profili korunur; domain ayrı INCOMPLETE/not_enabled; require-domain overall'a taşır |
| Copy-upgrade sınırı | Yeni olaylar denetlenir; migration öncesi geçmiş INCOMPLETE |
| Genesis ve tam kanıt | Doğrulanan command/cancel/pause/stop/TP/mutation kontrolleri PASS olabilir |
| Eksik bar/decision/source/outcome veya bilinmeyen sürüm | INCOMPLETE; bilinmeyen kanıt PASS yapılmaz |
| Yanlış projection/ilişki/formül | MISMATCH; bozuk hash/schema/sequence CORRUPT |
| Teknik erişim hatası | ERROR; kaynak değiştirilmez |

Görev 12'nin cancel/stop/preimage/control-history eksikliği yeni kaydı gerçekten
doğrulanan kontroller için azalır. Soak'taki 282 sayısı kontrol toplamıdır, 282 ayrı
finansal hata değildir. Aynı yeni fixture'da 0 INCOMPLETE bütün gerçek dünyaya genellenmez.
Tam strateji seçimi, her risk veto/politika kararı, dış piyasa verisinin gerçekliği,
geçmişte saklanmamış fiyat snapshot'ı ve eski tarih yeniden üretilemez. Chain içindeki
bir kararın kanıtı, veri kaynağının bağımsız doğruluğunu veya imzalanmış komutu kanıtlamaz.

Audit mevcut record/body/total/scratch/finding bütçelerini korur (1M kayıt, 2MiB/body,
128MiB okunan body, 256MiB scratch, 200 finding varsayılanları). Sıralı journal taranır,
fold state geçici disk scratch'tedir. Limitte INCOMPLETE; kaynak onarımı/silmesi yok.

## D. Test ve ölçüm kanıtları

Yerel Python 3.12.14 Linux: **285/285 V2** (253 eski + 32 yeni test metodu),
ResourceWarning=error, 33.243s. Ayrıca quote 2/2 + offline outcome 9/9, Gateway 42/42,
compile/import başarılı. Yanlış `server_v2.py` compile hedefi bir kez “Can't list” verdi;
gerçek dosya `server.py` ile kontrol tekrarlandı ve geçti. Bu ilk komut tam compile
kanıtı olarak kabul edilmedi. V1 uzak/gerçek servis testleri çalıştırılmadı.

Yeni testler: journal 8, API 9, bağımsız audit 14, bounded soak 1. Parametrik alt
vakalar ayrıca vardır. Eksik event/seq/hash/tail, unique ID, yanlış account/header,
yeniden hash'lenmiş preimage, eksik fact/ack/evaluation/control source, unfinished
command, illegal projection/quantity/stop/pause, future sürüm/tür, invalid Decimal,
legacy/migration/repeat/rollback, old writer/missing guard, lost response/concurrency/
restart/backup restore ve uzun chain kapsanır. Immutable bozma yalnız ayrı fixture
kopyasında yapılır; bazı testler gerçek sebebi kanıtlamak için guard'ları geri kurar.
Valid partial refill/cancel ve gecikmiş stop yanlış pozitif vermemelidir.

[Ham eşlenik ölçüm](TASK13_SOAK_METRICS.json): seed12/cycles3, aynı binary/senaryo,
935 mum, 50 finansal journal, 10 order/position, 63 audit, 225 aynı tekrar yanıtı,
10 kayıp ACK recovery, 4 restart, 3 kontrollü SQLite arızası, 2 UTC günü.

| Ölçüm | Legacy | Journal |
|---|---:|---:|
| Domain event | 0 | 5.750 |
| Son audit kayıt sayısı | 1.060 | 6.810 |
| Finansal mismatch / beklenmeyen hata | 0 / 0 | 0 / 0 |
| INCOMPLETE toplamı | 282 | 0 |
| DB byte | 2.977.792 | 9.269.248 |
| Audit toplam saniye | 12,003 | 40,809 |
| Domain audit toplam saniye | 0,005 | 28,249 |
| Senaryo saniye | 21,788 | 57,296 |
| Python allocation peak byte | 12.185.552 | 21.187.028 |
| Finansal HTTP ortalama / max ms | 6,800 / 18,490 | 13,663 / 52,461 |

Journal append 5.798 deneme (rollback dahil), ortalama 0,222ms/max2,785ms.
Finansal tablo ID/body_hash digest'leri birebir aynı; karşılaştırma bunu assert eder.
Bu tek eşlenik gözlemdir: tracemalloc RSS değildir, append fsync/transaction latency
ölçümü değildir, HTTP ASGI/lock beklemesini içerir. Üretim veya istatistiksel performans
iddiası yok. Maliyet ve disk büyümesi belirgindir; future checkpoint/archive tasarımı gerekir.

f3ba82e matrix CI: Windows/Ubuntu × Python 3.11/3.12 dört job success.
PR quote CI: Python 3.11/3.12 iki job success. Job/log sonuçları doğrulandı.

| Matrix ortamı | V2 sonucu / süre | Quote+outcome |
|---|---|---|
| Ubuntu Python3.11.17 | 285 /49,738s | 11 geçti |
| Ubuntu Python3.12.15 | 285 /34,938s | 11 geçti |
| Windows Python3.11.9 | 285 /175,576s | 11 geçti |
| Windows Python3.12.10 | 285 /167,410s | 11 geçti |

Bu checkpoint'te başarısız veya atlanan test yok; Windows launcher parse geçti.
Ubuntu'da Windows'a özgü launcher adımı koşul gereği çalışmaz. PR quote işlerinin
her biri ayrıca285 V2+2quote geçti. AnyIO/Starlette BlockingPortal deprecation ve
actions Node punycode deprecation uyarıları loglarda duruyor; bastırılmadı.

Hiçbir test yeşil görünmek için azaltılmadı/gevşetilmedi; yalnız ek yük için timeout
5'ten10 dakikaya çıkarıldı. Beklenen fault trace'leri uyarı olarak gizlenmedi.

## E. GitHub teslimatı ve uyumluluk

- `17c5209`: mimari/compatibility planı.
- `88026e0`: temel journal, copy migration ve atomicity testleri.
- `92161c9`: lifecycle/control/decision evidence entegrasyonu.
- `1facd05`: gerçek ambiguous receipt düzeltmesi ve red kanıtı.
- `8484a00`: bağımsız karar audit ve negatif regresyonlar.
- `f3ba82e`: eşlenik soak/CI checkpoint'i.
- Son dokümantasyon commit'i PR geçmişindedir; SHA kendi dosyasına yazılmaz.

[Matrix CI](https://github.com/FatihBirgul/trade-ai/actions/runs/41198231996),
[PR quote CI](https://github.com/FatihBirgul/trade-ai/actions/runs/41198412896).
Final HEAD run'ları PR checks'tedir; somut sonuçlar progress log'a eklenir.

Değişen dosyalar: yeni domain_journal/domain_audit; ProductDatabase/API/ledger/
analysis/scanner/tracking bağlantıları; paper_audit, audit/backup/migration/soak
scriptleri; launcher flag; domain fixture ve dört test modülü; CI workflow ve belgeler.
OpenAPI export başlangıç 02152e9 ile semantik eşit: **26 path/34 schema**; dosya özgün
byte'larına döndürüldü. Endpoint, alan/tür, USDT, WAIT, yetki ve session sözleşmeleri
korundu. Eksik receipt içeriği düzeltmesi B bölümünde açıklandı.

Android yalnız referans: PR #5 `a14c11775288051b54c8a8fcb78749167a9b0304`,0.7.2/11.
Gateway PR #1 `19038bdecd5ef472ff7826bb074208d300d682f8`; backend reference ile 42
entegrasyon testi başarılı. İki depo kaynağı değiştirilmedi. Main'e merge/force push,
canlı DB migration, özel ağ/PC/telefon erişimi, deployment veya otomatik sanal emir
etkinleştirme yapılmadı. Yazma testleri geçici fixture DB'lerde çalıştı.

## F. Eksikler ve sonraki geliştirme

1. Sürüm kontrollü tüm risk/strateji girdilerini bağımsız oracle'a taşı; eksik alanları
   INCOMPLETE tut. Persist edilmeyen geçmişi veya dış market doğruluğunu uydurma.
2. Domain head için dış güvenilir anchor/imza ve archive read/restore doğrulaması.
   Hash tek başına saldırgana karşı güvence değildir; gizli anahtar kurulmadı.
3. Immutable journal/command/analysis/source geçmişini koruyan segment/checkpoint ve
   arşiv tasarımı. Sürekli büyüyen domain/transactions/events/analyses/notifications
   tabloları için kapasite bütçeleri; otomatik silme/retention etkin değil.
4. Özellikle eski receipt hatası bulunan DB'ler için ayrı, kullanıcı tarafından gözden
   geçirilmiş migration/uyumluluk prosedürü. Üretim eski veri kopyası burada yok;
   gerçek veri uyumluluğu tam doğrulandı denemez. İndeks source-order journal hâlâ scan,
   account journal ORDER BY geçici B-tree kullanır (ham ölçüm query_plans).
5. Gerçek Windows servis, Android telefon ve özel Gateway uçtan uca testi yapılmadı.
   CI Windows fixture/SQLite handle testi gerçek kullanıcının cihaz testi değildir.
   Bu görevde production activation, canlı arıza testi veya backup retention yok.
