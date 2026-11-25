# Trade Bot — Android

0.8.0 sürümünden itibaren görünen sekmeler sunucuda çalışan trade botunu (`trade-bot/`) denetler:

- **Panel:** bakiye, varlık, bugünkü kâr/zarar (bot / elle / toplam), bot durumu; Durdur, Devam, Hepsini kapat, Canlı moda geç / Deneme moduna dön. Her işlem onay ister; canlıya geçiş ve kayıp sınırı durmasından sonra devam iki ayrı onay ister.
- **Pozisyonlar:** açık pozisyonlar, SL/TP düzenleme (eski → yeni değer onayı; yanlış taraf ve fiyattan çok uzak seviye gönderilmez), kapatma, kademeli stop.
- **Bildirimler:** botun olay akışı (Önemli / Tümü); uygulama açıkken önemli olaylar için yerel bildirim.
- **Bağlantı:** sunucu adresi ve 6 haneli eşleştirme kodu. Kod sunucuda `sudo tradebot-pair` ile üretilir, 10 dakika geçerlidir.

Bağlantı anahtarı yalnızca telefonun güvenli deposunda tutulur. Deneme modunda bot emir göndermez; uygulamadan verdiğiniz kapatma ve SL/TP emirleri her zaman gerçek hesapta yapılır. Uygulama kapalıyken bildirim için Firebase yapılandırması (`google-services.json`) ve Expo proje kimliği gerekir; henüz yok.

## İmzalı APK (kalıcı anahtar)

APK iş akışı (`.github/workflows/android-apk.yml`) imza Secret'ları tanımlıysa APK'yı kalıcı anahtarınızla imzalar.
Tanımlı değilse APK, React Native şablonunun **herkesçe bilinen test anahtarıyla** imzalanır ve iş akışı bunu uyarı
olarak yazar. Bu sürümler birbirinin üstüne güncellenir, ama anahtar gizli olmadığı için aynı anahtarla imzalanmış
başka bir APK da uygulamanın üstüne kurulabilir: yalnızca deneme içindir, gerçek parayla kullanmadan önce kalıcı
anahtara geçin. Kalıcı anahtara ilk geçişte eski uygulamayı bir kez kaldırmanız gerekir; kaldırınca telefondaki
bağlantı anahtarı da silinir, sunucuda `sudo tradebot-pair` ile yeniden eşleştirirsiniz.

Anahtar deposunu bir kez, kendi bilgisayarınızda üretin (parolayı siz belirlersiniz; dosyayı ve parolayı saklayın —
kaybolursa uygulama bir daha güncellenemez):

```bash
keytool -genkeypair -v -keystore tradebot-release.keystore -alias tradebot -keyalg RSA -keysize 2048 -validity 10000
```

```bash
base64 -w0 tradebot-release.keystore
```

(macOS: `base64 -i tradebot-release.keystore`; Windows PowerShell:
`[Convert]::ToBase64String([IO.File]::ReadAllBytes("tradebot-release.keystore"))`.)

