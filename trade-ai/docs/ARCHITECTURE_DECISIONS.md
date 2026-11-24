# Trade AI mimari karar kaydı

## ADR-001 — Deterministik karar ve AI anlatımı ayrılır

- **Problem:** Dil modeli çıktısının yön, risk veya evidence kararlarını değiştirmesi analizin tekrarlanabilirliğini ve açıklanabilirliğini bozar.
- **Seçilen çözüm:** Yön, skor, gate, zone ve RR yalnızca deterministik engine'lerden gelir. AI, doğrulanmış structured payload üzerinden açıklama üretir; kullanılamazsa deterministic fallback narrative kullanılır.
- **Alternatifler:** AI'nin doğrudan sinyal üretmesi; AI'nin composite skoru değiştirmesi.
- **Neden seçildi:** Test edilebilirlik, audit edilebilirlik ve veri hatalarında güvenli davranış sağlar.
- **Trade-off:** Narrative, yeni bir piyasa sinyali keşfetse bile karar sistemine otomatik katkı veremez.
- **Etkilenen bileşenler:** `backend/server.py`, `market_ai/engines/*`, `market_ai/providers/ai_provider.py`.

## ADR-002 — Confluence, yönsel evidence için tek katmandır

- **Problem:** Pattern, Order Flow, Liquidity, Futures Positioning, Liquidation ve MTF'nin hem weighted composite hem de confluence içinde sayılması güveni yapay olarak şişirir.
- **Seçilen çözüm:** Composite yalnızca trend, momentum, volume, structure ve news kullanır. Diğer katmanlar Evidence/Confluence'a doğrudan girer; recency/confirmation uygulanır ve bucket bazında tekilleştirilir.
- **Alternatifler:** Tüm sinyalleri composite ağırlıklarına eklemek; her engine'in kendi bağımsız gate'iyle son karar vermesi.
- **Neden seçildi:** Double counting'i engeller ve çatışan evidence'ın tek, açıklanabilir kapıda değerlendirilmesini sağlar.
- **Trade-off:** Yeni evidence'ın etkisi ağırlık eklemekten daha muhafazakârdır; kalibrasyon gerektirir.
- **Etkilenen bileşenler:** `backend/market_ai/engines/analysis.py`, `confluence.py`, `mtf.py`, `order_flow.py`, `liquidity.py`, `futures_positioning.py`, `liquidation.py`.

## ADR-003 — Zone/RR geometri kısıtları zorunludur

- **Problem:** Uzak destek/direnç seviyeleri orantısız risk veya çalıştırılamaz TP1 üretebilir.
- **Seçilen çözüm:** `469b27d` algoritması yakındaki seviyeleri ATR sınırlarıyla kullanır, uygunsuz seviyelerde ATR fallback'ine döner ve volatility-aware RR gate'i uygular.
- **Alternatifler:** Her zaman en yakın support/resistance'ı kullanmak; yalnız ATR hedefleri kullanmak.
- **Neden seçildi:** Piyasa seviyelerini korurken invalidation, target ve RR'nin matematiksel olarak geçerli kalmasını sağlar.
- **Trade-off:** Bazı zayıf setup'lar yönsel composite olumlu olsa bile neutral'a düşer.
- **Etkilenen bileşenler:** `backend/market_ai/engines/analysis.py`, outcome değerlendirmesi ve frontend sonuç gösterimi.

## ADR-004 — Uzak entegrasyon testleri varsayılan olarak güvenli değildir

