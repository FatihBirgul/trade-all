# 8008 runtime uzlaştırması ve PWA release durumu

11 Kasım 2026. **BLOCKED_BACKEND_RUNTIME**. Onaylı 8008 proxy yönlendirmesi
doğru kabul edildi ve gerçek HTTP ile doğrulandı; önceki routing engeli giderildi.
Kalan engel exact loaded backend sürümünün aynı process'e ait güvenilir kanıtıdır.
Bu görev restart, proxy değişimi, HMR, APPLY veya canlı dosya yazımı yapmadı.

## A-D. Gerçek process ve yönlendirme

| Port | PID / rol | Cwd ve launch ortamı | Sürüm sonucu |
| --- | --- | --- | --- |
| 5173 | 10320 / original PWA Vite | trade-ai-forex-web, Program Files/nodejs/node.exe | /engine gerçekte 8008 schema'sını sunuyor |
| 8005 | 9880 / MT5 bridge | original PWA, global Python311 / py launcher | Mevcut bridge korunur |
| 8006 | 8284 / eski backend | main V3, V5Runtime launcher parent 11380 | Historical alanı olmayan eski schema; VERSION_UNVERIFIED |
| 8007 | 12152 / news | original PWA, global Python311 / py launcher | Mevcut news korunur |
| 8008 | 13988 / yeni V5 Forex API | trade-ai-v3-runtime-candidate; V5CandidateRuntime parent 3944 | V5 rolü doğrulandı, exact loaded SHA VERSION_UNVERIFIED |

8008 başlangıç 11 Kasım 21:44:26 Europe/Istanbul; plain `python -m uvicorn
forex.api:app`, inline wrapper yok, reload bayrağı/child watcher yok. Parent
V5CandidateRuntime/Scripts/python.exe; child exe global Python311 yolunda
görünmesi global dependency ortamı anlamına gelmez. Launch venv disk metadata'sı
NumPy 2.2.6, FastAPI 0.162.0, MetaTrader5 5.0.6231; bu eski RAM'deki her importun
load-anı kanıtı değildir. İzinli policy env REAL_READONLY_DATA /
Exness-MT5Real50 / USC. Hesap numarası, ham env veya command line kaydedilmedi.

Runtime candidate Git HEAD `56cbd7e05a40b106deda9298e2be28b488d0d952`, temiz.
Ana backend aynı SHA'da ve temiz. 8008 API'nin public content digest'i candidate
diskinden bağımsız interpreterda hesaplanan digest ile eşleşti. Public digest
dosya içeriklerini okuyarak üretildiğinden bu loaded-function-code attestation
değildir. Mevcut private aday manifestleri başka PID/ephemeral portlara aittir;
13988'e mal edilmedi. İlgili runtime checkout, launch şekli ve mevcut manifestler
incelendi; aynı process startup attestation bulunamadı. Sonuç VERSION_UNVERIFIED.

Original Vite `/engine -> http://127.0.0.1:8008`, prefix rewrite `/engine`'i
kaldırıyor. Disk config ve çalışan 5173 proxy aynı sonucu gösteriyor: canonical
schema SHA 8008 direct = 5173 proxy = Tailscale HTTPS proxy ve 8006 schema'sından
farklı. Analysis client göreli `/engine/api/v5/analysis` kullanır; backend URL'si
browser'da sabitlenmez. Analysis HTTP POST'tur; bu proxy için ws ayarı yoktur.
Orijinal veya Tailscale config'i değiştirilmedi. RC'nin service-worker POST
cache reddi önceki preview kabulünde doğrulandı; fiziksel cihaz/cache kabulü
bu görevde yapılmadı.

## E-H. Gerçek API, PWA ve yeni manifest

8008 direct + actual proxy/Tailscale kabulü **15/15 PASS**: health/schema,
old-schema ayrımı, order-route bulunmaması, disk/actual proxy8008 ve dört exact
sembol metadata/analysis kontrol grubu. Gerçek HTTP yanıtlarında:

- XAUUSDc/EURUSDc/GBPUSDc/USDJPYc; Exness-MT5Real50 ve USC metadata eşleşmesi.
- REAL_READONLY_DATA bağlamı, HYPOTHETICAL_CAPITAL, execution_permission=false.
- CURRENT_MT5_OBSERVED broker contract; INSUFFICIENT_DATA/BLOCKED, null plan/lot.
- Spread **UNVERIFIED / BLOCK**, maximum null: policy onayı/konfigürasyonu yok.
  Önceki adayın UNAPPROVED template durumuyla aynı etiket değildir; ikisi de
  onaysız ve güvenli ret durumudur. Limit uydurulmadı, live env değiştirilmedi.
- Historical SOURCE_NOT_SUPPLIED / historical_gap_authorized=false.
- V2 pattern context QC nedeniyle null/unavailable olabilir; oluşum uydurulmaz.

42 API/client tekrar PASS; ayrıca gerçek dört 8008 yanıtı ve historical additive
alanı olmayan eşdeğerlerinin RC parser kabulü **2/2 PASS**. New response tüketimi
legacy BUY/SELL/WAIT matematiğini veya risk kapılarını değiştirmez. UI src/public,
package ve Vite RC kaynakları değişmedi; UI payload SHA hâlâ
`34c6ec2e1a02893cd1d8301d8bf6c5048c6aeb05` kaynak kodudur.

