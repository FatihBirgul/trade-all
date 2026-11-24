# Trade AI 2.0 — Kalıcı ürün hafızası

Gelecekteki geliştirme görevleri bu dosyayı ve güncel GitHub HEAD'lerini kontrol
ederek başlamalıdır. Önceki kararlar yeni fikir olarak tekrar sunulmaz.

## Kesin kararlar

- Mevcut deterministik V2 engine ve immutable karar/snapshot kayıtları korunur.
- DEMO/CANLI ile BASİT/PRO birbirinden bağımsızdır. Basit varsayılandır; görünüm
  seçimi analiz girdilerini, algoritmayı veya kararı değiştirmez.
- Analiz takip asistanı daha önceden kararlaştırılmış ürün hedefidir. WAIT sonrası
  değişen gerçek koşulları izler; aynı durum için tekrar tekrar bildirim üretmez.
- Önce güvenilir çalışan özellikler; premium görünüm gerçek veriye dayanır.
- Gerçek para/emir/transfer, owner backend tokenının mobilde veya logda bulunması,
  Funnel/public port ve izinsiz main/merge/force push yasaktır. Paper yazma bayrakları
  cihaz kalıcılığı/idempotency doğrulaması yapılmadan açılmaz.
- Çevrimiçi Expo Doctor için ayrıca izin gerekir; ağsız kontroller kullanılabilir.

## 0.4.0 — Kullanıcının gerçek cihaz doğrulamaları

26 Ekim 2026 tarihli kullanıcı beyanı; bunlar otomatik test sonucu değildir:
Windows Python 3.11 backend + gateway + özel Tailscale Serve ve Android eşleştirme
çalıştı. BTC/ETH analizi, göstergeler/dört strateji, mumlar, immutable geçmiş,
AUTO/MANUAL okumaları, performans, scanner grant/tick/jobs/pause cihazda denendi.
Scanner completed ve iki iş kaydı oluşsa da bazı yanıtlarda Android belirsizlik
uyarısı verdi. Paper create/cancel/close mobilde henüz etkin veya doğrulanmış değil.

## Görev 6 checkpoint sırası

1. Güvenli oturum yenileme: access 24 saat, ilk yerel eşleştirmede cihaza bağlı
   mutlak 30 günlük yenileme ailesi; hash-only sunucu kaydı, rotasyon, exact replay
   receipt, farklı reuse durumunda aile iptali. SecureStore'da gönderim öncesi
   successor journal; unknown ağ sonucunda aynı istek. Eski bearer tek başına yeni
   kalıcı yetki alamaz. İlk kez güncel gateway ile yeniden eşleştirme gerekir.
2. Kısa sonuç → ayrıntılı analiz; makine kodlarına anlaşılır Türkçe açıklama.
3. Sınırlandırılmış gerçek piyasa fiyatları ve güncelliği gösteren ana sayfa.
4. Kalıcı Basit/Pro; aynı motor/girdiler, farklı kontrol yoğunluğu.
5. Scanner belirsiz sonucun kök nedeni ve güvenli uzlaştırma.
6. Takip asistanı: sınırlı scanner işçisi, anlamlı değişim/outbox dedup/stop.

Checkpoint 1 kodu yerel kontrollü testlerle doğrulanır; yenileme özelliğinin
kullanıcının telefonunda veya Windows bilgisayarında test edildiği iddia edilmez.
PC açık ve servisler erişilebilir olmadığında yenileme/analiz garantisi yoktur.
Yenileme 30 günü uzatmaz; iptal/absolute expiry sonrası yerel pairing gerekir.
Yeni kodlar PC'de kendiliğinden güncellenmez; ayrıca güncelleme/restart gerekir.

## Sonraki checkpoint'ler

- Paper oluştur/iptal/kapat gerçek cihaz kalıcılık ve recovery testleri.
- AUTO/MANUAL paper otomasyonu; hesaplar ve idempotency kesinlikle ayrıdır.
- Gerçek sınırlı arka plan scanner; otomatik emir ayrı kapalı güvenlik bayrağı.
- Performans geçmişi/sanal portföy grafikleri yalnız doğrulanabilir verilerle.
- Güvenilir teslim altyapısı kurulmadan pending outbox, push diye sunulmaz.
- Forward test/backtest; indikatör eklemek performans kanıtı değildir.
- ADX, Supertrend, Order Blocks ve planlanan yöntemler; mevcut hesaplar değiştirilmez.
- Ek veri kaynakları ve doğrulanmış provider/calendar sonrası Forex/XAUUSD.
- Yedekleme SQLite tutarlı snapshot ile; production DB silme/reset yoktur.

