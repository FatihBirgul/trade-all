# XAUUSDc seans kanıtı edinme durumu

10 Kasım 2026. Bu inceleme yalnız resmî sayfaları ve mevcut terminalin salt-okunur arayüzlerini kullandı. Otomatik web kazıyıcı, hesap girişi veya terminal script çalıştırması yapılmadı.

| Kaynak | Kapsam ve tarih | Sonuç |
| --- | --- | --- |
| [Exness enstrüman saatleri](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours) | Sayfa 29 Eylül 2026 güncellenmiş; enstrüman, tarih ve zaman dilimi seçilebilen çizelgeyi anlatıyor. | Metin görünümü seçilmiş XAUUSDc/9 Kasım çizelgesini vermiyor. Yerel tarayıcı seçiciye erişim denemesi Personal Area yönlendirmesinde zaman aşımına uğradı. Seçici içeriği doğrulanamadı. |
| [Exness Standard Cent](https://get.exness.help/hc/en-us/articles/17537782786588-Standard-Cent-account) ve [sembol ekleri](https://get.exness.help/hc/en-us/articles/360014560220-Account-type-suffixes) | 7 Kasım ve 26 Eylül 2026 güncellemeleri. | XAUUSDc'nin ayrı `-c` Standard Cent enstrümanı olduğunu doğruluyor; seans saatini vermiyor. |
| [Exness ABD yaz saati bitişi duyurusu](https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026) | 3 Kasım 2026 güncellemesi; UTC tablo, XAUUSD satırı. | XAUUSD için kışın Pazartesi–Perşembe 21:58–23:00:30 kapalı, 23:00:30–23:02 close-only diyor. XAUUSDc adını açıkça kapsamıyor; bu kural XAUUSDc'ye aktarılmadı. |
| [MQL5 quote seansı](https://www.mql5.com/en/docs/marketinformation/symbolinfosessionquote) ve [trade seansı](https://www.mql5.com/en/docs/marketinformation/symbolinfosessiontrade) | Sembol ve haftanın günü için mevcut haftalık pencereler. | MQL5 scripti bu iki salt-okunur fonksiyonu kullanabilir. Tarihsel holiday/DST veya belirli tarihteki CLOSE_ONLY sonucunu vermez. |

Resmî Exness seçicisinin kullanım koşullarından otomatik erişim izni belirlenemedi. Bu nedenle kazıma kodu kurulmadı; CAPTCHA veya Personal Area girişi denenmedi. Kaynak sayfanın genel `XAUUSD` açıklaması ile `XAUUSDc` sembol kimliği eşit sayılmadı.

Güvenli tarihsel açılış için enstrüman adı `XAUUSDc`, 9 Kasım 2026, Exness-MT5Real50 sunucu kapsamı, UTC saatleri, quote ve yeni pozisyon durumları, tatil/DST etkisi ve kaynak sürümü birlikte doğrulanmalıdır. Mevcut kanıt düzeyi **UNVERIFIED**. Bir defalık MT5 haftalık seans çıktısı, bugünkü farkları gösterebilir; 9 Kasım boşluğunu tek başına doğrulamaz.
