# TRADE AI — Kapsamlı Devir ve Devam Dosyası

> **Amaç:** Bu belge, önceki ChatGPT konuşmalarındaki Trade AI projesine ilişkin bağlamı, doğrulanmış ilerlemeyi, mimari kararları, test sonuçlarını, Codex ayarlarını ve devam planını başka bir GPT’ye aktarabilmek için hazırlanmıştır.
>
> **Önemli sınırlama:** Bu dosya kelimesi kelimesine tüm sohbet mesajlarının dışa aktarımı değildir. Konuşma içindeki teknik ve operasyonel açıdan önemli bilgileri tek bir, kendi içinde anlaşılır devir belgesinde toplar. Son durumun doğrulanmadığı yerlerde bunu özellikle belirtir.

---

## 0. Yeni GPT için ilk talimat

Bu belgeyi baştan sona oku ve Trade AI projesinin devam bağlamı olarak kabul et. Kullanıcıya aynı bilgileri yeniden sordurma. Önce burada belirtilen **son doğrulanmış durumu** anla; ancak önceki konuşma tarihinden beri dosya, GitHub, deployment ve plan kullanımı değişmiş olabileceğinden, işlem yapmadan önce güncel durumu uygun şekilde doğrula.

### Çalışma ilkeleri

- Kullanıcıyla Türkçe konuş; doğrudan, pratik ve adım adım ilerle.
- Kullanıcı haftalardır manuel kod kopyalayıp yapıştırmaktan yoruldu. Bundan sonraki geliştirme işinin büyük kısmını yerel repo üzerinde Codex yapacak; ChatGPT’den mimari denetim, planlama ve bağımsız sonuç kontrolü bekleniyor.
- Kullanıcı, **otonomi ile doğrulamayı birbirine karıştırmıyor**: Codex’in normal kod değişikliği, test, commit/push ve erişilebilir deployment kontrolleri için tekrar tekrar izin istemeden ilerlemesini istiyor; ancak bunu küçük, test edilmiş ve geri alınabilir aşamalarla yapmasını istiyor.
- Kullanıcıya doğrulanmamış başarı bildirme. Bir test gerçekten çalıştırılmadıysa “geçti” deme. Bir deploy başarısızsa “tamamlandı” deme.
- Kullanıcıya her seferinde dosyanın tamamını elle kopyalatma yöntemini tekrar başlatma; yerel dosyada çalışabilen Codex mevcut iş akışının tercih edilen aracıdır.
- Çalışma sırasında yeni bir kritik bulgu oluşursa önce kısa ve somut bir açıklama yap; ardından gereken tek sonraki adımı ver.
- Gereksiz kod değişikliği, tüm projeyi baştan yazma, yalnızca test geçsin diye eşiği gevşetme ve sahte canlı piyasa verisi oluşturma yasaktır.

### Kullanıcı hedefi

Mevcut uygulamayı, kriptoya ek olarak Forex ve özellikle **XAUUSD** desteğini de içeren, sağlam test altyapısına, risk/ödül hesaplarına, explainability’ye, outcome/backtest altyapısına ve düzgün bir frontend/backend sözleşmesine sahip bir Market Intelligence / Trading Analysis platformuna dönüştürmek. Kârlılık ya da istatistiksel doğruluk garantisi varsayılmamalı; bunun için backtest ve out-of-sample doğrulaması gereklidir.

---

## 1. Repo ve ortam

- Windows masaüstü kullanılıyor.
- Yerel repo yolu:
  `%USERPROFILE%\OneDrive\Desktop\Trade-main V1\Trade-main`
- Backend klasörü:
  `%USERPROFILE%\OneDrive\Desktop\Trade-main V1\Trade-main\backend`
- GitHub remote:
  `https://github.com/FatihBirgul/trade-ai.git`
- Ana branch: `main`
- Son doğrulanmış Zone/RR checkpoint’i: `469b27d` — `Redesign trade zone geometry and risk reward`
- Daha sonraki Codex çalışmasında `50136e1` — `Align outcome ambiguity regression contract` commit’inin GitHub’da doğrulandığı bildirildi.
- **Güncel HEAD bilinmiyor:** son konuşma anında Codex yeni bir scenario güvenliği milestone’u üzerinde çalışıyordu ve kullanım limitine ulaştı. Başka GPT veya Codex, işlem yapmadan önce `git status`, `git log`, `git rev-parse HEAD`, `git rev-parse origin/main` ve varsa `docs/CODEX_STATE.md` ile gerçek durumu yeniden doğrulamalı.

### Korunacak untracked backup dosyaları

Son teyit edilen listede şu dosyalar untracked idi. Bunlara dokunma, silme, taşıma, yeniden adlandırma veya commit etme:

- `backend/market_ai/engines/analysis_before_zones_v2.py`
- `backend/market_ai/engines/analysis_checkpoint_6b73ec2.py`
- `backend/market_ai/engines/confluence_checkpoint_6b73ec2.py`

Codex’in bunları koruduğu bildirilmişti. Mevcut güncel durumda hâlâ untracked olup olmadıkları doğrulanmalı; dosyaların kendileri yine de korunmalı.

### Başlangıçtan bilinen Git checkpoint’leri

Aşağıdaki commit’ler önceki proje oturumlarında başarıyla oluşturulduğu ve/veya push edildiği bildirilen checkpoint’lerdir (bu liste tüm Git geçmişinin eksiksiz listesi değildir):

- `250c202` — Add futures positioning engine
- `972eea6` — Add futures positioning evidence to confluence
- `9e307b8` — Integrate futures positioning into analysis
- `973cf1e` — Integrate live futures positioning data
- `610d8d4` — Add Binance liquidation stream listener
- `2951491` — Add deterministic liquidation analysis engine
- `e9fb7f1` — Add liquidation evidence to confluence
- `1f59f84` — Integrate liquidation into analysis
- `f2323d9` — Integrate background liquidation stream
- `469b27d` — Redesign trade zone geometry and risk reward (**yerel ve `origin/main` ile aynı olduğu doğrulanmıştı**)
- `50136e1` — Align outcome ambiguity regression contract (**Codex tarafından GitHub’da doğrulandığı söylendi; canlı deployment başarısız bildirimine konu oldu**)

