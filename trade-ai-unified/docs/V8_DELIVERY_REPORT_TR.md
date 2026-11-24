# TRADE AI V8 — Türkçe ön sürüm mühendislik teslim raporu

6 Kasım 2026. Mevcut V7 motoru korunarak doğrulama ve eksik tamamlama çalışması
uygulandı. Gerçek Forex edge/forward performansı, lisanslı tarihsel veri ve Windows
MT5 broker pilotu henüz doğrulanmış değildir. Statüler aşağıda açıkça ayrılmıştır.

## A. GitHub

Başlangıç/uzak HEAD `f22190a575dfb8426a7f66d3df34c6290c7a57a2`; düzeltilmiş son
çalıştırılabilir checkpoint `a7927c100717a8f3de535da92f2c19bcbe80fefb`. Bu raporun
bulunduğu dokümantasyon commit'i son teslim commit'idir; tam son HEAD final mesajda
ve PR'dadır. Dal `codex/unified-forex-engine-v6`, mevcut draft PR:
https://github.com/FatihBirgul/trade-ai-unified/pull/1 . Depo PRIVATE kalır.

Main4df4b48 korunmuştur. Day Trader fdcdd418… ve V2 b6911160… checkout'ları temizdir.
trade-ai-pwa/android/gateway dahil korunan depolara yazılmadı; main merge/force-push,
production DB mutation, public deployment veya gerçek/demo emir yoktur.

| Commit | Mühendislik paketi |
|---|---|
|1314a7f |M0/M1 recovery; eski ATR ve stale kanıt kırmızı→yeşil regresyonları |
|9d5a8e5 |M2/M3 pattern snapshot QA ve causal FVG checkpoint/rolling ledger |
|63a3e2f |M5–M7 bounded import, tarihlenmiş maliyet, code freeze, iptal/registry |
|0aa7cac |M8/M10 resmî tarih güvenliği ve sanitized Windows pilot/margin |
|a2c224f |M4/M9/M11/M12 typed uyumluluk, revision/alert/iptal adversarial testleri |
|34e111f |M12/M13 V8 sürüm/contract/provider hata dalları |
|d6f98af |Eski isteğin yeni FVG durumunu görmesini engelleyen nedensellik düzeltmesi |
|a7927c1 |Windows rooted/UNC/drive-relative/ADS import sınırı düzeltmesi |

Sekiz kod/kurtarma commit'inden sonra son dokümantasyon/evidence commit'i vardır.
Herhangi bir kaynak taşıması veya ikinci nihai karar motoru üretilmedi.

## B. Recovery ve mevcut davranışların korunması

Çalışma ağacı temizdi; kaydedilmemiş kullanıcı değişikliği yoktu. Yerel/uzak HEAD,
branch, PR/draft/private ve main doğrulandı. Başlangıç423+152+76=651 yeniden geçti.
V7 net-RR, asymmetric tick, frozen plan, canlı okumalar sonrası as-of, closed MTF,
crypto real-volume ve no-order kapıları korundu. Source manifest/MIT attribution
korunur; V8 yeni modüllerin hash/provenance kayıtları ayrı JSON'dadır.

Severity audit yüksek iki geçmişe bakma sorununu yeniden üretti: son ATR'nin geçmiş
swing/equality etiketini değiştirmesi ve stale kanıtın yeni yönü veto etmesi. Bunlar
ilk-known toleransı ve evidence lifecycle/age kapısıyla düzeltildi. Ek concurrency
regresyonunda eski istek daha yeni FVG ledger durumunu görebiliyordu; artık reddedilir.
V8_AUDIT.md ve ilgili testler kanıttır. Bu resmî sertifikasyon değildir.

## C. Analiz, pattern lab, yapı/FVG ve confluence

Yeni formasyon adı eklenmedi. Mevcut11 candle/16 chart geometri ailesi ve gerçek V2
pivot/slope yardımcıları korundu. V8 laboratuvarı kimlik/sürüm, required bars/pivots,
tick, first-known/confirmation/expiry/invalidation, source evidence/test status ve
confidence semantiği taşır. Direct detector girişlerine closed snapshot/QC kapısı
kondu; yalnız dış engine kontrolüne güvenilmez.

Fiyat translation/scaling, mirror, prefix, min tick, bozuk son mum, nonstructural
noise ve gelecekte/kapanmamış/eksik/yanlış kaynaklı mum testleri eklendi.12 seed816
rastgele yolun detection oranı kaydedildi; UNLABELLED engineering diagnostic olup
piyasa false-positive/accuracy/win probability değildir. Her aile için geniş gerçek
OHLC/adversarial doğrulama hâlen PARTIAL; rounding EXPERIMENTAL; yön yetkisi yoktur.

