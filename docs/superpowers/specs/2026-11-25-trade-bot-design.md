# Trade Bot — Tasarım (2026-11-25)

## 1. Amaç ve neden

Exness cent hesabında 7/24 kendi başına çalışan bir trade botu. Bot sunucuda bir çalışan gibi çalışır:
sürekli tarar, analiz eder, haberleri takip eder, işleme girer, stopu kademeli yönetir, işlemden çıkar.
Kullanıcı Android uygulamasından **müdahale etmeden denetler**. İsterse anında işlem kapatır,
SL/TP değiştirir, elle işlem açar, sembol ve ayar seçer.

Başarı tanımı (kullanıcının sözleri): önce sistem kendini kanıtlasın, sonra yavaş yavaş ama uzun sürmeden
düzenli ve yüksek gelir getirsin.

Bu fikir daha önce 3 kez denendi ve bitmedi. Repo'daki V2/V5/V9 sürümleri analizi mükemmelleştirdi
ama hiçbiri emir göndermedi. **Bu projenin bir numaralı kuralı: 1. haftanın sonunda uçtan uca çalışan
bot** (tara → sinyal → emir → stop yönetimi → uygulamada gör). Diğer her şey bunun üstüne eklenir.

## 2. Hedefler / hedef olmayanlar / anti-hedefler

**Hedefler**
- Exness resmi Trading API'si (REST + WebSocket) ile gerçek cent hesapta otomatik işlem.
- Hesaptaki tüm Forex ve metal enstrümanları + BTC ve ETH taranır. Hafta sonu kripto çalışır.
- Repo'daki tüm strateji ve indikatörler (V9 `unified_forex` ve içindeki V2/V5/Day Trader kodu) kullanılır.
  Her strateji bağımsız sinyal üretir. Hepsinin aynı anda onay vermesi beklenmez (bkz. §6.2 sinyal birleştirme).
- **Strateji ve indikatör kütüphaneleri yarım kalmış durumda.** Bu proje kapsamında tamamlanır, gerekirse
  yükseltilir. Daha iyi stratejiler bulunursa eklenir. Bu iş, bot canlıda çalışmaya başladıktan sonra
  canlı verilerle yönlendirilerek yapılır (§6.2, §10).
- Kademeli stop: önce girişe (breakeven), sonra kâra doğru.
- Yüksek etkili haberden 30 dk önce ve 30 dk sonra ilgili para birimlerinde yeni işlem yok.
- Android: canlı izleme, bildirimler, acil durdur/devam, ayarlar, elle işlem aç/kapat, SL/TP düzenleme,
  sembol seçimi, günlük/haftalık/aylık kâr-zarar.

**Hedef olmayanlar (bu 30 günde)**
- Geçmiş veriye aşırı uydurulmuş (overfit) parametre optimizasyonu. Ayarlar canlı sonuçlarla ve
  açık eşiklerle yapılır, geçmiş veride en iyi görünen sayıların peşine düşülmez.
- MT5 entegrasyonu, web arayüzü, kripto V2 analiz ürünü.
- Hisse senedi ve endeks. API bunları desteklemiyor.

**Anti-hedefler (çalışsa bile başarısızlık sayılır)**
- Stopsuz işlem. Her pozisyonun SL'i **broker tarafında** kayıtlı olmalı, gizli stop yok.
- Martingale, grid, zarardaki pozisyona ekleme.
- Sessiz arıza. Bot durduysa, bağlantı koptuysa veya emir reddedildiyse kullanıcı bunu öğrenmeli.
- Aynı sinyalden çift emir (yeniden başlatma, ağ hatası veya tekrar deneme sonrası).
- Yine yalnızca analiz yapan bir sistem.

## 3. Kısıtlar

- **Hesap:** Exness platform hesabı, cent, başlangıç ~30 USD (3000 USC). KYC tamam, API anahtarı Trading Full access.
- **API:**
  - İmzalama Ed25519 ile. `EXN-DATA` (base64url payload) ve `EXN-SIGN` başlıkları. Değişiklik yapan isteklerde idempotency key zorunlu.
  - Hesaba özel host, Gateway DNS'ten bulunur (access point).
  - Emirler asenkron çalışır. ACK sadece "kabul edildi" demektir, sonuç WebSocket `transaction_event` ile ya da operasyon durumu sorgulanarak öğrenilir.
  - Rate limit ve geçmiş veri sınırları sabit değildir, `GET /v1/configuration/accounts/{id}/limits` ile okunur.
  - Hisse senedi ve endeks yok.
  - SL/TP değiştirme, kısmi kapama, enstrüman özellikleri ve mum zaman dilimlerinin kesin şemaları API Reference'tan doğrulanacak.
