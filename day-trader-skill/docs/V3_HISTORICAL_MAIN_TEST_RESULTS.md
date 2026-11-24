# Historical main promotion kabul sonuçları

11 Kasım 2026. Sonuçlar bu entegrasyon görevi sırasında yeniden hesaplandı;
önceki teslim raporundan kopyalanmış kabul değildir. Source HEAD
`24df2ed6a6c94b8eea8548ec8980ba897057e0b5`; main başlangıcı
`3c8adb810058b4738640f46bde84de8ec12205ad`, FF sonrası kod hedefi source SHA'dır.
Son docs commit'i Python/test/tool kodunu değiştirmez.

| Grup | Source Python 3.11.9 | Source Python 3.13.15 | Main Python 3.11.9 | Main Python 3.13.15 |
| --- | --- | --- | --- | --- |
| Full unittest | 600/600 PASS, 75.283 s | 600/600 PASS, 47.515 s | 600/600 PASS, 70.746 s | 600/600 PASS, 46.928 s |
| Historical/importer/TestClient | 81 yeni metod full pakete dahil | 81 dahil | 81 dahil | 81 dahil |
| Mevcut HTTP | 63/63 PASS | 63/63 PASS | 63/63 PASS | 63/63 PASS |
| Historical HTTP | 14/14 PASS | 14/14 PASS | 14/14 PASS | 14/14 PASS |
| PWA contract | 9/9 PASS | 9/9 PASS | 9/9 PASS | 9/9 PASS |
| compileall forex/tests/tools | PASS | PASS | PASS | PASS |
| Failure / error / skipped | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

Her repo içinde önce 3.11 tam koşusu bitti, sonra 3.13 koşusu başladı.
NumPy iki izole interpreter'da **2.2.6**. Global NumPy ayrıca okunarak **2.4.6**
olarak doğrulandı; kurulum/güncelleme yapılmadı. 3.11 executable
`%USERPROFILE%\trade-ai-v3-v2-p1\.venv\Scripts\python.exe`, 3.13 executable
`%TEMP%\trade-ai-p1-main-qa-20261111\py313\Scripts\python.exe`.

600 = önceki 519 korunmuş test + 81 yeni historical metod. AST sayımı 81'i
bağımsız doğruladı; başlangıç/source test farkları yalnız eklenen yeni dosyalardır.
81 zaten 600 içinde olduğundan ayrıca toplanmaz. HTTP 63, 62 fixture kabul ve
owned-process cleanup kontrolünü içerir. Historical HTTP 14, 12 senaryo,
malformed request ve listener cleanup grubudur. PWA 9 pure guard/kaynak
sözleşmesidir; canlı UI kabulü değildir. Dört full koşu 2400 farklı test metodu
anlamına gelmez. Fixture başarıları gerçek broker kanıtı değildir.

## İnceleme ve güvenlik kanıtı

Kaynak diff'inde core.py, policy.py, spread_policy.py, broker_contract.py,
api.py ve V2 bridge kaynakları değişmedi. contracts/provider/sessions/unified
farkları satır düzeyinde incelendi. JSON verified alanı strict schema'da ret;
APPROVED tek başına yetki değil; source/original hash, independent review,
exact server/product/currency/symbol, coverage ve knowledge-as-of kapıları vardır.
Production review tuple boş; test DI API/env girdisinden erişilemez.

Full paket no evidence, weekly/operator, yanlış XAUUSD/EURUSD alias, yanlış
server/date, partial/conflicting/hash/unreviewed, look-ahead ve future retlerini
kapsar. Pozitif sentetik kapsam yalnız bütünü kapalı M5/M15 boşluğu açıklar;
kısmen quote-open veya close-only quote aralığında kayıp mum ret edilir.
23:00 M15 bucket'ı 23:15'ten önce kapalı sayılmaz. UTC/DST, ambiguous/fold,
nonexistent, holiday ve tarihler arası eksik kapsam testleri geçti.

Mevcut BUY/SELL/WAIT, Entry/SL/TP, UNAPPROVED spread, USC, hypothetical capital,
minimum lot risk, PnL oracle, REAL_READONLY_DATA ve V2 DESCRIPTIVE_ONLY testleri
aynı full koşularda geçti. AST no-order kontrolleri korunur. Hatalı evidence API
girdisi 422; geçerli historical fixture bile spread/contract kapısını aşamaz.

## Tekrar üretim ve yerel loglar

QA root: `%USERPROFILE%\trade-ai-historical-promotion-qa-20261111`.
Full loglar: `source311.log`, `source313.log`, `target311.log`, `target313.log`.
Her scope/version için `<source|target><311|313>-http/results.json`,
`-historical.json`, `-pwa.json` gerçek makine sonuçlarını içerir.
`before.json` başlangıç kimliklerini; `recovery-ref.txt` recovery ref'i saklar.

İlgili repo cwd'sinde, yukarıdaki izole Python executable'ı ile:

```text
python -m unittest discover -s tests -v
python tools/runtime_acceptance/run.py --run-fixture-acceptance --broker-readiness --output <repo-disi-QA>
python tools/runtime_acceptance/historical.py --run-historical-fixtures --output <repo-disi-QA>/historical.json
node tools/runtime_acceptance/pwa_contract.cjs --inspect-readonly %USERPROFILE%\trade-ai-forex-web <http-results.json> <pwa-results.json>
python -m compileall -q forex tests tools
git diff --check
```

Source fixture process/port: 3.11 PID 1380/62784, 3.13 PID 2444/62898;
historical portları 62863/62999. Main fixture process/port: 3.11 PID 12052/63163,
3.13 PID 5056/63340; historical portları 63293/63426. Hepsi yalnız kendi
başlatılan kimlikleriyle kapatıldı ve cleanup kontrolleri başarılı oldu.

`git diff --check` başarılı. Bu görevde test başarısızlığı veya skip olmadı.
İlk runtime inspection denemesinde global Python'da psutil bulunmadı; mevcut
önceki QA inspection-lib read-only kullanılarak giderildi, paket kurulmadı.

## Canlı sınırı

8006 PID 8284, 5173 PID 10320, 8005 PID 9880, 8007 PID 12152 korundu.
8006 schema historical_session_evidence alanı öncesinde/sonrasında yok;
loaded runtime sürümü UNVERIFIED. Canlı hesap/veri analizi ve runtime cutover
yapılmadı. Gerçek Exness 6-11 Kasım kanıt kabulü **NOT_RUN /
BLOCKED_BY_EXTERNAL_EVIDENCE**; bu bir skipped unit test değildir.
