# Broker readiness ana V3 promotion

11 Kasım 2026, Europe/Istanbul. Sonuç: **PROMOTION_PASS**, yalnız yerel fast-forward. Canlı runtime geçişi yapılmadı.

## Git recovery ve yöntem

Kök `%USERPROFILE%\trade-ai-v3-core`. Başlangıçta checkout temiz ve `codex/v3-broker-evidence-readiness` / `93c3382d20540ee40653c43176fac2974eedbb76` idi; bu önceki görevin beklenen durumudur. Hedef `codex/v3-real-readonly-analysis`, HEAD `09e5dab3bead337b3fab6a9267bbfe4fc16f3e7b`; staged/unstaged/untracked değişiklik yoktu. Başka hedef worktree yok; aynı checkout kaynak dalda zaten yeni dosyaları taşıyordu. P1 ayrı worktree'si `753ed59` olarak korundu.

Merge-base tam `09e5dab...`; ancestry başarılı; kaynak tek commit ileri. Recovery ref `refs/recovery/v3-broker-main-promotion-20261111-993349f665c2`, `09e5dab...` gösterir. Önceki recovery ref ve commit geçmişi korunur.

Kaynak kabulünden sonra hedef/kaynak SHA ve temizliği tekrar doğrulandı. Aynı checkout'taki Python dosyalarına dokunmadan hedef ref'i Git'in non-force fast-forward kontrolüyle güncellendi:

```powershell
git fetch --no-tags --no-write-fetch-head . refs/heads/codex/v3-broker-evidence-readiness:refs/heads/codex/v3-real-readonly-analysis
git switch codex/v3-real-readonly-analysis
```

`.` yalnız aynı yerel depodur; GitHub/network fetch veya uzak merge değildir. Git çıktısı `09e5dab..93c3382` fast-forward'dır. Force, merge commit, reset, stash, rebase veya cherry-pick yok. Kaynak ve hedef aynı commit olduğundan switch aynı tree üzerinde yapıldı. Önce/sonra 230 tracked dosyanın SHA256 **ve mtime_ns** değerleri birebir aynı; dosya değişimi sıfır. Ardından ana branch üzerinde bağımsız kabul tekrar çalıştırıldı. Sonraki yalnız belge commit'i ana dalda yereldir; full SHA son kullanıcı raporunda verilir.

## Gerçek kapsam

`09e5dab..93c3382`: 22 dosya, 1890 ekleme/16 çıkarma. Yedi üretim dosyası: yeni `forex/broker_contract.py`, `forex/spread_policy.py`; değişen `forex/providers.py`, `forex/core.py`, `forex/policy.py`, `forex/unified.py`, `forex/api.py`. Ayrıca 32 yeni test içeren `tests/test_broker_readiness.py`, üç QA aracı, dokümanlar, sanitize current observation ve dört onaysız policy taslağı. Bu promotion görevinde üretim koduna ek değişiklik yapılmadı.

Denetimde: exact dört c alias/USC; current metadata ile tarihsel trust ayrımı; contract size/tick/broker loss oracle; PRICE/POINTS ve effective dates; bounded provenance/version/approval; fail-closed ret; additive V5 contract/spread alanları; risk endpoint preflight; V2 descriptive-only korundu. Session importer/engine ve V2 kaynakları değişmedi. Yeni algoritma/strateji/formasyon yok.

## Auto-reload kabul kapısı

8006 PID 7532, global Python 3.11 executable; start 15:30:28, listen 15:30:29. Cwd ana V3; dolayısıyla bu klasör import kaynağı olabilir. Cwd veya disk hash'i loaded-module sürüm kanıtı sayılmadı. Parent zinciri: python -> py launcher -> elle açılmış PowerShell -> Explorer; child process yok. Reload CLI/reload-dir yok; UVICORN_RELOAD unset, WatchFiles polling override yok. İlgili watcher/supervisor process, Windows service veya scheduled task bulunmadı. Denetimin kendi PowerShell süreci watcher kelimeleri içerdiğinden ancestor olarak dışlandı; bağımsız watcher diye sayılmadı.

5173 Vite'ın React dosya izlemesi vardır; cwd `trade-ai-forex-web`, ana V3'ten ayrı. Vite config/source incelemesinde V3 root watcher/import bağlantısı bulunmadı; /engine yalnız HTTP proxy'dir. 8005/8007 aynı PWA klasöründe reload'suz uvicorn; parentları elle açılmış shell/launcher, child watcher yok. Ana V3 tracked dosyalarının hiç yazılmaması ayrıca koruma sağlar. Bu gözlenen CLI/env/process/service/task/config kapsamındaki yeterli risk değerlendirmesidir; bellekteki tüm modüllerin kriptografik ispatı değildir.

