# Trade Bot Faz 4: sertleştirme, yedek, günlükler, kullanım kılavuzu

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Her Task sonunda testler yeşil → commit → push.

**Goal:** Botu gözetimsiz 7/24 çalışmaya hazırlamak: veri kaybına ve sessiz arızaya karşı korumalar, bakım işleri,
hata senaryosu testleri ve teknik olmayan kullanıcı için Türkçe kılavuz.

**Spec:** `docs/superpowers/specs/2026-11-25-trade-bot-design.md` (§9 işletim, §11 kurallar, §12 4. hafta).
**Önceki fazlar:** `trade-bot/PROGRESS.md`.

## Global Constraints

- Faz 1–3 kısıtları aynen: SL'siz emir yok; martingale/grid yok; emirler kendiliğinden yinelenmez; sırlar yalnızca
  sunucudaki `/etc/tradebot/tradebot.env` dosyasında; herkese açık günlük ve uçlarda hesap no/bakiye/tutar yok;
  testler ağsız çalışır; Exness alan adları yalnızca `tradebot/exness/schema.py`'de.
- V9 geliştirilebilir; risk/maliyet kapılarını gevşeten değişiklik test + bağımsız inceleme + kullanıcı onayı ister.
- **Kullanıcıya yeni sunucu adımı açılmaz.** Dağıtım kullanıcısının yetkisi yalnızca servisi yeniden başlatmaktır;
  bu yüzden bakım işleri (yedek, temizlik) root gerektiren systemd zamanlayıcılarıyla değil **bot sürecinin içinde**
  çalışır ve yalnızca `/var/lib/tradebot` altına yazar. Root gerektiren iyileştirmeler `install.sh`'a eklenir ve
  kılavuzda "isteğe bağlı" diye anlatılır.
- Bakım işleri işlem yolunu asla bloklamaz ve asla düşürmez: hata olursa olay kaydı + uyarı, bot çalışmaya devam eder.
- Bot deneme modunda kalır; canlıya geçiş yalnızca kullanıcının açık onayıyla. main'e alma kullanıcı onayı ister (🛑).

## Task 1 — Mum önbelleği: boşluk onarımı

> **Durum:** PR #12 ile ayrı olarak main'e alındı (kullanıcı onayıyla): `CandleStore.heal`, tarama başına en çok 4
> onarım, borsanın da vermediği boşluk için 6 saat yeniden deneme yok. Bu fazda ek iş yok.

