# Bir sonraki yetkili runtime geçişi

Broker/spread readiness güncellemesi: sonraki operasyonda `V3_RUNTIME_CUTOVER_READINESS.md` esas alınmalı. REAL için eski MT5_MAX_SPREAD çıplak değerleri artık onay değildir; typed MT5_SPREAD_POLICY_FILE gerekir. Kullanıcı henüz limit onaylamadı; null/onaysız template BLOCK kalır. Aşağıdaki önceki P1 planı tarihsel bağlamdır; servisler bu görevde restart edilmedi.

11 Kasım 2026. Bu plan mevcut servisleri şimdi durdurmaz/restart etmez. QA araçları çalıştırıldı; canlı cutover yapılmadı. Üretim motoru değiştirilmedi.

## Mevcut kimlik ve hedef

8006 PID 7532, start 15:30:28 Europe/Istanbul; global Python 3.11 executable; `forex.api:app`, reload yok. Loaded-version VERSION_UNVERIFIED. Global interpreter NumPy 2.4.6 içeriyor; P1 chart bunu kabul etmez. Mevcut süreç içindeki gerçek NumPy/config ayrıca doğrulanmalı; disk paketi bellek kanıtı değildir.

Başlangıç kaynak `806ed902ba76d87523047d43eef396491b462cbb`; üzerine yalnız QA tools/belge commit'i gelir. V5 public kod SHA256 `e31b9f0a8b3759f53401d3df191dbe663017904ee0575db4b746610a5f172c31`. V2 commit `c80c97f227a2c233a610df669919ba2f464e4f9f`; chart SHA256 `af69112c91938c4bd6fea3d16f43a333f63c35ea3715ed082069868e1018f1ba`.

## Hazır fixture kabulü

Ana repo cwd'sinde izole Python 3.11/NumPy 2.2.6 ile `tools/runtime_acceptance/run.py --run-fixture-acceptance --output <ayrı-QA-dizini>` çalıştırılır. Port otomatik boş loopback portudur; 5173/8005/8006/8007 kullanılmaz. İki Python sürümünde 56 kontrol geçti. Fixture wrapper test senaryoları ve sentetik REAL policy içerir; canlı servis launcher'ı olarak kullanılmamalıdır.

## Ayrı deployment ortamı

Bir sonraki yetkili operasyonda mevcut servis ortamını değiştirmeden örneğin `%USERPROFILE%\.venvs\trade-ai-v3-p1-runtime` Python 3.11 venv'i oluştur. `requirements-test-py311.txt` pinlerini buraya kur; Windows MT5 bağımlılığını ayrıca pinle/doğrula. Makinede gözlenen MetaTrader5 5.0.6231. Bu görev yeni servis ortamına/global ortama kurulum yapmadı. `pip check`, NumPy 2.2.6 ve 487 regression başarılı olmadan canlı adaya geçilmez.

Kaynak immutable release klasörü olmalı. Tam yerel teslim SHA'sı için `git archive --format=zip --output=<yeni-release.zip> <SHA>` ile kaynak paketlenip yeni boş staging klasörüne açılabilir. Kullanıcı dosyası temizlenmez; branch reset veya global downgrade gerekmez. Source/dependency manifestleri sanitize olarak kaydedilir.

Yalnız aday sürecin ortamında gereken sözleşme:

| Değişken | Değer / kontrol |
|---|---|
| MT5_ANALYSIS_POLICY | REAL_READONLY_DATA |
| MT5_EXPECTED_REAL_SERVER | Exness-MT5Real50 exact |
| MT5_EXPECTED_REAL_CURRENCY | USC exact |
| MT5_SYMBOL_MAP | XAUUSD:XAUUSDc, EURUSD:EURUSDc, GBPUSD:GBPUSDc, USDJPY:USDJPYc; geçerli JSON |
| MT5_MAX_SPREAD | Dört canonical sembol için bağımsız onaylı pozitif fiyat birimli limitler. Şu an null; değer uydurma. |
| V2_CHART_GIT_ROOT | %USERPROFILE%\trade-ai-v2-antigravity; pinli nesne/SHA okunabilir |
| V2_CANDLESTICK_FILE / V2_CANDLESTICK_SHA256 | Mevcut pinli kaynak korunur. QA aynı V2 commitinden immutable blob SHA256 45ee833fd3a5ffd178a4ee565e5914f79e9fb0b1c2aa62fe16b703057f63542c doğruladı. Kirli çalışma dosyasından otomatik yeni güven üretme. |
| MT5_BROKER_HOURS | Operatör beyanı geçmiş REAL boşluklarını açmaz; XAUUSD saatleri XAUUSDc'ye kopyalanmaz. |