İnceleme için psutil 7.2.2 yalnız `%TEMP%\trade-ai-broker-promotion-20261111\inspection-lib` içine --target ile kuruldu. Global veya mevcut venv paketleri değiştirilmedi. Raw command line, keyfi env değerleri, hesap numarası/token/parola loglanmadı; yalnız güvenli kimlik ve reload booleans kaydedildi.

## Servis ve kabul ayrımı

Önce/sonra port PID/start/listen zamanları aynı: 5173/10320, 8005/2840, 8006/7532, 8007/12152. 8006/local proxy/Tailscale OpenAPI SHA256 aynı: `c6f59f0abf8a7d5807dda7e60a9ba384fcc07e1ba10253686df07a0164625bc9`. Yeni broker_contract/spread_status alanları hâlâ yok. 8006 şemasında veya süreç kimliklerinde promotion kaynaklı beklenmedik değişim gözlenmedi; servislere müdahale edilmedi.

Son koruma hash kontrolünde PWA `src/MarketChart.tsx` dış eşzamanlı değişiklik gösterdi. Bu görev PWA dosyasına yazmadı; main promotion anında 230 tracked V3 dosyası değişmemişti. Vite PWA klasörünü izlediği için bu dış frontend değişimi HMR doğurabilir; 5173 PID'sinin aynı kalması frontend belleğinin aynı olduğunu ispatlamaz. Canlı PWA kabulü bu nedenle ayrıca UNVERIFIED kalır. Güncel chart source eşlemesi salt okunur incelendi, AnalysisPanel guard/source kontrolleri tekrar 9/9 geçti. News/bridge dosyalarının başlangıç hash'lerinde değişiklik saptanmadı.

**Son dış süreç olayı (16:54:50 Europe/Istanbul gözlemi):** Dokümantasyon aşamasında 8005 dinleyicisi bir sorguda görünmedi; sonraki sorguda PID 9880, process start 16:54:32 / listen 16:54:34 olarak döndü. Önceki PID 2840 sonlandı. Yeni zincir python 9880 -> py 15772 -> aynı manuel PowerShell parent 12164. Bu görev 8005'e stop/restart/kill uygulamadı; yalnız ayrı QA Popen PID'leri kapatıldı. İşlem ana ref promotion'ından ve hedef testlerinden sonra gözlendi; promotion anında V3 tracked dosyaları yazılmamıştı. Son durumda dört servisin tümünün başlangıçtan beri aynı olduğu iddia edilmez. 5173/8006/8007 kimlikleri aynı kaldı. Olayı düzeltmek için otomatik servis müdahalesi yapılmadı; sonraki canlı kabulde bridge/API source tutarlılığı yeniden denetlenmeli.

| Durum | Sonuç | Kanıt |
|---|---|---|
| SOURCE_INTEGRATED | YES | Ana ref 09e5dab -> 93c3382, doğru checkout |
| LOCAL_TESTS_PASSED | YES | Kaynak/hedef: iki Python sürümünde ayrı 519/519 ve HTTP 63/63; PWA 9/9 |
| RUNTIME_VERSION_VERIFIED | OLD_VERSION, exact P1 loaded checkpoint UNVERIFIED | Çalışan şemada broker/spread alanları yok |
| LIVE_API_ACCEPTED | UNVERIFIED / yeni sürüm için kabul edilmedi | Eski API schema erişimi 200; yeni live deployment yok |
| LIVE_PWA_ACCEPTED | PARTIAL / yeni özellik kabulü UNVERIFIED | Transport/guard var, UI trust/pattern eksikleri sürüyor |

Dört spread rule maximum null/UNAPPROVED; max_allowed_price null, yeni işlem uygunluğu BLOCK kalır. Eski gözlenen 0.240/0.00008/0.00010/0.010 değerleri maksimum yapılmadı. Exact XAUUSDc 9 Kasım tarihsel quote session kanıtı BLOCKED_BY_EXTERNAL_EVIDENCE. REAL_READONLY_DATA, gerçek bakiye kullanılmaması ve execution_permission false korunur. Bu görev canlı MT5 veri/hesap/emir işlemi yapmadı.

Detaylı test matrisi `V3_BROKER_MAIN_TEST_RESULTS.md`, operasyon `V3_RUNTIME_CUTOVER_HANDOFF.md`, frontend `V3_PWA_FINAL_INTEGRATION_CHECKLIST.md` içinde. Push/Actions/remote merge yok; PWA/News/MT5 bridge/V2 yazımı yok.
