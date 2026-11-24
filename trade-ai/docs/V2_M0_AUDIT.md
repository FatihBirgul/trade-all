# M0.1 — V1 analiz envanteri ve geçiş kararı

**Denetim tarihi:** 2026-10-20. **Kaynak:** `main` commit `50136e13428028156b17c5953bdb27dc99eb682f` dosyalarının GitHub üzerinden okunması.  
**Kapsam sınırı:** Kaynak kodu incelendi; bu oturumda Python testleri çalıştırılamadı. Bir fonksiyonun var olması, doğruluğunun veya üretimde çalıştığının kanıtı değildir.

## Fonksiyon ve yöntem matrisi

| Alan | V1'de doğrulanan fonksiyon/modül | V2 kararı | Gerekçe / eksik |
| --- | --- | --- | --- |
| EMA/SMA | `technical.ema`, `sma`; EMA20/50/100/200 | **Koru, test et** | Timeframe-aware warm-up var; eksik bar durumları ve spot/FX ayrımı test edilmeli |
| RSI/MACD/Stoch RSI | `technical.rsi`, `macd`, `stoch_rsi` | **Koru, test et** | Momentum korelasyon kovası ile çift sayım engellenmeli |
| ATR/Bollinger | `technical.atr`, `bollinger` | **Koru, test et** | Risk/rejim girdisi; yönsel kanıt olarak sayılmamalı |
| Swing/market structure | `technical._swings`, `support_resistance`, `market_structure` | **Refaktör** | BOS/CHoCH gibi ayrı, doğrulanabilir olay modelleri gerekiyor |
| Mum formasyonları | `candlestick.detect` | **Koru, test et** | Recency, confirmation ve same-candle conflict koruması mevcut |
| Grafik formasyonları | `chart_patterns.detect` | **Koru, test et** | Pivot doğrulaması var; detector hatada boş listeye düşüyor, hata gözlemlenebilirliği gerek |
| Trend/momentum/hacim/structure skorları | `analysis._trend_score`, `_momentum_score`, `_volume_score`, `_structure_score` | **Refaktör** | Ağırlıklar kalibre değil; puan güvenilir olasılık değildir |
| Volatilite rejimi | `analysis._volatility_regime`, `_volatility_rr_floor` | **Koru ve genişlet** | **Tam piyasa rejimi/Strategy Router değildir** |
| Confluence / correlation | `confluence.Evidence`, `deduplicate_evidence`, `build_confluence` | **Koru, test et** | Correlation bucket, recency, confirmation mevcut; yeni göstergelere bucket tanımı gerekir |
| MTF | `mtf.analyze`, `higher_timeframes`, `lower_timeframes` | **Koru, refaktör** | Bias ile tradeability ayrılmış; kapanmış mum ve zaman hizalaması upstream zorunlu |
| Order flow/delta | `order_flow.analyze`, `score`, `evidence` | **Veriye bağlı koru** | Aggregate trades gerekir; FX spot'ta aynı veri varmış gibi davranma |
| Order-book liquidity | `liquidity.analyze`, `score`, `evidence` | **Veriye bağlı koru** | Gerçek borsa order book gerektirir; spoofing riski, snapshot freshness |
| OI/funding | `futures_positioning.analyze`, `score`, `evidence` | **Veriye bağlı koru** | Yalnız futures; OI tek başına yön sinyali değil |
| Liquidation | `liquidation.normalize_event`, `analyze`, `score`, `evidence` | **Veriye bağlı koru** | Kaynak Binance Futures; geçmişte HTTP 451 erişim engeli |
| Outcome | `outcome.evaluate`, `summarize` | **Koru, test et** | Intrabar TP/SL belirsizliği `ambiguous` kalmalı |
| Zone / RR | `analysis.build_zones`, `aggregate` | **Koru, test et** | Geometri ve no-trade gate mevcut; yeni portfolio risk gate ayrı |
| Binance provider | `MarketDataProvider`, `BinanceProvider` | **Adapter refaktörü** | Spot/futures ayrımı, provider capability, freshness ve normalize data contract |
| Haber | `news_provider.NullNewsProvider` | **Yeni sağlayıcı gerekli** | Ekonomik takvim, release timestamps, DST ve blackout yok |
| AI | `AIProvider` | **Adapter refaktörü** | Deterministik kararı değiştirmeyen challenger; API/auth/kota doğrulanmalı |

## V2'de **yeni geliştirilecek** yöntemler

**Market regime + Strategy Router:** trend/range/breakout/reversal/unknown, market/session/data-capability uyumu, conflict resolver, no-trade. V1'deki `_volatility_regime` bunun yerine geçmez.

**Structure/SMC:** BOS, CHoCH, liquidity sweep, order blocks, breaker blocks, FVG; repaint/lookahead-free pivot event ve objektif eşikler.

**Trend:** ADX, Supertrend; cross-market relative strength.

**Volume/profile:** VWAP, Anchored VWAP, Volume Profile (POC/VAH/VAL/HVN/LVN), TPO/Market Profile. Gerçek işlem hacmi, tick volume ve unavailable birbirinden ayrılacak.

