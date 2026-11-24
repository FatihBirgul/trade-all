# Görev 11 — finansal motor bütünlüğü (31 Ekim 2026)

## Doğrulanmış başlangıç ve kapsam

GitHub PR metadata ve ayrı `git ls-remote`/clone ile doğrulandı:

- Backend PR #2 açık/Draft; `codex/v2-android-integration-20261029`,
  `b6066bf8f10ac28229db81d1448c475e455c1a41`. Yeni dal bunun üzerinden açıldı:
  `codex/task11-paper-integrity-20261031`. PR #1 ve main birleştirilmedi.
- Android PR #5 açık/Draft; `a14c11775288051b54c8a8fcb78749167a9b0304`,
  `codex/android-integration-20261029`; app.json 0.7.2/versionCode 11.
- Gateway PR #1 açık; `19038bdecd5ef472ff7826bb074208d300d682f8`,
  `codex/gateway-continuity-20261026`.
- Karşılaştırma dalı `bionic/task9-inspect-20261028`:
  `4b3999dc1c5a564f11744a5bf5824861737f230d`. `paper_ledger.py`,
  `paper_risk.py`, `api_models.py` referansla aynı; ayrışan quotes/tracking ve
  OpenAPI değişiklikleri taşınmadı. Otomatik merge yapılmadı.

AGENTS.md, master plan, implementation state, progress log, frontend API sözleşmesi,
OpenAPI ve testler incelendi. Finansal kapsam: paper_ledger, paper_risk, api_models,
API pozisyon/performance projeksiyonları, product_db, provider sayısal sınırları,
recovery/polling ve mevcut scanner/follow/backup regresyonları.

## Kanıtlanmış hatalar ve en küçük düzeltmeler

| Önem | Hata ve düzeltme öncesi kanıt | Düzeltme |
| --- | --- | --- |
| Yüksek | 10 birim giriş → kapasite 2 ile TP1 → 8 açık/3 TP1 bekleyen → manuel 6 kapatma → 2 açık. Sonraki TP1 mumunda 3 kapatılmaya çalışılıyor: HTTP 422 `INVALID_CLOSE_SIZE`. İşlem rollback yaptığı için fazla satış yok; mum ilerlemesi ve koruma işlemleri aynı sembolde engellenebiliyor. | Bekleyen TP1 miktarını mevcut açık miktarla sınırla; likidite ve step kuralları korunur. |
| Orta | Pozisyon GET hesabı çağıranın Decimal context'ini devralıyor. Aynı kayıt, precision=6/ROUND_UP ile `0.09240830`; normal context'te ve portfolio hesabında `0.09168824`. Performance toplam ücreti aynı koşulda `1.31808000` yerine `1.31807336` olmalı. | İki GET hesabını mevcut ledger'ın prec=60/ROUND_HALF_EVEN context'i içine al. Bakiye kayıtları değişmez. |
| Düşük | Para biçimleyicisi dış rounding'i devralıyor: `1.000000005`, ROUND_UP ile `1.00000001`; varsayılan half-even `1.00000000`. `-0` ve sıfıra yuvarlanan küçük negatifler negatif sıfır gösterebiliyor. | Ayrı sabit context ve yuvarlandıktan sonra pozitif sıfır. Sekiz ondalık basamak korunur. |

Context testleri açıkça değiştirilmiş çağıran context'ini kullanır; varsayılan
çalışmada gözlenmiş bakiye kaybı iddiası değildir. Float dönüşümü eklenmedi.
Mevcut finansal çekirdekte Decimal kullanımı zaten vardı; teknik analiz float
katmanını yeniden yazmak veya fiyat hassasiyetini sessizce değiştirmek kapsam dışıdır.

## Denetim sonucu ve korunan kurallar

