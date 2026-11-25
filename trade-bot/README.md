# Trade Bot — kullanım kılavuzu

Bu kılavuz botu **kullanan** kişi içindir. Sunucu kurulumu ayrı bir belgede: [`deploy/README.md`](deploy/README.md).

## Bot ne yapar, ne yapmaz

- Exness hesabınızda, sunucuda 7/24 çalışır. Her 15 dakikada bir, işlem yapılabilen sembolleri tarar.
- Bir kurulum bulursa ve bütün güvenlik kapılarından geçerse işlem açar. **Her işlemin zarar durdurma (SL) seviyesi
  emirle birlikte Exness'e gönderilir**; bot ya da sunucu çökse bile SL Exness tarafında durur.
- Açık işlemleri yönetir: kâr 1R'ye ulaşınca stopu girişe çeker (başa baş), 2R'de işlemin yarısını kapatır, sonra
  stopu fiyatın arkasından sürükler. (R = o işlemde göze alınan zarar.)
- Yapmadıkları: zarardaki işleme ekleme yapmaz (martingale/ızgara yok), SL'siz işlem açmaz, kayıp sınırlarını
  kendiliğinden gevşetmez, başarısız bir emri kendiliğinden yeniden göndermez.

Bot kazanç garantisi vermez. Küçük hesapta en küçük lot bile ayarladığınız riskten büyük olabilir; bot o durumda
işlem açmaz.

## İki kip: deneme ve canlı

| | Deneme modu | Canlı mod |
|---|---|---|
| Tarama ve analiz | Yapar | Yapar |
| Emir gönderme | **Göndermez**; "açardım" diye kaydeder | Gerçek parayla gönderir |
| Sizin uygulamadan verdiğiniz emirler | **Her zaman gerçektir** | Gerçektir |

Deneme modunda bile uygulamadan "Kapat", "SL/TP düzenle", "Hepsini kapat" ve "Elle işlem aç" gerçek hesapta işlem
yapar. Uygulama bunu her onay penceresinde hatırlatır.

Canlıya geçiş: **Panel → Canlı moda geç** (iki adımlı onay). Geri dönüş: **Panel → Deneme moduna dön**.
Kayıp sınırlarının tabanı, canlıya ilk geçtiğiniz andaki hesap varlığıdır; sonradan yatırdığınız ya da çektiğiniz
para kâr/zarar sayılmaz, taban ona göre kayar.

## Telefona kurulum ve eşleştirme

1. APK'yı GitHub'daki **Actions → Android APK** çalışmasının çıktısından indirip kurun.
2. Sunucuda bir eşleştirme kodu üretin (10 dakika geçerli, tek kullanımlık):

   ```bash
   tradebot-pair
   ```

3. Uygulamada **Ayarlar → Bağlantı ayarları**: sunucu adresini (`https://…sslip.io`) ve 6 haneli kodu girin.

Bağlantı anahtarı yalnızca telefonun güvenli deposunda tutulur. Telefon kaybolursa bütün cihazların erişimini
sunucudan iptal edin (komut [`deploy/README.md`](deploy/README.md) içinde, "Telefon kaybolursa" başlığında), sonra
yeniden eşleştirin.

Uygulama kapalıyken bildirim gelmesi için ek kurulum (Firebase) gerekir; **henüz yapılmadı**. Şimdilik bildirimler
uygulama açıkken görünür.

## Ekranlar

- **Panel:** kip (deneme/canlı), bot durumu (son tarama, Exness bağlantısı), hesap (bakiye, varlık, serbest
  teminat), bugünkü kâr/zarar (bot / elle / toplam) ve açık işlem sayıları.
  Düğmeler: **Durdur**, **Devam**, **Hepsini kapat**, **Canlı moda geç / Deneme moduna dön**.
- **Pozisyonlar:** açık işlemler. Her kartta **Kapat** ve **SL/TP düzenle**; üstte **Elle işlem aç**.
- **Raporlar:** bot / elle / toplam sonuç, kazanma oranı, en büyük düşüş, strateji ve sembol kırılımı, gölge
  karnesi, son işlemler. Günler UTC saatine göre ayrılır. **Yenile** düğmesi ve "son güncelleme" saati vardır.
- **Bildirimler:** botun kayıtları (açılan/kapanan işlem, uyarılar, hatalar).
- **Ayarlar:** risk ve sınırlar, korumalar, semboller, stratejiler, bağlantı.

