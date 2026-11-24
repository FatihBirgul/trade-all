# P1 yerel test sonuçları

Tarih: 2026-11-10. Testler `%USERPROFILE%\trade-ai-v3-v2-p1` izole worktree'sinde; kaynak V2 deposuna yazılmadı.

| Aşama | Ortam / komut | Sonuç |
|---|---|---|
| Başlangıç V3 referansı `f78b638` | Python 3.13 `py -3.13 -m unittest discover -s tests -q` | 475/475 PASS |
| Başlangıç V3 referansı `f78b638` | Python 3.11.9 izole `.venv`, pinli test bağımlılıkları ile aynı runner | 475/475 PASS |
| P1 hedefli | `.venv\Scripts\python.exe -m unittest discover -s tests -p test_v2_chart_bridge.py -q` | 12/12 PASS |
| P1 tüm paket | Python 3.13.15 `py -3.13 -m unittest discover -s tests -q` | 487/487 PASS, 0 failure, 0 error, 0 skip; 72.973 s |
| P1 tüm paket | Python 3.11.9 `.venv\Scripts\python.exe -m unittest discover -s tests -q` | 487/487 PASS, 0 failure, 0 error, 0 skip; 78.312 s |
| Bağımlılık tutarlılığı | `.venv\Scripts\python.exe -m pip check` | No broken requirements |

Yeni 12 test: pinli commit/SHA ve kirli kaynak ayrımı, kaynakta emir/ağ/dinamik import çağrısı denetimi, NumPy sürüm ret, çift tepe ve dip pivot ilk bilgi zamanı, önek replay, M15/H1/H4, expiry/invalidation sınırı, breakout dışlama, eksik/gelecek mum, yanlış kaynak/pazar, stale H4, seans ret, BUY/SELL/kapalı karar değişmezliği, USC/lot/risk, tick volume yeteneği, kandil + chart birleşimi, API yanıtı ve kaynak yokken 503, hesaplama süresi/çıktı sınırı. Mevcut `test_v3_v2_integration.py` G-001 eksik RSI, G-002 sıfır MACD, G-003 üst TF cutoff/stale ve gerçek hacim ret testlerini korur. G-004 için algoritma sürümleri karşılaştırıldı; V5 hesaplaması değiştirilmedi.

Bu testler sentetik fixture ve yerel API TestClient kullanır. Gerçek Exness/XAUUSDc seans geçmişi, MT5 terminal bağlantısı, broker tick doğruluğu, kârlılık veya işlem yürütme test edilmedi. `V2_CHART_GIT_ROOT` ile kaynak checkout ve NumPy 2.2.6 üretim ortamında ayrı sağlanmalıdır. İşlem emirleri açılmadı.
