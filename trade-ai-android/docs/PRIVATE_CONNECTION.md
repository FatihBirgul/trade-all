# Android 0.3.0 — özel gateway bağlantısı

Backend kaynak checkpoint'i: `022e3e2173f2448de089945a41956517a643eb40`, `trade-ai-v2`.
Android önceki checkpoint'i `9fc92d517a002d3cb60c11c4e7c295cea0622482` korunur.
Backend kodu, kalıcı DB, branch veya kullanıcının bilgisayarındaki ağ ayarları değiştirilmedi.

**Yerel entegrasyon test edildi; gerçek telefon-PC bağlantısı bekliyor.**

Gateway ayrı Python kaynak paketidir; Android projesi veya APK içine konmaz. Mevcut
GitHub bağlantısı yeni PRIVATE depo oluşturma aracı sunmadığı için bağımsız kaynak
ZIP ve git bundle teslim edilir. Gateway paketinin README'sinde kurulum ve PRIVATE
`FatihBirgul/trade-ai-gateway` deposuna güvenli aktarım adımları vardır.

## Kullanıcı bilgisayarında

1. Python 3.11 ile mevcut backend'i kendi `docs/V2_WINDOWS_SETUP.md` yönergesine göre
   `127.0.0.1:8002` üzerinde live modunda, mevcut V2 DB ile başlatın.
2. Gateway paketini ayrı klasöre çıkarın. README'deki venv kurulumunu yapın ve
   `Start-Gateway.ps1 -PublicOrigin 'https://PC.TAILNET.ts.net'` çalıştırın. Gerçek backend
   token'ı yalnız bu bilgisayardaki gizli prompt'a girilir; telefona/sohbete/GitHub'a girilmez.
3. PC ve telefon aynı özel Tailscale ağına bağlanır. Kullanıcı erişim kurallarını kontrol
   eder. Gateway paketindeki `Serve-Private.ps1`, mevcut eşlemeleri gösterip onay aldıktan
   sonra ön planda `tailscale serve --https=443 http://127.0.0.1:8787` başlatır.
   Funnel, modem port yönlendirme veya firewall kapatma yoktur.
4. PC'de `Pair-Device.ps1` ile 120 saniyelik tek kullanımlık kod alın. Android Ayarlar'da
   aynı HTTPS adresini, kodu ve cihaz adını girip bağlantıyı test edin. Mobil metadata ve
   backend sağlık yanıtı birlikte doğrulanınca CANLI modunu seçin.
5. BTCUSDT analizi alın. HTTP 200 tek başına sinyal değildir; `provider_unavailable`
   durumunda WAIT, boş fiyat/indikatör ve kapalı işlem seviyeleri beklenir.
6. İptal için gateway CLI `sessions` ve `revoke OTURUM_ID` komutlarını kullanın.
   Gateway/Serve ön plan terminallerinde Ctrl+C yalnız ilgili hizmetleri durdurur.

Her eşleştirme ayrı cihaz kimliği ve 24 saatlik opak mobil oturum alır. Token SecureStore'da,
sunucuda yalnız hash olarak tutulur. Yeni açılış her zaman DEMO başlar; kayıtlı oturumla
sağlık/kimlik doğrulama yeniden yapılır. 401/403 veya süre sonu CANLI erişimini kapatır ve
kalıcı, açık Türkçe uyarı gösterir; sessiz DEMO veri ikamesi yapılmaz.

## Yazma sınırı

`auto_paper=false` istemci ve gateway tarafından zorlanır. Gateway'de emir
oluşturma/iptal/kapatma, `/paper/events` ve `/paper/poll` kapalıdır. Native IntentJournal
korunur. Scanner yazmaları yalnız PC'de ayrı `--scanner-write` yetkisiyle eşleşen
cihazda kullanılabilir; ilk telefon kurulumunda bu yetki verilmemesi önerilir.

## Doğrulama sınıfları

- Android birim/UI: mevcut testler + oturum metadata, tek kullanımlık eşleştirme,
  eski oturum isteğinin geç yanıtı ve immutable snapshot eşleşmesi.
- Gateway birim/güvenlik: auth hash/expiry/revoke, tek kullanım, allowlist, scope,
  boyut/hız/timeout, kapalı backend, bozuk JSON, 409/503, token/header sızmaması.
- Gerçek V2 fixture uygulaması: geçici DB ile BTC/ETH/SOL, idempotency, kayıtlı mumlar,
  geçmiş, hesaplar ve scanner/performans/pending notification okumaları.
- Gerçek TLS soketi: üretim Android API modülleri → CA doğrulamalı yerel HTTPS gateway
  → değiştirilmemiş V2 backend; kontrollü unavailable sağlayıcı ile WAIT. Gerçek piyasa
  bağlantısı olduğu iddia edilmez. Sertifika doğrulaması kapatılmamıştır.
- Kullanıcı PC/telefon: Windows başlatma, gerçek Tailscale Serve, gerçek sağlayıcı,
  SecureStore cihaz kalıcılığı, yerinde APK güncellemesi ve erişim iptali bekliyor.

Resmî Serve komutları 26 Ekim 2026'da kontrol edildi:
https://tailscale.com/docs/reference/tailscale-cli/serve

## Expo Doctor ağ engeli

Bu oturumda tam Expo Doctor tamamlanamadı. Otomatik onay incelemesi cdp.expo.dev
telemetri ve exp.host çevrimiçi kontrol isteklerini, payload bilinmediği ve proje
metadata'sı paylaşımı için açık izin olmadığı gerekçesiyle reddetti. Telemetri ve
offline bayraklarına rağmen Doctor exp.host isteği denedi; tekrar denenmedi.
Ağ paylaşımı yapmayan `npm run doctor:local` bağımlılık/lock/kurulu Expo SDK uyumunu
ve sürüm/konfigürasyon ayrımını denetler. Bu komut Expo Doctor'un 20/20 sonucu diye
sunulmaz. CI da bu yerel kontrolü kullanır. Tam Doctor'un ağ kontrolleri kullanıcı
onayı bekleyen ayrı doğrulamadır.
