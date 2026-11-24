# REAL piyasa verisi, manuel simülasyon politikası

10 Kasım 2026. V5 MT5 isteğinde varsayılan `MT5_ANALYSIS_POLICY=DEMO_ONLY` korunur. REAL veriye yalnız operatörün açık `MT5_ANALYSIS_POLICY=REAL_READONLY_DATA`, `MT5_EXPECTED_REAL_SERVER` ve `MT5_EXPECTED_REAL_CURRENCY` ayarıyla geçilir. Bilinmeyen/eksik politika 503 `ACCOUNT_PREFLIGHT_BLOCKED`; DEMO_ONLY eski 503 `DEMO_PREFLIGHT_BLOCKED` davranışını korur. MT5 SDK DEMO/CONTEST/REAL enumları, connected terminal, exact server/currency ve bellek içi account identity kontrol edilir. Hesap değişimi symbol, quote, rates ve broker profit okumalarının öncesi/sonrasında reddedilir. Login/bakiye API veya loga yazılmaz.

REAL modda `symbol_select` çağrılmaz; alias yalnız zaten görünürse okunur. Kullanılan MT5 yöntemleri `initialize`, `terminal_info`, `account_info`, `symbol_info`, `symbol_info_tick`, `copy_rates_from_pos`, `order_calc_profit` ve ayrı süreç bağlantısını kapatmak için `shutdown` ile sınırlıdır. Emir, order_check, login/logout veya otomatik tarama yoktur. `analysis_mode=MANUAL_SIMULATION`, `execution_permission=false`, `market_data_account_mode=REAL` yanıt alanları emre izin vermez. `DEMO_ONLY` ile hesap bakiyesi davranışı korunur.

Canlı terminal ayrı süreçte read-only preflight'tan geçti: REAL, `Exness-MT5Real50`, `USC`. Bu kendi bağlantısının kanıtıdır; 8005 ve 8006 süreçlerinin aynı terminali kullandığı kanıtlanmadı. Kaynak: [MetaQuotes hesap türleri](https://www.mql5.com/en/docs/constants/environment_state/accountinformation).

Preflight'ta doğrulanan para birimi, mum/seans QC güvenli ret üretse bile V5 `account_currency` alanında kalır. Bu yalnız para birimi kimliğidir; gerçek hesap bakiyesi taşınmaz.
