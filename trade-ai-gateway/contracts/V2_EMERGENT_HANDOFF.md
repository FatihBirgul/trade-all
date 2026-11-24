# Trade AI 2.0 — Emergent teslimi

**2026-10-21 / trade-ai-v2 / v2-product-analysis-2.** Mevcut backend'i yeniden yazma.
Amaç mobil uyumlu arayüzdür. Kaynak sözleşme: [V2_FRONTEND_API_CONTRACT.md](V2_FRONTEND_API_CONTRACT.md),
[V2_OPENAPI.json](V2_OPENAPI.json), gerçek backend çağrılarıyla üretilmiş
[v2_examples](v2_examples/). Bunlar açıkça **fixture** örnekleridir; canlı fiyat değildir.

## Çalışan backend

FastAPI, Binance public spot (BTCUSDT/ETHUSDT/SOLUSDT), immutable analiz/mum
snapshot'ları, QC/freshness, rejim/router, teknik/MTF/Confluence, SQLite, iki sanal
portföy, risk kapısı, pending/partial emir ve pozisyonlar, masraflı OHLC execution,
restart/idempotency/rollback, watchlist/scanner, kalıcı pending notification outbox.
Dört strateji: continuation, range reversion, confirmed breakout, failed breakout.
FVG, teyitli BOS/CHoCH, sweep ve rolling typical-price VWAP analiz içindedir.
Bu özellikler istatistiksel kârlılık veya doğrulanmış başarı olasılığı değildir.

## Bağlantı ve token

Standalone backend: `http://127.0.0.1:8002/api/v2`. Her endpoint
`Authorization: Bearer <private-runtime-token>` ister. Token en az 24 karakter,
yalnız backend/proxy sunucusunun environment'ında; frontend kaynak kodu, public env
(`NEXT_PUBLIC_*`, `VITE_*`, `EXPO_PUBLIC_*`), bundle, URL, GitHub veya loga koyma.
Tek yerel owner token vardır; kullanıcı/session login API'si yoktur.
Yerel CORS yalnız localhost/127.0.0.1:3000 için açıktır; wildcard açma.

Telefon için önerilen teslim: PC'de çalışabilen UI + aynı origin server-side proxy
(BFF); proxy sabit `127.0.0.1:8002`'ye gider, bearer token'ı server-side ekler.
UI oturum kimlik doğrulaması, Secure/HttpOnly cookie ve CSRF korumasını uygula.
Proxy'yi kimliksiz bir bearer aktarıcısı veya kullanıcı URL'sine istek atan açık
proxy yapma. BFF/session katmanı bu backend'de **henüz uygulanmadı**.
PC/telefon aynı özel Tailscale ağı, Serve ile HTTPS, cihaz erişim kısıtları;
Funnel veya modem port forwarding yok. Backend loopback'te kalır.
[Windows/özel ağ yönergesi](V2_WINDOWS_SETUP.md). Gerçek ağ ayarlarını değiştirme.
Emergent uzak preview'sinin localhost'u kullanıcı PC'si değildir; fixture demo ile
canlı bağlı kullanım açıkça ayrılmalıdır.

## Kullanılabilir endpoint'ler

Tüm yolların başı `/api/v2`; gerçek OpenAPI 23 path / 25 GET-POST operation içerir.