| Kontrol | Sonuç / kanıt |
| --- | --- |
| Decimal/float ve geçersiz sayılar | Ledger/risk Decimal; API para/miktar metin. Context/biçimleme hataları düzeltildi. Pydantic finite/pozitif/24 digit/8 decimal kapıları ve yeni kötü girdi testleri başarılı. |
| Kısmi gerçekleşme | Emir kalan miktarı, pozisyon, nakit ve rezerv aynı transaction içinde. Mevcut partial entry/expiry/cancel ve yeni TP1 etkileşim testi başarılı. |
| Ücret/spread/slippage | Emir üzerinde parametre snapshot'ı; giriş en kötü edge + adverse, çıkış base - adverse; fee quote üzerinden. Journal/nakit denkleştirme ve TP/stop maliyet regresyonları başarılı. Model parametreleri değiştirilmedi. |
| Gerçekleşmiş/gerçekleşmemiş PnL | Entry fee cost basis'e dahil, partial exit basis oransal, son exit tüm kalan basis'i tüketiyor. Realized journal'dan, unrealized quantity × mark − basis. GET context farkı düzeltildi. |
| AUTO/MANUAL | Ayrı balance/risk/pause/journal ve bar başına ayrı kapasite; yeni eşzamanlı mum ve iki hesap rollback testi başarılı. |
| SL/TP | Mevcut gap-stop, partial sticky stop, TP1/TP2 ve ambiguous sıra testleri başarılı; yeni TP1 manuel azaltma sınırı eklendi. |
| Tekrar/eşzamanlılık/restart | BEGIN IMMEDIATE, kalıcı command scope/key ve immutable event fingerprint; mevcut order concurrency ve yeni event concurrency/restart testleri başarılı. |
| Rollback | İlk journal ve ikinci hesap journal arızaları sonrası tam rollback, aynı event ile tek retry başarılı. |
| Fiyat/miktar/para birimi | Riskte instrument/settlement/account quote eşleştirme; fiyat ve miktarın ayrı API alanları; existing quote/portfolio mismatch testleri başarılı. FX dönüşümü eklenmedi. |

Bu satırlar test edilen modelin kapsamını belirtir; tüm olası sayısal aralıkların
formel doğrulaması veya canlı borsa execution sertifikasyonu değildir.

## Yedi yeni regresyon

`backend/tests/test_v2_product_api.py`:

1. `test_partial_tp1_then_manual_reduction_cannot_overclose_or_block_replay`:
   TP1/manual etkileşimi, tam kapanış, mum tekrarı, toplam çıkış miktarı ve
   seed + gerçekleşmiş PnL = nakit; AUTO bakiye izolasyonu.
2. `test_position_pnl_is_independent_of_callers_decimal_context`:
   pozisyon/portföy PnL eşitliği ve düşük precision/ROUND_UP bağımsızlığı.
3. `test_money_text_uses_fixed_rounding_and_unsigned_zero`:
   half-even ve negatif sıfır normalizasyonu.
4. `test_performance_fees_are_independent_of_callers_decimal_context`:
   gerçek fixture giriş/çıkışından sonra performance ücret toplamı.
5. `test_invalid_numeric_inputs_never_create_orders_closes_or_events`:
   NaN/sNaN/Infinity, negatif/sıfır miktar, metin ve fazla ondalık reddi;
   tüm OHLCV alanlarında nonfinite/geçersiz girdi, değişmeyen durum ve ardından
   geçerli mumun işlenmesi.
6. `test_concurrent_event_and_restart_keep_account_liquidity_and_journal_isolated`:
   iki eşzamanlı aynı mum, hesap başına bağımsız %1 kapasite, tek journal,
   nakit denkleştirme ve restart sonrası aynı mumun tekilleştirilmesi.
7. `test_second_account_journal_failure_rolls_back_both_accounts_and_retries_once`:
   ikinci journal yazımına enjekte SQLite hatası, iki hesapta tüm fill/nakit/
   pozisyon/journal/receipt rollback ve aynı mumla başarılı tek retry.

Yeni hata testleri düzeltmeden önce çalıştırıldı: TP1, pozisyon context ve
biçimleyici testleri 3/3 başarısız; ayrı performance testi 1/1 başarısız.
TP1 422; PnL/ücret/rounding farkları yukarıdaki değerlerle kaydedildi.
Son durumda bu hatalar ve bütün mevcut regresyonlar başarılıdır.

## Yerel doğrulama

Python 3.12/Linux, geçici SQLite ve kontrollü fixture girdileri:

