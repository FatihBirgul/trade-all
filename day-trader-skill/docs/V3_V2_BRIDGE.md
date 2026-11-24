# Manuel V2 mum formasyonu köprüsü

Bu aşama V2 `backend/market_ai/engines/candlestick.py:detect` fonksiyonunu V5 `analytical_extension` ABI'sine bağlar. V2 dosyası kopyalanmaz veya değiştirilmez. Köprü yalnız açıkça yapılandırılmış, SHA-256 içerik hash'i eşleşen kaynak dosyayı yükler. Kaynak dosyadan bytecode/cache yazmaz. Bu dosya güvenilir yerel V2 checkout'undan seçilmelidir; hash eşleşmesi kaynak lisansı veya imzası değildir.

Windows PowerShell yapılandırması, analiz API'sini başlatan süreçte:

```powershell
$env:V2_CANDLESTICK_FILE = '%USERPROFILE%\trade-ai-v2-antigravity\backend\market_ai\engines\candlestick.py'
$env:V2_CANDLESTICK_SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $env:V2_CANDLESTICK_FILE).Hash.ToLowerInvariant()
```

Bu iki değişken yoksa mevcut public V5 davranışı sürer. Eksik veya uyuşmayan yapılandırma manuel `POST /api/v5/analysis` isteğinde 503 döndürür. Önceden açıkça ayarlanmış `app.state.analytical_extension` önceliklidir. Köprü yalnız istek geldiğinde çalışır; scheduler veya emir fonksiyonu yoktur. PWA bağlantısı için mevcut Analiz Et akışının V5 endpoint'ini ve tipli yanıt alanlarını tüketmesi ayrıca gerekir; PWA ve Windows `mt5_bridge.py` bu çalışmada değiştirilmedi.

V3 snapshot'u önce sembol, bid fiyat tabanı, broker saatleri, kapalı mum, OHLC, kimlik, üst zaman dilimi cutoff ve tazeliği denetler. Köprü yalnız bu snapshot'un ana zaman dilimi OHLC verisini V2 dedektörüne verir. Dönen örüntüler isim, yön, oluşum ve ilk bilinebilir UTC kapanış zamanı, confirmation ve yaş içerir. Pattern yönü bu aşamada bağımsız işlem oyu değildir. V5 confluence conflict ve V3 risk/entry/SL/TP/lot kapıları olduğu gibi çalışır. Tam V2 strateji motoru, grafik formasyonları, FVG ve gerçek hacim metotları açıkça eksik kalır. Tick volume gerçek hacim olarak kullanılmaz.

10 Kasım 2026 tarihinde doğrulanan V2 HEAD `c80c97f` içindeki dedektörün yerel SHA-256 değeri `3ab2582b92c69d3f7dffece1b923f5793658677713f8ea7d66a543729c01a628` olarak doğrulandı. Fixture ile gerçek kaynak çağrısında 6 pattern, `PRIVATE_PARTIAL`, `BUY_CANDIDATE` ve 1.02 lot görüldü. Bu sentetik sonuç canlı Forex performansı değildir. Kaynak güncellenirse hash yeniden incelenip açıkça güncellenmelidir.
