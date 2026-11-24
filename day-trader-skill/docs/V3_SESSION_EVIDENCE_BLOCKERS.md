# Tarihsel seans kanıtı engelleri

11 Kasım 2026: **BLOCKED_BY_EXTERNAL_EVIDENCE**. Bu görev broker seans motorunu, importer'ı veya MQL5 exporter'ı değiştirmedi. Güncel contract/tick/spread gözlemi, 9 Kasım XAUUSDc tarihsel quote seansını doğrulamaz.

Önceki gözlemler: son M1 21:57, sonraki M1 23:00; 23:00:30.141 / 23:01:00.199 / 23:02:00.115 tick'leri; 23:00 M15 açılışı. Önceki runtime görevinde M1/M15 aralığı yeniden okundu; bu görev onları bağımsız seans takvimiymiş gibi yükseltmedi. 23:00 M15 barı 23:15'ten önce kapanmış değildir.

`forex/session_evidence.py` v1 yalnız MT5_CURRENT_WEEKLY_SCHEDULE alır; historical_gap_authorized false ve effective_period null. `tools/mt5_session_export/MT5SessionExport.mq5` güncel haftalık quote/trade pencerelerini verir; geçmiş DST/holiday veya tarihli CLOSE_ONLY onayı değildir. Yeni sentetik testler eksik dış kanıtın yerine geçirilmedi.

## Gereken dış kanıt

Exact XAUUSDc ve Exness-MT5Real50 kapsamı; 9 Kasım 2026 effective tarih aralığı; açık UTC quote/trade pencereleri; server timezone/DST dönüşümü; holiday/maintenance istisnaları; kaynak URL/doküman sürümü, toplama zamanı ve insan kaynak incelemesi. XAUUSD genel saatleri veya bugünkü haftalık schedule otomatik kullanılamaz. Şu anda böyle onaylı tarihsel dosya sağlanmadı; importer'a yeni kabul yolu açılmadı.

## Kanıt sağlanırsa kabul planı

1. Orijinal baytlar/hash ve kaynak kapsamını muhafaza et; hesap bilgisi içeren belgeyi public API'ye taşıma.
2. Yeni tarihsel şema için source, exact alias/server, effective interval, quote/trade ayrımı ve her günün kapsamasını bağımsız doğrula. Sadece etiketi HISTORICALLY_VERIFIED yapmak yetmez.
3. Önce offline fixtures: yanlış sembol/sunucu/tarih, eksik gün, çakışma, DST, tatil, quote-trade farklılığı, sınırda dakika/saniye ve invalid UTC retleri.
4. Orijinal M1/M15/tick gözlemini tarihli quote pencereleriyle karşılaştır; açık aralıkta eksik barı reddet, kapanış aralığını yalnız tam kanıtla kabul et; kapanmamış M15'i ekleme.
5. Core/V5 regressions, source/first-known ve no-order kontrollerini tekrar çalıştır; yalnız yetkili ayrı değişiklikle kanıtı runtime'a bağla.

Yeni testte bir sembolün UNKNOWN seansı diğer geçerli fixture sembolünün BUY sonucunu global kapatmıyor. Kullanılan schedule açıkça sentetik test verisidir; canlı XAUUSDc saatleri değildir. Canlı ret güvenli sonuç olarak kalır.
