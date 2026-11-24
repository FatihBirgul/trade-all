# P1 ana entegrasyon test sonuçları

Tarih: 11 Kasım 2026. Sentetik veri, mock terminal ve yerel FastAPI TestClient kullanıldı. Çalışan servisler veya MT5 terminali üzerinde test/emir çalıştırılmadı.

## Ortam ve tekrar üretme

Python 3.11.9: `%USERPROFILE%\trade-ai-v3-v2-p1\.venv\Scripts\python.exe` (mevcut izole ortam).

Python 3.13.15: `%TEMP%\trade-ai-p1-main-qa-20261111\py313\Scripts\python.exe` (bu görev için ayrı izole ortam).

İki ortamda `requirements-test-py311.txt` pinleri: NumPy 2.2.6, FastAPI 0.115.14, Starlette 0.46.2, httpx 0.28.1, Pydantic 2.14.3, pydantic_core 2.50.4, uvicorn 0.54.0, tzdata 2026.6. Kalan tam sürümler requirements dosyasındadır. Her iki `pip check` başarılı. Global Python paketleri değiştirilmedi; global Python 3.11 NumPy 2.4.6 korundu.

Her çalışma ağacında, o dizin current directory iken iki interpreter için ayrı çalıştırılan komut:

```powershell
& <isolated-python.exe> -m unittest discover -s tests -v
```

## Tam paket matrisi

| Çalışma ağacı / kod | Python | Sonuç | Süre |
|---|---|---|---|
| P1 / `753ed59` | 3.11.9 | 487 PASS; 0 failure, 0 error, 0 skip | 75.028 s |
| P1 / `753ed59` | 3.13.15 | 487 PASS; 0 failure, 0 error, 0 skip | 58.360 s |
| Ana V3 / entegre P1 | 3.11.9 | 487 PASS; 0 failure, 0 error, 0 skip | 86.291 s |
| Ana V3 / entegre P1 | 3.13.15 | 487 PASS; 0 failure, 0 error, 0 skip | 80.994 s |

487 sayısı önceki referansla aynıdır: tabandaki 475 + P1'in 12 testi. Test silme, değiştirilmiş başarı kriteri veya yeni skip yoktur. P1'in 12 hedefli testi tam pakette ayrı test isimleriyle çalıştı.

## Kritik kapsam ve ek kabul

- `test_v2_chart_bridge.py`: pinli SHA/commit, kirli dosyayı okumama, import/no-order AST denetimi, sürüm reddi, Double Top/Bottom, pivot first-known, prefix causality, M15/H1/H4, expiry ve desteklenmeyen breakout dışlama, gelecek/unfinished/yanlış kaynak mumları, BUY/SELL/kapalı kararlar, USC/risk, candlestick composite ve API 503.
- Mevcut candlestick/V2 integration, unified API/security/contract, risk, sessions, Exness gap, XAUUSDc evidence, REAL readonly testleri tam paketin içindedir. XAUUSD saatlerinin XAUUSDc'ye aktarılmaması korunur.
- Ek dış QA scripti `audit.py`: ham Git blob SHA256, AST import listesi, aynı immutable snapshot üzerinde BUY/SELL/WAIT/USC/INSUFFICIENT_DATA açık/kapalı kıyası; iki aile için 213/215/216/220 bar prefix çıktıları; NumPy sürüm değeri 2.4.6 olarak mock edildiğinde yüklemenin reddi. Farklı NumPy matematiği sessizce kullanılmaz.
- WAIT ve INSUFFICIENT_DATA ek kıyasları kontrollü core fixture'larıdır. REAL_READONLY_DATA hesap politikası mevcut mock-terminal testleriyle doğrulanır; ek scriptin `account_mode='REAL'` alanı gerçek terminal bağlantısı anlamına gelmez.
- Dört ek QA çıktısı (P1 3.11/3.13 ve ana 3.11/3.13) bayt düzeyinde eşittir. SHA256: `abe3303f466a9b63e01d87dcdc5605260ef9fd38f9be76bcddca3dec432263d6`.
- İki çalışma ağacında ve iki Python sürümünde `python -m compileall -q forex tests tools` başarılı. `git diff --check f78b638..753ed59` ve temiz çalışma ağacı diff kontrolü başarılı.
- P1 farkında V5 core/unified/policy/session/API ve diğer kritik üretim dosyalarının değişmediği doğrulandı.

Ek QA scriptinin ilk denemesinde hesap modu yerine policy adı verilmesi nedeniyle harness ValidationError oluştu; yalnız dış QA scripti doğru `REAL` enum değeriyle düzeltildi. Üretim kodu/testler değiştirilmedi; düzeltilmiş dört kıyas başarılıdır. Tam unittest paketlerinde hata yoktur.

Ham verbose loglar ve ek deterministik JSON çıktıları `%TEMP%\trade-ai-p1-main-qa-20261111` altında saklanır: `p1-py311.log`, `p1-py313.log`, `main-py311.log`, `main-py313.log`, `p1-audit311.json`, `p1-audit313.json`, `main-audit311.json`, `main-audit313.json`, `audit.py`. Temp klasörü kalıcı arşiv garantisi vermez; sürümlü sonuç özeti bu dosyadır.
