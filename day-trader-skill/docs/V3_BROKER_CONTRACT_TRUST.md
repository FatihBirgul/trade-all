# Broker contract trust

11 Kasım 2026. Kaynak başlangıç `09e5dab3bead337b3fab6a9267bbfe4fc16f3e7b`; geliştirme dalı `codex/v3-broker-evidence-readiness`.

`forex/broker_contract.py` her metadata alanını bağımsız değerlendirir. `CURRENT_MT5_OBSERVED` güncel terminal gözlemidir; operatör onayı veya geçmiş sözleşme doğrulaması değildir. `UNVERIFIED` eksik/yetersiz alanı, `CONFLICTING` kimlik/birim/tutarlılık uyuşmazlığını gösterir. `OPERATOR_APPROVED` bu sürümde yalnız ayrı spread konfigürasyonunda açık operatör beyanıdır. Hiçbir alan kendiliğinden `HISTORICALLY_VERIFIED` olmaz.

`broker_contract.fields`: canonical/broker symbol, server, account currency, base/profit/margin currency, contract size, digits, point, tick size, profit/loss tick value, volume min/max/step, stop/freeze level, trade/calc mode ve tanınan calc-mode adı. `missing_fields` ve `conflicting_fields` ayrı listelerdir. Point/digits, tick grid ve volume aralığı ayrıca kontrol edilir. Alanlardan biri bozukken diğerlerinin gözlemi silinmez. REAL metadata eksik/çelişkiliyse plan/lot kapısı kapalıdır.

## Güncel canlı gözlem

11 Kasım 2026 13:20:32 UTC / 16:20:32 Europe/Istanbul. Exact REAL / Exness-MT5Real50 / USC preflight; hesap kimliği okumadan önce/sonra bellekte aynı; hesap numarası ve gerçek bakiye kaydedilmedi. Dört alias açık mapping ile doğrulandı.

| Canonical / broker | Current contract trust | Contract size | Digits / point / tick | Profit / margin | Calc / trade mode | Stop / freeze |
|---|---|---:|---|---|---|---|
| XAUUSD / XAUUSDc | CURRENT_MT5_OBSERVED | 1 | 3 / 0.001 / 0.001 | USD / XAU | FOREX(0) / 4 | 0 / 0 |
| EURUSD / EURUSDc | CURRENT_MT5_OBSERVED | 1000 | 5 / 0.00001 / 0.00001 | USD / EUR | FOREX(0) / 4 | 0 / 0 |
| GBPUSD / GBPUSDc | CURRENT_MT5_OBSERVED | 1000 | 5 / 0.00001 / 0.00001 | USD / GBP | FOREX(0) / 4 | 0 / 0 |
| USDJPY / USDJPYc | CURRENT_MT5_OBSERVED | 1000 | 3 / 0.001 / 0.001 | JPY / USD | FOREX(0) / 4 | 0 / 0 |

Tümünde lot min/max/step 0.01/200/0.01. Profit/loss tick değerleri dahil tam, sanitize gözlem: `docs/evidence/broker_current_observation_20261111.json`. USDJPY tick değeri kurla değişebilir; kalıcı sabit yapılmadı. Bu snapshot tek zaman noktasıdır.

`market_classification` tam sembol ve currency kimliğinden PRECIOUS_METAL_PAIR veya FOREX_PAIR olarak, CURRENT_MT5_OBSERVED düzeyinde yayımlanır. MT5 FOREX hesaplama modu hukuki ürünün spot olduğu anlamına gelmez. Eski `market_type` / `contract_type` alanları bağımsız kanıt olmadan unverified bırakılır; ekonomik aileyi hukuki spot/CFD onayı sayma. Raw calc mode ile adı da bağımsız eşleştirilir.

## Sınırlar ve kaynaklar

Güncel contract size/tick değeri bütün geçmiş barları doğrulamaz; taze quote da tarihsel seans boşluğunu açmaz. Session gate değiştirilmedi. API metadata dosya yolu veya operator reference içeriği sızdırmaz. Özel kaynak yolları public tanılama endpoint'ine eklenmedi.

[MQL5 symbol properties](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants) point, digits, spread ve calc-mode semantiği için kullanıldı. [Exness Standard Cent](https://get.exness.help/hc/en-us/articles/17537782786588-Standard-Cent-account) cent lot ve USC birim ayrımını destekler; güncel dört broker sözleşmesinin tarihsel onayı yerine geçmez.
