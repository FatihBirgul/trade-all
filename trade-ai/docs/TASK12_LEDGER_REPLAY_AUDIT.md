# Görev 12 — bağımsız finansal replay ve dayanıklılık raporu

## A. Sistem ve kullanım

Başlangıç `f690a1301aa2f75da36d0d37a84da6f25ac93d25`; GitHub PR #3 açık/Draft,
fetch/ls-remote ile aynı HEAD, daha yeni commit yok. Yeni dal
`codex/task12-ledger-replay-audit`; main taban alınmadı. Android PR #5 a14c117
(0.7.2/versionCode 11) ve Gateway PR #1 19038bd yalnız uyumluluk referansı.

Plan ve kaynak haritası: [TASK12_LEDGER_AUDIT_PLAN.md](TASK12_LEDGER_AUDIT_PLAN.md).

`backend/market_ai/v2/paper_audit.py` journal muhasebesini yeniden kurar.
Ledger/risk/API/provider/ProductDatabase fonksiyonlarını import etmez veya çağırmaz.
İlk emir command response'u miktar/parametre/level kaynağıdır; transactions
miktar ve sıra kaynağıdır; events execution fiyatı/mark kaynağıdır. analyses ve
emirlerin referans verdiği product/source decision record'larının hash ve
instrument/level/step bağları kontrol edilir. Mutable cash/quantity/basis/PnL
replay girdisi olarak kullanılmaz; hesaplanan sonuçlarla karşılaştırılır.

### Bağımsız denklikler

- Model v1 genesis: her hesapta 10000 sanal USDT. Cash = genesis + yeniden
  hesaplanan debit/credit; journal cash delta'sı ayrıca bu sonuçla karşılaştırılır.
- Entry notional ve fee; exit proceeds ve fee, parça başına tahsis edilen basis,
  kalan basis, açık miktar, realized PnL. Son çıkış kalan basis'i tamamen tüketir.
- Original order amount = entry toplamı + pending remainder + çıkarılan iptal
  miktarı. Terminal order remainder sıfır; filled amount tamamen gerçekleşmiş.
- Open quantity = entry toplamı − exit toplamı; overclose/negative quantity,
  closed status/basis, average entry, protective level ve timestamp denklikleri.
- Snapshot execution modelinin adverse price ve fee kuralları; quantity_step
  instrument kaynağından, reservation/risk-per-unit quote alanları ayrı doğrulanır.
- Hesap başına bar volume participation; journal/order/position/event/command
  sahipliği; transaction ID'nin event+order+kind bağı; orphan/duplicate ilişkiler.
- Pending close source/quantity/consumed/reserved ve request time uyumu;
  cancel acknowledgement varken order'ın yeniden aktif görünmemesi.
- Açık risk boyunca market history continuity; kayıtlı son uygun mark ile
  unrealized = quantity × mark − remaining basis, equity = cash + marked value
  ve seed + realized + unrealized denklikleri. Yeni fiyat üretilmez.

Muhasebe aynı matematiksel sözleşmeyi uygular; başka bir kopya ledger event()
çalıştırılmaz. El hesabı oracle testi: 10 @129.92598 ve .64962990 giriş ücreti;
2 @130.4739 çıkışında .13047390 ücret. Beklenen kalan basis 1039.92754392,
realized .83544012, cash 8960.90789620, unrealized 4.87245608,
equity 10005.70789620 gerçek fixture API çıktılarıyla ayrıca karşılaştırılır.

### Sonuç sınıfları ve CLI

Backend dizininden, açıkça seçilmiş mevcut bir dosya için:

```text
python scripts/audit_v2.py /absolute/path/to/verified-copy.sqlite
python scripts/audit_v2.py C:\verified-backups\v2-copy.sqlite
python scripts/audit_v2.py /path/to/copy.sqlite --max-records 100000 --max-findings 100
```

| JSON status | Exit | Anlam |
| --- | --- | --- |
| PASS | 0 | Beyan edilen muhasebe/evidence kontrolleri doğrulandı. Tüm execution kararlarının kanıtı değildir. |
| MISMATCH | 1 | Mevcut kaynaklarla doğrulanmış finansal/ilişkisel fark. |
| INCOMPLETE | 2 | Eksik kaynak, desteklenmeyen model, bütçe sınırı veya yeniden oynatılmayan kontrol zaman çizelgesi. |
| CORRUPT | 3 | Bozuk hash/JSON/Decimal/koruma/schema yapısı. |
| ERROR | 4 | Teknik dosya/SQLite/IO nedeniyle tamamlanamayan audit. |

