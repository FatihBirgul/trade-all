# Son mühürleme engeli: dış proxy değişikliği

11 Kasım 2026 21:55:25 İstanbul: orijinal PWA vite.config.ts dışarıdan /engine hedefini 8006 -> 8008 değiştirdi. 8008 PID 13988 yeni historical alanlı schema sunuyor; 5173 proxy artık bu schema'yı veriyor. 8006 PID 8284 aynı ve exact loaded sürümü VERSION_UNVERIFIED. Görev bu değişikliği yapmadı veya geri almadı. Son preflight BLOCKED; paket yalnız inceleme içindir (deployable=false). Aşağıdaki 8006 operasyon sırası uygulanamaz: önce yetkili backend/proxy hedefi uzlaştırılmalı, sonra manifest/backup ve uçtan uca kabul yeniden mühürlenmelidir. Yeni canlı operasyon onayı bu aşamada istenmiyor. Önceki başarılı kabul sonuçları test edilmiş adayın kanıtıdır; değişmiş canlı routing kabulü değildir.

# Güncel kontrollü geçiş: backend 56cbd7e + PWA RC 34c6ec2

Bu plan önceki 3c8adb8 geçiş talimatının yerini alır. Hazırlık bir canlı işlem
yetkisi değildir. Tek yeni kullanıcı onayı olmadan 8006 stop/start, PWA APPLY,
5173 HMR veya canlı rollback çalıştırılmaz. 8005/8007/Tailscale değişmez.

Backend exact SHA: `56cbd7e05a40b106deda9298e2be28b488d0d952`.
PWA UI RC SHA: `34c6ec2e1a02893cd1d8301d8bf6c5048c6aeb05`.
İzole repo son tooling SHA ve bütün paket dosyalarının hash'leri
`release/reconciled-56cbd7e/source-manifest.json` içindedir. UI payload değişmedi.
Eski ZIP korunmuştur ve bu operasyon için kullanılmaz.

## Hazır paket ve read-only preflight

Yeni ZIP: `release/TRADE_AI_V3_RECONCILED_56cbd7e_34c6ec2_BLOCKED_REVIEW.zip`.
Yanındaki `.sha256` arşiv hash'idir. Paket original PWA src/config/bridge
hash'lerini, current backend tracked hash'lerini, backend archive ve extracted
release'i, RC manifest/payload'ını, 27 dosyalık ön yedeği, eski baseline failback
kaynak/config'ini, V2 pin dosyalarını, araçları ve raporları içerir.
node_modules/venv, .env, credential, hesap numarası veya QA V2 Git history dahil
edilmez. Host'a özgü yollar değişirse yeni inceleme ve config hash'i gerekir.
ZIP gözden geçirme/geri kazanım paketidir; canlı PWA köküne topluca açılmaz.
Komutlar doğrulanmış izole PWA çalışma kökünde yürütülür.

```powershell
& '.artifacts/cutover/runtime-venv/Scripts/python.exe' -B tools/reconcile-release.py preflight
node tools/promotion-apply.mjs
```

İlk komut backend exact HEAD/clean status ve original/backend hash'lerini;
ikinci komut dokuz payload, 27 guard ve envanteri sıfır yazmayla doğrular.
Manifest/source/tool/config hash'lerini source-manifest ile ayrıca karşılaştır.
Drift veya beklenmeyen process/watchers varsa STOP; hash veya receipt tarihini
elle güncelleme. Snapshot/backup/seal seçenekleri yalnız izole release çıktısı
yazar. Eski orijinal PWA bir Git deposu değildir; ona Git işlemi uygulanmaz.

## Tek onaydan sonra uygulanacak sıra

1. O andaki 8006 PID/CreationDate/executable/parent/cwd/launch env, port sahibi,
   loaded kimlik, aktif hesap ve devam eden istekleri tekrar doğrula. Kayıtlı PID
   tek başına stop yetkisi değildir. Private config/rollback hash'lerini koru.
2. Yeni izin kapsamında yalnız exact doğrulanmış 8006 process ağacını kontrollü
   durdur; port başka sürece geçerse dur. 5173/8005/8007 süreçlerini hedefleme.
3. Yeni backend'i reload'suz, gizli pencereyle başlat. Config SHA'sını doğrulanmış
   source-manifest'ten al; UUID manifest yolu yeni olmalı. Aşağıdaki `<CONFIG_SHA>`
   placeholder'ını manifestin runtime-config.json hash'iyle değiştir:

```text
.artifacts/cutover/runtime-venv/Scripts/python.exe -B tools/cutover-runtime.py --release release/reconciled-56cbd7e/backend-56cbd7e --config release/reconciled-56cbd7e/runtime-config.json --config-sha256 <CONFIG_SHA> --manifest .artifacts/cutover/live-runtime-<UUID>.json --port 8006 --operator-approved-live
```

4. Yeni süreç manifestinde source/config/launcher, Python 3.11.9, NumPy 2.2.6,
   loaded function fingerprint, REAL_READONLY_DATA, Exness-MT5Real50/USC,
   execution=false doğrula. Startup production historical registry ve evidence
   inputs boşluğunu ayrıca zorunlu kılar. Bu kontrol broker onayı üretmez.
5. `node tools/cutover-live-accept.mjs --operator-approved <fresh-manifest-path>`
   ile yeni live receipt al. Güncellenen gate yalnız backend 56cbd7e kabul eder;
   dört sembolde SOURCE_NOT_SUPPLIED/unauthorized historical evidence ve
   UNAPPROVED spread BLOCK/null plan gerekir. Herhangi bir farklılıkta PWA APPLY yok.
6. Receipt 120 saniyeden gençken dokuz dosyayı aşağıdaki ayrı yetkili adımla uygula:

```text
node tools/promotion-apply.mjs --apply --operator-approved 1035c98420554d268c32f1a38bd0ed19379c18a67c53d93362edee216105b715 <fresh-backend-receipt-path>
```

Araç yeni UUID backup oluşturur; dependency dosyaları önce, App en son değişir.
Dokuz dosya bir bütün olarak atomik değildir; HMR/yenileme bakım onayının parçasıdır.
MarketChart exact hedef hash'iyle korunur; NewsPanel payload dışıdır.

## Rollback / failback

PWA smoke başarısızsa yalnız exact APPLY backup receipt'i ile:

```text
node tools/promotion-apply.mjs --rollback --operator-approved 1035c98420554d268c32f1a38bd0ed19379c18a67c53d93362edee216105b715 <exact-apply-backup-path>
```

Yeni backend başarısızsa yalnız yeni process kimliğiyle durdur; korunan V5Runtime
executable ve dondurulmuş eski baseline config/source ile
`tools/cutover-failback.py --port 8006 --manifest <new-UUID-path> --operator-approved-live`
başlat. Bu eski RAM'in birebir restore'u değildir; güvenli davranışı ayrı portta
doğrulanmış baseline reproduction'dır. Backup corruption/user drift varsa
otomatik overwrite yok; STOP/CONFLICT_REQUIRES_REVIEW. Bridge/news/global paket
değişikliği rollback çözümü değildir.

## Smoke ve fiziksel telefon kontrol listesi

- Health, local/proxy/Tailscale schema ve loaded startup manifest aynı backend'i göstermeli.
- Dört sembolde yalnız manuel Analyze; 10000 örnek sermaye açıkça hypothetical USC olmalı.
- Historical SOURCE_NOT_SUPPLIED ve spread UNAPPROVED/BLOCK; Entry/SL/TP/lot null,
  execution_permission=false. BUY/SELL zorunlu değildir.
- Candlestick/Double Top/Bottom varsa DESCRIPTIVE_ONLY; yoksa boş/unavailable durumu
  açık olmalı. NOT_EVALUATED emir onayı sayılmamalı.
- Gerçek telefonda HTTPS origin ve standalone mod, görünüm/taşma, dört sembol,
  symbol/race/timeout, eski sonucun temizlenmesi, chart ve NewsPanel kontrol edilmeli.
- SW/controller/asset sürümü yalnız bu origin'de doğrulanmalı; offline POST cache'ten
  dönmemeli. Origin dışı cache/storage temizlenmez.
- Fiziksel telefon testi bu hazırlıkta NOT_RUN; mobil browser viewport testi onun yerine geçmez.

Onay kapsamı yalnız 8006 kontrollü geçişi, dokuz PWA dosyasının güncellenmesi/HMR,
smoke ve gerektiğinde exact backup rollback/failback'tir. Hesap değişimi, spread
onayı, gerçek historical evidence approval veya emir gönderme kapsam dışındadır.
