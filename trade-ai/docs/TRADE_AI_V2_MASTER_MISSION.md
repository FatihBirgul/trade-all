# Trade AI V2 — master mission

V3/yeniden yazım yok. Başlangıç Task13 980340d; yeni branch
codex/trade-ai-v2-master-development. PR#5 açık/Draft; final Task13 matrix41198675320
ve quote41198679523 success bağımsız doğrulandı. Android a14c117 (0.7.2/11),
Gateway19038bd PR#1 açık; erişim referans amaçlı doğrulandı.

Milestone0: gerçek inventory + baseline. Milestone1: sürümlü causal candle research,
izinli QC/context/confirmation ve confluence-only evidence; default trading değişmez.
Milestone2: açık tarihsel dataset üzerinde chronological paper execution research,
Decimal maliyet/PnL/equity, bağımsız audit, OOS/walk-forward split ve validation
etiketleri. Milestone3: ek teknik yöntem/causal MTF ve güvenli configuration doğrulaması.
Her milestone unit/regression/compile→commit/push→DraftPR/CI→ilerleme kaydı.

Tüm master aşamaları bu ilk teslimatta tamamlanmış sayılmaz. Canlı DB/deploy/gerçek
para/private network/anahtar/ücretli servis yok. Otomatik paper izni genişletilmez.
Mevcut API değişmedikçe Android/Gateway kaynaklarına gereksiz değişiklik yapılmaz.
Gerçek market backtest/forward olmadan üstünlük veya başarı olasılığı üretilmez.

## Araştırma arayüzü — ürün sözleşmesinden ayrı

`pattern_research.detect_patterns`: mevcut24 legacy pattern adı korunur; eksik15
family kimliği eklendi (matching high ve yön varyantları dahil). Kurallar sürümlü,
20-bar prior context; yeni karşılaştırmalar Decimal60/HALF_EVEN. Legacy float
şekilleri yeniden yazılmaz. Son6 oluşum, maksimum4096girdi; confirmation yalnız
kapanmış next bar veya açıkça intrinsic formation. OHLC sezgisi, trade sinyali değil.
`confluence_evidence` tek mevcut candlestick bucket'ı kullanır; ürün route/score'a
kendiliğinden bağlanmaz. Hikkake/TA-Lib'in kalan ailesi tamamlanmış sayılmaz.

`research.HistoricalDataset`: tek source/venue/instrument, real volume, USDT spot,
historical/synthetic etiketi, data_version, point-in-time instrument rules ve içerik
hash'i zorunlu. Kaynak lisansı/universe/corporate/provider doğruluğunu kendi başına
kanıtlamaz.30kbar/32MiB input bütçesi; malformed/future/unfinished/duplicate/gap/
identity/frame alignment reddedilir. HistoricalProvider yalnız close<=asof prefix
sunar (300bar); MTF frame yoksa koşu başlamaz. Stale/missing input safe WAIT'tir.

`run_backtest`: aynı AnalysisService, dört strategy version, paper risk/cost/partial/
ambiguity kuralları ve domain journal kullanılır. Default simulate_orders=false.
İzin verilen research simulation gerçek endpoint/otomatik worker değildir. Yeni
TempDirectory DB dışında path kabul edilmez. Tam1m execution window, ençok5000event/
100analysis; bütçe aşımı önceden reddedilir. Her checkpoint bağımsız accounting/domain
audit'ten geçer; önceki başarısız audit final PASS ile gizlenmez. End-window forced
liquidation yok; açık/belirsiz pozisyonlar win/loss değildir. Pattern confluence ayrı
research context'tir; mevcut composite/risk izinleri değiştirilmez.

```sh
# backend; dosya mevcut, açık schema1 dataset olmalı; network fetch yok
python scripts/research_v2.py /path/to/historical.json --start-ms 1800000000000 --end-ms 1800000180000 --timeframe 1m --every 10
# yalnız owned temporary DB'de paper simulation için ayrıca --paper
```

