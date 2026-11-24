# Tarihsel seans test sonuçları

11 Kasım 2026, Windows. Başlangıç `3c8adb810058b4738640f46bde84de8ec12205ad`.
Son üretim kodu checkpoint'i `848d2a3`; iki yeni sentetik fixture düzeltmesi
dahil nihai çalışma içeriği aşağıdaki son tam koşularla sınandı. Eski 519 testin
hiçbiri değiştirilmedi. Yeni 81 test metodu ile tek suite toplamı **600** oldu.

| Grup | Python 3.11.9 / NumPy 2.2.6 | Python 3.13.15 / NumPy 2.2.6 |
| --- | --- | --- |
| Temiz başlangıç full unittest | 519/519 PASS, 53.027 s | Başlangıçta ayrıca çalıştırılmadı |
| Son full unittest | **600/600 PASS, 56.410 s** | **600/600 PASS, 62.070 s** |
| Yeni tarihsel / TestClient testleri | 81/81 PASS; full pakete dahil | 81 test full pakette geçti |
| Mevcut loopback HTTP | 63/63 PASS | 63/63 PASS |
| Yeni tarihsel loopback HTTP | 14/14 PASS | 14/14 PASS |
| Mevcut PWA contract / pure guards | 9/9 PASS | 9/9 PASS |
| compileall: forex, tests, tools | PASS | PASS |
| pip check | No broken requirements found | No broken requirements found |
| Son failure / error / skipped | 0 / 0 / 0 | 0 / 0 / 0 |

3.11 tam koşusunun başarılı tamamlanmasından sonra 3.13 tam koşusu başlatıldı.
600, 81, 63, 14 ve 9 sayıları farklı bağımsız benzersiz testler diye toplanmaz.
81 zaten 600'e dahildir; TestClient senaryoları da bu 81'in içindedir.
63 mevcut HTTP kontrolü 62 kabul kontrolü ve owned-process cleanup içerir.
14 yeni HTTP kontrol grubu 12 tarihsel senaryo, malformed-input 422 ve kendi
listener'ının kapandığı denetimidir. Bir grupta birden fazla assertion vardır.
İki interpreter koşusu 1200 farklı test metodu anlamına gelmez.

## Ortam ve tekrar komutları

3.11 interpreter:
`%USERPROFILE%\trade-ai-v3-v2-p1\.venv\Scripts\python.exe`.
3.13 interpreter:
`%TEMP%\trade-ai-p1-main-qa-20261111\py313\Scripts\python.exe`.
Mevcut izole interpreter'lar yalnız çalıştırıldı; paket kurma/güncelleme yapılmadı.
Global Python 3.11 NumPy doğrudan kontrol edildi: **2.4.6**, değiştirilmedi.
Geliştirme, dosya yazımı ve commitler yalnız bağımsız historical clone içindedir.

İzole repo çalışma dizininde:

```text
python -m unittest discover -s tests -v
python -m unittest discover -s tests -p "test_historical*.py" -q
python tools/runtime_acceptance/run.py --run-fixture-acceptance --broker-readiness --output <repo-disi-QA-dizini>
python tools/runtime_acceptance/historical.py --run-historical-fixtures --output <repo-disi-QA-dizini>/historical.json
node tools/runtime_acceptance/pwa_contract.cjs --inspect-readonly %USERPROFILE%\trade-ai-forex-web <HTTP-results.json> <PWA-results.json>
python -m compileall -q forex tests tools
python -m pip check
git diff --check
```

`python` burada yukarıdaki izole executable'lardan biri anlamındadır.
PYTHONDONTWRITEBYTECODE=1 ile normal test importları yapıldı; explicit compileall
yalnız izole clone'da bytecode üretti. Günlükler root manifest testini etkilememesi
için depo dışında tutuldu.

## Somut kapsam

`test_historical_sessions.py`: strict schema ve unknown field; duplicate JSON
key; byte/interval bütçeleri; original hash; exact dört Cent sembolü; yanlış
broker/server/product/currency; weekly/operator ret; self-asserted verified ret;
coverage ve future interval; partial/date holes; conflicting/unreviewed kaynaklar;
hash değişimi; publication/acquisition/review look-ahead; DST fold/nonexistent,
doğru/yanlış dated offset; UTC/midnight/weekend/holiday/exceptional; M5/M15 tam
kapalı ve kısmen açık bucket; positive tick; unfinished/stale/future/real-volume
retleri; trade-only, close-only, trade/quote mismatch; traversal/absolute/ADS,
reparse-bit ve gerçek hardlink; config'ten onay verilememe ve read-only CLI.

