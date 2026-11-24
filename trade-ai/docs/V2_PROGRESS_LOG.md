# V2 aşama ve doğrulama kaydı

## 2026-10-29 — Android entegrasyon sözleşmesi ve Windows test düzeltmesi

- Başlangıç `codex/v2-mobile-quotes-20261026` HEAD `6b545e7` temizdi; çalışan
  8002 servisi ve canlı DB değiştirilmedi. Ayrı görev worktree'si kullanıldı.
- Tracking router'ın 422 OpenAPI açıklaması açıkça sabitlendi. Önce kayıtlı
  `V2_OPENAPI.json` ile dört path farkı yeniden üretildi; sonra sözleşme testi geçti.
- Backup regresyon testindeki SQLite bağlantısı Windows dosya kilidini açık
  bırakıyordu. Test bağlantısı açıkça kapatıldı; geçici DB ile hedefli test geçti.
- 220 çevrimdışı V2 test ve compile geçti. Gateway'in aynı Backend uygulamasını
  geçici fixture DB üzerinden kullanan 42 entegrasyon/unit testi geçti.
- Canlı provider, yetkili Gateway/Backend çağrısı ve gerçek telefon doğrulanmadı.
  Public Binance ucunun bağımsız erişimi çalışan servisin provider kanıtı değildir.

## 2026-10-21 — İkinci geliştirme: dört strateji, causal price action, paged recovery

- Başlangıç GitHub `trade-ai-v2` HEAD `172dcca2584b27a4643165585ebaee96b1f900ff`; daha yeni commit yoktu. Root AGENTS ve altı proje belgesi okundu. Doğrudan clone private repository auth istediği için sabit commit'in metinleri bağlı GitHub connector ile alındı. Tree karşılaştırması blob SHA ile yapılır; API commit parent'ı uzak HEAD'dir, ref force=false/expected_sha ile yalnız V2 dalında fast-forward güncellenir. Frontend/main/Render/user DB/yerel V1 yedeklerine yazılmadı.
- Dört sürümlü aktif strateji: continuation (eski trend_momentum_v2 kimliği/v2), range mean reversion, confirmed breakout, failed breakout/sweep. QC ve 250 kapalı/fresh bar; farklı rejimler ve her stratejiye ayrı teyit, koşullu geometri/invalidation, warm-up, WAIT nedenleri. Zıt yön priority'den önce WAIT; aynı yönde açık operasyonel öncelik. Trend composite/Confluence korunur; yeni setup'lar price_structure/momentum/volume kovalarını tekilleştirir. MTF zıt kanıtı veto; spot short hâlâ kapalı. Ortak risk politikası ve eşikler düşürülmedi; yeni stratejilerin gross RR>=1.5 kontrolü tick rounding sonrasında da korunur.
- `price_action.py`: üç mum FVG/displacement, strict 2/2 confirmed pivot BOS/CHoCH, 20-bar sweep/reclaim, gerçek hacimli rolling typical-price VWAP. Oluşum eşiği o anın ATR'siyle sabit; sonraki ATR eski FVG'yi repaint etmez. Tick/unavailable/zero hacim VWAP oluşturmaz. FVG/BOS/sweep aynı price_structure kovası. RSI14 Wilder setup momentum'u eski simple rolling RSI'dan ayrı alanla etiketlendi. Replay kayıtlarında yeni engine sürümleri/parametreler saklanır.
- `candle_window`: Binance public GET ile exact start/end tarihsel 1m sayfası. Latest-source quality/identity önce doğrulanır; en çok 300 bar/symbol/tick, tam sınır/süreklilik/closed kontrolü sonrası atomik ledger/outbox commit. Toparlama sürüyorsa PAPER_RECOVERY_IN_PROGRESS ile scanner yeni iş açmaz; API mark_time_ms ve scanner last_error görünür. 12 saat, sayfalar arası restart, idempotency, eksik sınır/gap/source/unfinished, kesinti, stale ve rollback doğrulandı. Toplam beş saat cutoff'u kalktı; kaynağın gerçek geçmişi sunması koşullu, fiyat uydurulmaz.
- Windows manuel launcher, env örneği, loopback health/shutdown, 2 MB + üç backup log rotasyonu, read-only verified SQLite backup/restore yeni hedefe ve özel ağ/BFF tasarımı hazır. Gerçek Windows ayarı/servis/firewall/telefon kurulumu yok. Backup testleri yalnız kendi temporary DB'lerinde çalıştı.
- API'nin mevcut 23 path/25 operation'ı korunur; additive technical_methods/strategy_setups. OpenAPI, eski örnekler ve range/breakout/sweep confirmed fixture JSON'ları actual backend'den üretildi. Emergent teslimi `V2_EMERGENT_HANDOFF.md`; Windows yönergesi `V2_WINDOWS_SETUP.md`. Ek yedi TA yöntemi, backtest/kârlılık doğrulaması, FX/XAU, GPT, notification delivery, UI/BFF/session ve persistent service tamamlanmış sayılmaz.
- Gerçek loopback HTTP/chart/order/fill/close/reconciliation/scanner/restart smoke başarılı; `V2_SECOND_SESSION_LOOPBACK_REPORT.json`. Ayrı public live smoke ilk denemede ortamın SOCKS proxy bağımlılığı eksikliğinin API 500'e sızdığını buldu. Provider adapter bunu artık proxy'yi bypass etmeden unavailable'a çevirir; regresyon eklendi. Tekrar HTTP 200 saved WAIT/provider_unavailable, AUTO=0 ve readback eşit, probe **exit 2**; `V2_SECOND_SESSION_LIVE_REPORT.json`. Bu oturumda canlı Binance fiyat erişimi doğrulanamadı; önceki başarılı live raporu yeni test gibi sunulmaz.
- Yerel compile, **210 V2 + 9 seçili V1 outcome** başarılı; ardından eski bir mumdaki unavailable volume için ek fail-closed regresyonu ve güvenli koşul eklendi. **Son koşu 211/211 V2 başarılı (33.841 saniye), compile başarılı; ek 9 seçili V1 outcome da başarılı.** Kod checkpoint ve CI kanıtı aşağıdadır. Hiçbir başarısız test gizlenmedi/skip yapılmadı. İlk baseline koşusu eksik bağımlılık/OpenAPI dosyası, ilk yeni recovery testi ise yalnız son 20 notification sayfasını okuyan test varsayımı nedeniyle başarısızdı; bağımlılıklar kuruldu, aynı upstream OpenAPI alındı ve tüm notification'ları gerçekten sayan assertion ile düzeltilip suite tekrar geçirildi.
- İzole fixture benchmark: Python 3.12, üç TF ×300 mum, altı analiz medyan **93.111 ms** (`V2_FIXTURE_BENCHMARK.json`). Bu i3-3240 veya canlı ağ ölçümü değildir; retention/outbox compaction hâlâ yoktur.