Argüman eksikliği argparse kullanım hatasıdır (exit 2, JSON audit sonucu yok).
Rapor `checks` sayıları, tablo başına kayıt sayısı, sabit bulgu kodu/table/row
ordinal ve kapsam sınırlamalarını içerir. Kayıt gövdesi, anahtar, bearer, dosya yolu
ve finansal tutar yazılmaz. Zaman ölçümü audit raporuna katılmaz; aynı snapshot
aynı sonucu verir. En ağır bulgu overall sonucunu belirler; yalnızca ilk 200
bulgu gösterilse de diğer bulguların sayısı ve overall şiddeti korunur.

### Salt okunur ve kaynak sınırları

- Var olan regular file: strict path, URI mode=ro, query_only=ON,
  trusted_schema=OFF, BEGIN altında tek committed snapshot. Yeni DB/parent
  oluşturulmaz; RW fallback/migration/repair/worker/ağ çağrısı yok.
- immutable=1 kullanılmaz; committed WAL değişikliklerini görmezden gelmek yanlış
  PASS üretebilir. WAL snapshot ve eşzamanlı writer testi vardır. SQLite normal
  read lock/sidecar mekanizmasını kullanabilir; finansal satırlar değiştirilmez.
- Scratch yalnız kendi TemporaryDirectory'sinde, ayrı bağlantıda; source
  şemasına indeks yazılmaz. Tablolar akışla okunur; lookup/sıralama disk indeksleri.
  Cache yaklaşık 2 MiB/connection; temp_store=FILE.
- Varsayılan bütçeler: 1 milyon kayıt, tek body 2 MiB, toplam body 128 MiB,
  order başına 10000 bağlı kayıt, 200 gösterilen bulgu, scratch 65536 sayfa
  (varsayılan 4 KiB sayfayla 256 MiB). Body boyutu Python'a almadan önce SQL'de
  kontrol edilir. Referans decision record'ları disk cache ile bir kez doğrulanır.
- Exception/interrupt sonrası source/scratch connection ve geçici dosyalar kapanır.
  Düzeltme/DELETE/UPDATE/otomatik onarım yolu yok. Bu araçla canlı DB çalıştırılmadı.

### Açık INCOMPLETE ve kapsam sınırları

Geçerli pending/full/partial/TP/manual/ambiguity muhasebesi PASS olabilir.
İptal/remainder expiry için miktar doğrulanır, ancak tam cancel zamanı/pause
zaman çizelgesi saklanmadığından `cancellation_timeline_not_persisted` INCOMPLETE.
Stop için adverse price adayları ve muhasebe kontrol edilir; sıfır volume stop
trigger'ını da içeren tüm protective state machine yeniden oynatılmadığından
`stop_trigger_sequence_not_replayed` INCOMPLETE. Bunlar bozuk veri diye sunulmaz.

Eksik ack/analysis/event/decision source ve aktif risk history gap'i PASS olamaz.
Eksik order ack durumunda eksik replay toplamı cash ile kıyaslanıp sahte mismatch
üretilmez. Desteklenmeyen execution model için hesap uydurulmaz.

Bu v1 araç her yapılması gereken ama hiç kaydedilmemiş fill'i, bütün kayıtların
birlikte silinmesini/yeniden yazılmasını veya geçmiş risk/pause kararlarının
uygunluğunu kanıtlayamaz. SHA-256 checksum imza değildir. Request digest'lerinin
orijinal argüman gösterimleri bütünüyle saklanmadığından preimage'ler tekrar
hesaplanmaz; format/scope/key/ack ilişkileri denetlenir. Outbox ve referanssız
analysis decision record'ları finansal audit kapsamının dışındadır. Güncel saate
bağlı risk/daily-loss API projeksiyonu için as-of-aware karşılaştırma eklenmemiştir.

## B. Hata kanıtları

Mevcut Görev 11 ledger'ında yeni doğrulanmış üretim hatası bulunmadı; hesaplama
motoruna/API'ye düzeltme veya büyük refactor uygulanmadı. Kasıtlı bozukluklar
ayrı fixture kopyalarında, hash yeniden hesaplanarak veya bilerek bozularak üretildi.
Kopyalarda immutable guard geçici kaldırıldıysa test mutasyonundan sonra aynen
kuruldu; gerçek kaynaklara veya canlı history'ye dokunulmadı.