Yeni RC klasörü `release/runtime8008-56cbd7e`. Eski BLOCKED manifest/ZIP
değiştirilmedi. Yeni manifest 9 exact allowlisted frontend dosyasını, source ve
current destination SHA-256'larını, 27 güncel guard'ı, proxy8008 kimliğini,
backend expected SHA'yı, prerequisites ve deployable=false bilgisini taşır.
NewsPanel ve proxy payload dışındadır. MarketChart yalnız incelenmiş exact
hash ile aday listede kalır. Yeni yedek, mevcut onaylı 8008 config'ini korur;
8006 config'ine geri dönmez.

## I-M. Test, dry-run ve backup

| Kontrol | Sonuç / tekrar kapsamı |
| --- | --- |
| Backend 600 / Python 3.11 ve 3.13 | Önceki exact 56cbd7e archive kabulü 600/600, iki sürümde; backend değişmediği için bu görevde tekrar edilmedi |
| HTTP 63 / historical HTTP14 / baseline PWA9 | Önceki mühürlü kabul iki interpreter'da PASS; port/view auditinden ayrı referans |
| RC API/client | Bu görevde 42/42 PASS |
| Actual8008 RC parser | Bu görevde 2/2 PASS |
| Yeni route/version/no-order + backup rehearsal | Bu görevde 9/9 PASS |
| TypeScript / production build / full ESLint | Bu görevde PASS |
| RC browser 34 / production preview-cache3 | Önceki başarılı 34/34 ve 3/3 kullanıldı; UI/runner byte'ları değişmedi, tekrar edilmedi |
| Actual8008 / proxy HTTP | Bu görevde 15/15 PASS; fixture değildir |
| Yeni dokuz dosyalı dry-run | PASS, writes=0 / deletes=0 / guards27; runtime gate BLOCKED |
| Yeni backup / fixture restore | 27 dosya hash'i PASS; nine-file apply/restore yalnız .artifacts sahte hedefte |

9 yeni Python testi yanlış proxy, 8006 eski schema'sının yeni sayılması, proxy
mismatch, yanlış source SHA, public-disk/JSON ile loaded version yükseltilememesi,
real-balance/execution/lot/spread/historical negatifleri, sıfır yazma dry-run ve
backup/restore'u kapsar. Sentetik fixture/restore başarısı gerçek runtime SHA
doğrulaması değildir. Test sayıları benzersiz toplam diye toplanmaz.

İlk API checker UNAPPROVED bekledi; canlı gerçek UNVERIFIED/BLOCK olduğundan
durdu. İki onaysız statü yalnız BLOCK + null max koşuluyla kabul edildi; PASS
negatif testi korunur. Ardından nullable pattern context checker'da None hatası
görüldü; doğru nullable wire şekli desteklendi. Son 15/9/2 kabul koşulları geçti.
Bu araç düzeltmeleri production backend veya PWA parser değişikliği değildir.

## N-R. Teslim, koruma ve sonraki adım

Yeni ZIP: `release/TRADE_AI_V3_PWA_8008_56cbd7e_BLOCKED_RUNTIME.zip`.
Source manifest: `release/runtime8008-56cbd7e/source-manifest.json`; final tooling
commit SHA burada ve teslim yanıtındadır. Paket current8008 manifest/payload,
27-file backup, read-only araç/test/rapor, proxy/runtime ve API kanıtlarını içerir.
Eski manifest/ZIP yeniden etiketlenmez. Archive CRC ve bütün dosya hash'leri
kontrol edilir. Backend deployment payload'ı yoktur; 8006 deployment hedefi değildir.

Read-only tekrar komutları (izole PWA cwd):

```text
python -B tools/runtime8008-preflight.py accept
python -B tools/runtime8008-preflight.py dry-run
python -B tests/runtime8008_test.py
npm test
node --test tests/runtime8008-client.test.mjs
```

Python mevcut `.artifacts/cutover/runtime-venv/Scripts/python.exe` anlamındadır.
Yeni araç APPLY/restart uygulamaz. `stage` mevcut klasörü overwrite etmez;
`seal` yeni archive'i exclusive oluşturur. Source/target drift güvenli ret üretir.

PID'ler 5173=10320, 8005=9880, 8006=8284, 8007=12152, 8008=13988 korundu.
Source snapshot orijinal config dahil güncel 8008 düzenine göre alındı; main ve
orijinale yazılmadı. Yalnız izole repo yerel commit'i; push/merge yok.

Talimat M7: doğrulanamayan runtime sürümünde BLOCKED_BACKEND_RUNTIME. Dolayısıyla
şimdi PWA APPLY onayı istenmez. Önce 13988'e ait güvenilir same-process loaded
source kaydı bulunmalı; yoksa bunun edinileceği ayrı yetkili operasyon planlanmalı.
Bu görev bunun için 8008 restart veya endpoint ekleme yetkisi kullanmaz.
Bu kapı daha sonra sağlanırsa sonraki tek onay yalnız dokuz PWA dosyası transferi,
Vite HMR/cache/UI smoke ve exact backup rollback olur; 8006 restart planlanmaz.

## Beş net cevap

1. 8008 doğrulanmış V5 backend mi? **YES**, rol/API/güvenli davranış doğrulandı.
2. 5173 /engine gerçekten 8008'e gidiyor mu? **YES**.
3. 8008 exact 56cbd7e sürümünü mü çalıştırıyor? **UNVERIFIED**; disk/public digest
   uyumlu, loaded-code kanıtı yok.
4. PWA RC mevcut 8008 ile uyumlu mu? **YES, HTTP/client sözleşmesi bakımından**.
5. Güvenli canlı PWA aktarımına hazır mı? **NO — BLOCKED_BACKEND_RUNTIME**.
