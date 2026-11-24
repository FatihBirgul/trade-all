# Codex mühendislik değişiklik kaydı

## 2026-10-29 — V2 Android sözleşmesi test uyumu

- Tracking yollarının 422 OpenAPI açıklaması kayıtlı şemaya sabitlendi.
- Backup testinin Windows'ta geçici SQLite dosyasını kilitleyen bağlantısı
  kapatıldı. Canlı veritabanı veya çalışan servis değiştirilmedi.
- İzole Backend 220/220 ve Gateway–Backend 42/42 test geçti.

## 2026-10-20 — V2 ağ/DB korumalı test runner

- V2 allowlist'li test runner socket/DNS bağlantılarını ve kendi geçici kökü dışındaki SQLite bağlantılarını engeller. Üretim yapılandırması okunmaz; legacy uzak API testleri toplanmaz.
- 126 V2 testi korumalar altında geçti; CI Windows/Ubuntu'da aynı runner'ı kullanır. Ayrıntılar `docs/V2_PROGRESS_LOG.md` içinde.

## 2026-10-20 — V2 snapshot replay

- Orijinal as-of ve sürüm girdileriyle offline yeniden hesaplama, hash karşılaştırma ve restart sonrası replay eklendi. Bozuk/desteksiz/nonfinite diagnostic girdiler unavailable kalır.
- Compile ve 122 V2 testi geçti. Ayrıntılar `docs/V2_PROGRESS_LOG.md` M1/M2.6 kaydında.

## 2026-10-20 — V2 veri/MTF güven sınırı

- MTF nonfinite confidence/score ve truthy string gate, Confluence generic kaynak/score ve V2 malformed identity/source açıkları regresyonlarla kapatıldı.
- 120 V2 test + 9 saf outcome testi başarılı; CI Windows/Ubuntu matrix'ine genişletildi. Ayrıntılar `docs/V2_PROGRESS_LOG.md` M1/M2.5 kaydında.

## 2026-10-20 — V2 append-only kayıt deposu prototipi

- Explicit yeni dosya, yabancı DB koruması, hash/idempotency, immutable SQL trigger ve backup/reopen için izole SQLite prototipi eklendi. Kullanıcı verisi veya MongoDB migration yok.
- Compile ve 115 V2 testi başarılı; persistence testleri geçici DB'lerle sınırlı. Immutable analiz aşaması `95302d6` için GitHub CI başarılı. Ayrıntılar `docs/V2_PROGRESS_LOG.md` M1.4 kaydında.

## 2026-10-20 — V2 immutable analiz ve risk kaydı

- Tam snapshot/config/strateji/engine sürümleri ve parametreleriyle hash'li immutable kayıt eklendi; teknik warm-up üst seviye WAIT ve analiz→risk instrument/zaman/record ID bağı doğrulandı.
- Compile ve 105 V2 testi geçti. Risk aşaması `420c40a` için GitHub CI başarılı. Ayrıntılar `docs/V2_PROGRESS_LOG.md` M1/M2.3 kaydında.

## 2026-10-20 — V2 paper risk sözleşmesi

- Geometri, maliyet sonrası RR, toplam/grup/günlük risk ve hesap ayrımı için saf risk gate eklendi. Pozisyon boyutu explicit policy'den hesaplanır; gerçek veya kalıcı veri kullanılmaz.
- Compile ve 93 V2 testi başarılı. M2.1 kodu `f0cafb6` için GitHub Actions başarıyla doğrulandı. Ayrıntılar `docs/V2_PROGRESS_LOG.md` M2.2 kaydında.

## 2026-10-20 — V2 teknik/MTF/Confluence referansları

- QC korumalı teknik adaptör ve 23 yeni test metodu eklendi; RSI zero-loss/flat, Confluence input sırası ve nonfinite Evidence hataları düzeltildi.
- Compile, 77 V2 testi ve 9 saf outcome regresyonu başarılı. Kapsam/kararlar/sınırlar `docs/V2_PROGRESS_LOG.md` M2.1 kaydında. `main`, üretim, DB/provider ve yerel yedekler korunuyor.

## 2026-10-20 — V2 QC/rejim/Strategy Router izole entegrasyonu

