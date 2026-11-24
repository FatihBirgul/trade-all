# P1 V2 API kabulü

11 Kasım 2026. Üretim `forex/*.py` değiştirilmedi. Ana V3 kodu ayrı Windows süreçlerinde gerçek HTTP üzerinden çalıştırıldı; bu sonuç canlı broker formasyon bulunabilirliği değildir.

## Pin ve pattern çıktısı

V2 commit `c80c97f227a2c233a610df669919ba2f464e4f9f` chart Git blob SHA256:

`af69112c91938c4bd6fea3d16f43a333f63c35ea3715ed082069868e1018f1ba`

QA candlestick kaynağı da aynı committen değişmez Git nesnesi olarak alınıp yalnız temp QA `engines/candlestick.py` dosyasına yazıldı; V2 checkout'a yazılmadı. Ayrı beklenen candlestick SHA256:

`45ee833fd3a5ffd178a4ee565e5914f79e9fb0b1c2aa62fe16b703057f63542c`

`POST /api/v5/analysis` chart ve candlestick composite ile HTTP 200 döndürür. Fixture top/bottom alanları `chart_patterns.role=DESCRIPTIVE_ONLY`, doğru aile, source_commit/SHA256, timeframe, formed/first-known/confirmation zamanlarını taşır. `first_known_utc > formed_at_utc`; mevcut testlerde pivot indeks 212, first-known indeks 215, sağ pencere 3 bar. 213/215 bar prefix'inde erken bilgi yok; 216/220 bar çıktısı karşılaştırıldı. M15/H1/H4 testleri tam regression içindedir. Kaynak dışı yeni formasyon ailesi eklenmedi.

Boş fixture chart listesi `AVAILABLE` + `items=[]` verir; unavailable ile karıştırılmaz. Yanlış SHA veya olmayan kaynak yükleme denemesi HTTP 503 `DATA_UNAVAILABLE` verir. Hatalı source configuration başarılı pattern response sayılmaz. Candlestick bağlamı ayrı `candlestick_patterns` alanında korunur; yeni chart etiketleri karar oyu üretmez.

## Değişmezlik

HTTP senaryoları top, bottom, sell, wait, missing candle, unknown session, opening soon, close only, stale ve empty için bridge açık/kapalı karşılaştırıldı. İki çağrının snapshot_id değeri de aynı olmak zorunda. Birebir eşit alanlar:

`final_decision`, `decision_reasons`, `trading_eligibility`, `data_status`, `entry_zone`, `stop_loss`, `take_profit_1`, `take_profit_2`, `spread`, `account_currency`, `lot_size`, `risk_amount`, `risk_reward`, tüm `risk_policy`, `market_status`, `execution_permission`.

`risk_policy.sizing` içindeki maliyetli/net risk hesabı da sözlük eşitliği kapsamındadır. Ek snapshot QA `legacy_signal` alanını da karşılaştırır. BUY, SELL, gerçek WAIT, USC ve INSUFFICIENT_DATA kontrollü fixture kıyasları iki Python sürümünde aynıdır. REAL-policy branch'i mock-only MT5Provider alt sınıfıyla işletilir; terminal erişimi yoktur. `HYPOTHETICAL_CAPITAL` için eligibility `NOT_EVALUATED`; gerçek broker bakiye/provenance üretilmez. `execution_permission=false` tüm senaryolarda değişmez.

Legacy `balance:10000` REAL policy altında yok sayılır, lot null kalır. Explicit hypothetical USC istekleri desteklenir; minimum lotu karşılamayan sermaye `NO_TRADE` ve lot null üretir. USD/USDC karışıklığı, REAL balance okunmaması ve no-order testleri mevcut tam pakette geçer.

## PWA ve canlı sınır

Güncel PWA `hypothetical_capital`, `hypothetical_currency='USC'`, `risk_pct`, `confirmations=['H4']`, `require_private=false` gönderir; API bu şekli kabul eder. PWA additive chart/candlestick alanlarını reddetmez. Ancak panel bu alanları çizmez ve NOT_EVALUATED planını saklar; frontend uyumu PARTIAL'dır.

Mevcut canlı 8006'dan alınan yanıt `INSUFFICIENT_DATA`, chart null, lot null, `execution_permission=false`. Dolayısıyla P1'in **gerçek ağ API yanıtında varlığı YES (fixture)**, **mevcut canlı broker yanıtında kabulü UNVERIFIED/PARTIAL**. Kaynak hash'i eşleşen disk ile çalışan belleğin sürümü eşit sayılmadı. Daha fazla ayrıntı `V3_RUNTIME_ACCEPTANCE_TR.md` ve `V3_RUNTIME_CUTOVER_PLAN.md` içindedir.
