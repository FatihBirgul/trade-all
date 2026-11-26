# Trade Bot — ilerleme kaydi

Uygulayicinin kendi verdigi kararlar ve kesif bulgulari, tarih sirasiyla tek satir.

## 2026-11-25
- `executing-plans` skill'i oturumda yoktu; plan ayni duzenle (test → kod → commit) dogrudan yurutuldu.
- Gelistirme ortami Python 3.12 venv (`trade-bot/.venv`), VPS ile ayni surum. V9 testleri CI'da 3.11'de kalir.
- Exness dokumanlari okunabildi (OpenAPI 1.0.2, `www.exness-api.com`); asagidaki "API bulgulari" buna dayanir, canli kesifle dogrulanacak.
- Imza: payload `json.dumps(separators=(',',':'))`, alan sirasi `api_key, idempotency_key, timestamp, sign_version, method, path, body_hash`. Resmi Python ornegi ve dokumandaki test vektoru ile birebir dogrulandi (`tests/exness/test_signing.py::test_official_test_vector`); canli kesifte yalnizca anahtar yukleme dogrulanacak.
- Ozel anahtar: Exness'in urettigi 128 hex (tohum + acik anahtar) ve PKCS#8 PEM desteklenir; 64 hex / base64 32 bayt da kabul edilir.
- Host: `EXNESS_AP_HOST` verilmisse o kullanilir; yoksa Gateway'de `GET /v1/trading/access-point?account_id=` ile kesfedilir ve onbellege alinir.
- Hata kodlari sayisaldir (1001 = AUTH_INVALID_SIGNATURE, 3015 = REQUEST_RATE_LIMIT). Istemci hicbir istegi kendiliginden tekrarlamaz.
- `RateLimiter.acquire(method, path)`: plan `acquire(operation)` diyordu; `/limits` yaniti her operasyon icin metod + yol sablonu verdigi icin eslestirme sablondan yapilir, operasyon adi koda gomulmez.
- Dagitim: plan `appleboy/ssh-action` diyordu; SSH ozel anahtarini ucuncu taraf bir action'a vermemek icin runner'daki duz `ssh` kullanildi. Ek istege bagli secret'lar: `VPS_KNOWN_HOSTS` (onerilir), `VPS_PORT`.
- Sunucuda iki kullanici: `deploy` (kodu ceker, venv'i gunceller; sudo yalnizca uc sabit komut: `systemctl restart tradebot`, `systemctl is-active tradebot`, `journalctl -u tradebot -n 40 --no-pager`) ve `tradebot` (servis; yalnizca `/var/lib/tradebot`'a yazar). Not: `deploy` kullanicisi servisin calistirdigi kodun sahibidir; `main`'e push yetkisi ya da `VPS_SSH_KEY` islem anahtarina erisim demektir. `production` ortaminda "Required reviewers" acilmasi onerilir.
- Kesif ciktisi `var/discovery/` yerine `<db klasoru>/discovery/<ts>/` altina yazilir (servis kullanicisinin yazabildigi tek yer).

### API bulgulari (OpenAPI 1.0.2; canli kesifle dogrulanacak)
- Pozisyonda SL/TP alani yok: SL/TP, pozisyona bagli ayri bir `sltp` emridir. Acilista `stop_loss_price`/`take_profit_price` verilir; sonradan degisiklik `PATCH orders/{sltp_emir_id}`, hic yoksa `POST orders {type: sltp}`. `schema.parse_snapshot` ikisini birlestirir.
- Kismi kapama govde degil sorgu parametresidir: `DELETE positions/{id}?volume=`. Bu yuzden plan'daki `close_position_body` yerine `close_position_path` var; `open_position_body` → `open_position_request` (yol + govde), `modify_sltp_body` → `sltp_create_request` / `sltp_modify_request`.
- Enstruman kosullarinda `tick_value` ve `stops_level` yok. `tick_size = 10^-point_digits`; tick degeri yerelde `contract_size × tick_size × (kote → hesap para birimi kuru)` ile hesaplanir (Task 7). `stops_level = 0`; asiri yakin stop broker tarafinda `TRADING_RULE_INVALID_PRICE_LEVELS` ile reddedilir.
- Enstruman listesi yalnizca ad dondurur; kosullar enstruman basina ayri istektir. Katalog acilista hepsini limitlere uyarak ceker.
- Tur (forex/metal/crypto/other) `category` + para birimi yapisindan cikarilir; gercek `category` degerleri kesifte gorulecek (`summary.json` → `categories`).
- Cent hesapta enstruman adlarinin sonek tasimasi beklenir (or. `EURUSDc`). `Instrument.symbol` kanonik ad (EURUSD), `broker_symbol` API adi. Bot ici her yer kanonik adi kullanir.
- Islem saatleri `trade_sessions` (UTC, "Mon, 00:00:00") alanindan V9 haftalik pencere bicimine cevrilir. Alan yoksa saatler bilinmiyor sayilir ve V9 islem acmaz (fail-closed).
- Mum: `time` ISO acilis zamani, `volume` → `tick_volume`. `from` dahil, `to` haric. Zaman dilimi adlari V9 ile ayni (M15/H1/H4).
- Pozisyon basina kar/zarar API'de yok; yerelde hesaplanir. Hesap bakiyesi/equity `snapshot.account_state` ve `account_state_event` ile gelir (2 sn'de bir).
- Emir sonucu: `transaction_event.status` success/rejected/failed; operasyon durumu pending/confirmed/rejected/failed, 24 saat saklanir. Idempotency key 5..128 karakter, `[A-Za-z0-9._~-]`.
- 429 (`REQUEST_RATE_LIMIT`, 3015) dokumanda "otomatik tekrar edilemez" olarak tanimli; istemci tekrar denemez.
- Tarihler URL'de `2026-03-16T12:00:00Z` biciminde gonderilir (kacis gerektirmez); istemci imzalanan yol ile gonderilen yol farkliysa istegi gondermeden reddeder.
- Task 6: V9'da `is_supported_symbol` (`[A-Z0-9]{3,12}`) eklendi; `capture` ve `analyze` beyaz liste yerine bunu kullaniyor. `SYMBOLS` aynen duruyor. Hicbir eski test kirilmadi (V5 423, V2 152, engine 132 gecti). `docs/source_manifest.json` `refresh_manifest.py` ile yenilendi.
- Task 7: Tick degeri `contract_size × tick_size × kur` ile hesaplanir; kur Exness donusum kurallariyla (dogrudan, ters, USD uzerinden) bulunur. Zarar yuksek kurla, kar dusuk kurla cevrilir (temkinli). Cent hesap: `USC = USD × 100`.
- **Canliya gecmeden dogrulanacak:** cent hesapta `contract_size` degerinin lot basina gercek carpan oldugu (kesif ciktisi + dry-run'da hesaplanan risk tutari ile).
- V9'a `enabled_strategies` sirali liste olarak verilir (V9 parametreleri JSON'a cevirir). Bilinmeyen strateji adlari sessizce elenir; hic etkin strateji kalmazsa aday uretilmez.
- `evaluate()` karar ve nedenleri de dondurur (dry-run ozeti icin); `evaluate_symbol()` plandaki imzayla ayni.
- Task 10: Broker'daki TP = TP2 (3R). TP1 (2R) broker'a yazilmaz; orada kismi kapamayi pozisyon yoneticisi yapar.
- Sonucu bilinmeyen ACMA emri hicbir kosulda yeniden gonderilmez (bayat M15 sinyaliyle islem acmamak icin). Cozum sirasi: (1) olaydaki `client_request_id`, (2) operasyon durumu, (3) broker anlik goruntusunde emre birebir uyan pozisyon. 60 sn icinde karsiligi bulunmazsa emir `CANCELLED` olur ve `order_unknown` olayi uretilir.
- Gerceklesen kar/zarar deal bazinda tutulur (`realized` tablosu, `deal_id` tekil): ayni kapanis hem WS olayiyla hem mutabakatla gelse de bir kez sayilir. Tutar = `profit − |commission|` (komisyonun isareti kesifte dogrulanacak).
- Botun disindan (MT5/web) acilan pozisyonlar `manual` olarak ice alinir; SL'i disaridan degistirilen bot islemi `user_sl_override` olur.
- Reddedilen SL/TP degisikligi ya da kapama sonrasi ayni pozisyon icin 60 sn beklenir (dongude tekrar yok).
- Task 11: Basa bas seviyesi `giris ± cost_per_unit`; spread ayrica eklenmez cunku BUY'da SL bid'e, SELL'de ask'a gore tetiklenir (giris fiyatinda kapanis = 0 kar/zarar). `cost_per_unit` = komisyonun fiyat karsiligi + 1 tick (servis dongusu hesaplar).
- Iz suren stop yalnizca kismi kapama asamasi tamamlandiktan (ya da hacim bolunemedigi icin atlandiktan) sonra baslar. Tek cagrida en fazla bir SL hareketi dondurulur (basa bas ve iz surme ayni anda uygunsa daha iyi olan).
- Task 12: Gunluk ve toplam kayipta acik (gerceklesmemis) kar/zarar da sayilir; toplam, botun ilk calistigi andaki equity'ye (`start_capital`) gore olculur ve yeniden baslatmada sifirlanmaz.
- Kalp atisi `bot_state.heartbeat_at` alanina yazilir (30 sn); `last_scan_at` yalnizca gercek taramada guncellenir. Plan ikisini tek alanda tutuyordu; uygulamanin "5 dk kalp atisi yok" alarmi 15 dakikalik tarama araligiyla calismazdi.
- Acilista kimlik hatasi (1001 vb.) alinirsa surec cikmaz: tek bildirim gonderir, 5 dk bekleyip yeniden dener. Aksi halde systemd 5 sn'de bir yeniden baslatip istek dongusu olustururdu.
- Engellenen adaylar (limit dolu, ayni sembolde acik islem) ayri olay uretmez; tarama ozetindeki `blocked_reasons` icinde sayilir. Kapali piyasalar `closed` sayacina girer, bildirim uretmez.
- V9 analizi sembol basina ~80 ms surer ve senkrondur; semboller arasinda olay dongusune sira verilir (pozisyon yonetimi gecikmesin).
- Tick abonelikleri 20'li gruplar halinde ve abonelik hiz sinirina gore araliklarla gonderilir (limit `/limits` yanitindan; bilinmiyorsa 10'lu grup, 1 sn ara).
- `tp2_r` ayari 3.0'dan farkliysa broker TP'si `giris ± tp2_r × R` olarak yeniden hesaplanir; 3.0 iken V9 planindaki TP2 aynen kullanilir.
- Task 13: `/pair` 5 hatali denemeden sonra bekleyen kodu iptal eder (6 haneli kod kaba kuvvetle denenemesin); ayni anda tek gecerli kod vardir.
- `/bot/resume` (%25 durmasindan sonra, `confirm_halt=true` ile) olcum tabanini sifirlar: `start_capital` = o anki equity, `start_at` = simdi. Aksi halde bot ayni kayip yuzunden hemen yeniden dururdu. Gunluk limit o UTC gunu icin gecerli kalir.
- `/bot/close-all` botu da durdurur (`stopped=true`); yoksa kapanan pozisyonlarin yerine yenileri acilabilirdi. Bot ve elle islemlerin hepsini kapatir.
- Elle islem (`POST /trades`): SL mesafesi zorunlu, TP istege bagli. Lot verilmezse gercek equity × risk% / (1 lot zarari) ile hesaplanir. Dry-run yalnizca botu etkiler; elle islemler her zaman gercektir.
- API belgeleri (`/docs`, `/openapi.json`) kapali; `WS /stream` token'i sorgu parametresi ya da Authorization basligiyla alir.
- Task 14: Bildirim tekrar bastirma anahtari `tur + sembol + pozisyon` (plan `tur + sembol` diyordu): ayni sembolde art arda kapanan iki ayri islemin ikisi de bildirilir. Basarisiz gonderim bastirma sayilmaz. `DeviceNotRegistered` donen cihaz silinir.
- Kullaniciya gorunen metinler (bildirim, olay, API hata mesaji) Turkce karakterlidir; kod ici yorumlar ASCII Turkce.