### Tamamlanan checkpoint'ler

- Oturum yenileme: Android 4ce21a6 / gateway aa414e0. Yerel 79 Jest, 39 pytest;
  sertifikalı yerel HTTPS lost-ack/recovery zinciri başarılı. Yeni yenileme özelliği
  gerçek cihazda henüz doğrulanmadı; yukarıdaki cihaz beyanı eski özellikler içindir.
- Sonuç → detay ayrımı: aynı immutable analysis_id; kısa Türkçe BEKLE/gerekçe/risk
  özeti ve ayrı teknik ekran. 80 Jest, TypeScript ve ESLint geçti. Yeni ekranın
  fiziksel telefon doğrulaması bekler.
- Piyasa checkpoint'i: üç market için read-only /api/v2/quotes; 30 saniye ticker,
  beş dakika kapalı 1H grafik önbelleği, bayat/veri yok ayrımı ve yalnız odaktaki
  aktif ana sayfada kontrollü yenileme. Motor değişmedi; eski tüm V2 paths/schemas
  eşitliği doğrulandı. Yerel 82 Jest, 40 gateway pytest, 211 mevcut offline V2
  regresyonu + iki yeni quote testi geçti. Yeni fiyatlar fiziksel cihazda henüz
  doğrulanmadı. Backend geliştirme dalına ayrı güncelleme gerekir.
- Basit/Pro checkpoint'i: ilk kurulum Basit; tercih SecureStore'da korunur ve
  DEMO/CANLI, hesap veya immutable analiz içeriğini değiştirmez. Pro tarayıcı ve
  geçmiş kontrollerini açar; Basit portföy özetini ve kısa sonuçları gösterir.
  Yerel 84 Jest; TypeScript/ESLint başarılı. Piyasa backend CI düzeltmesi sonrası
  Python 3.11 ve 3.12'de 211 eski regresyon + iki quote testi geçti.
- Scanner recovery checkpoint'i: genel gateway 10s/istemci 15s süreleri iki
  analizin cevabını kesebilir. Bu yol kontrollü thread/TLS senaryosunda yeniden
  üretildi; kullanıcının kesin HTTP hata cevabı bu ortamdan görülmedi. Tick için
  gateway 45s/Android 50s ayrı sınır; diğer istekler kısa kalır. Native kalıcı
  scanner intent, tek POST ve restart sonrası salt okunur state/jobs uzlaştırması
  eklendi. Belirsiz sonuçta yeni tick otomatik gönderilmez. Sunucu kayıtlarıyla
  gözlenen tamamlanma, kesin bir request-id onayı diye sunulmaz (V2 tick explicit
  idempotency anahtarı almaz). Gerçek cihazda yeni recovery doğrulaması bekler.

## Görev 6 sürüm checkpoint'i: 0.5.0 / versionCode 6

İlk beş aşama GitHub'a kaydedildi: süreli/rotasyonlu cihaz yenileme,
kısa sonuç-teknik detay ayrımı, salt okunur gerçek fiyat sözleşmesi ve bayatlık,
kalıcı Basit/Pro, scanner timeout ve kalıcı salt okunur recovery. Son yerel
checkpoint: 87 Jest, TypeScript/ESLint, 41 gateway pytest; backend 211 mevcut
çevrimdışı regresyon ve iki yeni quote testi. Backend Python 3.11/3.12 CI geçti.
Tam çevrimiçi Expo Doctor çalıştırılmadı. Main dalları ve PR merge edilmedi.

Takip asistanı üzerinde yerel kod ve temel kontrollü testler başlatıldı; çalışma
ortamı erişilemez olduğu için son değişiklikler/testler GitHub'a aktarılamadı.
Bu özellik 0.5.0 kaynaklarında ve APK'sında AKTİF DEĞİLDİR. Takip/push garantisi
verilmez. Sonraki oturum erişim gelirse yerel uncommitted çalışmayı incelemeli,
yoksa bu sürümden güvenli ayrı checkpoint olarak devam etmelidir.

