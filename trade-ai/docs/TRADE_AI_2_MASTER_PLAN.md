# Trade AI 2.0 — Master Plan (taslak v0.1)

**Tarih:** 2026-10-20  
**Durum:** Aşamalı uygulama sürüyor; M1/M2'nin izole veri kalite, rejim ve Router akışı doğrulandı. Tam ürün veya tüm milestone'lar tamamlanmadı; güncel kanıt ve sınırlar `docs/V2_IMPLEMENTATION_STATE.md` içindedir. Bu belge `trade-ai-v2` geliştirme dalında tutulur; `main` ve Render üretim ortamı değiştirilmez.
**Hedef:** Kişisel kullanım için, kripto / Forex / XAUUSD (ve veri lisansı elverirse hisse) piyasalarında açıklanabilir analiz, izleme, iki ayrı **sanal işlem** portföyü ve telefon erişimi. **Gerçek emir gönderme ve aracı kurumda otomatik işlem kapsam dışıdır.**

## 0. Temel ilkeler

1. V1 korunur; çalışan modüller test edilerek V2'ye taşınır. Doğrulanmamış V1 modülleri “çalışıyor” diye etiketlenmez.
2. Tek modüler Trade AI 2.0 mimarisi; özellikler aşamalı teslim edilir. V3/V4 diye yeniden inşa yok.
3. Deterministik hesaplama kararın kaynağıdır. GPT yalnızca bağımsız eleştiri ve açıklama sunar; veriyi, fiyatı, pozisyonu veya risk kurallarını değiştiremez.
4. Veriler eksik/eski/çelişkiliyse, belirsizlik yüksekse veya risk sınırı aşılmışsa **NO-TRADE / WAIT**. Sahte canlı fiyat, garantili başarı oranı, uydurma işlem sonucu yok.
5. Stratejiler gerçekçi maliyetlerle geriye ve ileriye dönük test edilmeden güvenilir diye sunulmaz.
6. Yerel Windows PC ana sunucu hedefi; 8 GB RAM, i3-3240, SSD, Windows 10 Home kısıtlarına göre hafif görevler ve kademeli hesaplama.
7. Git güvenliği: `main` korunur, force push yok, üç takip edilmeyen yerel yedek dosya silinmez/üzerine yazılmaz. Üretim ve gerçek kullanıcı geçmişine dokunan testler izole edilmeden çalıştırılmaz.

## 1. V1 envanteri (2026-10-20 GitHub main 50136e1 üzerinden dosya varlığı doğrulandı)

| V1 modülü | Kaynak | V2 yaklaşımı | Not |
| --- | --- | --- | --- |
| Teknik göstergeler | `backend/market_ai/engines/technical.py` | Test edip yeniden kullan / genişlet | EMA, SMA, RSI kodu görüldü; diğer fonksiyonların doğruluğu tam denetlenmedi |
| Çoklu zaman dilimi | `engines/mtf.py` | Yeniden kullan, 1D→4H→1H→15m→5m sözleşmesi | Yönsel bias ile işleme uygunluk ayrımı var |
| Confluence | `engines/confluence.py` | Koruyup Strategy Router'a bağla | Correlation bucket / recency mekanizması mevcut |
| Piyasa analiz çekirdeği | `engines/analysis.py` | Kademeli refaktör | Trend/momentum/hacim skorları var; tamamı test edilmeli |
| Mum ve grafik formasyonları | `engines/candlestick.py`, `chart_patterns.py` | Test et, yeniden kullan | Hesaplama kalitesi henüz onaylı değil |
| Likidite, order flow, futures, liquidation | `engines/liquidity.py`, `order_flow.py`, `futures_positioning.py`, `liquidation.py` | Veriye bağlı yetenek olarak koru | Binance Futures HTTP 451 engeli geçmişte gözlendi |
| Outcome | `engines/outcome.py` | Koruyup genişlet | Aynı OHLC mumunda TP/SL ikisi de görülürse `ambiguous` |
| Market provider | `providers/market_data.py` | Çok sağlayıcılı normalize edilmiş katman | Şu an Binance odaklı; FX/XAU/hisse ayrı gereksinim |
| AI provider | `providers/ai_provider.py` | GPT challenger / anlatım için adapte et | Plus hesabı API kotası sayılmaz; OAuth uygunluğu doğrulanacak |
| Haber provider | `providers/news_provider.py` | Makro takvim + haber sağlayıcı ekle | `NullNewsProvider` var |
| API + mobil arayüz | `backend/server.py`, `frontend/app`, `frontend/src/api/client.ts` | Mevcut iskeleti koru; V2 arayüzü yeniden tasarla | FastAPI / Expo |
| Saklama | `backend/market_ai/models.py`, `db.py` | Tek kullanıcı için SQLite aday; migration kararı test sonrası | V1 MongoDB / BSON kullanıyor |

