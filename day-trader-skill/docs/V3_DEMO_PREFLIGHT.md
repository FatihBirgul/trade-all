# DEMO hesap ön kontrolü

10 Kasım 2026. Manuel `POST /api/v5/analysis`, MT5 provider kullanıyorsa sembol, quote, mum veya broker kârı okumadan `MT5Provider.demo_preflight()` çağırır. Beklenen `MT5_EXPECTED_DEMO_SERVER` ve `MT5_EXPECTED_DEMO_CURRENCY` açıkça yapılandırılmalıdır. Terminal connected, account_info `trade_mode`, exact server, currency, pozitif balance ve SDK'nın DEMO/CONTEST/REAL enum sabitleri kontrol edilir. REAL/CONTEST/UNKNOWN, bağlantı veya ayar eksikliğinde yalnız generic `503 DEMO_PREFLIGHT_BLOCKED` döner; hesap numarası ya da bakiye yanıta/loga yazılmaz. Sonraki MT5 symbol okumaları hesap kimliği ve modunun değişmediğini yeniden denetler.

Resmî enum kaynağı: [MetaQuotes Account Properties](https://www.mql5.com/en/docs/constants/environment_state/accountinformation) ve [Python account_info](https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py). Sunucu adında Demo sözcüğü tek başına kanıt değildir.

Yerel Python 3.11 SDK'sında üç enum sabiti mevcut. Salt okunur, ayrı süreçte yapılan varsayılan terminal `initialize` + terminal/account_info kontrolü `PREFLIGHT REAL` döndürdü. Yalnız hesap türü okundu; fiyat, mum veya sembol okunmadı. Bu, 8006 servisinin hangi terminale bağlı olduğunu kanıtlamaz. Başka hesaba otomatik geçilmedi ve çalışan servisler kapatılmadı. Canlı DEMO kabulü BLOCKED.
