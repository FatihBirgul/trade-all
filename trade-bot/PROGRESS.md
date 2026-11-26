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
