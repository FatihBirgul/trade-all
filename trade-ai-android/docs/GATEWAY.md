# Mobil HTTPS gateway sınırı

Backend belgeleri 25 Ekim 2026 tarihinde trade-ai-v2 dalından salt okunur alındı.
Backend kullanıcı login/session API'si sunmuyor. Android uygulamasındaki mobil oturum,
backend owner bearer tokenı değildir. Gateway henüz geliştirilip dağıtılmadı.

## Hedef mimari

Android -> özel ağdaki HTTPS gateway -> sabit loopback backend /api/v2.
Backend owner tokenı yalnız gateway sunucusunun ortamında bulunur. Gateway gelen
mobil Authorization değerini backend'e aktarmamalı; doğruladıktan sonra server-side
owner tokenı eklemelidir. Hedef URL kullanıcı isteğinden üretilemez.

Gateway gereksinimleri:

- Mobil oturumu güvenilir kimlik sağlayıcı üzerinden doğrula (issuer, audience,
  imza, expiry, iptal). Her hesap için ayrı yetkilendirme yap.
- Yalnız izin verilen /api/v2 yollarını ve yöntemlerini aktar; gerçek para
  endpoint'i yoktur. /paper/events mobil istemciye açılmamalı.
- analyze ve watchlist gövdelerinde auto_paper=false zorunlu olsun.
- HTTPS, istek boyutu sınırı, zaman aşımı, oran sınırlaması ve gizli değerleri
  kaydetmeyen loglar uygula. Redirect veya açık proxy davranışına izin verme.
- Web cookie seçeneğinde HttpOnly/Secure/SameSite ve CSRF denetimi gerekir.
  Native mobil istemci ayrı kısa ömürlü oturum kullanır; SecureStore'da saklanır.
- Ağ erişimi özel cihaz ağıyla sınırlı olmalı. Backend loopback'te kalmalı.
- Canlı veri modu yalnız live yanıtları kabul eder; fixture yanıtları reddedilir.

## İdempotency

IntentJournal işlem gövdesini, hesabı/gateway kapsamını ve anahtarı ağdan önce
kalıcı adaptöre kaydeder. Zaman aşımı / 5xx / bozuk yanıt sonrası kayıt tutulur.
Uygulama yeniden başlatıldığında aynı gövde ve anahtar tekrar kullanılır.
GET orders/positions/transactions ile gerçek son durum doğrulanır. Pending,
filled veya closed olarak yeniden etiketlenmez.

Sanal emir oluşturma/kapatma/iptal arayüzü henüz açılmadı. Native SecureStore
adaptörü ve yeniden açılış simülasyonu Jest ile sınandı. Gerçek cihazda
kalıcılık, işlem uzlaştırma ve gateway entegrasyonu tamamlanmadan bu işlemler
açılmamalıdır.

## Bağlantı testi

Health HTTP 200 tek başına provider sağlığını kanıtlamaz. Uygulama
real_execution=false ve data_mode=live kontrol eder, provider_status ve storage
alanlarını gösterir. Hata halinde demo yanıtı döndürmez.

## Android 0.2.2 oturum yaşam döngüsü

Sağlık testi, adres ve mobil oturum kontrolü merkezi AppProvider içinde yapılır;
UI doğrudan doğrulanmış işareti koyamaz. Başarısız bağlantı testi CANLI kilidini
kapatır. 401/403 yanıtı DEMO moduna döndürür; tekrar sağlık testi gerekir.
Mobil oturumu silmek belleği anında temizler ve SecureStore silmesini sıraya alır.
Silme sırasında biten eski sağlık testi oturumu yeniden etkinleştiremez.
Kaydedilmiş oturum sonraki açılışta CANLI modunu kendiliğinden açmaz.

Analiz yanıtındaki risk_portfolio istenen AUTO/MANUAL hesabıyla eşleşmelidir.
Hesap hareketi yanıtları URL'deki hesap kapsamıyla uyuşmazsa reddedilir.
Bu kontroller sunucu yetkilendirmesinin yerine geçmez.
