# TRADE AI V7 — Türkçe teknik teslim raporu

6 Kasım 2026. Bu çalışma V6'nın mevcut özel deposu üzerinde sürdürülmüştür.
Mühendislik checkpoint'i teslim edilmiştir; bütün formasyonların piyasa doğrulaması,
gerçek Windows MT5 ve gerçek veriyle strateji başarısı tamamlanmış değildir.

## A. GitHub

Başlangıç: `ce01eb8933e45e8cd25af6b34418d19f0026c26c`; son çalıştırılabilir kod
checkpoint'i: `a108c9dddc9208574054cb9e6933b36976fc61b8`. Dokümantasyon teslim
commit'i bu raporun bulunduğu commit'tir; son HEAD PR üzerinden görülebilir.
Dal: `codex/unified-forex-engine-v6`. Mevcut PR korunmuştur:
https://github.com/FatihBirgul/trade-ai-unified/pull/1 . Draft kalır.

V7 kapsamında yedi kod/kurtarma commit'i ve son dokümantasyon commit'i vardır:

| Commit | Mantıksal kapsam | Doğrulama |
|---|---|---|
| cb37681 | M0 recovery, kaydedilmemiş V6 çıktılarının korunması, severity audit |622 baseline, dört eski CI işi |
| 2dcfe5c | Finansal/session düzeltmeleri |Üç kırmızı hata yeniden üretildi; yeni4 test ve host51 geçti |
| ba6f1ed | Mum/grafik geometrisi, yapı yaşam döngüsü, divergence |Host60 checkpoint; aile testleri genişletildi |
| 21cb25b | Veri/kural manifesti, validation/freeze, deney kayıtları |Host65 checkpoint, as-of hash ve registry testleri |
| 4822da2 | Broker diagnostic, macro, alerts/API/risk |Host74, kaynak423+152 geçti |
| 53b1736 | Descriptive kanıtın conflict veto'yu gizlemesini önleme |Kırmızı→yeşil regresyon, cache/profiling |
| a108c9d | Tarihsel session/contract/retrieval sınırları, aile bazında causality |Son host76; dört CI işinde651 |

PRIVATE görünürlük yeniden doğrulanmıştır. Main `4df4b48` olarak korunur; merge ve
force-push yoktur. Kaynak checkout'lar temizdir: Day Trader `fdcdd418…`, V2
`b6911160…`; eski kaynak PR1/PR7 head'leri ve draft durumları değişmemiştir.

## B. Recovery

Yerel/uzak HEAD ce01eb8 ile eşleşti. İzlenen veya staged fark yoktu; üç untracked
JSON dosyası vardı ve silinmeden cb37681 ile korundu. Arayüzdeki21 dosya özetinin
kaydedilmemiş21 dosya olduğu varsayılmadı. Eski CI42144724852 dört işte başarılı;
Windows3.11 logunda423/152/47 ayrıca doğrulandı. Yerel baseline622/622 geçti.

`forex-cost-netrr-v6-2` ve canlı okumalar SONRASI as-of düzeltmesi gerçekten mevcuttu;
yeniden yazılmadı. Bağımsız195/115=39/23 maliyet oracle'ı ve unsized net-RR veto'su
korundu. V7 sürümü asimetrik profit/loss tick dönüşümleri ve hesap para biriminde
brüt R/R ayrımını ekler. Replay yeni açılışta stop/TP'yi kaydırma hatası giderildi.
Audit: V7_AUDIT.md. Kalan kritik/yüksek bulgu tespit edilmemiştir; bu bir resmî
güvenlik veya piyasa sertifikası değildir.

## C. Gerçek kaynak yeniden kullanımı

Day Trader capture/provider/ATR plan/lot/risk/session, confirmed pivot, RSS parser,
alert ve bootstrap kodu gerçekten çalışmaktadır. V2 QC/capabilities, numerical
varyantlar, price action/regime/candle/chart, MTF, Evidence/build_confluence,
router ve train/select/freeze/test protokolü korunmuştur. Kaynak taşıması tekrarlanmadı.
Yeni chart adaptörü V2 `_pivots`/`_slope` yardımcılarını; lifecycle V5 confirmed pivot
çıktılarını kullanır. V2 ürün ledger/DB/auto-paper modülleri çalışmaya bağlanmadı.

Başlıca sürümler: engine7.0.0; risk forex-cost-netrr-v7-1; strategy fx-price-setups-v7-1
(aile version2); candle fx-candle-catalog-v7-1; chart fx-chart-geometry-v7-1;
structure fx-structure-lifecycle-v7-1; divergence fx-aligned-divergence-v7-1;
confluence fx-provenance-confluence-v7-1; dataset fx-dataset-manifest-v7-1;
walk-forward v2-walk-forward-fx7-1. Dosya hash manifesti günceldir.