HH/HL/LH/LL/equality/zone toleransı ilk bilinen prefix ATR'sinden dondurulur. FVG
ledger oluşum, partial fill, mitigation, closed invalidation, expiry ve re-entry'yi
bilinebilir zamanlarıyla tutar.128 event/15 bar warmup, explicit bounded eviction,
identity/QC/revision kontrolü, checkpoint/hash/schema ve replay/restart semantiği
vardır. API store provider'a aittir, kilitlidir ve24 anahtarla sınırlıdır. Eski snapshot
yeni ledger'ı kullanamaz. Derin kalıcı cross-process geçmiş ayrıca kurulmamıştır.
FVG yalnız OHLC sezgisidir; gerçek likidite/emir hacmi iddiası yoktur.

Confluence hâlâ actual V2 reducer'ı kullanır. Future/unconfirmed/expired/invalidated/
stale kanıt önce reddedilir. Aynı event/related-event tek temsilci; descriptive
pattern karşıt authoritative kanıtı gizleyemez. Volatility/MTF/news/pattern nötr
bağlamdır. Brüt skor kalibre kazanma ihtimali değildir. Divergence V7 asenkron pivot
teyit kurallarını korur; invalid pattern risk/session veto yetkisini aşamaz.

## D. Dört Forex stratejisi

Trend+momentum, range/mean-reversion, confirmed breakout ve failed breakout/sweep
korundu. Entry rule/parameter version, history, regime/capabilities, maximum age,
closed-candle confirmation, invalidation ve executable stop/target/net-RR kapıları
çalışır. Crypto real-volume şartları gevşetilmedi. BUY/SELL çelişkisi gerekçeli WAIT
üretir. Aynı closed setup kimliği API istekleri arasında kararlıdır; structure alert
kimliği artık değişen tick snapshot'ından değil gerçek closed event'ten türetilir.
Setup expiry/invalidation yerel olay üretir, dış push/SMS yoktur. Bu ailelerin gerçek
piyasa edge'i IMPLEMENTED_UNVERIFIED_IN_MARKET durumundadır.

## E. Finans, point-in-time broker ve stress

V7 independent195/115=39/23 ve asymmetric95/225 BUY/SELL oracle'ları; XAUUSD/EURUSD/
GBPUSD/USDJPY ve USD/EUR/JPY sentetik hesap-unit/grid/minimum risk testleri korunur.
Yeni tarihlenmiş cost_assumptions: hesap para biriminde round-trip/lot komisyon,
spread_price/slippage_price; eksikse yalnız açık fixed-bps simülasyon varsayımı.
Entry ve exit kendi geçerli round-trip tarifesinin yarısını öder. Bağımsız4→10
komisyon oracle'ı2+5=7,400 brüt→393 net/lot ve R393/104 sonucunu doğrular.

SELL exit spread'i doğru tarihte bid chart stop/target trigger'ına çevrilir; fiyat
seviyeleri dondurulmuş kalır. Güncel adverse stop slippage/mark spread uygulanır.
Sonradan artan maliyet/gap kaybı ilk risk cap'i aşabilir; sonuç saklanmaz. Currency/
conversion/min lot/commission/slippage stress vetoları ve negatif equity korunur.

Tarihli tick/contract/currency değişimi ve margin/leverage/swap-mode revalidation
gerektiren açık pozisyon değişimi bloklanır. Candle içi rule sınırı settlement modeli
olmadan desteklenmez. Margin/swap ve broker PIT fee arşivi uydurulmaz. Read-only
order_calc_margin yalnız diagnostic estimate'tir; mevcut pozisyonları hesaba katmaz,
order_check/order_send değildir ve işlem onayı sayılmaz. Gerçek broker doğrulaması
BLOCKED_BY_EXTERNAL_DATA/UNVERIFIED olarak kalır.

## F. Veri import, provenance ve araştırma

Local operator CLI ile salt-okunur CSV/JSON import uygulandı.8MB/2000 row; strict
identity/finality/source/contract, integer UTC ms, bid basis, OHLC/order/duplicates,
future/acquisition, timezone, session/holiday-gap ve raw hash kontrolleri vardır.
POSIX/Windows absolute/rooted/UNC/drive-relative/ADS/traversal/symlink/archives
reddedilir. Parquet decoder bilinçli UNAVAILABLE; yeni zorunlu dependency yoktur.
Elle yazılmış küçük CC0 fixture piyasadan alınmış veri gibi etiketlenmez.
Raw/normalized hash ayrı; acquisition/license/use ve declared PIT epoch coverage açık.
Güçlü source/PIT doğrulaması caller flag'iyle açılamaz.