`f2323d9` anında üç backup dosyası dışında çalışma ağacında değişiklik yoktu. Sonra `469b27d` commit’i oluşturuldu ve `git push origin main` başarılı oldu. Ardından Codex phase/state belgeleri ve outcome test sözleşmesiyle çalıştı.

---

## 2. Mevcut uygulama mimarisi

### Genel akış

- Frontend: Expo / React Native.
- Merkezi API istemcisi: `frontend/src/api/client.ts`.
- Backend: FastAPI, `backend/server.py`.
- Ana analiz endpoint’i: **`POST /api/analysis`**. Bu endpoint GET değildir.
- Analiz isteği gövdesi `AnalysisRequest` şemasına göre JSON’dur; en az `symbol` gerekir, `timeframe` varsayılanı `4H`, ayrıca opsiyonel `image_base64` alanı vardır.
- Önce Binance ticker ve seçilen timeframe için yaklaşık 300 mum alınır; sonra teknik analiz ve yardımcı analiz katmanları yürütülür.
- API’de `/api/health`, `/api/config`, `/api/assets`, `/api/markets`, `/api/markets/{symbol}`, `/api/markets/{symbol}/klines`, `/api/markets/{symbol}/technical`, `/api/news`, `/api/history`, `/api/history/{item_id}`, `/api/history/evaluate-all`, `/api/performance` gibi endpoint’ler vardır.

### Teknik analiz ve kanıtlar

Ana motorun mevcut katmanları:

- Teknik göstergeler: EMA20/50/100/200, SMA20, RSI14, MACD/histogram, Stoch RSI, ATR/ATR%, Bollinger, hacim ve hacim oranı.
- Swing-temelli market structure, destek/direnç.
- Candlestick patterns ve chart patterns; recency/confirmation alanları.
- Haber sentiment (önceki gerçek API çıktısında `News unavailable`).
- Order Flow / Delta: Binance aggregate trades üzerinden buy/sell hacmi, delta, delta ratio ve dominant side.
- Liquidity / Order Book: Binance Futures depth snapshot, bid/ask volume, imbalance ve spread.
- Futures Positioning: current/historical Open Interest ve Funding Rate.
- Liquidation: Binance Futures force-order WebSocket stream’i, arka planda çalışır ve sınırlı in-memory cache kullanır.
- MTF: üst zaman dilimi bias’ı, current timeframe ve alt zaman dilimi teyidi.
- Confluence: kanıtlar, recency/confirmation, bucket tekilleştirme, bullish/bearish güç ve çakışma.
- Decision gate, trade zones, risk/reward, outcome/history ve AI narrative/fallback.

### Core composite ve double-counting kararı (önemli invariant)

Ağırlıklı yön composite’i yalnızca şu çekirdek bileşenlerden hesaplanır:

- trend: `0.35`
- momentum: `0.275`
- volume: `0.15`
- structure: `0.175`
- news: `0.05`

Pattern, Order Flow, Liquidity, Futures Positioning, Liquidation ve MTF weighted composite’e tekrar eklenmez; bunlar Confluence/evidence katmanından değerlendirilir. Aynı bilgiyi composite ve Confluence içinde iki kez sayma.

Volatility yönsel kanıt değildir; kalite/risk context’i olarak kullanılmalıdır. Confidence’a yapay bir minimum taban veya kozmetik bonus eklenmemeli. Confidence bir heuristic’tir, istatistiksel olarak kalibre edilmiş başarı olasılığı olduğu iddia edilemez.

### Decision Gate

Mevcut mantık:

- composite direction ile confluence direction aynı yönde olmalı;
- en az iki destekleyici evidence olmalı;
- supporting evidence sayısı opposing sayısından yüksek olmalı;
- aksi durumda direction `neutral`.
- Sonrasında volatility-aware RR gate, minimum RR şartını kontrol eder. RR düşükse executable yön tekrar neutral olabilir.

RR geometry sorunu threshold’u gevşeterek çözülmemeli; kök neden zone geometrisidir.

### Liquidation

- Üretim kaynağı WebSocket `wss://fstream.binance.com/ws` ve ilgili `symbol@forceOrder` stream’leridir.
- REST `/fapi/v1/forceOrders` 401 verebildiği için production liquidation kaynağı yapılmamalıdır.
- Listener FastAPI lifespan ile açılır/kapanır; endpoint başına yeniden WebSocket açılmamalıdır.

---

## 3. Data provider detayları ve daha önce doğrulanan testler

`backend/market_ai/providers/market_data.py` içinde:

- Spot base: `https://data-api.binance.vision/api/v3`
- Futures base: `https://fapi.binance.com`
- Spot ticker/klines
- Futures order book `/fapi/v1/depth`
- aggregate trades `/fapi/v1/aggTrades`
- current OI `/fapi/v1/openInterest`
- historical OI `/futures/data/openInterestHist`
- funding `/fapi/v1/fundingRate`
- forceOrders REST metodu vardı, ancak production liquidation akışında kullanılmaması kararlaştırıldı.
- Historical OI metodu `get_open_interest_history(symbol, period="5m", limit=30, start_ms=None, end_ms=None)` eklenmiş ve canlı olarak test edilmişti.

### Order Flow

`backend/market_ai/engines/order_flow.py` var.

- Synthetic testte buy volume 3, sell 1, delta 2, delta ratio 0.5, score 50, bullish evidence sonucu elde edilmişti.
- Live örnek: 500 trade, buy volume ~16.998, sell volume ~8.154, delta ~8.844, score ~35.2.
- Confluence evidence source `order_flow` doğrulanmıştı.

### Liquidity

`backend/market_ai/engines/liquidity.py` var.

- Synthetic testte bid volume 8, ask 3, imbalance ratio ~0.454545, bullish score ~45.5.
- Live örnek 200 depth level: bid ~41.708, ask ~21.541, imbalance ratio ~0.318851, spread 0.1, bullish score ~31.9.
- Confluence entegrasyonu test edildi; Liquidity doğrudan `final_score`’a eklenmiyor.

### Futures Positioning

`backend/market_ai/engines/futures_positioning.py` var.