**Bilinen işler:** Render'da `50136e1` deploy başarısızlığı (kök neden henüz bilinmiyor); fallback senaryo metninde `None` sızıntısı; Codex durum belgesinde eski commit bilgileri; uzak API'ye yazan/silen testler güvenli ortam olmadan çalıştırılmayacak. V1'in tüm algoritmaları için henüz tam denetim yapılmadı.

## 2. Mantıksal V2 bileşenleri

```text
Provider Adapters (crypto/FX/gold/stocks/news/calendar)
  -> Data Normalizer + Timestamp/Session/Contract Rules
  -> Data Quality Gate + Immutable Candle/Event Store
  -> Regime Detector (trend/range/breakout/reversal/unknown)
  -> Strategy Router (market + regime + session + data capability)
  -> Indicator / Structure / SMC / Flow Engines
  -> Evidence Deduplication + Scenario Builder
  -> Risk & Portfolio Gate (can veto)
  -> Immutable Analysis Record + Versioned Decisions
  -> [Manual UI] [Scanner] [Paper Fill Simulator] [Alerts]
  -> GPT Challenger (read-only interpretation; cost gated)
  -> Backtest / Replay / Forward Test / Performance
```

**Ortak sözleşme:** `symbol`, `market_type`, `venue/provider`, `contract_type`, `timeframe`, `bar_open_utc`, `bar_close_utc`, `is_final`, `as_of_utc`, `price_type` (bid/ask/mid/last), `volume_type` (real/tick/unavailable), `quality_flags`, `data_version`. Aynı isimli farklı kontratlar veya spot/futures fiyatları körlemesine birleştirilemez.

**Önemli:** Strategy Router bir “tek gösterge oylaması” değildir. Strateji koşulları, hangi verilerin gerekli olduğu, geçerlilik süresi, önceliği ve çakışma çözümü tanımlıdır. Router'ın `unknown` durumu sinyal üretmez. GPT yeni veri uyduramaz, deterministic gate'i aşamaz.

## 3. Analiz yöntemi kapsamı

- **Trend / momentum:** EMA, SMA, ADX, Supertrend, RSI, MACD, Stochastic RSI, divergence, göreli güç.
- **Market structure / price action:** HH/HL/LH/LL, swing/pivot, BOS, CHoCH, destek/direnç, mum ve grafik formasyonları, false breakout / failed auction.
- **SMC / likidite:** FVG, order blocks, breaker blocks, liquidity sweep, stop hunt, liquidity pools, invalidation; yöntem tanımları açık, objektif ve tekrar üretilebilir olmalı.
- **Hacim / profil:** Volume Profile, POC/VAH/VAL/HVN/LVN, VWAP, Anchored VWAP, Market Profile/TPO; gerçek hacim ve tick volume ayrı etiketlenir.
- **Order flow / futures:** Delta, CVD, delta divergence, absorption/exhaustion, order book/liquidity walls, open interest, funding, liquidation; sadece doğrulanmış destekli piyasalarda. Veri yoksa yöntem unavailable.
- **Volatilite / rejim:** ATR, Bollinger Bands, sıkışma/genişleme, trend/range/breakout/reversal/unknown.
- **Seans / makro:** Asya-Londra-New York high/low, ORB, piyasa saatleri, tatil ve DST, Fed/FOMC, CPI, NFP ve yüksek etkili haber aralıkları.
- **Cross-market:** DXY, US10Y, VIX, endeksler ve korelasyon; zaman hizalaması ve veri erişimi şart.
- **MTF:** 1D bölge, 4H eğilim, 1H setup, 15m tetik, 5m teyit; yalnızca kapanmış mumla karar.
- **Senaryo:** Long/short koşulları, giriş aralığı, invalidation/SL, TP1–3, R:R, setup geçerlilik süresi, karşı senaryo, “bekle” gerekçesi.

Birbirini tekrarlayan göstergeler bağımsız kanıt sayılmaz. Her yöntemin `required_data`, `supported_markets`, `warmup_bars`, `confirmation_policy`, `version`, `tests` tanımı olmalı.

## 4. Kritik özellikler ve tasarım kapıları

