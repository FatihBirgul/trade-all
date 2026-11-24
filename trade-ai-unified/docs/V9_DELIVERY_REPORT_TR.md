# TRADE AI V9 — Türkçe teslim raporu

V9, mevcut birleşik motorun9.0.0-rc1 mühendislik checkpoint'idir. Kritik state,
fiyat tarafı, import ve araştırma kimliği riskleri giderildi. Offline RC kapıları
geçti; gerçek piyasa güvenilirliği/kârlılık doğrulanmadı. Genel durum
IMPLEMENTED_UNVERIFIED_IN_MARKET. V9_GATES.json her kapının sınırını kaydeder.

## A. GitHub checkpoints

Tek yazılabilir depo private FatihBirgul/trade-ai-unified; branch
codex/unified-forex-engine-v6. Başlangıç/remote HEAD doğrulandı:
d2bf026885cec0dcbf0ac803a589b5cfdb95b9a0. Son çalıştırılabilir kod checkpoint'i:
f1cf856d34dd3d1b0f8fbbcbc8d806ab3909b858. Bunu izleyen teslim commit'i yalnız
belge/kanıt içerir; tam son SHA PR ve GitHub commit geçmişindedir, son kullanıcı
mesajında bildirilir. Code SHA256:
04f874f4b085ec212686a86553fa6f840a3138d653a8ce517e8bd77ab56d7c59.