Yeni auditor geliştirilirken şu gerçek test başarısızlıkları giderildi:

| Önem | Kırmızı test / kök neden | Düzeltme |
| --- | --- | --- |
| Orta | Missing ack sonrası partial replay cash karşılaştırması MISMATCH veriyordu; kaynak yetersiz. | Account replay completeness kapısı; INCOMPLETE, sahte cash farkı yok. |
| Yüksek | Journal'da işlem olmayan ara mum silindiğinde yalnız journal/son mark kontrolü PASS veriyordu. | Açık exposure boyunca ardışık kalıcı mum kontrolü; INCOMPLETE. |
| Yüksek | Cancel ack mevcutken projeksiyon pending/remaining=original yapılınca PASS veriyordu. | Immutable cancel acknowledgement ile current order state bağı; MISMATCH. |
| Orta | Step hem ack hem order'da aynı yanlış değere çevrilince PASS veriyordu. | Bağımsız instrument rules karşılaştırması; MISMATCH. |

Son ilişki incelemesinde ek iki kırmızı regression testiyle şu açık da kapatıldı:
farklı primary key altında aynı order'a bağlı sahte position ve positions kaydı
olmayan/yanlış account scope'unda financial command, kontrol döngüsünün dışında
kalıp PASS alabiliyordu (yüksek önem). Global position/order ID eşitliği, close
command position varlığı ve financial command account scope bağı eklendi;
bozuk kopyalar artık MISMATCH alır. Mevcut ledger/API yine değiştirilmedi.

Bu hata testleri önce başarısız çalıştırıldı, sonra en küçük denetleyici düzeltmesiyle
geçti. İlk iki test de modül yokken import hatasıyla kırmızıydı. Başlangıç modül
eksikliği mevcut finansal motor hatası olarak raporlanmaz.

## C. Test ve dayanıklılık kanıtı

Yerel Linux/Python 3.12:

- 253/253 V2 offline unittest (227 eski + 24 audit + 2 bounded soak),
  `-W error::ResourceWarning`; runner socket/DNS ve geçici kök dışı SQLite'ı engeller.
- Quote 2/2 + seçili V1 outcome 9/9; compileall başarılı.
- Gateway 19038bd: 42/42; sekiz gerçek V2/geçici DB entegrasyonu dahil.
- OpenAPI yeniden üretildi: f690a13 ile JSON nesneleri birebir eşit;
  26 path/34 schema. Örneklerde fark yok; salt sıralama farkı geri alındı.
- Audit testlerinde eksik cash delta/journal, yanlış fee/price/PnL/basis/quantity,
  duplicate fill, wrong account, active reservation/cancel, missing event/ack,
  event sıra değişimi, NaN/sNaN/Infinity/invalid exponent, hash/decision record/
  immutable guard bozulması ve IO arızası beklenen sınıfta yakalandı.
- CLI beş sınıf/exit code, eksik dosya oluşturmama, source byte eşitliği, doğrudan
  write reddi, source rename/cleanup, WAL commit/snapshot ve Decimal context
  bağımsızlığı başarılı. Geçerli kısmi fill/close, delayed close ve ambiguity
  yanlış bozulma olarak raporlanmadı.

Tekrarlama (backend dizini):

```text
python -W error::ResourceWarning tests/run_v2_offline_tests.py
python -m pytest -c tests/pytest-v2.ini tests/test_v2_mobile_quotes.py tests/test_outcomes.py::TestOutcomeEngineUnit -q
python -m compileall -q market_ai server.py start_v2.py scripts
python scripts/soak_v2_audit.py --cycles 3 --seed 12
```

Soak yalnız yeni geçici dosya kullanır; mevcut DB yolu kabul etmez. `cycles` 1–8,
her çevrim 60 idle mum ve sınırlı lifecycle; tek 720 dakikalık recovery üç bounded
scanner tick'te tamamlanır. Her lifecycle/recovery aşaması, her 20 idle bar,
rollback/restart ve backup/restore sonunda bağımsız audit çalışır.

[Ham ölçüm](TASK12_SOAK_METRICS.json): 935 mum, 50 journal, 10 order/position,
722 pending notification; son audit'te 1060 kayıt, 63 audit, 225 eşit tekrar yanıtı,
10 response hook timeout sonrası idempotent recovery, dört restart, üç kontrollü
ikinci-journal SQLite hatası, iki UTC gün. Finansal mismatch **0**, beklenmeyen
hata **0**. `incomplete_checks=282` audit aşamaları boyunca tekrar sayılan bilinen
cancel/stop sınırlarıdır; 282 ayrı bozukluk anlamına gelmez.