- **Problem:** Rejim sınıflandırıcısı ve Router ayrıydı; ortak akışın quality gate ve capability sözleşmesi test edilmemişti. `unavailable` volume, NaN/bozuk metni boş değer gibi kabul ediyordu.
- **Çözüm:** Yeni `v2.pipeline`, bütün mum batch'ini doğrular ve capability → rejim → Router sırasını uygular. `v2.capabilities`, gerçek/tick/eksik hacmi ayırır; mumlardan futures/order-flow feed'leri türetmez. FX/XAU için doğrulanmış takvim bulunmadığında WAIT verir. Hacim unavailable ise yalnız açık boş değer kabul edilir.
- **Test:** Backend compile geçti; 54 offline V2 unit/contract integration testi geçti. Adapter→Router smoke, veri kalitesi vetosu, risk/conflict, deterministik tekrar ve capability izolasyonu kapsandı.
- **Sınır:** V1 API bağlantısı, portföy risk hesabı ve FX takvimi bu milestone'da uygulanmadı. Production/persistent veri ve gerçek işlemler kapsam dışıdır.
- **GitHub:** `4179e9c` yalnız `trade-ai-v2` dalına normal push ile kaydedildi. [Actions 39452469362](https://github.com/FatihBirgul/trade-ai/actions/runs/39452469362) syntax ve V2 test adımları başarılı.

## 2026-09-10 — M0.1 Baseline ve kalıcı çalışma kaydı

- **Problem:** Depoda otonom çalışmanın recovery/baseline bilgisini taşıyan kalıcı çalışma belgeleri yoktu; mevcut testlerin güvenli hedefi de belgelenmemişti.
- **Çözüm:** Kök `AGENTS.md`, `docs/CODEX_STATE.md` ve `docs/ARCHITECTURE_DECISIONS.md` eklendi. Başlangıç checkpoint'i, korunan yedekler, mimari değişmezler ve test güvenlik sınırları kaydedildi.
- **Test:** `python -m compileall -q market_ai server.py` geçti. `tests/test_outcomes.py::TestOutcomeEngineUnit`: 7 geçti, 1 başarısız (`ambiguous`/`loss` outcome politikası çelişkisi). `python -m pytest --collect-only -q`: 13 test keşfedildi; `backend/tests/backend_test.py` için `ModuleNotFoundError: PIL` nedeniyle koleksiyon tamamlanmadı.
- **Commit:** `89db2a691266ca0478f99492b0e706ff1e1453c9` — `Add Codex baseline state documents`.
- **Push:** Başarılı — GitHub `origin/main` aynı commit'te doğrulandı.
- **Kalan konu:** Yerel test bağımlılıklarını ve izole integration test stratejisini değerlendirmek; görev belgesindeki Scenario `None` raporunu yeniden üretmek ve kök nedeni doğrulamak.

## 2026-09-10 — M1.1 Outcome intrabar ambiguity regression sözleşmesi

- **Problem:** Aynı OHLC mumunda hem TP1 hem invalidation temasını `ambiguous` yapan engine/model/API sözleşmesiyle, başlangıçtan kalan testin muhafazakâr `loss` beklentisi çelişiyordu. History outcome status testi de geçerli `ambiguous` durumunu kabul etmiyordu.
- **Çözüm:** Production engine korunarak test sözleşmesi `ambiguous` davranışıyla hizalandı. Bullish ve bearish çift temaslar için birer regression kontrolü, ayrıca history status sözleşmesine `ambiguous` eklendi.
- **Test:** `python -m compileall -q market_ai server.py` geçti. `python -m pytest -n 0 --basetemp C:/tmp/trade-ai-pytest-outcome tests/test_outcomes.py::TestOutcomeEngineUnit -q` — 9 passed.
- **Commit:** Beklemede — outcome regression atomic commit'i Git geçmişinden doğrulanacaktır.
- **Push:** Beklemede — commit sonrası `origin/main` doğrulanacaktır.
- **Kalan konu:** Scenario metinlerinde zone değeri yokken `None` sızıntısını yeniden üretmek ve güvenli fallback sözleşmesini oluşturmak.