JSON üst alanları tam olarak schema_version(1),data_kind(synthetic/historical),
data_version,instrument,source,rules,frames. Instrument mevcut Candle sözleşmesi:
symbol/market/venue/price_kind/contract_type/quote_currency. Rules:
quantity_step,minimum_quantity,maximum_quantity,minimum_notional,maximum_notional,
price_tick,source. frames {"1m":[...],"1H":[...]} satırları open_time_ms,
close_time_ms,is_final,open,high,low,close,volume,volume_kind. Timestamp UTC exclusive
close; fiyatlar sayısal string olabilir. Unknown field/duplicate JSON key reddedilir.
CLI kaynak dosyasını değiştirmez, dataset yoksa oluşturmaz. JSON stdout raporudur;
geçersiz input exit2, herhangi checkpoint audit başarısızsa exit1, integrityPASS exit0.

Metrics Decimal'dır: closed position net PnL (entry/exit fee ve adverse execution
zaten ledger'da), ambiguity dışlama, expectancy/profit factor, drawdown, win/loss
streaks. Para özetleri8hane/HALF_EVEN, negatif sıfır normal. Enaz30scoredtrade için
seed'li500IIDbootstrap percentile mean interval üretilebilir; serial dependence/
selection bias nedeniyle bu istatistik üstünlük veya gelecek başarı olasılığı değildir.
Tüm koşularda evidence_status=INSUFFICIENT_EVIDENCE/forward_validated=false.
Sentetik koşu DETECTION_IMPLEMENTED kalır. Historical etiketiyle enazbirorder ve
integrityPASS varsa BACKTESTED yalnız bu maliyet modeliyle çalıştırılma durumudur.
Kaynak etiketi bağımsız veri sertifikası değildir. Walk_forward_splits expanding
train/disjoint test+purge index planıdır; optimizer/OOS/fittedmodel performansı değildir.

## Ek teknik yöntemler ve MTF

`technical_research.compute_methods` altı named method üretir: roc12,stochastic14
(rawK),donchian20_previous (son bar hariç20),bollinger_bandwidth20 (mevcut legacy
sample-std fonksiyonunun yuvarlanmamış bandları),adx14_wilder (+DI/-DI/ATR) ve
supertrend10_3. Wilder14 TR/DM seed,14DX mean ile ilkADX28mumda; Supertrend
ATR10/multiplier3 ve retained band close crossing, seed side close>mid ile açıktır.
Warmup/flat-range/numeric-unavailable ayrı durumlar; yetersiz veriden sahte sayı yok.
Özellikle legacy float band overflow olursa unavailable_numeric_range dönülür.
OHLC-only yöntemler eksik hacmi doldurmaz; direction context emir izni değildir.

`resample_closed` continuous UTC timeframes için larger exact multiple kabul eder.
Kapalı/QC-valid kaynak tümü doğrulanır; group'un ilk/son zamanı ve bar sayısı tam
olmalı. Leading/trailing partial bar sayısı raporlanır, yalnız tamamlanan bucket çıkar.
OHLC extrema ve volume toplamı Decimal; tick/unavailable semantiği korunur.
Session calendar/Forex/DST verisi icat edilmez. Bu, kullanıcı MTF rolleri veya yeni
canlı provider/timeframe desteğinin tamamlandığı anlamına gelmez.


## İlk güvenli teslimatın kapsamı

M0–M6 milestone'ları bütün master aşamalarının bittiği anlamına gelmez. Yeni
kod b172ce8 checkpoint'inde 334 V2 testle yerel doğrulandı; PR#6 sonraki doküman
HEAD/checks'i için canlı GitHub kaydıdır. Code revert gerekiyorsa gözden geçirilmiş
normal revert commit'i kullanılır; DB rollback/reset/silme yok. Yeni productversion3
immutable kayıtlar tutulur; eski sürümün yeni kayıtları okuması ayrıca gözden geçirilir.
Yeni migration/schema yok; Task13 journaling activation/copy-migration sınırı aynıdır.