| Method | Yol | İşlev |
| --- | --- | --- |
| GET | `/health` | storage/provider state/mode; real_execution=false |
| GET | `/markets` | desteklenen spot; FX/XAU unavailable |
| POST | `/analyze` | kaydedilmiş analiz veya gerekçeli WAIT |
| GET | `/analyses` | limit/offset ile immutable geçmiş |
| GET | `/analyses/{analysis_id}` | tek kayıt |
| GET | `/analyses/{analysis_id}/candles` | aynı snapshot, timeframe/limit |
| GET | `/portfolios` | AUTO/MANUAL dizisi |
| GET | `/portfolios/{portfolio_id}` | tek sanal hesap |
| GET | `/portfolios/{portfolio_id}/orders` | emirler |
| POST | `/portfolios/{portfolio_id}/orders` | risk kontrollü pending sanal emir |
| POST | `/portfolios/{portfolio_id}/orders/{order_id}/cancel` | kalan giriş miktarını iptal |
| GET | `/portfolios/{portfolio_id}/positions` | open_only, limit/offset |
| POST | `/portfolios/{portfolio_id}/positions/{position_id}/close` | queued partial/full close |
| GET | `/portfolios/{portfolio_id}/transactions` | değiştirilemez journal |
| POST | `/portfolios/{portfolio_id}/pause` | yeni riski durdur/resume |
| GET | `/performance` | hesap bazında gerçekleşmiş sonuçlar |
| POST | `/paper/poll` | açık risk için verified closed 1m bars/catch-up |
| POST | `/paper/events` | yalnız fixture modunda test mumları |
| GET | `/watchlist` | kalıcı izleme listesi |
| POST | `/watchlist` | upsert/soft disable |
| GET | `/scanner` | pause/lease/last_error |
| POST | `/scanner/pause` | pause/resume |
| POST | `/scanner/tick` | tek bounded tick |
| GET | `/scanner/jobs` | running/completed/failed/skipped_stale |
| GET | `/notifications` | pending outbox; gönderilmiş değildir |

## Analiz request / response

Canlı runtime için örnek request:

```json
{"symbol":"BTCUSDT","market":"crypto_spot","timeframe":"1H","timeframes":["15m","4H"],"data_mode":"live","risk_portfolio":"MANUAL","auto_paper":false,"idempotency_key":"ui-analysis-unique-001"}
```

Eksiksiz gerçek response örnekleri: [analysis.json](v2_examples/analysis.json),
[range_setup.json](v2_examples/range_setup.json),
[breakout_setup.json](v2_examples/breakout_setup.json),
[sweep_setup.json](v2_examples/sweep_setup.json).
Son üçü yalnız export/test sağlayıcılarıyla üretilir; public `fixture_case=range`
kontrol örneği hâlâ WAIT'tir. Bu dosyalardan canlı hareket eden grafik üretme.

Başarılı range örneğinin alan seçkisi (tam sözleşme yukarıdaki dosyada):

```json
{"data_mode":"fixture","direction":"bullish","reason":"conditional_setup","router":{"status":"selected","strategy_id":"range_mean_reversion_v2","reason":"eligible_priority","eligible_strategy_ids":["range_mean_reversion_v2"]},"levels":{"entry_low":"91.8003","entry_high":"92.1997","invalidation":"88.5017","target_1":"100.0","target_2":"110.3","target_3":null,"reward_risk":"2.109329367225527312060573283"}}
```

WAIT (seçki):

```json
{"data_mode":"fixture","direction":"WAIT","reason":"strategy_confirmation_missing","levels":null,"auto_order_id":null}
```

Provider unavailable, HTTP 200 olarak **kaydedilmiş WAIT** (seçki):

```json
{"data_mode":"live","provider":"binance_public_spot","direction":"WAIT","reason":"provider_unavailable","price":null,"price_time_ms":null,"quality":{"ok":false,"issues":["provider_unavailable"]},"levels":null,"auto_order_id":null}
```

Tam örnekler: [wait.json](v2_examples/wait.json), [provider_unavailable.json](v2_examples/provider_unavailable.json).
HTTP 200, işleme uygun veya canlı kaynak sağlıklı demek değildir.

## Teknik alanlar ve strateji kuralları

`indicators` önceki teknik snapshot'ı korur; mevcut `rsi14` simple rolling RSI'dır.
Yeni `strategy_setups.<id>.momentum.rsi14_wilder` Wilder smoothing kullanır;
ikisini aynı gösterge gibi etiketleme. Strateji sürümleri, `required_data`,
`warmup_bars=250`, parametreler, `requirements`, status/reason, direction ve
confirmed_at_ms adaylarda bulunur. `technical_methods` eklenen geriye uyumlu alandır:

| Alan | Hesap / kullanılabilirlik |
| --- | --- |
| `fvg` | üç mum gap'i >= oluşum anı ATR14 SMA ×0.1; orta gövde >=0.5 ATR, gap yönünde; sonraki tam dolum siler; son 50 oluşum taranır |
| `structure` | strict 2 sol/2 sağ pivot; iki sağ mum kapanınca bilinir; son mum ilk kez seviyeyi kapatarak kırarsa BOS; önceki HH/HL veya LH/LL bias'ına zıtsa CHoCH |
| `liquidity_sweep` | son mum önceki 20 high/low'u aşar ve içeride kapanır; wick >=0.25 ATR; iki taraf süpürülürse conflict |
| `vwap` | son 20 mum Σ((H+L+C)/3 × gerçek hacim)/Σhacim; tick/missing/zero volume unavailable; **session VWAP veya trade-tape VWAP değildir** |

Her yöntemde status/version/as_of ve availability nedeni vardır; as_of son
kapanmış bar timestamp'idir. FVG/BOS/sweep `price_structure` kovasını paylaşır;
VWAP ve volume tek `volume` kovasıdır. Bunları ayrı başarı oyu gibi toplama.

| Strateji / sürüm | Teyit | Invalidation/hedef ve WAIT |
| --- | --- | --- |
| `trend_momentum_v2` / 2 | trend rejimi, EMA20/50 ve son close devamı, VWAP hizası; zıt BOS/CHoCH veya fiyat içindeki zıt FVG veto | mevcut Confluence/composite/RR ve zone gate aynen gerekir; yön uyuşmazsa WAIT |
| `range_mean_reversion_v2` / 1 | range; önceki 20 barda efficiency <=0.3, genişlik >=3 ATR; kenar çeyreğinden rejection sonrası close önceki extreme'i aşar; RSI14 toparlanır ve long <45 / short >55; 1.5× hacim ve VWAP'e dönüş boşluğu | iki son ekstrem dışı 0.25 ATR stop, midpoint TP1/opposite edge TP2; tick rounding sonrası da gross RR<1.5 WAIT |
| `confirmed_breakout_v2` / 1 | trend/breakout; iki close önceki 20 bar dışında +0.25 ATR, ikinci close devam; RSI long 55–80 yükselen / short 20–45 düşen, VWAP ve 1.5× hacim | kırılan sınırın öte yanında 0.25 ATR stop; 2R/3R hedef; tek breakout close WAIT |
| `failed_breakout_v2` / 1 | range/trend/reversal; önceki kapalı sweep, sonraki close sweep extreme'ini aşar; RSI long <50 yükselen / short >50 düşen, VWAP dönüş boşluğu ve 1.5× hacim | sweep extreme dışı 0.25 ATR stop; 2R/3R hedef; takip kapanışı yoksa WAIT |

Range/breakout/sweep üç ayrı kavramsal kova kullanır: price_structure, momentum,
volume. Bu, istatistiksel bağımsızlık iddiası değildir. Başka TF'nin zıt teyitli
kanıtı yeni setup'ı veto eder. Zıt stratejiler öncelikten bağımsız WAIT.
Aynı yönde öncelik sweep > confirmed breakout > range > trend; skor bonusu yok.
Yeni setup'lar mevcut trend composite'ini range işlemine zorlamaz; kendi açık
teyit gate'leri vardır. Ortak risk/maliyet/portföy limitleri değişmemiştir.
Spot bearish analiz adayı görülebilir, fakat spot short sanal emir desteklenmez;
üst response risk kapısında WAIT/null levels olur. Nested candidate levels hiçbir
zaman üst seviyedeki WAIT'i aşmak veya emir oluşturmak için kullanılamaz.

## Sanal hesaplar, emir ve pozisyonlar

AUTO ve MANUAL başlangıçta ayrı 10.000 sanal USDT'dir. Hesap başına cash,
reserved/available/equity, PnL, pause ve risk bağımsızdır. `risk_portfolio` seçimi
analizde aynı hesabın durumunu değerlendirir; AUTO placement yalnız AUTO hesabıyla.