## D. Teknik analiz

Canonical EMA/RSI/MACD/ATR/Bollinger tanımları korunur; rolling/Wilder, seed ve
sample/population farkları ayrı sürümlüdür. Gerçek hacim bulunmadığında VWAP ve
volume-based crypto yöntemleri açılmaz. RSI ve MACD regular/hidden bullish/bearish
divergence, eşleşen ayrı indicator/fiyat pivotlarının EN GEÇ teyit zamanında bilinir.

11 yeni mum geometrisi eklenmiştir. Positive, flat-negative, uygun mirror, minimum
tick, fiyat birimi ölçekleme ve HER yeni aile için teyitten önce/sonra prefix testleri
vardır. Modified Hikkake korunur. Ladder/Mat Hold/Concealing gerçek V2 koduyla ayrıca
sınanır; eski aileler gereksizce yeniden yazılmaz. Tüm pattern'lar betimleyicidir.

16 grafik ailesi geometri kataloğu vardır: bull/bear flag, pennant, üç triangle,
rounding bottom/top, rectangle/channel, iki wedge, double top/bottom ve iki shoulder.
Gerçek pole, confirmed pivot, çizgi uyumu/containment, width/tick toleransı, neckline
ve iki kapanışla breakout ayrıdır. Retest, failure ve expiry mevcut. Rounding
experimental kalır. Katalog PARTIAL_FAMILY_VALIDATION: her ailenin gerçek OHLC üzerinde
tüm zamanlama/adversarial false-positive sınırlarının doğrulandığı iddia edilmez.

Yapı HH/HL/LH/LL/equality, BOS/CHoCH, zone/retest/invalidation/expiry ve önceki20 bar
range'ini zamanlarıyla sunar. FVG halen V2 active-only kapsamındadır; tüm dolmuş
geçmiş gap'lerin ledger'ı eksiktir. Sweep/reclaim yalnız OHLC sezgisidir. Order book
ve kurumsal likidite kanıtı yoktur.

Confluence gerçek V2 reducer'ı kullanır. Karşıt authoritative kanıt veto'su dedup
ÖNCESİNDE hesaplanır; güçlü descriptive etiket onu gizleyemez. Aynı olay/cross-frame
related_event tekrarı ayrı oy sayılmaz. Volatility/news/MTF/pattern nötr bağlamdır.
Regime/MTF/session/spread/risk veto yetkisi korunur. Dört Forex aile ID'si aynıdır;
strict sürümlü parametreler, maximum age ve sabit setup kimliği eklenmiştir.

## E. Finansal doğruluk

BUY ask, SELL bid girişleri; SELL ask çıkışlarının bid chart trigger dönüşümü açıktır.
Tick/point/price/volume grid, broker yön/minimum stop ve minimum lot risk kapıları
korunur. Eksik para birimi/dönüşümle lot yoktur. Broker stop profit'i pozitifse BLOCK.
Profit/loss tick değerleri farklıysa hesap para birimindeki brüt R/R, fiyat R/R'sinden
ayrıdır. Komisyon bir round trip/lot olarak bir kez muhasebeleştirilir. Net beklenen
TP1 ödülü komisyon sonrası; beklenen zarar komisyon+adverse stop slippage dahilidir.

Replay mutlak stop/TP'yi dondurur; kötü açılış geometry/net-RR kapısından geçmezse
reddedilir. Adverse entry slippage ayrıca uygulanır; exit slippage stop içindir.
Realized R, gerçek simüle net PnL/ilk maliyet dahil risk tutarıdır. Gap ile negatif
özkaynak ve100% üstü drawdown saklanmaz. Aynı bar stop/TP belirsizliği işaretlenir;
stop-first yalnız açık simülasyon varsayımıdır. Eski *_quote alanları ACCOUNT_CURRENCY
alias'ıdır. Margin/swap sonuçları UNAVAILABLE; leverage/free margin yalnız bilgi.

Bağımsız BUY/SELL195/115 ve asimetrik95/225; XAUUSD/EURUSD/GBPUSD/USDJPY ve
USD/EUR/JPY sentetik hesap birimi oracle'ları geçti. Bunlar gerçek broker dönüşümü,
marjin yeterliliği, swap veya maliyet doğrulaması değildir.

## F. Araştırma ve veri güveni