- OI değişimi + funding’den oluşur; ağırlıklar `0.70 * OI score + 0.30 * funding score`.
- Evidence ancak `abs(score) >= 8` olduğunda Confluence’a girer.
- Synthetic bullish/bearish senaryolar test edildi.
- Live testte OI ve Funding düzgün geldi; positioning zayıfsa Confluence evidence oluşturmaması beklenen davranıştı.

### Liquidation

`backend/market_ai/engines/liquidation.py` ve `backend/market_ai/providers/liquidation_stream.py` var.

- BUY liquidation = short liquidation = bullish pressure.
- SELL liquidation = long liquidation = bearish pressure.
- Synthetic test: 3 events, 2 BUY / 1 SELL; short notional 702, long notional 99, imbalance ~0.752809, score ~75.3 bullish.
- Production health testinde stream `connected=true`, `cached_events=0` olabilir; event olmaması bug anlamına gelmez.

---

## 4. Zone / Risk-Reward değişikliği — son doğrulanmış ana çalışma

### Kök sorun

Eski `build_zones()` uzaktaki bir destek/direnci entry/invalidation geometry’sine gereğinden fazla katabiliyordu. Bullish örneklerde TP1’e karşı risk çok büyük çıkıyor ve RR 1.0 minimum eşiğinin altında kaldığı için sinyal nötrleşebiliyordu. Çözüm minimum RR eşiğini düşürmek değil, zone geometry’yi düzeltmekti.

### Commit

`469b27d — Redesign trade zone geometry and risk reward`

- `analysis.py` içinde yalnızca `build_zones()` işlevi değiştirildi.
- Değişiklik commit edildi ve `git push origin main` başarılı oldu.
- Git diff kontrolünde diğer engine/confluence bölümlerinin değişmediği görülmüştü.
- `LF will be replaced by CRLF` uyarısı satır sonu uyarısıydı, hata değildi.

### Yeni algoritmanın test çıktıları

`python -m py_compile backend\market_ai\engines\analysis.py` hatasız tamamlandı; ardından altı sentetik örnek çalıştırıldı:

```text
B1 {'entry_low': 99.8, 'entry_high': 100.0, 'target_1': 104.0, 'target_2': 108.0, 'invalidation': 98.3, 'risk_reward': 2.35}
B2 {'entry_low': 98.5, 'entry_high': 100.0, 'target_1': 103.0, 'target_2': 108.0, 'invalidation': 97.0, 'risk_reward': 1.0}
B3 {'entry_low': 99.0, 'entry_high': 100.0, 'target_1': 104.0, 'target_2': 108.0, 'invalidation': 97.5, 'risk_reward': 1.6}
B4 {'entry_low': 99.0, 'entry_high': 100.0, 'target_1': 104.0, 'target_2': 108.0, 'invalidation': 97.5, 'risk_reward': 1.6}
S1 {'entry_low': 100.0, 'entry_high': 100.5, 'target_1': 97.0, 'target_2': 92.0, 'invalidation': 102.0, 'risk_reward': 1.5}
S2 {'entry_low': 100.0, 'entry_high': 101.5, 'target_1': 96.0, 'target_2': 94.0, 'invalidation': 103.0, 'risk_reward': 1.33}
```

Testler yeni algoritmanın devrede olduğunu gösterdi. Bunlar yalnızca synthetic geometry testleridir; finansal başarının kanıtı değildir. B2’de RR tam 1.0 olduğu için düşük-volatility RR floor’u geçer ama daha yüksek rejimlerde yetmeyebilir.

### Live API smoke test (eski snapshot)

`GET /api/analysis` 405 döndürdü; OpenAPI’den endpoint’in `POST /api/analysis` olduğu doğrulandı. Doğru test:

```cmd
curl -X POST "http://127.0.0.1:8000/api/analysis" -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"timeframe\":\"5m\"}"
```

Bir test çağrısı başarılı JSON döndürdü. Fakat çıktıdaki `created_at` ve fiyat snapshot’ı eski/tutarsız görünebilir; cevapta `created_at: 2026-09-10...`, `price_at_analysis: 77321.54` vardı. **Bu sonuç şu anki canlı piyasa değeri olarak kullanılmamalı.** Testin önemli tarafı response yapısı ve gate davranışıydı.

Gözlenen değerler:

- `direction: neutral`
- `final_score: -9.6`
- `quality.composite_direction: neutral`
- `quality.confluence_direction: bearish`
- `quality.gate_passed: false`
- `quality.rr_gate_passed: true`
- `zones` içindeki tüm seviye alanları `null`
- `supporting_count: 3`, `opposing_count: 5`
- Confluence `bullish_strength: 122.8`, `bearish_strength: 144.68`
- Order Flow bullish; Liquidity bearish; 4H HTF bias bearish; 1m LTF confirmation bullish.

Bu durumda zones’ın `null` olması RR hatası değildir: direction, zone üretiminden önce gate nedeniyle neutral olmuştur. **RR gate true idi.** Composite ve Confluence çelişince gate’in nötr kalması mevcut tasarıma uygundur.

### İkinci bug: neutral scenario metninde `None`

Aynı API çıktısı şunu gösterdi:

```json
"scenarios": {
  "bullish": "If price holds above None and reclaims None, momentum could extend toward None.",
  "bearish": "A loss of None would invalidate the neutral case and open downside risk.",
  "neutral": "If price stays inside the current range, expect chop until a level breaks with volume."
}
```

Bu açık bir kullanıcıya görünen bug. Zone yokken fallback scenario metinleri `None` değerlerini string içine yerleştiriyor. Root cause’un backend scenario üretiminde/AI fallback sanitization’ında olduğu düşünülmüş; frontend’in bu hatalı string’i olduğu gibi göstermeye hazır olması nedeniyle ilk düzeltmenin backend’de yapılması planlanmıştı.

---

## 5. Outcome regression test çelişkisi ve Codex’in sonraki commit’i

Codex Phase 0’da güvenli testleri çalıştırdı:

- Python compile: geçti.
- Saf outcome unit testleri: **7 geçti, 1 başarısız**.
- Çelişki: aynı OHLC mumunda hem hedef hem invalidation görülünce engine `ambiguous` dönüyor, test ise `loss` bekliyordu.
- Tam `backend_test.py` test koleksiyonu `Pillow` eksikliği nedeniyle yüklenemedi. Ayrıca o koleksiyonun uzak API’ye bağlanma ve history/evaluation üzerinden dış veride silme/değiştirme riski olduğu bildirilmişti; izole ortam olmadan çalıştırılmamalı.