```json
{"analysis_id":"<64-character-saved-analysis-id>","quantity":"1","idempotency_key":"manual-order-unique-001"}
```

`POST /portfolios/MANUAL/orders` response: [order.json](v2_examples/order.json).
Sadece kaydedilmiş uygun analize dayanır; pending döner, doldu demek değildir.
Aynı key farklı body =>409; zaman aşımında aynı key ile retry, sonra GET durumunu oku.

```json
{"quantity":"0.5","idempotency_key":"manual-close-unique-001"}
```

`POST .../positions/{id}/close` queued/pending döner. Sonraki uygun kapalı 1m
mumun open'ında masraf ve hacim sınırıyla işler; eski mark'tan anında kapatılmaz.
Cancel yalnız dolmayan giriş miktarını bırakır. TP1 yarım, TP2 kalan miktar;
aynı mum SL/TP veya giriş/çıkış sırası bilinmiyorsa ambiguous, yeni risk pause.
Volume-limited stop `exit_pending` olarak sonraki mumlarda devam eder.
Ortak politika: trade %0.5, total %3, crypto-group %1.5, günlük gerçekleşmiş kayıp
+ açık stop rezervi %3, notional %90, en çok beş exposure, net TP1 RR>=1.2.
Bunlar demo parametreleridir; başarı/kazanç garantisi değildir.

## Watchlist, scanner, kesinti ve tazelik

```json
{"symbol":"BTCUSDT","timeframe":"1H","enabled":true,"auto_paper":false}
```

`POST /watchlist` upsert eder; en çok 10 kayıt. Scanner default paused,
AUTO per watch default false. `POST /scanner/pause {"paused":false}` ve
`POST /scanner/tick` explicit; `--scanner` worker 60 saniye ve en çok iki analiz/tick.
120 saniye lease; restart current job aynı idempotency key, eski job skipped_stale.

Paper risk önce toparlanır. Binance exact historical adapter ile **300 adet 1m
mum/symbol/tick** alınır, sınırlar ve süreklilik doğrulanır, ledger + outbox birlikte
commit edilir. 12 saatlik kesinti/restart testi vardır; 5 saat toplam sınırı kalktı.
Daha uzun geçmiş gerektiğinde sayfalarla devam edilir; kaynakta geçmişin gerçekten
bulunması koşulludur. Eksik/sahte gap-fill fiyat yoktur.
`PAPER_RECOVERY_IN_PROGRESS` (409): sayfa kaydedildi, yeniden poll gerekir.
`PAPER_HISTORY_UNAVAILABLE` / `PAPER_HISTORY_INCOMPLETE` (503): yeni risk bekler.
Scanner aynı durumda HTTP 200 `status=blocked` ve `reason` döndürür.
UI mark_time_ms, last_error ve recovery uyarısını açık gösterir. Sırf bakiye ekranı
çalışıyor diye fiyatı güncel sayma. Scanner yeni analizleri toparlama bitene kadar engeller; doğrudan analyze/order çağrıları seçili hesabın mevcut stale/risk gate'lerinden geçer.

`*_ms` UTC epoch milliseconds. `price_time_ms` ticker değil, current TF son kapalı
bar; `age_ms` yalnız analiz anındaki yaştır. Geçmiş ekranda yaşı yeniden hesapla;
immutable kararı değiştirme. Aynı snapshot mumları chart endpoint'inden alınır.
Money/order/levels decimal string; teknik değerler sayı veya null olabilir.
Fixture/live rozeti her ekranda görünür. WAIT'te çizilebilir işlem seviyeleri yoktur.
TP3=null, success probability yok. Scanner 60 saniyeyken UI polling'i 15–60 saniye
aralığında tut, hidden tab'de durdur; charts en çok 300 bar, listelerde pagination.

## Hatalar ve performans

```json
{"error":{"code":"RISK_REJECTED","message":"Paper risk gate: portfolio_risk_limit"}}
```

