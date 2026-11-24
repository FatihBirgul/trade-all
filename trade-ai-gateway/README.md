# Trade AI Gateway — Görev 6 geliştirme dalı

Bağımsız Python 3.11+ servisi. Android APK'sına eklenmez. Backend deposunu değiştirmez.
Upstream sabittir: `http://127.0.0.1:8002`. Gateway yalnız `127.0.0.1:8787` üzerinde dinler.
HTTPS uç noktası kullanıcının kendi bilgisayarında **Tailscale Serve** tarafından sonlandırılır.
Tailnet erişimi ayrıca 24 saatlik, iptal edilebilir mobil oturum gerektirir.

**Güncelleme:** Kaynaklar PRIVATE depodaki `codex/gateway-continuity-20261026` dalındadır.
Yeni Android 0.5.0 ile önce Gateway'i ve backend'in `codex/v2-mobile-quotes-20261026`
dalını PC'de bilinçli olarak güncelleyin. Main/PR merge gerekmez. Servisleri normal
durdurun, mevcut DB/env/token ve kullanıcı ACL'lerini koruyarak tutarlı yedek alın.
Yerel değişiklik varsa üzerine yazmayın; ayrı checkout kullanıp mevcut DB yollarını
açıkça belirtin. Yeni checkout'un boş DB ile eski cihaz/hesap kayıtlarını kaybetmesine
izin vermeyin. Gateway bağımlılıklarını `.venv\Scripts\python.exe -m pip install -e .`
ile kurup aynı loopback/HTTPS adresleriyle yeniden başlatın. Tailscale Serve eşlemesi
çalışıyorsa ağ ayarını değiştirmeniz gerekmez.

Kullanıcı 0.4.0 analiz/geçmiş/portföy/scanner akışlarını kendi telefon-PC zincirinde
doğruladı. Yeni yenileme, quotes ve scanner recovery yerel kontrollü testlidir;
0.5.0 fiziksel cihaz doğrulaması bekler. Bu geliştirmede PC'ye işlem yapılmadı.

## Windows kurulumu

1. Mevcut `trade-ai` deposunun `codex/v2-mobile-quotes-20261026` geliştirme dalını kullanın. Backend yönergesi
   `docs/V2_WINDOWS_SETUP.md`; salt okunur referansı `contracts/V2_WINDOWS_SETUP.md` içindedir.
   Python 3.11 ve ayrı mevcut V2 canlı veritabanı ile backend'i `127.0.0.1:8002` üzerinde
   başlatın. Fixture ve canlı DB'leri karıştırmayın. Backend token'ını burada veya Android'de paylaşmayın.
2. Bu bağımsız kaynak klasöründe PowerShell: `py -3.11 -m venv .venv`, ardından
   `.\.venv\Scripts\python.exe -m pip install -e .`.
3. PC ve telefonda kendi Tailscale hesabınızla oturum açın; yalnız kendi cihazlarınıza erişim
   sağlayan tailnet kurallarını kontrol edin. Bu adım kullanıcı tarafından gerçekleştirilir.
4. Tailscale'in verdiği kendi `https://PC.TAILNET.ts.net` adresi ile:
   `.\scripts\Start-Gateway.ps1 -PublicOrigin 'https://PC.TAILNET.ts.net'`.
   Gateway backend token'ını gizli yerel prompt ile ister. Aynı PowerShell'de önceden
   ayarlanmış `V2_API_TOKEN` varsa onu kullanır; komut argümanına/URL'ye/yapılandırma
   dosyasına token yazılmaz. Otomatik servis kurulmaz; terminal açık kalır.
5. Ayrı terminalde `scripts/Serve-Private.ps1` betiğini inceleyip çalıştırın. Önce
   `tailscale serve status` ile mevcut eşlemeleri kontrol eder ve kullanıcıdan EVET ister.
   Komut: `tailscale serve --https=443 http://127.0.0.1:8787`.
   Bu özel Serve eşlemesidir; Funnel değildir. Var olan başka 443 eşlemesini üzerine yazmayın.
   HTTPS/tailnet izinlerini Tailscale'in resmî ekranında kullanıcı doğrular.
6. Başka terminalde `.\scripts\Pair-Device.ps1`. Görünen rastgele kod tek kullanımlık ve
   120 saniyeliktir. Android 0.5.0 Ayarlar ekranında HTTPS adresini, kodu ve cihaz adını
   girin; bağlantıyı test edin. Sağlık **ve** mobil oturum doğrulanınca CANLI seçilebilir.
   `provider_status=not_probed` piyasa sağlayıcısının çalıştığı anlamına gelmez; ilk analiz
   gerçek veri yoksa WAIT döner. Sunucudaki gerçek token telefona asla girilmez.
