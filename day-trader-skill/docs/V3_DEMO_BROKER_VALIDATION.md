# DEMO broker doğrulama durumu

Gerçek DEMO preflight geçmediği için canlı XAUUSD/EURUSD/GBPUSD/USDJPY alias, bid/ask, UTC tick, digits, tick size/value profit/loss, contract size, lot grid, stop/freeze level, profit currency, broker session ve `order_calc_profit` doğrulaması yapılmadı. Önceki `XAUUSDc` vb. eşlemeler REAL Exness Cent gözlemidir; DEMO'ya taşınmaz. Mevcut `MT5_SYMBOL_MAP`, `MT5_BROKER_HOURS` ve `MT5_MAX_SPREAD` açık yapılandırma gerektirir. Gözlenen boşluklar otomatik VERIFIED schedule değildir.

Port 8005 Python 3.11, 8006 Python 3.11, 5173 Node süreçlerinde dinliyor; 8006 OpenAPI V5 analiz yolunu gösteriyor. Süreçler yeniden başlatılmadı. İki servis arasında terminal/account/source eşitliği kanıtlanmadı. Güvenli DEMO terminali sağlanırsa önce preflight, ardından dört sembol için yalnız read-only metadata, quote, kapalı mum ve profit oracle karşılaştırması yapılmalıdır.
