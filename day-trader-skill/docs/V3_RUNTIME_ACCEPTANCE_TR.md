# V3 Windows runtime kabulü

11 Kasım 2026, Europe/Istanbul. Başlangıç HEAD `806ed902ba76d87523047d43eef396491b462cbb`, dal `codex/v3-real-readonly-analysis`, temiz çalışma ağacı. P1 `753ed59` ancestry doğrulandı. Bu teslim üretim motorunu değiştirmez; opt-in QA araçları ve kabul belgeleri ekler. Son HEAD bu dosyaları içeren yerel teslim commitidir; tam SHA son kullanıcı raporunda verilir.

## Sonuçlar

| Alan | Sonuç | Sınır |
|---|---|---|
| P1 ana kaynak | YES | `753ed59` ana dalın atası. |
| Güncel izole backend | YES / EXACT_VERSION_VERIFIED | Ana kaynaklardan yeni süreç, izole Python 3.11.9 ve 3.13.15, NumPy 2.2.6; gerçek loopback HTTP kabulü. Test sonunda yalnız kendi süreçleri kapatıldı. |
| Mevcut 8006 | VERSION_UNVERIFIED | PID 7532, başlangıç 11 Kasım 2026 15:30:28, global Python 3.11, `forex.api:app`, reload bayrağı yok. Belleğe yüklenmiş P1 modül sürümü ve chart config bağımsız teyit edilmedi. |
| P1 gerçek HTTP yanıtı | YES, fixture ortamında | Double Top/Bottom ve pinli candlestick bağlamı serileştirildi. Canlı broker yanıtında chart alanı null; canlı P1 kabulü PARTIAL. |
| PWA sözleşmesi | PARTIAL | İstek ve ek alanlara tolerans var; dört sembollü analiz ve betimleyici/hypothetical plan gösterimi eksik. |
| Gerçek veri ön kontrolü | PASS, analiz planı kabulü BLOCKED | REAL/Exness-MT5Real50/USC ve dört exact `c` alias; seans güveni eksik. |

## Mevcut süreç incelemesi

Başlangıç port/PID: 5173/10320, 8005/2840, 8006/7532, 8007/9724. Bu görev bu süreçleri durdurmadı veya yeniden başlatmadı. Son gözlemde ilk üç süreç aynı kalırken 8007 PID 12152 ve listen zamanı 15:58:52 oldu. Aynı dönemde `news_bridge.py` ve `src/NewsPanel.tsx` hash'leri değişti; bu görev bunlara yazmadı veya haber sürecini yönetmedi. Bu dış eşzamanlı değişiklik nedeniyle bütün servis/dosyaların değişmeden kaldığı iddia edilmez. Analiz paneli ve MT5 bridge hash'leri aynı kaldı. Yalnız executable, başlangıç zamanı, tanınan uygulama modülü ve reload bayrağı kaydedildi; tam komut satırı, hesap numarası, token veya parola kaydedilmedi. 8006 executable: `%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe`. Başlangıç modülü komut satırında `forex.api:app`; çalışan modülün kesin dosya yolu / yüklenen kod objeleri mevcut public API ile belirlenemiyor. Ek process-cwd yardımcısı `psutil` kurulu değildi; global pakete kurulum yapılmadı.

8006 `/openapi.json` HTTP 200, uygulama sürümü 0.2.0, V1/V5 yolları mevcut. Şema SHA256: `c6f59f0abf8a7d5807dda7e60a9ba384fcc07e1ba10253686df07a0164625bc9`. Manuel V5 yanıtındaki `public_code_sha256`, güncel diskteki `e31b9f0a8b3759f53401d3df191dbe663017904ee0575db4b746610a5f172c31` ile eşleşiyor. Ancak `public_code_digest()` dosya baytlarını okur ve ilk kullanımda cache'ler; bellekteki fonksiyonların commit kimliğini kanıtlamaz. Şema da chart adapter sürümünü ayırt etmez. Bu yüzden EXACT_VERSION_VERIFIED veya OLD_VERSION denmedi. Public API'ye tanılama endpoint'i eklenmedi. İzole süreç için başlangıç manifesti yalnız yerel QA çıktısına yazılır.

## Gerçek MT5 ön kontrolü

Mevcut bağlı terminale yalnız IPC attach yapıldı; login/logout, kimlik bilgisi, hesap değişimi, symbol_select, emir kontrolü/gönderimi yok. Ön kontrol okuma yetenekleri allowlist ile sınırlandı. REAL balance okunup sermaye yapılmadı veya kaydedilmedi. Dahili hesap kimliği, mod, server ve currency canlı analizden önce/sonra bellekte karşılaştırıldı; aynı kaldı, identifier rapora yazılmadı.