7. Oturum listesi: `.\.venv\Scripts\python.exe -m trade_gateway sessions`.
   İptal: `.\.venv\Scripts\python.exe -m trade_gateway revoke OTURUM_ID`.
   Her telefon ayrı rastgele cihaz kimliği ve oturum alır. Aynı cihaz yeniden eşleşirse eski
   oturumu iptal edilir. Eski oturumlar bir kez yeni yerel kodla eşleştirilmelidir. Yeni yenileme yetkisi
   30 günlük mutlak süre içinde 24 saatlik erişimi yeniler; iptal/süre sonu yeniden
   yerel eşleştirme gerektirir. Scanner gerekiyorsa kodu yerelde açık `--scanner-write`
   grant ile üretin; yenileme eski yetkileri genişletmez. Varsayılan parola yoktur.
8. Durdurmak için gateway ve ön plandaki Serve terminallerinde ayrı ayrı Ctrl+C kullanın.
   `Stop-Gateway.ps1` yerel run_id doğrulamalı kontrol dosyası ile gateway’i normal kapatır; PID öldürmez ve backend’e dokunmaz.
   Daha önce `--bg` kullanıldıysa yalnız bu gateway'e ait eşlemeyi, resmî CLI yönergesine göre
   `tailscale serve --https=443 off` ile durdurun; toplu `reset` kullanmayın.

Bu betikler hazırlanmıştır, gerçek Windows bilgisayarda çalıştırılmamıştır. Script policy
engeli varsa sistem policy'sini düşürmek yerine betikteki Python komutlarını elle çalıştırın.
Firewall kapatılmaz, modem portu açılmaz, backend `0.0.0.0`'a bağlanmaz.
Aynı PC üzerindeki yerel süreçler güven sınırının içindedir; PC'nin ele geçirilmesine karşı
bu uygulama bir işletim sistemi güvenlik ürünü değildir. Gateway DB'sini kullanıcıya özel
klasörde tutun. `chmod` Windows DACL yerine geçmez. DB yalnız token/kod hashlerini tutar.

Kontrol kaydı `local_data/gateway.pid.json` içindedir. PC/işlem sert kapanırsa bu dosya
kalabilir; çalışan gateway olmadığını doğrulamadan silmeyin. Normal kapanış kaydı temizler.
Betikler gerçek Windows üzerinde henüz denenmedi; yerel kontrol mekanizması birim testlidir.

## İzin verilen işlemler

`GET /api/v2/health`, `/markets`, `/quotes`, `/analyses`, `/analyses/{id}`, `/analyses/{id}/candles`,
`/portfolios` ve hesap altındaki orders/positions/transactions okumaları,
`/performance`, `/scanner`, `/scanner/jobs`, `/watchlist`, `/notifications`.
Kısıtlı tek-hesap oturumunda analiz listesi filtrelenir; detay ve mum isteği analizdeki
risk hesabı üzerinden yetkilendirilir. Hesap atfı garanti edilemeyen pending bildirim
okuması kısıtlı oturumda kapalıdır. Varsayılan kişisel oturum iki hesaba yetkilidir.
`POST /api/v2/analyze` ayrı analyze yetkisi ister; `auto_paper=false` sunucuda zorlanır.
Scanner pause/tick/watchlist yazmaları ancak yerelde `pair --scanner-write` ile açıkça verilen
ayrı yetkiyle kullanılabilir. İlk telefon kurulumunda bu yetkiyi vermeyin.
`/paper/events`, `/paper/poll`, sanal emir oluşturma/kapatma/iptal ve tüm diğer yazmalar
bu sürümde gateway'de kapalıdır. Android IntentJournal korunmuştur; sanal emir UI'sı açılmaz.

## Güvenlik sınırları

- Ayrı mobil token 256 bit rastgele; eşleştirme kodu 192 bit rastgele. DB'de SHA-256 hashleri.
- Tek kullanımlık kod tüketimi ve hız sınırı SQLite `BEGIN IMMEDIATE` ile atomiktir.
- Her oturum hesap ve scope listesi taşır; mobil istek bunları genişletemez.
- İstemci Authorization değeri upstream'e aktarılmaz; yalnız gateway sunucu token'ı eklenir.
- Yalnız sabit loopback hedefi, redirects kapalı, ortam HTTP proxy'si kapalı.
- 16 KiB istek, 2 MB yanıt, iki eşzamanlı upstream istek, 10 s toplam upstream timeout; yalnız scanner tick için 45 s.
- Dakikada 240 global istek, 5 eşleştirme denemesi, oturum başına 6 analiz / 60 okuma.
- Hassas gövde/Authorization/kod/exception metni loglanmaz; access log kapalıdır.
- Upstream hataları sabit Türkçe metne çevrilir; Set-Cookie/Location/debug header aktarılmaz.
- V2 OpenAPI yanıtları ve data_mode doğrulanır; production CLI yalnız live modu kabul eder.
- Gelen oturum yanıt verilmeden önce tekrar kontrol edilir; iptal/expiry eski sonucu kapatır.

