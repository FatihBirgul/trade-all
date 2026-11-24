# REAL salt-okunur manuel analiz kabulü

Durum: **PARTIAL / BLOCKED** (10 Kasım 2026). REAL hesap yalnız piyasa verisi kaynağıdır; otomatik veya manuel emir gönderme yolu eklenmedi. `DEMO_ONLY` varsayılanı, `REAL_READONLY_DATA` açık seçimi, `execution_permission=false`, USC risk/lot sınırları ve mevcut Entry/SL/TP kapıları korunur.

| Kapı | Sonuç |
| --- | --- |
| Tam broker alias, sunucu, para birimi | XAUUSDc / Exness-MT5Real50 / USC canlı salt-okunur metadata ile görüldü. |
| Güncel quote | Taze quote okunabildi; fiyat değeri rapora alınmadı. |
| Güncel trade mode | Okuma anında `4`; geçmiş 9 Kasım modu bilinmiyor. |
| 9 Kasım XAUUSDc quote seansı | UNVERIFIED; resmî seçici içeriği alınamadı. |
| Eksik M15 aralığının kapalı seans olarak kanıtı | YOK; `forex.contracts` ret kapısı açık. |
| Güncel haftalık MT5 export | Kaynak ve derlenmiş script hazır; terminalde çalıştırılmadı. Tarihsel kanıt olmaz. |
| `/api/v5/analysis` ve PWA proxy | Ulaşıyor; `INSUFFICIENT_DATA` / `WAIT`, plan ve lot yok. |
| Entry/SL/TP ve USC lot | Mevcut regresyonlar korunuyor; eksik gerçek veriyle canlı plan üretilmedi. |
| Çalışan yeni commit | RUNTIME_VERSION_UNVERIFIED; servisler yeniden başlatılmadı. |

Gerçek 9 Kasım seans kanıtı, tam `XAUUSDc` kimliği ve geçerli tarih aralığıyla elde edilmeden eksik candle kabulü açılmayacaktır. Güncel haftalık script çıktısı, resmî Exness çizelgesiyle karşılaştırma için yararlıdır; geçmiş tatil, DST, quote-only veya close-only durumunu tek başına doğrulamaz. İlk çalışan güvenilir manuel sürüm için tarihli sembol-spesifik kanıt, güvenli import/onay sözleşmesi ve yeni kodun izole canlı kabulü gerekir. En kısa zorunlu operatör adımı, Exness seçicisindeki `XAUUSDc` için 9 Kasım 2026 UTC çizelgesini bir defa dışa aktarıp sağlamaktır. MT5 scripti güncel haftalık çapraz kontrol için isteğe bağlıdır. Seçici hesap girişi gerektiriyorsa kullanıcı erişimi zorunludur.
