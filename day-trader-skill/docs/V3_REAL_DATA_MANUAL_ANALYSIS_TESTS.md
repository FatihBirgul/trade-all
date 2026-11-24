# Gerçek veri ile salt okunur manuel analiz gözlemi

10 Kasım 2026, ayrı Python 3.11 MT5 bağlantısı. Explicit REAL_READONLY_DATA preflight REAL/Exness-MT5Real50/USC olarak geçti. Dört görünür alias, metadata, taze bid/ask quote ve 256'şar M15/H4 kapalı bar okunabildi. Son M15 bar-open UTC dört sembolde 11:45, son H4 08:00 idi. M15 örneklerinde XAU 3 boşluk, diğerleri 1; H4 örneklerinde 8 boşluk görüldü. Gözlem seans sözleşmesi değildir. Exact quote değerleri hızla eskidiği için bu raporda tekrar edilmedi.

Doğrulanmış `MT5_BROKER_HOURS` sağlanmadan `unified_analyze` dört sembolde de `INSUFFICIENT_DATA`/`DATA_UNAVAILABLE`, null lot ve `missing candle without verified broker hours` gerekçesi verdi. BUY/SELL, gerçek Entry/SL/TP veya V2 pattern canlı kabulü iddia edilmez. 8006 çalışan servisinin yeni commit'i kullandığı ve 8005 ile aynı terminale bağlı olduğu doğrulanmadı; mevcut servisler yeniden başlatılmadı. Bu koşullarda uçtan uca kabul **PARTIAL/BLOCKED**.