- Başlangıç: 220/220 V2 unittest.
- Son: 227/227 V2 unittest (`-W error::ResourceWarning`), ağ ve kalıcı SQLite
  erişimi runner tarafından engellenerek.
- Quote pytest 2/2 ve seçili offline V1 outcome 9/9.
- Güncel Gateway geliştirme dalında 42/42 pytest; sekiz gerçek V2 uygulaması /
  geçici DB entegrasyonu dahil (`TRADE_AI_BACKEND_REFERENCE` yeni backend).
- Backend compileall başarılı.
- Gerçek 127.0.0.1 HTTP smoke: fixture analiz/chart readback, idempotency,
  fill/close nakit denkleştirme, AUTO/MANUAL ayrımı, scanner dedup ve server
  restart persistence başarılı; geçici server test sonunda durduruldu.
- `export_v2_contract.py` üretimi ile kayıtlı OpenAPI JSON nesneleri birebir eşit;
  yalnız sıralama/biçim farkı geri alındı. Örnek JSON dosyalarında fark yok.

Tekrar çalıştırma (backend dizini):

```text
python -W error::ResourceWarning tests/run_v2_offline_tests.py
python -m pytest -c tests/pytest-v2.ini tests/test_v2_mobile_quotes.py tests/test_outcomes.py::TestOutcomeEngineUnit -q
python -m compileall -q market_ai server.py start_v2.py scripts
python scripts/smoke_v2_loopback.py
```

## Uyumluluk ve sınırlar

API path/schema/alan türleri, USDT anlamı, seed=10000, risk limitleri, %1 katılım,
5 bps ücret, 2 bps spread, taraf başına 1 bp slippage, maliyet bazlı PnL,
TP1/TP2/stop/ambiguity politikası korunur. Negatif sıfır matematiksel sıfıra
normalize edilir. İstemci veya Gateway uyarlaması gerekmiyor; depoların hiçbir
kaynak dosyası değiştirilmedi. Android schema/portfolio validator/paper request
kodları incelendi. Bu görevde fiziksel telefon veya kullanıcının Windows PC'si
üzerinden test yapılmadı. Mevcut immutable journal/analiz geçmişi yeniden yazılmaz.

Windows/Linux için Decimal/SQLite/Python standart API'leri kullanılıyor;
mevcut iki OS workflow'una bu görev dalının push tetikleyicisi eklendi.
Kod/CI checkpoint `757f202dd4e2e57c81f9042ee252f574c6495e51` için:

- [Windows + Ubuntu CI](https://github.com/FatihBirgul/trade-ai/actions/runs/41185741446):
  iki OS success; her birinde 227 V2, 9 outcome, compile; Windows PowerShell
  launcher yalnız syntax kontrolü başarılı.
- [Python 3.11 + 3.12 quote CI](https://github.com/FatihBirgul/trade-ai/actions/runs/41185756688):
  iki iş success; her birinde 227 V2 + 2 quote.

[Draft PR #3](https://github.com/FatihBirgul/trade-ai/pull/3); kod commit
[75f82e9](https://github.com/FatihBirgul/trade-ai/commit/75f82e9), CI commit
[757f202](https://github.com/FatihBirgul/trade-ai/commit/757f202).
Sonraki belge commit'i yalnız denetim ve doğrulama kaydını tamamlar.

Canlı/verili DB, özel ağ, main, deploy veya gerçek para işlemleri değiştirilmedi.
Otomatik sanal işlem ayarları etkinleştirilmedi; AUTO yalnız izole mevcut/yeni
fixture testlerinde kullanıldı. Yeni testlerin başarısı gerçek piyasa execution
veya strateji kârlılığı kanıtı değildir.

Eksikler: tick/order-book execution, FX/XAU/kur dönüşümü, çok dönemli backtest ve
walk-forward, history retention, notification delivery ve fiziksel cihaz/Windows
operasyon testi hâlâ ayrı iş kapsamıdır. Sonraki öneri: kaydedilmiş olayları yeniden
oynatan bağımsız finansal invariant denetleyicisi; ardından kontrollü uzun süreli
fixture soak/recovery testi ve history retention tasarımı. Önce kârlılık iddiası
yerine nakit/journal/cost-basis/realized-unrealized PnL denkleştirmesi ölçülmeli.