1. **Data QC / fail-closed:** UTC, gap, duplicate, out-of-order, stale, incomplete candle, provider divergence; canlı veri yoksa alarm/sinyal üretme. Provider değişimi fiyat tipini veya sembol semantiğini bozmasın.
2. **Capability matrix:** Hangi piyasa/sağlayıcı hangi göstergeye gerçek veri sunuyor? Forex spot'ta merkezi borsa hacmi/OI varmış gibi davranma.
3. **Regime + Strategy Router + conflict resolver:** Birden çok strateji çakışırsa açık öncelik ve `NO-TRADE`; tek bir sinyalin birkaç kez sayılmasını engelle.
4. **Risk & portfolio veto:** Stop bazlı sanal pozisyon boyutu, toplam eşzamanlı risk, günlük sanal zarar limiti, korelasyon, seans/haber filtresi; ayrı demo hesaplar.
5. **Paper execution simulator:** Bid/ask, spread, fee, slippage, gecikme, minimum lot, contract multiplier, FX pip/altın birimleri, emir yaşam döngüsü; gelecekteki fiyattan geçmişe emir doldurma yok. OHLC içi TP/SL sırası belirsizse `ambiguous`.
6. **Immutable decision & reproducibility:** Sinyal üretildiği andaki fiyat/veri kaynağı/sürüm/parametre/kanıt/gate sonucu korunur; reanaliz ayrı versiyon olarak kaydedilir.
7. **Backtest, replay, walk-forward:** Lookahead leakage testleri, bağımsız dönem, masraf ve veri boşluğu simülasyonu, strateji seçimi yanlılığı; ileriye dönük demo takip.
8. **Performance & drift:** Win-rate tek başına yeterli değil; expectancy, max drawdown, R-multiple, kalibrasyon, piyasa/seans/rejim kırılımı, yöntem ve router sürümlerinin karşılaştırılması.
9. **Scanner + scheduler:** Kapanmış mum olayına göre çalış; açık sanal pozisyonlara öncelik, idempotent işler, dayanıklı görev durumu, yeniden başlatma sonrası catch-up; i3/8GB için CPU/RAM/istek/GPT bütçesi.
10. **Alert reliability:** De-dup, teslim denemesi, cooldown, önem seviyesi, stale alert engeli, bildirim test merkezi, kullanıcıya görünür geçmiş.
11. **GPT challenger:** Yapılandırılmış kanıtla bağımsız itiraz, uyuşmazlık, sürüm ve maliyet kaydı; haber metinlerindeki prompt injection'a karşı koruma; GPT yoksa deterministik sistem çalışır.
12. **System health / safety:** Sağlayıcı sağlığı, analiz gecikmesi, görev kuyruğu, depolama, kaynak tüketimi, emergency pause; backup + restore testi.
13. **Security:** Windows 10 Home destek ömrü riski; internete açık port forwarding yerine özel ağ/tünel; cihaz kimlik doğrulaması, secrets env/OS secret store, güvenli güncelleme.
14. **UI:** Tek ANALYZE, etiketli grafik, watchlist, veri tazeliği, router seçimi/gerekçe, kanıt-çelişki, iki sanal portföy, analiz geçmişi, performans, GPT sohbet, alarmlar, sistem durumu.
15. **Recovery:** Windows oturum açılmadan otomatik servis başlatma; elektrik geri geldiğinde PC'nin kendiliğinden açılması ayrı BIOS/donanım meselesidir ve **ertelendi**. Açıldıktan sonra SQLite/queue durumunu geri yükle, kaçırılan mumları kontrol et, duplicate paper fills üretme.

## 5. Test ve kabul kriterleri

- [ ] Aynı kapalı mumlar + aynı strateji/parametre sürümü => aynı deterministik sonuç.
- [ ] Kapanmamış/eksik/eski mum => sinyal yok; sebebi kaydedilir.
- [ ] BTC spot / BTC perpetual ve FX bid/ask fiyatları birbirine karıştırılmaz.
- [ ] Forex'te gerçek order book yoksa CVD/OI uydurulmaz; yetenek devre dışı görünür.
- [ ] Trend/range/unknown için router seçimleri test edilir; iki strateji çakışırsa sonuç deterministiktir.
- [ ] Yanlış SL/TP geometrisi veya portföy risk sınırı => işlem senaryosu reddedilir.
- [ ] Aynı olay iki kez işlenirse ikinci sanal emir/uyarı oluşmaz.
- [ ] Aynı OHLC mumunda TP ve SL => bilinmeyen sıra için `ambiguous`; sonuç “win”e zorlanmaz.
- [ ] Backtest, gelecekte kapanacak mumları ve henüz yayımlanmamış haberleri kullanamaz.
- [ ] Geriye dönük performans, forward testten açıkça ayrı raporlanır; istatistiksel olarak kanıtlanmamış `confidence` olasılık diye gösterilmez.
- [ ] GPT yanıtı deterministik karar, gerçek veri, hesap bakiyesi veya sanal emir durumunu değiştiremez.
- [ ] Uygulama kapatılıp yeniden açılınca analiz/sanal pozisyon/geçmiş korunur; tekrar doldurma olmaz.
- [ ] Üretim veya kullanıcı verisine dokunan entegrasyon testleri izole ortamda çalışır.
- [ ] UI üzerinde unavailable data, haber filtresi, no-trade ve stale durumu açık görünür.

