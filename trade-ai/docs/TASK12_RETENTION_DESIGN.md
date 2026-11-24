# Görev 12 — silme yapmadan retention ve arşiv tasarımı

Bu belgede politika önerilir; çalışan DB'ye index/migration/cleanup uygulanmaz.
Mevcut immutable trigger'lar kaldırılmaz. Yaşına göre finansal kayıt silmek yasaktır.

## Büyüyen veri ve bağımlılıklar

| Tablo | Büyüme / yeniden üretilebilirlik | Saklama gereği |
| --- | --- | --- |
| transactions | Her entry/exit; accounting replay'in temel kaynağı | Süresiz erişilebilir; quantity/price/fee/cash/PnL, order/position/event ilişkileri korunmalı. |
| events | Her kapalı 1m mum/symbol; OHLCV + receipt | Açık risk boyunca kesintisiz tarihçe; journal fiyatını/mark'ı doğrulayan barlar zorunlu. Receipt içinde fill miktarı yok; sadece receipt ile journal yeniden kurulamaz. |
| commands | Her farklı analyze/order/cancel/close anahtarı | Aynı anahtar orijinal response'u döndürür. Sadece anahtarı tutmak bu sözleşmeye yetmez; response ve request digest gerekli. Aktif emir/close kaynakları asla atılmaz. |
| orders / positions / accounts | Her emir için kalıcı projeksiyon; accounts iki satır | Finansal miktarlar journal'dan türetilebilir. Pause/cancel zaman çizelgesi ve protective/ambiguity durumlarının tamamı güncel şemada yeniden üretilemez. Projeksiyonlar da korunmalı. |
| analyses | Her benzersiz immutable analiz | Order/command/history/chart istemcilerinin kaynakları. Yalnız API response'unu saklamak candle provenance yerine geçmez. |
| decision_records | Product record + TF başına candle/config/engine snapshot | İlgili analiz/order varsa bütün transitive source_records zinciriyle korunmalı. Kayıt aynı ID için deterministik; aynı fiyatlar farklı as-of/config'te ayrı kayıt olabilir. |
| scanner_jobs | Watch/closed boundary/provider başına job | Running/pending işler, dedup/recovery anahtarları korunmalı. Eski terminal gövdeler teorik arşiv adayı; key ve immutable analysis referansları korunmalı. |
| notifications | Pending outbox; event details mum receipt'ini tekrar içerebilir | Delivery henüz yok. Gönderilmemişi silmek veri kaybıdır. Dedup key, event/analysis kaynağı ve delivery durumu kalmalı. |
| watchlist / scanner_state | Watch sınırı 10; state tek satır | Güncel kontrol durumu; history replay kaynağı değildir. |
| analysis_tracking / analysis_tracking_state | Follow sayısı sınırlı; analiz/command/outbox dolaylı büyür | Aktif/pending follow state ve dedup referansları korunmalı. |

En büyük uzun vadeli risk, her analizde TF başına candle snapshot'ı ve product
response tekrarları; sürekli 1m event/outbox ve sınırsız command geçmişidir.
Bu görevdeki 935 olay/50 journal ölçümü gerçek uzun dönem trafik tahmini değildir.
Kaynak verisi veya borsa tarihçesini sonradan tekrar indirmek, orijinal snapshot ve
aynı sağlayıcı sürümünün elde edileceğine dair garanti vermez.

## Sorgu ve indeks değerlendirmesi

Mevcut indeksler: analysis_time(created_ms DESC,id), order_account(portfolio,id),
position_account(portfolio,id), transaction_account(portfolio,id), AUTO signal
unique partial index, scanner job status expression index; id/scope+key PK'leri.

Fixture DB üzerinde `EXPLAIN QUERY PLAN` ölçümü soak çıktısında bulunur:

- Analiz history analysis_time covering index kullanır.
- Account journal transaction_account kullanır; rowid sıralaması için SQLite
  geçici B-tree kullanabilir (mevcut index id ile bitiyor).
- `MAX(close_ms) WHERE symbol=?` events üzerinde scan/search yapar; symbol/close
  composite index yok. Büyük event geçmişinde poll/event path'i maliyeti büyür.
- Transaction order_id yalnız JSON body'dedir; json_extract ile order başına
  replay kaynakta tam tarama gerektirir. Audit bu yüzden kaynak şemasını
  değiştirmeden disk scratch'ta (t,owner,n)/(t,event,account)/(t,symbol,ms) indeksler.

Gelecek ayrı migration adayı: events(symbol,close_ms), transaction order ilişki
indeksi/typed kolon ve portfolio+rowid paging tasarımı. Önce çok daha büyük izole
veride boyut/yazma maliyeti ve gerçek sorgu planı ölçülmeli; varsayımsal hızlanma
iddiası yapılmamalı. JSON body içi hidden referanslar archive GC için güvenli FK
olarak kabul edilmemeli.

## Önerilen güvenli arşiv mimarisi

1. Önce eksik kontrol geçmişini tamamlayan sürümlü append-only domain journal
   tasarla: order/cancel/pause/close/stop-trigger karar zamanı, instrument ve model
   parametreleri, önce/sonra seq bağlantıları. Mevcut kayıtları uydurma olaylarla
   doldurma. İleride yazım projection/journal/command ile aynı transaction olmalı.
2. Ayrı dosyaya SQLite online backup snapshot'ı; manifest içinde schema/mode,
   model sürümleri, row count/sequence/time aralıkları, içerik hash'leri ve önceki
   manifest hash'i. Seed/genesis ve source_record closure dahil. Hash imza değildir;
   saldırgan kaynak değişimine karşı dış imza/append-only storage ayrıca gerekir.
3. Arşiv okuma ve birleşik history/idempotency/audit lookup API'si önce geliştir.
   Kullanıcı geçmişi ve aynı-key response davranışı değişmeden sıcak+arşiv okunmalı.
   Archive parent chain eksikse INCOMPLETE; sessiz yalnız-hot PASS verilmemeli.
4. Yeni dosyaya restore + bağımsız audit + kayıt sayısı/hash karşılaştırması +
   eski request anahtarlarıyla read/replay doğrulaması. En az iki doğrulanmış,
   erişim kontrollü kopya; power-loss/atomic manifest publish ve restore tatbikatı.
5. Ancak bu okuma/restore/dedup altyapısı ve ayrıca açık onay sağlandıktan sonra
   sıcak storage azaltma ayrı görevde değerlendirilebilir. Pending/active exposure,
   açık close, unresolved ambiguity, outbox veya erişilmeyen referans varken olmaz.

Bu görevde 1–5 tasarımdır. TTL/DELETE/VACUUM, canlı dosya taşıma, tablo birleştirme,
arşivden otomatik fallback veya hot history azaltma etkinleştirilmedi.