## Faz 1 bagimsiz incelemesi (2026-11-25) ve duzeltmeler
Inceleme 3 kritik, 13 onemli bulgu cikardi; gerileme testleri `tests/test_review_fixes.py` icinde.
- **C1** Dry-run'da pozisyon yoneticisi gercek SL degisikligi/kismi kapama gonderiyordu → dry-run'da bot hicbir emir gondermez (yapacagi adim loglanir). Botun disindan (MT5/web) acilan pozisyonlar artik `manage=False` ile ice alinir; uygulamadan acilan elle islemler `manage=True` kalir (spec §6.4). 1R yalnizca ZARAR tarafindaki stoptan turetilir; kar tarafina cekilmis stoplu pozisyon yonetilmez.
- **C2** Ayni taramada gonderilmis ama henuz dolmamis acma emirleri risk kapisinda sayilmiyordu → acik islem sayisi, sembol ve para birimi kurallarina dahil edildi.
- **C3** Bayat anlik goruntu yeni acilmis islemi kapatip pozisyonu sahipsiz birakabiliyordu → goruntu alinirken veritabani degistiyse goruntu yeniden alinir; 120 sn'den yeni ve kapanis deal'i olmayan islem tek goruntuyle kapatilmaz; DB'de kapali ama broker'da acik pozisyon yeniden acilir (`trade_reopened`).
- **I1** Olaylar kayipken acilip kapanan pozisyon artik deal gecmisinden bulunup kapali bot islemi olarak kaydedilir (kayip limitlere girer).
- **I2** Hiz sinirlayici beklerken kilit tutmuyor; genel kotanin %10'u emir istekleri icin ayrilir (mum taramasi stop tasimayi bekletmez).
- **I3** `manage_tick` her pozisyonu islemeden once yeniden okur ve bayrak guncellemelerini hedefli `UPDATE ... WHERE closed_at IS NULL` ile yapar.
- **I4/I5** Sonucu ogrenilemeyen emir 120 sn sonra birakilir (pozisyon kilitli kalmaz). Kullanicinin kapama istegi botun bekleyen SL degisikligi yuzunden engellenmez. `close-all` atlanan pozisyonlari dondurur. Deal sorgusunda gelecege donuk `to` gonderilmez.
- **I6** Stop korumasi: bot pozisyonunda (ve yonetimi acik elle islemde) broker'in onayladigi SL yoksa once broker'dan dogrulanir; gercekten yoksa istenen seviyeye yeniden kurulur, fiyat o seviyeyi gectiyse pozisyon kapatilir; `sl_missing` bildirimi gider. `trade.sl` artik yalnizca broker'in onayladigi degerdir. Bu koruma dry-run'da da calisir (stopsuz pozisyon anti-hedefi daha onceliklidir).
- **I7 (uygulanmadi, gerekce):** Inceleyici SL/TP degisikliginde her iki seviyenin de gonderilmesini onerdi. OpenAPI "omitted field is not changed" diyor; yalnizca degisen alani gondermek belgelenmis sozlesmedir ve bayat yerel degerin broker'daki (belki kullanicinin elle koydugu) SL'in ustune yazilmasini onler. **Ilk canli pozisyonda dogrulanacak:** SL degisince TP yerinde kaliyor mu.
- **I8** Yeni SL/TP emri konup eskisi iptal edildiginde yerel SL silinmiyor; yalnizca islemin kendi emrinin iptali SL'i siler (ve stop korumasi devreye girer).
- **I9** Katalog yenileme 429 ya da kimlik hatasinda kalan enstrumanlar icin istek gondermeyi birakir.
- **I10** Her 5 dakikada bir ve olay akisi her yeniden baglandiginda REST ile mutabakat yapilir (sunucunun yeniden baglanmada goruntu gonderdigi varsayimina dayanilmaz).
- **I11** sudoers'taki `journalctl ... *` jokeri kaldirildi (root kabuguna cikis yolu).
- **I12** "SL girise cekildi" bildirimi artik broker degisikligi onayladiginda gider; `be_done` de o zaman isaretlenir.
- **I13** Iptal sayilmis bir acma emrinin gec gelen dolumu yine o emre baglanir (bot islemi olarak), `manual` diye ice alinmaz.
- Kucukler: kimlik hatasi tek bildirim + yonetim istekleri 5 dk durur (`auth_error` / `auth_restored`); push verisinde `kind` ezilmiyor (`order_kind`); push gonderimi arka planda (olay islemeyi bekletmez); tarama atlansa da acik islemlerin M15 mumlari guncellenir; kurulamayan emir taramayi durdurmaz; `start_capital` acilista kurulamadiysa sonradan kurulur; `POST /trades` icin istege bagli `client_id` (tekrar gonderimde ikinci emir acilmaz); eksik `instrument_event` katalogdaki sozlesme bilgisini silmez; `python -m tradebot revoke` tum token'lari iptal eder; dagitimdan once V9 paketleri de calisir; acilis deal'indeki komisyon gerceklesen zarara yazilir.
- **Bilerek ertelenenler:** stop sonrasi ayni sembole yeniden giris icin bekleme suresi (Faz 2 sinyal katmani); swap ucretlerinin islem bazinda takibi; token'larin sure sonu; `/pair` kodunun 5 hatali denemeyle yakilabilmesi (API yalnizca 127.0.0.1'de).
- **Ilk canli pozisyonda (en kucuk hacimle) dogrulanacaklar:** PATCH'in verilmeyen alani korudugu (I7), dolum olayinin SL/TP emrini tasidigi (I6), kimlik ve durum bicimleri (I4), yeniden baglanmada goruntu gelip gelmedigi (I10), cent hesapta `contract_size` carpani.

