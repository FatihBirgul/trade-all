# V3 teknik analiz aktarım notu (Codex 2)

Yerel çalışma: `antigravity/v2-analysis-research`, başlangıç HEAD `195af2e`.
Başlangıç checkpoint'i `469b27d` bu branch'in atasıdır. Bu çalışma yalnızca
çevrimdışı fixture ve sentetik dizilerle doğrulandı; Forex/XAUUSD piyasa
performansı, başarı yüzdesi veya canlı sağlayıcı davranışı doğrulanmadı.

## Doğrulanan bulgular

- **G-001, doğrulandı ve düzeltildi:** Pozitif MACD histogramı sabitken RSI 40
  için momentum 3, confidence 12.7, karar kapısı kapalıydı. RSI `None` için
  momentum 25, confidence 32.3 ve kapı açıktı. Eksik RSI artık momentum
  yönüne katkı vermez. Karşılaştırma tüm Momentum → Confluence → Confidence →
  Gate zincirini `test_v2_analysis_missing_momentum.py` içinde sınar.
- **G-002, doğrulandı ve düzeltildi:** MACD histogramı sıfırken eski koşul
  `-25` üretirdi. Sıfırın yönsel işaret taşımadığı kabul edildi; sıfır artık
  nötr. Pozitif ve negatif küçük değerler mevcut işaret temelli `+25/-25`
  davranışını korur; büyüklüğe göre kalibrasyon yapılmadı.
- **G-003, mevcut kapı doğrulandı:** Çoklu zaman dilimleri aynı `as_of_ms`
  değeriyle istenir. Her çerçevenin son kapanmış mumu kendi süre sınırında
  denetlenir; gelecek veya gecikmiş 4H verisi tüm kararı `WAIT` yapar.
  `test_v2_mtf_time_integrity.py` servis düzeyinde bunu sınar. Forex seans
  boşlukları için ayrı takvim uyarlayıcısı henüz yoktur.
- **G-004, varyant farkı hata sayılmadı:** `engines/technical.py` Cutler/SMA
  RSI ve SMA ATR kullanır. V2 stratejileri Wilder RSI ve SMA ATR kullanır;
  `technical_research.py` ayrıca ADX/Supertrend için Wilder ATR hesaplar.
  `test_v2_rsi_atr_reference.py` matematiksel referans, sıfır kazanç/kayıp,
  ısınma ve sınır örneklerini içerir. Bu test dosyası çalışma başında
  takip edilmiyordu; mevcut kullanıcı çalışması olarak korundu. NaN içeren
  ham mumlar `data_quality.py` katmanında reddedilir. Doğrudan `atr()` çağrısı
  pandas satır maksimumunun NaN atlama davranışını kullanır; V3'te bu fonksiyon
  kalite kapısı olmadan çağrılmamalıdır.

## V3 için aktarım envanteri

| Bileşen | Kaynak | Aktarım koşulu |
| --- | --- | --- |
| EMA, SMA, RSI, MACD, ATR, Bollinger, Stoch RSI ve OHLCV | `backend/market_ai/engines/technical.py` | Varyantları açıkça etiketle; Forex gerçek hacmi yoksa volume/VWAP sonucu üretme. |
| ROC, Stochastic, Donchian, ADX/DMI, Supertrend | `backend/market_ai/v2/technical_research.py` | Araştırma çıktısıdır; doğrudan işlem izni vermez. |
| HH/HL/LH/LL, BOS/CHoCH, FVG, VWAP, sweep | `backend/market_ai/v2/price_action.py` | Kapanmış mum, pivot onay gecikmesi ve FX seans takvimi korunmalı. |
| Mum ve grafik formasyonları | `backend/market_ai/v2/pattern_research.py`, `chart_research.py`, `chart_confirmations.py`, `chart_boundaries.py`, `backend/market_ai/engines/chart_patterns.py` | Kapanış/onay zamanını ve ileri veri sızıntısı testlerini taşı. `chart_patterns.py` çalışma başında kirliydi; bu çalışmada değiştirilmedi. |
| Trend, range, confirmed/failed breakout | `backend/market_ai/v2/strategies.py` | Kripto spot ve gerçek hacim varsayımlarını FX/XAUUSD için yeniden değerlendir. |
| Confluence, MTF, karar ve zone | `backend/market_ai/engines/confluence.py`, `mtf.py`, `analysis.py` | Composite yalnızca trend, momentum, volume, structure, news kullanır. Diğer evidence tekilleştirilir. Confidence doğrulanmış olasılık değildir. |
| Veri kalitesi ve teknik adaptör | `backend/market_ai/v2/data_quality.py`, `market_data_contract.py`, `technical_adapter.py` | Şimdiki adaptör yalnızca kesintisiz kripto spot ve gerçek hacim içindir; FX için ayrı sözleşme gerekir. |

Codex 1 için: V3 Forex/XAUUSD entegrasyonunda `analysis_service.py` ve
`spot_provider.py` doğrudan taşınmamalı; bunlar kripto spot kimliği, Binance
kuralları ve gerçek hacim gerektirir. Piyasa veri adaptörü normalize edilmiş,
UTC temelli ve kapanmış mum üretmeli. Seans/tatil boşlukları için ayrı kalite
denetimi kurulmadan `gap_or_overlap` kapısı gevşetilmemeli. AI yalnızca
deterministik kararın açıklamasını üretmeli.

Kalan işler: Gerçek Forex/XAUUSD verisiyle kaynak, seans ve fiyat ölçeği
doğrulaması; işaret temelli MACD puanının büyüklük duyarlılığına ilişkin
kalibrasyon; strateji performansının yürüyen pencere ve maliyetli backtest
ile ölçümü. Bu not hiçbir başarı oranı iddia etmez.

## Yerel doğrulama

- `python -m compileall -q market_ai` ve `git diff --check` geçti.
- `python -m unittest tests.test_v2_product_api tests.test_v2_legacy_engines
  tests.test_v2_technical_adapter tests.test_v2_mtf_time_integrity
  tests.test_v2_analysis_missing_momentum -q`: 74/74 geçti.
- `python -m unittest tests.test_v2_legacy_engines
  tests.test_v2_technical_adapter tests.test_v2_rsi_atr_reference -q`:
  39/39 geçti.
- `python tests/run_v2_offline_tests.py`: 559 çalıştırıldı, 1 import hatası.
  Çalışma başında takip edilmeyen
  `backend/tests/test_v2_chart_pivot_causality.py`, runner `backend/`
  dizinindeyken `from backend.market_ai.engines import chart_patterns`
  satırında `ModuleNotFoundError: No module named 'backend'` üretiyor.
  Dosya kullanıcı çalışması olarak değiştirilmedi. Diğer 558 test geçti;
  kontrollü hata enjeksiyonlarının günlükleri test başarısızlığı değildir.
