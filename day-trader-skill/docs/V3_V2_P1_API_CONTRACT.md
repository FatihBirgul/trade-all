# Manuel analiz API sözleşmesi: P1

Endpoint değişmedi: yalnız kullanıcı POST isteği ile `/api/v5/analysis`. `forex/api.py`, React PWA ve `mt5_bridge.py` değiştirilmedi. `V2_CHART_GIT_ROOT=%USERPROFILE%\trade-ai-v2-antigravity` ayarı varsa, doğrulanmış kaynak blob yüklenir; ayar yoksa mevcut V5 akışı sürer. `V2_CANDLESTICK_FILE` + `V2_CANDLESTICK_SHA256` ayrıca ayarlıysa iki betimleyici adaptör birleşir. Kaynak/NumPy uyuşmazlığında yapılandırılmış endpoint 503 `DATA_UNAVAILABLE` verir. İstek sırasında hesap değişimi veya emir fonksiyonu yoktur.

Başarılı yanıtta mevcut `chart_patterns` alanı kullanılır. Örnek (test fixture'ındaki çift tepe, alanların bir bölümü):

```json
{
  "final_decision": "BUY_CANDIDATE",
  "legacy_signal": "BUY",
  "execution_permission": false,
  "integration_status": "PRIVATE_PARTIAL",
  "chart_patterns": {
    "status": "AVAILABLE",
    "role": "DESCRIPTIVE_ONLY",
    "version": "v2-chart-pivot-descriptive-1",
    "items": [{
      "name": "Double Top",
      "direction": "BEARISH",
      "formed_at_utc": 1799992800,
      "first_known_utc": 1799995500,
      "confirmation_utc": 1799995500,
      "age_bars": 7,
      "confirmation_state": "STRUCTURAL_CONFIRMED",
      "invalidation_state": "NOT_MODELED",
      "integration_status": "DESCRIPTIVE_ONLY"
    }]
  }
}
```

Örnekteki bearish chart etiketi BUY kararına karşı oy olarak kullanılmaz; P1'in sözleşmesi betimleyicidir. Üretim yorumunda bu etiket işlem gerekçesi sayılamaz. Mevcut `candlestick_patterns`, `private_extension`, `source_versions` ve `missing_capabilities` alanları korunur. `v2_strategy_routing` ve `real_volume_methods` eksik kalır. `require_private=true` bu kısmi entegrasyonu tam özel motor saymaz ve güvenli ret üretir.

V5 snapshot doğrulaması önce çalışır. Eksik/henüz kapanmamış mum, bilinmeyen broker saati, yanlış provider/pazar kimliği ve risk engeli V2 alanıyla açılamaz. REAL hesap yalnız salt-okunur kaynak olarak kalır; varsayımsal sermaye kuralı, USC kimliği ve hesap güvenliği aynı kalır.