401 auth; 403 fixture ingress live'da kapalı; 404 bulunamadı; 409 risk/idempotency/
gap/recovery/conflict; 422 validation/mode/size; 503 provider/quality/storage;
500 V2_INTERNAL_ERROR. Tam enum/listeler API sözleşmesindedir. İç exception veya
secret ekrana/loga taşınmaz. 500 sonrası GET ile durumu oku ve aynı key'i kullan.

`GET /performance`: hesap bazında kapalı pozisyon, wins/losses, ambiguous count,
gerçekleşmiş sanal PnL/equity/fees ve örnek sayısı. Win rate tanımsızsa null;
ambiguous örnekler kazanma/kaybetme istatistiğine katılmaz. Eğri/expectancy/
max drawdown/backtest başarı oranını frontend uydurmasın.
Tek process, az sayıda sembol, bounded I/O; hedef PC'de ölçüm yapılmadı.
İzole Python 3.12 fixture benchmark'ında üç TF ×300 bar/analiz, altı çağrıda
medyan 93.111 ms ölçüldü ([rapor](V2_FIXTURE_BENCHMARK.json)); bu canlı ağ veya
i3-3240 performans garantisi değildir. Snapshot
başına TF başına 300 bar. Kalıcı history/outbox retention henüz yoktur.

## Henüz uygulanmayanlar

UI/BFF/session ve gerçek telefon bağlantısı, Windows service/autostart kurulumu;
notification delivery/push/email; GPT challenger/chat; FX/XAU/hisse feed/calendar;
çok dönemli backtest/walk-forward/istatistiksel doğrulama; arbitrary manual setups;
Order Blocks, ADX, Supertrend, Anchored VWAP, Session High/Low, ORB ve ayrı volatility
compression/expansion yöntemleri. Bu ek yöntemler çalışıyor diye gösterilmez.

## Emergent'ın değiştirmemesi gereken kurallar

Backend strateji/QC/risk/ledger hesaplarını frontend'de tekrar üretme veya değiştirip
WAIT'i sinyale çevirme. Yeni endpoint varsayma. Gerçek borsa emri/API key ekleme.
AUTO/MANUAL ve fixture/live DB'leri karıştırma. Zamanı veya kullanıcı saatini
backend as_of yerine gönderme. Token'ı kaynakta/bundle'da saklama. Görsel amaçla
canlı fiyat, başarı oranı, gönderildi bildirimi veya kâr geçmişi üretme.
`main`/Render/üretim/veri yedeklerini değiştirme. Yalnız V2 dalında geriye uyumlu UI.

## Teslim doğrulaması

Backend'de `python scripts/export_v2_contract.py` OpenAPI ve tüm örnekleri yeniden
üretir. `python -W error::ResourceWarning tests/run_v2_offline_tests.py` ağ/DB guard
altında testler; V1 remote testleri toplanmaz. `scripts/smoke_v2_loopback.py` gerçek
loopback HTTP/restart acceptance; `scripts/smoke_v2_live.py` ayrı public read-only
probe'dur ve veri unavailable olduğunda exit 2 verir. En son test/CI kanıtı
[V2_PROGRESS_LOG.md](V2_PROGRESS_LOG.md). Windows yerel operasyon ayrıntısı
[V2_WINDOWS_SETUP.md](V2_WINDOWS_SETUP.md).

Son doğrulanan backend kodu: `207f2bec67c2eb7117fa48f73b36c203f2d079ae`.
[Windows ve Ubuntu CI](https://github.com/FatihBirgul/trade-ai/actions/runs/39547404990)
başarılı: her OS'ta 211 V2 + 9 seçili offline V1 outcome; Windows launcher syntax
kontrolü de geçti. Gerçek loopback HTTP/restart geçti; bu oturumdaki canlı provider
probe'u unavailable/exit 2'dir. Kullanıcının PC'sinde kurulum/telefon testi ve
istatistiksel kârlılık doğrulaması henüz yapılmadı.

