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