Actual V2 train/select/freeze/test yürütücüsü genişletildi; exact source code hash'i
frozen protocol'e eklendi. Chronological validation/purge/embargo ve held-out mutation
regresyonları korunur. Veri revizyonu yeni identity üretir; aynı experiment farklı
sonuç kabul etmez. Multiple testing disclosure vardır; cross-run preregistration/
selection accounting ayrıca gereklidir. Ayrı hesap fold'ları pooled equity değildir;
strateji breakdown'ları bağımsız deney diye gösterilmez.

Cancellation bar/fold sınırında cooperative; request run ID deterministic experiment
ID'den ayrıdır. Stale run iptal edemez, başarısız/iptal sonuç registry'ye PASS olarak
yazılmaz, finally kaynakları bırakır. Bounded registry eviction/restart/race testleri
geçer. Monte Carlo seed/sample uyarıları korunur. Sentetik OOS INSUFFICIENT_EVIDENCE;
gerçek piyasa başarısı/forward observation kanıtı yoktur.

## G. Gerçek resmî kaynak kapsamı

BLS ICS korunur. V8 gerçek bounded probe Fed HTML54, ECB HTML34, BEA ICS169 kayıt
ayrıştırdı. Count/hash/retrieval JSON'dadır; tam feed/page republished edilmedi.
Fed/ECB date-only kayıtlarına açıklama saati uydurulmaz. Optional risk filtresi
belirsiz yerel toplantı günü/range'ini açık conservative bağlam olarak veto eder.
Fed cross-month biçimlerinin bir kısmı hâlen unsupported; tam coverage iddiası yoktur.

BEA UTC saatleri ICS'den gelir. DTSTAMP, yayın zamanı kanıtı değil record timestamp
olarak ayrıldı; published_utc NULL kalabilir. known/retrieved ayrı, legacy alanın
FIRST_OBSERVED_RETRIEVAL semantiği açıktır. Actual, gerçekleşmeden bilinemez; equal
revision çatışması son retrieval ile gizlenemez. Tarihsel as-of filtreleri testlidir.

BoE direct fetch403→DATA_UNAVAILABLE, bypass/fallback yok. BoJ adapter fixture-tested;
kullanım/olası ticari izin incelemesi bekler. Default usage gate kapalıdır. Kaynak
araştırması legal certification değildir; kuruma mesaj/izin isteği gönderilmedi.
Feed URL/terms/limitations V8_MACRO_COVERAGE.md'dedir. API default provider ayrıca
yapılandırılmadan otomatik verified calendar servisi oluşmaz.

## H. Windows MT5 pilotu

scripts/windows_pilot.py; scripts/reconcile_pilot.py; Türkçe adımlar
V8_WINDOWS_MT5_HANDOFF.md. Paket JSON evidence/code hash, timestamp, whitelisted
broker/symbol/contract/tick/grid/stops/directions/currency, bid/ask/tick age, read-only
profit/margin samples, missing configuration ve recommended next test üretir.
Login/account number/username/terminal path/password/token/free cash alanları export
edilmez; raw exception metni paylaşılmaz. Reconciliation yalnız bounded sanitized
financial fields üzerinden yapılır. SDK forbidden method regression'ları geçti.

Gerçek Windows terminali çalıştırılmadı. Linux smoke DATA_UNAVAILABLE/UNVERIFIED
verdi, fixture'a geçmedi. Mock doğrulaması, kullanıcı terminalindeki pilotun yerini
almaz. Broker tatil/seans/DST bilgisi authenticated sayılmaz.

## I. API, concurrency ve güvenlik

Engine8.0 /api/v6/schema6 ve40 eski path'i korur; toplam41 actual path. Tek yeni
endpoint POST /api/v6/research/cancel; strict active run_id. Nested EntryZone,
LotSizing, CostAdjustedPlan ve RiskPolicy şemalandırıldı; JSON fields/dict-style
Python compatibility korunur. V7 kayıtlı örnekleriyle regression testleri geçer.
Tüm vendor iç sözlüklerinin typed olduğu iddia edilmez. Actual OpenAPI/route/example
çıktıları V8 dosyalarındadır.

422 schema/contract,409 stale cancel,429 bounded active research,404 missing
registry ve503 provider durumları testlidir; mevcut HTTP semantiği korunur.
Symbol isolation, provider request cache, stable alert dedup ve registry yarışları
sınanır. Localhost/default no CORS allowance; public unauthenticated hosting yok.
Dosya path import'u HTTP'ye açılmadı. No order, account mutation, production DB,
source write veya frontend/PWA değişimi yapılmadı.

## J. Testler, CI, coverage ve performans

651 başlangıç→682 final:423 V5+152 seçilmiş V2+107 host.31 yeni anlamlı host testi.
Final failure0, skipped0. Linux local3.11.17/3.12.14 compile/source/host/coverage geçti.
Code CI42214034689, a7927c1 için Windows/Ubuntu×3.11/3.12 dört iş başarılı; her logda
423/152/107 ve SHA doğrulandı. https://github.com/FatihBirgul/trade-ai-unified/actions/runs/42214034689

