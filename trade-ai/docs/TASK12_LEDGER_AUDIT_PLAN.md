# Görev 12 teknik planı

Başlangıç: GitHub PR #3 açık/Draft, HEAD f690a1301aa2f75da36d0d37a84da6f25ac93d25;
31 Ekim 2026 fetch/ls-remote ile eşit. Yeni dal daha önce mevcut değildi.
Android PR #5 a14c117 (0.7.2/11), Gateway PR #1 19038bd yalnız referanstır.
Bulut çalışma alanı dışında servis/DB/ağ erişimi yapılmayacak.

## Kaynak haritası

- accounts: mutable cash/seed/pause, checksum; başlangıç model v1'de 10000 USDT.
- commands: immutable order/cancel/close response + scope/key/request digest.
  Order response ilk miktar, execution parametreleri ve levels'i korur. Close
  response miktar/zamanı korur. Cancel zamanı ve pause geçmişi saklanmaz.
- transactions: immutable gerçekleşmiş entry/exit miktarı, fiyat, fee, cash delta,
  PnL; order/position/event ilişkileri. Muhasebe replay'inin ana girdisi.
- events: immutable kapalı 1m mum ve receipt; fill miktarı receipt içinde yoktur.
- orders/positions: mutable projeksiyonlar; replay sonucuyla karşılaştırılacak.
- analyses/decision_records: değişmez analiz/snapshot; emir kaynağı ve instrument
  kimliğini bağlar. Scanner/notifications finansal hareketin kaynağı değildir.

## Uygulama checkpoint'leri

1. Başarılı ve bozulan fixture kayıtları için testleri önce yaz. Doğrudan ledger
   import etmeyen `paper_audit.py`: Decimal muhasebe replay, schema/hash/identity/
   referans kontrolleri; bağımsız formüller ve maliyet/miktar korunum denklikleri.
2. CLI açık existing path ister. mode=ro, query_only, tek read transaction;
   yeni kaynak DB, migration/repair/API/worker yok. SQLite scratch dosyasındaki
   indeksler ve akışlı taramalarla kaynak boyutuna göre RAM artışını önle.
   Finding/record/body sınırları; deterministik ve kayıt içeriği içermeyen rapor.
3. Ayrı geçici bozuk kopyalarda fee/cash/quantity/basis/PnL/duplicate/missing/
   cross-account/event-order/hash/Decimal/erişim arızası testleri. Salt okunur ve
   snapshot/determinism/context testleri. Eksik kanıt INCOMPLETE olmalı.
4. Sabit seed ve sınırlı olay sayılı soak: partial/TP/stop/cancel/close, duplicate,
   concurrency, lost ack/retry, restart, transaction failure, UTC gün sınırı,
   scanner ve backup/restore. Her aşamada bağımsız audit ve ölçüm.
5. Retention/source bağımlılıkları ve EXPLAIN QUERY PLAN incelemesi; silme yok.
6. Tüm V2 offline/quote/outcome/Gateway testleri, API JSON eşitliği, Ubuntu/Windows
   Python 3.11/3.12 CI; küçük commitler, yeni Draft PR, kanıt raporu.

## Denetimin sınırı

Bu araç journal'dan muhasebe replay'i yapar; ledger event() fonksiyonunu yeniden
çağırmaz. Eksik pause/cancel zaman çizelgesi nedeniyle bütün emir kararlarını,
hiç üretilmemiş fill'leri veya tüm kayıtların birlikte yeniden yazılmasını
kanıtlayamaz. İptalin miktarı ilk emir − entry toplamı − kalan ile çıkarılabilir;
iptal zamanı veya o anda ne yapılmalıydı sorusu ayrı INCOMPLETE kontroldür.
Hash'ler imza değildir. Eksik market snapshot'tan fiyat üretilmez. Kontroller
PASS/MISMATCH/INCOMPLETE/CORRUPT/ERROR ayırır; en ağır bulgu overall sonucunu
belirler. Desteklenmeyen execution model/version PASS alamaz.

## İlk uygulama checkpoint'i

- `paper_audit.py` ve explicit-path `scripts/audit_v2.py` eklendi; ledger/risk/API
  importu yok. Kaynak mode=ro/query_only + tek snapshot; 2 MiB body, 1 milyon
  satır, 200 bulgu ve emir başına 10000 bağlı kayıt sınırı; disk scratch indeksleri.
- 17 yeni audit testi; geçerli pending/partial/close/TP/ambiguity kayıtları,
  bozuk kopyalar, eksik kaynaklar, WAL snapshot, CLI, hata ve kaynak kapanışı.
- Geliştirme sırasında testle yakalanan audit açıkları: missing ack sonrası kısmi
  toplamı nakitle kıyaslama, ara mum silinmesinde yanlış PASS, cancel ack sonrası
  tekrar aktif projeksiyonu fark etmeme. Önce kırmızı testlerle gösterilip kapatıldı.
  Bunlar yeni denetleyicinin geliştirme hatalarıdır; mevcut ledger hatası iddiası yok.
- Yerel mevcut + yeni V2 suite 244 test; quote/outcome ayrıca doğrulanır.

## Dayanıklılık checkpoint'i

- Test kapsamı 22 audit + iki soak testi oldu. Ek el hesabı oracle'ı, entry fee,
  partial close basis/PnL/nakit/unrealized/equity için literal beklenen değerleri
  kontrol eder. Yanlış step hem order hem ack'te aynı olsa da instrument'tan yakalanır.
- `scripts/soak_v2_audit.py`: seed=12, üç bounded cycle, 935 final mum/50 journal,
  63 audit, iki UTC gün, 720 dakikalık scanner recovery, lost response hook,
  concurrency/rollback/restart ve verified backup/restore. Gerçek servis yok.
- Scratch disk sayfa sınırı 256 MiB, toplam body sınırı 128 MiB; source decision
  record'ları disk cache ile yalnız bir kez doğrulanır. CLI tüm beş exit code'u
  test eder. Maksimum kaynak sınırında INCOMPLETE; disk/IO hatasında ERROR.


## Son kaynak ilişki incelemesi

İki ilave negatif test position primary key ile order kimliğinin ve financial
command position/account scope'unun küresel kontrolünü gerektirdi. Önce yanlış
PASS kanıtlandı; ek ilişki gate'leriyle MISMATCH doğrulandı. Final 24 audit + 2
soak ile 253 V2 testi geçti. Ledger/API değişmedi.