Kullanıcı, hataları otomatik düzeltme ve testlere devam etme işini Codex’e verdi. Codex daha sonra şu commit’in GitHub’da doğrulandığını söyledi:

- `50136e1` — `Align outcome ambiguity regression contract`

Ekrandaki açıklama, var olan `ambiguous` davranış sözleşmesinin test/contract ile hizalandığı yönündeydi. **Render bu commit için otomatik deployment başarısız e-postası gönderdi.** Bu, deploy hatasının koddan kaynaklandığını tek başına kanıtlamaz; Render build/deploy logları görülmeden kök neden bilinmiyor.

---

## 6. Codex masaüstü kurulumu ve izin ayarları

Kullanıcı Windows ChatGPT masaüstü uygulamasını açtı ve bir `Trade AI` projesi oluşturup şu kaynak klasörünü ekledi:

`%USERPROFILE%\OneDrive\Desktop\Trade-main V1\Trade-main`

Codex/Work görevi başlığı görüntüde `İncele mimariyi ve Git durumunu` idi.

### Görünen Codex ayarları

`%USERPROFILE%\.codex\config.toml` çıktısında şu alanlar vardı:

```toml
model = "gpt-5.6-terra"
model_reasoning_effort = "xhigh"

[windows]
sandbox = "elevated"

[projects.'%USERPROFILE%\onedrive\desktop\trade-main v1\trade-main']
trust_level = "trusted"
```

Dosyada görünür bir approval policy satırı yoktu.

Settings ekranında “Tam erişim” anahtarı açık görünüyordu. Sohbet compose alanındaki izin menüsünde seçenekler:
- `Onay iste`
- `Benim için onayla` — yalnızca potansiyel olarak güvenli olmadığı düşünülen işlemlerde sor
- `Tam erişim` — internet ve bilgisayardaki dosyalara sınırsız erişim

Kullanıcı daha sonra bu menüde **`Tam erişim` seçeneğine tıklamaya yönlendirildi**. En son ekranın alt bölümünde `Tam erişim` ibaresi görünüyordu. Bu yüzden son bilinen çalışma ayarı tam erişimdi; yine de yeni oturumda arayüzü doğrulamak gerekebilir.

Codex başlangıçta Git index yazma izni isteği nedeniyle `git add` için durdu. Kullanıcı, tekrar tekrar normal işlemlerde izin istememesini özellikle istedi. Bu sorun görüldükten sonra Tam erişim seçeneği açıldı.

### Kullanım kotası

Codex uzun süren bir oturumdan sonra ekranda şunu gösterdi:

- “Kullanım limitine ulaştınız.”
- “Continue to upgrade your plan or retry on 10 Eki 2026 20:46” benzeri reset bilgisi.
- `You're out of Codex and Work usage` uyarısı.

Bu screenshot eski tarihliydi (2026-09-10 konuşma bağlamı). **Bugünkü plan ve kullanım durumu kesin bilinmiyor.** Kullanıcı şu sırada Go planında aylık 6 USD ödediğini gösteren bir ekran paylaştı; Plus 20 USD/ay, Pro 120 USD olarak görünüyordu. Kullanıcı Pro’nun bütçesine uymadığını söyledi; cumartesi para alıp pazar Plus’a geçmeyi planladığını belirtti. Bu planın gerçekleşip gerçekleşmediği doğrulanmadı; yeni GPT, mevcut planı varsaymamalı.

Kullanıcının temel kaygısı: sınırlı Codex kullanımını büyük işi bitirmeden tüketmemek. Daha sonraki işlerde mümkün olduğunca dosyaların tekrar tekrar okunmasını, dev promptun her seferinde yeniden çalıştırılmasını ve gereksiz `xhigh` kullanımını azaltacak; fakat mühendislik doğruluğundan taviz vermeyecek bir plan gerekiyor. Kullanım limiti güncel ekranından kontrol edilmeli; günlerce kesintisiz çalışma garanti edilemez.

---

## 7. Kalıcı Codex hafızası için oluşturulan belgeler

Master görevde repository içinde kalıcı durum yönetimi istendi:

- `AGENTS.md`
- `docs/CODEX_STATE.md`
- `docs/CHANGELOG_CODEX.md`
- `docs/ARCHITECTURE_DECISIONS.md`

Codex Phase 0’da bu dört dosyanın oluşturulduğunu bildirdi. İlk commit denemesi Git index izin isteği nedeniyle reddedilmişti. Sonraki Codex aşamasında `50136e1` commit’i GitHub’da doğrulandığı bildirildi; bu nedenle bu belgelerin hangi commit’e girdiği ve güncel içerikleri yeniden kontrol edilmelidir.

Bunlar kalıcı kaynak-of-truth olacak şekilde düşünülmüştür:

1. Git commit geçmişi ve çalışma ağacı.
2. `AGENTS.md` — doğrulanmış sürekli kurallar ve invariant’lar.
3. `docs/CODEX_STATE.md` — güncel phase/milestone/task, son test/commit/push, sonraki iş, blockers/deferred items.
4. `docs/CHANGELOG_CODEX.md` — milestone kronolojisi.
5. `docs/ARCHITECTURE_DECISIONS.md` — problem, seçilen çözüm, alternatifler, trade-off.

Her yeni Codex oturumu bu belgeleri ve Git’i kontrol ederek başlamalıdır. Elektrik kesintisi/terminal kapanması durumunda sohbet hafızasına güvenilmemeli. Her tamamlanmış, doğrulanmış milestone küçük commit ile kaydedilmeli ve GitHub’a push edilmelidir.

---

## 8. En son görünür durum — kritik devralma noktası

En son ekran görüntüsünde Codex şöyle bir iş akışı yürütüyordu:

- GitHub’da `50136e1` commit’i doğrulandı.
- `M1.2` olarak scenario üretimi ve `None` sızıntısı ele alınmaya başlandı.
- Codex güvenli fixture ile kök nedeni yeniden üretti: boş zone sözlüğü, fallback’in bullish ve bearish metinlerine doğrudan `None` koyuyordu.
- Codex’in ilan ettiği dar kapsam:
  - yeni scenario engine yalnızca finite sayılar ve geçerli bullish/bearish geometry varsa trigger/invalidation/target metni üretsin;
  - aksi halde güvenli `validated setup yok` benzeri metin dönsün;
  - `server.py` fallback’i bu engine’e yönlendirsin ve AI’den gelen scenario metnini de `None / NaN / Infinity / undefined` karşısında sanitize etsin;
  - saf unit testler: boş, geçersiz, bullish, bearish ve AI metni senaryoları;
  - ilk düzeltmede frontend değiştirilmesin; API mevcut sözleşmede güvenli metin dönsün.
- Kullanıcı, her push sonrasında Render deploy ve runtime health doğrulamasının zorunlu olmasını ayrıca istedi. Codex bunu kalıcı çalışma kurallarına ekleyeceğini, Render arayüzünü mevcut oturumla tarayıcı üzerinden kontrol etmeyi deneyeceğini söyledi.
- **Sonrasında Codex kullanım limitine ulaştı.** Ekranda “You're out of Codex and Work usage” göründü. Bu nedenle scenario bug’ının tamamlandığı, test edildiği veya commit/push edildiği doğrulanmış değil.
- Aynı zamanda daha önce `50136e1` commit’i için Render’dan “deploy failed for trade-ai” e-postası gelmişti. Codex’in bu deployment’ı loglarla incelemeyi bitirdiği doğrulanmış değil.

### Bu yüzden yeni GPT/Codex’in ilk yapacağı iş

Kodlamaya direkt devam etmeden, mevcut durumu sakin şekilde doğrula:

1. `git status`
2. `git log --oneline -n 15`
3. `git rev-parse HEAD`
4. `git rev-parse origin/main`
5. `git diff`
6. `AGENTS.md`, `docs/CODEX_STATE.md`, `docs/CHANGELOG_CODEX.md`, `docs/ARCHITECTURE_DECISIONS.md` dosyalarını oku.
7. Scenario/AI fallback değişikliklerinin yerel diff’te var mı, commit edildi mi, push edildi mi, test edildi mi kontrol et.
8. `50136e1` için Render deployment durumunu ve loglarını mevcut Render web oturumu/erişilebilir entegrasyonla kontrol et. Login/API key lazımsa önce onsuz diğer güvenli işlere devam edilebilir mi değerlendir; erişilemezse tam blocker’ı raporla.
9. Commit veya push yapmadan önce mevcut değişikliklerin ne olduğunu anla; körlemesine `git add .` kullanma.
10. Üç yedek dosyaya dokunma.

---

## 9. Kullanıcıya daha önce verilen büyük kapsamlı hedefler / backlog

Bu backlog’un tamamını bir kerede kodlamak şart değildir. Önce mevcut kodu incele; özelliklerin zaten var olup olmadığını ve gerçek ihtiyacı belirle. Her modülü ancak anlamlıysa, veri kaynağı varsa ve test edilebiliyorsa ekle. “Architecture ready” ile “gerçekten live/işlevsel destek var” ifadelerini birbirinden ayır.

### A. Core doğruluk ve sağlamlaştırma

- `build_zones()` geometry ve RR invariant’ları.
- `scenarios` alanında `None`, `NaN`, `Infinity`, `undefined` olmaması.
- Outcome engine aynı OHLC mumunda TP ve invalidation birlikte görülünce `ambiguous` olarak davranıyorsa contract/test bununla tutarlı olmalı; bu koşulda sonucu keyfi biçimde win/loss sayma. Intrabar veri yetersiz olduğunda belirsizliği açıkça temsil et.
- Decision gate testleri; aynı yön, min supporting evidence, opposing evidence ve composite/confluence çelişkileri.
- API response ve frontend display doğrulaması.
- Data-quality kontrolleri: missing/duplicate/out-of-order/stale/malformed candles, invalid OHLCV, timestamp inconsistency, insufficient candles.
- Sayısal güvenlik: divide-by-zero, negatif risk, yanlış tarafta target/invalidation, NaN/Inf/None ve bozuk JSON.
- Provider timeout, network errors, rate limit, empty/malformed response ve opsiyonel kaynağın unavailable olması halinde güvenli fallback.
- Test DB/izole testlerde destructive history/delete işlemlerinden kaçınma.

### B. Market intelligence

- Market regime: TRENDING, RANGING, BREAKOUT, BREAKDOWN, HIGH_VOLATILITY, LOW_VOLATILITY; accumulation/distribution ancak veriye dayalıysa.
- Market structure: HH/HL/LH/LL, BOS, CHoCH, internal/external structure, confirmation.
- Liquidity sweeps / false breakout / wick rejection.
- Volume Profile: POC, VAH, VAL, HVN, LVN (veri/hesap mantığı uygunsa).
- Divergence: RSI, MACD, volume, CVD, price/OI.
- Daha gelişmiş Order Flow: CVD, aggressive buy/sell, absorption, exhaustion, delta divergence.
- Daha gelişmiş Order Book: depth imbalance, liquidity wall, wall persistence, pressure changes. Tek snapshot'a aşırı anlam yükleme; temporal metrik için cache/history gerekir.
- Futures Positioning: Price ↑/↓ ile OI ↑/↓ kombinasyonları ve funding context’i.
- Liquidation: clusters, acceleration, cascade, squeeze context; WebSocket reconnect, duplicate/stale/malformed event ve restart testleri.
- MTF: HTF bias/current timeframe/LTF confirmation/tradeability ayrı kalsın; üst timeframe bias tek başına current timeframe trade sinyali zorlamasın.
- Cross-market context: DXY, US10Y, VIX, NASDAQ, S&P 500, gold, oil; correlation sabit kabul edilmemeli, gerekiyorsa rolling correlation kullanılmalı.
- Macro/economic calendar: CPI, PPI, NFP, FOMC, Fed rates, GDP, unemployment, ECB, BOJ; veri kaynağı yoksa provider interface + unavailable/deferred; fake live data yok.
- News: headline, source, timestamp, asset relevance, freshness, sentiment, impact, confidence; ilgisiz haber ilgili varlık evidence’ı olmamalı.
- Trading sessions: Forex Tokyo/London/New York/London-NY overlap; crypto için Asia/Europe/US session context opsiyonel.
- Explainability: “neden bu yön?” sorusuna gerçek deterministik evidence’larla cevap; AI evidence uyduramaz ve kararı değiştiremez.