**Order flow:** CVD, delta divergence, absorption/exhaustion; yalnız veri yeteneği varsa.

**Session/volatility:** Asya/Londra/NY high-low, ORB, failed breakout/failed auction, volatility compression/expansion, session DST.

**Macro/cross-market:** Fed/CPI/NFP/FOMC, DXY/US10Y/VIX, cross-market korelasyon; kaynak ve zaman hizalaması koşullu.

## Kaynak düzeyinde görülen riskler

1. **`backend/server.py::_fallback_narrative`**: `zones.get(...)` değerlerini f-string ile yazıyor; `None` kelimesinin kullanıcıya sızması mümkün. Ayrıca yön nötr olsa bile bullish/bearish senaryo metinleri üretilebiliyor. Test-fixture ile düzeltilecek.
2. **`backend/market_ai/providers/market_data.py::_parse_candles`**: Binance kapanış zamanı (`close_time`) ile yerel saat karşılaştırılıyor. Genel V2 data contract için bar-close exclusive, server-clock drift ve stale/gap kontrolü açıkça tanımlanmalı.
3. **`backend/market_ai/engines/chart_patterns.py`**: beklenmeyen hata boş pattern listesiyle sonuçlanıyor; silent degradation için gözlemlenebilirlik gerekiyor.
4. **`backend/market_ai/db.py`**: `MONGO_URL` ve `DB_NAME` import sırasında zorunlu; saf test izolasyonu güçleşiyor. Yeni modüller DB/env import etmemeli.
5. **`backend/tests/test_outcomes.py`**: varsayılan uzak preview URL'sine çağrı yapan testler var; bazıları kayıt yaratır / evaluate eder. İzole test ortamı doğrulanmadan çalıştırma.
6. **`docs/CODEX_STATE.md`**: `main` güncel HEAD'i ile eski checkpoint farklı. V2 için ayrı state tutulmalı, eski kayıt geriye dönük değiştirilmemeli.
7. **`backend/market_ai/config.py`**: varsayılan AI model ve sağlayıcı değerleri canlı erişim garantisi değildir; kullanılabilirlik maliyet/kimlik doğrulaması ayrı kontrol edilmeli.

## Veri yetenek matrisi — tasarım hedefi

| Özellik | Kripto spot | Kripto perpetual | Spot FX | XAUUSD spot |
| --- | --- | --- | --- | --- |
| OHLC | Sağlayıcıya bağlı | Sağlayıcıya bağlı | Sağlayıcıya bağlı | Sağlayıcıya bağlı |
| Gerçek borsa hacmi | Genellikle mümkün | Genellikle mümkün | **Merkezi toplam hacim yok** | **Merkezi toplam hacim yok** |
| Aggressor delta / CVD | Trade feed varsa | Trade feed varsa | **Varsayılan unavailable** | **Varsayılan unavailable** |
| Order book | Borsa feed varsa | Borsa feed varsa | **Varsayılan unavailable** | **Varsayılan unavailable** |
| OI / funding / liquidation | **Yok** | Feed varsa | **Yok** | **Yok** |
| Tick volume | Feed'e bağlı | Feed'e bağlı | Broker'a bağlı | Broker'a bağlı |

**Not:** Yukarıdaki tablo tasarım kısıtıdır; belirli bir sağlayıcı seçilmeden hiçbir sütun canlı erişim garantisi vermez. Altın futures ile spot XAUUSD ayrı kontrattır.

## M0→M1 teslim sözleşmesi

- [x] V1 modül/fonksiyon varlığı GitHub kaynak kodundan envantere alındı.
- [x] Korunacak/refaktör edilecek/yeni geliştirilecek alanlar sınıflandırıldı.
- [ ] Fonksiyon doğruluk ve regresyon testleri yerel veya izole CI'da çalıştırıldı.
- [ ] Provider capability ve normalize edilmiş kapalı-mum şeması kod/test ile doğrulandı.
- [ ] Strategy Router karar sözleşmesi ve conflict/no-trade testleri oluşturuldu.
- [ ] `None` fallback narrative bug için güvenli regresyon testi ve düzeltme tamamlandı.
- [ ] FX/XAUUSD kaynak ve lisans kararı verildi.

**Güvenlik:** `main`, Render, üretim verisi, yerel üç yedek dosya değiştirilmez. V2 geliştirmeleri `trade-ai-v2` dalındadır.

## Uygulama sonrası ek kayıt — 2026-10-20

Yukarıdaki envanter ve checkbox'lar ilk kaynak denetimi anının kaydıdır. Sonraki uygulamada normalize spot kontratı, kapalı mum QC, güvenli narrative, rejim sınıflandırıcısı ve QC→capability→regime→Router bağlantısı için 54 offline test çalıştırıldı; `4179e9c` commit'inin GitHub Actions syntax ve unit adımları başarılı oldu. Ayrıntı ve CI bağlantısı `V2_IMPLEMENTATION_STATE.md` içindedir. Bu doğrulama tüm V1 fonksiyonlarının doğruluğu, FX/XAU sağlayıcı/lisans kararı, kalıcı mum deposu veya portföy risk hesabının tamamlandığı anlamına gelmez.
