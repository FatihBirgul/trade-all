# P1 runtime devir notu

Tarih: 11 Kasım 2026, Europe/Istanbul.

| Durum | Sonuç | Kanıt / sınır |
|---|---|---|
| SOURCE_INTEGRATED | YES | Ana dal `f78b638 -> 753ed59` yerel fast-forward. |
| LOCAL_TESTS_PASSED | YES | Her iki çalışma ağacında izole Python 3.11 ve 3.13 kabulü; test raporuna bakınız. |
| RUNTIME_VERSION_VERIFIED | UNVERIFIED | Çalışan süreçte P1 kaynak kimliği, ortam değişkenleri ve yüklü NumPy/adapter sürümü teyit edilmedi. |
| LIVE_PWA_ACCEPTED | UNVERIFIED | PWA üzerinden yeni P1 alanları için uçtan uca canlı kabul yapılmadı. |

## Servislerin korunması

İlk listen-port sorgusunda dört port da görünmedi. Daha sonraki sorgularda servisler aşamalı olarak görünür oldu. Bu görev hiçbir servis başlatmadı, durdurmadı, yeniden başlatmadı veya ortamını değiştirmedi; dış süreçlerin başlangıcı bu entegrasyonun sonucu olarak sunulmaz.

| Port | Gözlenen PID | Listen zamanı (Europe/Istanbul) |
|---|---|---|
| 8005 MT5 bridge | 2840 | 11 Kasım 2026 15:27:49 |
| 8006 Forex API | 7532 | 11 Kasım 2026 15:30:29 |
| 8007 haber | 9724 | 11 Kasım 2026 15:30:54 |
| 5173 PWA | 10320 | 11 Kasım 2026 15:31:26 |

8006 süreci global Python 3.11 interpreter yolunu kullanıyor; komut satırında `forex.api` var ve `--reload` bayrağı yok. Interpreter yolu süreç içindeki gerçek NumPy sürümünü veya adapter yüklenmesini tek başına kanıtlamaz. Diskteki Git güncellemesi çalışan belleğin güncellendiğini kanıtlamaz. Bu nedenle PWA'nın P1 kullandığı iddia edilmez. Kaynak entegrasyonu için süreç restartı yapılmadı. İşletim sistemi gözlemi dışında canlı hesap/piyasa isteği yapılmadı.

## Sonraki güvenli adım

1. Önce mevcut P0 engelini çöz: Exness seçicisinden tam `XAUUSDc` sembolü için 9 Kasım 2026 UTC tarihli doğrulanabilir tarihsel seans kanıtı; effective date, timezone/DST, quote/trade ayrımı, maintenance ve holiday kapsamı. Güncel haftalık saatler geçmiş mum boşluklarını tek başına doğrulamaz. XAUUSD saatleri XAUUSDc için otomatik kullanılamaz.
2. Sonraki açıkça planlanmış servis sürüm geçişinden önce ayrı deployment ortamında NumPy 2.2.6 ve pinli kaynak erişimini doğrula. Global NumPy 2.4.6 P1 için uyumlu ilan edilmemeli. Bu görev canlı API ortamını değiştirmedi.
3. V2 `c80c97f...` Git nesnesi, chart SHA256, `V2_CHART_GIT_ROOT`, mevcut candlestick pin/config ve REAL_READONLY_DATA exact server/currency politikasını yeni süreçte ayrı doğrula. Bozuk kaynak/NumPy güvenli unavailable/503 üretmeli.
4. Yetkili bir sürüm geçişinden sonra runtime kaynak kimliğiyle P1'i kanıtla; ardından manuel API ve PWA'da betimleyici alanları, USC risk birimini ve `execution_permission=false` değerini doğrula. Eksik seans nedeniyle `INSUFFICIENT_DATA` devam ederse bunu beklenen güvenli ret olarak kaydet.

Bu devir notu servisleri şimdi yeniden başlatma talimatı değildir. Yeni aile, tarama, bildirim, emir veya hesap değişimi kapsam dışıdır. Mevcut P1 ve eski V3 geçmişi ile recovery ref korundu; V2 kirli dosyalarına dokunulmadı.
