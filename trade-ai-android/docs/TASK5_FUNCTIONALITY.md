# 0.4.0 işlevsel entegrasyon

Backend sözleşmesi ve algoritmaları değiştirilmedi. Referans: trade-ai/trade-ai-v2,
022e3e2173f2448de089945a41956517a643eb40. Android geliştirme dalı kullanılır; PR #1 birleştirilmez.

## Kullanılabilir

- BTCUSDT, ETHUSDT, SOLUSDT analiz başlatma ve MTF seçimi mevcut V2 API'yi kullanır.
- Detaydan aynı seçimlerle yeni analiz alınır; eski immutable kayıt değiştirilmez.
- Geçmişten iki aynı market/zaman dilimi/hesap/veri modu kaydı seçilerek karşılaştırılır.
- Snapshot mum grafiği analizin kendi kaydından alınır; yeni fiyatla değiştirilmez.
- Dört strateji durumu/gerekçesi, Wilder RSI14 ve mevcut RSI14 ayrı gösterilir.
- AUTO/MANUAL bakiye, rezerv, açık/kapanmış pozisyonlar, emirler, hareketler okunur.
- Performans seçili hesap için backend'in kapanan/kazanç/kayıp/belirsizlik/PnL verisidir.
- Pending outbox bildirimleri ilgili analiz kaydını açar; push teslimatı yapılmaz.
- Geçmiş/bildirim sayfaları oturum değişiminde sıfırlanır; aynı ID tekrarı çizilmez.
- Scanner yetkili oturumlarda market/zaman dilimi ekleme, izlemeyi kapatma/açma,
  duraklatma/devam ve tek tick destekler. İş kayıtlarından analize geçilir.
  V2 silme endpoint'i sunmadığından kapatma kaydı silmez; 10 kayıt sınırından düşürmez.
  1m scanner sözleşmesinde yoktur; seçenek yalnız gerçek WatchRequest enum'udur.
- Mobil uygulama arka planda otomatik tick çalıştırmaz. Scanner varsayılan durumu
  backend'de paused'dır; bağlanmak mevcut PC durumunu kendiliğinden değiştirmez.

## Kapalı

Paper create/cancel/close ve hesap risk pause/resume istemcisi, kalıcı IntentJournal
ve aynı anahtarla açık recovery altyapısı vardır. AppProvider paperWritesEnabled
bayrağını açmaz. APK'da bu yazma butonları yoktur. Gateway'de ayrı paper:write kapsamı
VE varsayılanı kapalı sunucu bayrağı gerekir; üretim CLI bayrağı açmaz.
Gerçek telefon kalıcılığı/idempotency/hesap izolasyonu doğrulanmadan açılmayacaktır.
Risk limitlerini değiştiren endpoint mevcut sözleşmede yoktur; uydurulmaz.
Sharpe/equity curve/drawdown/backtest ve gerçek push altyapısı yoktur.

## Doğrulama sınırı

Yerel kontrollü testler gerçek V2 uygulamasını ve geçici DB'leri kullanır. Fixture
ve kontrollü sağlayıcı testleri gerçek piyasa erişimi değildir. Kullanıcının Windows
PC'si/telefonu, gerçek Tailscale HTTPS bağlantısı ve SecureStore güncelleme kalıcılığı
bu ortamdan doğrulanamaz. Tam çevrimiçi Expo Doctor izinsiz çalıştırılmaz.

Scanner tick öncesi gateway PC'deki enabled auto_paper watch kayıtlarını denetler ve
varsa 409 ile reddeder. PC üzerinde doğrudan backend'e paralel watch değişiklikleri
mobil gateway kilidinin dışındadır; mevcut sözleşme atomik 'tick without orders'
seçeneği içermez. Gerçek cihaz doğrulamasında PC otomatik emir ayarları kapalı
olmalıdır. Sanal emir otomasyonu bu sürümün doğrulanmış özelliği değildir.

Sanal işlem günlüğü aynı süreçte birden fazla servis örneğinden eşzamanlı gönderimi
engeller; gövdeyi ilk asenkron adımdan önce kopyalar. Miktar yalnız pozitif ondalık
metin olarak kabul edilir; sayı/virgül/bilimsel gösterim veya fazladan alan sessizce
atılmaz. Bu sınır ve farklı örneklerden çift gönderim 73 Android testi içinde
doğrulandı. Yerel HTTPS zinciri bu ek kontrollerden sonra yeniden başarılı oldu.
