# Sonraki güvenli adımlar

## 11 Kasım 2026 historical main promotion

Historical kaynak `24df2ed6a6c94b8eea8548ec8980ba897057e0b5`, ana
`3c8adb8` başlangıcından yerel `--ff-only` ile entegre edildi. Recovery:
`refs/recovery/historical-main-20261111-39c4c1b98405`. Kaynak değişmedi;
source ve main kabul sonuçları V3_HISTORICAL_MAIN_TEST_RESULTS.md içinde ayrıdır.
Gerçek XAUUSDc/EURUSDc historical kanıt yok, production review listesi boş;
BLOCKED_BY_EXTERNAL_EVIDENCE ve onaysız spread BLOCK korunur. Canlı 8006
şemasında historical alan yok; runtime geçişi yapılmadı. Sonraki iş ayrı yetkili
runtime kabul/cutover ve exact broker belgesidir. Ayrıntılar:
V3_HISTORICAL_MAIN_PROMOTION_TR.md ve V3_HISTORICAL_RUNTIME_HANDOFF.md.
Aşağıdaki izole teslim ve eski promotion kayıtları tarihsel bağlamdır.

## 11 Kasım 2026 izole tarihsel kanıt paketi

`codex/v3-historical-session-evidence`, bağımsız yerel clone:
`%USERPROFILE%\trade-ai-v3-historical-sessions`. Ana V3'e aktarılmadı.
Tarihli exact Cent evidence şeması, güvenli importer, bağımsız hash-pinned
source review kapısı, provider/snapshot entegrasyonu ve read-only tek komut
hazır. Gerçek XAUUSDc/EURUSDc 6-11 Kasım kaynağı henüz yok;
`BLOCKED_BY_EXTERNAL_EVIDENCE`. Haftalık MT5 export geçmiş boşlukları açamaz.
Production review listesi boş, spread limitleri UNAPPROVED kalır.
Sonraki kullanıcı adımı yalnız orijinal broker belgesini sağlamaktır.
Prosedür: V3_EXNESS_EVIDENCE_OPERATOR_HANDOFF_TR.md. Teknik sözleşme,
testler ve aktarım sınırları: V3_HISTORICAL_SESSION_DELIVERY_TR.md.
Aşağıdaki eski promotion/runtime notları tarihsel bağlam olarak korunur.

## 11 Kasım 2026 broker main promotion

Broker readiness `93c3382` ana `codex/v3-real-readonly-analysis` dalına `09e5dab -> 93c3382` yerel fast-forward ile aktarıldı. Kaynak aynı checkout'ta zaten açık olduğundan hedef ref yerel non-force fetch ile ilerletilip aynı tree'de ana dala geçildi; 230 tracked dosyanın içerik/mtime değeri değişmedi. Recovery: refs/recovery/v3-broker-main-promotion-20261111-993349f665c2. Reload/supervisor denetimi ve süreç/schema karşılaştırması yapıldı; canlı servis restart edilmedi. Kaynak ve hedef test sonuçları V3_BROKER_MAIN_TEST_RESULTS.md içinde ayrı tutulur.

Dört spread limiti hâlâ UNAPPROVED/null/BLOCK; exact XAUUSDc tarihsel seans kanıtı dış engeldir. Canlı 8006 eski şemayı kullanır; source promotion runtime geçişi değildir. Sonraki operasyon V3_RUNTIME_CUTOVER_HANDOFF.md, frontend V3_PWA_FINAL_INTEGRATION_CHECKLIST.md ve promotion kanıtı V3_BROKER_MAIN_PROMOTION_TR.md içinde. PWA/V2/News/MT5 bridge yazımı, push veya uzak merge yok.

## 11 Kasım 2026 broker/spread readiness güncellemesi