`expected_mode='fixture'` yalnız Python test factory'sinin açık test ayarıdır; production
CLI'da böyle bir seçenek yoktur. Fixture yanıtları canlı diye yeniden etiketlenmez.

## Testler

`python -m pip install -e '.[test]'`, sonra `python -m pytest -q`.
Gerçek backend entegrasyonu için salt okunur `codex/v2-mobile-quotes-20261026`
checkout yolunu `TRADE_AI_BACKEND_REFERENCE` olarak verin ve backend bağımlılıklarını aynı
ayrı test ortamına yükleyin. Bu yol yoksa yedi entegrasyon testi açıkça SKIP olur.
Testler yalnız pytest tmp_path altında yeni DB kullanır; mevcut product DB'ye erişmez.

Üretim Android API modülleriyle TLS socket zinciri:
`python scripts/test_android_https.py --backend BACKEND_CHECKOUT --android ANDROID_CHECKOUT`.
Android checkout'ta `npm ci`, test ortamında OpenSSL ve Node 24 gerekir. Kendine ait geçici
CA/cert kullanır, sertifika doğrulamasını kapatmaz; yalnız 127.0.0.1:8002/8787 üzerinde
izole süreçler başlatır. Bu portları başka uygulama kullanıyorsa testi çalıştırmayın.
Kontrollü live-provider-unavailable backend kullanır; gerçek borsa bağlantısı testi değildir.

## Kaynak geçmişi

Kod mevcut PRIVATE `FatihBirgul/trade-ai-gateway` deposunda korunur.
Görev 6 geliştirme dalı `codex/gateway-continuity-20261026`, PR #1 açıktır.
Eski ZIP/bundle aktarımını yeniden çalıştırmayın. Force-push, main merge ve sır
içeren env/DB/sertifika/anahtar commit'i yapılmaz.

Resmî Tailscale kaynakları 26 Ekim 2026'da kontrol edildi:
- https://tailscale.com/docs/reference/tailscale-cli/serve
- https://tailscale.com/docs/features/tailscale-serve
- https://tailscale.com/docs/reference/examples/serve

## 0.1.1 paper integration boundary

Default production CLI continues to reject all portfolio POSTs. The Python app
factory has a default-false `paper_writes_enabled` flag, and sessions need a
separate `paper:write` grant. Neither is enabled by the Windows scripts/CLI.
Only isolated integration tests enable both, using temporary databases.
Create validates the analysis risk account; cancel/close validate response IDs;
all existing API request/response validation, expiry/revoke and account checks apply.
No paper/events or paper/poll route is exposed, even with the paper grant.
A pending close acknowledgement never means that an exit was filled.

Mobile scanner ticks preflight the existing watchlist and reject enabled
`auto_paper=true` entries with 409. The PC backend can independently change this
configuration: its contract has no atomic per-tick no-order override. Do not run
concurrent local auto-order watch changes during mobile testing. Automatic paper
execution is not a verified mobile feature. Scanner writes require AUTO account
scope because V2 scanner analyses use AUTO.

Additional local tests execute the unmodified pinned V2 application through the
gateway: all three symbols × six analysis timeframes, MTF, four strategies,
immutable candles/history, invalid-data WAIT, scanner jobs/outbox, and paper
create/lost-ack/restart/replay/cancel/queued-close/fill/account isolation.
Reference checkout is read-only. `TRADE_AI_BACKEND_REFERENCE` selects it. Without
that variable pytest explicitly skips backend integration tests; CI unit results
must not be reported as the complete integration run.

## Device renewal (Task 6)

A new Android pairing requests `renewal: true`. Pairing still needs the one-use
120-second local code. Existing sessions are never silently upgraded: re-pair
once after updating gateway/Android. Access remains 24 hours. The separate
per-device renewal family expires absolutely 30 days after pairing; rotation
never extends this deadline. Pairing again or CLI revoke of ANY family session
revokes all descendants. Other devices remain independent.

`POST /gateway/refresh` accepts only the current refresh token, device ID,
cryptographic request ID, and client-proposed next access/refresh credentials.
The client durably saves these successors in SecureStore before the request.
SQLite stores only credential hashes. Rotation is atomic. Exact replay returns
only the same metadata, without minting credentials or extending expiry. A used
refresh token with a different proposal revokes the entire family. Lost response
recovery can acknowledge an expired access receipt and then rotate the known
successor; revoked/expired families require local pairing. Scopes/accounts are
copied from the initial grant, never accepted from refresh input.

