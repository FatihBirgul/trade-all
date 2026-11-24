# İzole Windows backend API kabul testleri

11 Kasım 2026. Ana kaynak başlangıcı `806ed90`. Araçlar varsayılan kapalıdır; public/çalışan API'ye route eklemezler. `fixture_server.py` yalnız explicit fixture modu ile açılır, daima `127.0.0.1` bağlar ve canlı MT5 import etmez. İzole request middleware senaryoları sadece bu QA sürecinde kullanılabilir; üretim launcher olarak kullanılmamalıdır.

## Tekrar üretme

```powershell
$qa = Join-Path $env:TEMP 'trade-ai-runtime-acceptance-20261111'
$py311 = '%USERPROFILE%\trade-ai-v3-v2-p1\.venv\Scripts\python.exe'
$py313 = Join-Path $env:TEMP 'trade-ai-p1-main-qa-20261111\py313\Scripts\python.exe'
& $py311 tools\runtime_acceptance\run.py --run-fixture-acceptance --output (Join-Path $qa 'http311')
& $py313 tools\runtime_acceptance\run.py --run-fixture-acceptance --output (Join-Path $qa 'http313')
& $py311 -m unittest discover -s tests -v
& $py313 -m unittest discover -s tests -v
```

Komutlar ana repo cwd'sinde çalışır. İki interpreter izole, NumPy 2.2.6. Python sürümleri sırasıyla 3.11.9 ve 3.13.15. İki `pip check` başarılı. Global Python 3.11 NumPy 2.4.6 değiştirilmedi.

## Sonuçlar

| Paket | Python 3.11.9 | Python 3.13.15 |
|---|---|---|
| Başlangıç tam regression | 487 PASS, 65.644 s | 487 PASS, 59.161 s |
| Son araçlarla tam regression | 487 PASS, 79.272 s | 487 PASS, 74.120 s |
| Gerçek localhost HTTP fixture kabulü | 56/56 PASS | 56/56 PASS |
| Aynı snapshot / prefix ek QA | PASS | PASS |
| PWA saf guard/source kabulü (Node, bir kez) | 9/9 PASS | Ortak kaynak kontrolü |

Tam paketlerde failure/error/skip yok. Yeni unittest eklenmedi veya mevcut test kaldırılmadı; 487 referansı korundu. 56 HTTP assertion, 487 test sayısına dahil edilmez.

HTTP kapsamı: startup, TEST_ONLY health, dört sembol, 220 kapanmış mum, V1/V5 schema, risk USC yanıtı, BUY/SELL/WAIT, missing candle, unknown session, OPENING_SOON, sentetik CLOSE_ONLY, stale quote, Double Top/Bottom, candlestick composite, empty chart list, source mismatch/missing 503, minimum lot veto, REAL-policy legacy balance reddi, varsayımsal USC ve 10 senaryoda aynı snapshot bridge açık/kapalı eşitliği. Candle fixture'ları dört sembol için yalnız transport amaçlı kopyalanır; gerçek FX fiyat ölçeği/oraklı sayılmaz. WAIT kontrollü core karşıt strateji fixture'ıdır. CLOSE_ONLY sentetiktir; gerçek tarihsel broker modu iddiası yoktur.

`OPENING_SOON` fixture sonucu `NO_TRADE` + `market_status=OPENING_SOON`; yeni pozisyon planı verilmez. CLOSE_ONLY sonucu `MARKET_CLOSED` + `market_status=DISABLED`. Bunları zorla BUY/SELL üretmek için değiştiren kod yoktur.

Fixture subprocess sahibi Popen handle ile izlenir. Windows venv launcher parent/child ayrımı manifestte `pid`, `parent_pid` ve tek çalıştırımlık nonce ile doğrulanır. Yalnız bu başlatılan Popen PID ağacı kapatılır; porttan süreç öldürülmez. Son assertion kendi portunun kapandığını doğrular. Windows force-termination çıkış kodu 1 beklenen kontrollü kapanmadır; test hatası değildir. Son başarılı 3.11 fixture launcher PID 7800/port 59734; 3.13 PID 8552/port 59772; ikisi kapatıldı. 5173/8005/8006 aynı kaldı. Sonraki dış eşzamanlı haber değişikliğinde 8007 PID 9724 -> 12152 gözlendi; bu QA aracı 8007'yi yönetmedi.

İlk QA geliştirme denemelerinde yanlış composite importu, OPENING_SOON için yanlış beklenen karar ve Windows launcher PID varsayımı düzeltildi. Yalnız yeni QA araçları değişti; üretim algoritması, mevcut test veya güvenlik kapısı değiştirilmedi. Nihai 56/56 koşuları bu düzeltmelerden sonradır. İlk başarısız denemeler canlı broker veya mevcut 487 regression hatası değildir.

Kaynak SHA, first-known/prefix ve beş aynı-snapshot ek QA çıktısı iki interpreterda aynı: SHA256 `abe3303f466a9b63e01d87dcdc5605260ef9fd38f9be76bcddca3dec432263d6`. NumPy 2.4.6 sürüm değeriyle yükleme mock edildiğinde beklenen güvenli ret var; global sürüm değiştirilmedi veya farklı sürüm sessizce çalıştırılmadı.

Default kapalı runner flag'siz çağrıldığında exit 2 verdi. İki sürümde `compileall -q forex tests tools` ve `git diff --check` başarılı. Araçlar hesap bilgisi, parola veya token manifestine yazmaz. `fixture-manifest.json`, `results.json`, `fixture-server.log`, `full311.log`, `full313.log`, `final311.log`, `final313.log` ve ek QA JSON'ları temp QA dizinindedir.