`REAL_READONLY_DATA`, `Exness-MT5Real50`, `USC` exact preflight PASS; balance null. XAUUSDc/EURUSDc/GBPUSDc/USDJPYc için metadata, taze bid/ask ve quote zamanı; her sembolde 220 kapanmış M15 ve 220 kapanmış H4 bar okundu. Bu sayı session-gap doğrulaması değildir.

| Alias | Kontrat | Tick size | Tick value (USC; anlık) | Lot min / max / step |
|---|---:|---:|---:|---|
| XAUUSDc | 1 | 0.001 | 0.1 | 0.01 / 200 / 0.01 |
| EURUSDc | 1000 | 0.00001 | 1 | 0.01 / 200 / 0.01 |
| GBPUSDc | 1000 | 0.00001 | 1 | 0.01 / 200 / 0.01 |
| USDJPYc | 1000 | 0.001 | yaklaşık 0.62823 | 0.01 / 200 / 0.01 |

Mevcut 8006 metadata dört sembolde `broker_hours_status=UNVERIFIED_REAL_SESSION`, `max_spread=null`, `market_type=unverified`, `contract_type=unverified` veriyor. Trade mode gözlem anında 4; bu, tarihsel CLOSE_ONLY durumunu veya execution iznini kanıtlamaz. Yeni plan kabulünden önce seans ve uygun instrument/spread sözleşmesi ayrıca gerekir.

Manuel 8006 V5 isteği: kullanıcıdan verilen varsayımsal 2500 USC, risk %1. Sonuç HTTP 200; `INSUFFICIENT_DATA`, `DATA_UNAVAILABLE`, `BLOCKED`; gerekçe `missing candle without verified broker hours`; `market_data_account_mode=REAL`, `risk_balance_source=HYPOTHETICAL_CAPITAL`, `execution_permission=false`, lot/risk null. Gerçek bakiye kullanılmadı. Fixture başarısı bu canlı engeli geçersiz kılmaz.

## Tarihsel seans kanıtı

Terminalden 9 Kasım 2026 21:45-23:20 UTC aralığı yeniden salt okunur alındı. M1: 34 kayıt, 21:57'den 23:00'a 3780 saniye açılış farkı. M15: 3 kayıt, 21:45'ten 23:00'a 4500 saniye açılış farkı. Bunlar gözlemdir; aralığın broker tarafından meşru kapalı olduğunu veya eksik veri olmadığını ispatlamaz. Önceki 23:00:30.141 / 23:01:00.199 / 23:02:00.115 tick kayıtları belgelerdeki önceki gözlem olarak incelendi, yeni tick geçmişiymiş gibi sunulmadı.

Mevcut `forex/session_evidence.py` importer yalnız `MT5_CURRENT_WEEKLY_SCHEDULE` alır; `historical_gap_authorized=false`, `effective_period=null`. `tools/mt5_session_export/MT5SessionExport.mq5` quote/trade haftalık pencerelerini verir; çalıştırılmadı. Terminal klasöründe `session_evidence_v1.json` bulunamadı. Yeni haftalık çıktı geçmiş DST/holiday kanıtı olamaz.

[Exness enstrüman saatleri](https://get.exness.help/hc/en-us/articles/4405235684498-Instrument-trading-hours) ve [1 Kasım 2026 DST duyurusu](https://get.exness.help/hc/en-us/articles/31342732737180-Trading-Hours-Update-End-of-US-Daylight-Saving-Time-01-Nov-2026) tekrar incelendi. Duyuru XAUUSD için kış saatlerini verir; exact XAUUSDc/sunucu/tarih quote kapsamını kanıtlamaz. XAUUSD çizelgesi XAUUSDc'ye uygulanmadı. **XAUUSDc 9 Kasım tarihsel seans engeli devam eder.**

## Kanıt ve korunma

İzole HTTP matrisi ve test sayıları `V3_ISOLATED_API_TESTS.md`; P1 değişmezlikleri `V3_P1_API_ACCEPTANCE.md`; güncel frontend bulguları `V3_PWA_INTEGRATION_HANDOFF.md`; uygulanabilir sonraki operasyon `V3_RUNTIME_CUTOVER_PLAN.md` içindedir. Ham, sanitize edilmiş artefaktlar `%TEMP%\trade-ai-runtime-acceptance-20261111` altındadır; temp kalıcı arşiv değildir.

V2 HEAD `c80c97f227a2c233a610df669919ba2f464e4f9f`; chart SHA256 `af69112c91938c4bd6fea3d16f43a333f63c35ea3715ed082069868e1018f1ba`. Önceden var olan V2 kirli dosyaları korundu. P1 dalı/HEAD değişmedi. PWA, MT5 bridge, haber, V5 üretim motoru ve global paketler değiştirilmedi. Push, Actions, merge, reset veya emir yok.