| Master aşaması | Bu teslimattaki durum |
|---|---|
|0Envanter | IMPLEMENTED; gerçek çağrı/test ve V1/V2 farkları belgelendi |
|1Mumlar | PARTIAL;24legacy+15newfamily,remainingTA-Lib/Hikkake eksik |
|2Teknik/yapı | PARTIAL;6ekmethod+mevcutpriceaction;divergence/OB/session/chart eksik |
|3Strateji | PARTIAL;4korunan;research filter sürümlü;ürün kullanıcı kombinasyonları yok |
|4MTF | PARTIAL;causal full-frame resampling;role/UI/calendar yok |
|5Backtest | PARTIAL;chronological execution+audit/metrics/foldplan;real OOS/optimizer/forward yok |
|6Scanner/7Follow | Mevcut bounded uygulama korunur; bu checkpoint'te yeni ranking/filtre yok |
|8Portföy | Mevcut muhasebe korunur;research equity/metrics var;ürün performancecurve/UI yok |
|9Kaynak | Mevcutspot korunur;Forex/XAU/news UNAVAILABLE |
|10Android/push | Kaynak değişmedi;özel diagnosticsUI ve pushdelivery MISSING/UNVERIFIED |
|11Performans/güvenlik | Stream/frozen/budget+auditfix/soak;archive/externalanchor/DBindex işi bekler |

## Gerçek hata ve yeni kodun geliştirme sorunları

Mevcut Task13 auditor'da orta önem numeric-equality yanlış pozitifi: aynı bardaki
TP1 completion için desired/fill string'leri biçim farkıyla eşit sayılmıyordu.
6b736b2 bağımsız Decimal karşılaştırması yapar; legacyengine cash/fill/PnL değişmedi.
Önce API DomainFixture10.000003 miktarla domain_tp2_condition başarısız, sonra aynı
regresyon ve tam334paket başarılı. Finansal kayıp/üretim veri bozulması iddiası yok.

Yeni research kodu içinde missing-frame/analysisbudget/checkpoint aggregation,
malformedloader,stream preallocation,mutableprovenance ve band-overflow açıkları
kırmızı testlerle düzeltildi. Bunlar eski finansal motor hataları olarak raporlanmaz.
İlk Tasuki/shortline fixture ve Decimal ratio reference context hataları açıklandı;
tanım/riske testleri yeşil yapmak için tolerans eklenmedi (ratio50decimal oracle).

## Ölçüm sınırı

[Ham ölçüm](TRADE_AI_V2_MASTER_METRICS.json): paperpaired935mum/50journal/5750domain/
63audit/4restart/3SQLiteinjection/225duplicate/10lostACK; mismatch/error0 ve iki
mod financial ID/body_hash digest'iaynı. Legacy282,newgenesis0INCOMPLETE bu senaryoya
aittir. LegacyDB3.145.728byte,journal9.428.992byte; eventappend mean0,245ms/max10,479ms;
journal audit49,486s toplam/domain34,093s. Pythonallocationpeak21.284.724byte.
Testler kısmen paralel koştu; Task13 ile kesin hız oranı veya üretim iddiası yok.
Researchsmoke3sentetikbar/1order/3journal/integrityPASS,0,497s ve2.082.397byte Python
peak. Bu smoke market backtest sonucu değil; netkâr rakamı performans kanıtı diye
raporlanmadı. Seed12/120bar/6decision ayrı fixture bütün checkpoint'lerdePASS.


Public provider smoke: mevcut BinanceSpotProvider ile 300 kapanmış 1m bar,
identity/continuity/freshness QC geçti. Aynı açık kaynak üzerinde yeni pattern
katmanı ve altı ek yöntem available; persistent DB veya işlem kullanılmadı.
Ham fiyatlar yayımlanmadı. Lisans ve tarihsel point-in-time rules doğrulanmış
sayılmaz; bu gerçek market backtest veya forward validation değildir.

M6: yeni research money formatter'ın rounded zero için8hane kaybetmesi düzeltildi;
expectancy/fee/closed net PnL sekiz hane ve normalize sıfırdır. Dimensionless ratio
aynı zorunluluğa tabi değildir. Equity drawdown yalnız kapanmış 1m markları
üzerindedir; intrabar maximum drawdown ölçümü veya borsa execution doğruluğu değildir.