Tek ölçümde toplam audit süresi 15.374417 saniye; DB 2977792 byte (~2.84 MiB),
tracemalloc Python peak 12042576 byte (~11.5 MiB). Tracemalloc etkin, toplam
scenario süresi/RSS ölçülmedi; üretim performans garantisi değildir. Sabit seed
finansal sonuç ve sayıları tekrar üretir; süre/bellek ölçümü ortamla değişir.
Beklenen üç enjekte hata loglanabilir; bunlar başarısız test değildir. Normal
final suite'te başarısız veya atlanan test yok. CI uyarıları ayrıca kaydedilir.

## D. GitHub ve değişen alanlar

- `cbb6c25`: bağımsız source/scratch replay, CLI, ilk bozukluk/read-only testleri.
- `4bddb47`: bounded soak, lost-ack/concurrency/restart/scanner/backup testleri,
  resource budget'ları, hand oracle ve ek auditor regresyonları.
- `056015d`: Ubuntu/Windows × Python 3.11/3.12 matrisi; her OS/Python'da offline
  suite, quote/outcome, compile ve Windows launcher parse.
- Yeni source: paper_audit; script: audit_v2/soak_v2_audit; test: paper_audit/paper_soak.
  Finansal API, ledger/risk/ProductDatabase, Android/Gateway kaynakları değişmedi.

[Draft PR #4](https://github.com/FatihBirgul/trade-ai/pull/4), base Görev 11 dalı;
main merge yok. Kod/CI checkpoint `056015dcddf20dec1a7d9410e31314d67027216d`:

- [Matrix CI 41188644740](https://github.com/FatihBirgul/trade-ai/actions/runs/41188644740):
  Windows/Ubuntu × Python 3.11/3.12 dört iş success; her işte 251 V2 + 11
  quote/outcome, compile; Windows launcher parse başarılı.
- [Quote CI 41188786105](https://github.com/FatihBirgul/trade-ai/actions/runs/41188786105):
  Python 3.11/3.12 iki iş success; her işte 251 V2 + 2 quote.
- GitHub run/job metadata ve log test sayıları ayrı doğrulandı. Atlanan test yok;
  Ubuntu'da Windows-only launcher adımının skip edilmesi beklenen workflow dalıdır.
- Starlette TestClient/AnyIO BlockingPortal alias deprecation uyarısı mevcut
  dependency kaynaklıdır; bastırılmadı. Actions checkout/setup-python eski Node 20
  hedefi nedeniyle Node 24'e zorlanma ve Ubuntu image geçişi annotation'ları var.
  Bunlar test hatası değildir; dependency/action bakım işi olarak açık kalır.

`b254606` ilk belge checkpoint'idir. Son ilişki düzeltmesiyle yerel suite 253'e
çıktı (24 audit + 2 soak); final HEAD CI sonucu Draft PR'da ayrıca kaydedilir.
Yukarıdaki 056015d run'ları önceki 251 testli checkpoint'in kanıtıdır. Commit bağlantıları:
[cbb6c25](https://github.com/FatihBirgul/trade-ai/commit/cbb6c25),
[4bddb47](https://github.com/FatihBirgul/trade-ai/commit/4bddb47),
[056015d](https://github.com/FatihBirgul/trade-ai/commit/056015d).

## E. Sınırlamalar ve sonraki sıra

[Retention ve arşiv tasarımı](TASK12_RETENTION_DESIGN.md) tablo bağımlılıkları,
EXPLAIN sonuçları ve güvenli manifest/restore/lookup sırasını açıklar. Otomatik
silme/TTL/VACUUM veya canlı index migration yok.

Gerçek Windows PC/telefon/özel ağ, çalışan servis restart'ı veya gerçek piyasa
execution testi yapılmadı. Android oturum/yetki/API/USDT kararları değişmedi.
Forex/XAU/FX conversion/inverse contracts veya tick/order-book replay desteklenmez.

Sonraki öncelik: sürümlü append-only control/domain event journal'ı ile cancel,
pause, protective trigger ve request preimage eksiklerini gidermek; ardından
full execution replay kapsamını genişletmek. Source event/order indekslerini
ayrı, büyük izole veri ölçümüyle değerlendirmek ve archive read/restore zincirini
kurmak. Veri silme ancak bu kanıt zinciri ve ayrı onaydan sonra gündeme gelebilir.