Gerçek cihaz beyanı yalnız 0.4.0 için yukarıdadır. Yeni yenileme/fiyat/arayüz/
scanner recovery için gerçek telefon testi bekler. PC servisleri otomatik güncellenmez.
Gateway dalı: codex/gateway-continuity-20261026. Backend dalı:
codex/v2-mobile-quotes-20261026. Bu dallar gözden geçirilip PC'de bilinçli
uygulanmalı; mevcut DB/env/token korunmalı, servisler nazikçe durdurulmalı ve
yedeklenmelidir. Sonrasında yeniden başlatıp bir kez yeni yerel kodla eşleştirin
(scanner gerekiyorsa aynı açık grant korunarak). Bundan sonra yenileme 30 günlük
mutlak aile süresi içinde fiziksel PC kodu gerektirmez; PC ve özel ağ erişilebilir
olmalıdır. Süre sonu/iptal sonrası yerel pairing gerekir. Execution policy,
firewall veya Tailscale Funnel değişikliği gerekmiyor.

## 27 Ekim 2026 — Takip asistanı devam checkpoint'i (0.5.1 / 7)

Önceki 0.5.0 / ba8cd4d APK ve ilk beş aşama korunmuştur. GitHub HEAD kontrolü
Android ba8cd4d, Gateway fb589b1, backend 7d83bb7 ile aynıydı; PR'lar açık kaldı.
Önceki kesintide kalan yerel takip kaynakları bulundu ve değişmeden yedeklendi.
Yukarıdaki “takip AKTİF DEĞİLDİR” ifadesi 0.5.0 için geçerlidir.

Bu checkpoint analiz takip API'sini, varsayılan kapalı --tracking işçisini,
Gateway hesap/scope preflight'ını ve Android sonuç ekranındaki takip kartını ekler.
Aynı origin POST'u deterministik kimlikle idempotenttir. Duraklat/devam da aynı
altı aktif takip sınırını denetler. Toplam 100 kayıt, en çok iki analiz/dakika,
scanner ile ortak lease ve kesintide 1/2/4/8/15 dakika bekleme uygulanır.
Aynı doğrulanmış koşula dönüş sadece kaynak kesildi diye yeni bildirim üretmez.
Sadece yeni geçerli koşul immutable outbox'a atomik kaydedilir; push teslim yoktur.
Orijinal analiz ve hesap ayrımı korunur; auto_paper=false sabittir. Paper yazma
bayrakları yine kapalıdır. Yeni takip kartı son immutable analizi açar ve işçinin
kapalı olduğu durumu dürüstçe gösterir. Eski Gateway yetenek bilgisi vermiyorsa
bu yeni özellik açılmaz; güncel olmayan backend anlaşılır hata verir.

Windows güncelleme, yedek ve --tracking komutu backend docs/V2_ANALYSIS_FOLLOW.md
belgesindedir. Backend özel token'ı PC'de kalır. Servisler otomatik güncellenmez;
script execution policy, firewall veya Tailscale paylaşım sınırları değiştirilmez.
Yeni özellikler kontrollü test ortamında doğrulanır; gerçek telefon/Windows PC
üzerinde yenileme, takip, güncelleme ve açılış doğrulaması kullanıcıyı bekler.
0.4.0 için kullanıcının beyan ettiği testler yeni sürüm testleri sayılmaz.

Bu devam checkpoint'inin yerel sonuçları: 90 Jest / 23 suite, TypeScript, ESLint,
17 ağsız SDK kontrolü ve Android export; backend 219 offline unittest + iki
quote pytest; Gateway 42 pytest (sekiz gerçek V2/geçici DB entegrasyonu dahil)
geçti. Doğrulanan yerel TLS zinciri üretim Android API istemcisini kullanır.
Özel backend bulunmayan Gateway CI'ında sekiz entegrasyon testi SKIP olur.
Online Expo Doctor izinsiz çalıştırılmadı. Kaynak secret-pattern kontrolü geçti.



## 27 Ekim 2026 — Görev 7: premium Android 0.6.0 / 8