- **Problem:** Mevcut testler varsayılan uzak preview API'ye çağrı yapar ve history silme/evaluate işlemleri içerebilir.
- **Seçilen çözüm:** İzole DB veya açıkça doğrulanmış test endpoint'i olmadan yalnızca saf unit/compile/collection kontrolleri çalıştırılır. Entegrasyon testleri önce güvenli hedefe ayrıştırılmalıdır.
- **Alternatifler:** Mevcut test takımını doğrudan production-benzeri hedefte çalıştırmak; entegrasyon testlerini tamamen kaldırmak.
- **Neden seçildi:** Kullanıcı verisi ve kalıcı analiz geçmişi korunur; testler yine mimarinin parçası olarak geliştirilir.
- **Trade-off:** Canlı entegrasyon kapsamı, test ortamı kurulana kadar ertelenir.
- **Etkilenen bileşenler:** `backend/tests/backend_test.py`, `backend/tests/test_outcomes.py`, MongoDB yapılandırması ve CI/test altyapısı.

## ADR-005 — OHLC ile aynı mumda çift temas kesin sonuç değildir

- **Problem:** Tek bir OHLC mumunda hem TP1 hem invalidation görülürse intrabar sıra bilinmez. Bu durumda kesin win/loss üretmek backtest sonucuna veri olmayan bir varsayım ekler.
- **Mevcut çözüm:** Outcome engine bu durumu `ambiguous` olarak kaydeder ve hit-rate win/loss paydasının dışında tutar.
- **Alternatifler:** Her çift teması muhafazakâr `loss` saymak; her çift teması `win` saymak.
- **Neden seçildi:** Mevcut engine dokümantasyonu ve kodu, OHLC sınırına sadık biçimde ölçülemeyeni kesin sonuç yapmamayı seçmiştir.
- **Trade-off:** `ambiguous` sonuçları hit-rate paydasında yer almaz; bu, ölçülemeyen intrabar sıralama için sahte kesinlik üretmekten daha doğrudur. Regression sözleşmesi bullish ve bearish çift temaslar için bu davranışla hizalanmıştır.
- **Etkilenen bileşenler:** `backend/market_ai/engines/outcome.py`, `backend/tests/test_outcomes.py`, performance metrikleri.

## ADR-V2-001 — İzole QC/rejim/Router akışı ve veriden türeyen yetenekler

- **Problem:** Bağımsız V2 bileşenleri veri kalite kapısı atlanarak veya dışarıdan uydurulan capability listesiyle birleştirilebilir.
- **Çözüm:** `v2.pipeline.evaluate_strategies`, normalize mum batch'ini bütünüyle doğrular; sonra mumdan türetilen konservatif yeteneklerle rejim ve Router'ı çağırır. Aynı snapshot ve girdiler aynı sonucu verir. Sonuç akış sürümü ve `as_of_ms` taşır.
- **Sınır:** Seçilen strateji yalnız analiz uygunluğudur; işlem izni değildir. Risk veto dışarıdan açıkça sağlanır, portföy risk hesabı henüz uygulanmamıştır. Canlı API/DB bağlantısı yoktur.
- **Veri yeteneği:** Mumlar yalnız OHLC ve tek tip gerçek/tick hacim yeteneğini kanıtlar; order book, trade feed, OI/funding/liquidation ayrı doğrulanmış feed gerektirir. FX/spot altın merkezi gerçek hacim iddiasını reddeder.
- **Trade-off:** FX/XAU için doğrulanmış seans/tatil/DST takvimi yokken pipeline WAIT verir. Sürekli piyasa gap kontrolü gevşetilmez. Sağlayıcı/lisans kararı ve takvim sonraki milestone'dur.
- **Doğrulama:** 54 offline V2 unit/contract integration testi ve backend syntax kontrolü geçti; V1 algoritmalarının tamamının doğrulandığı anlamına gelmez.

## ADR-V2-002 — Test edilmiş teknik motor ve bucket çatışması

V1 teknik motoru QC korumalı V2 adaptörü üzerinden kullanılacak; birleşik volume hesapları nedeniyle tick/eksik hacim bu ilk adaptörde unavailable kalacak. Simple-average RSI'nın yalnız tamamlanmış sıfır-kayıp pencereleri 100, tamamen düz pencereleri nötr 50 üretir; Wilder adı kullanılmaz. Confluence aynı rank'teki zıt bucket kanıtını sıfır güçte neutral conflict marker ile temsil eder. Kaynak sırasından yön çıkarılmaz. Referanslar ve sınırlar `docs/V2_PROGRESS_LOG.md` içindedir.