Ekranda "Bağlantı yok" ya da "Bot yanıt vermiyor" görüyorsanız gösterilen sayılar eski olabilir; uygulama bunu
belirtir. Açık işlemlerinizin SL'i Exness tarafında durduğu için bu durumda da korunursunuz.

## Acil durum

| Ne istiyorsunuz | Ne yapın |
|---|---|
| Bot yeni işlem açmasın, açıkları yönetsin | **Panel → Durdur** |
| Her şeyi kapatıp botu durdurmak | **Panel → Hepsini kapat** (onay ister) |
| Telefon/uygulama çalışmıyor | Exness uygulamasından ya da MT5'ten pozisyonları elle kapatın; bot bunu görür ve kaydeder |
| Sunucuya ulaşılamıyor | İşlemlerin SL'i Exness'te durur. Sunucu dönünce bot kaldığı yerden devam eder |

**Durdur** kalıcıdır: siz **Devam** diyene kadar yeni işlem açılmaz (sunucu yeniden başlasa da).

Toplam kayıp sınırı dolarsa bot kendini **kilitler** ve yalnızca açık işlemleri yönetir. Kilidi açmak ayrı bir onay
ister; önce nedenine bakın.

## Elle işlem açma

**Pozisyonlar → Elle işlem aç.** Sembol ve yönü seçin, zarar durdurma mesafesini (fiyat farkı olarak) girin; kâr al
mesafesi isteğe bağlıdır. Lotu kendiniz yazabilir ya da boş bırakıp risk yüzdesine göre önerilmesini
isteyebilirsiniz.

1. **Önizle:** lot, yaklaşık giriş/SL/TP, en çok zarar ve hesabın yüzdesi gösterilir. Emir gönderilmez.
2. **Emri gönder:** önizlenen sayılarla onay penceresi açılır. Önizleme 1 dakikadan eskiyse yenilemeniz istenir.

Elle işlemler botun "aynı anda açık işlem" sınırına sayılmaz, ama zararları hesabınızdan çıkar.

**"Emrin sonucu bilinmiyor" görürseniz** yeni emir göndermeyin. **Sonucu kontrol et** düğmesi yalnızca sorar,
emir açmaz: emir sunucuya ulaşmışsa durumunu gösterir, ulaşmamışsa o emri iptal eder. Bu uyarı, ekranı ya da
uygulamayı kapatıp açsanız da sonuç öğrenilene kadar kalır.

## Ayarlar

Her kayıt "eski → yeni" listesiyle onay ister. Riski artıran değişiklikler **⚠ risk artar** diye işaretlenir.

| Ayar | Anlamı | Aralık | Varsayılan |
|---|---|---|---|
| İşlem başı risk | Bir işlemde göze alınan zarar, hesabın yüzdesi | %0,25–1 | %0,5 |
| Aynı anda açık bot işlemi | Botun aynı anda taşıyabileceği işlem sayısı | 1–5 | 3 |
| Günlük kayıp sınırı | Dolunca o gün yeni işlem açılmaz | %2–10 | %5 |
| Toplam kayıp sınırı | Dolunca bot kilitlenir | %10–30 | %25 |
| Haber penceresi | Önemli haberin öncesi/sonrasında yeni işlem yok | 5–120 dk | 30 dk |
| En düşük güven puanı | Altındaki sinyale işlem açılmaz (yalnızca izlenir) | 0–100 | 40 |
| Orta güven eşiği | Altındaki sinyal yarım lotla açılır | 0–100 | 60 |
| Yüksek güven eşiği | Üstündeki sinyal tam lotla açılır | 0–100 | 80 |

Anahtarlar (hepsi birer korumadır; kapatmak riski artırır):

- **Haber penceresi koruması**, **Güven puanı**
- **Başa baş stopu**, **Kısmi kâr alma**, **İz süren stop** — kapatılan aşama atlanır. İşlemin ilk zarar durdurma
  seviyesi hiçbir durumda kaldırılmaz.

**Semboller:** botun işlem açacağı sembolleri açıp kapatabilirsiniz. Kapatılan sembolde yeni işlem açılmaz; açık
işlemi varsa yönetilmeye devam eder.

Emin değilseniz varsayılanları değiştirmeyin. 30 USD gibi küçük bir hesapta riski yükseltmek, birkaç kayıpla
sınırlara çok çabuk ulaşmak demektir.

## Stratejiler ve gölge modu

Her strateji üç kipten birindedir: **Canlı** (işlem açar), **Gölge** (sinyali sanal işlem olarak izlenir, emir
gönderilmez), **Kapalı**.

