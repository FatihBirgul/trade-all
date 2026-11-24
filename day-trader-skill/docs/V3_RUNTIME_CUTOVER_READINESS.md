# Broker readiness runtime geçiş paketi

11 Kasım 2026. Bu görev canlı restart yetkisi kullanmaz. 5173/8005/8006/8007 süreçleri korunur; yalnız QA aracının kendi Popen süreç ağacı kapatılır.

## Kimlik ve sürüm

Başlangıç exact SHA `09e5dab3bead337b3fab6a9267bbfe4fc16f3e7b`. Yeni release SHA, bu dosyaları içeren yerel teslim commitidir; son kullanıcı raporunda ve yerel paket adında verilir. Dal `codex/v3-broker-evidence-readiness`; ana `codex/v3-real-readonly-analysis` dalına merge yapılmadı.

Bu teslimde test edilen production public-code SHA256: `8ae5f726d7fae3dd8311c9d0a0c53a49a187ccc33831305fdf1c18ae296ea99a`. Bu disk kaynak bütünlüğüdür; loaded-code fingerprint ile karıştırılmaz.

Mevcut 8006 PID 7532, process start 11 Kasım 15:30:28, listen 15:30:29 Europe/Istanbul; global Python 3.11 executable, `forex.api:app`, reload yok. Başlangıç checkpoint'inde aynı kimlikti. Tam command line veya özel env kaydedilmedi. Global Python 3.11 disk NumPy 2.4.6; süreç içi NumPy/modül nesneleri ayrıca doğrulanmadı.

8006, local /engine ve Tailscale şemalarında yeni `broker_contract` ve `spread_status` yok. Bu nedenle **OLD_VERSION, bu broker-readiness API sürümüne göre**. P1'in bellekteki exact checkpoint'i halen VERSION_UNVERIFIED; disk hash'i onun kanıtı değildir. Çalışan servise tanılama endpoint'i eklenmedi.

## Hazır izole kabul

Python 3.11.9 ve 3.13.15 izole, NumPy 2.2.6. `tools/runtime_acceptance/run.py --run-fixture-acceptance --output <QA-dir>` eski 56 kontrolü korur. `--broker-readiness` eklenince toplam 63 assertion: aynı 56 + 7 typed broker/spread HTTP kontrolü. Bunlar farklı bağımsız test toplamları gibi toplanmaz. Tüm süreçler loopback; fixture provider; canlı terminale erişim yok. Kendi portu kapandı assertion'ı vardır.

Startup manifesti git checkpoint, NumPy, V2 source pins, loaded file hash'leri ve yeni `build_fingerprint.loaded_fingerprint()` sonucunu özel local QA dosyasına yazar. Yeni digest diski okumadan o süreçte yüklü Python fonksiyonlarının code object'lerinden üretilir. Dosya değişmeden loaded code değiştirilince değiştiği test edilir. Python cache tag ile birlikte yorumlanır; sürümler arası eşitlik iddiası yok. Co_filename normalize edildiğinden dosya yolu dışarı taşınmaz. Bu bir imza/uzaktan bellek ispatı değildir; module globals, C extension içi kod, hesap/config veya sonraki lazy importları otomatik kapsamaz. Fresh immutable startup, source hash ve dependency setiyle birlikte kullanılır. Fixture başlangıcı broker/spread lazy modüllerini de explicit yükler. Public auth'suz endpoint yoktur.

## Bir sonraki yetkili operasyon

1. Tam teslim SHA'sını immutable release klasörüne paketle; `git archive --format=zip --output=<yeni.zip> <exact-SHA>` kullanılabilir. V2/PWA checkout'a yazma veya reset gerekmez. Eski release, private launch config ve ortamı güvenli tut.
2. Ayrı Python 3.11 venv; `requirements-test-py311.txt` pinleri, NumPy 2.2.6; Windows MT5 gerekiyorsa gözlenen MetaTrader5 5.0.6231'i ayrıca doğrula. Global interpreter değiştirilmez. pip check + tam regression gerekir.
3. Yalnız aday süreç env'sinde REAL_READONLY_DATA, Exness-MT5Real50, USC ve dört exact alias JSON mapping ayarlanır. `MT5_SPREAD_POLICY_FILE` onaysız template ile test edilebilir; sonuç BLOCK olmalıdır. Kullanıcı limit onaylamadan maximum/date/approval doldurulmaz. Eski MT5_MAX_SPREAD artık REAL onayı yerine geçmez. V2 chart git root ve pinli candlestick SHA korunur.
4. Boşluğu doğrulanmış ayrı localhost portunda önce production app başlatılır. Örnek: `<new-venv>\Scripts\python.exe -m uvicorn forex.api:app --app-dir <immutable-release> --host 127.0.0.1 --port 18006`. Reload ve fixture wrapper kullanılmaz. Bu canlı aday komutu bu görevde çalıştırılmadı.
5. Fresh aynı interpreter başlangıcında `forex.api`, `forex.broker_contract`, `forex.spread_policy` importlarından sonra `loaded_fingerprint()` özel local manifestte exact release SHA, safe dependency versiyonları ve startup kimliğiyle tutulur. Ayrı interpreterdan alınmış fingerprint çalışan servise mal edilmez. Env değerleri/command line/account identifier loglanmaz. Uvicorn embedded başlatılacaksa manifesti yazan wrapper aynı interpreterdan `uvicorn.run(app,...)` çağırır.
6. Exact account preflight önce/sonra aynı olmalı. Health/symbols, manual V5, risk safety, schema ve source pins kontrol edilir. REAL balance kullanılmaz. Spread UNAPPROVED ve tarihsel session eksikse ret beklenen sonuçtur. İki yeni güven alanı yanıtta bulunmalı; execution false kalmalı. Canlı BUY/SELL veya formasyon bulma zorunlu değildir.
7. Ayrı operatör onaylı bakım adımında yalnız eski 8006 kimliği tekrar doğrulanıp yeni release/env 8006'ya alınır. Bu görev bunu yapmadı. 8005, 5173 ve özellikle başka iş akışının 8007 süreci korunur. Sonra local/Tailscale schema + manuel istek kontrol edilir; PWA feature kabulü ayrı handoff'a göre yapılır.

## Rollback ve engeller

Yeni süreç başarısızsa yalnız yeni sürecin kimliğiyle kapatılır; güvenli saklanan eski source/env/launch configuration ile eski 8006 geri alınır. Git reset/global paket değişimi gerekmez. Sadece sanitize PID/executable özeti tam restore komutu değildir; eski private config operatörce saklanmadan cutover yapılmamalıdır. Geçmiş Git recovery ref, runtime restore'un yerine geçmez.

Teknik test/operasyon planı hazır. Canlı plan uygunluğu ayrı: dört spread limiti UNAPPROVED; exact XAUUSDc tarihsel seans kanıtı BLOCKED_BY_EXTERNAL_EVIDENCE; hukuki market/contract türü tarihsel olarak doğrulanmadı. Operasyonel restart için ayrı yetki gerekir. Bu engeller kaynağın izole çalıştırılmasını ve güvenli ret kabulünü durdurmaz.