Dört Exness Cent sembolünün güncel field-level contract gözlemi CURRENT_MT5_OBSERVED; tarihsel/operatör onayı değildir. Kullanıcı kesin spread limiti olmadığını bildirdi: hiçbir maksimum uydurulmadı. Yeni MT5_SPREAD_POLICY_FILE sürümlü, exact broker/sembol/USC, PRICE/POINTS, effective interval/timeframe/provenance/approval sözleşmesi hazır; dört null UNAPPROVED template BLOCK üretir. Güncel spreadler risk limiti yapılmadı. REAL broker/currency/PnL, conversion ve spread kapıları güçlendirildi; session koruması değişmedi.

Öncelik: operatörün ayrı dört spread kuralını ve exact 9 Kasım XAUUSDc tarihsel seans kanıtını sağlaması. Diğer geliştirmeler tamamlandı; no-approval ve session eksikliğinde ret normaldir. Mevcut 8006 yeni broker/spread alanlarını taşımıyor; restart yapılmadı. Ayrıntılar V3_CODEX_DELIVERY_REPORT_TR.md, V3_SPREAD_POLICY.md, V3_SESSION_EVIDENCE_BLOCKERS.md, V3_RUNTIME_CUTOVER_READINESS.md ve V3_PWA_FINAL_HANDOFF.md içinde. Push/merge veya PWA/News/MT5 bridge/V2 yazımı yok.

## 11 Kasım 2026 runtime kabul güncellemesi

Ana V3 izole Windows Python 3.11/3.13 ve NumPy 2.2.6 ile gerçek localhost HTTP üzerinden 56/56 fixture kabul kontrolünü geçti; kendi test süreçleri kapatıldı. Mevcut 8006 PID 7532 korunuyor; loaded-version VERSION_UNVERIFIED. REAL/Exness-MT5Real50/USC preflight, dört exact alias, taze quote ve kapanmış M15/H4 okumaları başarılı. Canlı analiz missing candle without verified broker hours nedeniyle INSUFFICIENT_DATA; execution false. Dört sembolde max_spread null ve market/contract unverified da açık plan kabul engelleridir.

PWA'da sabit 10.000 aktif kodda yok; kullanıcı hypothetical USC sermayesi gönderiyor. Kalan işler dört sembollü analiz kapısı, betimleyici pattern gösterimi, NOT_EVALUATED aday planının doğru varsayımsal sunumu, kaynak/currency ve hassasiyet gösterimidir. PWA değiştirilmedi. Local/Tailscale schema HTTP 200; canlı UI kabulü PARTIAL. Detaylar V3_RUNTIME_ACCEPTANCE_TR.md, V3_ISOLATED_API_TESTS.md, V3_P1_API_ACCEPTANCE.md, güncel V3_PWA_INTEGRATION_HANDOFF.md ve V3_RUNTIME_CUTOVER_PLAN.md içinde. Öncelik exact XAUUSDc tarihsel seans kanıtı ve ayrı yetkili cutover'dır; mevcut servisler şimdi restart edilmez.

## 11 Kasım 2026 P1 ana entegrasyon güncellemesi

P1 Double Top/Double Bottom betimleyici adaptörü `f78b638 -> 753ed59` yerel fast-forward ile ana V3'e aktarıldı. Recovery ref: `refs/recovery/p1-main-20261111-3107aacf306d`. P1 ve ana çalışma ağacında izole Python 3.11/3.13 kabul sonuçları `V3_P1_MAIN_TEST_RESULTS.md` içinde belgelenir. Global paketler, PWA, MT5 bridge, haber servisi ve V2 kaynağı değiştirilmedi; push veya uzak merge yoktur.

Sonraki öncelik yeni formasyon eklemek değil, `XAUUSDc` için 9 Kasım 2026 tarihsel Exness seans kanıtını doğrulamak ve ayrı planlanmış runtime sürüm geçişinde pinli kaynak + NumPy 2.2.6 + REAL_READONLY_DATA yapılandırmasını kanıtlamaktır. `SOURCE_INTEGRATED=YES`; çalışan runtime ve canlı PWA kabulü `UNVERIFIED`. Servisleri bu görev kapsamında yeniden başlatma. Ayrıntılar `V3_P1_MAIN_INTEGRATION_REPORT_TR.md` ve `V3_P1_RUNTIME_HANDOFF.md` içindedir. Aşağıdaki önceki notlar tarihsel bağlam olarak korunmuştur.