## 6. Teslim sırası (tek V2, aşamalı)

| Aşama | Çıktı | Tamamlanma koşulu |
| --- | --- | --- |
| **M0 — Envanter / tasarım** | V1 fonksiyon matrisi, risk listesi, mimari, veri sağlayıcı adayları | Test edilecek modüller ve provider yetenekleri belgeli |
| **M1 — Data foundation** | Normalize edilmiş market data, QC, kalıcı mumlar, kaynak health | Stale/gap/closed-candle testleri yeşil |
| **M2 — Deterministik analiz** | Rejim, Router, SMC/TA/MTF, confluence, risk/no-trade | Sabit fixture'larda tekrar üretilebilir karar |
| **M3 — Test & paper engine** | Backtest/replay, forward test, iki ayrı demo portföyü | Spread/slippage/ambiguous/idempotency testleri yeşil |
| **M4 — Scanner / GPT / alerts** | Dayanıklı görevler, haber filtresi, GPT challenger, bildirim | Offline/restart/duplicate/AI-failure testleri yeşil |
| **M5 — UI / local ops** | Mobil uyumlu dashboard, Windows service, özel ağ erişimi, backup | Telefon erişimi + reboot/recovery + backup/restore testi |
| **M6 — Stabilizasyon** | Performans, gözlem, güvenlik ve regression raporu | Pilot demo izleme ve kabul kontrol listesi tamam |

**M0 başlamıştır:** GitHub V1 dosya ağacı ve seçili modüller okundu. Kod, test, dağıtım ve gerçek veri değiştirilmedi.

## 7. İş bölümü ve sınırlar

- **Asistan:** mimari, kapsam, inceleme, entegrasyon sözleşmeleri, test ve milestone denetimi.
- **Codex:** küçük, izole backend/test/refaktör görevleri; her görevde beklenen dosyalar, testler, değişmezler belirtilir.
- **Emergent:** ayrı UI prototipi; API sözleşmesine uyar, gerçek işlem entegrasyonu veya canlı veri uydurmaz; krediler kontrollü kullanılır.
- **Kullanıcı:** gerektikçe veri sağlayıcısı, maliyet, erişim ve arayüz tercihlerini onaylar.

**Henüz kesinleşmeyen kararlar:** FX/XAU/hisse veri sağlayıcısı ve lisansı; MongoDB→SQLite göç stratejisi; Expo push mekanizması; GPT API/OAuth uygunluğu ve maliyeti; Windows 10 güvenli işletim/güncelleme; Render V1 deploy hatasının kök nedeni. ChatGPT Plus üyeliği üçüncü taraf API erişimi garantilemez.

## 8. Hemen sonraki teknik iş (M0.1)

1. `backend/market_ai/engines/` içindeki tüm fonksiyonları, girdileri, çıktıları, veri bağımlılıklarını ve test durumlarını listele.
2. Her yöntemi **koru / refaktör / yeni geliştir / veri yoksa unavailable** şeklinde sınıflandır.
3. `server.py` ve provider sınırlarını denetle; `None` fallback hatasını izole fixture ile belgeleyip sonra düzelt.
4. Veri sözleşmesi ve Strategy Router arayüzünü önce test-fixture üzerinden tasarla.
5. M0 raporunu güncelle, ardından M1 koduna başla; üretime deploy yok.

## 9. Referanslar

- [Freqtrade — lookahead analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/)
- [TradingView — strategy simulation](https://www.tradingview.com/pine-script-docs/concepts/strategies/)
- [CCXT — manual](https://docs.ccxt.com/docs/manual)
- [MetaTrader 5 Python bar data](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py)
- [Binance developer docs](https://developers.binance.com/en/docs/introduction)
- [Backtest overfitting — Bailey et al.](https://papers.ssrn.com/sol3/Papers.cfm?abstract_id=2326253)

Bu belge planlanan özellikleri kapsar; uygulandıkları veya doğruluklarının kanıtlandığı anlamına gelmez.

## Uygulama checkpoint'i — 2026-10-20

`4ad3aa6` itibarıyla izole QC→rejim→Router→teknik adaptör, sürümlü immutable snapshot/provenance, explicit policy ile paper risk veto, yalnız yeni test DB'sinde append-only kayıt/backup/restore prototipi ve tek snapshot replay doğrulandı. 126 V2 testi Ubuntu/Windows CI'da, ek 9 saf outcome regresyonu yerelde başarılı. Üretim API'sine bağlantı, migration veya gerçek işlem yoktur. Tüm M1/M2 veya M3 tamamlandı anlamına gelmez; güncel sınırlar ve sıradaki işler `V2_IMPLEMENTATION_STATE.md`, aşama/CI kanıtları `V2_PROGRESS_LOG.md` içindedir.