İlk CI42213715258 Windows path testinde başarısız oldu: /etc/passwd is_absolute tek
başına Windows için yeterli değildi. Gerçek hata düzeltildi; test silinmedi/skip ile
gizlenmedi. Son dokümantasyon commit'i ayrıca dört CI işine girer; tam final SHA/run
PR checks/final mesajdadır. Makine kanıtı V8_VALIDATION.json.

Coverage yalnız unified_forex:2075/2173 statements=%95,49;632/804 branch=%78,61.
Baseline %93,56/%75,27: +1,93/+3,33 puan. Combined=%90,93. Vendor/Windows terminali/
piyasa kapsamı değildir. Offline guard soket/DNS'i kapatır, SQLite temp kökle sınırlı.

Üç tekrar sentetik Cloud median: analysis66,97ms;4-symbol364,65ms;MTF183,46ms;
candle2,70ms;chart11,26ms;confluence (100 observations) 1,31ms;500-bar1,27s;2000-bar8,86s;
OOS1,34s;Monte Carlo9,77ms;TestClient86,52ms. P95 için3 sample yetersiz, raporlanmadı.
Ayrı Python allocation peak RSS değildir. Benchmark checkpoint d6f98af; son importer
path guard'ı ölçülmeyen modülde değişti, ölçülen tüm modüller byte-identical olarak
kontrol edildi. Ayrıntılar V8_BENCHMARK_RESULTS.json. Gerçek Windows/MT5 latency
veya piyasa kârlılığı çıkarımı yapılmaz; concurrent Cloud test yükü vardı.

## K. Durumlar ve kalan engeller

| Bileşen | Doğru durum |
|---|---|
|Capture/QC/financial math/typed envelope/router |VERIFIED_OFFLINE; market edge unverified |
|Pattern snapshots/metamorphic/random diagnostics |VERIFIED_OFFLINE invariants; family real-OHLC validation PARTIAL |
|Rounding/sınırlı family geometry |EXPERIMENTAL, NON_DIRECTIONAL |
|FVG lifecycle/checkpoint/rolling/as-of |VERIFIED_OFFLINE; deep durable history PARTIAL |
|Dated costs/import/code freeze/cancellation |VERIFIED_OFFLINE mechanics |
|Parquet bounded decoder |MISSING/UNAVAILABLE dependency design |
|Gerçek broker PIT/margin/swap/holidays/D1 |BLOCKED_BY_EXTERNAL_DATA |
|Fed/ECB/BEA bounded source parsers |IMPLEMENTED_UNVERIFIED_IN_MARKET, coverage PARTIAL |
|BoE direct erişim/BoJ usage |BLOCKED_BY_EXTERNAL_DATA/USAGE_REVIEW_REQUIRED |
|Windows sanitized pilot tools |VERIFIED_OFFLINE; actual MT5 UNVERIFIED |
|Real licensed Forex/OOS/forward evidence |BLOCKED_BY_EXTERNAL_DATA, INSUFFICIENT_EVIDENCE |
|Public hosting/auth, durable multi-user jobs/alerts |MISSING, intentionally not deployed |

M0/M1 recovery/audit, M3/M4 causal guards, M6 independent financial stress, M7
research reliability, M9 services/concurrency, M11 contract, M12 adversarial gates
ve M13 measurement offline kanıtlarıyla teslimdir. M2 kapsamlı market-labelled family
QA, M5 authenticated PIT/Parquet, M8 complete official coverage ve M10 real terminal
pilot dış bağımlılık/kısmi durumları korur. M14 docs/CI/draft teslimi bu kanıtları
birleştirir; bütün misyonun piyasa doğrulaması tamamlandı denmez.

## L. Sonraki mühendislik eforu

NEXT_ACTIONS.md sıra/dependencies içerir. İlk adım salt-okunur Windows pilot ve
lisanslı bid/ask/PIT archives; sonra labelled family QA, preregistered real-data OOS,
cost stress ve forward observation. Macro usage/access/coverage ve bounded optional
Parquet decoder, deep durable lifecycle/revision policy ve istemci handoff devam eder.

Tahmin mühendislik yargısıdır:9–22 engineer-day; erişim hazırsa en iyi yaklaşık2
hafta, gerçekçi3–5 hafta tek mühendis. Access/permission waits ve forward gözlem süresi
hariç. Broker çeşitliliği, arşiv/lisans ve gerçek false-positive bulguları belirsizliği
belirler. Kesin teslim tarihi, production-ready veya garantili kârlılık iddiası yoktur.