API'ye credential env veya hesap değişimi gerekmez. Mevcut terminal exact read-only preflight ile doğrulanır; gerçek balance sermaye olmaz. Aday süreç 8005 hesabını veya mevcut 8006 ortamını değiştirmemeli.

## Canlı aday ve tek seferlik geçiş

1. Kullanılabilir ayrı loopback portu doğrulandıktan sonra örneğin 18006'da üretim uygulaması başlatılır: `<yeni-venv>\Scripts\python.exe -m uvicorn forex.api:app --app-dir <immutable-release> --host 127.0.0.1 --port 18006`. Reload ve fixture wrapper kullanılmaz. Bu komut bu görevde çalıştırılmadı.
2. Başlangıç source SHA, loaded modül yolları/hash'leri, dependency seti, PID/parent/start time ve sanitize config özel yerel manifestte tutulur. Public schema/hash loaded-version kanıtı sayılmaz. Parola/token/account number kaydedilmez. Teslimdeki fixture manifesti çalışan bir örnektir; public tanılama endpoint'i eklenmez.
3. Exact REAL preflight, health/symbols ve manuel V5 isteği yapılır. Balance yerine explicit hypothetical_capital/hypothetical_currency; önce/sonra hesap aynı; execution false. Source/NumPy mismatch testi yalnız fixture/adaya uygulanır, mevcut servis config'i bozulmaz.
4. Tarihsel XAUUSDc kanıtı yoksa INSUFFICIENT_DATA beklenen ret; chart null olabilir. Canlı formasyon bulunması garanti edilmez. max_spread null ve market/contract unverified ayrıca açık engellerdir; gevşetilmez.
5. Ayrı frontend handoff ve aday kabulünden sonra, yalnız yetkili bakım adımında eski 8006 kimliği yeniden doğrulanır. Tam private launch config güvenli operatör kaydına alınır; eski süreç kontrollü durdurulup doğrulanan release/env 8006'ya bağlanır. 5173/8005/8007 korunur. Bu görevde bu operasyon yapılmadı.
6. /engine aynı 8006 adresini korur; local/Tailscale health/schema/manual analysis kontrol edilir. 8005/8006 alias/provider/as-of tutarlılığı hesap ID göstermeden doğrulanır. Telefon/PWA/service-worker kabulü ayrıca yapılır.

## Rollback

Yeni servis health/contract/preflight başarısızsa yalnız yeni başlatılan süreç kimliğiyle durdurulur; önceden kaydedilmiş eski executable/source/environment ile eski servis yeniden kurulur. Global paket veya Git reset yapılmaz. Eski immutable release/env korunur. Sanitize PID/executable özeti tam restore komutu değildir; tam private launch config operatör tarafından güvenli saklanmadan cutover başlamamalı. Git recovery ref `refs/recovery/p1-main-20261111-3107aacf306d` kaynak incelemesidir; çalışan süreci tek başına geri yüklemez.

## Kullanıcıdan gereken en az dış girdi

Exact XAUUSDc, Exness-MT5Real50 kapsamlı 9 Kasım 2026 tarihsel quote/trade ve UTC/DST/holiday kanıtı gerekir. Onaylı spread/instrument sözleşmesi null/unverified alanları kaynakla tamamlamalıdır. Sonra ayrı yetkili runtime geçişi ve frontend değişikliği planlanır. Haftalık MQL5 export tek başına tarihsel kanıt değildir. Terminal hesabını değiştirmek veya emir göndermek gerekmez.