### İkinci görev — doğrulanmış kapanış

- Kod commit'i: **`207f2bec67c2eb7117fa48f73b36c203f2d079ae`**; önceki `172dcca` commit'inin doğrudan devamıdır. API ref update force=false/expected_sha ile gerçekleşti.
- [GitHub Actions 39547404990](https://github.com/FatihBirgul/trade-ai/actions/runs/39547404990) **success**. [Ubuntu işi](https://github.com/FatihBirgul/trade-ai/actions/runs/39547404990/job/119048588225): 211 V2 / 8.686s + 9 V1 outcome. [Windows işi](https://github.com/FatihBirgul/trade-ai/actions/runs/39547404990/job/119048588500): 211 V2 / 24.398s + 9 V1 outcome. İki OS'ta compile/install/test başarılı; Windows PowerShell launcher parser adımı da başarılı. Ubuntu'da yalnız Windows parser adımı platform gereği çalıştırılmaz; hiçbir başarısız test atlanmadı.
- Yerel son suite **211 V2 / 33.841s**, 9 seçili V1 outcome ve compile başarılı. Loopback HTTP acceptance başarılı. Public-live probe unavailable/exit 2; yeni canlı fiyat/başarı oranı üretilmedi.
- Uzak `main` hâlâ `50136e13428028156b17c5953bdb27dc99eb682f`; değişiklik ağacı yalnız backend/V2 testleri, V2 workflow ve docs içerir. Frontend/V1 yedekleri/Render/gerçek para/gerçek kullanıcı DB'sine yazılmadı.
- Emergent giriş dosyası **`docs/V2_EMERGENT_HANDOFF.md`**. API contract/OpenAPI/actual fixture örnekleri ve Windows/backup/private-network yönergesi güncel. UI/BFF/session/telefon ve gerçek Windows pilotu sonraki aşamadır; kârlılık doğrulaması yapılmadı.
- Sonraki yalnız dokümantasyon commit'i bu doğrulama kanıtını saklar; çalışan kod checkpoint'i yukarıdaki commit'tir.

## 2026-10-21 — Emergent grafik verisi için immutable candle API

- `GET /api/v2/analyses/{analysis_id}/candles`: kayıtlı analizin kullandığı aynı kapalı OHLCV snapshot'ı, source record hash doğrulaması, timeframe/limit, decimal string fiyatlar ve explicit fixture/live/snapshot etiketiyle sunulur. Yeni provider çağrısı yoktur; tarihsel kayıt canlı diye etiketlenmez.
- Quality-invalid/cross-source kayıtlar 409, olmayan timeframe 404, bozuk immutable source 503 verir. Yeni Pydantic chart modeli, OpenAPI ve `v2_examples/candles.json` hazır. Frontend grafik üretmek için dış feed veya uydurma fiyat kullanmak zorunda değildir.
- Yerel **180 V2 test**, compile ve yeniden gerçek loopback HTTP acceptance/restart başarılı. Grafik son mum fiyat/zamanı analiz yanıtıyla birebir doğrulandı. Son OpenAPI **23 path / 25 GET-POST işlemi**.
- Kod **`ddd3a2e0f2a95c4e510756dcacd191fc7fbaa09d`**, [Actions 39507706156](https://github.com/FatihBirgul/trade-ai/actions/runs/39507706156): Windows/Ubuntu tüm adımlar success; loglarda **180 V2 + 9 seçili offline V1 outcome** teyit edildi. Sonraki belge commit'i yalnız doğrulama kaydıdır. Kritik bekleyen kullanıcı kararı yoktur; main/Render/user DB/yedek güvenlik checkpoint'i aşağıda korunur.

## 2026-10-21 — Önceki HTTP çekirdek doğrulaması ve güvenlik checkpoint'i

- Kod `d9a30dded53168a7cf0006a3f1348c08690aa7b7`, [Actions 39507013408](https://github.com/FatihBirgul/trade-ai/actions/runs/39507013408): Windows/Ubuntu syntax, bağımlılıklar, **177 V2 + 9 seçili offline V1 outcome** ve cleanup success. Başarısız önceki CI'lar aşağıda korunmuştur; test atlanarak başarı raporlanmamıştır.
- Son OpenAPI: **22 path / 24 GET-POST işlemi**. Zorunlu on V2 endpoint ve paper lifecycle + watchlist/scanner/outbox endpoint'leri uygulanmıştır. Çalışan/planned ayrımı frontend contract'ta; TP3/null, FX/XAU/unavailable, fixture/live ayrımı korunur.
- GitHub `main` ve asıl checkout HEAD hâlâ `50136e13428028156b17c5953bdb27dc99eb682f`. Asıl kullanıcı klasörünün dört modified dosyası ve untracked listesi korunuyor; üç korunan yedek aynı ad/yolda ve 8845/20572/15004 byte. Main/Render/gerçek kullanıcı DB'sine yazılmadı; gerçek para emri/gizli anahtar kullanımı yok.
- Ayrı worktree normal push ile kaydedildi; test/smoke sunucuları kapatıldı, geçici DB'ler temizlendi. Kullanıcı yedekleri silinmedi. Açık kritik kullanıcı kararı yok; telefon erişimi/ücretli sağlayıcı/gerçek data migration/production hâlâ bu oturumun dışında.

## 2026-10-21 — HTTP acceptance ve tutarlı internal error sözleşmesi

- Scanner checkpoint `09fe499`: [CI 39506601248](https://github.com/FatihBirgul/trade-ai/actions/runs/39506601248) Windows/Ubuntu tüm adımlar success (**176 V2 + 9 seçili V1 outcome**).
- Beklenmeyen V2 hataları HTTP 500 `V2_INTERNAL_ERROR` JSON döner; exception payload frontend'e taşınmaz. Durum okunup aynı idempotency key ile retry önerilir; commit olup olmadığına dair uydurma rollback iddiası yoktur. Regresyon ve strict OpenAPI güncellendi; yerel **177 V2** testi geçti.
- Tekrarlanabilir `scripts/smoke_v2_loopback.py`: gerçek Uvicorn/HTTPX, yalnız ephemeral 127.0.0.1, geçici fixture SQLite. Analysis/readback, paper order/fill/queued close/cash reconciliation, AUTO/MANUAL ayrımı, event/request dedup, scanner/outbox ve gerçek HTTP server stop/restart persistence geçti. Mongo/AI import edilmedi; server kapatıldı. Rapor: `V2_LOOPBACK_SMOKE_REPORT.json`.
- `scripts/smoke_v2_live.py` public-read doğrulamasını geçici DB'de tekrarlanabilir yapar; AUTO kapalıdır ve outage/invalid data exit 2 üretir. Offline CI bu ağ kontrollerini çalıştırmaz. CI syntax kontrolü launcher ve smoke/export scriptlerini de kapsar.
- Son ayrı live probe 2026-10-20 22:16 UTC: Binance BTCUSDT 15m/1H/4H kalite kapıları başarılı, HTTP 200 gerekçeli WAIT/no_eligible_strategy, SQLite readback eşit, AUTO order=0, real_execution=false. `V2_LIVE_SMOKE_REPORT.json` status=verified. Bu, kârlılık veya canlı paper fill başarısı iddiası değildir.

## 2026-10-21 — Bounded scanner / watchlist / pending outbox

- Core `99be5dc` [CI 39505521204](https://github.com/FatihBirgul/trade-ai/actions/runs/39505521204) Windows ve Ubuntu'da syntax, **161 V2 + 9 seçili V1 outcome** ile tamamen success.
- Watchlist upsert/soft-disable (10 kayıt), scanner state/pause/tick/jobs ve pending notifications API'leri eklendi. Pydantic/OpenAPI ve actual fixture örnekleri frontend sözleşmesine işlendi. Background tek 60 saniye cooperative thread yalnız `--scanner`; import/router mount background başlatmaz. Default paused ve watch AUTO off.
- Önce açık paper riskine polling, sonra en fazla iki yeni watch analizi. 120 saniye persistent lease/concurrent tick kontrolü, closed-bar dedup, idempotent restart, eski yarım işi replay etmeden skipped_stale, provider I/O sonrası commit-time pause/lease/boundary gate var.
- Scanner paper event'i ve outbox aynı transaction'da yazılır; outbox fault dolumu/bakiyeyi rollback eder. Analiz sonrası job/outbox crash'i aynı analysis key ile toparlanır, ikinci AUTO order açmaz. Delivery servisi kurulmadı; her bildirim `pending/not_configured`.
- Poll identity kapısı kaynak/quote/price-kind/real-volume/epoch hizasına genişletildi. Açık risk yoksa provider çağrısı yapılmaz. Teknik engine hatası API'de açık `technical_engine_unavailable` WAIT üretir; eligible_priority gibi yanıltıcı fallback nedeni kalmaz.
- Yerel **176 V2 offline unit/ASGI/ledger/scanner testi + 9 V1 outcome**, compile başarılı. Worker stop/pause, concurrency lease, restart, stale job, outage, wrong source/quote/price/volume, watch limit ve fault rollback testleri dahil. Yeni checkpoint'in CI sonucu push sonrası doğrulanacak.
- Sınırlar: 300 1m bar recovery penceresi, history retention yok, job başarısı strateji kârlılığı değildir. Dış bildirim, GPT/FX/UI/telefon/Windows service/production kurulmadı. Graceful worker stop persist pause yapar; mevcut pozisyon silinmez veya otomatik liquidation yapılmaz.

## 2026-10-21 — Protective exit ve CI ortam doğruluğu

- Gap-open stop, daha sonra görülen target'tan önce gerçekleşir; yanlış ambiguous sonucu düzeltildi. Volume-limited stop kalan miktarı `exit_pending` olarak korur, rebound sonrası da kapatır. Çözülmeyen protective exit varken hesap resume reddedilir.
- Birden çok queued close aynı liquidity kapasitesini paylaşır; over-close reddi ve partial-entry expiry cash release regresyonları eklendi. Yerel **161 V2 + 9 seçili V1 outcome** testi ve compile başarılı.
- İlk ürün CI'ları 39503916113/39504454446, yalnız Python 3.11/3.13 HTTP 422 açıklama farkındaki strict OpenAPI testinde başarısız oldu; sözleşme açıklamaları sabitlendi, test zayıflatılmadı.
- [2083bfd CI](https://github.com/FatihBirgul/trade-ai/actions/runs/39504645256): Ubuntu/Windows **157 V2 test success**, ancak sonraki outcome adımı legacy required_plugins=pytest-xdist yüzünden başlayamadı. Bu sonuç tüm workflow success olarak sunulmaz. Ayrı `tests/pytest-v2.ini` ile legacy ayarlar değiştirilmeden seçili offline sınıf izole edildi; yerelde 9/9 geçti. Yeni push CI doğrulaması beklenir.

## 2026-10-21 — Çalışan FastAPI / paper ledger ürün dilimi

- Başlangıç: uzak `trade-ai-v2` HEAD `045452b`, daha yeni çalışma yok. Ayrı worktree kullanıldı; user diff/untracked yedekler ve main `50136e1` korundu. Master/M0/state/progress/ADR okundu; eski “V2 API yok” ifadeleri tarihsel baseline, güncel kod aşağıdaki üründür.
- Mevcut provider/QC/regime/router/technical/MTF/Confluence/paper_risk/record modülleri yeniden yazılmadan uygulamaya bağlandı. Kapalı/fresh/250 warm-up bar, source/symbol/contract/venue, TF epoch/as-of hizası ve current-MTF evidence tekilleştirmesi zorunlu. Risk veto olursa WAIT/null levels; TP3 uydurulmaz.
- Standalone FastAPI + reusable V2 router; Pydantic modeller, bearer, OpenAPI, loopback-only launcher. V1 import/startup/validation varsayılanı değişmez; mount explicit opt-in. Foreign DB/prototype migration yok; fixture/live DB mode sabit.
- AUTO/MANUAL ayrı sanal USDT hesapları. Pending/partial/full entry, queued partial/full close, TP1/TP2/SL, fee/spread/slippage, volume participation, cancel/expiry/ambiguity, pause, realized/unrealized PnL/performance. Her request ve piyasa barı persistent idempotent; AUTO ayrıca strateji/closed-bar tekilleştirmesi yapar. Close eski mark'tan anında doldurulmaz.
- SQL BEGIN IMMEDIATE: hesap/projection/journal/event receipt birlikte commit/rollback. Immutable history trigger'ları ve body checksum'ları var. Journal fault ve commit öncesi ayrı process crash testlerinde bakiye değişmedi; aynı key retry, concurrency ve restart testleri geçti. Hiçbir gerçek order gateway/trading key yok.
- Public Binance live smoke ayrı: 300 final BTCUSDT bar/TF, 15m/1H/4H kalite başarılı; gerçek piyasa koşulunda HTTP 200 WAIT, SQLite readback eşit, AUTO=0. `V2_LIVE_SMOKE_REPORT.json`. Fixture hiçbir zaman live fallback değildir. Aynı venue mirror; access/rate-limit yanıtları bypass edilmez. Provider Protocol başka venue için hazırdır, otomatik cross-venue fallback henüz yoktur.
- Emergent: `V2_FRONTEND_API_CONTRACT.md`, actual-app `V2_OPENAPI.json` ve endpoint çağrılarından fixture JSON örnekleri üretildi. Golden OpenAPI/example schema testi var. UI/telefon/GPT/scanner henüz tamamlanmış sayılmaz.
- Yerel compile + **157 V2 test** network/DB guard/ResourceWarning hata bayrağı altında, ayrıca **9 seçili V1 outcome unit regresyonu** geçti. İlk pytest denemesi eski `-n auto`/Temp izin sorununa takıldı; `-o addopts=` ve explicit class ile serial çalıştırılarak doğrulandı. Uzak V1 testleri çalışmadı.
- Windows asyncio socketpair IPC'sine yalnız doğrudan stdlib socketpair çağrısı için izin verildi; uygulama TCP/DNS ve temporary-root dışı SQLite engeli korunuyor. CI aynı V2 runner + seçili outcome sınıfını Windows/Ubuntu'da çalıştırır. Checkpoint CI teyidi push sonrasında eklenecek.
- Kalan sınırlar: son 300 1m bar (~5 saat) poll/catch-up penceresi, tanımlı sentetik liquidity modeli; full backtest/SMC/FX/news, scanner/notification/GPT/phone/service yok. Üretim/main/user DB/yedek ve gerçek para korunur.

## 2026-10-20 — M2.1 Teknik motor göç sınırı ve referans testleri

- Başlangıç `2caf690`; ayrı `trade-ai-v2` worktree temizdi. Master Plan ve M0 risk matrisi tekrar okundu.
- El hesabı referansları: EMA/SMA, simple-average RSI (Wilder değildir), gap içeren ATR, sample-standard-deviation Bollinger; MTF timeframe sırası ve RR veto/bias ayrımı; Confluence korelasyon kovası/recency/confirmation.
- Yeniden üretilen ve düzeltilen hatalar: sıfır kayıplı yükselişte RSI NaN (100 olmalı), düz fiyat penceresinde RSI NaN (açık nötr konvansiyon 50), eşit rank zıt Confluence kanıtlarında input sırasına göre bullish/bearish değişimi. Tied bucket artık sıfır güçte neutral conflict marker üretir; sıralama deterministiktir. Warm-up NaN'ları korunur.
- Evidence gücü finite 0–100, age tam sayı, confirmation boolean olarak doğrulanır; NaN/Infinity/bool gücü ve bozuk metadata reddedilir. Nötr marker destek/opposition sayılmaz.
- `v2.technical_adapter` kapalı mum QC → gerçek hacim yeteneği → eski OHLCV motoru sınırını kurar. Desteksiz timeframe varsayılan 4H'ye çevrilmez. Hata loglanır ve unavailable döner. V1 API'ye bağlanmadı.
- Sonuçta engine/adaptör sürümü ve as-of zamanı vardır; snapshot canonical JSON ile tutulur, tüketici bağımsız kopya alır. Eksik warm-up göstergeleri açık listelenir. Bu ilk adaptör tick/eksik hacimle komple OHLCV snapshot hesaplamaz; OHLC-only ayrıştırma sonraki iştir.
- Yerel: backend compile geçti; **77 V2 test + 9 mevcut saf outcome regresyonu geçti**. Outcome çalıştırması yalnız `TestOutcomeEngineUnit` sınıfını seçti; uzak endpoint fixture'ları çalışmadı.
- CI, yalnız `requirements-v2-tests.txt` içindeki sabit NumPy/Pandas test bağımlılıklarını kurar; API/DB/provider SDK'sı kurulmaz. GitHub sonucu push sonrası commit bazında doğrulanacak.

- GitHub doğrulaması: `f0cafb6`, [Actions 39468241375](https://github.com/FatihBirgul/trade-ai/actions/runs/39468241375) **success**; sabit NumPy 2.2.6/Pandas 2.2.3 ortamında testler geçti.

## 2026-10-20 — M2.2 Sanal portföy risk kapısı

- `v2.paper_risk`: yalnız hesap quote/settlement para birimi aynı linear kripto kontratlarını değerlendirir. FX, inverse ve spot short/borç alma unavailable kalır. Yön ve seviyeler bu modülde üretilmez.
- Bullish/bearish geometri; giriş aralığının en kötü kenarı; TP1 net reward/risk; açıkça girilen round-trip maliyet; quantity step/minimum quantity/notional/multiplier doğrulanır. Tüm limitler sürümlü politika girdisidir; kalibre edilmiş veya tavsiye edilen varsayılan risk yüzdesi yoktur.
- Toplam risk, correlation-group limiti, UTC günlük gerçekleşmiş kayıp + açık stop rezervi, nakit/notional ve açık pozisyon sayısı veto eder. Miktar aşağı yuvarlanır, son budget kontrolü yapılır. Decimal bağlamı sabittir; desteklenen girdiler finite Decimal, en fazla 28 basamak, exponent -18..18 ve 1e24 sınırındadır.
- İki demo hesabının risk/bakiye snapshot'ları karışamaz; quote currency conversion varsayılmaz. Snapshot freshness, UTC gün sınırı, setup expiry, session/news ve emergency pause fail-closed kontrol edilir.
- Sonuç yalnız `eligible_for_paper` veya `wait`; hiçbir bakiye yazılmaz, emir oluşturulmaz. Session/news doğruluğu çağıranın görevidir; bu aşamada canlı haber/takvim sağlayıcısı yoktur. Correlation group açık girdidir; otomatik korelasyon hesabı değildir.
- Yerel compile ve **93 V2 testi** geçti (16 yeni risk testi; sınır/parametre alt vakaları dahil). Risk module ayrı test fixture'ları kullanır, gerçek portföy verisi okunmaz.
- Sonraki adım: route/setup instrument ve veri/strateji sürümlerini aynı immutable analiz kaydında bağla; yalnız RouteDecision alanını geçirmek tam provenance garantisi değildir. Paper fill simulator bu aşamada uygulanmadı.

- GitHub doğrulaması: `420c40a`, [Actions 39468705895](https://github.com/FatihBirgul/trade-ai/actions/runs/39468705895) **success**.

## 2026-10-20 — M1/M2.3 Immutable analiz ve risk provenance

- `v2.decision_record`: tam kapalı-mum snapshot'ı, kaynak/instrument, data/config sürümleri, immutable ve sürümlü strateji listesi, pipeline/regime/router/technical sürümleri, gerçek teknik/rejim parametreleri, QC ve sonuçlar canonical JSON'da tutulur. SHA-256 kimliği ve frozen record ile tüketici kopyası ayrıdır.
- Aynı girdiler aynı ID; değişen data/config/strateji sürümü, mum veya parametre yeni ID üretir. Registry input sırası sonucu değiştirmez. Checksum bozulmayı algılar; dijital imza/kimlik doğrulama değildir.
- Önce QC ve Router; yalnız selected route'ta teknik hesaplama. Rejim için 20 mum yeterli olsa bile teknik warm-up 30'a ulaşmadıysa üst sonuç WAIT; analysis_ready bir işlem sinyali değildir.
- Nonfinite reddedilmiş girdiler JSON'a NaN/Infinity olarak değil hata etiketi olarak yazılır. Geçersiz veri üzerinde technical çalışmaz. Geçersiz raw sayının tam bit desenini koruyan bir arşiv değildir.
- Risk wrapper, setup'ın record ID/instrument/oluşturulma zamanı ile analiz bağını doğrular. Başka sembol, eski veya değiştirilmiş kayıt, WAIT analizi risk uygunluğuna dönüşmez. Politika, iki hesabın snapshot'ı, filtreler ve risk kararı ayrı immutable kayıtta analiz ID'sine bağlanır.
- Yerel **105 V2 testi** ve backend compile geçti; aynı snapshot tekrar, sıra invariance, sürüm değişimi, bozulma, future-bar/lookahead ve uçtan uca analysis→paper-risk smoke kapsandı.
- Kalıcı kayıt/depolama/migration bu aşamada yok; V1 API ve gerçek portföylerle bağlantı yok.

- GitHub doğrulaması: `95302d6`, [Actions 39469289592](https://github.com/FatihBirgul/trade-ai/actions/runs/39469289592) **success**.

## 2026-10-20 — M1.4 İzole append-only kayıt deposu prototipi

- `v2.record_store`, yalnız explicit dosya yoluyla oluşturulur; varsayılan yol/env/startup hook veya MongoDB migration yok. Yeni dosya exclusive create ile açılır; mevcut herhangi bir dosyanın üzerine yazılmaz. Eksik DB open sırasında otomatik oluşturulmaz.
- Var olan DB yalnız kendi application/schema marker'ları ve immutable trigger'ları doğrulanırsa açılır. Farklı veritabanı metadata incelemesinden sonra değiştirilmeden reddedilir. Bu marker bir güvenlik imzası değildir.
- Full candle snapshot dahil immutable JSON kayıtları hash kontrolüyle insert edilir. Aynı ID/aynı içerik ikinci kez eklenmez; reanalysis yeni ID ile eklenir. SQL UPDATE/DELETE trigger'ları normal değişiklikleri engeller; okuma sırasında checksum doğrulanır.
- Restart/yeniden açma, farklı sürüm ekleme, paper-risk→analysis bağı, bozuk kayıt reddi, yeni hedefe SQLite-consistent backup ve restore testleri geçti. Kullanıcı yedekleriyle ilişki yoktur; backup/restore sadece testin ürettiği geçici fixture üzerinde çalıştı.
- Windows testinde sqlite connection context manager'ın bağlantıyı kapatmadığı görüldü; test fixture bağlantıları explicit close ile düzeltildi. ResourceWarning hata sayılarak tekrar doğrulandı.
- Yerel backend compile ve **115 V2 testi** geçti. 10 yeni persistence testi sadece kendilerine ait TemporaryDirectory içinde DB oluşturur/değiştirir. Üretim/persistent kullanıcı verisi okunmadı veya yazılmadı.
- Bu bir kalıcı veri altyapısı adayı prototipidir; V1 MongoDB→SQLite göç stratejisi, candle query/index/retention ve iki demo hesabının emir lifecycle'ı hâlâ açık iştir.

- GitHub doğrulaması: `7a24c00`, [Actions 39469688104](https://github.com/FatihBirgul/trade-ai/actions/runs/39469688104) **success**.

## 2026-10-20 — M1/M2.5 Veri ve MTF fail-closed regresyonları

- Genişletilmiş kötü girdi testleri MTF'de NaN confidence'ın 100'e dönüşmesini, Infinity final_score sızıntısını ve `"false"` gibi truthy string gate'lerinin geçmiş sayılmasını yeniden üretti. Numeric confidence/score finite değilse 0, gate yalnız literal boolean True ise geçer. Confidence hâlâ heuristic; probability değildir.
- Confluence genel score girişi yalnız trend/momentum/volume/structure/news kabul eder; MTF ve bilinmeyen gösterge generic evidence olamaz. Core score/threshold bool/nonfinite/bozuk ise hata verir; Infinity'yi 100 strength'e clamp ederek uydurma kanıt oluşturmaz.
- Instrument identity alanları nonblank string olmak zorunda. V2 series QC, bozuk candle/instrument nesnesi ve blank/nonstring source için açık kalite hatası döner; AttributeError ile çökmez. Bütün batch WAIT olur.
- Yerel compile, **120 V2 test + 9 saf outcome regresyonu** başarılı (replay milestone testleri hariç). Mevcut V1 API/DB/provider davranışı canlı ortamda değiştirilmedi.
- CI, Linux ve Windows Python 3.11 matrix'ine genişletildi; ResourceWarning hata sayılır. İş başına 5 dakika sınırı ve contents:read yetkisi korunur; production/deploy adımı yok.

## 2026-10-20 — M1/M2.6 Kaydedilmiş analiz replay doğrulaması

- `replay_analysis`, immutable kayıttaki mum/config/stratejileri yeniden kurar; orijinal `as_of_ms` ile QC→Router→technical akışını yeniden çalıştırır. Aynı içerik hash'i `matched`, değişen karar/parametre `mismatch` sonucudur. Bakiye/emir/depolama yazımı yoktur.
- Desteklenmeyen engine sürümü sessizce güncel algoritmaya çevrilmez. Bozuk kayıt ve nonfinite raw sayının yalnız diagnostic etiketi bulunan kayıtlar `unavailable` döner.
- Gelecekteki mum içeren tarihsel snapshot, replay'de de WAIT kalır. Depo kapatılıp yeniden açıldıktan sonra okunan kayıt aynı karar ID'sini yeniden üretir.
- Yerel backend compile ve **122 V2 testi** geçti. Bu, backtest/replay'in ilk tek-snapshot primitive'idir; tarihsel walk-forward, fill simulator veya performans doğrulaması değildir.

## 2026-10-20 — Test izolasyonu ve güvenli tekrar çalıştırma

- `tests/run_v2_offline_tests.py` yalnız `test_v2_*.py` allowlist'ini toplar. Test-only context socket/DNS/UDP sendto bağlantı girişimlerini I/O öncesinde durdurur. SQLite yalnız aynı çalıştırmanın yeni geçici kökü altında veya memory DB'de açılabilir; kök dışı ve remote URI reddedilir.
- Bu guard, yanlışlıkla eklenen network/DB test çağrıları için ek korumadır; düşmanca kodu engelleyen OS sandbox değildir. Üretim URL'si/DB/env/kimlik bilgisi testlere verilmez.
- Dört guard testi dış dosya yaratılmamasını, ağ çağrısının engellenmesini, izole SQLite çalışmasını ve patch'lerin context sonunda geri alınmasını doğrular.
- Yerel **126 V2 testi**, ağ/DB guard ve ResourceWarning hata bayrağı altında geçti. Backend compile ve 9 saf outcome regresyonu da başarılı. CI aynı runner'ı Windows/Ubuntu üzerinde kullanır.
- Güvenli komutlar backend klasöründe: `python -m compileall -q market_ai server.py`, ardından `python -W error::ResourceWarning tests/run_v2_offline_tests.py`. V1 uzak testleri doğrulanmış izole hedef olmadan çalıştırma.

## GitHub doğrulama kapanışı — 2026-10-20

| Aşama | Commit | GitHub Actions |
| --- | --- | --- |
| Teknik motor/adaptör | `f0cafb6` | [39468241375](https://github.com/FatihBirgul/trade-ai/actions/runs/39468241375) success |
| Paper risk gate | `420c40a` | [39468705895](https://github.com/FatihBirgul/trade-ai/actions/runs/39468705895) success |
| Immutable kayıt/provenance | `95302d6` | [39469289592](https://github.com/FatihBirgul/trade-ai/actions/runs/39469289592) success |
| SQLite prototipi | `7a24c00` | [39469688104](https://github.com/FatihBirgul/trade-ai/actions/runs/39469688104) success |
| MTF/veri hardening | `1a50b45` | [39470237543](https://github.com/FatihBirgul/trade-ai/actions/runs/39470237543) Ubuntu + Windows success |
| Tek snapshot replay | `82ba6b2` | [39470466707](https://github.com/FatihBirgul/trade-ai/actions/runs/39470466707) Ubuntu + Windows success |
| Ağ/DB test guard | `4ad3aa6` | [39470520485](https://github.com/FatihBirgul/trade-ai/actions/runs/39470520485) Ubuntu + Windows success |

Son functional checkpoint'te 126 offline V2 test her iki CI işinde başarılı; yerelde ek 9 saf outcome regresyonu başarılı. Başlangıç 54 V2 testti. Main ref'i `50136e1` olarak kaldı, yerel kullanıcı değişiklikleri ve yedekleri korundu. Hiçbir üretim erişimi veya gerçek emir yok. V2 API bağlantısı, MTF snapshot sınırı, kapsamlı SMC, market feed registry, FX takvimi ve paper fill simulator tamamlanmış sayılmaz.

### İlk ürün CI kontrolü — düzeltme sürüyor

`19948c6` / [39503916113](https://github.com/FatihBirgul/trade-ai/actions/runs/39503916113): her iki OS'ta compile/install başarılı; 157 V2 testin yalnız golden OpenAPI karşılaştırması başarısız, 156 işlevsel test başarılı. Sonraki outcome adımı bu nedenle skipped, CI başarı diye raporlanmıyor. Yerel Python 3.13 ve CI Python 3.11 şema farkını path bazında raporlayan kalıcı diagnostic eklendi; sözleşme testi atlanmadı veya zayıflatılmadı.

### OpenAPI CI kök neden ve düzeltme

`089a2bd` / CI `39504454446` diagnostic'i yalnız HTTP 422 description farkını gösterdi: Python 3.13 stdlib `Unprocessable Content`, Python 3.11 `Unprocessable Entity`. Runtime/scheme alanları farklı değildi. Router error açıklamaları explicit sabitlenerek OpenAPI yeniden üretildi; strict golden test korundu. Gerçek loopback Uvicorn HTTP smoke da geçti (`V2_LOOPBACK_SMOKE_REPORT.json`): 127.0.0.1, health/analyze 200, SQLite readback eşit, server temiz kapandı, Mongo/AI provider import edilmedi.


## 31 Ekim 2026 — Görev 11 / paper integrity

- GitHub PR #2 açık/Draft ve b6066bf bağımsız doğrulandı; bu referans üzerinden
  `codex/task11-paper-integrity-20261031` açıldı. Android a14c117 (0.7.2/11),
  Gateway 19038bd yalnız incelendi; bionic/task9 dalı birleştirilmedi.
- `75f82e9`: partial TP1 + manual reduction sonrası 422/mum ilerleme engeli,
  pozisyon/performance Decimal context bağımlılığı, formatter rounding/negatif
  sıfır düzeltildi. Yedi yeni regresyon; önceden kırmızı hata kanıtları ve ayrıntılar
  [TASK11_PAPER_INTEGRITY.md](TASK11_PAPER_INTEGRITY.md).
- Yerel Linux/Python 3.12: 227 V2 + 2 quote + 9 outcome, compile ve geçici fixture
  DB/gerçek loopback HTTP/restart/cash reconciliation başarılı. Gateway geliştirme
  dalının 42 testi (8 V2 entegrasyonu dahil) başarılı. OpenAPI nesneleri referansla
  eşit; Android/Gateway kaynakları temiz; canlı DB/main/deploy/özel ağ değişmedi.
- `757f202`: bu görev dalında iki OS CI etkinleştirildi.
  [41185741446](https://github.com/FatihBirgul/trade-ai/actions/runs/41185741446)
  Windows/Ubuntu success (her OS 227 V2 + 9 outcome/compile; Windows launcher parse).
  [41185756688](https://github.com/FatihBirgul/trade-ai/actions/runs/41185756688)
  Python 3.11/3.12 success (her Python 227 V2 + 2 quote). Run metadata, job
  sonuçları ve log test sayıları GitHub'dan doğrulandı.
- [Draft PR #3](https://github.com/FatihBirgul/trade-ai/pull/3), base PR #2 dalı;
  merge/force push yok. Sonraki teknik öneri: bağımsız ledger invariant replay
  denetleyicisi, uzun süreli kontrollü soak/recovery ve history retention tasarımı.


## 31 Ekim 2026 — Görev 12 / bağımsız journal replay

- Başlangıç GitHub PR #3 açık/Draft, f690a1301aa2f75da36d0d37a84da6f25ac93d25;
  yeni dal `codex/task12-ledger-replay-audit`. Android a14c117 ve Gateway 19038bd
  kaynaklarına değişiklik yok. [Draft PR #4](https://github.com/FatihBirgul/trade-ai/pull/4).
- cbb6c25: ledger fonksiyonlarından bağımsız mode=ro/query_only accounting audit,
  explicit-path CLI, source/immutable/hash/finansal denklik ve negatif testler.
- 4bddb47: bounded soak/recovery, lost-ack hook, dört restart, üç ikinci-journal
  arızası, kaynak bütçeleri, el hesabı oracle'ı ve auditor geliştirme regresyonları.
- 056015d: Ubuntu/Windows × Python 3.11/3.12 matrisi. Her işte 251 V2 + 11
  quote/outcome, compile; Windows launcher parse.
  [41188644740](https://github.com/FatihBirgul/trade-ai/actions/runs/41188644740)
  dört iş success; [41188786105](https://github.com/FatihBirgul/trade-ai/actions/runs/41188786105)
  iki quote işi success (her biri 251 V2 + 2 quote). Metadata/job/log sayıları doğrulandı.
- Yerel son V2 suite 251/251, quote 2/2, outcome 9/9, Gateway 42/42. API export
  f690a13 ile semantik eşit, 26 path/34 schema; finansal motor/API değiştirilmedi.
- Ölçüm: seed12, 935 event, 50 journal, 1060 kayıt, 63 audit, 225 tekrar response,
  10 lost-ack recovery; mismatch/unexpected error=0. Bilinen INCOMPLETE'ler ayrı.
  [Ham ölçüm](TASK12_SOAK_METRICS.json), [rapor](TASK12_LEDGER_REPLAY_AUDIT.md),
  [silme uygulamayan retention tasarımı](TASK12_RETENTION_DESIGN.md).
- CI'da AnyIO/Starlette deprecation ve Node/Ubuntu image annotation'ları
  bastırılmadı; test failure veya skip yok (OS'a bağlı launcher step hariç).
  Main/force push/canlı DB/özel ağ/deploy/otomatik paper değişikliği yok.


### Görev 12 son referans kapsamı düzeltmesi

Farklı primary key altında mevcut order'a eklenmiş position ve position'sız/
yanlış hesap scope'unda financial command için önce kırmızı testlerle yanlış
PASS gösterildi. Global position-order identity, close-command position varlığı
ve command account sahipliği eklendi. Yerel final suite 253/253 (227 eski,
24 audit, 2 soak). Ölçüm tekrarlandı: 935/50/1060 kayıt, 63 audit; mismatch ve
unexpected error=0. Final HEAD CI sonucu PR #4'te doğrulanarak kaydedilir;
056015d'nin dört başarılı işi önceki 251 testli checkpoint'e aittir.


## 2026-10-31 — Görev 13 domain journal teslimatı

- Başlangıç bağımsız doğrulama: PR#4 açık/Draft, `02152e9f869a14222860ff1b1aae526b4f592d09`;
  daha yeni Task12 değişikliği yok. Task13 yeni branch; main taban yapılmadı.
- A17c5209/B88026e0/C92161c9: plan, explicit extension/copy migration,
  same-transaction SQLite trigger ve gerçek lifecycle/control kanıtları.
- 1facd05: eski ambiguous manuel kısmi çıkışın eksik receipt.processed kaydı;
  önce legacy/new kırmızı regresyon, sonra düzeltme. Finansal math/JSON alanı aynı.
- D8484a00: bağımsız domain replay; delta/fact/decision/projection/sequence/head,
  account/source/preimage, zero-volume stop ve unfinished command kontrolleri.
- Ef3ba82e: eşlenik bounded soak ve dört platform CI. 285 V2 (253 eski+32 yeni),
  11 quote/outcome yerel; Gateway42/42, compile ve OpenAPI26path/34schema eşit.
- [Matrix41198231996](https://github.com/FatihBirgul/trade-ai/actions/runs/41198231996):
  Ubuntu/Windows × Python3.11/3.12 dört job success. [PR quote41198412896](https://github.com/FatihBirgul/trade-ai/actions/runs/41198412896)
  iki job success. Final docs HEAD CI PR checks'te ayrıca doğrulanır.
- Aynı binary/seed12/cycles3 iki mod finansal ID/body_hash digest'i aynı.
  935 mum/50 finansal journal/63 audit/4 restart/3 injected SQLite failure;
  journal5750, mismatch/error0. Legacy282→new0 INCOMPLETE yalnız yeni fixture kapsamıdır.
  [Ham kaynak/maliyet ölçümü](TASK13_SOAK_METRICS.json), [A–F raporu](TASK13_DOMAIN_EVENT_JOURNAL.md).
- Eski DB auto-upgrade edilmez; yeni kopyada boundary ve preflight audit.
  Tarihsel receipt mismatch bulunan kaynak reddedilebilir; otomatik history repair yok.
- [Draft PR#5](https://github.com/FatihBirgul/trade-ai/pull/5) base Task12;
  main merge/force push/production/private-network/auto-paper activation yok.
  Android0.7.2/11 ve Gateway kaynakları değiştirilmedi; gerçek PC/telefon testi yok.


## 2026-10-31 — Master P0 doğrulanmış ilk checkpoint

Task13 980340d yeniden GitHub/CI ile doğrulandı; yeni master dalı ve DraftPR#6.
3c9c7c9 envanter;39f34c2 causal pattern;6b736b2 mevcut TP1/TP2 audit yanlış pozitifi;
afba643 chronological audited research;8f2c635 altı technical method/MTF;
647358f ürünün açık dict'ine descriptive version3 context;2a7320c bounded/frozen/
legacy response; b172ce8 research money biçimi. Son code suite334/334,11quote/outcome,
Gateway42; compile/OpenAPI26/34 eşit. M5 matrix41224534693 dört job vequote41224540659
iki job success; final HEAD sonucu PR checks'tedir. P0/eksik aşamalar yaşayan
MASTER_MISSION/PROGRESS/VALIDATION_MATRIX/NEXT_ACTIONS'ta açık; market backtest
kârlılığı/forward veya gerçek cihaz sonucu yok. Cloud public spot300bar QC + new
methods smoke geçti; ham fiyatlar yayımlanmadı. Main/Task13/Android/Gateway/deploy/
canlı DB/özel ağ/otomatik paper izinleri ve korunan yedekler değiştirilmedi.


## Master continuation — M7–M13

PR6 HEAD4ae1fdc/currentCI bağımsız doğrulandı, yeni continuation dalı ve DraftPR#7.
84f8cb7 WF;04aa675 manifest/capture;7b4fcd1 missing candles;43c51d0 chart knowledge
ve canonical experiment;3b6893f profiles;1535a03 frozen versions/retest;
4c97f4f CLI embargo. Yerel381/381 +11quote/outcome +42Gateway,compile veOpenAPI26/34
eşit. Financial invariant/domain audit eski suite'le korunur. Ayrıntılar yaşayan
MASTER_PROGRESS/VALIDATION_MATRIX/MISSION/NEXT_ACTIONS'ta. M7..M11 matrix/quote
success; son HEAD sonuçları PR7 checks'te. Public source360bar/0sample/OOS0/trust
INCOMPLETE; synthetic mechanical OOS, gerçek piyasa başarısı veya forward değildir.
Main/Task13/PR6,Android/Gateway/production/private network/korunan yedekler değişmedi.
