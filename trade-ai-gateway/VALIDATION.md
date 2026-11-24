# Gateway 0.1.0 doğrulaması — 26 Ekim 2026

**Yerel entegrasyon test edildi; gerçek telefon-PC bağlantısı bekliyor.**

Backend: FatihBirgul/trade-ai, trade-ai-v2, `022e3e2173f2448de089945a41956517a643eb40`.
Kod salt okunur referans kopyasıyla çalıştırıldı; uzak backend deposuna/branch'e/DB'ye yazılmadı.
Android üretim API kaynakları: `cccdf5b80990a00c71b3a5d46cd671064701a3fc`;
kilit düzeltmesi `0e2e84ca52f27ec9116e8ade78cfe86c54307455` uygulama API davranışını değiştirmez.

## Gerçekleştirilen kontroller

- Python 3.12: 29 pytest testi başarılı (26 birim/güvenlik/yerel kontrol, 3 gerçek V2 entegrasyonu).
- Backend entegrasyonu yeni geçici SQLite DB'lerde; tüm fixture veriler fixture modunda etiketli.
- BTCUSDT/ETHUSDT/SOLUSDT analiz, geçmiş/detay, immutable snapshot mumları,
  idempotency ve 409, AUTO/MANUAL hareket/bakiye/performance okumaları doğrulandı.
- Provider unavailable testi canlı-mod sözleşmesinde kontrollü unavailable sağlayıcıyla
  gerçek V2 uygulamasını çalıştırdı: WAIT, price=null, levels=null; fiyat uydurulmadı.
- Android üretim API istemcisi gerçek yerel HTTPS soketi üzerinden gateway'e bağlandı.
  Geçici CA açıkça güvenildi; TLS sertifika/hostname doğrulaması kapatılmadı.
  Eşleştirme/replay, yanlış oturum, metadata, markets, WAIT, aynı anahtarla tekrar,
  history/detail, hesaplar, jobs/watchlist/notifications/performance ve gateway-off doğrulandı.
- Scanner yazma yetkisi olmayan cihaz reddedildi. Ayrı yetki verilmiş fixture cihazında
  watch auto_paper=true girişi false olarak zorlandı, pause/tick çalıştı ve AUTO emirleri boş kaldı.
- Yanlış/süresi dolmuş/iptal edilmiş oturum; cevap beklerken iptal; yasak endpoint/metot,
  yanlış hesap, private peer/origin/HTTPS kontrolü, bozuk/çok büyük JSON, kapalı upstream,
  timeout, redirect, 409/503 ve backend token echo reddi test edildi.
- Tek hesapla yetkilendirilen cihazın diğer hesabın analiz detayı/snapshot erişimi reddedildi; analiz listesi filtrelendi. Hesap atfı doğrulanamayan notification okuması kısıtlı oturumda kapalı.
- Pinned referanstaki 38 backend kaynak dosyasının Git blob hashleri uzak checkpoint ile birebir doğrulandı.
- Yerel kapatma yalnız kendi PID/run_id kaydını kabul eder; başka süreç öldürmez.
- Python compileall başarılı; kaynaklar Python 3.11 grameriyle de ayrıştırıldı.

## Henüz yapılmayanlar

- Gerçek Windows/Python 3.11 çalıştırması, PowerShell betikleri, gerçek Tailscale Serve,
  telefonun Android SecureStore kalıcılığı, gerçek piyasa sağlayıcısı bağlantısı ve yerinde APK güncellemesi.
- Yeni gateway PRIVATE GitHub deposu oluşturma: mevcut bağlantıda create-repository aracı yoktur.
  Bağımsız kaynak ve git bundle ZIP içinde teslim edilir; README aktarımı açıklar.
- Otomatik Windows servisi kurulmadı. Arka plan başlangıç veya firewall değişimi yapılmadı.

## Kaynaklar

Resmî Serve CLI ve örnekleri 26 Ekim 2026'da kontrol edildi:
https://tailscale.com/docs/reference/tailscale-cli/serve
https://tailscale.com/docs/reference/examples/serve

Resmî kaynak kodunda HTTP proxy'nin gelen Host'u koruduğu ve HTTPS için
X-Forwarded-Proto=https eklediği kontrol edildi:
https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go
Bu, gerçek kullanıcı cihazında Serve kurulumu testi olduğu anlamına gelmez.

## Task 5 / 0.1.1 (2026-10-26)

- Python 3.12 local: **35 passed**, including all 6 real-backend integration tests.
- Matrix: BTCUSDT/ETHUSDT/SOLUSDT × 1m/5m/15m/1H/4H/1D, actual V2 engine,
  four strategies, MTF, indicators, immutable snapshot/history. Quality cases
  stale/gap/unfinished/mixed return WAIT without levels.
- Temporary paper DB: create, deliberate committed-but-lost acknowledgement,
  restart, same-key reconciliation (one order), changed-body 409, cancel replay,
  queued close (still open until event), event replay, fill/close transactions,
  account pause and AUTO/MANUAL isolation. Default closed gate separately tested.
- Actual Android production TypeScript API modules → CA-verified local TLS
  gateway → unchanged V2 app: both unavailable-provider and controlled synthetic
  positive-provider runs passed. Controlled positive test also uses a filesystem
  journal, lost acknowledgement, journal restart/recovery, create/cancel, scanner
  watch/timeframe/tick/jobs/pending outbox. No external market was contacted.
- Command (from gateway source):
  `python scripts/test_android_https.py --backend ../backend-reference --android ../trade-ai-android --controlled`
  Omit `--controlled` for the unavailable-provider scenario. Temporary self-signed
  CA is explicitly trusted only by the test transport; certificate/hostname
  verification is enabled. Test paper flags/grants never enter CLI/Windows setup.
- Gateway GitHub Actions runs Python 3.11 and 3.12 unit/security checks; absent a
  private reference checkout, 6 backend tests are explicitly skipped there.
- Physical Android SecureStore, upgrade persistence, real Windows/Tailscale and
  live provider connectivity remain unverified. No user network changes made.
