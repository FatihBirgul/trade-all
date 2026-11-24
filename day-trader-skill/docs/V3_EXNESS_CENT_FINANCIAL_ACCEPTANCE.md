# Exness Cent finansal kabulü

11 Kasım 2026. REAL veri kaynağı, USC varsayımsal sermaye, broker risk hesabı ve execution izni ayrı tutulur. Gerçek bakiye okunup sermaye yapılmadı; login/logout, hesap değişimi veya order_send/order_check çağrısı yok.

## Korunan ve eklenen kapılar

Mevcut minimum lot veto, minimuma ankrajlı volume rounding, stop/tick grid, spread sonrası stop mesafesi, net maliyet/R:R ve broker PnL/tick-loss tutarlılığı korunur. Yeni REAL contract alanları eksik/çelişkiliyse plan/lot reddedilir. Finansal endpoint'ler V5 ile aynı exact account preflight'ı kullanır. REAL_READONLY_DATA seçiliyken provider veri okumaları da preflight yapılmadan symbol selection yapamaz.

`size_lots` REAL metadata için taze quote ve bağlama uygun onaylı spread policy ister; onaysız durumda broker oracle'a bile geçmeden ret verir. Risk calculate için optional timeframe varsayılan M15; risk policy plan timeframe kullanır. Legacy fixture/DEMO davranışı korunur.

`order_calc_profit` yalnız salt okunur varsayımsal zarar oracle'ıdır. Birinci örnek ve yuvarlanmış son lotta sonuç, mevcut tick loss değeri yanında ayrıca contract-size eğimiyle karşılaştırılır. USD profit -> USC için açık 100 cent/USD çarpanı kullanılır; USD ve USC eşit kabul edilmez. USDJPY profit JPY olduğunda taze aynı USDJPY bid/ask çiftinin tersinden hesaplanan USC dönüşüm aralığı gerekir; eksik/stale dönüşümde BLOCK. Broker sonucu bu aralıkla %1 veya 0.01 USC yuvarlama toleransında uyuşmalıdır. Bu tolerans önceki tick oracle yaklaşımıyla aynı büyüklüktedir; broker dönüşüm/yuvarlama modelinin kesin tarihsel ispatı değildir.

## Canlı salt okunur örnekler

11 Kasım 2026 16:20:32 İstanbul; her iki yön için 1 lot ve 10 tick zarar mesafesi. Bunlar emir değildir, finansal örnektir. Hesap kimliği önce/sonra aynı; balance null.

| Sembol | Mesafe | BUY broker loss (USC) | SELL broker loss (USC) | Bağımsız contract hesabı |
|---|---:|---:|---:|---|
| XAUUSDc | 0.010 | 1.00 | 1.00 | delta * 1 * 100 = 1 |
| EURUSDc | 0.00010 | 10.00 | 10.00 | delta * 1000 * 100 = 10 |
| GBPUSDc | 0.00010 | 10.00 | 10.00 | delta * 1000 * 100 = 10 |
| USDJPYc | 0.010 | 6.28 | 6.28 | yaklaşık 6.27490-6.27530 USC, broker cent yuvarlamasıyla uyumlu |

Tam snapshot: `docs/evidence/broker_current_observation_20261111.json`. Bu sonuçlar gelecekteki tick value veya tarihsel contract/seans kanıtı değildir. Hiçbir canlı izin limiti veya uygulanabilir lot onaylanmadı; tüm sembollerde spread onayı yok.

Yeni deterministik kontroller bağımsız sabit aritmetik oracle kullanır: yanlış contract size, tick loss, profit/account currency, dönüşüm eksikliği/stale, minimum risk aşımı, volume rounding, stop level ve spread spike retleri. Mevcut V5 BUY/SELL/WAIT, Entry/SL/TP ve V2 descriptive-only testleri devam eder. Hypothetical USC sonucunda risk_balance_source HYPOTHETICAL_CAPITAL, trading_eligibility NOT_EVALUATED ve execution_permission false kalır.

[MQL5 OrderCalcProfit](https://www.mql5.com/en/book/automation/experts/experts_ordercalcprofit) güncel ortamda hesap para biriminde sonuç verdiğini açıklar; geçmiş kur veya uygulama garantisi değildir. Test sayıları teslim raporundadır.
