# Trade AI 2.0 — uygulama durumu

**Master continuation / M7–M13:** PR6 `4ae1fdc` üzerinden yeni
`codex/trade-ai-v2-master-continuation`, [Draft PR #7](https://github.com/FatihBirgul/trade-ai/pull/7).
Gerçek chronological train/select/freeze/OOS; dataset manifest/bounded capture;
Hikkake ve dört ek family ID; causal chart knowledge/range events; restrictive
versioned research profiles ve CLI'ler eklendi. Son kod4c97f4f, yerel381V2
(334korunan+47yeni),11quote/outcome,Gateway42; OpenAPI26/34 eşit. Kalan P0/P1/P2
NEXT_ACTIONS'ta; API/mobile selector,flags/pennants ve tam parametre optimizer eksik.
Public360bar source kontrolleri geçti;0training sample nedeniyle OOS0,trust
INCOMPLETE. Synthetic OOS market/forward kanıtı değildir. Financial math/limit,
production/Android/Gateway/private-network/auto-paper değişikliği yok. Nihai HEAD
CI sonucu PR7 checks'ten doğrulanır; eski checkpoint ile karıştırılmaz.

**31 Ekim 2026 / Master P0 ilk teslimat:** Task13 `980340d` üzerinden
`codex/trade-ai-v2-master-development`, [Draft PR #6](https://github.com/FatihBirgul/trade-ai/pull/6).
Mevcut V2 korunur. Versioned pattern research (legacy yeniden kullanım +15ek family),
6ek teknik yöntem, causal MTF aggregation ve mevcut paper ledger/audit ile bounded
historical research eklendi. Yeni analizversion3 mevcut technical_methods sözlüğüne
salt açıklayıcı research_context ekler; direction/levels/risk gate aynı kalır.
Gerçek Task13 auditor TP1/TP2 numeric-string yanlış pozitifi düzeltildi; ledger
math/ID/hash değişmedi. Yerel334V2 (285korunan+49yeni),11quote/outcome,Gateway42;
son kod b172ce8. M5 dört OS/Python CI333test success; final334HEAD PR checks'te
ayrı doğrulanır. Public300bar QC/diagnostic smoke var; gerçek market kârlılığı,
OOS/forward, cihaz/deploy doğrulaması yok. API26path/34schema eşit.
[Envanter](TRADE_AI_V2_FEATURE_INVENTORY.md), [yaşayan görev](TRADE_AI_V2_MASTER_MISSION.md),
[ilerleme](TRADE_AI_V2_MASTER_PROGRESS.md), [doğrulama](TRADE_AI_V2_VALIDATION_MATRIX.md),
[devam noktası](TRADE_AI_V2_NEXT_ACTIONS.md). Bütün master aşamaları bitmedi.

**31 Ekim 2026 / Görev 13:** Görev 12 `02152e9` üzerinden
`codex/task13-domain-event-journal`. Opt-in extension v1; aynı SQLite transaction'ında
sürümlü append-only domain kayıtları, command preimage ve control/TP/stop kanıtı.
Bağımsız domain oracle; explicit copy migration, legacy boundary INCOMPLETE.
Gerçek ambiguous manuel kısmi çıkış receipt eksikliği düzeltildi; geçmiş hash'ler korunur.
Yerel 285 V2 + 11 quote/outcome + Gateway 42 geçti. f3ba82e için Windows/Ubuntu ×
Python3.11/3.12 dört CI ve PR quote iki CI başarılı. Eşlenik seed12 koşusunda finansal
sonuçlar aynı; 5.750 domain event, mismatch/error0, legacy282/new0 INCOMPLETE.
Bu tam strateji/risk replay veya üretim performansı iddiası değildir. API26path/34schema
eşit; production/Android/Gateway değişikliği yok. [Draft PR#5](https://github.com/FatihBirgul/trade-ai/pull/5),
[rapor/kullanım/sınırlar](TASK13_DOMAIN_EVENT_JOURNAL.md), [ölçüm](TASK13_SOAK_METRICS.json).

**31 Ekim 2026 / Görev 12:** Görev 11 f690a13 üzerinden
`codex/task12-ledger-replay-audit`. Bağımsız salt okunur accounting replay + CLI,
24 bozuk veri/read-only/oracle regresyonu ve iki bounded soak testi eklendi.
253 V2 + 11 quote/outcome; Gateway 42 yerel test başarılı. 935 mum/50 journal,
63 audit, 4 restart, 3 kontrollü SQLite arızası, 720 dakika scanner recovery ve
backup/restore: finansal mismatch/beklenmeyen hata 0. İptal/stop control timeline
sınırları INCOMPLETE; tam execution replay iddiası yok. 056015d için dört
Windows/Ubuntu × Python 3.11/3.12 CI başarılı. API ve canlı DB değişmedi.
[Kullanım ve kanıt](TASK12_LEDGER_REPLAY_AUDIT.md),
[retention tasarımı](TASK12_RETENTION_DESIGN.md). Sonraki öncelik sürümlü control
journal ve ardından archive read/restore zinciri; otomatik silme etkin değil.


**31 Ekim 2026 / Görev 11:** `codex/task11-paper-integrity-20261031`, b6066bf
üzerinden. Kısmi TP1 sonrası manuel azaltmada mum işleme engeli, API finansal
projeksiyonlarında Decimal context bağımlılığı ve para biçimleyicide negatif sıfır/
yuvarlama düzeltildi. Yerel 227 V2 + 2 quote + 9 outcome; Gateway 42 test geçti.
API şeması korunur. Ayrıntılar: [Görev 11 denetimi](TASK11_PAPER_INTEGRITY.md).
GitHub CI kanıtı progress log içinde ayrıca kaydedilir.

**29 Ekim 2026 entegrasyon notu:** `codex/v2-android-integration-20261029`
dalında tracking 422 OpenAPI açıklaması sabitlendi ve Windows backup testindeki
açık SQLite bağlantısı kapatıldı. İzole V2 suite 220/220, Gateway'in geçici
fixture Backend entegrasyonu 42/42 geçti. Çalışan servisler güncellenmedi;
telefon ve Backend içinden canlı piyasa provider çağrısı doğrulanmadı.

**Güncelleme:** 2026-10-21
**Dal:** `trade-ai-v2` — `main` korunur.  
**Uygulama ilkesi:** Her küçük milestone kendi izole testleriyle doğrulanır; test sonuçları GitHub Actions'tan teyit edilmeden tamamlandı denmez.

## Güncel ikinci geliştirme görevi — 2026-10-21

- Başlangıç uzak HEAD `172dcca2584b27a4643165585ebaee96b1f900ff`; daha yeni commit yoktu. GitHub bağlantısıyla alınan sabit snapshot'tan geliştirme; normal fast-forward API ref update kullanılacak, main/Render/user DB/yedekler kapsam dışı.
- Dört etkin strateji: continuation (mevcut id korunarak v2), range mean reversion, confirmed breakout, failed breakout/sweep. Strateji bazlı objektif teyit/invalidation/warm-up/WAIT/sürüm; zıt yön çatışması priority'den önce veto. Mevcut trend composite/Confluence ve ortak risk limitleri korunur.
- Yeni `price_action.py`: causal FVG, teyit gecikmeli BOS/CHoCH, sweep ve gerçek hacimli rolling typical-price VWAP. FVG oluşum eşiği gelecekteki ATR ile yeniden yazılmaz. FVG/BOS/sweep aynı kanıt kovasıdır. Session/Anchored VWAP veya gerçek kurumsal emir iddiası yoktur.
- API `technical_methods` ve `strategy_setups` alanlarıyla geriye uyumlu genişledi; aynı 23 path / 25 operation. OpenAPI ve fixture örnekleri actual backend'den üretilir. Yeni setup'larda farklı TF'nin zıt kanıtı WAIT; spot short risk kapısı hâlâ unavailable.
- Binance exact historical 1m windows: symbol/tick başına 300 kapalı bar, birden çok tick ile >5 saat toparlama. 12 saat/restart/idempotency/eksik geçmiş/outage/stale/source/rollback testleri eklendi. Tamamlanmadıysa görünür PAPER_RECOVERY_IN_PROGRESS; geçmiş yoksa fiyat üretmeden bekler.
- Read-only SQLite backup/restore yeni dosyaya, integrity/projection/record hash doğrulaması; Windows manuel launcher, env örneği, 2 MB × 4 dosya log sınırı ve özel ağ tasarımı hazır. Gerçek PC/telefon/servis kurulmadı.
- Emergent için `V2_EMERGENT_HANDOFF.md`, API contract, OpenAPI ve confirmed fixture senaryoları hazır. Test ve commit/CI kanıtının son hali `V2_PROGRESS_LOG.md` içindedir.
- Henüz yok: ek yedi analiz yöntemi (Order Blocks/ADX/Supertrend/Anchored VWAP/session/ORB/compression), multi-period backtest/istatistiksel kârlılık, FX/XAU, GPT/bildirim teslimi, UI/BFF/telefon/Windows service. History/outbox retention yoktur. Hedef PC üzerinde kaynak/performance ölçülmedi.

### Son doğrulanan yeni kod checkpoint'i

**`207f2bec67c2eb7117fa48f73b36c203f2d079ae`**, [Actions 39547404990](https://github.com/FatihBirgul/trade-ai/actions/runs/39547404990): Windows ve Ubuntu **success**, her OS'ta **211 V2 + 9 seçili V1 outcome**, compile ve Windows launcher syntax doğrulandı. Yerel 211/211 ve loopback HTTP/restart başarılı. Bu oturumdaki live probe proxy transport unavailable nedeniyle HTTP 200 WAIT/exit 2'dir; canlı Binance bağlantısı başarılı diye sunulmaz. Sonraki docs-only commit bu kanıtı kaydeder.

## Önceki doğrulanan ürün çekirdeği — 172dcca baseline

- Standalone FastAPI: `backend/start_v2.py`, yalnız 127.0.0.1:8002; zorunlu bearer token ve ayrı V2 DB. MongoDB/AI importu yok. Aynı `/api/v2` router V1'e yalnız `V2_DB_PATH` ile opt-in takılabilir.
- Health/markets/analyze/history/detail, AUTO/MANUAL portföy/pozisyon/emir/journal/performance ve risk kontrollü pending order/cancel/queued close/pause/paper poll çalışıyor. Tam sözleşme: `V2_FRONTEND_API_CONTRACT.md`, `V2_OPENAPI.json`, `v2_examples/`.
- Mevcut QC/regime/router/technical/MTF/Confluence/paper_risk modülleri entegre; MTF source/instrument/as-of/epoch hizası ve current-evidence double counting kontrol edilir. WAIT seviyeleri null, TP3 unavailable. Risk hesabı seçimi `risk_portfolio` ile hesaplar arasında bağımsızdır.
- V2-only SQLite product tabloları: immutable analiz/komut/olay/journal + atomik, checksum'lı bakiye/order/position projection'ları. Mode DB'de sabit; foreign/prototype DB migration yok. `paper_only=true`; live yalnız piyasa verisi modudur.
- Sonraki kapalı 1m bar modeliyle partial/full fill, queued partial/full close, TP1/TP2/SL, fee/spread/slippage, cancel/expiry/ambiguous, idempotency, AUTO closed-bar dedup ve restart/rollback çalışıyor. Eski mark'tan anında close yok; gerçek order gateway yok.
- Çekirdek checkpoint `99be5dc`: **161 V2 + 9 seçili V1 outcome** ve compile, [Windows/Ubuntu CI success](https://github.com/FatihBirgul/trade-ai/actions/runs/39505521204). Kısmi stop kalan miktarı exit_pending olarak korur; çözülmeden resume olmaz.
- Kalıcı watchlist, bounded scanner tick/jobs, 120 saniye lease, restart/dedup, güvenli pause ve pending notification outbox eklendi. `--scanner` ile tek 60 saniye thread opt-in; default paused/auto_paper=false. Yeni checkpoint test/CI sonucu progress log'da kaydedilir.
- Son doğrulanan kod checkpoint'i **`ddd3a2e0f2a95c4e510756dcacd191fc7fbaa09d`**: [Windows/Ubuntu CI success](https://github.com/FatihBirgul/trade-ai/actions/runs/39507706156), iki OS'ta **180 V2 + 9 seçili V1** ve compile geçti. Gerçek loopback HTTP/chart/restart ve ayrı public live probe scriptleri/raporları başarılı; live QC geçti, gerekçeli WAIT, AUTO=0. Sonraki yalnız belge commit'i bu kanıtı kaydeder.
- Ayrı live public smoke: `V2_LIVE_SMOKE_REPORT.json`; BTCUSDT 300 final bar/TF, 15m/1H/4H QC başarılı, HTTP 200 gerekçeli WAIT, SQLite readback eşit, AUTO order=0, real_execution=false.
- Grafik için `GET /api/v2/analyses/{analysis_id}/candles` eklendi: aynı immutable analiz snapshot'ı, source integrity, quality kapısı, timeframe/limit ve açık tarihsel/fixture etiketi. Yeni provider isteği yok. **23 path / 25 GET-POST işlemi** OpenAPI ve frontend sözleşmesinde uygulanmış olarak kayıtlıdır.
- Hâlâ yok: uzun dönem backtest, gerçek order-book execution, başka venue fallback, notification delivery/GPT, FX/XAU, UI/telefon/Windows service. Main/Render/user DB/yedekler korunur. Aşağıdaki 2026-10-20 checkpoint'leri tarihsel baseline'dır.

## Gerçekleştirilenler

- V1 analiz modüllerinin GitHub üzerinden fonksiyon envanteri ve göç riskleri: `docs/V2_M0_AUDIT.md`.
- Tek mimari ve teslim kapsamı: `docs/TRADE_AI_2_MASTER_PLAN.md`.
- `backend/market_ai/v2/data_quality.py`: kapanmış mum, zaman sırası, gap, fiyat, hacim, stale/future kalite kapısı.
- `backend/market_ai/v2/strategy_router.py`: rejim/piyasa/seans/veri-yeteneği uyumlu, eşit öncelikte WAIT veren izole strateji seçici.
- `backend/market_ai/v2/market_data_contract.py`: kaynak, piyasa ve kontrat ayrımı; Binance spot inclusive close -> exclusive close normalizasyonu.
- `backend/market_ai/v2/regime.py`: kapanmış fiyat dizisinden deterministik trend/range/breakout/unknown sınıflandırması.
- `backend/market_ai/v2/capabilities.py`: doğrulanmış mumlardan OHLC/real-volume/tick-volume yetenekleri; mumlardan order book/OI/funding yeteneği çıkarılmaz.
- `backend/market_ai/v2/pipeline.py`: QC → yetenek → rejim → Router izole akışı; sürüm ve replay zamanı sonuçta tutulur. Hatalı batch bütünüyle WAIT; risk veto ve eşit öncelik çatışması korunur.
- `backend/market_ai/v2/narrative.py`: doğrulanmamış seviyeleri kullanıcıya `None` diye yazmayan senaryo metinleri.
- `backend/server.py` fallback anlatımı güvenli senaryo modülünü çağırır.
- `backend/market_ai/v2/technical_adapter.py`: QC sonrası gerçek hacimli kripto mumlarıyla V1 teknik motorunu kullanır; warm-up eksikleri açık, snapshot JSON kopyası değiştirilemez. Tick/eksik hacim için bu ilk birleşik OHLCV adaptörü unavailable verir.
- V1 teknik/MTF/Confluence offline referans testleri eklendi; RSI zero-loss/flat ve Confluence sıralama/nonfinite hataları V2 dalında düzeltildi. Ayrıntılı aşama kayıtları: `docs/V2_PROGRESS_LOG.md`.
- `backend/market_ai/v2/paper_risk.py`: açık politika ve aynı para birimindeki linear kripto kontratı için geometri/RR/maliyet, toplam/grup/günlük risk, nakit/notional, miktar adımı ve iki demo hesabı ayrımı. Yalnız uygunluk/miktar sonucu; bakiye değişikliği veya emir yok.
- `backend/market_ai/v2/decision_record.py`: mum/config/strateji/engine sürümleri ve parametreleriyle immutable, içerik hash'li analiz ve paper-risk kayıtları. Risk girdisi aynı record ID/instrument/as-of ile bağlanır; değişen snapshot/version yeni kayıt üretir.
- `replay_analysis`: kaydedilmiş snapshot'ı orijinal as-of/parametrelerle offline yeniden hesaplar; aynı ID'yi doğrular. Bozuk kayıt, desteklenmeyen engine sürümü veya nonfinite diagnostic etiketleriyle replay unavailable verir.
- `backend/market_ai/v2/record_store.py`: yalnız açıkça seçilen yeni dosya için append-only SQLite prototipi; ID bazlı tekrar önleme, bütünlük, yeniden açma ve backup/restore testleri. Yalnız geçici test DB'lerinde çalıştırıldı; MongoDB göç kararı veya kullanıcı verisi taşınması değildir.
- `backend/tests/test_v2_*.py`: offline unit/contract testleri; teknik motor testleri için yalnız NumPy/Pandas gerekir. Ağ/DB/gerçek portföy yok.
- `.github/workflows/v2-unit.yml`: `trade-ai-v2` push'larında Python 3.11 syntax kontrolü ve izole testler.
- CI testleri Ubuntu ve Windows'ta, minimum sabit numerik bağımlılıklarla çalışır; SQLite connection ResourceWarning'leri hata sayılır. Gerçek provider/API testleri bu workflow'a dahil değildir.
- `backend/tests/run_v2_offline_tests.py`: V2 allowlist, socket/DNS engeli ve yalnız kendi geçici kökünde SQLite bağlantısı. Varsayılan tüm pytest koleksiyonu güvenli sayılmaz; eski uzak testler bu runner'a dahil edilmez.

## Sınırlar ve açık işler

- Standalone V2 API ve V1'e opt-in router vardır. Varsayılan V1 endpoint'leri/üretim deploy'u değişmez; tüm V1 ürününün taşındığı anlamına gelmez.
- Mevcut V1 için tüm regresyon testleri çalıştırılmadı; bazı eski testler varsayılan uzak endpoint'e çağrı yapar.
- Forex/XAUUSD, takvim/DST/news, çok dönemli backtest, GPT/UI/telefon/service ve bildirim gönderimi henüz yok. İlk kapalı-bar paper lifecycle ve bounded scanner vardır; tick hassasiyeti veya gerçek borsa execution doğruluğu iddiası yoktur.
- `main` ve Render deploy değiştirilmedi; kullanıcıya ait yerel yedek dosyalara erişilmedi veya dokunulmadı.
- Güncel GitHub Actions sonuçları, ilgili commit'in `Actions` sekmesinden doğrulanmalıdır.

## Sonraki teknik sıra

1. Emergent UI'yi çalışan `V2_FRONTEND_API_CONTRACT.md`/OpenAPI üzerinden bağla; fixture ve stale/WAIT rozetlerini koru.
2. Eklenen paged recovery için kullanıcı PC pilotu; history retention ve uzun dönem offline backtest/walk-forward ekle. Kârlılık veya olasılık doğrulanmış değildir.
3. SMC/zone fixture kapsamını genişlet; ayrı order-book/news feed olmadan yeni capability uydurma.
4. FX/XAU doğrulanmış sağlayıcı/lisans/takvim; telefon/private-network erişimi ve bildirim servisi için ayrıca kapsam/izin belirle. Gerçek migration/üretim deploy varsayılmaz.

## Başarı tanımı

M0 kaynak envanteri tamamlandı. M1 veri temeli ve M2 strateji seçicinin **ilk izole bileşenleri** oluşturuldu; tüm M1/M2 kapsamı tamamlanmadı.

## Son doğrulanan geliştirme checkpoint'i — 2026-10-20

| Alan | Kanıt |
| --- | --- |
| Kod checkpoint'i | `4ad3aa659a3763513d66e01c51594d0407069259` |
| Yerel test | 126 V2 offline test, 9 mevcut saf outcome regresyonu ve backend compile başarılı |
| CI | [Actions 39470520485](https://github.com/FatihBirgul/trade-ai/actions/runs/39470520485): Ubuntu ve Windows Python 3.11 işleri, syntax/dependency/test adımları success |
| Test izolasyonu | Ağ/DNS/sockets kapalı; SQLite yalnız çalıştırmanın geçici kökünde; legacy uzak testler toplanmaz |
| Çalışma klasörü | Ayrı `trade-ai-v2-development` worktree; geliştirme dalı temiz ve normal push ile origin'e eşit |
| Korunan referans | `origin/main` = `50136e13428028156b17c5953bdb27dc99eb682f`; asıl klasörün kullanıcı diff/untracked listesi ve üç yedek aynı |
| Üretim | Render/deploy, gerçek piyasa/portföy verisi, emir gönderimi veya migration yapılmadı |

Aşama commit'leri ve test kapsamı `V2_PROGRESS_LOG.md` içindedir. Bu checkpoint işlevsel kodu belirtir; sonraki yalnız belge commit'leri Git geçmişinden görülebilir.

## 2026-10-20 — M1/M2 izole akış doğrulaması

- Başlangıç: `8f55c82`; `469b27d` checkpoint'inin dalın atası olduğu doğrulandı. Kullanıcının `main` çalışma klasörü değiştirilmeden ayrı worktree kullanıldı.
- `python -m compileall -q market_ai server.py` geçti.
- `python -m unittest discover -s tests -p 'test_v2_*.py' -v`: **54 test geçti** (önceki 41 + 13 yeni test metodu; parametrik alt vakalar dahil).
- Offline adapter→QC→regime→Router smoke; trend/range/breakout/unknown, stale/future/unfinished/gap/mixed-source/mixed-contract, conflict/risk veto, tekrar üretilebilirlik ve volume capability izolasyonu doğrulandı.
- `unavailable` hacimde NaN/Infinity/bozuk metin kabul edilmesi kapatıldı; yalnız açık `None` geçerli.
- Uzak V1 API/DB testleri çalıştırılmadı. V1 API'ye yeni bağlantı, üretim deploy, kalıcı veri değişikliği veya emir gönderimi yok.
- Kod commit'i: `4179e9c25afe2c110b2a6d66f5d3b40cf49e02a8`; `origin/trade-ai-v2` ile eşitliği doğrulandı.
- GitHub Actions: [39452469362](https://github.com/FatihBirgul/trade-ai/actions/runs/39452469362), `v2-pure-python` işi ve syntax/unit adımları **success**. CI ve yerel sonuçlar ayrı ayrı doğrulandı.
- Koruma kontrolü: `origin/main` hâlâ `50136e13428028156b17c5953bdb27dc99eb682f`; asıl klasörün başlangıçtaki tracked/untracked değişiklik listesi korunuyor, üç yerel yedek yerinde.