### C. Multi-asset / multi-market

- Kripto yalnızca BTCUSDT’ye bağlı kalmasın. Dinamik exchange metadata/symbol discovery kullan; örnek coinler: BTC, ETH, BNB, SOL, XRP, ADA, DOGE, AVAX, LINK ve kaynağın desteklediği uygun diğer semboller.
- Spot ile USDT-M futures market type ayrımı net olmalı; yanlış market endpoint’ine gitme.
- Forex provider abstraction: öncelik EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, USDCAD, NZDUSD.
- **XAUUSD zorunlu hedef**. Kullanıcı arayüzünde Forex/Markets altında sunulabilir, ancak internal market type’da FX ile Metals ayrımına izin ver; XAUUSD’yi kavramsal olarak sıradan FX pair sayma.
- Forex/metal için pip/tick size, spread, market hours, sessions ve gerekiyorsa rollover/swap context düşünülmeli.
- Hisse/indeksler: hemen tüm sembolleri live desteklemek şart değil; equities/indices için provider abstraction/extension point hazırlanabilir. “Hazır mimari” live provider varmış gibi sunulmamalı.

### D. Provider ve runtime güvenilirliği

- Provider-specific response shape’i analysis engine’in içine gömme; normalized market data model kullan.
- Gereken yerde timeout, retry, exponential backoff, cache, de-duplication, rate-limit handling ve circuit breaker.
- Var olan paralel çağrıları gereksiz yere seri hale getirme.
- Liquidation stream analiz request’i başına açılmamalı; FastAPI lifecycle içinde arka planda kalmalı.
- Structured logs, request id, analysis id, provider latency/failure ve toplam latency gibi observability iyileştirmeleri değerlendir.
- UTC storage ile frontend display timezone’u ayır.
- Secrets `.env`/environment üzerinden; source, Git, logs veya API response’a sızmamalı.

### E. Frontend

- Response alanları doğru gösterilmeli: direction, confidence, final_score, scores, zones, quality, confluence, scenarios, MTF, Order Flow, Liquidity, Futures, Liquidation.
- Null/unavailable değerleri kullanıcı dostu şekilde göster; `None`, `undefined`, `NaN`, `Infinity` asla gösterme.
- Türkçe/İngilizce dil sistemi ve sonraki diller için düzgün localization altyapısı eksikse değerlendir. Kullanıcı “dil” konusunun da eksiklere dahil olmasını istedi; bu görev önceki master promptların kapsam listesinde net biçimde unutulmuş olabilir. Dili/fallback metinlerini sadece tek bir backend string’ine değil, uygulamanın bütün kullanıcıya görünen UI metinlerine göre denetle.
- Frontend/backend API contract uyumunu koru; gereksiz breaking change yapma.
- UI evidence ile deterministic sonucunu çelişkili göstermesin; UI sadece “BUY” göstermek yerine gate/conflict/context’i anlaşılır hale getirebilir.

### F. Backtest / evaluation / calibration

- Backtest engine: symbol, market type, timeframe, timestamp, signal/direction/setup, entry, invalidation/SL, TP1/TP2, result, MFE, MAE, holding time.
- Metrics: win/loss rate, expectancy, profit factor, max drawdown, average RR, average win/loss.
- Walk-forward ve out-of-sample ayırımı.
- **Look-ahead bias/data leakage yok:** signal timestamp sonrasındaki candle/volume/liquidation/OI/funding/indicators/structure kararda kullanılmamalı.
- Live ve backtest mümkün olduğunca aynı deterministic decision path’i paylaşmalı.
- Heuristic confidence, tarihsel sonuçlarla kalibre edilmeden gerçek başarı olasılığı olarak sunulmamalı.
- Outcome pending/resolved akışını koru; intrabar belirsizliği dürüstçe işle.

### G. Deployment/CI/Git

- Her önemli milestone: test → diff review → commit → push → remote doğrulama.
- Push sonrası Render otomatik deployment’ını kontrol et; son durum sadece GitHub push ile tamamlanmış sayılmaz.
- Deploy başarısızsa loglarda root cause bul; körlemesine kod değiştirme. Kod kaynaklıysa düzelt/test/commit/push ve redeploy izle.
- Health endpoint ve uygun non-destructive API smoke tests çalıştır.
- Render’a erişim için mevcut tarayıcı oturumu veya mevcut entegrasyon kullanılabilir. API key/login gerçekten gerekiyorsa ve başka işler devam edebiliyorsa durma; eksik işi DEFERRED kaydet. Kritik/blocker ise güvenli checkpoint sonrası bekle ve kullanıcıdan tam olarak gereken erişimi iste.
- Force push, history rewrite, `git reset --hard` ile kullanıcı değişikliklerini silmek yasak.
- Destructive DB işlemleri, collection drop, toplu history silme ve production data temizleme öncesi dur.

---

## 10. Önceki Codex’e verilen çalışma davranışı kuralları

Bu kurallar devam eden her milestone için geçerlidir:

1. Baseline doğrulaması olmadan büyük kod değişikliği yapma.
2. Her değişiklikten önce ilgili kodu incele ve root cause’u anla.
3. Değişikliği küçük ve mantıksal tut.
4. Compile/syntax, unit/synthetic, regression, gerekirse integration/API testleri çalıştır.
5. Başarısız testleri gizleme; nedenini çöz.
6. `git diff` ve `git status` ile amaç dışı değişiklikleri kontrol et.
7. Yalnızca doğrulanmış milestone’u atomik commit et.
8. Uygunsa push et ve remote ref’i doğrula.
9. `CODEX_STATE.md`, `CHANGELOG_CODEX.md`, gerekirse `ARCHITECTURE_DECISIONS.md`’yi güncelle ve bunları commit ile kaydet.
10. Render deployment + runtime health zincirini kontrol et.
11. API kritik değilse provider interface/fallback/deferred kaydıyla devam et; önemli değil diye tüm geliştirme durmasın.
12. Fake live market data, uydurma API key veya sahte API yanıtlarını gerçekmiş gibi kullanma.
13. Büyük tek bir dev patch, tüm backend/frontend rewrite veya çok sayıda engine’i aynı anda değiştirmekten kaçın.
14. Finalde yalnızca gerçekten test edilmiş hususları “başarılı” diye bildir.
15. Elektrik kesintisi/restart halinde state + Git diff + commit history karşılaştırılmadan körlemesine devam etme.