Görev 6 GitHub kaynakları başlangıçta doğrulandı: Android c30e596, Gateway
19038bd, backend 6b545e7. Üç PR #1 açık kaldı. Görev 6 teslim raporundaki
son backend sayısı 220 offline unittest + iki quote pytest'tır.

Yeni dal: codex/task7-premium-mobile-20261027. Main ve Görev 6 dalları korunur.
Backend/Gateway sözleşmesi, oturum yenileme, scanner recovery ve takip asistanı
API/state kaynakları değişmedi (15 korunan Android blob SHA'sı aynı).
Windows servislerine veya veritabanlarına müdahale edilmedi.

Kaynak checkpoint'leri:
1. d6692b4 — Tasarım token'ları, CTA/ikincil/metin aksiyonu ayrımı, alt gezinme,
   gerçek fiyat ve ayrı AUTO/MANUAL özetleriyle yeni ana sayfa. 90 Jest.
2. 9c62cfa — Immutable snapshot grafiği, pan/pinch, eksen/OHLC, isteğe bağlı
   yükleme; Pro EMA20/50, snapshot başlangıcından gerçek hacimli VWAP,
   güvenli seviyeler. 96 Jest.
3. 53d7256 — Ekran başlıkları ve son düzenler, 0.6.0 / versionCode 8. 98 Jest.
4. 92a0bfb — Büyük yazıda okunabilir eksen, native gesture callback testi ve
   tekrarlanabilir export/Chromium kontrol script'i. 99 Jest / 25 suite.

Tüm kaynak checkpoint'leri Android frontend CI ile doğrulandı. 17 ağsız SDK
kontrolü, TypeScript/ESLint ve Android export geçti. Son APK kaynak checkpoint'i
92a0bfb; CI: https://github.com/FatihBirgul/trade-ai-android/actions/runs/40465585289 .
Önceki 0.5.1 APK değiştirilmez. Son teslim/CI ve görsel kanıt için
`docs/TASK7_PREMIUM_MOBILE.md` okunmalıdır.

Grafik kayıtlı analizdir; canlı mum grafiği değildir. EMA görsel hesapları yalnız
snapshot geçmişindendir; motorun uzun geçmiş hesabına eşitlik iddia edilmez.
VWAP seans VWAP'ı değildir; ilk kayıtlı mumdan başlar. Bunlar analiz girdisini ve
sonucunu değiştirmez. Basit/Pro aynı immutable kaydı kullanır. Veri olmayan yerde
fiyat/performans serisi üretilmez; paper-write ve gerçek para kapalıdır.

Yedi web görsel senaryosu kontrollü fixture'larla geçti; gerçek backend veya
telefon testi sayılmaz. Gerçek Android güncelleme, fontScale/TalkBack,
pinch/scroll akıcılığı, eski cihaz performansı, özel ağ ve Görev 6 yenileme/
scanner/takip regresyonları kullanıcı cihazında bekler. PC uzakta diye kodlama
ve CI durdurulmadı; PC kurulumu veya hizmet değişikliği yapılmadı.

Görev 7 son APK CI run 40465585289 başarılıdır. Artifact 12717780072;
0.6.0 / 8, arm64-v8a; kaynak 92a0bfb. APK SHA-256:
21d7d4f0f89b64f402715b2c7fdf7bebd84d172b1942a1022dc59a968819b48e.
CI v2 imza/embedded bundle ve bağımsız indirme hash/ZIP CRC kontrolleri geçti;
sertifika önceki 0.5.1 ile aynı. Yeni dosya ayrı Trade-AI-0.6.0-test.apk olarak
korundu; eski APK silinmedi/değiştirilmedi. Gerçek telefon testi yine bekler.


## 27 Ekim 2026 — Görev 8: Android 0.7.0 / 9

Başlangıç GitHub HEAD'leri doğrulandı: Android eba362b (Görev 7), Gateway
19038bd ve backend 6b545e7. Görev 6/7 raporları ve backend takip kılavuzu okundu.
Yeni dal codex/task8-native-reliability-20261027, doğrudan eba362b'den türetildi.
PR #1/#2, main, önceki geliştirme dalları ve APK dosyaları korunur.

Checkpoint'ler:
1. f676ad1 — Native ikon geometri/font bariyeri ve kaydırılmayan safe-area çerçevesi.
2. 8a499da — Kısa Basit sonuç; DEMO pasif takip kartı kaldırıldı; teknik notlar açılır.
3. 901a6ac — Tek takip yönetim ekranı, hesap kontrolü, salt okunur koşul/outbox geçmişi.
4. 6fdd644 — Kontrollü kayıtlı bağlantı doğrulaması, scope'lu recovery, aynı GET uçuşu
   birleştirme, kompakt gerçek piyasa satırları. Açılışta otomatik CANLI yoktur.
5. 687d17e — Geçmiş filtreleri/sıralama/karşılaştırma; bounded paging; scanner UX.
6. 07b4de8 — Sayısal/hesap doğrulaması, miktarı açık ambiguous pozisyonların görünmesi,
   yalnız gerçek defterden sınırlı PnL penceresi; 0.7.0 / versionCode 9.
Son QA: e5f82df — native tab iç boşluğu dahil ölçüm, kısa Basit takip, pinned analysis,
   font bariyeri ve startup eşzamanlılık testleri; ekranda en çok 20 geçmiş satırı.
Önceki navigation QA: 2bf00177b1d08968caaa6279d06d23f2c8314743 — Basic/Pro sonrası
   geri hedefi görünür Ana Sayfa; **123 Jest / 33 suite** ve 13 kontrollü web senaryosu.

Başlangıçtaki fontun 0.6.0 APK içinde bulunduğu SHA-256 ile kanıtlandı; eksik font
varsayımı doğrulanmadı. Geometri ve ScrollView içinde kaybolan safe inset düzeltildi.
Yeni release hattı gerçek APK'daki Ionicons bytes/embedded bundle/CRC'yi denetler.
Bu audit veya web görünümü gerçek Android telefon testi sayılmaz; yeni APK için
ikon/status bar, fontScale, gesture/navigation bar ve FPS testleri kullanıcıyı bekler.

Gateway 42 pytest (sekiz gerçek V2 entegrasyonu dahil), backend 220 offline unittest
ve iki quote testi geçti. Hedefli follow, scanner/recovery, risk/product testleri de
geçti. Üretim Android API → CA doğrulanan yerel TLS → Gateway → gerçek V2 zinciri
kontrollü sentetik sağlayıcı ve geçici DB ile geçti; canlı piyasa/telefon testi değil.
TypeScript/ESLint, 17 ağsız SDK kontrolü ve Android/Web export doğrulandı.

Gateway ve backend kaynak/API/DB şeması değiştirilmedi. Yenileme 24h/absolute30g,
rotasyon/revocation/journal, scanner tek POST/recovery ve takip dedup/sınırları korunur.
Sanal/gerçek emir yazmaları kapalı; AUTO otomatik emir açılmaz. Pending outbox push
değildir. Windows servisleri veya özel ağ ayarları değiştirilmedi.

Sınırlar: geçmiş en çok 400 yüklenen kayıt, ekranda 20; takip en çok100 kayıt,
outbox lookup en son100 bildirim; PnL grafiği son20 gerçek defter işleminin penceresi,
tüm hesap equity geçmişi değildir. Ücretsiz gerçek fiyat yerine fixture konmaz.
Ayrıntılı son teslim, imza/hash, native test sınırı ve güvenli PC geçişi için
`docs/TASK8_ANDROID_RELIABILITY.md` okunmalıdır. Yeni sürüm için gerçek cihaz
onayı alınmadan native görünüm/akıcılık tamamlandı iddiası yapılmaz.

Son kısa sonuç QA: 5b9421d46564de3a5351820bf213f267f7284080. Gerekçeler seçilmiş
strateji ve Router üzerinden seçilir; diğer reddedilmiş kurulumların gerekçeleri
ana karar gibi gösterilmez. Motor/girdiler/immutable kayıt değişmez. Son kaynak
**124 Jest / 33 suite**, TypeScript/ESLint ve 13 kontrollü web senaryosundan geçti.
APK için son uygulama kaynağı budur; sonraki dokümantasyon commit'leri davranışı
ve APK kaynağını değiştirmez. Önceki 2bf0017 ve e5f82df QA referansları korunur.

### Görev 8 — doğrulanmış 0.7.0 APK teslimi

- Son uygulama kaynağı `5b9421d46564de3a5351820bf213f267f7284080`.
- Android CI [40518709816](https://github.com/FatihBirgul/trade-ai-android/actions/runs/40518709816)
  başarılı; artifact `12742970172`. Manifest: 0.7.0 / versionCode 9.
- APK SHA-256 `fc8b0d0d6303461c001850375c7a51ac7da45b48b6d11be48efab77635c4b8d1`;
  sertifika 0.6.0 ile aynı. Font/embedded JS/CRC ve indirilen artifact digest doğrulandı.
- Ayrı [taslak PR #3](https://github.com/FatihBirgul/trade-ai-android/pull/3);
  kaynak değişiklikleri altı checkpoint'te kaydedildi. Önceki PR/APK/main korundu.
- Ayrıntılı APK bağlantısı, tüm checkpoint SHA'ları, test sonuçları, PC geçişi ve
  gerçek cihazda bekleyen kontroller: [Görev 8 teslim raporu](TASK8_ANDROID_RELIABILITY.md).

## 28 Ekim 2026 — Görev 9: Android 0.7.1 / 10

Kullanıcının 0.7.0 DEMO telefon gözlemleri: açılış/ikonlar/başlıklar/ekranlar,
Basit-Pro ve kaydırma olumlu. Bu oturumda görüntüler ekli değildi; gözlemler
kullanıcı beyanıdır. Bu cihaz testi canlı PC/Gateway/piyasa/worker kanıtı değildir.

Yalnız Android geliştirme dalı `gpt/task9-android-reliability-20261028`, doğrulanan
Task8 b2f829b'den oluşturuldu. İki geliştirici sınırı: Backend/Gateway commit/API
sözleşmesi ve LM Studio'nun devam eden dalı değiştirilmez/temel alınmaz.

- cdc4a7e: kompakt bağlantı kanıtı ve Ayarlar ayrıntısı; bilinmeyen NETWORK nedenini
  telefon ağı diye teşhis etmeme; LOCAL_PAIR_REQUIRED yeniden pairing durumu.
- cb14284: DEMO/gerçek/başarılı boş/başarısız veri ayrımı, yerel portföy etiketi,
  eksik piyasa verisinde rejim/MTF/strateji sunumunu engelleme; zamanlar değişmez.
- 5fa7e3b: DEMO scanner yerel kontrolleri, güncel okuma ve çift dokunma yazma kilidi,
  resume/worker ayrımı, 0.7.1 / versionCode 10. Son uygulama/APK kaynağı budur.

135 Jest / 35 suite, TypeScript/ESLint, 17 ağsız SDK kontrolü, Android CI export
ve 19 kontrollü web senaryosu geçti. Son kaynak frontend CI 40714922860 başarılı.
APK işi 40714925416; artifact/imza/hash sonuçları Task9 teslim raporunda tutulur.
16 korunan blob (ikon/nav, API/schema, renewal, journal, paper/safety, portföy
hesapları dahil) Task8 ile aynı. Native telefon/emülatör testi burada yapılmadı.

Kesin telefon interneti OS seviyesinde ölçülmez; genel erişim hatası için neden
belirsizliği sunulur. Özel PC ağı ve uzun süreli renewal cihaz doğrulaması bekler.
Eski APK'lar/main/PR'lar korunur; finansal yazma ve AUTO auto_paper kapalı kalır.
Task9 için PC kaynak/servis/DB güncellemesi gerekmiyor. Koordinasyon ve cihaz test
matrisi: [Görev 9 teslim raporu](TASK9_ANDROID_RELIABILITY.md).

Görev 9 APK sonucu: CI 40714925416 başarılı, artifact 12828109368, 0.7.1 / 10.
APK SHA-256 `6302816d479c03f6269e89acc31f3009a86331266e4b6b786002c528c749b9f0`. İmza 0.7.0 ile aynı; indirilen
ZIP/BUILD_INFO/hash/CRC/font/manifest denetimi geçti. Yeni APK ayrı dosyadır;
gerçek cihaz doğrulaması bölüm 8'de bekleyen iş olarak kalır.