## Continuation — M7–M13 (PR #7)

Base PR#6 4ae1fdc; dal codex/trade-ai-v2-master-continuation. Son kod checkpoint'i
4c97f4f6947f48f03510c198b89fae19569cae43. Yeni V3 veya main geçmişi yok.
[Draft PR #7](https://github.com/FatihBirgul/trade-ai/pull/7),
[ölçümler](TRADE_AI_V2_CONTINUATION_METRICS.json), güncel sınırlar NEXT_ACTIONS'ta.

### Walk-forward yürütümü

Önce bütün protocol/candidate/cost/version/window budget doğrulanır. Her eğitim
fold'u yalnız kendi kapanmış verisini alır; rolling başlangıcı crop edilir. Training
cadence ve mevcut selected-route filter seçilir; seçim marked equity change,
düşük drawdown ve sabit ID tie-break sırasındadır. En az belirtilen training closed
sample gerekir;0sample varsa test açılmaz. Kazanan parameters/strategy/engine/cost
hash'i held-out okumadan dondurulur. Test her fold'da bir kez yürütülür.

Purge >= declared label horizon; embargo burada held-out pencereler arasında boş
aralıktır, generic PurgedKFold CV embargo iddiası değildir. Sonraki chronological
training önceki test verisini artık bilinen geçmiş olarak kullanabilir. Train sonunda
open trades son bilinen mark ile değerlenir; sonraki outcome training label'ı olamaz.
Fold hesapları ayrı seed ile başlar; pooled continuous equity/DD/streak uydurulmaz.
Strategy/regime closed-trade attribution order'ın immutable origin analizine aittir,
fill-time regime sınıflandırması değildir.

Aynı ekonomik cost spelling/candidate sırası aynı experimentID üretir. Aynı dataset
ve protocol tekrarının yeni bağımsız OOS evidence sayılması yasaktır. Dış kullanıcının
held-out sonucuna bakıp başka deney başlatmasını bu offline araç tek başına engelleyemez;
preregistration/result registry hâlâ açık iştir. Yeni strateji/indicator threshold
optimizer yok; seçilebilir parametreler whitelist cadence/route filters ile sınırlı.
OOS_EVALUATED yürütüm durumudur; synthetic ve INSUFFICIENT_EVIDENCE ayrıca kalır.
FORWARD_VALIDATED hiçbir fixture veya historical koşu için üretilmez.

```sh
# backend; mevcut, açıkça etiketlenmiş dataset; yalnız owned temporary paper DB
python scripts/walk_forward_v2.py DATA.json --train-bars 303 --test-bars 3 --horizon 1 --purge 1 --embargo 1 --max-folds 1 --cadences 10,20 --paper
# manifest varsa --manifest MANIFEST.json; rolling için --rolling
```

CLI ilk sürümde1m evaluation kullanır; Python configuration desteklenen frame'leri,
yeterli history ve execution bütçesiyle bağlar. Maliyetler fee/spread/slippage flags
veya frozen configuration ile sabittir, optimize edilmez. Scriptte --paper açık
olmalıdır; gerçek para endpoint'i yoktur. CLI exit0 mechanical audited evaluation,
exit1 yetersiz selection/integrity,exit2 invalid input; provenance status ayrıca okunur.

### Historical kaynak sözleşmesi

Manifest v1 normalized dataset hash/source/venue/capture/normalization, license
review declaration, effective rule intervals+evidence hash ve simulation costs bağlar.
Content mismatch MISMATCH; bilinmeyen license/rules/cost evidence INCOMPLETE.
Current exchangeInfo geçmiş için kanıt değildir. Uniform rules desteklenir; değişen
rule schedule silently uygulanmaz. Raw wire payload arayüzde yoksa hash null kalır.
Review ve hash, authenticated source veya hukuki sertifika değildir.

capture_v2_history.py yalnız mevcut public provider,250..1200closed1m ve ençok4page
kabul eder; read-only GET'tir. Dataset ve manifest iki distinct NEW JSON dosyasına
exclusive yazılır. Existing target overwrite ve partial source fallback yoktur.
Ortadaki hata yalnız kendi oluşturduğu çıktıyı temizler; liveSQLite yolu kabul etmez.
Ham public OHLC bu teslimatta GitHub'a konmadı. `--help` gerekli açık UTC/path
argümanlarını gösterir; ücretli servis veya private-network adapter eklenmedi.

### Pattern ve chart kapsamı

Pattern bundle2 Hikkake3bar confirmation/expiry, LadderBottom/Top, MatHold ve
ConcealingBabySwallow içerir. Pozitif/negatif/mirror/equality/late confirmation
sınanmıştır; TA-Lib bit eşitliği veya bütün katalog tamamlandı iddiası yoktur.

Chart CLI `chart_research_v2.py DATA.json --bars 100` bounded source window üzerinde
V1 structural çekirdeğini yeniden kullanır. formed/known/confirmed zamanları farklıdır;
son fiyatla bilinen shape pivot tarihine backdate edilmez. Source max256bar/40warmup,
knowledge yalnız supplied window'da ilk observed andır. Yeni range breakout prior20bar
ve tick buffer; next closed confirmation,3bar retest/failure gözlemi. Retest sonraki
fakeout'ı gizlemez. Flags/pennants/rounding ve kapsamlı neckline doğrulaması eksiktir.
Bu pahalı prefix scan varsayılan ürün analizine eklenmedi; trade permission false.

### Kullanıcı profilleri

StrategyProfile v1 whitelist4strategy/version, indicator availability, regime ve
singleTF veya strict bias>setup>trigger seçer. 2..5 bağımsız confirmed bucket gerekir;
aynı bucket tekrarları sayılmaz. Cadence/type/range sınanır; risk/auto_paper/secret
alanları reddedilir. Profile construction strateji version snapshot'ını dondurur;
old profile ID runtime catalogue değişince değişmez. Analysis version mismatch
filter'ı kapatır. Revision/parent hash zinciri doğrulanır; imza veya access control değildir.

```sh
python scripts/profile_v2.py --output NEW-PROFILE.json --methods roc12,adx14_wilder --every 10
python scripts/research_v2.py DATA.json --profile NEW-PROFILE.json --start-ms START_UTC_MS --end-ms END_UTC_MS --paper
```

START/END açık UTC integer değerlerle değiştirilir. Parent revision için --parent
mevcut JSON; existing output asla overwrite edilmez. Profile yalnız mevcut analysis
uygunluğunu DARALTIR; alternatif route seçmez, WAIT'i canlandırmaz, risk veto'sunu
geçmez. Research configuration profile'la tam eşleşir; uyuşmazlık başlamadan reddedilir.
API/Gateway/Android selector bu checkpoint'te uygulanmadı; mevcut sözleşme korunur.

### Kanıt ve açık işler

Son yerel381/381 (44,456s), 334korunan+47yeni; quote/outcome11,Gateway42 ve compile
başarılı. OpenAPI26path/34schema eşit. Son HEAD matrix/quote CI PRchecks'tedir;
önceki checkpoint başarısı yeni HEAD'e atfedilmez. Bu oturumda eski ledger'da yeni
para hesaplama hatası gösterilmedi. Canonical IDs/zero, frozen profile metadata,
pattern index scope, retest ve CLI arg hataları yeni modüllerin geliştirme sorunlarıdır;
önce kırmızı regresyonla gösterilip düzeltildi.

Two-fold synthetic run:2candidate,2frozen test,6held-out event, auditPASS; CLI ve
chartCLI exit0. Python peak allocation ve süre ham ölçümdedir, RSS/üretim benchmark
iddiası yok. Paper domain soak793event/4848domain/27audit/2restart, mismatch/error0.
Public360bar capture+training çalıştı;0training sample nedeniyle0OOSfold. License,
historical rules ve fees INCOMPLETE; gerçek market kârlılığı/forward kanıtı yok.
P1/P2 ve kalan P0 işleri NEXT_ACTIONS'ta öncelikli biçimde devam eder.