## ADR-V2-003 — Saf sanal portföy risk kapısı

Risk modülü, sürümlü ve açık parametreli, Decimal tabanlı saf bir paper-only gate olacaktır. En kötü giriş kenarı, net maliyet, mevcut açık risk ve günlük kayıp rezervi beraber değerlendirilir. İki demo hesap/para birimi ayrı tutulur. Desteksiz payoff/FX veya belirsiz session/news girdisi WAIT verir. Module ne hesap bakiyesi ne emir lifecycle'ı değiştirir; ayrıntılar `V2_PROGRESS_LOG.md` içindedir.

## ADR-V2-004 — Snapshot provenance ve immutable kayıt

Her analiz tam snapshot, data/config/strateji/engine sürümleri ve parametreleriyle canonical JSON kaydı olarak üretilecek. Hash içerik kimliğidir; imza değildir. Paper risk wrapper aynı record ID/instrument/oluşturulma zamanını zorunlu kılar. Reanalysis eski kaydı değiştirmez; farklı içerik yeni kayıt üretir. Ana API ve kalıcı veri göçü henüz kapsamda değildir.

## ADR-V2-005 — İzole append-only SQLite prototipi

SQLite yalnız explicit yeni dosya ve test fixture'larında append-only karar/snapshot deposu prototipi olarak kullanılacak. Yabancı DB üzerine yazma veya otomatik migration yoktur. Bu, MongoDB göç kararını kesinleştirmez; mevcut API/store değişmez. Integrity, idempotency, restart ve backup/restore önce geçici DB'de doğrulanır.

## ADR-V2-006 — Local ürün runtime'ı ve atomik paper ledger

Standalone V2 FastAPI, V1 MongoDB/AI importlarından ayrıdır. V1 mount'u explicit opt-in, bind loopback-only ve bearer zorunludur. Fixture/live mode yeni V2 DB'de sabitlenir; user/foreign/prototype DB otomatik migrate edilmez. Önceki yalnız prototip/store ve saf risk kararları, bu ayrı ürün runtime'ı için kontrollü olarak genişletilmiştir.

Immutable snapshot/analysis/commands/events/journal yanında bakiye/order/position state projection'ları aynı SQLite transaction'da değişir; checksum ve idempotency zorunludur. AUTO/MANUAL ayrı hesaptır. Execution bir sonraki uygun kapalı 1m bar modeliyle, explicit fee/spread/slippage ve quantity kurallarıyla simüle edilir. Unknown intrabar sırası ambiguous; historical mark'tan avantajlı close yok. Gerçek exchange order/API key bağlantısı kapsam dışıdır.

## ADR-V2-007 — Bounded cooperative scanner ve gönderilmemiş outbox

Scanner default paused; background worker yalnız standalone `--scanner` opt-in ile 60 saniyelik tek thread'dir. Watch başına AUTO default kapalıdır. Kalıcı lease, closed-bar job kimliği ve analiz idempotency'si crash/restart/concurrent tick sonrası çift adayı engeller. Provider I/O sırasında DB kilidi tutulmaz; son commit'te pause/lease/bar-boundary kontrol edilir. Eski yarım iş historical trade üretmez. Açık paper riskinin fiyat takibi önce yapılır; recovery hatasında yeni analiz durur. Her tick en fazla iki yeni analiz, watchlist en fazla on kayıttır.

Yeni feature tabloları yalnız ownership/mode doğrulanmış V2 product DB'ye additive eklenir; yabancı DB/Mongo otomatik migration yoktur. Notifications append-only pending outbox'tır, gerçek delivery servisi yoktur. Graceful worker stop pause'u kalıcılaştırır; account pause ve scanner pause ayrı kavramlardır. Scanner pause polling'i de durdurur, liquidation yapmaz; frontend stale mark bilgisini göstermelidir.