Canlıda bazı semboller her taramada "eksik mum" ile eleniyor (PR #11 tanılaması hangi sembol/nerede gösterir).
Önbellek yalnızca son mumdan sonrasını çeker; bir kez oluşan boşluk kalıcıdır.

- `CandleStore.heal(symbol, tf)`: son `count` mumluk aralığı baştan çeker, `INSERT OR REPLACE` ile yazar.
- Bot, V9 bir sembolü "missing candle" ile reddettiğinde o sembolün çerçevelerini **bir sonraki taramada** onarır;
  sembol/çerçeve başına en çok saatte bir (istek limiti korunur), onarım sonucu olay olarak yazılır.
- Onarımdan sonra da boşluk sürüyorsa gerçek piyasa boşluğudur: tanılamada "onarım denendi" notu görünür.
- Test: boşluklu önbellek + API'de mum var → sonraki taramada onarılır; API'de de yoksa saatte birden fazla istek yok.

## Task 2 — Günlük SQLite yedeği (süreç içinde)

- `tradebot/store/backup.py`: `sqlite3.Connection.backup()` ile tutarlı kopya → `<db dizini>/backups/tradebot-YYYYMMDD.db`,
  geçici dosyaya yazıp `os.replace`; kopyada `PRAGMA quick_check`; dosya kipi 600; en yeni 14 yedek tutulur.
- Bot günde bir (UTC 00:10 sonrası ilk fırsatta, ayrıca açılışta bugünün yedeği yoksa) çalıştırır; bloklamamak için
  `asyncio.to_thread`. Sonuç: `backup_done` olayı (boyut, süre) ya da `backup_failed` uyarısı + bildirim.
- `/health`: `last_backup_at` (hesap verisi değil). 36 saatten eskiyse `status.sh` uyarı satırı yazar.
- Test: yedek açılabilir ve tabloları içerir; eskiler silinir; hata botu düşürmez; aynı gün ikinci kez alınmaz.

## Task 3 — Veri temizliği ve WAL bakımı

- Günlük bakımda: 60 günden eski `scan`, `scan_skipped`, `signal_observed`, `heartbeat` türü olaylar silinir
  (işlem, emir, ayar, uyarı ve hata olayları SİLİNMEZ); `PRAGMA wal_checkpoint(TRUNCATE)`; `events(at)` dizini
  (özet ucu tam tablo taraması yapmasın).
- Test: yalnızca gürültü olayları silinir; işlem geçmişi ve raporlar değişmez.

## Task 4 — Hata senaryoları (testle kanıtla, eksikse düzelt)

Her biri için sahte borsayla bir test; davranış yanlışsa düzeltme:
1. Açık pozisyon varken marjin kapanması (`can_open=False`): yeni işlem yok, açık işlemler yönetilir, uyarı bir kez.
2. Kısmi dolum (istenenden küçük hacim): işlem gerçek hacimle kaydedilir, SL o hacmi korur, kısmi kapatma adımı
   en küçük lot kuralına uyar.
3. Disk dolu / veritabanı yazılamıyor: emir GÖNDERİLMEZ (kayıt yazılamadan emir yok), bot durur ve uyarır.
4. Zamanlayıcı görevlerinden biri beklenmeyen hata verirse diğerleri (özellikle stop takibi) çalışmaya devam eder;
   hata olay olarak yazılır, art arda hatada uyarı.
5. Saat kayması: sunucu saati ile tick saatleri arasında > 5 sn fark sürerse uyarı (V9 veriyi bayat sayar).
6. Uzun kesinti sonrası açılış: kaçırılan mumlar çekilir, sanal işlemler doğru sonuçlanır, eski sinyale emir yok.

## Task 5 — Günlükler

- Bot stdout'a yazar; systemd-journald saklar ve kendisi döndürür. `deploy/journald-tradebot.conf` (drop-in:
  `SystemMaxUse=200M`, `MaxRetentionSec=30day`) eklenir; `install.sh` kurar (yeni kurulumlarda kendiliğinden,
  mevcut sunucuda isteğe bağlı tek komut — kılavuzda).
- Günlük satırlarında sır/hesap bilgisi olmadığını doğrulayan test (token, API anahtarı, hesap no, bakiye kalıpları).
- Açılışta tek satır sürüm/commit ve kip (deneme/canlı) bilgisi.

## Task 6 — Türkçe kullanım kılavuzu (`trade-bot/README.md`)

Teknik olmayan kullanıcı için: bot ne yapar/ne yapmaz; telefona kurulum ve eşleştirme; Panel/Pozisyonlar/Raporlar/
Bildirimler/Ayarlar ekranları; deneme → canlı geçiş ve geri dönüş; acil durum (Durdur, Hepsini kapat, telefon yoksa
MT5/Exness'ten kapatma); ayarların anlamı ve güvenli aralıklar; yeni stratejilerin gölgeden canlıya alınması;
yedekler ve geri yükleme; sık görülen uyarılar ve ne yapılacağı; sunucu komutları (kopyala-yapıştır, her biri ayrı).
Sır içermez; sırların nerede durduğunu ve asla sohbete/depoya yazılmayacağını söyler.

## Task 7 — Faz sonu

- `pytest`, V9 paketleri, Android testleri; bağımsız inceleme (`requesting-code-review`); bulgular regresyon
  testleriyle düzeltilir; `PROGRESS.md` Faz 4 bölümü; PR; 🛑 main'e alma onayı.

## Review Focus

- Bakım işleri işlem yolunu bloklayabilir ya da düşürebilir mi? Yedek sırasında yazma kilidi ne kadar sürer?
- Yedek dosyaları kimlerce okunabilir (kip, dizin)? Yedekte token özetleri var; depo/günlüğe sızmamalı.
- Temizlik, raporların ya da karnenin dayandığı bir kaydı silebilir mi?
- Boşluk onarımı istek limitini aşabilir ya da taramayı geciktirebilir mi?
- Kılavuzdaki her komut ve ekran adı gerçek olanla birebir mi?