| Secret | Değer |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | ikinci komutun çıktısı |
| `ANDROID_KEYSTORE_PASSWORD` | anahtar deposu parolası |
| `ANDROID_KEY_ALIAS` | `tradebot` |
| `ANDROID_KEY_PASSWORD` | anahtar parolası (depo parolasıyla aynıysa bu Secret'ı hiç tanımlamayın) |

Anahtar deposu ve parolalar repoya, sohbete ya da uygulamaya yazılmaz.

Eski kripto analiz ekranları kod olarak duruyor ama sekme çubuğunda gösterilmiyor. Aşağıdaki bölümler o eski uygulamaya aittir.

---

## Eski uygulama (Trade AI 2.0)

React Native / Expo Android istemcisi. Bu depo yalnızca mobil ön yüzü içerir; backend deposu olan `FatihBirgul/trade-ai` ve `trade-ai-v2` dalı bu projeden bağımsızdır.

## İlk kapsam

- Türkçe, premium dark/light arayüz
- 5 sekme: Ana Sayfa, Analiz, Portföyler, Tarayıcı, Ayarlar
- Demo / Canlı mod ayrımı
- İstemcide sır veya API anahtarı tutmayan güvenli API katmanı

> Dahili APK GitHub Actions'ta üretildi. Fiziksel Android cihazda kurulum/açılış ve gerçek backend bağlantısı henüz test edilmedi.

## Güvenlik yaklaşımı

- Uygulama yalnızca kısa ömürlü kullanıcı oturum belirtecini güvenli depolamada saklar.
- Borsa anahtarları, servis sırları ve backend yönetici anahtarları mobil pakete konmaz.
- Canlı mod kapalı başlar; gerçek işlem uçları bu istemcide tanımlı değildir.
- HTTPS gateway adresi ve yalnız mobil oturum Ayarlar ekranından yapılandırılır. Gateway henüz kurulmamıştır; backend bearer token'ı telefona girilmez.

## Geliştirme ve doğrulama

Node 24 ile `npm ci`, sonra `npm start`. Kontroller: `npm run typecheck`, `npm run lint`, `npm test`, `npx expo-doctor`.

Beş Expo Router sekmesine ek olarak analiz geçmişi/detayı, performans ve bildirim ekranları vardır. API modelleri gerçek `docs/backend/V2_OPENAPI.json` belgesinden üretilmiştir. Hatalı canlı istekler demo başarıya çevrilmez; analiz otomatik emir oluşturmaz.

Güncel sonuçlar: [Doğrulama kaydı](docs/VALIDATION.md). [Özel gateway bağlantısı ve kullanıcı kurulum adımları](docs/PRIVATE_CONNECTION.md).

[0.3.0 iç test APK derlemesi](https://github.com/FatihBirgul/trade-ai-android/actions/runs/40279469216) başarılı: versionCode 4, arm64-v8a, gömülü JS, dahili debug imzası. Artifacts → trade-ai-internal-apk ZIP içinden APK kurulabilir; Metro sunucusu gerekmez. 0.2.2 ile imzalama sertifikası eşleşir. Fiziksel telefonda kurulum/yerinde güncelleme henüz test edilmedi.

Ayarlar ekranında backend tokenı girilmez. Kullanıcının PC'sinde çalışan bağımsız gateway'in 120 saniyelik tek kullanımlık eşleştirme kodu girilir; mobil oturum ve backend sağlık yanıtı doğrulanınca CANLI modu açılır. Gateway kaynağı bu Android deposunda veya APK içinde değildir; bağımsız kaynak ZIP/git bundle olarak teslim edilir.

**Yerel entegrasyon test edildi; gerçek telefon-PC bağlantısı bekliyor.**

### Product profile / research integration (development)

Requires matching Backend product-profile API and Gateway `strategy-profiles-v1`.
The analysis tab opens immutable per-account profiles; selecting a revision binds
that revision to the next analysis. Creation/revision needs an explicit
`profiles:write` mobile grant. Old sessions stay read-only; DEMO does not save
server profiles. Profile timeframes must be identical or strictly ordered; the
server remains the final validator. Arbitrary indicator tuning, risk changes and
automatic scheduling are not enabled. Lost write responses retain a frozen
command/selection for retry. Session/account changes remount the editor.

Result and detail screens display saved research_context patterns, formation /
confirmation times, volume confirmation and extra technical methods. Research is
descriptive, never trade permission or a win probability. Old/malformed/missing
records get explicit missing-data text; snapshot charts and WAIT level rules remain.

Development build based on0.7.2/11; no release, device validation, real push,
private PC connection or production deployment is claimed. Local checks:
143 Jest tests/36 suites,TypeScript,lint,17 local Expo compatibility checks and
Android bundle export passed. npm transitive dependency deprecation notices remain;
no broad dependency upgrade was mixed into this feature. Full online Expo Doctor
and native device/APK validation were not run for this increment.

M17 follow/scanner integration: scanner form can select an AUTO profile revision
(capability profile-scanner-v1, existing scanner:write plus AUTO account required).
Selection alone does not start scanning. Existing watch toggles preserve profile_id
and continue forcing auto_paper=false. New client requests include_profile=true
only with negotiated capability, keeping old Gateway calls unchanged. Follow
re-evaluations retain the originating revision in the Backend; Android does not
recalculate trading decisions. Broader signal TTL/new notification lifecycle and
profile-driven cadence are not claimed. Current local145tests/36suites,TypeScript,
lint,localdoctor and Android export PASS. Backend PR8/Gateway PR2/Android PR6.

Final response binding: selected profile analysis must return the exact requested
profile_record_id, or client rejects it as INVALID_RESPONSE and preserves the
uncertain request for reconciliation. Profile filter/validation/conflict reasons
are shown in Turkish. Final local146tests/36suites,TypeScript,lint and Android export
PASS; these do not constitute native-device or market performance validation.

Continuation4 M18: read-only equity history panel with real source-linked snapshots,
account/date filters and UTC day/week/month transaction periods. Stale/incomplete
marks never enter the chart. Drawdown covers observed complete snapshots since
capture began, not continuous/intrabar prices; no backfilled history or device-side
accounting. Fees/PnL/cash/reserves/strategy totals come from Backend. Rendering is
capability/read/account-gated; old Gateway shows unavailable. Latest200observations
are explicitly labeled; old checksum-only proof remains distinct after migration.
151Jest tests/37suites,TypeScript/lint and Android JS export passed locally.
First current-product APK (pre-M18) source92e4e3e/run41307683801/artifact13084058630
verified against actual previous certificate/manifests; physical installUNVERIFIED.
APK SHA256f88f6ae65582cd3019f24bfe13ded1617baa672e4416f57b2ec256dfd6f1349f.
Certificatefac61745dc0903786fb9ede62a962b399f7348f0bb6f899b8332667591033b9c
matches previous actual APK; no certificate stability assumed for future builds.
Package/version remaincom.fatihbirgul.tradeai/0.7.2/code11; no published release.

Final Continuation4: source availability notices are explicit/default-off; policy
UI requires the existing owner/scanner scope, preserves lost-response preference
and never starts a worker/push service. Expired pending records are not delivered.
Confirmed RSI14(SMA)/MACD12/26 divergence is descriptive, with actual pivot/known
and confirmation times; no new trade strategy or probability.155Jest tests and
6stdlib Python APK-evidence parser tests passed, plus typecheck/lint/doctor/export.
The APK workflow now emits APK_EVIDENCE.json from actual aapt2/apksigner outputs,
checks native package/version against source, ABI, CRC, embedded bundle and source
SHA. Certificate match with the verified previous artifact is measured/reported,
not assumed; no production key management added. Version stays0.7.2/code11 for this
internal build; installed-device update remainsUNVERIFIED. No uninstall/data wipe.

### Continuation 8 internal release candidate

Candidate metadata: **0.7.3 / versionCode12**, package
`com.fatihbirgul.tradeai`; existing internal signing policy is unchanged.
No physical-device install/update or SecureStore continuity claim is made.

The real compiled API client can be exercised through certificate-verified
loopback HTTPS with the sibling Backend/Gateway sources:

```sh
python ../trade-ai/backend/scripts/release_candidate_e2e.py --android . --gateway ../trade-ai-gateway --output /tmp/trade-ai-rc-acceptance.json
```

Run from clean checkouts with npm dependencies installed, Python3.11/3.12,
Backend test requirements, Gateway test dependencies, Node and OpenSSL. The
controller owns disposable databases and an ephemeral test CA, binds127.0.0.1
only and supplies no Backend administrator bearer to this client. Controlled
fixture prices exercise the live wire contract; they are not real market data.
No real worker, sender or automatic paper permission is activated.

The permanent acceptance/stack/Windows preparation report is maintained in
Backend`docs/RELEASE_CANDIDATE.md`; exact artifact/signature evidence in this
candidate's Draft PR body and APK artifact. Earlier APK evidence remains historical.
