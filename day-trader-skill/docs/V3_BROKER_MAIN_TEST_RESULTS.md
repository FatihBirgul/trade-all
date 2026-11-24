# Broker main promotion testleri

11 Kasım 2026. Kaynak kabulü `codex/v3-broker-evidence-readiness` / `93c3382`; hedef kabulü fast-forward sonrasında aynı klasörde **codex/v3-real-readonly-analysis** / `93c3382`. Aynı dosya ağacı olması hedef koşusunun yerine sayılmadı; iki koşu gerçekten ayrı çalıştırıldı.

| Kapsam | Python 3.11.9 | Python 3.13.15 |
|---|---|---|
| Kaynak full unittest | 519/519 PASS, 67.509 s | 519/519 PASS, 62.679 s |
| Kaynak HTTP | 63/63 PASS | 63/63 PASS |
| Hedef full unittest | 519/519 PASS, 75.477 s | 519/519 PASS, 71.106 s |
| Hedef HTTP | 63/63 PASS | 63/63 PASS |
| PWA salt okunur Node guard/source | Kaynak 9/9 PASS; hedef 9/9 PASS | Ortak frontend kaynak kontrolü |

NumPy iki izole interpreterda 2.2.6. Python 3.11 executable `%USERPROFILE%\trade-ai-v3-v2-p1\.venv\Scripts\python.exe`; 3.13 executable `%TEMP%\trade-ai-p1-main-qa-20261111\py313\Scripts\python.exe`. Global Python 3.11 NumPy 2.4.6 korundu. İnceleme yardımcı paketi ayrı temp target'a kuruldu; API/venv/global paketlerine kurulum yapılmadı.

Full runner: `python -m unittest discover -s tests -v`. HTTP: `python tools/runtime_acceptance/run.py --run-fixture-acceptance --broker-readiness --output <QA-dir>`. PWA: mevcut `pwa_contract.cjs --inspect-readonly` aracı. 519 = önceki 487 + 32 broker/readiness testidir. 63 HTTP, önceki 56 ve 7 yeni assertion'ı kapsar; unit/HTTP/PWA sayıları benzersiz toplam diye toplanmaz. Fixture başarıları canlı broker kabulü değildir.

Full kapsam: current contract field trust, exact alias/server, PRICE/POINTS, approval/effective date/version/source, boundary/spike, null limit/BLOCK, USC/profit currency, contract-size/PnL/tick oracle, rounding/minimum lot, stop-level, dönüşüm eksikliği/stale, BUY/SELL/WAIT/INSUFFICIENT_DATA, session unknown/verified fixture, XAUUSDc tarihsel gap reddi, REAL account/balance/no-order, V1/V5 API, V2 chart/candlestick hash/first-known/prefix ve descriptive-only invariant. Kaynakların pinli hash'i mevcut testler tarafından gerçek Git nesnesinden doğrulanır.

İki sürümde `compileall -q forex tests tools`; `git diff --check 09e5dab..93c3382`, working-tree check ve iki pip check başarılı. Kaynak ve hedef suite'lerde 0 failure, 0 error, 0 skip. Test silme/skip veya onaysız limit üretme yoktur. QA süreçleri kendi Popen kimlikleriyle kapatıldı; her koşuda own_fixture_port_closed kontrolü geçti. 5173/8005/8006/8007'ye kill/restart uygulanmadı. Hedef HTTP startup manifestleri source_head=93c3382 olarak kaydedildi.

Ham kanıt `%TEMP%\trade-ai-broker-promotion-20261111`: source311/source313/main311/main313 logları; source-http311/source-http313/main-http311/main-http313 results/manifest/logları; pwa-source/pwa-main JSON; watcher-before/after, supervisor-check, runtime-before/after, tracked-before ve promotion-file-check JSON'ları. Temp dosyaları kalıcı arşiv değildir; sürümlü sonuç özeti bu belgedir.