Aynı canonical motorun kapalı prefix'leriyle çok işlemli replay ve gerçek retained
V2 walk-forward çalışır. İsteğe bağlı chronological validation_bars, train'den purge
ile ayrılır; aday seçimi yalnız geçmiş validation/training verisine dayanır. Frozen
candidate, source/engine/risk/cost ve input digest'leri vardır. Held-out fiyat
mutasyonu önceki seçimi/frozen hash'i değiştirmez. Fold hesapları bağımsızdır;
pooled compounded equity/drawdown iddiası yoktur. Registry32 sonuç/8MB process memory,
aynı experiment ID'ye farklı sonuç kaydı yasak, restart/eviction açık. Haricî
preregistration/çoklu araştırmacı seçim kontrolü kurulmuş değildir.

Dataset manifest kaynak/venue/sembol/contract, retrieval/timezone/license/use,
frame count/range/bid-volume/hash ve QC bilgilerini taşır. Tarihli rule epoch'ları
historical timestamp'te kullanılır; coverage açıktır. Candle içi contract değişimi
ve açık pozisyon boyunca finansal contract değişimi settlement modeli olmadan
reddedilir. Static today's rules, geçmişe ait doğrulanmış kural diye sunulmaz.
SYNTHETIC_TEST/DECLARED_HISTORICAL kullanılır; güçlü doğrulama sınıfları caller flag'i
ile açılamaz. Lisanssız Forex dataset indirilmedi/yayımlanmadı.

Win/loss/trade count/expectancy/PF/drawdown/streak/holding/average R, yön/strateji/
regime dağılımları ve OOS degradation bilgileri vardır. Retained fixed-seed bootstrap
percentile outcome/DD dağılımı küçük örnek uyarısı taşır. EVIDENCE=INSUFFICIENT_EVIDENCE,
forward_validated=false. Gerçek piyasa başarısı gösterilmemiştir.

## G. API ve servisler

Koddan üretilen40 path:20 legacy,20 /api/v6. Engine7.0, schema6 yollarını korur.
Yeni GET `/api/v6/research/experiments/{experiment_id}`; analysis strategy_parameters,
OOS validation_bars ve additive broker/provenance/lifecycle/cache alanları vardır.
Strict bounded istekler, typed envelope, versioned vendor dictionaries kullanılır;
iç içe tüm vendor sözlüklerinin tamamen typed olduğu iddia edilmez.

Legacy unhealthy analysis HTTP503/WAIT; invalid query422 korunur. Aktif research
varken429; invalid budget/contract422; evicted/unknown experiment404. Singleton provider
kurulumu kilitlidir. Scanner tek sembol arızasını izole eder ve request cache reuse
eder. Alerts stable event/setup kimliği, invalidation, severity/reason/source,
cooldown, bounded storage ve restart semantiği taşır; dış bildirim gönderilmez.

Windows read-only diagnostic exact symbol/server, bid/ask/tick age, contract/tick/
volume/stops/mode/currency ve profit sign örneklerini sunar. SDK allowlist korunur;
order_send/order_check yoktur. UNKNOWN schedule yeni planı engeller; beyanlar
DECLARED ve authenticated=false olarak görünür. Tam/özel tarih kapanışları overnight
spill'i keser. Gerçek terminal testleri yapılmamıştır.

Resmî BLS ICS adapter'i313 gerçek kayıt ayrıştırdı; observed response21 gelecek olay
ve0 red içerdi. Kaynak DTSTAMP vermediği için source publication null, ilk bilgi
retrieval'dır. Kapsam/authenticity UNVERIFIED. Fed RSS kaynağı ve ECB/BoE/BoJ resmi
schedule'ları araştırıldı; tam provider/usage/coverage entegrasyonu hâlen kısmi.
Kaynak başarısızsa fixture fallback yoktur. Haber kesin yön üretmez.

Handoff: V7_OPENAPI.json, V7_ROUTES.md, V7_RESPONSE_EXAMPLES.json ve
FRONTEND_HANDOFF.md. Frontend/PWA/Windows projesi değiştirilmedi. Localhost8006;
public deployment/auth/HTTPS yapılmadı.

## H. Test, CI, coverage ve performans

Başlangıç622 → final651:423 korunmuş V5 +152 seçilmiş V2 +76 host testi.
Fail0, skip0. Vendor suite'leri silinmedi/gevşetilmedi. Python3.11.17 ve3.12.14
Linux local compile/suite koşuları geçti. CI42208624107 dört işte başarılı:
Windows/Ubuntu × Python3.11/3.12. Her iş logunda423/152/76 ve a108c9d SHA doğrulandı.
https://github.com/FatihBirgul/trade-ai-unified/actions/runs/42208624107
Son dokümantasyon commit'i ayrıca aynı matriste kontrol edilir; güncel PR checks
ve final mesaj son commit/run kimliğini verir. V7_VALIDATION.json makine kanıtıdır.

