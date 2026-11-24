# V3/V2 güvenli analiz entegrasyonu: yerel rapor

7 Kasım 2026. Başlangıç V3 kökü `%USERPROFILE%/trade-ai-v3-core`, branch `codex/forex-xauusd-backend-v1`, temiz HEAD `d9e79b3`. Yeni yerel branch `codex/v3-v2-analysis-integration` bu commit'ten açıldı. V2 salt-okunur kök `%USERPROFILE%/trade-ai-v2-antigravity`, branch `antigravity/v2-analysis-research`, HEAD `c80c97f`; G-001/G-002 kod commit'i `68048b2` incelendi. V2'de başlangıçta değiştirilmiş `backend/market_ai/engines/chart_patterns.py` ve takip edilmeyen üç test ile `market_ai/__init__.py` korundu.

## Bulgular

- **G-001:** V2'nin eksik RSI ile güçlenen ağırlıklı momentum skoru V3'te yok. V3'ün normal 220 kapalı mum penceresinde Wilder RSI tanımlı. Ancak indikatör kaynağı `None` döndürürse V3 `candidates` içinde karşılaştırma hatasına düşüyordu. `forex/core.py` artık RSI yoksa veya sonlu değilse açık veri hatası veriyor; V4 `WAIT`/plansız, V5 `INSUFFICIENT_DATA`/plansız döner. Eksik değere sıfır veya yön puanı atanmaz.
- **G-002:** V3 MACD histogramından işaret puanı üretmiyor; `macd > signal` ve `< signal` kullanıyor. Eşitlik trend/pullback momentum teyidi üretmez. Bağımsız sıfır regresyonu eklendi; V2 skoru taşınmadı.
- **G-003:** Snapshot ana karar kapanışını ortak cutoff kullanır. Gelecek H4 gözlemi snapshot dışında kalır; eski H4, tamamlanmamış mum, yanlış market tipi ve mum kaynak kimliği reddedilir. Quote üzerindeki açık `provider` alanı V3 provider adıyla eşleşmek zorundadır; bu kimlik açığı kapatıldı. Broker seans boşlukları yalnız doğrulanmış saatlerle kabul edilir. Gerçek broker tatil/DST takvimi henüz doğrulanmadı.
- **G-004:** V2 teknik Cutler RSI rolling 14 gain/loss SMA; V3 14 değişim SMA seed'i ve sonraki Wilder RMA. Her ikisi ilk 15 kapanışta değer verir, düz seride 50 döner. V2 temel ATR ile V3 ATR 14 true-range SMA; V2 araştırma ADX/Supertrend ATR'si Wilder yumuşatması kullanır. V3 temel MACD 12/26/9 SMA-seeded EMA, V2 pandas ilk-değer seed'i kullanır; Bollinger V3 population, V2 sample std kullanır. Bunlar tanımlı varyant farklarıdır. V3 sürüm etiketleri `forex/unified.py:ALGORITHMS` içinde korunur. V2 referans testleri ve V3 golden testleri ayrı kanıttır.

## Uygulama kararı

Yeni bir V2 indikatör veya strateji motoru taşınmadı. V3'te mevcut olan EMA/RSI/MACD/ATR/Bollinger, breakout, yapı, MTF ve confluence karşılıkları korunuyor. V2 Stoch RSI/ADX/Supertrend/ROC, zone/pattern aileleri ve dört özel stratejinin mevcut verilerle ek karar değeri veya Forex uygunluğu kanıtlanmadı. Böylece bu teslimdeki gerçek entegrasyon, V2 bulgularının V3 veri/karar kapılarına uyarlanması ve bağımsız regresyon kanıtıdır. Ayrıntılı seçim [V3_V2_INTEGRATION_MATRIX.md](V3_V2_INTEGRATION_MATRIX.md) içindedir.

Manuel `POST /api/v5/analysis` sözleşmesi değişmedi; otomatik analiz, bildirim veya emir akışı eklenmedi. V1 yolları korunuyor. Yanlış/eksik veri plan veya lot yaratmaz. Çelişkili kanıt veto ve tekrar eden olay tekilleştirmesi mevcut testlerle doğrulandı. Sinyaller analitik adaydır; broker emir izni değildir. Gerçek MT5 terminali, Forex seansı, kaynak lisansı ve kârlılık doğrulanmadı. Push, merge veya Actions kullanılmadı.