Mevcut [PR1](https://github.com/FatihBirgul/trade-ai-unified/pull/1) draft korunur.
Main4df4b48556df0a5e8a32324fdbf6d9d3bf1e5203 değişmedi; merge/force push yok.
Kaynak A fdcdd418d96d05e71453e70c1f39956dd1cfe9d5, kaynak B
b69111608ea3c2e78609fd84a0d81dee2781c980 salt okunur kaldı.

Kod commitleri:

```
5dd7e4b fix(recovery): own FVG checkpoints and bind incremental state to data source
460c03e feat(history): bind paired bid-ask replay and harden bounded import and frozen research protocols
43c24f8 feat(evidence): validate pilot input, persist scoped checkpoints and separate forward observations
4ba5b28 feat(rc): monitor official calendar changes and expose V9 evidence-safe release candidate
57b0927 fix(identity): normalize cross-platform source hashes and validate restored chronology
f1cf856 fix(windows): separate cross-API file timestamps from handle mutation checks
```

## B. Recovery — VERIFIED_OFFLINE

Başlangıçta temiz branch/status/diff/remote ve SHA incelendi. V8 raporları ile
kod karşılaştırıldı;423 V5+152 V2+107 host=682 test tekrar geçti, fail0/skip0.
Mevcut canonical motor, V2 reducer, dört strateji, divergence/pattern/FVG, import,
dated costs/rules, cancellation, calendar, pilot ve41 rota korundu. Eski motorlar
bir daha birleştirilmedi. V8 kanıt dosyaları tarihsel kayıt olarak saklandı.

## C. Gerçek geliştirmeler ve giderilen hatalar

- HIGH: dışarı verilen checkpoint canlı FVG event sözlüklerini paylaşıyordu;
  bağımsız kırmızı/yeşil testle sahiplik kopyası ve locking düzeltildi.
- HIGH: aynı instrument ile farklı provider-source incremental update kabul
  ediliyordu; ledger/checkpoint kaynak bağlama ve restore QC eklendi.
- Import check/open ve aynı boyutta değişim risklerine descriptor yürüyüşü,
  pre/open/post identity kontrolleri; JSON depth/duplicate/nonfinite sınırları.
- Paired bid/ask import ve replay: BUY gerçek sağlanan ask, SELL ask-side exit;
  side/hash/PIT identity bağımsız oracles ile sınandı.
- Historical quote zamanı artık gerçek son kapalı bar zamanı; replay clock ile
  tazelik uydurulmaz. Epoch broker/source/account-currency değişimi reddedilir.
- Yeni data_sides, research_protocol, pilot_validation, checkpoint_store ve
  decision_journal modülleri; ayrı analiz/backtest motoru yok.
- Fed cross-month/year ve coverage değişim özeti. Cross-OS code hash POSIX yol
  normalizasyonuyla aynı kaynak baytlarında eşleşir.
- Windows3.12'de CI ile bulunan stat/fstat ctime uyumsuzluğu düzeltildi;
  aynı handle mutation kontrolü korundu. Hata gizlenmedi/skip eklenmedi.

V9_AUDIT.md, V9_SOURCE_PROVENANCE.json ve ilgili yeni testler kod kanıtıdır.

## D. Market data — IMPLEMENTED_UNVERIFIED_IN_MARKET / PARTIAL

Yedi veri türü açık capability tablosuyla ayrıldı: BID_OHLC, ASK_OHLC,
BID_ASK_OHLC, QUOTE_TICKS, MID_ONLY, MODELLED_SPREAD, EXECUTION_COST_ARCHIVE.
CSV/JSON yalnız bid veya synchronized paired side OHLC import eder. Ask-only/mid
canonical analize girmez; tick arşivi doğrulanabilir ama tick executor MISSING.
Parquet UNAVAILABLE; bounded güvenli decoder ve CI kurulmadan ağır bağımlılık yok.

Venue/contract/source/timestamp/finality/volume-kind eşleşir; ask<bid reddedilir.
Hash iki fiyat tarafını kapsar. OHLC ekstremumları aynı anın tick kaydı değildir.
Bid-only spread modelled, paired side declared-observed; maliyetler DECLARED,
authentication false. Lisanslı gerçek archive sağlanmadı: BLOCKED_BY_EXTERNAL_DATA.
Kaynak beyanı/hash geçmesi lisans veya broker/PIT doğrulaması sağlamaz.
V9_MARKET_DATA_CONTRACT.md ve V9_DATA_CAPABILITIES.json ayrıntıları içerir.

## E. Financial — VERIFIED_OFFLINE; canlı doğrulama UNVERIFIED

Retained dört varlık/USD-EUR-JPY, asymmetric tick, lot grid/min-risk, commission,
spread/slippage, net-RR/gap ve frozen SL/TP goldens korundu. Yeni BUY oracle
2000bid/2000.2ask ->2004 exit için380*lots ve380/120 R; SELL oracle bid stop'a
ulaşmazken ask spike ile stop loss100*lots. Beklenen değerler üretim fonksiyonundan
hesaplanmadı. Entry ask/bid, exit bid/ask, stop-first ambiguity ve dated cost
hesabı kullanılır. Mevcut fee-jump oracle korunur:2+5=7 commission,400->393 net.

Epoch broker/server/source/account-currency mismatch ve unsupported conversion
refuse eder; açık pozisyonda sözleşme değişimi sessiz settlement yapmaz. Margin/
swap/rollover ve gerçek historical currency conversion UNVERIFIED/UNAVAILABLE.
Varsayımlı net sonuç broker performansı değildir. Gerçek terminal karşılaştırması
BLOCKED_BY_EXTERNAL_DATA; V9_FINANCIAL_VALIDATION.md sınırları açıklar.

## F. Structure/pattern — VERIFIED_OFFLINE + PARTIAL/EXPERIMENTAL

FVG creation/partial fill/mitigation/invalidation/expiry/re-entry, bounded history,
revision rejection, replay ve checkpoint restore korundu. Yeni source ownership,
deep copy, locks, stored chronology/QC ve optional project-local16-file persistence
var. Eski unsigned checkpoint sessiz migrate edilmez; geçmiş replay gerekir.
Hash dijital imza/source authentication değildir.

11 candle+16 chart geometri ve retained V2 aileleri korundu. Mevcut positive/
negative/prefix/mirror/scale/tick/translation/finality testleri geçti; V9 yeni
per-family gerçek etiketli piyasa çalışması yapmadı. Tam adversarial family timing
kapsamı PARTIAL, rounding EXPERIMENTAL, real-market labelled validation MISSING.
Random-path eşleşmesi gerçek false-positive oranı değildir. Gelecek test önceliği
pivot/breakout sınırları, eksik seans/expiry ve gerçek OHLC venue varyasyonudur.
V9_STRUCTURE_PATTERN_VALIDATION.md kapsamı ve sınırlamaları kaydeder.

## G. Confluence/strategies — VERIFIED_OFFLINE

Gerçek V2 reducer ve dört Forex stratejisi korunur. Correlated momentum çift oy
olmaz; expired/invalidated/descriptive evidence yön otoritesi kazanmaz. Confirmed
divergence, BOS/CHoCH, breakout/retest, MTF/regime ve FVG kapalı bar/as-of koşulları
ile çalışır. Volatility/macro yalnız context/veto; no real volume durumunda volume
stratejisi unavailable; güçlü çelişki WAIT/NO_TRADE, closed session/high spread/
missing contract metadata/insufficient net-RR planı engeller. Retained setup ID,
repeat-request/tick/expiry testleri geçti. Yeni gerçek-market başarı iddiası yok.

## H. Backtest/OOS — VERIFIED_OFFLINE + PARTIAL

Mevcut replay ve V2 train/validation/select/freeze/test kullanılır. Paired ask
prefix'i cutoff ile kırpılır. Held-out ask değişimi experiment ID'yi değiştirirken
önceki frozen seçim değişmez. Dataset/rules/cost/code/config/folds/seed/criteria
manifest'e bağlanır; değişiklik preregistration verify ile reddedilir.

Local preregistration dış zaman damgası/attestation değildir. TrialRegistry16
campaign,100'e kadar frozen budget ve completed/cancelled/failed tüm başlayan
attempt'leri sayar; export ve bounded existing ExperimentRegistry korundu.
Restart/başka process/başka campaign ile global denemeleri zorla takip etme PARTIAL.
Cancellation cooperative; publication sınırlarında dağıtık transaction garantisi
yok. Tekrarlanan OOS yeni bağımsız piyasa kanıtı değildir. Veri yokluğunda
INSUFFICIENT_EVIDENCE; VERIFIED_BID_ASK_REPLAY üretilmez. V9_RESEARCH_PROTOCOL.md.

## I. News/calendar — PARTIAL

2026-11-06 resmî URL fresh probe: Fed57, ECB34, BEA169; BLS313 kayıt/20 gelecek.
Fed V8'de54'tü; sayı sabit varsayılmadı. Cross-month/year DATE_ONLY parsing ve
payload/event-ID/schema/upcoming/added/removed özeti eklendi. İlk probe değişim
geçmişi kanıtı değildir. Revision-vintage archive ve complete macro coverage yok.

BoE unavailable (önceki403), bypass yapılmadı. BoJ USAGE_REVIEW_REQUIRED,
automatic retrieval/redistribution kapalı. Permission talebi gönderilmedi.
Tarih-only event kesin açıklama saati üretmez; retrieval/source/published time
ayrıdır. Macro yalnız risk/NO_TRADE, BUY/SELL üretmez. V9_OFFICIAL_SOURCE_PROBE.json
ve V9_MACRO_COVERAGE.md gerçek bağlanan URL/status/count/hash kanıtıdır.

## J. MT5 — IMPLEMENTED_UNVERIFIED_IN_MARKET

V8 read-only Windows pilot/reconcile korundu;256KB strict whitelist/hash/code/time/
quote/financial shape doğrulaması ve generic refusal CLI eklendi. Kişisel alanlar
whitelist dışı, hesap/login/password/token/terminal path dışarı verilmez. Başarılı
validate sonucu VALID_UNTRUSTED_LOCAL_EVIDENCE; otomatik contract override yok.
Kaynak checksum gerçek terminali kanıtlamaz. Actual Windows MT5 pilot verilmedi;
Linux'ta terminal unavailable, gerçek Windows latency UNVERIFIED. Ayrı Windows
sohbeti için V9_PILOT_HANDOFF.md kısa Türkçe komutları içerir; yerel projelere
dokunulmadı. Gate L UNVERIFIED.

## K. API/operations — VERIFIED_OFFLINE; dağıtık operasyon PARTIAL

41 path/20 legacy+21 v6, schema6 ve nested finance compat korunur; endpoint yok.
V9_ROUTES.md/V9_OPENAPI.json/V9_RESPONSE_EXAMPLES.json güncel. Optional decision
journal default kapalı; immutable decision hash ve daha sonraki ayrı observation
var, outcome SIMULATED_OBSERVATION_NOT_BROKER_EXECUTION. Scheduler/order yok.

Localhost/no wildcard CORS/bounded work/generic errors/no execution SDK guard
korundu. POSIX descriptor boundary ve Windows trusted operator fallback farkı
belgeli; strict require_descriptor_boundary unsupported OS'ta refuse eder.
Concurrency/state ownership ve mevcut scanner/provider/cancel/cache testleri geçti;
multi-process durable/distributed operasyon sertifikasyonu yok. Public auth/HTTPS/
production DB/deployment yapılmadı. V9_API_CONTRACT.md ve V9_SECURITY_AUDIT.md.

## L. Tests/coverage/CI — VERIFIED_OFFLINE

Başlangıç682 -> final702 (423+152+127), passed702/fail0/skip0. Test sayısı hedefi
yoktu;20 ek test gerçek risklere bağlı. Orijinal baseline testleri değiştirilmedi.
Local Linux3.11/3.12 ve CI Ubuntu/Windows3.11/3.12 geçti. Kod CI:
https://github.com/FatihBirgul/trade-ai-unified/actions/runs/42244153003 .
Job IDs127981848593/127981848678/127981848748/127981849006; dört kaynak hash eşleşti.
Ara Windows3.12 failure42243686985 düzeltildi ve açıkça kaydedildi.

Coverage yalnız unified_forex: statement2470/2578=%95,8107 (V8 %95,4901), branch
782/1026=%76,2183 (V8 %78,6070). Branch oranı düştü; yeni hata dallarında QA açığı
saklanmadı. V9_COVERAGE.json eksik line/branch listesini içerir. Tam depo coverage
iddiası yok. V9_TEST_RESULTS.md tekrar komutları, benchmark V8 karşılaştırması ve
ölçüm sınırları; V9_VALIDATION.json sayısal kanıttır. Shared-cloud süre farkları
algoritmik hızlanma olarak sunulmadı. Real MT5 latency UNVERIFIED.

Gate A–K yalnız belgelenmiş offline kapsamda VERIFIED_OFFLINE. E, ailelerin doğru
PARTIAL/EXPERIMENTAL etiketini doğrular; tüm ailelerin gerçek piyasa doğruluğunu
kanıtlamaz. C/D/H declared-input sınırındadır. Gate L UNVERIFIED; production-ready,
kârlı veya market-validated sonuç yok.

## M. Kalan blockers ve tamamlanma kategorileri

| Alan | Durum | Gerekli kanıt/iş |
|---|---|---|
| Mevcut kaynak/test/API koruma | VERIFIED_OFFLINE | Dört CI kombinasyonu |
| Paired side replay/PIT/ledger/pilot plumbing | IMPLEMENTED_UNVERIFIED_IN_MARKET | Actual permitted archive ve broker örnekleri |
| Tam family adversarial timing/market labels | PARTIAL | Family-specific curated etiket ve sınır QA |
| Rounding/öznel chart geometrileri | EXPERIMENTAL | Bağımsız annotator değerlendirmesi |
| Lisanslı bid/ask, PIT rules/fee/FX/session | BLOCKED_BY_EXTERNAL_DATA | Provider/broker ve kullanım hakkı |
| Real Windows terminal validation | BLOCKED_BY_EXTERNAL_DATA | Sanitized fresh pilot |
| Global immutable trial accounting | PARTIAL | External attestation/durable multi-run registry |
| Parquet/tick replay | MISSING | Bounded optional decoder/tick executor için ayrı gerekçe |
| Real forward observation/labelled market study | MISSING | Önceden kayıtlı plan ve zaman içinde yeni kanıt |
| BoE/BoJ tam kapsam | PARTIAL | İzinli kaynak erişimi/usage review |

No-order sınırı korundu;0 gerçek/demo emir,0 production mutation; main merge,
force push, protected source write, kullanıcı dosyası silme veya public deploy yok.
Yalnız hedef private branch'e commit/push yapıldı.

## N. Kalan mühendislik tahmini

Erişim sağlandıktan sonra tek mühendis için planlama yargısı: data/PIT/settlement
reconciliation3–6 gün; Windows pilot1–3; labelled family/adversarial QA2–5;
calendar schema/permission integration1–3; durable research/journal ve tüketici
handoff2–4. Toplam9–21 mühendis-günü, yaklaşık2–5 çalışma haftası. Lisans/broker/
kurumsal izin beklemeleri ve ileri gözlem takvimi dahil değil. En büyük belirsizlik
veri vintage kalitesi, broker contract çeşitliliği ve family false-positive etiketleri.
Bu süre teslim veya kârlılık garantisi değildir. Somut sonraki adımlar NEXT_ACTIONS.md.