Coverage yalnız unified_forex: **1483/1585 statement=%93,56;411/546 branch=%75,27**.
Combined statement+branch=%88,88. Vendor, Windows terminali ve piyasa coverage'ı
anlamına gelmez. Offline guard socket/DNS'i kapatır; SQLite yalnız izole temp köktür.

Üç tekrarlı sentetik Cloud medianları; ayrı tracemalloc ölçümü RSS değildir:

| İşlem | Median saniye |
|---|---:|
| Tek XAUUSD |0,065469 |
| Dört sembol scanner |0,323895 |
| Üç timeframe |0,137726 |
| Candle catalogue |0,002910 |
| Chart geometry |0,011434 |
| Gerçek V2 confluence100 |0,001103 |
|500 bar replay |1,017795 |
|2000 bar replay |8,320868 |
| İki fold validation/OOS |1,206456 |
| Monte Carlo200×100 trades |0,008374 |
| TestClient analysis API |0,075284 |

Aynı Cloud ortamında test yükü de vardı; CPU pinning/MT5/network latency ölçümü değildir.
Tam repetitions, memory peak, provider calls/cache hit-miss ve platform bilgisi
V7_BENCHMARK_RESULTS.json içindedir. Benchmark code hash'i checkpoint ile eşleşir.
Tek analiz1 metadata+1 quote+2 frame; dört sembol scanner16 kaynak okuması yapar.

## I. Kalan engeller ve milestone durumu

| Aşama | Durum / sınır |
|---|---|
|M0 recovery |PASS:622 korunmuş, checkpoint/PR/evidence kurtarıldı |
|M1 audit |PASS offline inceleme/regresyon; resmî sertifikasyon yok |
|M2 candle |IMPLEMENTED engineering; legacy context ve kapsamlı gerçek-data validation PARTIAL |
|M3 chart |DESCRIPTIVE/EXPERIMENTAL; aile başına tam OHLC adversarial/timing PARTIAL |
|M4 structure |Pivots/BOS/CHoCH/lifecycle var; full FVG/history/persistence PARTIAL |
|M5 indicators/divergence |PASS fixture/oracle/as-of; piyasa edge UNVERIFIED |
|M6 confluence |PASS dedup/conflict/context regresyonları; calibration yok |
|M7 strategies |Dört aile/param/age/guards PASS; real-market selection UNVERIFIED |
|M8 finance |Offline independent math PASS; broker margin/swap/fees UNVERIFIED |
|M9 MT5/sessions |Mock/read-only tooling PASS; gerçek Windows/D1-DST UNVERIFIED |
|M10 provenance |Manifest/epochs/coverage PASS; source/PIT authentication UNAVAILABLE |
|M11 OOS |Train/validation/freeze/test/registry mechanics PASS; real evidence insufficient |
|M12 macro |BLS actual retrieval/parse var; diğer feed/coverage adapter'ları PARTIAL |
|M13 services |Bounded scanner/alerts/concurrency PASS; durable delivery yok |
|M14 API |40 route/legacy/security/budget PASS; full nested typing/public hosting yok |
|M15 invariants |Financial/data/research/confluence/security regression PASS |
|M16 E2E |Offline scenarios PASS; fixture sonuçları market validation değildir |
|M17 performance |3-repeat measured PASS; canlı Windows/MT5 profiling yok |
|M18 final |Compile/suites/source manifest/coverage/CI/docs PASS; PR draft kalır |

Ek engeller: licensed historical bid/ask ve broker contract/cost archives; authenticated
session/holiday feed; rollover/swap/margin validation; complete source calendars;
forward observation; kalıcı state ve araştırma cancellation/multi-user scheduling.
Gerçek/demo emir, account mutation, kaynak yazımı, DB müdahalesi ve main merge yoktur.

## J. Devam planı

NEXT_ACTIONS.md ayrıntılı sıra ve bağımlılıkları taşır. İlk iş ayrı Windows chat'inde
read-only diagnostic ve broker kontrat/session kanıtıdır. Sonra lisanslı tarihsel
veri/point-in-time archive ile preregistered OOS, cost stress ve forward observation.
Aile bazında gerçek-OHLC/adversarial fixture derinleştirmesi, full FVG/zone history,
macro provider/coverage ve PWA refusal/null/provenance eşlemesi tamamlanmalıdır.

Öngörü mühendislik tahminidir:11–23 engineer-day; erişimler hazırsa en iyi2–3 hafta,
gerçekçi3–5 hafta (tek mühendis). Veri/terminal erişim beklemesi ve ileri gözlem süresi
hariçtir. En büyük belirsizlik broker farkları, arşiv/lisans ve false-positive
kontrolleridir. Kesin bitiş tarihi veya garantili kârlılık iddiası yoktur.