---

## 11. Render / deployment olayı

Kullanıcının telefonuna Render bildirimi geldi:

- `deploy failed for trade-ai`
- Commit: `Align outcome ambiguity regression contract`

Bu commit adı `50136e1` ile uyuşuyor. Bu deployment hatasının sebebi bilinmiyor; build logları görülmedi. Kullanıcı, “tam yetki verdik, Render’ı da kontrol edemez mi?” diye sordu. Codex mevcut Render tarayıcı oturumu varsa kullanacağını, erişim anahtarı istemeden Computer Use ile kontrol etmeye çalışacağını söyledi. Ancak hemen ardından Codex kullanım limitine ulaştı; Render araştırmasının bittiği doğrulanmadı.

**Gerekli işlem:** Güncel Render deployment history/logs aç, failure reason’ı belirle. En son commit deployment’ı başarısızsa bunu state’e kaydet. Failure sebebi geçici platform sorunu, eksik environment variable, build komutu, bağımlılık veya uygulama runtime hatası olabilir; logsuz varsayım yapma. Render deploy başarısızken projenin production-ready olduğunu söyleme.

---

## 12. Sonraki doğru hareket sırası

Yeni GPT şu sırayı takip etmeli:

### Aşama 1 — Güncel durumu doğrula

- Kullanıcının Plus/Go durumunu ve Codex kullanım limitini varsayma; güncel ekran/ifade üzerinden öğren.
- Repo’nun gerçekten hangi commit’te olduğunu yerelde ve remote’da kontrol et.
- `AGENTS.md` ve docs state dosyaları varsa oku.
- Uncommitted scenario değişiklikleri var mı belirle.
- Backup dosyalarına dokunma.

### Aşama 2 — Scenario milestone’u güvenli bitir

Eğer henüz tamamlanmadıysa:

- `None` scenario bug’ını güvenli fixture ile test et.
- Scenario üretimini backend’de sağlamlaştır.
- Sonlu (finite) numeric değer ve doğru side/geometry olmadan directional price-specific narrative üretme.
- Neutral/zone-less durum için güvenli generic fallback kullan.
- AI narrative içinden `None`, `NaN`, `Infinity`, `undefined` sızıntısını sanitize et; mümkünse response schema doğrulamasını da ekle.
- Empty/invalid/bullish/bearish/AI fallback senaryoları için unit + regression testleri ekle.
- Frontend’i sırf metin bug’ı için gereksiz değiştirme.
- Compile/test/diff yap, atomik commit ve push, state/changelog güncelle.

### Aşama 3 — Render başarısız deployment’ını incele

- Özellikle `50136e1` ve ondan sonra push edilmiş commit’lerin deployment durumunu kontrol et.
- Render erişilemiyorsa hangi permission/API/login’e ihtiyaç olduğunu açıkla; ancak kritik değilse diğer güvenli işlere devam et.
- Deployment ve health doğrulamasını master procedure’a ekle.

### Aşama 4 — Phase 1 devamı

- Zone/RR invariant regression tests.
- Outcome ambiguity test contract: aynı mumda hem TP hem invalidation olduğunda existing `ambiguous` behavior, intrabar sıralama bilinmediğinden muhafazakâr olarak kabul edilmişti; bu sözleşme açıkça belgelenmeli. Eğer farklı tercih yapılacaksa veri/algoritma gerekçesi olmalı.
- Core gate, numerical safety, provider fallback, data quality ve API/frontend contract testlerini öncelik sırasına koy.
- Daha sonra market regime, advanced engines, multi-asset/FX/XAUUSD, localization, backtest ve diğer backlog’a geç.

---

## 13. Kullanıcının açıkça ifade ettiği kaygılar

- Haftalardır projeyle uğraşıyor, manuel dosya kopyalama ve küçük adımlarla yoruldu.
- Daha yüksek otonomi istiyor; normal teknik işlemlerde tekrar tekrar onay sorulmasını istemiyor.
- Aynı zamanda hiçbir şeyi test etmeden başarı saymayı istemiyor. Kontrol ve doğrulama önemli.
- Evde olmadığı sırada elektrik gidebilir. Çalışmanın nerede kaldığını unutan veya bozuk bir yarım durum bırakan süreç istemiyor.
- Kullanım hakkı sınırlı; gereksiz yere repository’yi yeniden okutmak, her görevde uzun reasoning tüketmek istemiyor. Önce konuşulmuş final hedefler ve gerçek eksikler envanteri çıkarılmalı, ardından kullanımı verimli, ama güvenli milestone’larla ilerlenmeli.
- Plus’a geçmeyi düşünüyordu; önceki ekran Go $6/ay, Plus $20/ay, Pro $120/ay gösteriyordu. Pro bütçesine uygun değil. Plus’a geçme planının güncel durumu doğrulanmalı.
- Harici API gerektiğinde, API kritik değilse diğer işlere devam edilmesini ve bu işi `DEFERRED` olarak kaydetmesini istiyor. Ancak olmadan devam etmek gerçekten imkânsız olan kritik API/credentials varsa güvenli checkpoint sonrası tam olarak ne gerektiği söylenerek beklenmesini istiyor.
- **XAUUSD zorunlu hedef.**
- Dil/i18n sistemi de eksiklik envanterinde olmalı; önceki ilk master promptlarda bu başlık net listelenmemişti.
- Render deployment ve runtime health doğrulaması, GitHub push sonrası işin tamamlanması için zorunlu olmalı.

---

## 14. Kod/komut referansları

### Git baseline kontrolü (repo dizininde)

```cmd
git status
git branch
git log --oneline -n 15
git remote -v
git rev-parse HEAD
git rev-parse origin/main
git diff
```

### Python compile

Repo root’ta:

```cmd
python -m py_compile backend\market_ai\engines\analysis.py
```

### Zone synthetic test (repo root)