## Ikinci bagimsiz dogrulama (2026-11-25) ve duzeltmeler
Ikinci inceleme ilk turdaki bulgulari dogruladi (I6 ve I13 kismi), yeni kritik bulmadi, duzeltmelerin kendisinde 6 onemli sorun (N1–N6) buldu. Hepsi duzeltildi; testler `tests/test_review_fixes.py` sonunda.
- **N1** Stop korumasi dogrulama (anlik goruntu) basarisiz olsa da emir gonderiyordu → dogrulanamadiysa hicbir sey gonderilmez ve kontrol hakki harcanmaz.
- **N2** Eksik stop ilk (−1R) seviyeye kuruluyor ve TP dusuyordu → `trades.last_sl` (broker'in son onayladigi SL) ve `trades.planned_tp` ayri sutunlarda tutulur; stop, son onayli SL ile ilk SL'den iyi olanina, TP ile birlikte yeniden kurulur (kullanici stopu elle degistirdiyse onun son degeri). 3 basarisiz denemeden sonra pozisyon kapatilir. `sl_missing` olayi her denemede degil, ilk tespitte ve kapatmada uretilir. Stop korumasi dry-run'da da calisir; artik stopu gevsetmez.
- **N3** Bot pozisyonu `manual` olarak ice alinabiliyordu → (a) birakilmis ya da pozisyonsuz tamamlanmis acma emirleri de eslestirilir (pozisyon emirden sonraki 5 dk icinde acildiysa); (b) mutabakatin `manual` yazdigi pozisyon, olay emrin kimligiyle gelince bot islemine cevrilir; (c) operasyonu onaylanmis emir asla iptal sayilmaz (15 dk sonra izi hala yoksa uyariyla kapatilir); (d) pozisyon tasimayan dolum olayi emri tamamlanmis saymaz.
- **N4** Kor donemde kapanmis pozisyonun kaydi icin artik hacmin tamamini kapatan deal'ler sart; operasyon onaylanmadiysa yalnizca emirden sonraki 30 sn icindeki acilis eslesir (kullanicinin elle islemi bota yazilmaz).
- **N5** Kimlik kilidi: bekleme 30 sn'den baslar, art arda retlerde 5 dk'ya kadar katlanir; basarili herhangi bir imzali istek kilidi acar (`ExnessClient.last_ok_at`); uyari 1 saat sonra yeniden verilebilir; operasyon sorgusu ve mutabakattaki kimlik hatalari da ayni yoldan gecer.
- **N6** Kapanis deal'i olmadan "pozisyon yok" → en az 60 sn arayla iki gozlem sart (tek bos goruntu hicbir islemi kapatmaz); deal'i bulunamadan kapatilan islem icin gecmis 24 saat boyunca yeniden aranir ve kar/zarar sonradan yazilir.
- **I7 icin tespit eklendi:** yalnizca SL gonderilen bir degisiklikten sonra broker'daki TP kaybolursa `tp_lost` olayi/bildirimi uretilir ve TP yeniden kurulur.
- Kucukler: operasyon kaydi bulunamayan (404) degisiklik "onaylandi" sayilmaz, basa bas yalnizca broker'daki SL istenenle ayniysa duyurulur; dolum olayi SL'i tasimadiysa mutabakat bunu kullanici degisikligi saymaz; eksik `instrument_event` artik sembolu kapatmaz (yok sayilir); kucuk genel limitlerde de emirler icin en az 1 istek ayrilir; ayni `client_id` ile tekrar gelen elle islem ilk emrin degerlerini dondurur; kapanista bildirimler tamamlanir; ATR 3 mumdan eskiyse iz surme yapilmaz; mevcut veritabanlari icin sutun gocu (`ALTER TABLE`).
- **Not:** Bu ikinci tur duzeltmeler ucuncu bir bagimsiz incelemeden gecmedi. `dry_run=false` oncesinde, kesif ciktisiyla yapilacak sema duzeltmeleriyle birlikte yeniden incelenmeli.

## Faz 1 durumu
Kod tarafi tamam (Task 1–14 adim 5). Kullanicidan beklenenler:
1. Repo push yetkisi (Claude GitHub App) — commit'ler yerelde.
2. VPS kurulumu ve GitHub Secrets (`trade-bot/deploy/README.md`).
3. VPS'te `python -m tradebot.discover` ciktisi → fixture'lar ve sema gercek yanitlara gore guncellenecek (Task 4 adim 4).
4. Dry-run ozeti sonrasi ilk gercek emir icin onay (Task 14 adim 7).

## Faz 2 (plan: `docs/superpowers/plans/2026-11-25-trade-bot-faz2.md`)
- Kontrolcu kararlari (2026-11-25): Faz 1 `main`'e birlestirildi; disa acilis alan adsiz ve Tailscale'siz, Caddy + Let's Encrypt ile `https://<IP>.sslip.io`; sunucu kurulumu tek komut (`deploy/bootstrap.sh`).
- Task 1: `setup-https.sh` Caddy'yi kurar ve yalnizca `127.0.0.1:8090`'a vekillik eden bir Caddyfile yazar (erisim logu yok: `/stream` token'i diske dusmesin; admin API kapali; 64 KB govde siniri; HSTS). Genel adres `/etc/tradebot/public-url` dosyasina yazilir. `tradebot-pair` komutu (`/usr/local/bin`) eslestirme kodunu ve adresi gosterir.
- `bootstrap.sh` kesfi servisten ONCE calistirir ve o sirada servisi durdurur: WebSocket baglanti siniri ve istek kotasi ortak. Exness degerleri gorunmeden okunur, 128 hex anahtar gercek Ed25519 dogrulamasindan gecer, env dosyasina yalnizca guvenli karakterler yazilir.
- **VPS'te dogrulanacak:** `sslip.io` icin Let's Encrypt sertifikasinin alinabildigi (hiz siniri) ve 80/443'un disaridan erisilebildigi.
- Task 2: Haber vetosu bot katmaninda uygulanir, V9'un `information_provider` yolu KULLANILMAZ: V9 `MacroEvent` yalnizca USD/EUR/GBP/JPY kabul eder (AUD, CAD, CHF, NZD haberleri temsil edilemez) ve V9 degistirilemez. Pencere icindeki sembol analiz edilmeden atlanir (`ScanSummary.news_blocked`), bildirim uretilmez.
- Takvim kaynagi `nfs.faireconomy.media/ff_calendar_thisweek.json`; 6 saatte bir yenilenir, basarisiz denemeden sonra en erken 15 dk'da yeniden denenir, SQLite'ta saklanir. Saat dilimi (ofset) tasimayan kayit kullanilmaz. Bos ya da taninmayan yanit mevcut takvimi silmez. 24 saattir alinamiyorsa gunde bir `news_unavailable` uyarisi gider; bot calismaya devam eder (spec §6.6).
- Ayar: `news.enabled` (varsayilan acik), `news.window_minutes` (varsayilan 30, aralik 5–120). `GET /news` onumuzdeki yuksek etkili haberleri dondurur.
- Task 3: Guven puani = `100 × Σ wᵢ·sᵢ / Σ wᵢ` (destek 1, cekimser 0.5, karsi 0). Moduller: `mtf`, `regime` (agirlik 2), `candle_pattern`, `chart_pattern`, `structure`, `momentum`, `confluence`, `other_strategies`, `session` (agirlik 1). Hepsi V9 raporunu okur; V9'a dokunulmaz. Carpanlar sabit (0.5 / 0.75 / 1.0), esikler ayarlanir (`fusion.min_score/mid_score/high_score`).
- Puan riski yalnizca azaltir: lot adima ASAGI yuvarlanir; en kucuk lotun altina duserse islem acilmaz ve `signal_observed` olayi yazilir (yukari yuvarlama yok). Sira: V9 adayi → puan → portfoy kapisi → emir. `trades.score` ve `trades.votes_json` dolumda emir kaydindan yazilir.
- Seans oyu: forex/metal icin Londra ya da New York acikken destek, yalnizca Asya'da cekimser, seans disinda karsi; kripto cekimser.
- Task 4: Strateji kipleri `strategy_modes` (`live` / `shadow` / `off`; listede olmayan `live`). Eski `enabled_strategies` alani gecerli kalir: listede olmayan strateji `off` sayilir; acik kip onceliklidir.
- `evaluate_all`: V9'un sectigi strateji sonraki bir kapidan gecemezse, ayni anda CONFIRMED olan diger stratejiler tek tek yeniden degerlendirilir (en cok 3 ek analiz). Ters yonlu onayda ya da V9 hic secim yapmadiysa yeniden deneme yapilmaz (sert veto delinmez). Sembol basina en cok bir aday doner.
- Golge islemleri (`shadow_trades`): golge kipindeki stratejinin adayi ve puani esigin altinda kalan aday emir acmaz, sanal olarak izlenir. Sonuc kapanmis M15 mumlarindan: once stop (ayni mumda ikisi de varsa stop sayilir), sonra TP1 (2R); 96 mumda sonuclanmazsa son kapanisa gore R. Gercek islemdeki kismi kapama + iz suren stop modellenmez; golge R'si yaklasik bir gostergedir.
- Task 5: Karne `GET /scorecard`: strateji basina canli (islem, kazanma orani, ortalama R, kar faktoru) ve golge sonuclari; modul basina destek/karsi/cekimser oylarinin sonuclari. R = gerceklesen kar/zarar ÷ giristeki risk tutari; riski bilinmeyen ve elle acilan islemler karneye girmez.
- Otomatik duraklatma: canli kipteki strateji ≥ `fusion.pause_min_trades` (20) islemde ortalama R < `fusion.pause_avg_r` (0) ise kipi `shadow` yapilir (kalici), `strategy_paused` bildirimi bir kez gider. Duraklatilan strateji golgede izlenmeye devam eder (plan "duraklat" diyordu; kapatmak yerine golgeye almak, geri acma karari icin veri uretir).
- Geri acma: `POST /strategies/{id}/mode {mode: "live", confirm: true}` (onaysiz 409) ya da `PUT /settings`. Her iki yolda da karne denetimi o andan sonraki islemlerle yeniden baslar; yoksa strateji eski karnesi yuzunden hemen yeniden duraklatilirdi.
- Modul agirliklari otomatik degismez (spec §6.2); karne yalnizca gosterir.
- Kontrolcu kararlari (2026-11-25, ek): (1) Stop korumasi dry-run'da da acik kalir (yalnizca botun/uygulamanin actigi pozisyonlar icin). (2) Ucuncu bagimsiz inceleme, kesif ciktisiyla yapilacak sema duzeltmeleriyle birlikte ve ILK GERCEK EMIRDEN ONCE yapilir. (3) Exness API anahtarinin IP beyaz listesine sunucu IP'si eklendi; ozel anahtar kullanicida.
- `setup-https.sh` adresi tireli bicimde uretir (`a-b-c-d.sslip.io`); noktali bicim (`a.b.c.d.sslip.io`) de ayni adrese cozulur. Sertifika tireli ad icin alinir; uygulamaya kurulum sonunda yazilan adres girilmelidir.


## İlk canlı keşif (2026-11-25) ve düzeltmeler

- Gerçek yanıtlar `tests/exness/fixtures/real/` altında (hesap no maskeli); ayrıştırıcılar değişmeden geçti. Cent hesap: semboller eksiz (`EURUSD`), EURUSD `contract_size` 1000, para birimi USC, evren 30 enstrüman.
- WebSocket: sunucu `exness-ws-protocol` alt-protokolünü seçiyor; istemci artık öneriyor (`schema.WS_SUBPROTOCOL`).
- Mum: 9 istekten yalnızca ilki `AUTH_INVALID_API_KEY` (1000) ile reddedildi → `CandleStore._fetch` yalnızca bu kodda bir kez yineler; REST istemcisi hâlâ hiçbir isteği yinelemez.
- Limitler (gerçek): mum 2 istek/sn, genel 15/sn, emir 4/sn, en çok 5 WebSocket bağlantısı.
- Sermaye tabanı (kontrolcü kararı): deneme modunda geçici (varlığı izler); bot ilk kez canlıya geçtiğinde o andaki varlıktan alınır ve ölçüm o andan başlar (`capital_base_live`). Deneme moduna gidip dönmek tabanı sıfırlamaz. Boş hesapla taban kurulmaz.
- Para yatırma/çekme (`balance` türü deal): bot K/Z'sine girmez; canlı tabanı tutar kadar kaydırır, her deal bir kez (`balance_ops`). Kaynak: olay akışı + 5 dakikada bir deal geçmişi. Tabandan önceki işlemler yalnızca kaydedilir.
- `/health` son taramanın sayılarını verir (hesap bilgisi yok); `deploy/status.sh` ve iş akışının `status` kipi dağıtım sonrası doğrulama içindir.
- Hâlâ gerçek örneği olmayanlar: pozisyon, emir, deal, tick, WS olayları, ACK, operasyon durumu → ilk asgari lot işleminde doğrulanacak.

## Faz 2 bağımsız incelemesi (2026-11-25, sunucu + Android ayrı ayrı)

Sunucu (d6551d9..2fcf2e1) — düzeltilenler, gerileme testleri `tests/test_phase2_review.py` (her biri mutasyonla doğrulandı):
- C1: `PUT /settings` bir stratejiyi canlıya alamaz (409). Önceki karar ("ya da PUT /settings") geri alındı: bayat ayar kopyası botun duraklattığı stratejiyi onaysız açabiliyordu. Tek yol `POST /strategies/{id}/mode` + `confirm`.
- I1: gölge işlem açıldığı mumu da sayar (giriş mum kapanışından 5 sn sonra, yeni mumun içinde).
- I2: aynı sembol/strateji/yön için açık gölge varken yenisi açılmaz; karne gölge sonuçlarını nedene göre ve duraklatmadan sonrası olarak ayırır.
- I3: takvim hiç alınamadıysa hemen (ve her gün) uyarılır; `/news.stale` bu durumda `true`.
- I4: gölgedeki strateji canlı stratejiyi bastırmaz; yalnızca aynı yöndeki canlı aday kabul edilir.
- I5: karne tabanı yalnızca botun duraklattığı strateji yeniden açılınca sıfırlanır.
- Kullanıcı SL/TP (Android C2'nin sunucu tarafı): yanlış taraf ve fiyattan %50'den uzak seviye 422.
- Ertelenen (Minor): haber `country: All` olayları, uzun süre çözülemeyen gölge işlemler için 128 mum sınırı, SELL gölgede spread, `signal_observed` tekrar kaydı, taramada V9 analizlerinin `manage_tick`'e yol vermemesi.

Android (aynı aralık) — düzeltilenler, testler `__tests__/bot*.test.ts(x)`:
- C1 veri hiç alınmadıysa "pozisyon/olay yok" yerine hata + yeniden dene. C2 SL/TP: her değişiklik eski → yeni değerle onaylanır; yanlış taraf ve fiyattan çok uzak seviye gönderilmez; SL uzaklaşıyorsa risk uyarısı. C3 bayatlık bir isteğin bitmesini beklemez.
- I1 kâr al = broker emri (`tp2`). I2 deneme modunda onay metinleri işlemin gerçek olduğunu söyler. I3 bayatken "Çalışıyor"/CANLI gösterilmez. I4 eski bağlantının geç 401'i yeni eşleştirmeyi silemez. I5 değişiklik isteklerinde 502/503/504 ve okunamayan 2xx "sonuç belirsiz". I6 eşleştirme hata metinleri. I7 başka adresten gelen yanıt reddedilir. I8 pozisyon kimliği biçimi serbest. I9 birikmiş olaylar tek özet bildirim. I10 kademeli stop kapatma onaylı. I11 yanıt biçimi doğrulanır.
- Açık kalan: I12 uzak push (FCM yok; kanal kimliği `default` ile hizalandı), uygulama arka plandayken kalp atışı uyarısı gelmez, "Bağlantıyı sil" token'ı sunucuda iptal etmez (`tradebot revoke` ile yapılır).
- Öneri (kontrolcü kararı): `PUT /settings` ile `dry_run: false` geçişi için de açık onay alanı.
- Canlıya geçiş onayı (kontrolcü kararı): `PUT /settings` ile `dry_run: true → false` yalnızca `?confirm_live=true` ile kabul edilir (yoksa 409); gövdeye gömülü onay kabul edilmez. Deneme moduna dönüş onay istemez. Canlıya tekrar dönüşte taban sıfırlanmaz (onaylandı).

## Üçüncü bağımsız inceleme (2026-11-25; ikinci tur düzeltmeleri + canlı keşif düzeltmeleri)

Kritik bulgu yok; "deneme modunda dağıtılabilir". İkinci tur düzeltmeleri (N1–N6) doğru bulundu. Düzeltilenler:
- I-1: stop doğrulaması yapılamadıysa 15 sn sonra yeniden denenir (her 2 sn'lik turda değil; 429'u döngüde yinelemiyoruz).
- I-2: TP geri yüklenirken SL de birlikte gönderilir (verilmeyen alan siliniyorsa stop silinmesin).
- I-4: taban alınırken geçmişteki para yatırma/çekme işlemleri kimlikle "görüldü" işaretlenir (broker/sunucu saat farkı çifte saymaya yol açamaz).
- I-5: taban 0'dan yeniden kurulurken ölçüm başlangıcı korunur (hesabı boşaltıp doldurmak önceki bot zararını silmez).
- I-6: akış beklemesi yalnızca bağlantı 30 sn ayakta kaldıysa sıfırlanır (kabul-et-kapat döngüsü saniyede bir yeniden bağlanmaz).
- I-7: fiyat akışının döndürdüğü hata loglanır; `/health` `last_scan.quoted` (taze fiyatlı sembol) ve `tick_errors` verir.
- I-8: mum servisinin art arda 1000 reddi taramayı bırakır ama yönetim isteklerini kilitlemez (`market_data_rejected`); imza/yetki reddi kilitler.
- I-9: deal geçmişi 29 günle sınırlandı. Ayrıca `has_more` var ama imleç yoksa açık hata.
- Kontrolcü: deneme modunda ilk okunan varlık `capital_seen` olayıyla, para yatırma/çekme `balance_change` olayıyla kayda geçer (biçim `/events` üzerinden doğrulanacak).

İlk gerçek emirden ÖNCE yapılacaklar (inceleme kararı: "henüz değil"):
1. Gerçek fixture'lar: balance deal, pozisyon, sltp emri, deal, tick, WS olayları (I-3, I-10). Deneme modunda terminalden elle 0.01 lot pozisyon açıp `/positions` içinde `sl`/`tp` göründüğünü doğrula; yoksa stop koruması sağlıklı pozisyonu ~96 sn'de kapatır.
2. Kapanan elle işlemde `trade_closed` K/Z'sinin terminaldekiyle (USC, komisyon işareti) aynı olduğunu doğrula.
3. İlk bot emrinde: PATCH verilmeyen TP'yi koruyor mu (I7), dolum olayı sltp emrini taşıyor mu, ACK/operasyon biçimleri, yeniden bağlanmada snapshot, `client_request_id` yankısı.
4. Cuma 21:45 UTC girişleri (kapanıştan 13 dk önce) isteniyor mu: kullanıcı kararı.
- Ertelenen (Minor): WS yönlendirmesinde imzalı başlıklar, hız sınırında pay, seansların yalnızca açılışta okunması (yaz saati), tick aboneliklerinde tek hatalı sembolün grubunu düşürmesi, N5 testlerinin eksikleri.

## Faz 3 (plan: `docs/superpowers/plans/2026-11-25-trade-bot-faz3.md`)

- **Ortak modül arayüzü:** `tradebot/signals/modules/` (`Context`, `Vote`, `Signal`, kayıt defteri). Oy modülleri
  tek tek dosyalara taşındı; eski kodun dondurulmuş kopyasıyla (`tests/signals/legacy_votes.py`) birebir aynı oy
  verdikleri testle doğrulanır. V9 (`trade-ai-unified/`) değişmedi.
- **Yeni stratejiler (varsayılan gölge):** `tb_ema_pullback_v1`, `tb_donchian_breakout_v1`. `tb_` önekli her
  strateji varsayılan olarak gölgededir; canlıya yalnızca `POST /strategies/{id}/mode {mode: live, confirm: true}`
  ile ve gölge karnesi olumluysa alınır. `PUT /settings` hiçbir stratejiyi canlıya alamaz.
- **API:** `GET /strategies`, `POST /trades/preview`, `GET /symbols`, `POST /trades/{client_id}/resolve`,
  herkese açık `GET /health/summary` (yalnızca sayılar ve nedenler).
- **Android 0.9.0:** Raporlar, Ayarlar ve Elle işlem ekranları; APK iş akışında kalıcı anahtarla imzalama adımı
  (Secret'lar tanımlıysa).

### Canlı dry-run bulgusu: hiç aday çıkmıyordu (PR #7)

İlk canlı özet 15 taramada 0 aday gösterdi; son taramada 30 sembolün 29'u V9'da `stale tick` ile elenmişti.
Neden: tarama başlangıç saati bütün semboller için V9'a "şimdi" diye veriliyordu; mumlar istek limitiyle ~1
dakikada çekilirken canlı fiyat bu saatten 5 saniyeden fazla ileride kalıyordu. Düzeltme: her sembol kendi anında
değerlendirilir. Ders: "30/30 tarandı" sayısı sinyal üretildiğini göstermez; özetin karar/neden dağılımına bakılır.

### Faz 3 bağımsız incelemesi (2026-11-25, sunucu + Android ayrı ayrı) ve düzeltmeler

Sunucu:
- **K1 bayat fiyatla lot:** yeni stratejiler giriş/lotu son tick'ten hesaplıyordu, tick'in yaşına bakmadan. 2 saatlik
  fiyatla stop mesafesi küçülüyor, lot bütçenin ~10 katına çıkıyordu. Artık fiyat 60 sn'den eskiyse (ya da
  gelecekten görünüyorsa) aday yok; V9 aynı sembolde `STALE_DATA`/`PROVIDER_UNAVAILABLE` dediyse de yok. V9 raporu
  yoksa ya da `INSUFFICIENT_DATA` ise canlı strateji de yalnızca gölgede izlenir.
- **K2 özetten varlık çıkarımı:** herkese açık örneklerde lot + stop % + risk % birlikte hesap varlığını %0,04
  hatayla veriyordu. Örneklerden **lot kaldırıldı** (yetkili API'de duruyor); neden metinlerindeki sayılar `#` olur.
- **Ö1** Canlıya alma eşiği ayarla düşürülemez: `max(20, pause_min_trades)`.
- **Ö2** Botun duraklattığı strateji eski karnesiyle değil, duraklatmadan SONRAKI gölge sonuçlarıyla değerlendirilir.
- **Ö3** Elle işlem: lot adım ızgarasında değilse 422 (gönderimde yukarı yuvarlanıyordu); risk uyarısı her zaman
  ayarlardaki sınıra göre (`settings_risk_pct`), istekteki `risk_pct` uyarıyı susturamaz.
- **Ö4 (bilinçli davranış değişikliği):** `POST /trades` artık lot açıkça verilse de hesap durumu ve dönüşüm kuru
  bilinmeden emir göndermez (zarar hesaplanamayan emir gönderilmez).
- **Ö5 küçük hesap:** risk bütçesi en küçük lota yetmiyorsa önizleme reddetmez; en küçük lotu ve gerçek zararı
  uyarıyla gösterir. Emir, lot açıkça verilmeden (kullanıcı o sayıyı görüp onaylamadan) gönderilmez.
- **Ö6** Yeni strateji adaylarında komisyon riske ve net R/R'ye dahil; en büyük lot adıma aşağı yuvarlanır;
  yeni stratejilerdeki beklenmeyen hata taramayı düşürmez.
- **Ö7** Gölge SELL sonuçları spread kadar iyimserdi (mumlar bid, SELL ask ile kapanır): açılıştaki spread kaydedilir
  (`shadow_trades.spread`), stop/hedef denetimi ona göre kaydırılır.
- **Ö8** Eksik testler eklendi (giriş tarafı, yuvarlama yönü, en küçük lot, canlı eşiği, komisyon); 15 mutasyonun
  hepsi testlerce yakalanıyor.

Android:
- **K1** Geç gelen önizleme başka sembol/yöne yapışabiliyordu: yanıt yalnızca kendi isteğiyle eşleşirse kullanılır,
  istek sürerken girdiler kilitli, onay metni önizlemenin kendi sembol/yönünden yazılır.
- **K2/K3** "Sonucu kontrol et" emri yeniden gönderiyordu (ulaşmamışsa O AN açardı) ve kesin görünen bir hata kilidi
  kaldırıyordu. Artık `POST /trades/{id}/resolve` yalnızca sorar: kayıt varsa durumunu döner, yoksa kimliği geçersiz
  kılar (yolda kalmış istek sonradan ulaşsa da 409). Kilit yalnızca sunucunun kesin yanıtıyla kalkar.
- **Ö1** Belirsiz emir kilidi cihazda saklanır; ekran/uygulama kapanıp açılsa da sürer.
- **Ö2** `REJECTED`/`UNKNOWN`/`PENDING` durumları "gönderildi" diye gösterilmez.
- **Ö3** Değişiklik isteklerinde her 5xx ve 408 "sonuç belirsiz" sayılır.
- **Ö4/Ö5** Çift onay tek kimlik üretir; önizleme 60 sn sonra eskir, seviyeler "yaklaşık" yazılır.
- **Ö6/Ö7** Ayarlar: yazılan değerler yeniden yüklemede silinmez; okunamayan ayarın üstüne kayıt yapılmaz; sunucudaki
  değer onaylanan "eski" değerden farklıysa yazılmaz.
- **Ö8/Ö9/Ö10** Hatalar uyarı penceresiyle de gösterilir; Raporlar/Ayarlar'da "Yenile" ve son güncelleme saati;
  canlıya alma onayında gölge karnesi, duraklatma ve deneme modu bilgisi.
- **Ö12/Ö13** İmzalama: yarım yapılandırma hata verir; README, yedek anahtarın herkesçe bilinen test anahtarı
  olduğunu yazar.

Bilerek ertelenenler: Ayarlar'da orta/yüksek puan eşikleri, kademeli stop anahtarları ve sembol seçimi; elle işlemde
risk % girişi; dry-run'da aynı sembolde V9 + yeni strateji adayının ikisinin de `would_open` sayılması (canlıda
ikincisini sembol kapısı engeller); `scan_summary` için `events.at` dizini; sinyal mumundan uzaklaşmış fiyatta
giriş ("kovalama") sınırı.

### Canlıya geçmeden / yeni strateji canlıya alınmadan önce

- İmzalı APK için dört Secret (README) ve gerçek telefonda kurulum denemesi.
- Yeni stratejiler en az 20 sonuçlanmış gölge işlem ve pozitif ortalama R olmadan canlıya alınamaz (sunucu zorlar).
- Yukarıdaki "İlk gerçek emirden ÖNCE yapılacaklar" listesi geçerliliğini korur.

### V9 hafta sonu boşluğu düzeltmesi ve V9 kuralının güncellenmesi (2026-11-25, kullanıcı onayıyla)

- PR #7'den sonra canlı özette 30 sembolün 28'i `missing candle during open or unknown broker hours` ile eleniyordu.
  V9, açılıştan önceki 30 dakikayı (`OPENING_SOON`) "kapalı" saymadığı için hafta sonu boşluğu içeren her H1
  serisini reddediyordu; H1'de 256 mum her zaman bir hafta sonu içerir. Düzeltme: boşluk denetiminde `OPENING_SOON`
  da kapalı sayılır (`trade-ai-unified/vendor/day_trader/forex/contracts.py`, tek satır). İşlem kapıları değişmedi.
  Regresyon: `tests/signals/test_weekend_gap.py` (gerçek Exness oturumları + boşluklu mumlar).
- **Kural güncellendi (spec §11):** V9 geliştirilebilir. Risk/maliyet kapılarını (net R/R ≥ 1.5, SL zorunluluğu,
  lot/risk sınırları) gevşeten değişiklikler test + bağımsız inceleme + kullanıcı onayı ister. Önceki kayıtlardaki
  "V9 değiştirilemez" ifadeleri bu kararla geçersizdir.
- Ders: sahte borsa verisinde hafta sonu boşluğu yoktu; gerçek veriye özgü biçimler (boşluk, oturum saatleri) için
  testler gerçek keşif verisinden türetilmeli.

### Faz 3'te ertelenen ayarların tamamlanması (2026-11-25, Android 0.9.1)

- **Kademeli stop anahtarları:** `manage.be_enabled / partial_enabled / trail_enabled` (varsayılan açık). Kapatılan
  aşama atlanır; broker tarafındaki ilk stop her zaman yerinde kalır. Kısmi kapatma kapalıyken iz süren stop aynı
  eşikte (`partial_at_r`) başlar. Karar: anahtarlar "koruma" sayılır, kapatmak uygulamada "risk artar" uyarısı verir.
- **Sembol seçimi:** `PUT /settings` bilinmeyen sembolü ve boş listeyi reddeder (boş liste yerine Durdur). Listede
  kalmış, artık evrende olmayan eski sembol başka ayarın kaydını engellemez. Uygulamada evrenin tamamı seçiliyse
  `null` (hepsi) yazılır; böylece broker'a sonradan eklenen semboller de açık kalır.
- **Orta/yüksek puan eşikleri:** uygulamada düzenlenir; sıra (en düşük ≤ orta ≤ yüksek) hem uygulamada hem sunucuda
  doğrulanır. Eşiği düşürmek "risk artar" sayılır (aynı puanla daha büyük lot).
- **Elle işlemde risk %:** yalnızca önizlemede lot önermek içindir (0,05–2); emirde her zaman önizlenen lot gider.
  Ayardaki sınırın üstündeyse sunucu uyarır ve uyarı onay penceresinde tekrarlanır.

### PR #10 bağımsız incelemesi (2026-11-25)

Kritik bulgu yok: üç anahtarın 8 birleşimi, AL/SAT, rastgele fiyat yürüyüşleri ve işlem ortasında anahtar
değişimiyle ~1,4 milyon `decide` çağrısında stopu gevşeten, kaldıran ya da yanlış tarafa koyan tek hareket çıkmadı.
Düzeltilenler:
- **Sürüm geri alma:** yeni sürüm ayarlara yeni alanlar yazıyor; eski sürüm bunları reddedip açılamazdı. Ayar
  yükleme artık yalnızca TANINMAYAN alanları yok sayar (başka her bozuk değer yine hata). Not: bu koruma bu
  sürümden itibaren geçerlidir; **bu sürümden öncesine (a25d0eb ve eskisi) geri dönmek** için `bot_settings`
  kaydındaki `manage.*_enabled` anahtarları elle silinmelidir.
- **Sembol listesi:** başka bir ayarı kaydetmek, sunucudaki açık listeyi "hepsi"ye çevirebiliyordu (evren tam o
  listeye daraldığında). "Hepsi"ye çevirme artık yalnızca kullanıcı sembolleri değiştirdiyse yapılır; yeni sembol
  açmak "risk artar" diye işaretlenir.
- Eksik testler eklendi: SAT tarafı, 2R'nin altına geri dönüş, işlem ortasında anahtar değişimi, eski/yeni ayar kaydı.
Bilinen, bilerek bırakılan: kısmi kapatma kapalıyken iz süren stop fiyat 2R'nin altına inince bekler (stop yerinde
kalır); anahtar etiketlerindeki "1R/2R" sabit yazıdır (eşikler sunucuda değiştirilirse etiket güncellenmez).

## Faz 4 (plan: `docs/superpowers/plans/2026-11-25-trade-bot-faz4.md`)

- **Karar: bakım işleri bot sürecinin içinde.** Dağıtım kullanıcısının yetkisi yalnızca servisi yeniden başlatmak;
  root gerektiren systemd zamanlayıcıları kullanıcıya yeni sunucu adımı açardı. Yedek ve temizlik bu yüzden botun
  içinde, yalnızca `/var/lib/tradebot` altına yazarak çalışır.
- **Günlük yedek:** `sqlite3.Connection.backup()` ile tutarlı kopya, ayrı bağlantı ve ayrı iş parçacığı; geçici
  dosya → `quick_check` → yerine taşıma; kip 600; en yeni 14 yedek. Hata botu durdurmaz, günde bir kez bildirilir.
  `/health.last_backup_at`.
- **Temizlik:** 60 günden eski `scan`, `scan_skipped`, `signal_observed` (yalnızca `info` düzeyi) silinir; işlem,
  emir, ayar, uyarı ve hata kayıtları silinmez. Günlük `wal_checkpoint(TRUNCATE)`; `events(at)` dizini.
- **Hesap durumu:** hesap ayarları her mutabakatta (5 dk) yeniden okunur; "yalnızca kapat"/marjin kısıtı yeniden
  başlatma beklemeden fark edilir (tek uyarı, düzelince tek bilgi). Önceden yalnızca açılışta okunuyordu.
- **Saat kayması:** tick saati sunucu saatinden 5 sn'den fazla ilerideyse tek uyarı (V9 böyle veriyi reddeder).
- **Günlükler:** journald saklar ve döndürür; `deploy/journald-tradebot.conf` yeni kurulumlarda kendiliğinden,
  mevcut sunucuda isteğe bağlı iki komutla kurulur (kılavuzda). Günlük ve olay kayıtlarında sır bulunmadığı
  uçtan uca testle doğrulanır.
- **Hata senaryosu testleri:** broker yeni pozisyonu reddederse emir yinelenmez; kısmi dolum gerçek hacimle
  kaydedilir ve SL yerinde kalır; veritabanı yazılamıyorsa emir gönderilmez; bir zamanlayıcı görevinin hatası
  döngüsünü durdurmaz.
- **Kılavuz:** `trade-bot/README.md` (Türkçe, teknik olmayan kullanıcı için).
- Yapılmayan (plandaki Task 4/6. madde): "uzun kesinti sonrası açılış" için ayrı test yazılmadı; mevcut yeniden
  başlatma testleri (açık pozisyonla açılış, kapalıyken stop tetiklenmesi) ve boşluk onarımı bu alanı kapsıyor.

### Faz 4 bağımsız incelemesi (2026-11-25) ve düzeltmeler

İşlem yolu sağlam çıktı (yedek sırasında 139 bin yazmada kilit hatası yok, en uzun duraksama 48 ms). Düzeltilenler:
- **K1 geri yükleme talimatı işe yaramıyordu:** servis durunca eski veritabanının `-wal` dosyası diskte kalıyor ve
  kopyalanan yedeğin üstüne yeniden oynatılıyordu. Kılavuz artık eski dosyayı kenara alıp `-wal`/`-shm`'yi siliyor;
  geri yüklemenin kipi, sonradan açılan işlemleri ve iptal edilmiş telefon bağlantılarını nasıl etkilediği yazıldı.
- **Ö1** Yedek parça parça kopyalanıyordu; arada her yazmada baştan başlayıp yoğun yazma altında hiç bitmeyebilirdi.
  Tek adımda (`pages=-1`) alınıyor; yazma sürerken bittiği testle doğrulanır.
- **Ö2** Yeni uyarılar (`backup_failed`, `account_blocked`, `clock_skew`, `loop_failing`) uygulamada bildirim
  üretmiyordu ve etiketsizdi; eklendi. Kılavuzdaki "bildirim gelir" ifadesi gerçeğe göre düzeltildi.
- **Ö3** Kılavuz: deneme modunda açık bot işlemlerine kademeli stop uygulanmadığı yazıldı.
- **Ö4** Tek bir ileri tarihli tick "saat kaymış" uyarısı üretiyordu; fark art arda iki kalp atışında sürmeli.
- **Ö5** Biçimi bozuk hesap yanıtı iyi kopyanın yerine geçip hesap durumunu donduruyordu; önce doğrulanıyor.
- **Ö6** Bir zamanlayıcı görevi art arda 5 kez hata verirse tek `loop_failing` uyarısı; sürekli hata günlüğü
  doldurmaz. `status.sh` yedek 36 saatten eskiyse uyarır.
- **Ö8** Yedekten önce boş alan denetimi (veritabanının 2 katı + 50 MB); hata günlüğüne dosya yolu yazılmaz.
Bilinen, bırakılanlar: disk tamamen doluyken olay kaydı da yazılamadığı için uyarı üretilemez (tek işaret
uygulamadaki "bottan haber yok"); sunucu saatinin İLERİDE olması algılanmıyor; `systemctl stop` süreci temiz
kapatmıyor (WAL diskte kalır — veri kaybı yok, geri yükleme talimatı bunu hesaba katar); sürüm satırı commit
bilgisini içermiyor; kısmi dolumda `risk_amount` planlanan tutarda kalıyor (R istatistiğini hafif kaydırır).

### V9: devir saatindeki tek eksik M15 mumu (2026-11-25, kullanıcı onayıyla — A seçeneği)

- Boşluk onarımı (PR #12) sonucu: USDJPY, CHFJPY, EURCHF, GBPCHF'de gece 22:00 UTC devrindeki eksik M15 mumu
  **borsada da yok** (o 15 dakikada hiç fiyat gelmemiş; Exness saati "açık" beyan ediyor). V9 bu sembolleri eksik
  mum 64 saatlik pencereden çıkana kadar reddediyordu.
- Karar (kullanıcı): V9, açık saatte tek mumluk boşluğu hoş görür. Sınırlar
  (`trade-ai-unified/vendor/day_trader/forex/contracts.py`), hepsi birlikte sağlanmalı: işlem saati durumu
  gerçekten AÇIK; yalnızca M15; boşluk tam bir mum; eksik mum New York saatiyle 16:00–17:59 arasında (günlük devir,
  yaz/kış saatine uyumlu); seri başına en çok 4; boşluktan sonra en az 16 mum gelmiş olmalı. H1/H4/M5'te, art arda
  iki mumda, devir saati dışında, yakın zamanda ya da 5+ boşlukta ret sürer. İşlem kapıları (seans, spread, net R/R,
  risk) değişmedi; ATR(14) ve stop mesafesi etkilenmez (boşluk ATR penceresinin dışında kalır).
- Bağımsız inceleme (kritik yok) sonrası eklenenler: "açık" durumu ve devir saati koşulu (ilk sürüm okunamayan
  saatlerde ve günün herhangi bir saatinde de hoş görüyordu); boşluk onarımı artık V9 reddetmese de çalışır ve
  başarısız istek "denendi" sayılmaz (borsada aslında var olan bir mum sessizce eksik kalmasın); kalıcı devir
  boşluğu aynı semboldeki sonraki gerçek eksiği gizlemez. Testler güçlendirildi: 10 mutasyonun hepsi yakalanıyor
  (ilk sürümde "iki gece" doğrulaması boşa çalışıyordu).
- Sonuç: devirden etkilenen sembol devirden sonraki 4 saat analiz dışı kalır, sonra geri döner (önceden 64 saat).
- Testler: `tests/signals/test_weekend_gap.py` (gerçek Exness saatleriyle uçtan uca ve sınır değerleriyle).

### Faz 4 düzeltmelerinin ikinci bağımsız incelemesi (2026-11-26)

Kritik bulgu yok. Düzeltilenler:
- **Gölge sonuçları uzun kesintide yanlış kaydediliyordu (gerçek hata):** sanal işlemler yalnızca son 128 mumla
  (32 saat) sonuçlandırılıyordu; daha uzun kesintide stopa değen mum pencerenin dışında kalıyor, işlem 0R ya da
  kazanç diye yazılabiliyordu. Bu, stratejileri canlıya almanın dayandığı karneyi bozar. Artık açılıştan bugüne
  bütün mumlar kullanılır (önbellek 1500 tutar); geçmiş yetmiyorsa işlem tahmin edilmez, sonuçsuz silinir.
- **Stop yönetiminde işlem başına yalıtım:** bir işlemdeki hata döngüyü kesiyor, sonraki işlemlerin stopu
  ilerlemiyordu. Her işlem ayrı korunur; hata yine yukarı bildirilir.
- **Süren görev hataları:** tek uyarı yerine gün aşırı yinelenir; tarama döngüsü de sayılır; `/health`
  `failing_loops` alanında ve `status.sh` çıktısında görünür.
- **Yedek:** yoldaki `#`/`?` karakterleri URI'yi kesip boş bir dosyayı "yedek" saydırabiliyordu; yol kaçışlanır ve
  kopyada botun tabloları aranır. Önceki günden kalan yarım dosyalar silinir; boş alan hesabına WAL dahil.
- **Kılavuz:** geri yüklemenin kilidi ve kayıp sayaçlarını da geri aldığı, yedeğin günün başını tuttuğu, yedekleri
  listeleme komutu, `.eski` dosyası; deneme modunda stopsuz pozisyon korumasının çalıştığı yazıldı.
- Küçükler: tanılama notu yalnızca "eksik mum" retlerine eklenir; eşleştirme betiği doğru ekranı söyler; üç olay
  türüne uygulama etiketi.
Açık öneri (kullanıcı kararı): veritabanındaki son kayıt çok eskiyse (geri yükleme ya da uzun kesinti) botun
"durdurulmuş" başlaması. Güvenli yönde bir davranış değişikliği; onaysız yapılmadı.
Bilinen, bırakılanlar: `pages=-1` düzeltmesini kıran bir test yok (zamanlamaya bağlı); sunucu saatinin İLERİDE
olması algılanmıyor; hata yollarındaki gizli bilgi kalıpları `test_log_secrets`'te sınanmıyor.

Üçüncü (odaklı) inceleme sonrası eklenenler (kritik yok; stop yönetimindeki yeniden düzenlemenin hatasız durumda
öncekiyle birebir aynı davrandığı satır satır doğrulandı): düzelen bir görev bir saat sonra yeniden bozulursa uyarı
24 saat beklemez; sürekli bozuk bir işlem günlüğe her 2 saniyede iz yazmaz (ilk görülüşte bir kez); gölge işlemde
mum listesinin ortasında 5 günden uzun veri boşluğu varsa da sonuç tahmin edilmez; kılavuzda geri yüklemeden sonra
başlatma anı için uyarı.

## Dry-run gözlemleri

Kaynak: `deploy-trade-bot.yml` (`mode: status`) çıktısındaki `saglik:` ve `ozet:` satırları (son 24 saatlik pencere).
Yalnızca sayılar ve nedenler; hesap bilgisi yok.

### 2026-11-26 06:31 UTC (gece / Asya seansı sonu)

- **Sağlık:** `status: ok`, akışlar bağlı, son tarama 06:30 UTC (30/30 sembol fiyatlı, hata 0), `failing_loops` boş,
  yedek güncel (son yedek 00:08 UTC), `last_data_rejects` boş.
- **Gece (22:48 → 06:31 UTC):** beklenen 31 taramanın 31'i yapıldı; yeni atlanan tarama ya da hata yok
  (özetteki `stream_down: 10` ve `errors: 1` önceki günden, 22:48 okumasında da vardı).
  Aday 9 → 49, "açılırdı" 3 → 7, gölge işlem 3 → 20.
- **24 saat toplamı:** 67 tarama, 1931 sembol değerlendirmesi, 49 aday, 7 açılırdı, 0 emir (deneme modu),
  20 gölge, 12 haber engeli, 0 portföy engeli.
- **Kararlar:** WAIT 1332, STALE_DATA 354, INSUFFICIENT_DATA 229, NO_TRADE 9.
- **Veto nedenleri:** uygun strateji yok 1228; eksik mum 128 (çoğu PR #14 öncesi; son taramada yok); üst zaman
  dilimi yönü/tetik yok ya da çelişkili 86; bayat tick 30; karşıt strateji/fiyat kanıtı 18; `max_spread` eksik 17
  (yeniden başlatma sonrası ısınma); spread politikayı aşıyor 8; yüksek oynaklık 1.
- **"Açılırdı" örnekleri (hepsi net R/R 2.0):**

  | UTC | Sembol | Yön | Strateji | Puan | Stop % | Risk % |
  |---|---|---|---|---|---|---|
  | 25 Kas 20:30 | AUDNZD | SELL | fx_failed_breakout_v6 | 59.1 | 0.076 | 0.24 |
  | 26 Kas 01:30 | GBPCHF | SELL | fx_failed_breakout_v6 | 63.6 | 0.086 | 0.34 |
  | 26 Kas 01:45 | AUDCAD | SELL | fx_failed_breakout_v6 | 63.6 | 0.182 | 0.36 |
  | 26 Kas 03:45 | EURCAD | SELL | fx_trend_momentum_v6 | 90.9 | 0.042 | 0.50 |
  | 26 Kas 03:45 | GBPCAD | SELL | fx_trend_momentum_v6 | 81.8 | 0.042 | 0.49 |

- **Dikkat:** 03:45'teki iki işlem aynı anda, aynı yönde, CAD karşısında ve çok dar stopla (%0.04) çıktı; ikisi
  birlikte ~%1 risk. Portföy engeli devreye girmedi (0). Canlıda birbirine bağlı iki pozisyonun aynı anda açılması
  isteniyor mu, akşam kararında sorulacak. Bu işlemlerin sonucu (ne olurdu) özet uç noktasında yok; gölge karnesinden
  ayrıca okunmalı.

### 2026-11-26 10:10 UTC — "açılırdı" işlemlerin sonucu ve karar

- Kaynak: `/health/outcomes` (`sonuclar:` satırı). "Açılırdı" 8 işlemin 8'i stop oldu (**−8,0R**); hiçbiri 1R'ye
  ulaşmadı (en iyi an: 0,03–0,77R). Gölge (`tb_ema_pullback_v1`): 22 sonuçlanan işlemin 21'i stop, 1 kazanç
  (**−19,0R**). Benzetim kötümser (aynı mumda önce stop), spread'siz; işlemlerin çoğu aynı temaya bağlı (CAD/CHF
  alımı), bağımsız 30 deneme değil.
- 03:45 EURCAD+GBPCAD: canlıda portföy kapısı ikisini de açardı (`per_currency_side` = 2 sabit); o anda GBPCHF de
  açık olurdu → 3 işlem, toplam ~%1,33 risk, üçü de stop. Deneme modunda açık pozisyon olmadığı için portföy kapısı
  hiç sınanmıyor.
- 10 atlanan tarama (25 Kas 11:00–13:30) ve 354 STALE_DATA (25 Kas 13:30–18:00) eski hatalardan; 18:00'den beri sıfır.
- **Karar (kullanıcı + kontrolcü): canlıya geçilmedi.** Önce kök neden.

### Kök neden analizi (26 Kasım, sürüyor)

- Yön ters çevrilmesi yok (sinyal → `Candidate.side` → emir gövdesi aynı); giriş fiyatı doğru (BUY ask, SELL bid,
  sinyal mumunun kapanışına stop mesafesinin −%4…+%19'u kadar yakın).
- **Maliyet kapısı spread'i saymıyor:** `reward_risk_after_costs` yalnızca komisyon ve kaymayı düşer; komisyon 0
  olduğundan "net R/R" her işlemde tam 2,0. Spread fiyata gömülü: bid'in stopa gitmesi için `d − s`, hedefe gitmesi
  için `2d + s` yol gerekir. Spread kapısı (`max_spread`) spread'i yalnızca kendi son 30 dakikasıyla kıyaslar; stop
  mesafesine oranına bakan kural yok.
- Ölçüm: stop çoğunlukla M15 ATR14 × 1,5 (8 işlemin 5'i; diğerleri 2,4–2,7). Gölge işlemlerde girişteki
  spread/stop ortanca **0,16** (0,07–0,33). Yönsüz bir strateji bu oranla işlem başına ~0,16R kaybeder.
- Bu tek başına 21/22 stopu açıklamaz; kenar olup olmadığını ileri test ölçecek.
- Stop sonrası aynı sembole yeniden giriş beklemesi yok (gölgede USDCAD SELL beş kez art arda stop).
- Araçlar: `/health/outcomes` (işlem kuruluşu tanıları), `/health/backtest` + `tradebot/backtest.py` (son 30 günün
  gerçek mumlarıyla V9 oynatması; yalnızca deneme modunda, ayrı düşük öncelikli süreç; eşikler sonuca göre
  ayarlanmaz). Sınırlar: sabit spread varsayımı, mum içi sıra kötümser, haber/puan/portföy kapıları yok.

### İleri test sonucu (26 Kasım 10:37–12:39 UTC; `/health/backtest`, sürüm bt-1)

Son 30 günün gerçek Exness M15/H1/H4 mumları (113 322 mum), canlıdaki V9 değerlendirmesi, kademeli stop kuralları,
sembol başına sabit spread. İki saatlik süre sınırı 30 sembolün 11'ine yetti (7 majör + AUDCAD, AUDCHF, AUDJPY,
kısmen AUDNZD): 22 946 değerlendirme, 0 hata, **171 işlem**.

| | İşlem | Kazanç / başa baş / zarar | Net R | Brüt R (spread'siz) |
|---|---|---|---|---|
| **Toplam** | 171 | 42 / 32 / 97 | **−7,68** (işlem başı −0,045) | **+14,76** (işlem başı +0,086) |
| trend_momentum | 109 | 25 / 18 / 66 | −11,51 | +7,07 |
| failed_breakout | 33 | 8 / 6 / 19 | −2,62 | −2,71 |
| confirmed_breakout | 15 | 5 / 6 / 4 | +7,19 | +8,96 |
| range_reversion | 14 | 4 / 2 / 8 | −0,74 | +1,45 |
| Asya / Londra / New York | 66 / 42 / 63 | | −4,84 / −4,46 / +1,62 | +2,29 / +6,34 / +6,13 |
| AL / SAT | 36 / 135 | | −11,14 / +3,46 | +2,54 / +12,22 |

- Spread/stop ortanca **0,123**; spread'in toplam maliyeti ~22R (işlem başı ~0,13R): brüt küçük artıyı eksiye çeviriyor.
- En iyi an (MFE): 51 işlem 0,25R'ye bile ulaşmadı; 20'si 0,25–0,5R; 26'sı 0,5–1R; 31'i 1–2R; 43'ü ≥2R.
- Stoptan sonraki 2 saat içinde aynı sembole yeniden giriş: 23 işlem, +1,97R (işlem başı +0,086); diğerleri 148
  işlem, −9,65R. Bu veride yeniden girişler daha kötü değil: **bekleme (cooldown) kuralını bu veri desteklemiyor.**
- **Yorum:** 171 işlemde işlem başı ±0,1R dolayında belirsizlik var; net −0,045R da brüt +0,086R da sıfırdan
  ayırt edilemez. Kanıtlanmış bir kenar yok; sistematik bir yön/fiyat hatası da görünmüyor (gece 8/8 stop,
  bu dağılımın kötü ve birbirine bağlı bir kuyruğu). Maliyet kapısının spread'i saymaması gerçek ve ölçülebilir.
- **Sınırlar:** spread sabit (testin başladığı Londra saatindeki değer; Asya ve gece devrinde gerçekte daha geniş
  → maliyet olduğundan az); mum içi sıra kötümser; haber, güven puanı ve portföy kapıları yok; 30 sembolün 11'i;
  tek bir 30 günlük dönem. Hiçbir eşik sonuca göre ayarlanmadı.
- **Öneriler (karar kullanıcıda):** (1) maliyet kapısı spread'i saysın: spread/stop oranına üst sınır ya da net
  R/R'nin spread dahil hesabı (sıkılaştırma; eşik seçimi bir parametre olduğundan onaysız yapılmadı);
  (2) canlıya geçilmesin; (3) ileri test bütün sembollerle ve seansa göre spread'le yinelensin; deneme modundaki
  sinyallerde artık giriş anındaki spread/stop kaydediliyor.
- **İşletme notu:** 13:00:50 UTC'de (tarama sırasında) `/health` 5 saniyede yanıt vermedi; 13:01:56'da normaldi.
  Tarama sırasında olay döngüsünün ne kadar meşgul kaldığı ölçülmeli (stop yönetimi 2 saniyede bir çalışır).

### Yeniden başlatma beklemesi (2026-11-26, kullanıcı kararı)

PR #16 (spread örneklerini saklama) yerine B seçeneği: süreç her başladığında 30 dakika yeni bot işlemi açılmaz;
analiz, gölge kayıtları, açık pozisyon yönetimi ve elle işlemler sürer (`RESTART_ENTRY_PAUSE`, `Bot.entry_paused`).
Bağımsız inceleme: kritik bulgu yok; tek kapı (`_consider`) bütün bot açılışlarını kapsıyor. Bilinen: taramalar
çeyrek saatte olduğu için fiilî bekleme 30–45 dk; deneme modunda her yeniden başlatma o kadar "açılırdı" kaydını
eksiltir; saat ileri sıçrarsa bekleme kısalır (duvar saati kullanılıyor). PR #16 bu kararla gereksiz.
"İlk gerçek emirden ÖNCE" listesindeki 5. madde (spread sınırı kararı) bu kararla kapandı.

## Swing ailesi ve genişletilmiş ileri test (2026-11-26, kullanıcı isteği)

Kaynak: kullanıcının eski masasındaki kurallar; resmi geçmiş testi yok. **Yalnızca gölge kipinde**, canlıya alınmaz.

- `tb_smc_sweep_v1`: günlük yön → H1'de likidite süpürmesi + displacement + yapı kırılımı + Order Block/FVG bölgesi →
  kapanmış M15 tetik mumu. `tb_emapb_h1_20_21_v1`, `tb_emapb_h1_21_50_v1`: günlük yön doğrultusunda H1 EMA
  bölgesine geri çekilme + ret mumu (iki bölge sürümü).
- Ortak kurallar (`strategies/swing_rules.py`): D1 (EMA20/50) + H4 (EMA50) yönü; H1 RSI > 70 / < 30 iken işlem yok;
  stop yapının ötesinde **ve en az 1,5 × günlük ATR**; en yakın karşı günlük dönüş noktasına < 1R ise geç.
- Çıkış planı (`outcome.simulate_swing`): TP1 = 1R'de yarısı kapanır ve stop girişe; ilerleme %60 → stop hedef
  mesafesinin %30'una, %80 → %60'ına; kalan hedefte (1,5 / 2 / 2,5R).
- **Benim yorumumla doldurulan yerler (kullanıcıya soruldu):** TP1 = 1R; kâr kilidi seviyeleri; SMC'de yalnızca
  kapanmış tetik mumu (POI'de limit emir yok); "yer" = karşı günlük dönüş noktası (son 60 gün); POI = Order Block +
  ona bitişik FVG'nin alt yarısı.
- Canlı gölge izlemede bu stratejilerin sanal sonucu düz stop/2R hedefle tutulur (çıkış planı yalnızca ileri testte);
  gölge defteri en çok ~15 günlük mum tuttuğu için daha uzun süren sanal işlem sonuçsuz silinir.
- Bot artık günlük (D1) mumları da önbelleğe alır ve 5 dakikalık spread medyanlarını kaydeder (`spread_stats`):
  ileri testin "saate göre gerçek spread" profili buradan çıkar; bütün saatlerin ölçülmesi için en az 24 saat gerekir.
- İleri test `tradebot/forward.py` (ft-2): 90 gün (ilk 60 iç, son 30 dış örneklem), bütün semboller; swing için
  hedef ve EMA bölgesi iç örneklemde seçilir, dış örneklemde raporlanır; portföy kuralları (günde 5 giriş, art arda
  3 kayıptan sonra o gün giriş yok) ayrıca uygulanır. V9 son 60 günde kendi stopuyla ve 1,5 × günlük ATR stopuyla
  yan yana. V9 pahalı olduğu için süre sınırlıdır; biten semboller saklanır, iş sonraki açılışta sürer.

### Bağımsız inceleme sonrası (ft-3, 2026-11-26)

İnceleme kritik bulgu çıkarmadı: stratejilerde ve oynatmada geleceğe bakma yok (kesilmiş geçmişle aynı sinyaller),
SAT mantığı AL'ın tam aynası, gerçek emre giden yol yok. Düzeltilenler:

- **Testler**: 21 mutasyondan 9'u hayatta kalıyordu (oluşan mumun gösterilmesi, üst zaman dilimlerinin yenilenmemesi,
  giriş mumundan benzetim, AL girişinde spread, SMC SAT stopu, RSI/yer kapıları, geniş stop tabanı, açık işlemlerin
  0 sayılması, geçmişe oluşan mum yazılması). Hepsi için koruma testi eklendi; 15 mutasyonun 15'i artık yakalanıyor.
- **Günlük mumlar**: istek sınırı ve kimlik hatası artık yutulmuyor (taramanın kendi kuralları işler). Son kapanmış
  H4/D1 mumu 4 günden eskiyse swing stratejileri o sembolde çalışmaz (bayat önbellekle sinyal yok).
- **V9 aşaması**: bitmezse aynı geçmişle art arda en çok 6 tur (tur başına 6 saat) sürer, her tur sonunda ara sonuç
  yayınlanır. Yarım kalan işin penceresi saklanır; 3 güne kadar sonraki yeniden başlatmalarda aynı pencereyle sürer.
- **Raporlama**: iç örneklem yalnızca ayrım anından önce KAPANMIŞ işlemlerdir (ayrımı aşanlar `straddle`, iki
  döneme de girmez). Açık kalan işlemler ortalamaya girmez; anlık R toplamı `open_r` olarak ayrıca verilir.
  "Art arda 3 kayıp" kuralı günün kalanını gerçekten kapatır. Seçilen stratejilerin hesap geneli sonucu
  (`portfolio`: günlük sınır ve kayıp serisi hepsine birlikte) eklendi.

Bilinen sınırlar (düzeltilmedi, sonuç okunurken dikkate alınmalı):
- Canlı gölge kaydı en küçük lot risk bütçesini aşan sinyalleri atlar; ileri testte lot denetimi yok. Geniş
  stoplu swing sinyallerinde canlı gölge örneklemi ileri testten dar olabilir.
- Stoplar tam stop fiyatından dolmuş sayılır (boşluk/kayma yok). İlk çalışmalarda spread profili "bugünkü"
  spreadlerdir; saatlik ölçüm biriktikçe iyileşir.
- Geçmiş çekimi ~840 istek; bu sırada canlı taramanın mum istekleri aynı sınırlayıcıda sıraya girer.

## Eski masanın gerçek kodu: v13 hizalaması, WEEK TRADE ve mutlak lot tavanı (2026-11-26, kullanıcı onayıyla)

Kullanıcı eski masanın gerçek dosyalarını gönderdi: `smc.py` (v13 SMC/EMA aday motoru), `ta_engine.py` ve tüm
backtest dökümü. Önceki swing stratejileri (`tb_smc_sweep_v1`, `tb_emapb_h1_*`) bir .docx özetinden YORUMLA
yazılmıştı; onlar karşılaştırma için duruyor, yanlarına gerçek kodun birebir taşınmış hâli eklendi.
**Hepsi yalnızca gölge kipinde; canlıya alınmadı, risk ayarları değişmedi.**

### Yeni gölge stratejiler
| Kimlik | Kaynak | Mum | Çıkış (ileri testte) |
|---|---|---|---|
| `tb_smc_day_v13` | `smc.py` Model 1/3/4 | H1 | Hedef 1'de yarı + stop girişe, kalan Hedef 2; ilerleme kilitleri; en çok 5 gün |
| `tb_emapb_day_v13` | `smc.py` Model 2 | H1 | aynı |
| `tb_smc_week_v13` | `smc.py` Model 1/3/4 | H4 | hedef yok; +1R'de girişe, sonra 4H dönüş noktalarının 0,3 ATR ötesi |
| `tb_emapb_week_v13` | `smc.py` Model 2 | H4 | aynı |
| `tb_week_trade_v1` | belge §2.10 ("yumuşak") | H4 | +1R'de girişe, +2R'de +1R kilit, sonra en iyi − 2 × 4H ATR; 7 günde +1R yoksa çık |

- **Birebirlik kanıtı:** özgün `smc.py` (pandas) ile taşınan kod aynı sentetik veride yan yana çalıştırıldı:
  1408 karar anında geçen adaylar (yön, model, puan, stop, hedefler) aynı. Özgün kodun çıktısı
  `tests/signals/v13_golden.json` olarak saklandı; test her çalışmada karşılaştırır (özgün dosya depoya konmadı).
- **Kaynaktan bilinçli farklar:** veri Exness mumları (256 H1 / 120 H4 / 120 D1); seans saatleri UTC+3 sabit
  kaydırmayla; sabit kodlu "US PMI −5" yok (canlıda botun haber kapısı; geçmiş oynatmada haber takvimi yok);
  "önceki gün" = karar anında KAPANMIŞ son günlük mum (özgün kod İstanbul 00–03 arasında oluşmakta olan günü
  kullanabiliyordu: bakış-öne); Hedef 1 tam 1,5R iken kayan nokta yuvarlamasının işlemi rastgele elemesi
  engellendi (1e-9 pay).
- **Çıkış planlarında yorum olan yerler:** `smc.py` DAY için yalnızca Hedef 1/Hedef 2 verir; yönetim v10 gün içi
  kurallarından alındı (yarı + girişe; %40/%60/%80 ilerlemede girişe / %25 / %50 kilit; 5 gün). v13 WEEK için
  kaynak "4H yapısının arkasından veya 4H kapanışı EMA20 ötesi" der; yapı sürümü uygulandı (EMA sürümü, EMA'ya
  geri çekilmede girilen işlemi hemen kapatırdı).
- **Canlı gölge kaydı** bu stratejileri de botun ortak 2R planıyla izler (kaba ölçüm); kesin ölçüm ileri testtir.

### İleri test ft-4
- Aynı oynatma: eski yorum stratejileri + 5 yeni strateji + V9 (iki stopla). Yeni stratejilerde seçilecek
  parametre yok: iç/dış örneklem yalnızca yan yana raporlanır.
- Strateji başına: işlem, kazanan/kaybeden, net R, **PF**, **en büyük düşüş (R)**, **maliyet/stop** (spread ÷ stop
  mesafesi, medyan), çıkış türleri. Kırılımlar: model, enstrüman türü, kripto hafta sonu / hafta içi, DAY'de tetik
  mumu hacmi (≥ 0,7 × 20 mum ortalaması / altı), WEEK TRADE'de aşırı uzama.
- Geçmiş dosyası artık mum hacmini de saklar. Pencereler canlıyla aynı (256 H1 / 120 H4 / 120 D1).
- Belgedeki ölçütler (karşılaştırma için): WEEK TRADE 2 yıl 182 işlem +21,8R PF 1,44 (XAU +16,4R, EUR −5,7R);
  scalp net −145R (maliyet); BTC gün içi +23R PF 1,34; hafta sonu kripto gün içi pozitif; hacim filtresi gün
  içinde +7R. Bizim test 90 gündür: aynı işaret beklenir, aynı büyüklük beklenmez; 90 günde WEEK işlem sayısı azdır.

### Mutlak lot tavanı (eski masadaki 10 lot kazası için)
- **Bulgu:** bot emirleri risk bütçesiyle boyutlanıyordu, ama ELLE girilen lot yalnızca enstrümanın en büyük
  lotuyla sınırlıydı; bakiyeye bağlı mutlak bir tavan YOKTU.
- **Eklenen:** `Bot.lot_guard` (ayar değil, sabit): tek emirde stopta oluşacak zarar varlığın **%5**'ini,
  pozisyon büyüklüğü varlığın **50 katını** aşamaz; varlık ya da kur bilinmiyorsa emir gönderilmez. Bot emirleri
  ve elle emirler aynı iki yürütücü yolundan geçer, ikisi de tavanı denetler. Önizleme "Bu emir GÖNDERİLEMEZ"
  uyarısı verir. Normal boyutlandırma (risk %0,25–1) bu tavanın çok altındadır.
- Testler: 10 lot elle emir 422 ve broker'a istek yok; bot adayı tavanı aşarsa gönderilmez; tavan bakiyeyle
  küçülür; SAT yönü; dar stopta büyüklük tavanı.
- Eski masa %5 bileşik risk kullanıyordu; bizim risk ayarlarımıza (en çok %1) dokunulmadı.

### Ek 2 (2026-11-26): `bt.py` + işlem listeleri, gölge izleyici kanıtı, kimlik reddi tanılaması

**WEEK TRADE artık `bt.py` ile birebir** (önceki sürüm belge özetinden yazılmıştı; farklar: ATR basit ortalama,
4H'te EMA20 eğimi aranmaz, günlük veri "bir önceki takvim günü", iz süren stopun ATR'si girişte sabit).
- Kanıt: özgün `bt.py` ile taşınan kod aynı sentetik veride (altı sembol, portföy kuralları dahil) çalıştırıldı;
  işlem listesi satır satır aynı (yumuşak 85/85, sıkı 59/59: giriş zamanı, sembol, yön, R, çıkış, neden).
  Referans `tests/week_golden.json`; özgün dosya depoya konmadı.
- Özgün çıktılar doğrulandı: yumuşak 182 işlem +21,79R PF 1,44; **altın hariç 149 işlem +5,36R PF 1,13**; açık
  kalan 3 işlem +3,01R (anlık fiyatla sayılmış). Sıkı 184 işlem +17,25R PF 1,35; altın hariç PF 1,07.
- `tradebot/week_replica.py`: `bt.py`nin portföy döngüsü Exness mumlarıyla 2024-12-15'ten bugüne çalışır
  (ileri test işinin içinde; altı sembol için H4/D1 geçmişi uzun çekilir). İki kip:
  - **bt**: kaynak varsayımlar → kaynak işlem listesiyle karşılaştırma (aynı sembol+yön; giriş aynı / 1 gün içinde).
    Liste `tradebot/data/week_reference.json` (yalnızca zaman, sembol, yön, R, çıkış).
  - **fixed**: düzeltilmiş ölçüm: (a) gerçek Exness spread'i, SAT ask'tan kapanır; (b) ATR girişten önce kapanmış
    mumdan (kaynak giriş mumunu da kullanıyordu); mum stopun ötesinde açılırsa açılıştan çıkılır; (d) açık kalanlar
    toplam dışında. Altın dahil / hariç, 1. yıl / 2. yıl ve sembol bazında ayrı satır.
  - **(c) gecelik faiz:** bu Exness API'sinde enstrüman bazında swap oranı YOK (yalnızca açık pozisyonun birikmiş
    swap'ı var). Taşınan gece sayısı raporlanır ve yıllık %3 / %6 aleyhte faiz varsayımıyla duyarlılık verilir.
    Kaba hesap: stop ≈ fiyatın %1–2'si iken %5/yıl faiz ≈ gece başına 0,01R.
  - Veri kaynağı farkı: kaynak yfinance/Binance (altın: GC=F vadeli), biz Exness spot. Listelerin birebir aynı
    çıkması beklenmez; sapma sayıları raporlanır.
- İleri test ft-5: ilk alt süreç yalnızca A aşamasıdır (swing + WEEK yeniden üretimi) ve sonucu dakikalar içinde
  yayınlar; V9 turları sonra gelir ve A aşamasını yeniden hesaplamaz.

**Gölge izleyicinin doğruluğu** (karnede `tb_ema_pullback_v1` 31 sanal işlem, %3 kazanma görüldü):
- `tests/signals/test_shadow_accuracy.py`: (1) 400 rastgele işlemde izleyici, testteki kitabî hesap ve bağımsız
  `outcome.simulate_fixed` ile aynı sonucu verir; (2) eğilimsiz piyasada AL ve SAT için beklenen ≈ 0R ve 2R hedefte
  kazanma ≈ 1/3; (3) spread stopun %20'si iken beklenen ≈ −0,2R (spread bir kez ödenir; iki kez düşülseydi −0,4R).
  İzleyici hatalı değil.
- Canlı çapraz denetim: `/health/outcomes` her gölge işlemi bağımsız hesapla ve gerçek mumlarla yeniden sonuçlandırır
  (`check_r`, MFE/MAE, mum sayısı; `shadow_check` sayaçları: uyuşan/ayrışan, ilk mumda stop, ≥1R gören).
- `tb_ema_pullback_v1` ve `tb_donchian_breakout_v1` aynı kuralla 90 günlük ileri teste alındı.
- Yorum: stoplar M15 ATR'sine göre çok dar (spread/stop 0,13–0,33); o günkü işlemlerin çoğu aynı yöne (CAD/CHF
  karşısında SAT) açılmış, birbirine bağlı işlemlerdi. %3'ün ne kadarının strateji, ne kadarının o gün olduğunu
  90 günlük ölçüm gösterecek.

**Kimlik reddi (AUTH_INVALID_API_KEY, kod 1000) bildirimleri:**
- Bilinen davranış: canlı sunucu bazı isteklerin İLKİNİ 1000 ile reddediyor, aynı istek sonra geçiyor (keşif
  2026-11-25). Mum istekleri bu kodda bir kez yinelenir; diğer okuma istekleri yinelenmez ve bildirim üretir.
- Rette ne olur: yönetim istekleri 30 sn durur (art arda retlerde 5 dakikaya kadar katlanır), ilk başarılı istekte
  açılır. Broker tarafındaki stop yerinde kalır. **Canlıda emir sırasında olursa:** emir ACK'ten önce reddedilmiş
  sayılır, gönderilmez ve YİNELENMEZ (o giriş kaçar; çift emir ya da belirsiz emir oluşmaz).
- Saat kayması / imza hatası olsaydı ret sürekli olurdu ve kod 1001 (imza) beklenirdi; tek seferlik 1000 buna uymuyor.
- Eklenen tanılama: her ret kaynağıyla (okuma / emir) ve ardışık sayısıyla `auth_reject` olarak kaydedilir;
  `auth_restored` düzelme süresini taşır; herkese açık özette `auth` bloğu (an, kod, kaynak, süre).

**Elle test için tanılama:** herkese açık özette `positions`: kapanan son işlemlerde broker tarafında stop/hedefin
görülüp görülmediği ve `sl_missing` olay sayısı (tutar/fiyat yok).

**Uygulama:** Raporlar'da "Stratejiye göre" ve "Sembole göre" veri yokken açıklama metni gösterir (sonraki APK'da).