Backup the gateway DB using SQLite online backup while the service is active,
or copy it only after a graceful stop; preserve Windows user ACLs. It contains
hashes and device metadata, not backend secrets. Never commit or share this DB.
A backup rollback can invalidate renewal state: do not guess or issue new keys;
re-pair affected devices locally. No execution policy change is required: use
`py -3.11 -m venv .venv`, `.venv\Scripts\python.exe -m pip install -e .`, then
set `GATEWAY_PUBLIC_ORIGIN` in the current terminal and run
`.venv\Scripts\python.exe -m trade_gateway serve`. The backend token is entered
in the hidden local prompt. Tailscale Serve remains a separate foreground process.

## Analiz takip asistanı

Güncel backend dalındaki `docs/V2_ANALYSIS_FOLLOW.md` kurulum/sınır belgesini okuyun.
Backend işçisi `--tracking` ile açıkça başlatılır; kayıt oluşturmak işçiyi açmaz.
Mobil takip yazmaları mevcut `scanner:write` grant ve origin hesabını gerektirir.
Gateway önce origin/hesap yetkisini doğrular, istemci URL hedefi seçemez.
Pending outbox push teslimatı değildir; paper yazma bayrakları kapalı kalır.
Yeni sürüm fiziksel telefon/PC doğrulaması bekler.

### Product strategy profiles (development increment)

Adds `strategy-profiles-v1` session capability and a separate optional
`pair --profiles-write` grant. Existing pairings/sessions never receive this grant
implicitly; paper/scanner scopes do not authorize profile writes. Account-scoped
profile reads and saved-snapshot evaluation use `read`. Creation/revision require
`profiles:write`; paper writes remain governed by their existing disabled-by-default
switch. Backend still validates account, immutable revision and safe analysis filter.

Contract:31 Backend paths/39 schemas (additive; existing26 operations unchanged,
only AnalyzeRequest gains an optional profile_id). Requires the matching product
Backend branch/PR. Old backend endpoint errors remain errors, never success.

Local integration with a pinned, accessible private Backend checkout:
`TRADE_AI_BACKEND_REFERENCE=/workspace/trade-ai python -m pytest -q`.
No CI credential for cross-private-repo checkout is introduced; default CI explicitly
skips those integration tests, while route/scope unit tests run normally.
Rollback: revert this branch's code to the previous Gateway build; no existing
session grants, Backend financial records or live services are rewritten.

M17: optional WatchRequest.profile_id binds an AUTO revision; mobile watch writes
require AUTO account plus scanner:write. MANUAL-only scanner grants previously
could modify shared AUTO watches (reproduced200 before fix); now403 before upstream.
Bound profile watches are omitted from MANUAL-only read results. New capability
profile-scanner-v1. Real Backend integration47passed; standalone CI38passed/9skipped
(private Backend checkout). Profile permission remains independent of scanner scope.

Compatibility follow-up: watchlist include_profile=true is opt-in; default wire
bodies remain compatible with old Android schemas. Old updates without profile_id
preserve existing bindings. Real Backend/Gateway integration covers opt-in read,
AUTO binding, forced auto_paper=false and a legacy-client pause cycle.47passed.
The lost-ack timeout test had one scheduler-sensitive60ms sleep failure under CPU
load; replaced only that assumption with a bounded worker-completion event. Original
HTTP deadlines,504/200 results and both persisted-job assertions remain intact.
Current default CI38passed/9explicit private-backend skips. No auth rule weakened.

Response binding hardening: a profile-bound analyze response must carry the same
immutable profile_record_id; otherwise Gateway returns502. An actual Backend ASGI
response with only that proof removed reproduced200 before fix. Profile conflict/
timeframe/version errors retain safe public codes, with generic redacted messages.
Local integrated48passed; standalone38passed/10explicit private-backend skips.

Continuation4: read-only account-scoped equity-history route, equity-history-v1
capability, same account/mode checks for every nested point.32paths/41schemas match
Backend/Android. No new write grant. Real Backend ASGI suite49passed; private
checkout integration tests remain explicit skips in standalone CI. No live services
or devices touched. Backward-compatible older Backend404 returns update-required.

Follow source-event policy (capability follow-source-events-v1) adds explicit,
default-off per-follow preferences. Reads require account ownership/read; writes
use existing scanner:write and fetch the owning TrackingResponse before forwarding.
No scope is added to a session. Source TTL/dedup remains Backend-owned. Contract
33paths/43schemas matches both companion repositories.49realASGI tests passed,
including reader/foreign-account denial, strict boolean, idempotent policy setting.