```cmd
cd "%USERPROFILE%\OneDrive\Desktop\Trade-main V1\Trade-main" && python -m py_compile backend\market_ai\engines\analysis.py && cd backend && python -c "from market_ai.engines.analysis import build_zones; cases=[('B1',100,[{'level':99.8}],[{'level':100.2}],2),('B2',100,[{'level':98}],[{'level':103}],2),('B3',100,[{'level':95}],[{'level':101},{'level':104}],2),('B4',100,[],[{'level':101}],2),('S1',100,[{'level':97}],[{'level':100.5}],2),('S2',100,[{'level':96},{'level':94}],[{'level':102}],2)]; [print(name,build_zones('bullish' if name.startswith('B') else 'bearish',price,sup,res,atr)) for name,price,sup,res,atr in cases]"
```

### Analysis API smoke test

Sunucu canlıyken, Windows CMD’de URL/JSON quote edilmelidir. Daha önce çalışan istek:

```cmd
curl -X POST "http://127.0.0.1:8000/api/analysis" -H "Content-Type: application/json" -d "{\"symbol\":\"BTCUSDT\",\"timeframe\":\"5m\"}"
```

`GET /api/analysis?...` kullanılmaz; OpenAPI doğrulamasına göre bu endpoint POST’tur. `&` içeren query URL’sini Windows CMD’de kullanacaksan tırnak içine al; ancak analysis endpoint’ine JSON POST tercih et.

### OpenAPI kontrolü

```cmd
curl "http://127.0.0.1:8000/openapi.json" | findstr /i "analysis"
```

### Uyarı

İzin/approval ayarlarını körlemesine `config.toml` üzerinde değiştirme. Kullanıcının Codex arayüzünde çalışma menüsünden `Tam erişim` seçeneğini açtığı bildirilmişti. Repo trust ve Windows sandbox elevated ayarları da mevcut config çıktısında vardı.

---

## 15. Önceki master görev promptlarının özeti

Kullanıcıya iki aşamalı kapsamlı Codex master promptları verildi; son revize sürümde ana kurallar şunlardı:

- Repo baseline, protected backups, persistent state documents.
- Elektrik kesintisi/recovery prosedürü.
- Otonom kod/test/Git/commit/push, ama destructive DB/secret/ücretli API/force push gibi riskli işlemlerde dur.
- API kritik değilse interface + fallback + deferred kaydıyla devam et; kritikse dur ve exact blocker’ı açıkla.
- Mimaride mevcut double-counting korumaları, Confluence, MTF bias/tradeability, risk/zone/RR, liquidation WS korunmalı.
- Scenario `None` bug’ı kesin düzeltilecek.
- Data quality, market regime, structure/sweeps, order flow/CVD/divergence, liquidity, volume profile, futures/liq, MTF, cross-market, macro/news, crypto dynamic symbols, FX majors + XAUUSD, sessions, equities/indices extension, explainability, backtest/out-of-sample/walk-forward, frontend i18n, API safety, security, caching/retry/performance.
- Her milestone test/review/diff/atomic commit/push/state update.
- GitHub push sonrası Render deployment/logs/health-check doğrulaması; deploy failed ise önce root cause loglarından belirle, körlemesine kod değiştirme.
- Final raporda gerçek testlerin sonuçları ve deferred/blocker açıkça bildirilecek.

**Bu devir dosyası, aynı master promptu yeniden göndermeden önce repo ve Codex state’inin kontrol edilmesini önerir.** Kullanım kotası kısıtlı olabileceği için geçmişi uzun uzun tekrar analiz etmek yerine mevcut state ile devam et.

---

## 16. Nihai başarı kriterleri

Uygulamanın bütün kapsamı için tek bir “yeşil” etikete güvenme. Her pazarı ve özelliği gerçek olarak doğrula:

- Core deterministic analysis ve Confluence doğrulanmış.
- Zone geometry/invalidation/TP/RR invariant testleri geçiyor.
- Neutral scenario’da None/NaN/Infinity/undefined yok.
- Outcome ambiguity contract belgeli ve testli.
- Data quality, network/error fallback ve numerical safety testli.
- Order Flow, Liquidity, Futures, Liquidation, MTF entegrasyonu regression testli.
- Crypto symbol keşfi gerçek sağlayıcıdan yapılıyor; spot/futures ayrımı doğru.
- Forex ve **XAUUSD** için gerçek veri sağlayıcısı varsa canlı doğrulandı; API yoksa açıkça “deferred/unavailable” deniyor, fake live data kullanılmıyor.
- Dil sistemi/UI lokalizasyonu varsa bütün kullanıcıya görünen metinler kapsanıyor, sadece API’de birkaç string değil.
- Backtest look-ahead bias içermiyor; walk-forward/out-of-sample sınırları belgeli; metrics gerçekten hesaplanıyor.
- Frontend/backend schema tutarlı.
- Secret sızıntısı yok; testler production history’yi silmiyor.
- Git commit/push doğrulandı.
- Render deploy başarılı ve runtime health mümkün olan ölçüde doğrulandı. Erişim yoksa bu başarı gibi gösterilmez; blocker/deferred raporlanır.
- `AGENTS.md`, `CODEX_STATE.md`, `CHANGELOG_CODEX.md`, `ARCHITECTURE_DECISIONS.md` güncel ve commit edilmiş.

---

## 17. Bu devir belgesinden sonra kullanıcıya verilecek kısa yönlendirme

Yeni GPT bu dosyayı yükledikten sonra kullanıcıdan tüm geçmişi tekrar anlatmasını istememeli. Önce şu şekilde yanıt vermeli:

1. Bu devir dosyasını okuduğunu ve ana checkpoint/son durum/bug’ları anladığını söyle.
2. Güncel repo/Codex state’i doğrulanmadan kodu körlemesine değiştirmeyeceğini belirt.
3. İlk olarak `50136e1` sonrasındaki scenario değişikliği ve Render deployment durumu ile başlayacağını söyle.
4. Kullanım kotası/plan bilgisi eski olabileceğinden bunu varsaymadan hareket et.

**En güncel teknik riskler:** Scenario `None` bug’ının tamamlanıp tamamlanmadığı bilinmiyor; `50136e1` Render deploy’u failed bildirimi aldı; Codex son oturumda usage limitine ulaştı. Öncelik bunların gerçek güncel durumunu bulmak olmalı.