1. Operatör, salt okunur test için ayrı bir DEMO MT5 terminali ve açık broker schedule kaynağı seçmeli. REAL hesap bağlantısı kullanılmamalı. UTC/server offset, effective date, DST, günlük bakım, hafta sonu ve holiday override doğrulanmalı.
2. Dört `c` sembolünün gerçek symbol_info, quote, kapalı M15/H4, spread ve broker profit sonuçları USC cinsinden karşılaştırılmalı; profit/tick uyuşmazlığı araştırılmalı.
3. Manuel 8006 API'si doğrulanmış DEMO provider ile read-only TestClient veya localhost istekleriyle denenmeli. Çalışan servis sürümünün yeni commit'i kullandığı ayrıca teyit edilmeli.
4. PWA ekibi GBPUSD/USDJPY buton kapsamını, sabit 10000 bakiyeyi ve USC birim gösterimini ayrı onaylı değişiklikte düzeltmeli. Bu depoda PWA veya `mt5_bridge.py` değiştirilmemeli.
5. Broker/session arşivi ve maliyetli Forex OOS kanıtı olmadan ek V2 yönsel strateji veya canlı başarı iddiası eklenmemeli.

DEMO kabul önceliği: varsayılan MT5 oturumu salt okunur ön kontrolde REAL çıktı. Operatör ayrı DEMO terminalini açıkça seçmeden veya oturum değiştirmeden canlı fiyat/mum testi yapılmayacak. İzole DEMO süreci için `MT5_EXPECTED_DEMO_SERVER` ve `MT5_EXPECTED_DEMO_CURRENCY` exact değerleri girilmeli; 8005/8006 kaynak eşitliği ve PWA risk birimi ayrıca doğrulanmalı. Ayrıntılar `V3_DEMO_PREFLIGHT.md` ve `V3_PWA_INTEGRATION_HANDOFF.md` içindedir.

REAL veri politikası güncellemesi: REAL salt okunur kaynak artık explicit `MT5_ANALYSIS_POLICY=REAL_READONLY_DATA`, `MT5_EXPECTED_REAL_SERVER=Exness-MT5Real50`, `MT5_EXPECTED_REAL_CURRENCY=USC` ile seçilebilir. Bu ayarlar mevcut 8006 servisine otomatik uygulanmadı. Operatör doğrulanmış Exness seans/holiday/DST kaynak sözleşmesini ve dört sembol için max spread politikasını sağlamadan canlı plan beklenmemeli. Sonra izole read-only süreçte 8005/8006 kaynak eşitliği, V2 pin, PWA gösterimi ve Tailscale yolunu test et; çalışan servisleri zorla yeniden başlatma.

10 Kasım seans kanıtı güncellemesi: 8006 ve 5173 proxy REAL/USC manuel çağrısı çalışıyor; sonuç hâlâ güvenli `INSUFFICIENT_DATA`. Öncelikli tek zorunlu operatör teslimi, Exness seçicisinden `XAUUSDc` için 9 Kasım 2026 UTC çizelgesidir. İsteğe bağlı tek MT5 işlemi, hazır derlenmiş read-only scripti mevcut terminalde bir kez manuel çalıştırmaktır; sonra Codex `session_evidence_v1.json` dosyasını yerel doğrulayıcıyla okuyabilir. Bu yalnız güncel haftalık saatleri sağlar ve geçmiş boşlukları açmaz. Tarihli kaynak doğrulanırsa UTC kanıt şeması ve onaylı quote/trade policy bağlantısı bir sonraki küçük geliştirme olacaktır. Yeni commit'i çalışan 8006 sürecinde kullanmak ayrı, açıkça planlanmış servis sürüm geçişi gerektirir; mevcut servis yeniden başlatılmadı.