- Yeni stratejiler ("(yeni)" ile işaretli) **gölgede** başlar. Canlıya alınabilmeleri için en az 20 sonuçlanmış
  gölge işlem ve pozitif ortalama sonuç gerekir; koşul sağlanmadan **Canlıya al** düğmesi kapalıdır ve nedeni altında
  yazar.
- Bot, kötü giden bir stratejiyi kendiliğinden duraklatabilir ("bot duraklattı"). Yeniden canlıya almak, duraklatmadan
  sonraki gölge sonuçlarının iyi olmasını ve sizin onayınızı ister.

## Yedekler

Bot her gün veritabanının bir kopyasını alır: `/var/lib/tradebot/backups/tradebot-YYYYAAGG.db`. Son 14 gün
saklanır. Yedek alınamazsa bildirim gelir.

Yedekler işlem geçmişinizi ve ayarlarınızı içerir; **paranız ve açık pozisyonlarınız Exness'tedir**, veritabanı
kaybolsa da onlar kaybolmaz. Veritabanı silinirse bot açık pozisyonları Exness'ten yeniden okur, ama onları "elle
açılmış" sayar ve geçmiş raporlar boş başlar.

Geri yükleme (yalnızca gerekirse; önce botu durdurur):

```bash
sudo systemctl stop tradebot
```

```bash
sudo -u tradebot cp /var/lib/tradebot/backups/tradebot-YYYYAAGG.db /var/lib/tradebot/tradebot.db
```

```bash
sudo systemctl start tradebot
```

`YYYYAAGG` yerine geri dönmek istediğiniz günün dosya adındaki tarihi yazın.

## Sık görülen uyarılar

| Uyarı | Anlamı | Ne yapmalı |
|---|---|---|
| Exness bağlantısı yok | Fiyat akışı kesildi; yeni işlem açılmaz | Genelde kendiliğinden düzelir. Saatlerce sürerse sunucu günlüğüne bakın |
| Günlük kayıp sınırı doldu | Bugün yeni işlem yok | Ertesi gün (UTC) kendiliğinden açılır |
| Bot durduruldu (toplam kayıp sınırı) | Kilit | Nedenini inceleyin; devam etmek ayrı onay ister |
| Stop eksik (`sl_missing`) | Bir pozisyonda SL görünmüyor | Bot stopu yeniden kurmayı dener; 3 denemede kuramazsa pozisyonu kapatır |
| Emir sonucu belirsiz | Bir emrin yanıtı alınamadı | Bot yeniden göndermez; Pozisyonlar ekranından durumu kontrol edin |
| Haber takvimi güncel değil | Haber koruması veri alamıyor | Bot çalışır ama haber penceresi uygulanamayabilir; düzelmezse haber bildirin |
| Yedek alınamadı | Günlük kopya yazılamadı | Çoğunlukla disk dolu; sunucuda `df -h /var/lib/tradebot` |
| Hesap yeni işleme kapalı | Exness hesabı yeni emir kabul etmiyor (marjin vb.) | Exness hesabınızı kontrol edin |
| Sunucu saati kaymış | Sunucu saati fiyat akışının gerisinde; analiz veriyi "bayat" sayıp işlem açmayabilir | Sunucuda `timedatectl status`; "System clock synchronized: yes" olmalı |

## Sunucuda işe yarayan komutlar

Durum (hesap bilgisi yazmaz):

```bash
/opt/tradebot/trade-bot/deploy/status.sh
```

Son günlük satırları:

```bash
sudo journalctl -u tradebot -n 80 --no-pager
```

Servisi yeniden başlatma:

```bash
sudo systemctl restart tradebot
```

Yeni eşleştirme kodu:

```bash
tradebot-pair
```

Günlük boyutunu sınırlama (isteğe bağlı, bir kez; sunucudaki bütün servislerin günlüğünü en çok 300 MB / 30 günle
sınırlar):

```bash
sudo install -D -m 644 /opt/tradebot/trade-bot/deploy/journald-tradebot.conf /etc/systemd/journald.conf.d/tradebot.conf
```

```bash
sudo systemctl restart systemd-journald
```

## Sırlar

API anahtarı, özel anahtar ve hesap numarası yalnızca sunucudaki `/etc/tradebot/tradebot.env` dosyasında durur.
Bunları depoya, sohbete, e-postaya ya da uygulamaya **yazmayın**; kimse sizden bunları mesajla istememelidir.
Uygulamanın kullandığı bağlantı anahtarı ayrıdır ve sunucudan iptal edilebilir.