`test_historical_api.py`: missing/weekly/wrong symbol/wrong broker/operator/
unreviewed/partial/conflicting/open-gap BLOCKED; sentetik geçerli veri OK/WAIT;
UNAPPROVED spread ve bozuk broker contract ret; V2 bağlamının güvenlik kapısını
aşamaması; malformed request 422; snapshot kimlik/as-of bağlama; candle
timestamp'lerinin değişmemesi; eski REAL dışı declared-hours yolunun korunması.

Mevcut full suite ayrıca OPENING_SOON/CLOSED/UNKNOWN, BUY/SELL/WAIT,
Entry/SL/TP, USC/lot/risk/PnL, V2 descriptive-only ve AST no-order regresyonlarını
korur. HTTP fixture'ları MetaTrader5 terminaline bağlanmaz ve gerçek broker
kanıtı değildir. PWA 9 kontrolü kaynak ve pure guard sözleşmesidir; canlı UI veya
eksik pattern renderer/dört sembol UI işlerinin tamamlandığı iddiası değildir.

## Gerçek hata geçmişi

İlk iki baseline denemesi 519 testte birer root manifest hatası verdi: QA günlüğü
için açılan `.qa` klasörü kök dosya beklentisini bozdu. Aktif dosya handle'ı kapanınca
yalnız bu görevin günlükleri repo dışına taşındı; test değiştirilmedi. Temiz
baseline 519/519 geçti.

Yeni DST testlerinde DataError'ın ValueError alt türü olması nedeniyle anlamlı
ambiguous/nonexistent mesajları maskeleniyordu; üretim exception sırası düzeltildi.
Taslak API fixture'ında bid price_kind eksikti; fixture düzeltildi. Operator state
test beklentisi ayrı OPERATOR_DECLARED semantiğiyle hizalandı. Son trade/quote
consistency kontrolü iki draft sentetik girdinin de tutarsız olduğunu yakaladı;
hash-pin testi source reference değiştirir hale getirildi, conflict testi quote ve
trade bitişini birlikte değiştirerek geçerli ama farklı kaynak sınar hale getirildi.
Ara geliştirme koşusunda bu iki hata görüldü; yukarıdaki final 600 testte yoktur.
Başarısızlık gizlemek için eski test değişikliği, skip veya xfail yapılmadı.

## Yerel kanıt dosyaları ve servisler

QA dizini: `%USERPROFILE%\trade-ai-historical-qa-20261111`.
Baseline: `baseline-clean-py311.log`. Son tam koşular: `verified-py311.log`,
`verified-py313.log`. HTTP: `http-py311/results.json`, `http-py313/results.json`.
Yeni HTTP: `historical-http-py311.json`, `historical-http-py313.json`.
PWA: `pwa-py311.json`, `pwa-py313.json`. Önceki development logları aynı dizinde
korunur; nihai sonuçlar verified loglarından okunmalıdır.

Son mevcut HTTP subprocess'leri: 3.11 PID 10460 / port 60884, 3.13 PID 10380 /
port 60990; yalnız kendi süreç ağaçları kapatıldı ve cleanup kontrolü geçti.
Yeni tarihsel HTTP listener'ları 60964 ve 61056 portlarında çalıştı; ikisi de
kapandı. Servis portlarından süreç öldürülmedi. 5173=10320, 8005=9880,
8006=8284, 8007=12152 başlangıç ve son denetimde aynı kaldı.

`git diff --check` temiz. Hash'li fixture'lar alt dizin `.gitattributes` ile
line-ending dönüşümünden korunur; committed original byte'ları çalışma dosyasıyla
aynı ve SHA-256 `c6bbcc38cfbda2f73c40ec10f22a85dfdc9ebc55358cc7f1d77d003c830d68b3`.

Gerçek broker historical acceptance: **NOT RUN / BLOCKED_BY_EXTERNAL_EVIDENCE**.
Bu bir skipped unit test değildir; gerekli Exness belgesi henüz sağlanmamıştır.
