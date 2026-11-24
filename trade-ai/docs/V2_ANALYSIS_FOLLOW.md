# Analiz takip asistanı — Görev 6

Bu ek, mevcut V2 analiz motorunu ve immutable snapshot kayıtlarını kullanır.
Analiz algoritması, karar kuralları ve paper ledger değiştirilmez.

## Çalıştırma

PC kaynakları kendiliğinden güncellenmez. Backend `codex/v2-mobile-quotes-20261026`,
Gateway `codex/gateway-continuity-20261026` dalları kullanılmalıdır. Main/PR merge
gerekmez. Servisleri normal kapatın, mevcut SQLite dosyalarını tutarlı yedekleyin;
mevcut DB yollarını, mode, token ve Windows kullanıcı ACL'lerini koruyun.
Gateway için mevcut venv Python'u ile `-m pip install -e .` çalıştırın.

Backend klasöründe mevcut komutunuza yalnız `--tracking` ekleyin:

```powershell
.\.venv\Scripts\python.exe start_v2.py --database ..\local_data\v2-live.sqlite --mode live --tracking
```

DB yolu örnektir; kendi mevcut dosyanızı kullanın. Token mevcut güvenli yerel
prompt/yöntemle süreç ortamına verilir; komut satırına veya telefona yazılmaz.
Script execution policy değiştirmek gerekmez. Alternatif ASGI fabrika kurulumu
`V2_TRACKING_WORKER=1` ile lifespan başlangıç/kapanışına bağlanabilir.
İşçi varsayılan olarak kapalıdır. `--scanner` açmak takip için gerekli değildir;
takipçi scanner'ın paper poll/emir yürütme yolunu çağırmaz.

Gateway'i aynı loopback hedefi ve mevcut özel Tailscale Serve HTTPS origin'iyle
yeniden başlatın. Funnel, firewall veya modem ayarı değişmez. Android oturumunda
açık `scanner:write` yetkisi ve analizin hesabı gerekir. Mevcut yetki otomatik
genişletilmez; gerekiyorsa yalnız PC'de yeni yerel kod/grant üretin.

## API ve kalıcılık

- `GET /api/v2/analysis-tracking`: en fazla 100 kayıt; Gateway hesapları filtreler.
- `POST /api/v2/analysis-tracking`, gövde `analysis_id`: aynı origin kayıt için
  deterministik takip kimliği; kayıp yanıt sonrası aynı gövde çift takip yaratmaz.
- `GET /api/v2/analysis-tracking/{tracking_id}`: kayıt ve gerçek işçi durumu.
- `POST /api/v2/analysis-tracking/{tracking_id}`, gövde `enabled`: idempotent
  durdur/devam et. Duraklamış aynı kaydı tekrar başlatmak için bu endpoint kullanılır.

Android sonuç ekranındaki takip kartı durum okuma, başlatma, durdurma/devam ve son
immutable analizi açmayı sağlar. Belirsiz yazma cevabından sonra önce GET ile
uzlaştırılır; otomatik yeni işlem/anahtar üretilmez. Eski Gateway yetenek bilgisi
vermiyorsa yeni özellik açılmaz; backend güncel değilse açıklayıcı hata gösterilir.

`analysis_tracking` ve `analysis_tracking_state` ek tabloları mevcut V2 DB sahibi/
mode doğrulamasından sonra açılır. Yedekleme script'i bu tabloların JSON hashlerini
de kontrol eder; eski DB'lerde tabloların bulunması zorunlu değildir. Yedek/restore
mevcut dosyanın üstüne yazmaz. Restart eski fiyatları geçmişe dönük analiz etmez.

## Kaynak ve güvenlik sınırları

En fazla altı aktif takip ve toplam 100 kayıt; aynı market/zaman dilimi/hesap için
tek aktif takip. Devam ettirme de aynı sınırı denetler. İşçi dakikada en fazla iki
analiz seçer ve scanner ile aynı 120 saniyelik lease'i paylaşır. Yeni kapanmış mum
sınırı değerlendirilir; kaynak yoksa 1/2/4/8/15 dakika bekleme uygulanır.
Geçici sağlayıcı kesintisi tek başına piyasa koşulu değişmiş sayılmaz.

Her analiz `auto_paper=false` ve origin hesabıyla çağrılır. Hesap bakiyesi, emir,
pozisyon veya mevcut analiz snapshot'ı değiştirilmez. Stop/revoke/oturum ve hesap
kontrolleri Gateway'de korunur; devam eden takip durdurulursa commit guard eski
analizin kaydedilmesini engeller. Worker kapalıysa kayıt bulunması çalışıyor
anlamına gelmez; API `worker_running=false` döndürür.

Yalnız güncel ve quality doğrulanmış kararda yön/gerekçe, rejim, router ve dört
stratejinin durum/gerekçe/yön değişimi outbox'a eklenir. Fiyat/RSI'daki her küçük
değişim bildirim değildir. Outbox ve son geçerli koşul hash'i aynı transaction'da
güncellenir. Eksik/bayat/gelecek zamanlı veya süresi dolmuş veri güvenli WAIT'tir.

Outbox `pending`, teslim servisi `not_configured` kalır. Telefon push altyapısı
yoktur. PC kapalıyken analiz, uygulama kapalıyken push teslimi garanti edilmez.
Immutable geçmiş büyür; periyodik yedek/disk alanı takibi gerekir; otomatik silme
ve doğrulanmamış performans istatistiği yoktur.

## Doğrulama sınırı

Geçici DB ve kontrollü sağlayıcıyla analiz→takip→yeni immutable analiz→mumlar→
pending outbox→stop/restart, sınırlar, hash/yedek, stale WAIT ve hesap izolasyonu
otomatik test edilir. Android üretim API modülleri doğrulanan yerel TLS üzerinden
Gateway ve gerçek V2 uygulamasına bağlanır. Bu testler canlı borsa veya fiziksel
telefon/Windows testi değildir. Yeni sürüm kullanıcı cihazında doğrulanmalıdır.