- **Sunucu:** Contabo, Ubuntu 24.04, Python 3.12. 7/24 çalışır, systemd ile otomatik yeniden başlar.
- **Süre:** 30 gün (2026-12-25'e kadar), ne kadar erken o kadar iyi.
- **Geliştirme ortamı:** Claude'un çalışma ortamından VPS'e ve Exness'e ağ erişimi yok. Kod burada
  sahte (mock) API'ye karşı testlerle yazılır. Canlı doğrulama VPS'te yapılır. Dağıtım GitHub'a push ile olur,
  ayrıntısı §9'da.

## 4. Değerlendirilen yaklaşımlar

| Yaklaşım | Artı | Eksi |
|---|---|---|
| **A. Monorepo'da yeni `trade-bot` servisi, V9'u kütüphane olarak içe aktarır** ✅ | En hızlısı. 702 testle korunan strateji/risk/maliyet mantığı aynen kullanılır | V9'un araştırma kodu da yanında gelir |
| B. Sıfırdan yalın bot, stratejiler kopyalanıp sadeleştirilir | Temiz kod | Test edilmiş mantığı 30 günde yeniden yazmak riskli. "Tüm stratejiler" isteğiyle çelişir |
| C. V9 ayrı HTTP servisi olarak kalır, ayrı bir emir botu onu sorgular | En az değişiklik | V9 API'si MT5'e göre tasarlanmış. Onlarca sembolü HTTP ile taramak yavaş. İki ayrı arıza noktası |

Kullanıcı **A**'yı seçti.

## 5. Mimari

Tek bir Python süreci (asyncio), `trade-bot/` klasöründe:

```
trade-bot/
  tradebot/
    exness/      # imzalama, host keşfi, REST istemcisi, WS istemcisi, limit takibi
    market/      # enstrüman kataloğu, mum önbelleği (SQLite), tick akışı
    signals/     # V9 unified_forex adaptörü: mumlar → strateji değerlendirme → aday işlem planı
    risk/        # portföy limitleri, lot hesabı (V9 risk/maliyet mantığı + portföy kuralları)
    execution/   # emir durum makinesi, idempotency, mutabakat (reconciliation)
    manager/     # açık pozisyon yönetimi: breakeven, kısmi kapama, iz süren stop
    news/        # ekonomik takvim, haber penceresi kontrolü
    store/       # SQLite: ayarlar, işlemler, olaylar, günlük özetler
    api/         # Android için FastAPI (REST + WebSocket push), cihaz eşleştirme / token
    notify/      # Expo push bildirimleri
    app.py       # süreç başlatma, zamanlayıcılar, kalp atışı (heartbeat)
  tests/
  deploy/        # systemd unit, Caddy/HTTPS, kurulum betiği
```

**Akış**
1. Açılışta: limitler okunur, enstrüman kataloğu ve hesap durumu çekilir, açık pozisyonlar SQLite ile **mutabakat** yapılır.
2. Tick akışı WebSocket'ten gelir. Mumlar REST ile yüklenip önbellekte tutulur.
3. Bir M15 mumu kapandığında, etkin her sembol için V9 motoru çalışır. Kullanılan zaman dilimleri:
   M15 giriş, H1/H4 yön (MTF), V9'un mevcut ayarıyla.
4. Onaylı (CONFIRMED) aday şu kapılardan geçer: V9 kapıları (seans, spread, net R/R ≥ 1.5, rejim, çelişki),
   haber penceresi ve portföy limitleri. Geçerse lot hesaplanır.
5. Emir gönderilir: market emri ve broker tarafında SL/TP. Idempotency key = V9 `setup_id`'den türetilir.
6. Sonuç WebSocket'ten gelir. İşlem SQLite'a yazılır ve bildirim gönderilir.
7. Pozisyon yöneticisi her tick'te (ya da birkaç saniyede bir) breakeven, kısmi kapama ve iz süren stop kurallarını uygular.

## 6. Davranış kuralları

### 6.1 Evren
- API'nin listelediği enstrümanlardan Forex ve metal olanlar, artı BTC ve ETH (USD karşılıkları).
- Kullanıcı uygulamadan sembolleri açıp kapatabilir. Varsayılan: hepsi açık.
- Pahalı veya egzotik enstrümanlar ayrıca listeden çıkarılmaz. V9'un maliyet dahil net R/R kapısı onları kendiliğinden eler.
- Forex hafta sonu kapalıdır. Kripto 7/24 taranır.

### 6.2 Stratejiler ve sinyal birleştirme (ince ayar)

**Kaynak:** V9'un dört Forex stratejisi (trend momentum, range, onaylı kırılım, sahte kırılım) ve V9 içinden
erişilebilen tüm strateji ve indikatör modülleri: V2 rejim, price action, formasyon, uyumsuzluk (divergence),
yapı (structure), confluence, MTF. Gerçek hacim isteyen V2 kripto stratejileri yalnızca kripto sembollerde çalışır.

**Ortak arayüz:** Her strateji ve her indikatör modülü aynı küçük arayüzü uygular:
`evaluate(context) -> Signal | Vote | None`. Yarım kalmış modüller bu arayüze uyarlanarak tamamlanır.
Yeni bir strateji eklemek tek bir dosya ve bir kayıt satırı demektir.

**Üç katmanlı karar** (bir setup'ta tüm stratejilerin bulunması beklenmez, bu zaten imkânsız):
1. **Tetik.** En az bir strateji `CONFIRMED` sinyal verirse işlem adayı oluşur. Tek bir strateji yeterlidir.
2. **Güven puanı (0–100).** Tetikleyen strateji dışındaki modüller gerekli değildir. Her biri adaya destek ya da
   karşı oy verir ya da çekimser kalır: MTF uyumu, rejim uyumu, formasyon, uyumsuzluk, yapı/likidite, seans kalitesi,
   aynı yönde onaylayan diğer stratejiler. Puan, modül ağırlıklarıyla hesaplanır.
   Ağırlıklar ve eşikler bir ayar dosyasında durur, uygulamadan değiştirilebilir.
   - Puan < en düşük eşik (varsayılan 40) → işlem açılmaz, aday "gözlem" olarak kaydedilir.
   - Puan, risk çarpanını belirler. Varsayılan: 40–60 → 0.5×, 60–80 → 0.75×, ≥80 → 1.0× işlem başı risk.
     §6.3'teki limitler hiçbir durumda aşılmaz.
3. **Sert vetolar.** Puan ne olursa olsun işlemi engeller: aynı sembolde ters yönlü onay, net R/R < 1.5,
   spread/seans, haber penceresi, portföy limitleri.

**Canlı karne ve kendi kendini ayarlama:**
- Her strateji ve her modül oyu için canlı sonuçlar tutulur: işlem sayısı, kazanma oranı, ortalama R,
  kâr faktörü. Kayıtta tetikleyen strateji, puan ve oy veren modüller yazılır.
- Bir strateji en az 20 işlem sonra ortalama R < 0 ise kendiliğinden duraklatılır ve kullanıcıya bildirim gider.
  Kullanıcı tekrar açabilir. Eşikler ayarlanabilir.
- Modül ağırlıkları otomatik değiştirilmez. Karne verileri raporda gösterilir, ağırlık değişikliği bilinçli
  bir ayar değişikliği olarak yapılır.

**Yeni veya yükseltilmiş stratejiler:** Önce **gölge modunda** çalışır. Sinyalleri ve sanal sonuçları
kaydedilir ama gerçek işlem açılmaz. Varsayılan 20 sanal işlemden sonra karnesi olumluysa (ortalama R > 0)
kullanıcı onayıyla canlıya alınır. Mevcut V9 stratejileri gölge modunu atlar, doğrudan canlıda başlar.

Her strateji ve modül uygulamadan açılıp kapatılabilir.

### 6.3 Risk (bot işlemleri)
| Kural | Varsayılan | Uygulamadan ayarlanabilir aralık |
|---|---|---|
| İşlem başı risk (equity'ye göre) | %0.5 | %0.25 – %1.0 |
| Aynı anda açık bot işlemi | 3 | 1 – 5 |
| Sembol başı açık işlem | 1 | sabit |
| Aynı para birimi aynı yönde | 2 | sabit |
| Günlük bot kaybı → o gün yeni işlem yok | %5 | %2 – %10 |
| Toplam bot kaybı → bot durur, "devam" bekler | %25 | %10 – %30 |

- Lot, V9'un lot hesabıyla belirlenir (broker lot adımı, en küçük lot, komisyon, kayma).
  En küçük lot risk limitini aşıyorsa işlem açılmaz.
- Ayarlar sunucuda doğrulanır. Aralık dışındaki değerler reddedilir.
- **Günlük ve toplam kayıp yalnızca botun kendi işlemlerinden** hesaplanır (gerçekleşen + açık kâr/zarar).
  Toplam kayıp, botun başlangıç sermayesine göre ölçülür. Gün sınırı UTC 00:00'dır.
  *(Claude'un kararı. Gün sınırı istenirse İstanbul saatine çevrilebilir.)*

### 6.4 Elle işlemler
- Uygulamadan açılır: sembol, yön, SL/TP mesafesi. Lot risk %'sine göre önerilir, kullanıcı değiştirebilir.
- `origin=manual` olarak işaretlenir. **Botun limitlerine sayılmaz** (açık işlem sayısı, günlük/toplam kayıp).
  Raporlarda ayrı ayrı ve toplamda görünür.
- Lot hesabı gerçek hesap equity'sini kullanır, çünkü sermaye ve marjin ortaktır.
- Elle işlemlerde kademeli stop yönetimi işlem bazında açılıp kapatılabilir (varsayılan açık).

### 6.5 Pozisyon yönetimi (kademeli stop)
- Kâr +1R'ye ulaşınca SL girişe çekilir. Spread ve komisyon da hesaba katılır, böylece işlem en kötü ihtimalle zararsız kapanır.
- +2R'de (TP1) hacim izin veriyorsa pozisyonun %50'si kapatılır. Kalan kısımda SL, M15 ATR(14) × 1.0
  mesafesiyle fiyatı takip eder. SL hiçbir zaman geri (zarar yönüne) gitmez.
- TP2 3R'dir ve broker tarafında kayıtlıdır.
- Bu eşiklerin hepsi uygulamadan değiştirilebilir.
- Kullanıcı herhangi bir işlemin SL/TP'sini değiştirebilir veya işlemi kapatabilir.
  Kullanıcının elle değiştirdiği SL, bot yönetimi tarafından zarar yönüne geri alınmaz.

### 6.6 Haber
- Kaynak: haftalık ekonomik takvim JSON'u (ForexFactory / faireconomy akışı). 6 saatte bir yenilenir ve önbelleğe alınır.
  Repo'daki Fed RSS köprüsü ek kaynak olarak kalır.
- Yüksek etkili haberden 30 dk önce ve 30 dk sonra, o para birimini içeren sembollerde yeni bot işlemi açılmaz.
  USD haberleri BTC/ETH'yi de etkiler. Açık işlemler stoplarıyla devam eder.
- Takvim 24 saatten uzun süre alınamazsa bot çalışmaya devam eder ve kullanıcıya uyarı gönderir.
  *(Claude'un kararı.)*

### 6.7 Durdur / devam
- **Acil durdur:** yeni işlem açılmaz, açık pozisyon yönetimi sürer.
- **Hepsini kapat:** ayrı bir onay ister.
- **Devam:** durumu sıfırlar. %25 durmasından sonra devam etmek bilinçli bir onay ister.

## 7. Güvenilirlik

- **Yeniden başlatma:** systemd `Restart=always`. Açılışta pozisyon ve emir mutabakatı yapılır, gönderilmiş
  ama sonucu bilinmeyen emirler operasyon durumu sorgulanarak çözülür. Çift emir oluşmaz.
- **Bağlantı:** WebSocket koparsa üstel bekleme ile yeniden bağlanır. Bağlantı yokken yeni işlem açılmaz.
  60 saniyeden uzun kopukluk bildirim üretir.
- **Rate limit:** limitler okunur ve yerelde sayılır. 429 alınırsa limitler yenilenir, beklenir ve yalnızca
  tekrarlanması güvenli işlemler yeniden denenir.
- **Kalp atışı:** API son tarama zamanını yayınlar. Sunucu tamamen ölürse kendisi bildirim gönderemez.
  Bunun yerine uygulama 5 dakikadan uzun süre kalp atışı göremezse kendi yerel bildirimini gösterir.
- **Saat:** sunucuda NTP açık olmalı. İmza zaman damgası buna bağlıdır.
- **Sırlar:** API anahtarı ve özel anahtar sunucuda `.env` dosyasında (izin 600) tutulur. Asla repoya girmez,
  asla uygulamaya gönderilmez.

## 8. Android

- Mevcut Expo uygulamasının iskeleti kullanılır: tema, eşleştirme, durum yönetimi ve test altyapısı.
  Kripto V2'ye ait ekranlar kaldırılır. *(Claude'un kararı. Repo'da kalırlar, uygulamada görünmezler.)*
- **Ekranlar:**
  - Panel: bakiye, equity, bugünkü kâr/zarar, bot durumu, son tarama zamanı
  - Pozisyonlar: kapat, SL/TP düzenle, kademeli stop aç/kapa
  - Elle işlem
  - Raporlar: gün/hafta/ay, strateji ve sembol bazında, kazanma oranı, en büyük düşüş, işlem geçmişi
  - Ayarlar: risk, limitler, semboller, stratejiler, stop yönetimi, haber penceresi
  - Bildirimler
  - Durdur/devam düğmeleri
- **Bağlantı:** uygulama HTTPS ile bot API'sine bağlanır. Cihaz eşleştirme kodu ve token kullanılır, mevcut Gateway'in
  modeli örnek alınır ve tek servise taşınır. HTTPS, alan adı varsa Caddy + Let's Encrypt ile, yoksa Tailscale ile sağlanır.
- **Bildirimler:** Expo push. İşlem açıldı/kapandı, SL girişe çekildi, günlük/toplam limit doldu,
  bağlantı koptu, emir reddedildi, haber takvimi alınamadı.
- Sürüm: EAS ile imzalı APK, GitHub Actions'taki mevcut iş akışıyla.

## 9. Dağıtım

- `main` dalına push → GitHub Actions testleri çalıştırır → SSH ile VPS'e dağıtır ve servisi yeniden başlatır.
- Kullanıcının bir kez yapması gerekenler: VPS'te bir deploy kullanıcısı ve SSH anahtarı oluşturmak,
  anahtarı GitHub Secrets'a eklemek, Claude oturumuna repo push yetkisi vermek.
- İlk canlı adım ayrı bir **API keşif betiği**dir. Bu betik salt okuma yapar: hesap, limitler, enstrümanlar
  (cent lot özellikleri) ve örnek mumları okuyup çıktıyı loglar. Bu çıktı, API Reference'tan doğrulanamayan
  şemaları kesinleştirir.

## 10. Takvim

- **1. hafta:** Exness istemcisi (imza, host keşfi, REST/WS), keşif betiği, V9 adaptörü, risk, emir yönetimi,
  breakeven/iz süren stop, SQLite, systemd, temel API ve push bildirimi. Bot canlıda %0.5 riskle çalışır.
- **2. hafta:** haber filtresi, sinyal birleştirme katmanı (güven puanı, karne, gölge modu),
  Android ekranları (izleme, pozisyonlar, durdur/devam, bildirimler).
- **3. hafta:** strateji ve indikatör kütüphanelerinin tamamlanması ve yükseltilmesi (ortak arayüz, eksik modüller,
  yeni stratejiler gölge modunda), raporlar, ayarlar ve elle işlem ekranları.
- **4. hafta:** hata senaryoları, sertleştirme, canlı karneye göre ince ayar, son APK.

## 13. Çalışma şekli

- Geliştirme Claude Code'da plan dosyasındaki görevler sırayla, **durmadan sonuna kadar** yürütülerek yapılır.
- Yalnızca şu durumlarda durulur ve kullanıcıya sorulur: kullanıcıdan bir şey gerekiyorsa (sır, erişim, alan adı,
  VPS'te komut), gerçek parayı etkileyen ilk canlı emir, geri alınamaz işlemler, ya da tasarımla çelişen bir bulgu.
  Diğer her karar uygulayıcı tarafından verilir ve ilerleme kaydına yazılır.

## 11. Uygulayıcıya bırakılanlar

- Exness API şemalarının tam eşlemesi (SL/TP değiştirme, kısmi kapama, enstrüman alanları, mum zaman dilimleri),
  keşif betiği çıktısına göre.
- V9 modüllerinin tam olarak hangi giriş noktalarından çağrılacağı (`engine.py` / `services.py`).
  Kural (2026-11-25'te kullanıcı kararıyla güncellendi): V9 geliştirilebilir; motorda eksikler var ve giderilecek.
  Ancak risk/maliyet kapılarını (net R/R ≥ 1.5, SL zorunluluğu, lot/risk sınırları) GEVŞETEN değişiklikler
  test + bağımsız inceleme + kullanıcı onayı ister. Diğer V9 değişiklikleri testle birlikte normal akıştan geçer.
- SQLite şeması, API uç noktalarının ayrıntıları, uygulama içi görsel tasarım.

## 12. Bilinen riskler

- Stratejilerin gerçek piyasada kâr ettiği kanıtlanmış değil (V9 dokümanları da böyle söylüyor).
  İlk haftalar kanıtlama dönemidir.
- Exness API yeni bir ürün. Bazı davranışlar ancak canlı keşifte netleşecek.
- 30 USD ile birkaç kayıp yüzdesel olarak büyük görünür. %25 durma kuralı bunun için var.
